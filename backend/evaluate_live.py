"""Opt-in live evaluation using synthetic briefs; never substitutes demo output."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter, monotonic, sleep
from datetime import datetime, timezone
from importlib.metadata import version
import zipfile

CASES = [
    ("onboarding", "Employee Onboarding",
     "Build an employee onboarding portal. HR registers new joiners with name, "
     "work email, start date and department. Managers approve or request changes. "
     "IT tracks equipment and application access provisioning after approval."),
    ("purchasing", "Office Supply Purchasing",
     "Build an office supply purchase request application. Employees enter item "
     "description, quantity, required date and cost centre. Managers approve or "
     "request changes. Operations tracks ordering, delivery and receipt after approval."),
    ("facilities", "Facilities Maintenance",
     "Build a facilities maintenance request portal. Staff enter building, room, "
     "issue description, contact email and preferred service date. Facilities leads "
     "approve or request changes. Technicians track inspection, repair and completion."),
    ("training", "Training Enrollment",
     "Build an employee training enrollment portal. Staff enter course name, "
     "course date, department and work email. Team leads approve or request changes. "
     "Learning coordinators track booking confirmation, attendance and completion."),
]


class EvaluationFailure(RuntimeError):
    pass


class EvaluationQuotaFailure(EvaluationFailure):
    pass


class RequestPacer:
    def __init__(self, requests_per_minute):
        self.interval = 60 / requests_per_minute
        self.last_started = None
        self.calls = 0

    def wait(self):
        if self.last_started is not None:
            delay = self.interval - (monotonic() - self.last_started)
            if delay > 0:
                sleep(delay)
        self.last_started = monotonic()
        self.calls += 1


def check(condition, message):
    if not condition:
        raise EvaluationFailure(message)


def request(client, method, path, expected=200, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code == 429 and expected != 429:
        raise EvaluationQuotaFailure(
            "Google AI quota/rate limit reached; evaluation stopped without retrying. "
            "Check Google AI Studio limits and wait before starting a fresh run.")
    # Do not persist arbitrary upstream error bodies, which may contain credentials.
    check(response.status_code == expected,
          f"{method} {path}: expected HTTP {expected}, got {response.status_code}")
    return response


def evaluate_case(client, provider, case, folder, pacer=None):
    slug, title, brief = case
    started = perf_counter()
    result = {"case": slug, "brief": brief, "status": "failed", "stages_seconds": {},
              "human_usefulness_review": "pending",
              "limitations": ["Checklist actions remain equipment/access/welcome templates, "
                              "not domain-specific fulfilment. Browser UX is not evaluated."]}
    p = None
    try:
        p = request(client, "POST", "/api/projects", expected=201,
                    json={"title": title, "brief": brief}).json()
        base = f"/api/projects/{p['id']}"
        result["project_id"] = p["id"]
        request(client, "POST", base + "/stories/generate", expected=409)
        request(client, "POST", base + "/prototype/generate", expected=409)
        request(client, "GET", base + "/export", expected=409)
        for endpoint, gate, version_key in [
            ("requirements/analyze", "g0", "requirements_version"),
            ("stories/generate", "g1", "stories_version"),
            ("prototype/generate", "g2", "prototype_version"),
        ]:
            if pacer is not None:
                pacer.wait()
            stage_start = perf_counter()
            p = request(client, "POST", base + "/" + endpoint).json()
            result["stages_seconds"][endpoint] = round(perf_counter() - stage_start, 3)
            if gate == "g0":
                ids = [r["id"] for r in p["requirements"]]
                check(ids and len(ids) == len(set(ids)), "Missing or duplicate requirements")
                check(all(r["source_id"] == "SRC-001" for r in p["requirements"]),
                      "Requirement provenance references an unavailable source")
            elif gate == "g1":
                ids = {r["id"] for r in p["requirements"]}
                covered = {rid for s in p["stories"] for rid in s["requirement_ids"]}
                check(covered == ids, "Stories must cover 100% of requirements with valid IDs")
                check(all(all(re.search(r"\b" + word + r"\b", c, re.I)
                              for word in ("Given", "When", "Then"))
                          for s in p["stories"] for c in s["acceptance_criteria"]),
                      "Acceptance criteria lack Given/When/Then")
                result["traceability_coverage"] = len(covered) / len(ids)
            else:
                check(p["prototype_provider"] == provider, "Non-live prototype detected")
                check([s["kind"] for s in p["prototype"]["screens"]] ==
                      ["intake", "approval", "checklist"], "Incorrect screen sequence")
                check(len(p["prototype"]["concepts"]) == 2, "Expected two concepts")
                values = {}
                fields = p["prototype"]["screens"][0]["fields"]
                check(bool(fields), "Intake has no fields")
                for field in fields:
                    if field["type"] == "select":
                        check(bool(field["options"]), "Select has no options")
                        value = field["options"][0]
                    else:
                        value = {"date": "2026-11-07", "email": "synthetic@example.com"}.get(
                            field["type"], "Synthetic evaluation value")
                    values[field["id"]] = value
                p = request(client, "POST", base + "/demo/actions",
                            json={"action": "submit", "values": values}).json()
                rid = p["demo_requests"][-1]["id"]
                request(client, "POST", base + "/demo/actions", expected=409,
                        json={"action": "toggle", "request_id": rid, "item": "Equipment assigned"})
                p = request(client, "POST", base + "/demo/actions",
                            json={"action": "approve", "request_id": rid}).json()
                check(p["demo_requests"][-1]["status"] == "approved", "Approval action failed")
                for item in p["demo_requests"][-1]["checklist"]:
                    p = request(client, "POST", base + "/demo/actions",
                                json={"action": "toggle", "request_id": rid, "item": item}).json()
                check(all(p["demo_requests"][-1]["checklist"].values()), "Checklist action failed")
                p = request(client, "POST", base + "/demo/actions",
                            json={"action": "submit", "values": values}).json()
                rid = p["demo_requests"][-1]["id"]
                p = request(client, "POST", base + "/demo/actions",
                            json={"action": "request_changes", "request_id": rid}).json()
                check(p["demo_requests"][-1]["status"] == "changes_requested",
                      "Request-changes action failed")
                request(client, "POST", base + "/demo/actions", expected=409,
                        json={"action": "approve", "request_id": rid})
                request(client, "GET", base + "/export", expected=409)
            p = request(client, "POST", base + "/approvals/" + gate,
                        json={"artifact_version": p[version_key], "decision": "approved",
                              "note": "Automated synthetic evaluation ONLY; not human approval."}).json()
        output = request(client, "GET", base + "/export").content
        with zipfile.ZipFile(io.BytesIO(output)) as archive:
            check({"requirements.md", "stories.md", "acceptance.feature", "prototype.json",
                   "traceability.json", "approvals.json", "audit.json"} <= set(archive.namelist()),
                  "Incomplete engineering handoff")
            check(json.loads(archive.read("prototype.json")) == p["prototype"],
                  "Exported prototype differs from approved prototype")
            mappings = json.loads(archive.read("traceability.json"))["mappings"]
            check(mappings == [{"story_id": s["id"], "requirement_ids": s["requirement_ids"]}
                               for s in p["stories"]], "Exported traceability differs")
        (folder / f"{slug}-handoff.zip").write_bytes(output)
        result.update(status="passed", requirement_count=len(p["requirements"]),
                      story_count=len(p["stories"]))
    except EvaluationFailure as exc:
        result["error"] = str(exc)
        result["error_kind"] = "quota" if isinstance(exc, EvaluationQuotaFailure) else "validation"
    finally:
        result["seconds"] = round(perf_counter() - started, 3)
        if p is not None:
            p = request(client, "GET", f"/api/projects/{p['id']}").json()
            (folder / f"{slug}-project.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
        (folder / f"{slug}-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["gemini", "adk", "both"], default="gemini")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--case", choices=[case[0] for case in CASES], default="purchasing")
    selection.add_argument("--all-cases", action="store_true")
    parser.add_argument("--requests-per-minute", type=positive_integer, default=5,
                        help="Local pacing target, not a claim about your Google quota (default: 5)")
    parser.add_argument("--model", default=os.getenv("KATALYST_GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--plan", action="store_true",
                        help="Show planned calls without credentials, network calls or output files")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = CASES if args.all_cases else [case for case in CASES if case[0] == args.case]
    providers = ["gemini", "adk"] if args.provider == "both" else [args.provider]
    plan = {"providers": providers, "model": args.model, "cases": [case[0] for case in cases],
            "planned_generation_calls": 3 * len(cases) * len(providers),
            "requests_per_minute": args.requests_per_minute,
            "automatic_retries": 0,
            "billing_notice": "Free only for an eligible model/project within free-tier limits. "
                              "This runner cannot verify billing tier or guarantee zero cost.",
            "privacy_notice": "Synthetic data only; free-tier content may improve Google products."}
    print(json.dumps(plan, indent=2), flush=True)
    if args.plan:
        return 0
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or
            (os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true" and
             os.getenv("GOOGLE_CLOUD_PROJECT"))):
        parser.error("Configure a local API key or Vertex AI/ADC before live evaluation")
    if args.provider == "both":
        for index, provider in enumerate(providers):
            if index:
                sleep(60 / args.requests_per_minute)
            command = [sys.executable, str(Path(__file__).resolve()), "--provider", provider,
                       "--output", str(args.output), "--model", args.model,
                       "--requests-per-minute", str(args.requests_per_minute)]
            command += ["--all-cases"] if args.all_cases else ["--case", args.case]
            code = subprocess.run(command).returncode
            if code:
                print(f"Stopped after {provider} failed (exit {code}); no further providers started.")
                return code
        return 0
    os.environ["KATALYST_AI_PROVIDER"] = args.provider
    os.environ["KATALYST_AUTH_MODE"] = "demo"
    os.environ["KATALYST_GEMINI_MODEL"] = args.model
    os.environ["KATALYST_STORE"] = "sqlite"
    folder = args.output.resolve() / args.provider
    folder.mkdir(parents=True, exist_ok=True)
    check(not (folder / "evaluation.sqlite").exists(),
          "Output already contains an evaluation; choose a fresh directory")
    os.environ["KATALYST_DB"] = str(folder / "evaluation.sqlite")
    from fastapi.testclient import TestClient
    from app.main import app
    from app import ai
    with TestClient(app) as client:
        config = request(client, "GET", "/api/config").json()
        check(config["provider"] == args.provider and config["is_live_ai"],
              "Live provider not active")
        results = []
        pacer = RequestPacer(args.requests_per_minute)
        for case in cases:
            if results and results[-1].get("error_kind") == "quota":
                break
            results.append(evaluate_case(client, args.provider, case, folder, pacer))
    skipped = [case[0] for case in cases[len(results):]]
    report = {"at": datetime.now(timezone.utc).isoformat(), "provider": args.provider,
              "model": ai.MODEL_ID, "sdk_versions": {name: version(name) for name in
                                                   ("google-genai", "google-adk")},
              "passed": sum(r["status"] == "passed" for r in results),
              "attempted": len(results), "cases": results, "skipped_cases": skipped,
              "plan": plan, "generation_calls_attempted": pacer.calls,
              "human_usefulness_review": "pending; mechanical success is not a quality verdict"}
    (folder / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{args.provider}: {report['passed']}/{report['attempted']} mechanical checks passed; "
          f"human review pending. Report: {folder / 'report.json'}")
    if any(result.get("error_kind") == "quota" for result in results):
        return 3
    return int(report["passed"] != report["attempted"])


if __name__ == "__main__":
    sys.exit(main())
