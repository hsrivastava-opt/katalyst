# Implementation status

Updated: October 17, 2026

## Confirmed SMTP handoff addition

Engineering Handoff now has an editable plain-text email template, exact registered
recipient validation through Firebase Admin, current approved ZIP attachment,
preview/explicit confirmation, mandatory TLS, trusted-sender UID allowlisting and
a durable independent delivery ledger. Duplicate identical sends are skipped;
pending/uncertain outcomes require administrator reconciliation. SMTP acceptance
does not prove inbox delivery. Live SMTP credentials/delivery remain unverified.
See [SMTP setup and limits](FOUNDATION_SETUP.md#shared-smtp-handoff-email).

User-reported live acceptance checks on October 17: Jira Story creation and link
persistence; real Gemini SRS generation, saved revision, approval, PDF review and
approved SRS inclusion in the handoff ZIP. These are user confirmations, not
independent cloud-service inspection by the implementation tools.

## Milestone 1: application foundation

Extended the existing React/TypeScript/Vite and FastAPI application rather than
rebuilding in Angular. Added Firebase Web/Admin authentication, account screens,
Google sign-in wiring, session persistence and logout, protected workspace,
owner-filtered projects, dashboard, metadata wizard, user profiles, Firestore
persistence wiring and saved-stage resume. The prototype workflow is preserved.

See [FOUNDATION_SETUP.md](FOUNDATION_SETUP.md) for modules, configuration, data
model, state-machine boundaries and cloud setup.

## Verified locally

- **193 backend tests pass** after SMTP handoff implementation, including the
  existing 160 cases plus registered-recipient, sender authorization, confirmation,
  stale-snapshot, exact ZIP/SRS attachment, TLS/MIME/Bcc, duplicate/concurrent
  claim, Firestore email ledger and uncertain-outcome regressions.
  Original coverage includes Firebase verifier/revocation contracts,
  missing/expired/revoked/disabled-session rejection, project ownership on every
  project surface, metadata validation, profile persistence, SQLite migration,
  owner-filtered Firestore adapter calls, explicit storage errors, restart/resume,
  approval gates, live-evaluation pacing/quotas, Gemini schema compatibility,
  manual artifact CRUD/validation/invalidation, optional SRS revisions/review/PDF,
  SRS ownership/legacy defaults/quota failures, simplified SRS schema/runtime
  limits, Jira delivery/ownership/atomic claims and original workflow/export.
- `npm run build` passes TypeScript checks and builds the React production assets.
- `pip check` reports no broken dependencies in the 64-bit live environment.
- Local browser smoke: create a synthetic facilities project through the wizard,
  analyse with demo AI, approve G0, verify 33% prototype progress on dashboard,
  reload and resume directly at the stories stage.
- Browser checks at mobile (470px) and desktop (1440px) widths found no horizontal
  document overflow in the checked screens.
- Firebase Web SDK UI smoke with **explicitly mocked** Firebase REST responses,
  public configuration and API profile/projects: email sign-in, API bearer token,
  persistent reload and logout clear the protected workspace.
- Logged-out Firebase landing, registration/login form switching and Google
  sign-in button render; no actual Google OAuth popup authorization was performed.
- Manual-editor browser smoke on an isolated demo database: create a requirement
  and linked story without AI, add/delete entries and criteria, create a manual
  prototype, reject invalid select options without losing the draft, save options,
  submit/approve/check a test request, approve G2, edit/delete a field and confirm
  G2/test-request invalidation, then delete/recreate the prototype. Cancelling
  navigation retained unsaved edits. Build assets were regenerated.
- Optional SRS browser smoke on an isolated demo database: G0 guard, generation,
  title/section editing, Save/Discard, navigation cancellation retaining edits,
  read-only history, request-changes/revision/approval, PDF response from the UI
  download handler (valid `%PDF-` bytes), persistence after reload, validation
  error retaining the draft, and requirement edits invalidating the current SRS
  while preserving history. Checked 470px layout with expanded sections.
- Jira handoff browser smoke used a separate SQLite database, synthetic
  administrator configuration and an in-process mocked Jira transport: G2
  handoff placement, exact ticket preview, confirmation checkbox before create,
  saved links, duplicate prevention, reload/preview persistence and 470px layout.
  No external tickets were created and no credentials were used.
- SMTP browser smoke used an isolated SQLite database, synthetic recipient
  resolution and mocked transport: editable template, preview invalidation after
  edits, explicit-confirmation guard, cancel-navigation retaining draft, accepted
  status, reload/same-draft delivery recovery, duplicate-button prevention and
  470px layout without horizontal overflow. No external email was sent.

## Jira handoff milestone

Engineering Handoff now supports a shared-account Jira Cloud REST integration:
preview one issue per approved story, explicitly approve sharing/creation, and
retain returned issue keys/links in a separate durable delivery ledger.
Administrator UID allowlisting is required. Atomic claims prevent concurrent
duplicate submissions; pending/uncertain outcomes require manual reconciliation.
Already delivered changed stories are flagged, not automatically updated.
See [setup](FOUNDATION_SETUP.md#shared-jira-cloud-integration) and
[delivery safety/limitations](API.md#jira-cloud-rest-handoff).

Real Jira authentication, Story creation and persistent links were subsequently
verified by the user. Per-user OAuth, sprint assignment and status synchronization
remain future work.

## Optional SRS milestone

Implemented after G0 within Requirement Intake, independently of stories/G1/G2.
Eight grounded sections use typed Gemini/ADK output, editable reference links,
saved snapshots, explicit current-revision approval/rejection and paginated PDF
export with reviewer metadata. Existing SDK credentials and PyMuPDF are reused;
no extra package or cloud service is required. Approved SRS JSON/approval join
the handoff ZIP; SRS remains optional. History is limited to 10 revisions /
400 KB per project while using whole-project persistence. See
[API.md](API.md#optional-srs-review) for all limits and concurrency caveats.

Validation uses deterministic demo output and mocked Gemini/ADK SDK responses.
Real Gemini generation, saved revision persistence, approval, PDF and ZIP inclusion
were subsequently verified by the user. No live Gemini quota was consumed by the
implementation tools' checks.

## Artifact editors

The React workspace now supports add/delete/edit requirements, stories and
acceptance criteria, plus manual prototype creation/deletion and editing of
screen text, two design concepts and intake fields/options. Save/Discard and
destructive-operation confirmations are included. Empty requirement/story
drafts can be saved, but cannot pass approval. All manual edits are versioned,
authenticated and ownership-checked and require no model calls. Prototype
editing preserves the fixed three-screen renderer and checklist actions.
See [API.md](API.md#manual-artifact-editing) for contracts and invalidation rules.

Two dependency warnings remain (Starlette/AnyIO deprecation and a Google Cloud
Storage future compatibility warning). They did not fail the suite.

## Live-service verification boundaries

- Earlier user-reported checks confirmed Firebase registration/login/Google
  sign-in, private project persistence and real Gemini prototype generation.
  These are manual confirmations, not independently inspected cloud evidence.
- Real ADK execution, systematic cross-domain usefulness evaluation, and the new
  SRS flow with real Gemini/Firestore still require verification.
- Firestore rules deployment/IAM have not been independently verified.
- Cloud Storage uploads, Cloud Run deployment or an actual Docker image build.

Successful mocks are not cloud evidence. No credentials are embedded in source.
The environment-template file restricted by organisation policy was not read or
modified.

## Future product milestones

DOCX extraction; client email preview and
Gmail; UI/UX analysis, prompts and supported Stitch integration/manual import;
technical clarifications and architecture; backlog/sprint planning; Jira
OAuth/sprint assignment/status synchronization and automated reconciliation;
durable background execution and production hardening.

The UI labels these future capabilities honestly. The displayed 0-100% progress is
the existing **prototype** workflow, not complete SRS-to-Jira planning or software
implementation. Local demo mode remains one shared identity and is not safe for
public use.
