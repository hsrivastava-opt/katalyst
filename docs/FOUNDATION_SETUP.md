# KATALYST application foundation (Milestone 1)

## Read-only Live voice pilot

Live discovery, a direct connection and a constrained ephemeral-token connection
succeeded in user-run checks with the free-tier key for `gemini-3.8-live`.
The read-only panel is deployed and allowlisted. Actual microphone answers and
speech quality remain unconfirmed; handshake success is not audio acceptance.

The optional project panel uses the Google GenAI JavaScript SDK, Web Audio,
AudioWorklet and direct browser-to-Gemini streaming. The backend issues one-use,
short-lived constrained tokens after Firebase ownership and allowlist checks.
No permanent key goes to the browser. Audio is captured at 16 kHz PCM and replies
play at the returned PCM sample rate. No video or browser speech-recognition
provider is used. Status/counts come from a saved server snapshot at session start.
Requirement dictation and Jira live status are not implemented in this stage.

In the same configured local backend PowerShell terminal:

```powershell
$env:KATALYST_LIVE_ENABLED = 'true'
$env:KATALYST_LIVE_MODEL = 'gemini-3.8-live'
$env:KATALYST_LIVE_ALLOWED_UIDS = $env:KATALYST_JIRA_ALLOWED_UIDS
```

Reuse the existing privately configured free-tier `GOOGLE_API_KEY` (or explicitly
set `KATALYST_LIVE_API_KEY` privately). Do not accidentally use the old paid-tier
local key after replacing only the deployed secret. Restart backend and refresh.
Production deployment accepts the three pilot variables via `deploy-cloud.ps1`;
its existing Secret Manager binding supplies `GOOGLE_API_KEY`.

Voice is disabled by default. Even when globally enabled, only explicitly listed
UIDs can start sessions. One start attempt per account every five minutes is
enforced transactionally across workers; failed upstream attempts consume the
slot. The UI ends at most three minutes after token issuance, and any End/error
releases the microphone. Users must consent to project/audio sharing first.
Do not log ephemeral tokens, store raw audio or promise that Google does not
process free-tier data for product improvement. See
[API scope/limits](API.md#read-only-voice-pilot).

## Shared SMTP handoff email

Engineering Handoff includes an editable subject/body template, up to 10 registered
recipient email addresses, preview of the current approved ZIP contents and a separate
confirmation before sending. Recipients are checked against this deployment's Firebase
Authentication project (including accounts not yet saved in the profile collection).
Disabled/nonexistent accounts are rejected. There is no public user-directory listing.
Only the project owner can send their project; sending does not grant recipients access
to that private project. Recipients receive its exported contents instead.

Set these variables privately in the **same PowerShell terminal as the backend**:

```powershell
$env:KATALYST_SMTP_HOST = 'smtp.gmail.com'
$env:KATALYST_SMTP_PORT = '465'
$env:KATALYST_SMTP_SECURITY = 'ssl'
$env:KATALYST_SMTP_USER = 'your-sender@gmail.com'
$env:KATALYST_SMTP_FROM = 'your-sender@gmail.com'
$env:KATALYST_EMAIL_ALLOWED_UIDS = 'your-firebase-uid'
$smtpSecret = Read-Host 'SMTP app password (not your normal account password)' -AsSecureString
$smtpCredential = New-Object System.Net.NetworkCredential('', $smtpSecret)
$env:KATALYST_SMTP_PASSWORD = $smtpCredential.Password
Remove-Variable smtpSecret, smtpCredential
```

For Gmail, enable 2-Step Verification and create an app password if the account's
policy permits it. Otherwise use an SMTP provider that permits password/app-password
authentication. Never paste the password into chat, commit it or put it in frontend
configuration. The sender must be authorized by the SMTP provider. `starttls` with
port `587` is also supported; TLS certificate verification is mandatory. No packages
are added. Restart the backend from this configured terminal.

The SMTP account is shared, so explicitly allowlist only trusted sender Firebase UIDs
(comma-separated). Recipient entry does not accept arbitrary external addresses; people
must register first. Demo authentication cannot resolve/send real registered recipients.
Preview makes no SMTP connection, but checks Firebase registration. Approval and send
use no Gemini quota. Subject/body drafts are not saved; navigation warns on edits.
Templates start prefilled with project details; there is no placeholder interpreter,
saved template library, HTML editor or AI-generated email.

The email attaches the same package contents as Download handoff, including approved
SRS JSON and approval when available, **not the separately downloaded SRS PDF**.
All contents, including audit actors and the original brief, are shared. Recipients are
delivered as Bcc envelope addresses, not visible To/Cc addresses.

Delivery records are separate from the project document: SQLite `email_deliveries` or
Firestore `{project_collection}/_email_deliveries/entries/{fingerprint}`. Atomic claims
block concurrent/repeated identical submissions. SMTP acceptance is **not** proof of inbox
delivery. A crash, partial refusal, timeout or final storage failure may leave a pending
or blocked record even if some/all recipients received the message. There is no automatic
retry, exactly-once guarantee, bounce tracking or background queue. Inspect the provider's
records using the saved delivery fingerprint in Message-ID, recipients and timestamp before
manually reconciling that single ledger entry. Mark `sent` only after confirming acceptance;
remove a claim only after confirming no accepted delivery and no request still in flight.
Do not change message text to bypass an uncertain delivery. Different drafts/snapshots can
be sent separately; this is not a general mail-campaign system. The encoded MIME message
limit is 20 MB; providers can impose smaller limits and daily quotas.

## Architecture and scope

The existing stack is **React 19 + TypeScript + Vite**, **FastAPI/Pydantic**,
SQLite/Firestore adapters and Gemini/ADK. It is extended, not replaced with Angular.

```text
backend/app/
  auth.py          Firebase Admin ID-token verification and fixed local demo identity
  main.py          Authenticated REST endpoints, ownership checks and existing gates
  models.py        Validated project metadata and existing AI artifact contracts
  store.py         Owner-filtered Firestore/SQLite projects and user profiles
  workflow.py      Existing workflow progress and server-derived resume destinations
  srs.py           Optional SRS validation, bounded revision snapshots and PDF rendering
frontend/src/
  AuthGate.tsx     Landing, registration, login, Google sign-in, session restoration
  ProjectDashboard.tsx  My Projects, dates, status, progress, create/resume actions
  ProjectForm.tsx  Two-step project metadata/requirements form
  App.tsx         Protected dashboard and existing project workspace
  SrsPanel.tsx    Optional G0-based SRS generation, revision editing/review and PDF
  api.ts          Fresh Firebase ID tokens on every project request and ZIP export
firebase.json     Firestore rule deployment configuration
firestore.rules   Deny direct browser access; backend IAM + ownership authorize data
```

Implemented: email/password registration/login, Google sign-in, local session
persistence, logout, profile display, protected workspace, project metadata,
owner-filtered dashboard, create/resume, persistent progress, and existing
requirements/stories/prototype gates.

An optional SRS milestone now adds documents, revision history, human review and
PDF download after G0 without blocking stories/prototypes. It uses the same AI
provider and credentials; no additional setup or dependencies are required.
See [SRS contracts](API.md#optional-srs-review), including history/document limits.

Confirmed Jira ticket creation is now available on Engineering Handoff via a
shared backend account; it is separate from the broader sprint-planning roadmap.
Confirmed SMTP email handoff is also available via a shared backend sender;
Gmail OAuth is not implemented.

Not implemented: DOCX,
per-user Gmail OAuth, Stitch, architecture agents, Jira sprint/status synchronization, durable background jobs, transactional
concurrent editing, pagination, tenant organisations or production certification.
AI generation is still explicitly invoked in the existing workspace, not
automatically launched on project creation. Do not label prototype progress as
SRS-to-Jira completion.

## Shared Jira Cloud integration

1. Create a Jira Cloud site and software project. The Free plan is sufficient
   for a small prototype team. Record the site URL and project key.
2. Select a shared account with permission to browse the project and create
   issues. Create an ordinary Jira Cloud API token for it, with an appropriate
   expiry. This implementation uses the site REST URL with email/API-token Basic
   auth, not scoped-token gateway URLs or OAuth. Never paste tokens into chat.
3. Identify a Story or Task issue type ID available in that project. Jira
   administrators can use the authenticated read-only endpoint
   `GET /rest/api/3/issue/createmeta/{projectKey}/issuetypes` to discover IDs.
   Ensure the chosen type does not require unsupported extra fields beyond
   project, issue type, summary and description, and supports labels.
4. In the backend's existing PowerShell session, set:

   ```powershell
   $env:KATALYST_JIRA_SITE = 'https://your-team.atlassian.net'
   $env:KATALYST_JIRA_PROJECT_KEY = 'KAT'
   $env:KATALYST_JIRA_EMAIL = 'your-service-account@example.com'
   $env:KATALYST_JIRA_ISSUE_TYPE_ID = '10001' # Replace with the actual issue type ID.
   $env:KATALYST_JIRA_ALLOWED_UIDS = 'your-firebase-uid' # Comma-separated exact UIDs.
   $secret = Read-Host 'Jira API token' -AsSecureString
   $env:KATALYST_JIRA_API_TOKEN = [System.Net.NetworkCredential]::new('', $secret).Password
   Remove-Variable secret
   ```

   Find the Firebase UID in Firebase Console > Authentication > Users.
   For local demo-only checks use `demo-user`, never a public deployment.
   All allowlisted users can send their owned projects into this one shared Jira
   destination; there is no per-user Jira account isolation. Do not allowlist
   users who should not have that ability. Secrets are backend-only and are not
   saved to project documents, returned to the browser, or written to source.
   Hosted deployments should inject these values through their secret manager.
5. Restart the backend in that same terminal. No new Python dependency is needed.
6. After G0/G1/G2, open Engineering Handoff > **Create Jira tickets**. Review the
   destination, each ticket's contents and sharing notice. Tick the confirmation
   and select **Approve & create**. Tickets are then created sequentially and
   their links persisted. Refresh preview to load delivery records after reload.

An unconfigured integration shows an explicit setup error without affecting ZIP
export or approvals. No external writes occur until confirmation. Test first in
a dedicated Jira project. Failed/uncertain deliveries are blocked to avoid
duplicates; see [reconciliation and limits](API.md#jira-cloud-rest-handoff).

## Firebase and Google Cloud setup

1. Create/select a Google Cloud project and add Firebase to that **same project**.
2. In Firebase Console → Authentication → Sign-in method, enable **Email/Password**
   and **Google**, configure Google's support email, and save.
3. Under Authentication settings, add your actual frontend hosts to **Authorized
   domains**. Add `localhost` explicitly for local development when it is absent.
   Prefer `http://localhost:5173` locally, not a random host or wildcard.
4. In Project settings → General → Your apps, register a **Web app** and copy its
   `apiKey`, `authDomain`, `projectId` and `appId` into the backend variables below.
   These are public web identifiers, not Admin/service-account credentials.
   Restrict the key appropriately for Firebase browser authentication and enable
   appropriate Firebase anti-abuse protections/password policy.
5. Create a **Firestore Native mode** database (default database) with a region
   suitable for your users. Do not enable public test rules.
6. Deploy the included deny-all client rules using an installed Firebase CLI:

   ```powershell
   firebase login
   firebase deploy --only firestore:rules --project YOUR_PROJECT_ID
   ```

   The browser deliberately never reads/writes Firestore directly. Admin SDK/Google
   Cloud client requests bypass these rules and depend on backend IAM. The API
   enforces the verified Firebase UID as owner on **every** project operation,
   including uploads, approvals, prototype actions and exports.
7. Provide **Application Default Credentials** locally, for example with an
   installed Google Cloud CLI:

   ```powershell
   gcloud auth application-default login
   gcloud auth application-default set-quota-project YOUR_PROJECT_ID
   ```

   Use a dedicated service account on Cloud Run, not a downloaded key in source.
   It needs narrowly scoped Firestore data access (e.g. `roles/datastore.user`)
   and Firebase user-read permission (e.g. `roles/firebaseauth.viewer`) for the
   revocation/disabled-user check. Enable the relevant Firebase Authentication,
   Identity Toolkit and Firestore APIs and grant required service-use permissions.
   API keys are not a replacement for server credentials.

## Environment configuration

Set these in the **backend process environment**. No frontend environment file or
Firebase credentials baked into the bundle are needed: `/api/config` serves only
the public web configuration. Environment files are not automatically loaded;
all required names and configuration examples are documented here.

| Variable | Purpose |
|---|---|
| `KATALYST_AUTH_MODE=firebase` | Default; verified login required, no silent demo fallback |
| `GOOGLE_CLOUD_PROJECT` | Same Firebase/Firestore project ID; required in Firebase mode |
| `KATALYST_FIREBASE_WEB_API_KEY` | Public Firebase web app `apiKey` |
| `KATALYST_FIREBASE_AUTH_DOMAIN` | Public web app `authDomain` |
| `KATALYST_FIREBASE_WEB_APP_ID` | Public web app `appId` |
| `KATALYST_STORE=firestore` | Default in Firebase mode; explicitly set for cloud deployment |
| `KATALYST_FIRESTORE_COLLECTION` | Optional project collection, default `katalyst_projects` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Optional local ADC credential file path; never commit the file |
| `KATALYST_CORS_ORIGINS` | Comma-separated actual browser origins; local Vite origins default |
| `KATALYST_AI_PROVIDER=demo` | Synthetic, deterministic AI for foundation testing without Gemini calls |
| `KATALYST_AI_PROVIDER=gemini` or `adk` | Actual model integration; requires separate model credentials/access |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Developer API credentials; backend only, never public Firebase config |
| `KATALYST_GEMINI_MODEL` | Optional model ID; verify account eligibility/quota before live runs |

The service rejects `FIREBASE_AUTH_EMULATOR_HOST` in Firebase mode rather than
accept unsigned emulator tokens in a deployment. Automated tests mock the verifier
and Firestore adapter explicitly. No emulator is silently used.

Example local shell (replace only the public identifiers):

```powershell
$env:KATALYST_AUTH_MODE = 'firebase'
$env:GOOGLE_CLOUD_PROJECT = 'YOUR_PROJECT_ID'
$env:KATALYST_FIREBASE_WEB_API_KEY = 'YOUR_PUBLIC_FIREBASE_WEB_KEY'
$env:KATALYST_FIREBASE_AUTH_DOMAIN = 'YOUR_FIREBASE_AUTH_DOMAIN'
$env:KATALYST_FIREBASE_WEB_APP_ID = 'YOUR_FIREBASE_WEB_APP_ID'
$env:KATALYST_STORE = 'firestore'
$env:KATALYST_AI_PROVIDER = 'demo'
.\.venv-live\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Keep this shell running; environments do not automatically transfer between
terminals. The frontend uses its backend's public configuration.

## Install, build and run

Use installed **64-bit Python 3.11+** and a supported Node.js version (Node 22 is
used by Docker). From the project root:

```powershell
# First command must use your 64-bit Python executable.
python -m venv .venv-live
.\.venv-live\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Set-Location frontend
npm ci
npm run build
Set-Location ..
```

Start the configured backend as above and open **http://localhost:8000**.
Alternatively, in a second terminal run `npm run dev` inside `frontend` and open
**http://localhost:5173**; Vite proxies the API. Build output is served by FastAPI
automatically. Without a React build, Firebase mode returns an explicit setup
error instead of serving the unauthenticated offline UI.

For Cloud Run, the existing root Dockerfile builds the frontend and serves both
from one origin. Set Firebase/Firestore environment values and runtime IAM on the
service; add its host to Firebase Authorized domains. Do not use the demo launchers
for a public deployment.

## Local development adapter

`start-demo.ps1` / `start-demo.sh` and `start-live.ps1` explicitly use
`KATALYST_AUTH_MODE=demo`, SQLite and one fixed `demo-user` identity. Client-supplied
`X-Demo-User` headers no longer select an identity. The UI and logs disclose this.
The live launcher tests **AI**, not real user authentication. Never expose these
local demo servers publicly.

SQLite owner indexing migrates existing rows without deleting artifacts or
changing owners. Legacy demo rows owned by another simulated identity stay
unassigned to the new fixed identity; no automatic account takeover or cloud
migration is performed. Back up and explicitly migrate trusted local records if
needed. Real Firebase users never inherit demo projects.

## Initial Firestore data model

- `users/{encodedUid}`: `uid`, `email`, `name`, `last_seen_at`. UID is percent-encoded
  as the document key; profile fields come only from verified token claims.
- `katalyst_projects/{projectId}` (or configured collection):
  - `id`, immutable-by-API `owner` (Firebase UID), `title`, `description`,
    `business_domain`, `brief`, `client_name`, `client_email`, `expected_timeline`,
    `additional_notes`, `created_at`, `updated_at`
  - existing `sources`, `requirements`, `stories`, `prototype`, version counters,
    version-bound `approvals`, `events`, `demo_requests`
  - derived `current_stage`, `resume_tab`, `completion_percentage`,
    `workflow_scope=prototype`, `planning_status=foundation_ready`

Owner queries use Firestore's default single-field `owner` index; results are
sorted by update time on the backend. SQLite has an `(owner, updated_at)` index.
No cross-user collection scan is used for listing. Unowned records are not visible.
Unauthorized IDs return 404; missing/invalid/expired/revoked sessions return 401;
authentication service/credential failures return 503, not demo access.

This retains the existing bounded MVP document shape. Firestore's **1 MiB per
document** limit and growing audit arrays mean this is not yet a scalable artifact
store. Later milestones must split `project_artifacts/{id}/versions/{version}`,
`agent_executions`, `approval_requests`, `review_comments`, `workflow_states`,
`technical_questions`, `technical_answers`, `email_records`, `jira_integrations`,
`jira_work_items`, `jira_sprint_plans`, and append-only audit records. Every record
must carry the project ID and server-enforced owner relationship; credentials
belong in secret storage, not client-readable documents.

## Workflow state machine

**Running today:** draft → requirements review → G0 approval → story generation/
review → G1 approval → prototype generation/review → G2 approval → handoff.
Edits or new evidence invalidate downstream artifacts/approvals. Rejections do not
advance. Resume destinations and progress are recomputed from valid approval
chains on read, not trusted from browser state. Logout does not delete work.
There is no automatic regeneration on resume.

**Planned integrated SRS-to-Jira states (not executable as a full pipeline yet):** PROJECT_CREATED →
REQUIREMENTS_SUBMITTED → SRS_GENERATED → HUMAN_SRS_REVIEW → SRS_APPROVED →
UIUX_PROMPT_REVIEW → UIUX_PROMPT_APPROVED → UIUX_DESIGN_REVIEW →
UIUX_DESIGN_APPROVED → TECHNICAL_CLARIFICATION → ARCHITECTURE_REVIEW →
ARCHITECTURE_APPROVED → BACKLOG_REVIEW → BACKLOG_APPROVED → JIRA_INTEGRATION →
PLANNING_COMPLETED. The optional SRS branch already supports a revision loop and
PDF download after approval, independently of the prototype gates. Architecture
and additional reviews remain planned; implemented SMTP email/Jira writes require
separate explicit confirmation and durable delivery claims.

Future integration prerequisites include verified Stitch API support or a labeled
manual import workflow, per-user Gmail OAuth consent/scopes and Jira OAuth.
Current shared-account SMTP and Jira REST are implemented and independently
configured; they do not imply those future OAuth integrations exist.

## Verification

```powershell
Set-Location backend
..\.venv-live\Scripts\python.exe -m pytest tests -q
Set-Location ..\frontend
npm run build
```

Tests mock external services, exercise Firebase verification/revocation contracts,
project metadata, every endpoint's ownership checks, owner-filtered Firestore
queries, SQLite migration, save/restart/resume, gate invalidation, quota handling
and the original end-to-end workflow. Successful mocks are not real Firebase or
Firestore cloud evidence.

Before claiming cloud readiness, run registration, email/password and Google
login in the configured project; create projects with two accounts and verify
cross-account denial; logout/relogin and refresh; restart the backend and resume;
verify actual Firestore documents. Live Gemini testing is separate and must use
synthetic data on the free tier. Concurrency controls, distributed limits,
durable jobs, verification/password-reset UX, full accessibility testing,
retention and production operational hardening remain future work.
