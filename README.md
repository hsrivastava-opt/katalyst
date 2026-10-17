# KATALYST

**From business intent to approved engineering handoff.**

KATALYST is a Google-powered, human-reviewed requirements-to-prototype application
for **Future of Work & Enterprise Productivity**. It turns a business brief and
supporting documents into structured requirements, linked user stories,
acceptance criteria, an optional Software Requirements Specification (SRS) and
an interactive workflow prototype. People review, edit and approve artifacts
before exporting or delivering them to engineering.

This is a working hackathon prototype, **not a production application generator,
autonomous development team or enterprise-certified platform**.

## Links and review guide

- **Live application:** https://katalyst-mvp-861461836467.asia-south1.run.app/
- **Public source:** https://github.com/hsrivastava-opt/katalyst
- **Automated checks:** https://github.com/hsrivastava-opt/katalyst/actions
- **API reference:** [docs/API.md](docs/API.md); interactive `/docs` on a running backend.
- **Setup and integrations:** [docs/FOUNDATION_SETUP.md](docs/FOUNDATION_SETUP.md).
- **Independent Google Cloud deployment:** [docs/DEPLOY_GOOGLE.md](docs/DEPLOY_GOOGLE.md).
- **Restrictions and roadmap:** [docs/LIMITATIONS_AND_NEXT_STEPS.md](docs/LIMITATIONS_AND_NEXT_STEPS.md).
- **Evidence and verification boundaries:** [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).
- **AI evaluation approach:** [docs/DEMO_AND_BENCHMARKS.md](docs/DEMO_AND_BENCHMARKS.md).

The presentation PDF and demonstration video are separate submission deliverables;
this repository does not currently include those deliverables or links to them.
Repository creation dates alone do not prove compliance with a hackathon's
fresh-code timeline; provenance must be established separately by the submitter.

## Problem and intended value

Business stakeholders, analysts and developers often work across disconnected
briefs, documents and ticket trackers. Requirements can be ambiguous, acceptance
criteria can be missing, and changes can leave downstream plans out of date.

KATALYST connects drafting, review and delivery in one project:

```text
Business brief + PDF/TXT/MD evidence
                 |
       Gemini requirement analysis
                 |
     Edit / save / approve requirements (G0)
          |                         |
          |               Optional SRS revisions,
          |                 approval and PDF
          v
     Linked stories + Given/When/Then criteria (G1)
                 |
     Two visual concepts + three-screen prototype (G2)
                 |
       Engineering handoff ZIP
           /                \
 Confirmed Jira creation   Confirmed SMTP email
```

The intended benefit is clearer shared understanding and less fragmented handoff
work. **No quantified time-saving, ROI, load-capacity or business-impact claim has
been established.** AI output still requires human review.

## For judges: evaluate the live app

### Access and restrictions

1. Open the live application and register with your own email/password or use
   **Continue with Google**. No shared password or API key is provided.
2. Create your own project. Existing projects are private to their owners;
   an empty dashboard on a new account is expected.
3. Use synthetic business data. This is not a production environment for
   confidential, personal, regulated or customer information.
4. The first request after inactivity may take longer because Cloud Run can
   scale to zero.
5. AI calls share the configured Gemini project's quota. Do not repeatedly click
   generation after a quota error.

| Capability | Who can use it in Firebase mode? |
|---|---|
| Create/read/edit projects and generate artifacts | Signed-in users, on their own projects |
| Approvals, PDF and ZIP export | Project owners after the required gates |
| Voice assistant | Project owners whose UIDs are in a separate voice pilot allowlist |
| Shared Jira delivery | Project owners whose UIDs are in the Jira allowlist |
| Shared SMTP delivery | Project owners whose UIDs are in the email allowlist |
| Receive email handoff | Active registered Firebase accounts; sender must be authorized |

**Voice, Jira and email are not automatically enabled for every new evaluator.**
Arrange access with the submitter through the submission's contact channel if
those integrations need review. Never send account passwords, ID tokens or API
keys. The Firebase UID is an account identifier, not a login credential.
Integration restrictions do not prevent the core prototype and ZIP workflow.
There is no admin-access screen or project-sharing UI.

### Suggested evaluation scenario

Create an **Office Supply Purchasing** project with this brief:

> Employees request office supplies with an item description, quantity, needed-by
> date and cost centre. Managers approve or request changes. Operations tracks
> ordering, delivery and receipt after approval. Automatic supplier ordering and
> payments are out of scope.

1. **Requirement Intake:** click **Analyze requirements**. Check that the
   requirements reflect the brief and that unanswered questions are not silently
   treated as confirmed business rules. Edit an item and save, then approve **G0**.
2. **Optional SRS:** generate the eight-section SRS after G0. Review its grounding,
   edit/save a revision, approve it and download the PDF. This branch is optional.
3. **Stories & Criteria:** generate stories, inspect requirement links and
   Given/When/Then criteria, then approve **G1**.
4. **Live Prototype:** generate the prototype, switch between its two concepts
   and test intake -> approval/request changes -> checklist interaction.
   Approve **G2** after review.
5. **Engineering Handoff:** download the ZIP and inspect its artifacts. If the
   current SRS is approved, its JSON and approval record are included.
6. **Optional authorized integrations:** preview Jira or email contents, then
   explicitly confirm only if you intend to create real issues/send real email.
7. Refresh and reopen your project to check saved artifacts and progress.

The runtime deliberately supports only an intake/approval/checklist workflow.
Checklist labels remain the equipment/access/welcome demonstration template,
even with a purchasing brief. Treat that as a visible domain-generalization
limitation, not as fully generated purchasing fulfillment logic.

## Implemented capabilities

| Area | Implementation and boundary |
|---|---|
| Intake | Business brief and PDF/TXT/MD text extraction with source references; not OCR or DOCX |
| AI drafting | Typed Gemini requirements, open questions, potential conflicts, stories, SRS and prototype schema |
| Editing | Add/delete/edit requirements, stories, criteria and prototype fields; save/discard and navigation warnings; no reorder controls |
| Governance | Version-bound G0/G1/G2 gates and audit events; deterministic backend controls, not model-controlled approvals |
| SRS | Eight sections, editable reference links, saved revisions, approve/request changes and paginated PDF |
| Prototype | Two concepts and exactly three ordered screens: intake, approval, checklist; trusted renderer, not executable AI-generated code |
| Handoff | Approved specification ZIP with traceability and approval/audit records |
| Jira | REST preview -> confirmation -> one issue per story; persistent links, atomic claims and duplicate safeguards |
| Email | Editable plain-text template, registered recipients, ZIP attachment, preview/confirmation and mandatory SMTP TLS |
| Voice | Read-only Gemini Live audio Q&A, saved project snapshot, exact supplied counts and visible transcripts |
| Identity | Firebase email/password and Google sign-in; backend ownership checks and revoked/disabled token checks |
| Persistence | Firestore for hosted use, SQLite for local evaluation; separate integration ledgers and voice cooldown records |
| Deployment | React and FastAPI in one Cloud Run container; backend credentials in Secret Manager |

### Editing and invalidation rules

- Saving requirements clears stories, prototype and G0/G1/G2, and invalidates the
  current SRS while retaining revision history.
- Saving stories clears the prototype and G1/G2.
- Saving/deleting the prototype clears G2 and prototype test requests.
- Saving/regenerating SRS clears only its own approval. SRS never blocks G1/G2.
- Empty requirement/story drafts may be saved, but cannot pass approval.
- Uploaded evidence/reanalysis can replace downstream work; the UI warns first.
- Approvals are owner decisions, **not separate organizational reviewer roles**.

### Voice pilot

**Ask KATALYST** can answer questions such as "How many stories are there?" or
"What remains before handoff?" using a server-derived snapshot from session start.
It is not continuously refreshed. Detailed artifact text is explicitly omitted
if the context exceeds its size limit; exact supplied counts remain available.
Answers/transcripts can still be inaccurate.

Voice requires consent, HTTPS/localhost, microphone permission, AudioWorklet and
a supported recent browser. It uses a Live-compatible model separately from the
text model. The browser receives a constrained one-use ephemeral token, never the
permanent key. Sessions expire after three minutes; each account can attempt
one start every five minutes across projects/workers. Failed token requests
consume the cooldown. End releases microphone/audio/socket resources.

**Not implemented:** voice requirement saving/drafting, voice approvals, ticket
creation, email sending, engineering-task counts or live Jira workflow status.
KATALYST does not persist raw voice audio or transcripts; Google processes
content according to its own API terms. Free-tier content may be used to improve
Google products. The ephemeral-token API is experimental.

## Architecture and Google technology

```text
Browser: React 19 + TypeScript + Vite + Firebase Web SDK
  |
  | Firebase ID token, same-origin HTTPS
  v
Cloud Run: FastAPI + Pydantic
  |-- Firebase Admin: identity / revocation / recipient lookup
  |-- Firestore: owner-scoped projects, delivery ledgers, voice cooldown
  |-- Gemini Developer API: structured artifact generation
  |-- Optional Google ADK stage-agent adapter
  |-- Jira Cloud REST: explicitly approved issue creation
  |-- Gmail/SMTP: explicitly approved ZIP delivery
  `-- Optional Cloud Storage: original upload archival

Browser microphone/audio <-> Gemini Live WebSocket
  `-- Backend authorizes project snapshot + constrained ephemeral credentials

Cloud Build -> Artifact Registry -> Cloud Run
Secret Manager -> runtime service account -> private backend credentials
```

Hosting and core infrastructure use Google services. Jira is an optional
Atlassian integration, not a competing hosting dependency. React and FastAPI
are application frameworks. Browser Firestore access is denied by
[firestore.rules](firestore.rules); backend IAM and ownership authorize data access.

The current text configuration uses `gemini-3.1-flash-lite`; the voice pilot uses
`gemini-3.8-live`. Model names, regional availability and free-tier eligibility
can change: verify your own account before running. The code's unconfigured text
model default is older; explicitly set `KATALYST_GEMINI_MODEL` for live runs.

## Run locally without cloud credentials

This is the recommended reproducible review path when hosted quota is unavailable.
It uses a **labeled deterministic demo provider**, not real Gemini inference.
Use **64-bit Python 3.12** and **Node.js 22** to match CI/container versions.
Initial dependency installation requires internet access.

### Windows PowerShell

Clone the repository, then run from its root:

```powershell
git clone https://github.com/hsrivastava-opt/katalyst.git
Set-Location katalyst
python -m venv .venv-live
& .\.venv-live\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Set-Location frontend
npm ci --no-audit --no-fund
npm run build
Set-Location ..

$env:KATALYST_AUTH_MODE = 'demo'
$env:KATALYST_STORE = 'sqlite'
$env:KATALYST_AI_PROVIDER = 'demo'
$env:KATALYST_LIVE_ENABLED = 'false'
& .\.venv-live\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

### macOS / Linux

```bash
git clone https://github.com/hsrivastava-opt/katalyst.git
cd katalyst
python3 -m venv .venv-live
.venv-live/bin/python -m pip install -r backend/requirements-dev.txt
(cd frontend && npm ci --no-audit --no-fund && npm run build)
export KATALYST_AUTH_MODE=demo KATALYST_STORE=sqlite KATALYST_AI_PROVIDER=demo
export KATALYST_LIVE_ENABLED=false
.venv-live/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000**. Keep that terminal running. Demo authentication
uses one shared local identity and bypasses login: **never expose it publicly**.
Saved demo data lives in `data/katalyst.sqlite` by default and is Git-ignored.

The optional `start-demo.ps1` / `start-demo.sh` install smaller demo dependencies
and may serve the limited legacy UI if no React build exists. They are not the
full-featured path above and do not configure Firebase. The separate
`start-live.ps1` launcher tests real AI with **local demo auth/SQLite**, not the
hosted Firebase setup.

### Frontend development

Keep the backend on port **8000**. In a second terminal:

```powershell
Set-Location frontend
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `127.0.0.1:8000`.
The microphone worklet is served from the Vite public directory. After Python
changes restart the backend; after production UI changes rebuild the frontend.
The backend serves the compiled frontend without a second server.

## Run with real Gemini

To test real generation locally while retaining explicit demo auth and SQLite,
use the setup above, stop the backend with Ctrl+C, then set these in that terminal:

```powershell
$env:KATALYST_AI_PROVIDER = 'gemini'
$env:KATALYST_GEMINI_MODEL = 'gemini-3.1-flash-lite'
$env:GOOGLE_GENAI_USE_VERTEXAI = 'false'
$secret = Read-Host 'Gemini Developer API key (hidden)' -AsSecureString
$env:GOOGLE_API_KEY = (New-Object System.Net.NetworkCredential('', $secret)).Password
Remove-Variable secret
& .\.venv-live\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Use your own key from [Google AI Studio](https://aistudio.google.com/api-keys).
`GOOGLE_API_KEY` takes precedence over `GEMINI_API_KEY`.
No environment file is automatically loaded; set process environment explicitly.
Keys configured in one terminal do not automatically appear in another.
This mode does not enable real Firebase users or registered-recipient email.

For actual login and Firestore use, follow
[Firebase/Google Cloud setup](docs/FOUNDATION_SETUP.md#firebase-and-google-cloud-setup),
obtain local Application Default Credentials and configure:

| Required setting | Value |
|---|---|
| `KATALYST_AUTH_MODE` | `firebase` (default if unset) |
| `KATALYST_STORE` | `firestore` (default with Firebase auth) |
| `GOOGLE_CLOUD_PROJECT` | Your Firebase/Firestore project ID |
| `KATALYST_FIREBASE_WEB_API_KEY` | Your Firebase web app's public `apiKey` |
| `KATALYST_FIREBASE_AUTH_DOMAIN` | Your web app's public `authDomain` |
| `KATALYST_FIREBASE_WEB_APP_ID` | Your web app's public `appId` |
| `KATALYST_AI_PROVIDER` | `gemini` for live generation; defaults to deterministic `demo` |
| `KATALYST_GEMINI_MODEL` | Eligible text model ID, explicitly configured |
| `GOOGLE_API_KEY` | Private Gemini Developer API key |

Firebase web identifiers are public browser configuration, **not** Admin
credentials or a substitute for a private Gemini key. ADC/service-account
permissions are required for backend Firebase/Firestore access.

If a Google Cloud project is set but no Developer API key is supplied, the Gemini
adapter attempts Vertex AI with ADC. That is a separate IAM/billing path; the
deployed evaluator app uses the Developer API, not Vertex AI.

### Optional integrations

| Integration | Configuration |
|---|---|
| Jira | `KATALYST_JIRA_SITE`, `KATALYST_JIRA_PROJECT_KEY`, `KATALYST_JIRA_EMAIL`, `KATALYST_JIRA_API_TOKEN`, `KATALYST_JIRA_ISSUE_TYPE_ID`, `KATALYST_JIRA_ALLOWED_UIDS` |
| SMTP | `KATALYST_SMTP_HOST`, `KATALYST_SMTP_PORT`, `KATALYST_SMTP_SECURITY` (`ssl`/`starttls`), `KATALYST_SMTP_USER`, `KATALYST_SMTP_PASSWORD`, `KATALYST_SMTP_FROM`, `KATALYST_EMAIL_ALLOWED_UIDS` |
| Voice | `KATALYST_LIVE_ENABLED=true`, `KATALYST_LIVE_MODEL`, `KATALYST_LIVE_ALLOWED_UIDS`; optional separate `KATALYST_LIVE_API_KEY` |
| Original uploads | `KATALYST_UPLOAD_BUCKET` plus bucket-scoped runtime permission |
| Local storage | Optional `KATALYST_DB`; default SQLite database under `data/` |
| Firestore namespace | Optional `KATALYST_FIRESTORE_COLLECTION`; defaults to `katalyst_projects` |
| Development origins | Optional `KATALYST_CORS_ORIGINS`; defaults to localhost/127.0.0.1 Vite origins |

Allowlist values are comma-separated exact Firebase UIDs. They are independent;
being registered does not grant shared-account or voice access. Leaving an
integration unconfigured does not block the core workflow.
Use [integration setup](docs/FOUNDATION_SETUP.md) for secret prompts, permissions
and delivery reconciliation. Jira is REST-based, not MCP. Gmail needs an app
password where supported, not your normal account password.

## Deploy on Google Cloud

Use the root [Dockerfile](Dockerfile) to build React and FastAPI into one container.
The deployment guide provides a **core-only path** that does not require Jira,
SMTP or voice, as well as the full integration script.

1. Create your own billing-enabled Google Cloud/Firebase project.
2. Enable required APIs, Firebase sign-in and a Firestore Native default database.
3. Create a dedicated runtime service account with appropriate least-scope roles.
4. Put private credentials in Secret Manager and grant access to that runtime.
5. Deploy on Cloud Run and add its hostname to Firebase **Authorized domains**.
6. Verify sign-in, owned data, one generation and exports on the hosted URL.

**Do not run the full script against the submitter's project.** Its defaults target
the existing showcase. For your own authorized project pass explicit parameters:

```powershell
.\deploy-cloud.ps1 -ProjectId YOUR_PROJECT_ID -Region asia-south1 -Service katalyst-mvp
```

The full script requires Jira/SMTP settings and three existing secrets; it is not
a one-command infrastructure bootstrap. It optionally propagates the voice pilot
settings. See [complete deployment instructions](docs/DEPLOY_GOOGLE.md).

### Costs and quota

- Cloud Run can scale to zero; this does not eliminate image-storage, build,
  network, Firestore or secret-operation charges.
- Maximum instance settings and budget alerts **are not hard spending caps**.
- Gemini API billing is independent of hosting allowances. A billing-linked
  project can require Prepay credits and return HTTP 402 when they are absent.
- A separate unbilled Gemini project may offer eligible free-tier models; it must
  obey Google's account terms and limits, not be used to bypass quotas.
- Free text-model access does not guarantee Live model access or quota.
- Voice has a per-UID cooldown, but ordinary artifact generation currently has
  no app-level per-user daily quota. Share the hosted prototype responsibly.
- Do not automatically retry or rotate keys/projects to evade limits.

## Tests and AI evaluation

From the repository root after installing development dependencies:

```powershell
& .\.venv-live\Scripts\python.exe -m pytest -q backend\tests
Set-Location frontend
npm run build
node --test tests\voice-audio.test.cjs
```

On macOS/Linux substitute `.venv-live/bin/python` and POSIX path separators.
GitHub Actions runs backend tests, the frontend production build and audio tests.
Backend tests use temporary SQLite databases, explicit demo identity and mocked
external services; **they do not need your cloud keys or send real Jira/email
requests**. They verify schemas, gates, invalidation, ownership, PDFs, exports,
delivery safety and voice-token/cooldown contracts. Mocked tests are not evidence
of AI semantic quality or production capacity.

Opt-in live multi-domain evaluation:

```powershell
.\start-live.ps1 -Evaluate -Plan
.\start-live.ps1 -Evaluate -Provider gemini -Case purchasing -Model gemini-3.1-flash-lite
```

The plan makes no model calls. A single case uses three generation calls; optional
SRS/voice are separate. The evaluator uses synthetic, automated test approvals,
isolated databases and paced calls, and writes reports under Git-ignored
`data/live-evaluation/`. Review results with the
[usefulness rubric](docs/DEMO_AND_BENCHMARKS.md) before claiming quality.
ADK is an alternative stage-agent adapter, not an additional free quota pool;
real end-to-end ADK execution has not been confirmed.

Live model discovery and explicit connection diagnostics are provided in
[backend/check_live.py](backend/check_live.py). Do not run them with someone
else's credentials or print keys/tokens. Instructions are in
[the API guide](docs/API.md#live-voice-assistant-discovery).

## Handoff contents

The ZIP is a **point-in-time specification package**, not a deployable generated app.

| Entry | Purpose |
|---|---|
| `README.md` | Project identity and package scope |
| `requirements.md` | Original brief, saved requirements and open questions |
| `stories.md` | Stories, linked requirement IDs and acceptance criteria |
| `acceptance.feature` | Gherkin-style acceptance specifications; no executable step definitions |
| `prototype.json` | Schema consumed by the trusted prototype renderer |
| `traceability.json` | Story-to-requirement mappings |
| `approvals.json` | Workflow gate decisions |
| `audit.json` | Recorded project events; not immutable compliance storage |
| `srs.json`, `srs-approval.json` | Included only for the approved current SRS revision |

The SRS PDF is downloaded separately, not attached automatically.
Email attaches the same ZIP contents as download. Jira issues do not automatically
receive the ZIP attachment. Changes do not update previously downloaded files,
delivered emails or existing Jira issues.

## Known restrictions and troubleshooting

| Symptom | Meaning / action |
|---|---|
| 401 / expired session | Sign in again; anonymous access to project APIs is intentionally denied |
| Firebase unauthorized domain | Add the exact frontend hostname under Authentication -> Settings -> Authorized domains |
| Blank Firebase setup / storage unavailable | Check public web config, ADC/runtime IAM, APIs and Firestore default database |
| 403 voice pilot authorization | Ask the administrator to authorize your exact signed-in Firebase UID |
| Jira/email unavailable or unauthorized | Optional shared integration is not configured or your UID is not allowlisted |
| 409 approval/version conflict | Save or discard edits; review current upstream artifacts and approve the required gate |
| Google HTTP 402 inside a 502 | Check the Gemini key project's billing plan and Prepay balance; hosting billing is separate |
| 429 generation quota | Check AI Studio RPM/token/daily limits and wait; no automatic retry/fallback is performed |
| 429 voice cooldown | One token attempt per five minutes; authorization rejection occurs before the slot is claimed |
| Voice fails / microphone denied | Use HTTPS/localhost and a current browser; check mic/audio permissions, Live access and quota |
| Frontend changes missing | Run `npm run build`, restart the backend if needed and hard-refresh |
| Vite API calls fail | Default proxy expects backend port 8000; a separately served backend on 8001 needs a deliberate proxy change |
| Pending/blocked Jira or email delivery | Administrator must reconcile provider records and the single ledger entry; never blindly resend/reset |

Additional hard boundaries:

- Up to 30 requirements and 30 stories; PDF/TXT/MD upload max 6 MB, PDFs max
  50 pages. Extracted evidence and generation context are truncated/bounded.
  Scanned-image PDFs are not OCR'd.
- SRS: eight fixed sections, 24,000 total content characters, at most 10 retained
  revisions / 400,000 UTF-8 JSON bytes. Hitting limits blocks further saves explicitly.
- Email: up to 10 input recipients, subject 200 characters, body 12,000 characters
  and encoded MIME max 20 MB; provider limits may be lower. SMTP acceptance is not
  proof of inbox delivery.
- Whole-project Firestore persistence is subject to its document-size limit.
  General project edits are not transactionally conflict-checked; concurrent edits
  can overwrite each other. Integration claims/voice cooldowns have separate
  atomic handling, but do not make the whole workflow transactional.
- No organization tenancy, collaborative reviewer roles, live Jira sync, sprint
  assignment, OAuth-connected per-user Jira/Gmail accounts, admin reconciliation
  UI, production job queue, immutable audit trail, load test or accessibility certification.
- No production code generation, Stitch integration, enterprise RAG or autonomous
  multi-agent organization. Raw uploads are not retained unless a bucket is configured.

## Verification status

- Latest local publication check: **222 backend tests**, **6 audio unit tests**
  and the TypeScript/Vite production build passed after a clean dependency install.
- Local automated and mocked browser checks cover the implemented paths; see
  [implementation evidence](docs/IMPLEMENTATION_STATUS.md) for details.
- The submitter reported successful real Firebase login/Google sign-in, private
  project persistence, Gemini generation, artifact revisions, SRS PDF/ZIP, Jira
  creation and email receipt with a valid attachment during local live-service tests.
- Cloud Run deployment, health/configuration, audio-worklet asset delivery and
  anonymous project/voice rejection were checked independently. These checks do
  not establish every hosted feature's end-to-end success.
- The submitter confirmed a direct Live connection and a constrained ephemeral-token
  connection using synthetic instructions. **Real microphone answers and voice
  accuracy have not yet been confirmed.** Hosted generation after switching the
  Gemini key also needs explicit acceptance evidence.
- No measured load capacity, impact improvement, security certification or completed
  real ADK evaluation is claimed.

## Source layout

```text
backend/
  app/
    main.py           REST routes, gates, ownership and shared ZIP builder
    ai.py             Gemini, optional ADK and explicit deterministic providers
    auth.py           Firebase token verification
    models.py         Validated request/output contracts
    store.py          SQLite/Firestore projects, ledgers and cooldowns
    srs.py            SRS lifecycle, limits and PDF rendering
    jira.py           Confirmed Jira REST delivery
    handoff_email.py  Confirmed SMTP ZIP delivery
    voice.py          Grounded snapshot and constrained ephemeral tokens
    workflow.py       Saved progress and resume stage
  tests/              Mocked API, provider and persistence regressions
  check_live.py       Opt-in Live discovery/connection checks
  evaluate_live.py    Opt-in paced synthetic multi-domain evaluation
frontend/
  src/                React workspace, editors and integration panels
  public/             Logo and microphone AudioWorklet
  tests/              PCM/audio lifecycle tests
  offline/            Limited legacy browser demo
docs/                 API, setup, deployment, evidence and limitations
.github/workflows/    CI tests and builds; not automatic Cloud Run deployment
Dockerfile            Multi-stage Google Cloud Run image
deploy-cloud.ps1      Full-integration deployment helper
firebase.json         Firestore rules deployment configuration
firestore.rules       Deny direct browser Firestore access
```

Private environment files, dependency directories, local databases and generated
builds are excluded from Git/source uploads. No keys or evaluator credentials are
distributed. Third-party libraries and assets remain subject to their own licenses;
no blanket license or ownership claim over dependencies is implied.
