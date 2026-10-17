# KATALYST — Prototype + SaaS Foundation

**Milestone 1 added:** Firebase email/password registration and login, Google
sign-in, persistent sessions, protected per-user projects, a project dashboard,
metadata wizard and saved-stage resume. The existing React/FastAPI application
and prototype gates are preserved. **The full SRS-to-Jira platform is not yet
implemented.**

Start with [Foundation setup](docs/FOUNDATION_SETUP.md) for Firebase/Firestore
configuration, modules, data model, workflow states and remaining milestones.
The default backend authentication mode is now **Firebase** (and Firestore is its
default store). Demo/live-AI launchers explicitly select the labeled local demo
identity and SQLite; they are not production login.

**Human Expertise. AI-Powered Execution.**

An end-to-end **requirements-to-prototype** demonstration for the **Future of Work & Enterprise Productivity** theme: business brief → atomic requirements → human confirmation (G0) → traceable user stories and Given/When/Then criteria → human approval (G1) → two visual concepts and a **working three-screen prototype** → human approval (G2) → ZIP engineering handoff.

## What is included

| Area | Implementation | Status |
| --- | --- | --- |
| Project intake | Brief, PDF/TXT/MD upload, extracted page references | Implemented; local tested |
| Requirements analysis | Structured requirements, open questions, basic policy conflict demonstration | Implemented; demo tested |
| Optional SRS review | Generate after G0, edit eight sections, save revisions, approve/request changes, download PDF | Implemented; local/mock tested; user verified live generation, revision, PDF and ZIP inclusion |
| Story generation | Traceable stories and Gherkin criteria | Implemented; demo tested |
| Manual artifact editors | Add/delete/edit requirements, stories, criteria and prototype intake fields; create/delete/edit a whole prototype | React workspace; versioned saves invalidate downstream approvals |
| Approval gates | G0, G1, G2 with version validation and audit events | Implemented; tested |
| Prototype generator | Two color/design concepts, three schema-driven screens | Implemented; tested at API level |
| Prototype actions | Submit → manager approve → provisioning checklists | Implemented; tested at API level |
| Handoff | ZIP with requirements, stories, tests, prototype JSON and audit | Implemented; tested |
| Email handoff | Editable template, registered recipients, approved ZIP attachment, preview and explicit SMTP send | Implemented; synthetic tests only; real SMTP verification pending |
| Jira handoff | Preview then explicitly approve creation of one Jira issue per story after G2; durable ticket links and duplicate guards | Implemented; mocked REST tested; user verified real Story creation and persistent links |
| Frontend | React 19 + TypeScript + Vite and CSS; separate offline browser UI | Type-check/build verified; local create/progress/resume browser smoke checked |
| Authentication | Firebase Web + Admin SDK, ownership on all project endpoints | Mocked tests and logged-out UI verified; **real provider login not cloud-tested** |
| Foundation | Dashboard, project metadata, profiles, saved-stage resume | Implemented; local/mock tested |
| AI | Google Gen AI SDK and optional Google ADK stage-agent adapter | Source included; **live credentials/models not tested** |
| Persistence | SQLite local, optional Google Firestore | SQLite tested; **Firestore live access not tested** |
| Cloud Storage | Optional original file archival via bucket | Integration code provided, **not cloud-tested** |
| Deploy | Full-stack Dockerfile for Google Cloud Run | Config provided; **not cloud-deployed** |

**IMPORTANT:** The default mode is explicitly **DEMO**, a deterministic, rule/template-based generator. It does not call Gemini. Switch to `gemini` or `adk` and provide Google credentials for genuine AI inference. Keep labels honest during judging.

### Editing generated or manually created artifacts

In the full React workspace, each stage has **Add**, **Delete**, **Save** and
**Discard** controls. Requirements can be authored without analysis; stories
can be authored after G0, and a prototype can be created manually after G1.
Manual editing does not make AI calls. Deleting all requirements or stories is
allowed as an empty saved draft, but it cannot be approved.

On **Live Prototype**, expand **Edit prototype structure and design** to edit
screen text, two design concepts and intake fields/options, or delete the entire
prototype. The intake/approval/checklist screen structure and demonstration
checklist actions remain fixed. Save before testing the live preview.

Saving requirements clears downstream stories/prototype and all approvals;
saving stories clears the prototype and G1/G2; prototype saves/deletion clear
G2. Cleared prototypes also clear their test requests. Confirmations warn before
these destructive operations; unsaved edits must be saved or discarded before
approval or generation. See [API contracts](docs/API.md#manual-artifact-editing).
These editors require the React build; the legacy dependency-free offline
fallback retains its more limited editing controls.

### Optional SRS generation and review

After confirming **G0**, stay in **Requirement Intake** and scroll to **SRS
generation & review**. Click **Generate SRS**, review the eight sections and
requirement/source links, edit as needed, and **Save SRS revision**. You can
request changes, view read-only saved revisions, explicitly approve the current
revision, and **Download SRS PDF**. Generation uses the configured Gemini/ADK
provider; demo mode is a labeled deterministic template. Editing and PDF export
use no model calls.

SRS is optional and does not change the existing G0/G1/G2 workflow or progress.
Saving/regenerating SRS clears its own approval only; changing requirements or
evidence invalidates the current SRS while preserving history. Unsaved SRS edits
are protected by the same navigation warning and Save/Discard behavior.
There is a deliberate MVP history limit of 10 revisions / 400 KB per project:
further revisions fail explicitly rather than discard history. Approved SRS JSON
and its approval are included in G2 handoff; PDF is a separate download.
See [SRS API and limitations](docs/API.md#optional-srs-review).

### Jira ticket creation from Engineering Handoff

After G0/G1/G2, **Create Jira tickets** previews the configured shared Jira Cloud
project and one ticket per story with acceptance criteria and requirement IDs.
Review the contents, tick the sharing confirmation and choose **Approve &
create** to perform the writes. No ticket is created by approval alone.
Confirmed deliveries retain links and are skipped on retries; uncertain outcomes
are blocked for administrator reconciliation rather than risk duplicates.
Changes to already delivered stories are flagged, not automatically pushed.
This is REST-based delivery, not MCP or sprint/status synchronization.
See [private backend setup](docs/FOUNDATION_SETUP.md#shared-jira-cloud-integration)
and [delivery safety/limits](docs/API.md#jira-cloud-rest-handoff). There is no
Gemini quota usage for this integration.

## Fastest start: offline browser demo

Requirements: Python 3.11+ and internet access to install Python dependencies the first time.

**macOS / Linux**

```bash
bash start-demo.sh
```

**Windows PowerShell**

```powershell
.\start-demo.ps1
```

Open **http://127.0.0.1:8000**. This serves a dependency-free browser UI with the same workflow and API. You do **not** need npm or Google credentials for this path.

Manual start if dependencies are already installed:

```bash
cd backend
export KATALYST_AUTH_MODE=demo
export KATALYST_STORE=sqlite
python -m uvicorn app.main:app --reload --port 8000
```

## Full React frontend (development)

In terminal 1:

```bash
cd backend
pip install -r requirements-demo.txt
export KATALYST_AUTH_MODE=demo
export KATALYST_STORE=sqlite
python -m uvicorn app.main:app --reload --port 8000
```

In terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` requests to port `8000`.

`npm run build` produces `frontend/dist`, which the FastAPI API will serve automatically on its own origin the next time you restart the backend. (The offline UI is the fallback if the React build isn't present.)

### Enable actual Gemini

```bash
cd backend
pip install -r requirements.txt
# Use either Gemini Developer API:
export KATALYST_AI_PROVIDER=gemini
export GEMINI_API_KEY='...'
# Local synthetic trial only; see foundation setup for Firebase accounts:
export KATALYST_AUTH_MODE=demo
export KATALYST_STORE=sqlite
# or Vertex AI with ADC and GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION.
python -m uvicorn app.main:app --reload
```

**ADK mode:** use `KATALYST_AI_PROVIDER=adk` and credentials supported by the Google ADK installation. The ADK adapter uses typed stage-specific LLM agents, while the approval state machine remains in deterministic backend code. Validate your installed SDK version and model access before using ADK in the demo.

### Live milestone: Gemini and ADK across multiple briefs

Use **64-bit Python 3.11+**. A 32-bit Python installation may fail to install ADK's
binary dependencies. Keep the existing demo environment separate:

```powershell
# Invoke your installed 64-bit Python executable for this first command.
python -m venv .venv-live
.\.venv-live\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\start-live.ps1 -Provider gemini
# Or run the same browser prototype through ADK:
.\start-live.ps1 -Provider adk
```

The launcher securely prompts for a Developer API key if one is not already in
`GEMINI_API_KEY` or `GOOGLE_API_KEY`. It passes the key only to the process;
it does not write a credential file. Never put a key in chat or source code.
`KATALYST_GEMINI_MODEL` overrides the default `gemini-2.5-flash`.

### Free-tier-friendly evaluation

Confirm the selected model has **free-tier access in your Google AI Studio project**
and check its current RPM, token and daily limits. The launcher cannot inspect
billing eligibility or guarantee zero cost. A paid Gemini chat subscription is not
required for eligible Gemini API free-tier access. ADK uses the same project/model
quota; it does not provide additional free calls. Use synthetic data only because
free-tier content may be used to improve Google products.

Start with a plan (no API key, model calls or output files):

```powershell
.\start-live.ps1 -Evaluate -Plan
```

Then run one purchasing brief with Gemini (**3 generation calls**), followed by ADK:

```powershell
.\start-live.ps1 -Evaluate
.\start-live.ps1 -Evaluate -Provider adk
# Select another brief or choose an eligible model ID from AI Studio:
.\start-live.ps1 -Evaluate -Case training
.\start-live.ps1 -Evaluate -Model 'YOUR_ELIGIBLE_MODEL_ID' -RequestsPerMinute 2
# Only after the small trials succeed, opt into all four briefs and both providers:
.\start-live.ps1 -Evaluate -AllCases -BothProviders
```

The default is one **non-onboarding** brief and one provider, not a 24-call run.
Available cases: `onboarding`, `purchasing`, `facilities`, `training`.
`-AllCases` uses 12 calls per provider; with `-BothProviders` it plans 24 calls.
The default local pacing target is **5 generation starts/minute** (12 seconds
between starts); set `-RequestsPerMinute` at or below your actual project limit.
Pacing is for this evaluation process only, not a global quota reservation for
other applications or manual browser requests. It does not enforce token or daily
quotas. Leave headroom for other users of the project.

Both adapters disable automatic HTTP retries. A Google quota/rate-limit failure
returns HTTP **429** with guidance; the evaluator records it and stops remaining
cases/providers rather than repeatedly consuming quota. It does not automatically
switch models, upgrade billing or substitute demo artifacts. Wait for the relevant
quota window before starting a fresh run.

Each evaluation uses an isolated SQLite database per provider, not your demo projects. Reports,
generated project JSON and successful handoff ZIPs are saved under a timestamped
`data\live-evaluation` directory. Failures produce a nonzero exit code, not demo
artifacts (exit **3** identifies quota exhaustion). Reports record planned calls,
attempted generation calls and skipped cases. Prototype generation errors surface
explicitly as errors.

The runner checks source IDs, **100% requirement-to-story coverage**,
Given/When/Then criteria, approval-gate enforcement, submit/approve/request-changes,
checklist actions and handoff consistency. Evaluation gate approvals are explicitly
**automated synthetic test approvals**, not human sign-off. Review the artifacts
using the rubric in [DEMO_AND_BENCHMARKS.md](docs/DEMO_AND_BENCHMARKS.md) before
claiming useful AI results. API success alone is not semantic or browser UX quality.
The fixed equipment/access/welcome checklist remains a known cross-domain limitation.

## Five-minute end-to-end walkthrough

1. Create the prefilled **Employee Onboarding Portal** project.
2. Click **Analyze requirements**. Review extracted statements and their source IDs; approve **G0**.
3. Click **Generate user stories**. Inspect acceptance criteria; approve **G1**.
4. Click **Generate prototype**. Switch between two concepts and three screens.
5. In screen 1, submit a synthetic employee; screen 2, approve; screen 3, check provisioning steps.
6. Approve **G2**, then download the engineering handoff ZIP.
7. Inspect `requirements.md`, `stories.md`, `acceptance.feature`, `prototype.json`, `traceability.json`, `approvals.json`.

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

Use the 64-bit live environment for the full suite, which includes mocked
Firebase and Firestore tests. Tests also cover gate ordering, source upload
validation, traceability, interactive actions, edit invalidation and export.

## Project layout

```text
KATALYST-MVP/
├── frontend/
│   ├── src/                React + TypeScript app
│   └── offline/            standalone browser demo, no npm required
├── backend/
│   ├── app/
│   │   ├── main.py         FastAPI endpoints + approval logic
│   │   ├── ai.py           Gemini + ADK + demo providers
│   │   ├── models.py       Typed output schemas
│   │   └── store.py        SQLite / Firestore data adapters
│   └── tests/
├── docs/
│   ├── DEPLOY_GOOGLE.md
│   ├── API.md
│   ├── DEMO_AND_BENCHMARKS.md
│   └── LIMITATIONS_AND_NEXT_STEPS.md
├── Dockerfile             multi-stage React/Python Cloud Run container
└── .env.example           configuration keys, NO secret material
```

## Accuracy and security caveats

This is a **foundation plus hackathon prototype**, not a certified production
system. Firebase mode verifies tokens (including revocation) and enforces per-user
ownership. Real cloud authentication and persistence still require configuration
and verification. Demo mode uses one fixed local identity; `X-Demo-User` no longer
selects a user. It has no enterprise RAG, organisation/role permissions, OIDC/SCIM,
secure sandbox for arbitrary generated code, distributed limits, load tests, high
availability SLA or accessibility certification. Use synthetic data, especially
with free-tier Gemini. **Never expose demo authentication publicly.** Production
requires operational hardening, permissions, retention, abuse prevention and cloud
verification beyond this milestone.

The UI schema is interactive only for the supported three-stage intake/approval/checklist workflow; this is **not** a general-purpose code generator. With live Gemini it can choose page titles and fields; the renderer deliberately limits executable behavior to trusted operations. Google Stitch integration is **not implemented** and should be evaluated separately.

## Related material

This build is a **narrow hackathon demonstrator** based on *KATALYST Hackathon MVP Specification v0.2* and *KATALYST SRS v0.1*. The 14-agent architecture, full voice-to-SDLC handoff, enterprise deployment topology and all five gates from the long-form SRS remain future scope.
