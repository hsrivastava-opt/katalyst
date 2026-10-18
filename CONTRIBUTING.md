# Working on KATALYST

Start with the [README](README.md) for the product scope, local installation and
restrictions. You do not need access to the showcase's cloud project, credentials
or accounts to run the deterministic demo and automated tests.

## Prerequisites and first run

- Git, 64-bit Python 3.12 and Node.js 22 with npm.
- Internet access for the initial dependency installation.
- Follow [local setup](README.md#run-locally-without-cloud-credentials), including
  the explicit demo authentication, SQLite and demo AI settings.
- Build the React frontend before serving the complete app from FastAPI.
- Open `http://localhost:8000`; `/docs` contains interactive API documentation.
- Use a feature branch for changes:

```powershell
git switch -c your-change-name
```

The repository does not automatically load environment files. Set environment
variables in the backend terminal as documented. Never commit keys, passwords,
Firebase Admin credentials, local databases or downloaded private documents.
Public Firebase Web app configuration is not an Admin credential.

## Exercise a complete workflow

1. Create an Employee Onboarding project with a brief such as:
   "HR submits employee details, managers approve or request changes, and IT
   tracks equipment, system access and welcome preparation."
2. Upload [the sample stakeholder notes](docs/examples/onboarding-notes.txt).
3. Analyze requirements, edit/save and approve G0.
4. Optionally generate/revise/approve the SRS and download its PDF.
5. Generate stories, check their requirement links and approve G1.
6. Generate the prototype, try its intake/approval/checklist actions and approve G2.
7. Download and inspect the engineering handoff ZIP.
8. Refresh/reopen the project to confirm persistence.

The demo provider is a labeled deterministic template, not Gemini inference or
proof of document understanding. For semantic evaluation use your own authorized
Gemini configuration and the [evaluation guide](docs/DEMO_AND_BENCHMARKS.md).
Never add silent demo fallbacks to live-provider failures.

## Development loop

Keep the backend running on `127.0.0.1:8000` using the README command and settings.
For automatic backend reload during development, add `--reload` to that uvicorn
command. In a second terminal, from the repository root:

```powershell
Set-Location frontend
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to backend port 8000.
The existing Vite script binds all interfaces; use only on a trusted machine/
network and never expose demo authentication publicly. For loopback-only binding:

```powershell
npm run dev -- --host 127.0.0.1
```

For the single-server production-style local path, run `npm run build` after UI
changes and serve the compiled frontend through FastAPI.

## Where to make changes

| Area | Entry points |
|---|---|
| API routes, ownership, workflow gates and exports | [main.py](backend/app/main.py) |
| Validated input and generated artifact contracts | [models.py](backend/app/models.py) |
| Demo, Gemini and optional ADK providers | [ai.py](backend/app/ai.py) |
| Token verification and Firebase configuration | [auth.py](backend/app/auth.py) |
| SQLite/Firestore persistence and delivery claims | [store.py](backend/app/store.py) |
| Progress and resume behavior | [workflow.py](backend/app/workflow.py) |
| Optional SRS lifecycle and PDF | [srs.py](backend/app/srs.py) |
| External delivery | [jira.py](backend/app/jira.py), [handoff_email.py](backend/app/handoff_email.py) |
| Voice credentials and saved context | [voice.py](backend/app/voice.py) |
| Workspace and navigation | [App.tsx](frontend/src/App.tsx) |
| Artifact editing | [ArtifactEditors.tsx](frontend/src/ArtifactEditors.tsx) |
| Browser API client and shared types | [api.ts](frontend/src/api.ts), [types.ts](frontend/src/types.ts) |
| Voice UI and resource cleanup | [VoicePanel.tsx](frontend/src/VoicePanel.tsx), [voiceAudio.ts](frontend/src/voiceAudio.ts) |

Read the [API contracts](docs/API.md) before changing a route or artifact schema.
Keep frontend types and all affected providers, persistence defaults, exports and
tests consistent. Existing saved projects must remain readable.

## Tests and build

Install the development dependencies from the README first. From the repository
root, select the backend tests relevant to your change:

```powershell
& .\.venv-live\Scripts\python.exe -m pytest -q backend\tests\test_artifact_editing.py
```

Choose other test files for ownership, SRS, delivery, voice or provider changes.
Before opening a pull request, run the full existing checks:

```powershell
& .\.venv-live\Scripts\python.exe -m pytest -q backend\tests
Set-Location frontend
npm run build
node --test tests\voice-audio.test.cjs
Set-Location ..
git diff --check
```

On macOS/Linux use `.venv-live/bin/python` and POSIX path separators.
The frontend build includes TypeScript checking. No separate general frontend
unit-test or lint script is currently configured; the audio tests are Node tests.
GitHub Actions runs backend tests, the frontend build and audio tests.

Automated tests use temporary databases and mock external services. They should
not require private credentials or create real Jira issues/send email.
Tests are not proof of live inference quality, production load capacity or
external-service acceptance.

## Protect existing behavior

- Preserve owner checks and private-project access on every project route.
- Preserve G0/G1/G2 version binding and downstream invalidation after edits.
- Keep SRS optional and independent of the story/prototype gates.
- Retain the fixed three-screen prototype boundary unless explicitly changing
  the renderer, schema, validation, tests and documentation together.
- Require preview and explicit confirmation for Jira/email. Preserve durable
  claims, duplicate safeguards and uncertain-delivery handling.
- Keep voice read-only and opt-in; release microphone, socket and playback
  resources on termination/error.
- Surface validation/upstream errors; do not silently invent successful results.
- Document behavior changes and test invalid inputs as well as the happy path.

## Real services and deployment

Use [Foundation setup](docs/FOUNDATION_SETUP.md) for your own Firebase, Firestore,
Gemini and optional integration configuration. Real inference may use paid quota.
Voice, Jira and email sender permissions are independently UID-allowlisted.

Use [Google deployment](docs/DEPLOY_GOOGLE.md) for an independent deployment.
The root deployment helper defaults to the submitter's showcase project; do not
run it against resources you do not control. A GitHub push runs checks but does
not automatically deploy Cloud Run.

## Pull-request checklist

- Explain the problem, behavior change and validation performed.
- Keep changes scoped; avoid unrelated refactoring or generated artifacts.
- Add/update focused regression tests.
- Update related README/API/setup instructions.
- Verify existing demo behavior and impacted approval/persistence paths.
- Include no secrets, user data, dependency folders, local databases or builds.
- Label mocked versus real-service evidence accurately.

No repository-wide license has been specified. Public source visibility does not
itself grant unrestricted reuse rights; clarify permission with the maintainer
before redistribution or reuse outside the permitted evaluation.
