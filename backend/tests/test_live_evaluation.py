import asyncio
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app import ai
from app.main import app
from app.models import Analysis, PrototypeSpec, StorySet
from evaluate_live import CASES, evaluate_case
import evaluate_live


@pytest.mark.parametrize("case", CASES, ids=[case[0] for case in CASES])
def test_evaluation_journey_with_mocked_live_outputs(tmp_path, monkeypatch, case):
    monkeypatch.setenv("KATALYST_DB", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("KATALYST_STORE", "sqlite")
    monkeypatch.setattr(ai, "PROVIDER", "gemini")
    brief = case[2]
    analysis = ai._make_requirements(brief, [])

    async def structured(prompt, schema):
        if schema is Analysis:
            return analysis
        if schema is StorySet:
            return StorySet(stories=[
                {"id": f"US-{i:03d}", "requirement_ids": [r.id], "role": "reviewer",
                 "goal": r.text, "benefit": "track progress",
                 "acceptance_criteria": ["Given a request\nWhen reviewed\nThen record the outcome"]}
                for i, r in enumerate(analysis.requirements, 1)])
        assert schema is PrototypeSpec
        return ai._default_prototype(brief, [])

    monkeypatch.setattr(ai, "_structured", structured)
    pacer = SimpleNamespace(wait=Mock())
    with TestClient(app) as client:
        result = evaluate_case(client, "gemini", case, tmp_path, pacer)
    assert result["status"] == "passed", result
    assert result["traceability_coverage"] == 1
    assert result["human_usefulness_review"] == "pending"
    assert (tmp_path / f"{case[0]}-handoff.zip").exists()
    assert json.loads((tmp_path / f"{case[0]}-result.json").read_text()) == result
    assert pacer.wait.call_count == 3


def test_evaluation_records_failed_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("KATALYST_DB", str(tmp_path / "failed.sqlite"))
    monkeypatch.setenv("KATALYST_STORE", "sqlite")
    monkeypatch.setattr(ai, "PROVIDER", "gemini")
    monkeypatch.setattr(ai, "_structured", AsyncMock(side_effect=RuntimeError("Model unavailable")))
    with TestClient(app) as client:
        result = evaluate_case(client, "gemini", CASES[1], tmp_path)
    assert result["status"] == "failed"
    assert "got 502" in result["error"]
    assert not (tmp_path / "purchasing-handoff.zip").exists()
    assert (tmp_path / "purchasing-project.json").exists()


def test_live_prototype_failure_does_not_create_template(tmp_path, monkeypatch):
    monkeypatch.setenv("KATALYST_DB", str(tmp_path / "failure.sqlite"))
    monkeypatch.setenv("KATALYST_STORE", "sqlite")
    monkeypatch.setattr(ai, "PROVIDER", "demo")
    with TestClient(app) as client:
        p = client.post("/api/projects", json={"title": CASES[1][1], "brief": CASES[1][2]}).json()
        base = f"/api/projects/{p['id']}"
        p = client.post(base + "/requirements/analyze").json()
        client.post(base + "/approvals/g0",
                    json={"artifact_version": p["requirements_version"], "decision": "approved"})
        p = client.post(base + "/stories/generate").json()
        client.post(base + "/approvals/g1",
                    json={"artifact_version": p["stories_version"], "decision": "approved"})
        monkeypatch.setattr(ai, "PROVIDER", "adk")
        monkeypatch.setattr(ai, "_structured", AsyncMock(side_effect=RuntimeError("Model unavailable")))
        response = client.post(base + "/prototype/generate")
        assert response.status_code == 502
        p = client.get(base).json()
        assert p["prototype"] is None
        assert p["prototype_version"] == 0
        assert "g2" not in p["approvals"]


@pytest.mark.parametrize("invalid", ["sequence", "empty-options", "duplicate-fields"])
def test_invalid_live_prototype_is_rejected(monkeypatch, invalid):
    spec = ai._default_prototype(CASES[0][2], [])
    if invalid == "sequence":
        spec.screens.reverse()
    elif invalid == "empty-options":
        spec.screens[0].fields[-1].options = []
    else:
        spec.screens[0].fields[1].id = spec.screens[0].fields[0].id
    monkeypatch.setattr(ai, "PROVIDER", "gemini")
    monkeypatch.setattr(ai, "_structured", AsyncMock(return_value=spec))
    with pytest.raises(ValueError):
        asyncio.run(ai.prototype(CASES[0][2], []))


def test_sdk_error_is_explicit_without_secret_message(monkeypatch):
    from google.genai.errors import ClientError
    monkeypatch.setattr(ai, "PROVIDER", "gemini")
    monkeypatch.setattr(ai, "_structured_live",
                        AsyncMock(side_effect=ClientError(403, {"message": "SECRET"})))
    with pytest.raises(RuntimeError, match="HTTP 403") as error:
        asyncio.run(ai._structured("synthetic", Analysis))
    assert "SECRET" not in str(error.value)


def test_gemini_adapter_validates_response_and_closes_client(monkeypatch):
    from google import genai
    analysis = ai._make_requirements(CASES[1][2], [])
    aio = SimpleNamespace(
        models=SimpleNamespace(generate_content=AsyncMock(
            return_value=SimpleNamespace(parsed=analysis.model_dump()))),
        aclose=AsyncMock())
    client_options = {}

    def factory(**kwargs):
        client_options.update(kwargs)
        return SimpleNamespace(aio=aio)
    monkeypatch.setattr(genai, "Client", factory)
    monkeypatch.setattr(ai, "PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert asyncio.run(ai._structured("synthetic", Analysis)) == analysis
    aio.aclose.assert_awaited_once()
    assert client_options["http_options"].retry_options.attempts == 1


@pytest.mark.parametrize("schema", [Analysis, PrototypeSpec])
def test_adk_runner_uses_typed_stage_output(monkeypatch, schema):
    from google.adk.models import google_llm
    from google.genai import types
    output = (ai._make_requirements(CASES[1][2], []) if schema is Analysis
              else ai._default_prototype(CASES[1][2], []))
    response = types.GenerateContentResponse(candidates=[
        types.Candidate(content=types.Content(
            role="model", parts=[types.Part(text=output.model_dump_json())]),
            finish_reason="STOP")])
    generate = AsyncMock(return_value=response)
    client = SimpleNamespace(vertexai=False,
                             aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    client_options = {}

    def factory(**kwargs):
        client_options.update(kwargs)
        return client

    monkeypatch.setattr(google_llm, "Client", factory)
    monkeypatch.setattr(ai, "PROVIDER", "adk")
    assert asyncio.run(ai._structured("synthetic", schema)) == output
    generate.assert_awaited_once()
    assert generate.call_args.kwargs["config"].response_schema is schema
    assert client_options["http_options"].retry_options.attempts == 1


def test_prototype_schema_is_supported_by_installed_genai_sdk():
    from google import genai
    from google.genai import _transformers
    with genai.Client(api_key="synthetic-test-key", vertexai=False) as client:
        schema = _transformers.t_schema(client._api_client, PrototypeSpec)
    assert schema.properties["concepts"].items.properties["primaryColor"] is not None
    wire_schema = schema.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert "additionalProperties" not in json.dumps(wire_schema)
    assert "additional_properties" not in json.dumps(wire_schema)
    fields = schema.properties["screens"].items.properties["fields"].items
    assert fields.properties["type"].enum == ["text", "date", "select", "email"]
    assert schema.properties["screens"].min_items == 3
    assert schema.properties["screens"].max_items == 3


def test_prototype_still_rejects_unexpected_field_properties():
    prototype = ai._default_prototype(CASES[1][2], []).model_dump()
    prototype["screens"][0]["fields"][0]["unexpected"] = "not allowed"
    with pytest.raises(ValidationError) as error:
        PrototypeSpec.model_validate(prototype)
    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_gemini_prototype_response_is_validated_locally(monkeypatch):
    from google import genai
    prototype = ai._default_prototype(CASES[1][2], []).model_dump()
    prototype["screens"][0]["fields"][0]["unexpected"] = "not allowed"
    aio = SimpleNamespace(
        models=SimpleNamespace(generate_content=AsyncMock(
            return_value=SimpleNamespace(parsed=None, text=json.dumps(prototype)))),
        aclose=AsyncMock())
    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(aio=aio))
    monkeypatch.setattr(ai, "PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-test-key")
    with pytest.raises(ValidationError):
        asyncio.run(ai._structured("synthetic", PrototypeSpec))
    aio.aclose.assert_awaited_once()


def test_pacer_spaces_generation_starts_without_unnecessary_waits(monkeypatch):
    clock = [0.0]
    waits = []
    monkeypatch.setattr(evaluate_live, "monotonic", lambda: clock[0])

    def fake_sleep(seconds):
        waits.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(evaluate_live, "sleep", fake_sleep)
    pacer = evaluate_live.RequestPacer(5)
    pacer.wait()
    clock[0] += 2
    pacer.wait()
    pacer.wait()
    assert waits == [10, 12]
    clock[0] += 30
    pacer.wait()
    assert waits == [10, 12]
    assert pacer.calls == 4


@pytest.mark.parametrize("endpoint,prerequisites", [
    ("requirements/analyze", []),
    ("stories/generate", [("requirements/analyze", "g0", "requirements_version")]),
    ("prototype/generate", [("requirements/analyze", "g0", "requirements_version"),
                            ("stories/generate", "g1", "stories_version")]),
])
def test_quota_returns_429_without_changing_artifacts(
        tmp_path, monkeypatch, endpoint, prerequisites):
    from google.genai.errors import ClientError
    monkeypatch.setenv("KATALYST_DB", str(tmp_path / "quota.sqlite"))
    monkeypatch.setenv("KATALYST_STORE", "sqlite")
    monkeypatch.setattr(ai, "PROVIDER", "demo")
    with TestClient(app) as client:
        p = client.post("/api/projects", json={"title": CASES[1][1], "brief": CASES[1][2]}).json()
        base = f"/api/projects/{p['id']}"
        for stage, gate, version_key in prerequisites:
            p = client.post(base + "/" + stage).json()
            assert client.post(base + "/approvals/" + gate, json={
                "artifact_version": p[version_key], "decision": "approved"}).status_code == 200
        before = client.get(base).json()
        monkeypatch.setattr(ai, "PROVIDER", "gemini")
        model_call = AsyncMock(side_effect=ClientError(429, {"message": "SECRET"}))
        monkeypatch.setattr(ai, "_structured_live", model_call)
        response = client.post(base + "/" + endpoint)
        assert response.status_code == 429
        assert "No automatic retry" in response.text
        assert "SECRET" not in response.text
        assert client.get(base).json() == before
        model_call.assert_awaited_once()


def test_evaluation_stops_remaining_cases_on_quota(tmp_path, monkeypatch):
    from google.genai.errors import ClientError
    monkeypatch.setattr(sys, "argv", ["evaluate_live.py", "--all-cases", "--output", str(tmp_path)])
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(ai, "PROVIDER", "gemini")
    model_call = AsyncMock(side_effect=ClientError(429, {"message": "SECRET"}))
    monkeypatch.setattr(ai, "_structured_live", model_call)
    assert evaluate_live.main() == 3
    report = json.loads((tmp_path / "gemini" / "report.json").read_text())
    assert report["attempted"] == 1
    assert report["passed"] == 0
    assert report["generation_calls_attempted"] == 1
    assert report["skipped_cases"] == ["purchasing", "facilities", "training"]
    assert report["cases"][0]["error_kind"] == "quota"
    assert "SECRET" not in json.dumps(report)
    model_call.assert_awaited_once()


@pytest.mark.parametrize("extra,expected_calls,providers,cases", [
    ([], 3, ["gemini"], ["purchasing"]),
    (["--provider", "adk", "--case", "training"], 3, ["adk"], ["training"]),
    (["--provider", "both", "--all-cases"], 24, ["gemini", "adk"],
     ["onboarding", "purchasing", "facilities", "training"]),
])
def test_plan_is_credential_free_and_does_not_write_files(
        tmp_path, monkeypatch, capsys, extra, expected_calls, providers, cases):
    output = tmp_path / "not-created"
    monkeypatch.setattr(sys, "argv", ["evaluate_live.py", "--plan", "--output", str(output)] + extra)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    model_call = AsyncMock()
    monkeypatch.setattr(ai, "_structured_live", model_call)
    assert evaluate_live.main() == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["planned_generation_calls"] == expected_calls
    assert plan["providers"] == providers
    assert plan["cases"] == cases
    assert plan["automatic_retries"] == 0
    assert not output.exists()
    model_call.assert_not_awaited()


@pytest.mark.parametrize("value", ["0", "-1", "nan", "1.5"])
def test_invalid_pacing_is_rejected(tmp_path, monkeypatch, value):
    monkeypatch.setattr(sys, "argv", ["evaluate_live.py", "--plan", "--output", str(tmp_path),
                                     "--requests-per-minute", value])
    with pytest.raises(SystemExit) as error:
        evaluate_live.main()
    assert error.value.code == 2


@pytest.mark.parametrize("first_code,expected_providers", [(0, ["gemini", "adk"]), (3, ["gemini"])])
def test_both_providers_share_selection_and_stop_on_failure(
        tmp_path, monkeypatch, first_code, expected_providers):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(sys, "argv", ["evaluate_live.py", "--provider", "both", "--case", "training",
                                     "--requests-per-minute", "2", "--model", "selected-model",
                                     "--output", str(tmp_path)])
    commands = []
    waits = []

    def run(command):
        commands.append(command)
        return SimpleNamespace(returncode=first_code)

    monkeypatch.setattr(evaluate_live.subprocess, "run", run)
    monkeypatch.setattr(evaluate_live, "sleep", waits.append)
    assert evaluate_live.main() == first_code
    assert [cmd[cmd.index("--provider") + 1] for cmd in commands] == expected_providers
    for cmd in commands:
        assert cmd[cmd.index("--case") + 1] == "training"
        assert cmd[cmd.index("--requests-per-minute") + 1] == "2"
        assert cmd[cmd.index("--model") + 1] == "selected-model"
    assert waits == ([30] if first_code == 0 else [])
