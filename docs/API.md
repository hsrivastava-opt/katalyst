# KATALYST MVP API

Swagger UI: `/docs` (on FastAPI backend). All project endpoints return the full updated project object except noted.

## SMTP email handoff

- `POST /api/projects/{id}/email/preview`: `{recipients: string[1..10], subject: string[1..200], body: string[1..12000]}`.
- `POST /api/projects/{id}/email/send`: same draft plus `{fingerprint: 64-character lowercase hex, confirmed: true}`.

Both require project ownership, version-current nonempty G0/G1/G2 artifacts,
trusted-sender UID allowlisting and complete private SMTP configuration. Preview
resolves exact recipient addresses through Firebase Authentication, rejects missing
or disabled users, deduplicates accounts and returns sender, canonical recipients,
literal subject/body, attachment filename/entry names, fingerprint, status, time
and safe delivery error. No user directory or credentials are returned. Subjects
cannot contain line breaks. Preview makes no SMTP writes.

Send repeats these checks, compares the snapshot-bound fingerprint (including
ZIP entry contents and mail destination) and atomically claims a separate email
ledger before network writes. It rereads current approvals/package before SMTP.
The attachment uses the shared ZIP builder used by export, with optional approved
SRS JSON, not its PDF. The response is the same preview shape with `sent` on SMTP
acceptance. Recipients use hidden envelope/Bcc delivery. The original project
document is unchanged; delivery metadata is saved separately.

States: `new`, `pending`, `blocked`, `sent`. Repeating an identical accepted
delivery returns `sent` without SMTP. Pending/blocked deliveries fail closed
(409); changed previews require renewed confirmation (409). SMTP errors/partial
refusals yield safe 502 errors and block blind retries. Storage errors use 503;
failed final persistence leaves the claimed record pending. Registration failures
use 422, recipient-service failures 503, unauthorized shared senders 403,
unconfigured SMTP 409 and oversized encoded MIME (>20 MB) 413.
This is not an inbox receipt, exactly-once delivery or a background job guarantee.
Concurrent project edits are not transactionally locked across an SMTP call.
See [SMTP setup/reconciliation](FOUNDATION_SETUP.md#shared-smtp-handoff-email).

## Endpoint reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/config` | AI mode (demo/gemini/adk), model and limitations |
| GET | `/api/me` | Verified user profile; persists last-seen profile |
| GET | `/api/projects` | Only the authenticated owner's summaries, stage, progress and resume tab |
| POST | `/api/projects` | `{title,brief,description?,business_domain?,client_name?,client_email?,expected_timeline?,additional_notes?}`; owner assigned from verified UID |
| GET | `/api/projects/{id}` | Read project, all artifacts and status |
| POST | `/api/projects/{id}/sources` | `multipart/form-data` file upload, PDF/TXT/MD |
| POST | `/api/projects/{id}/requirements/analyze` | Extract requirements, questions and conflicts |
| PUT | `/api/projects/{id}/requirements` | `{requirements, open_questions}`; increments version and invalidates gates |
| POST | `/api/projects/{id}/srs/generate` | Require G0; `{base_version}` generates a new optional SRS revision |
| PUT | `/api/projects/{id}/srs` | Require G0 and current SRS; `{base_version, document}` saves a human-edited revision |
| POST | `/api/projects/{id}/srs/approval` | Require G0; `{artifact_version, decision:'approved'\|'rejected', note?}` reviews current SRS only |
| GET | `/api/projects/{id}/srs/pdf` | Require G0 and approved current SRS; download paginated PDF |
| POST | `/api/projects/{id}/approvals/g0` | `{artifact_version, decision:'approved'}` |
| POST | `/api/projects/{id}/stories/generate` | Require G0; generate stories and criteria |
| PUT | `/api/projects/{id}/stories` | `{stories}`; validates traceability and invalidates G1/G2 |
| POST | `/api/projects/{id}/approvals/g1` | Approve current story version |
| POST | `/api/projects/{id}/prototype/generate` | Require G1; generate two concepts, three screens |
| PUT | `/api/projects/{id}/prototype` | Require G1; `{prototype: PrototypeSpec}` creates/replaces a manually authored prototype |
| DELETE | `/api/projects/{id}/prototype` | Require G1; remove prototype, G2 approval and test requests |
| POST | `/api/projects/{id}/demo/actions` | `{action:'submit'|'approve'|'request_changes'|'toggle', request_id?, values?, item?}` |
| POST | `/api/projects/{id}/approvals/g2` | Approve current prototype version |
| GET | `/api/projects/{id}/export` | Require G2; handoff ZIP |
| GET | `/api/projects/{id}/jira/preview` | Require current G0/G1/G2 and authorized Jira UID; read ticket preview and saved delivery status |
| POST | `/api/projects/{id}/jira/create` | `{fingerprint, confirmed:true}`; create approved preview's new tickets, skipping already confirmed deliveries |

## Example request

In Firebase mode, include `Authorization: Bearer FIREBASE_ID_TOKEN` on all project
requests and `/api/me`. Only health/config are public. The browser obtains and
refreshes tokens with the Firebase Web SDK. A missing/invalid/expired/revoked token
returns 401; attempts to access another owner's project return 404. Authentication
service outages return 503. Client-supplied owner fields are rejected.

Local demo launchers explicitly set `KATALYST_AUTH_MODE=demo`, with one fixed
`demo-user`. `X-Demo-User` is ignored and cannot select an identity. Do not use this
mode on a public deployment. Firebase/Firestore setup:
[FOUNDATION_SETUP.md](FOUNDATION_SETUP.md).

```bash
curl -s localhost:8000/api/projects -X POST \
  -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Onboarding Workflow","brief":"Build an employee onboarding portal where HR registers employees, managers approve new hire requests and IT manages equipment provisioning."}'
```

## Core invariants

- Stages cannot bypass approval gates.
- An approval records a specific artifact version.
- Changes to requirements invalidate stories, prototypes and their approvals.
- Changes to stories invalidate prototype and downstream approvals.
- Story source requirement IDs must exist, with testable Given/When/Then criteria.
- No arbitrary AI-provided code is executed; prototype actions are allowlisted.
- In `demo` mode, outputs are templates and must be identified as such.

## Manual artifact editing

The React workspace supports add/delete/edit for requirements, stories and
individual acceptance criteria. Requirement kind, source and source reference
are editable; story links must reference existing approved requirements.
Manual changes do not call Gemini or consume its quota.

Requirements/stories PUT operations replace the entire respective list (maximum
30 entries). Empty lists are permitted as saved drafts, including deleting the
last entry, but G0/G1 approval rejects empty artifacts with 409. Generation
responses still require at least one entry. Invalid edits return 422 without
changing stored artifacts or approvals.

The prototype editor can create/delete the entire prototype, edit titles,
descriptions, concept names/colors, and add/delete/edit intake fields and select
options. It preserves exactly two concepts and three screens in order:
`intake`, `approval`, `checklist`. Only intake supports editable fields; at least
one is required. IDs must be nonempty and unique in their respective collections,
and select fields require nonempty options. Arbitrary screens, executable code,
custom workflow actions and configurable checklist items are not supported.

Prototype PUT/DELETE increments `prototype_version`, removes G2 and clears
`demo_requests`. PUT sets `prototype_provider` to `manual` and records a
`prototype.edited` event; DELETE clears provenance and records
`prototype.deleted`. Deleting a missing prototype returns 409. Existing G0/G1
approvals are retained. Creation/recreation uses PUT, not an AI call.

All upstream replacements (including source upload and AI regeneration) clear
downstream prototype provenance and test requests. The UI confirms destructive
saves/replacements, offers Save/Discard, warns before leaving unsaved changes,
and blocks approval/generation/live actions until edits are saved or discarded.
Reloading or leaving the page does not persist an unsaved draft.

## Live generation failures

Prototype field schemas omit `additionalProperties` from generated JSON Schema
because the Gemini `response_schema` API rejects that keyword. This applies to
both Gemini and ADK stage outputs. Backend Pydantic validation still forbids
unexpected field properties and validates screen order, field types and concepts
before saving; schema compatibility does not relax runtime validation.

SRS generation schemas omit string-length and array-count bounds to reduce
constrained-decoding complexity. Types, section ID enums and required properties
remain in the model-facing schema; all length/count limits, exact eight-section
shape and reference coverage remain enforced locally before saving. This is a
compatibility mitigation for a generic Gemini HTTP 400, not a confirmed diagnosis
of every `invalid argument` response. A live retry is required to verify it for
the configured model.

The generation endpoints (including optional SRS) return HTTP **429** when Google reports quota or
rate-limit exhaustion, with a message directing the user to check project limits
in AI Studio. They do not retry automatically, change billing/model, or substitute
demo output. Existing artifacts, versions and approvals remain unchanged on a
failed generation. Other handled model/validation failures return HTTP **502**.

Both Gemini and ADK adapters disable automatic HTTP retries. The live evaluation
runner additionally spaces generation calls (default 5 starts/minute) and stops
on 429. That runner's pacing does not throttle independent browser requests or
other applications sharing the Google project; token/day quotas still apply.

## Optional SRS review

SRS review lives within Requirement Intake after G0. It is optional: G1/G2,
project status, resume tab and prototype progress do not depend on SRS approval.
Gemini/ADK generation uses the existing typed SDK path (one request, 120-second
timeout, no automatic retries or demo fallback). Demo mode produces an explicitly
labeled template. No new API key or package is required.

`SRSDocument` contains `title` and exactly eight `sections` with IDs in this order:
`purpose`, `scope`, `functional`, `non_functional`, `interfaces`, `data`,
`assumptions`, `acceptance`. Each section has editable `title`, nonempty plain-text
`content`, `requirement_ids` and `source_ids`. References must exist and every
approved requirement must be linked in at least one section. This validates
structural coverage, not semantic correctness: human review is still necessary.
Titles are limited to 160 characters for the document / 120 per section; content
is limited to 6,000 characters per section and 24,000 total.

Project responses add:
- `srs`: current revision, or `null` if absent/invalidated.
- `srs_version`: monotonically increasing saved revision number.
- `srs_revisions`: saved snapshots with `version`, `requirements_version`,
  `document`, `provider`, `actor`, `at`.
- `srs_approval`: version-bound review decision, or `null`.

Existing projects receive additive defaults on read; no destructive migration.
Each generate/save creates a revision and clears only SRS approval; story,
prototype and gate approvals remain untouched. Requirement edits/reanalysis and
source upload clear the current SRS and its approval but retain historical
revisions. G0 rejection clears SRS approval. Stale historical documents are
read-only and cannot be approved/downloaded as the current SRS.

All SRS endpoints use the same verified identity and owner checks. Stale
`base_version`/approval versions return 409; invalid edits return 422 without
modifying the saved revision/approval. Generation rereads requirements/evidence
before saving and rejects detected changes with 409. These checks do not replace
database transactions: simultaneous whole-project writes remain a known
limitation.

History is bounded at **10 revisions / 400,000 UTF-8 JSON bytes** per project
while persistence uses whole-project documents. At either limit, further
revisions return 409; no history is silently dropped. The UI disables saves and
generation at the revision-count limit. Large projects may still encounter the
underlying Firestore document limit; storage failures are explicit 503s.

PDF download requires approval of the saved current revision. It renders escaped
text, reference IDs, revision/provider/reviewer metadata and page numbers using
the existing PyMuPDF dependency. It does not execute model/user markup. Rendering
errors return 500 without changing saved data. No AI request is made for edits,
review, history viewing or PDF export.

The G2 handoff ZIP additionally includes `srs.json` and `srs-approval.json` only
when the current SRS is approved. Unapproved/absent SRS does not block handoff;
its PDF is downloaded separately from Requirement Intake. Gmail sending, DOCX
extraction and a full SRS-to-Jira state machine are not part of this milestone.

## Known prototype limitations

- SQLite does not provide transactional conflict detection for concurrent edits; Firestore adapter also requires a transaction strategy for multi-user editing.
- Source extraction stores limited text excerpts; PDFs containing mostly scans/images need separate OCR/Document AI services.
- Local demo identity is not authentication; Firebase mode uses server-verified identity.
- Schema-driven rendering supports a fixed workflow and component registry, not general application generation.

## Jira Cloud REST handoff

Engineering Handoff includes **Create Jira tickets**, which first previews the
fixed destination, issue type ID and exact contents. A separate checkbox and
**Approve & create** action authorize sharing the approved stories with
Atlassian. No issue is created by preview, generation or G2 approval alone.
This is a shared backend account, not per-user OAuth or an MCP connection.
Only administrator-allowlisted UIDs may use it, in addition to project ownership.
See [setup](FOUNDATION_SETUP.md#shared-jira-cloud-integration).

The preview includes `destination`, approved artifact `versions`, `fingerprint`
and `tickets`. Each ticket includes story ID, summary, description (story
role/goal/benefit, acceptance criteria, requirement IDs), durable delivery ID,
status (`new`, `pending`, `created`, `blocked`), issue key/link, changed-content
indicator and any safe error. Account email/token are never returned. Create
requires a matching preview fingerprint and all three current version-bound
approvals; stale previews or revoked approvals return 409 before new writes.
No AI requests are made for Jira delivery.

Delivery identity is KATALYST project + story ID + Jira site/project. A confirmed
story is not recreated when artifact versions change or users retry. Changed
content is flagged for manual Jira review; this milestone does not update
existing tickets automatically. New story IDs get new tickets: IDs must not be
repurposed for unrelated work. Changing the configured Jira destination permits
new deliveries there and requires a fresh preview/confirmation.

Before each REST POST, an atomic durable claim is written independently of
whole-project artifacts: SQLite `jira_deliveries`, or Firestore
`{project_collection}/_jira_deliveries/entries/{delivery_id}`. The ledger records
actor, timestamp, approved versions and content hash, then stores the returned
key/link or failure. Claims survive edits, application restarts and concurrent
requests. Do not clear this ledger when clearing project artifacts.

This is deliberately **not an exactly-once guarantee** across Jira and storage.
A crash, timeout or storage failure after a Jira write can leave a `pending` or
`blocked` record. No automatic POST retry occurs, even for 429 or a definite 4xx.
Partial successes retain their links; pending/blocked records stop further
delivery until an administrator reconciles them. The UI refreshes status after
failure without re-sending. Persistence failures return 503; delivery/config/
authorization conflicts return 409. Credentials/raw upstream responses are not
included in those errors.

Every issue is labeled `katalyst` and `katalyst-{delivery_id}`. Administrators
must search Jira for that exact label to reconcile uncertain outcomes. If the
issue exists, record its verified key/URL and `created` status in the ledger.
Only after verifying no ticket was created (and no request is still running)
may an administrator remove/reset that individual claim to permit another
explicit confirmation. Never delete all claims or blindly retry. There is no
automatic reconciliation endpoint in this MVP.

The integration creates issues of the configured issue type using Jira v3
Atlassian Document Format descriptions and normal API-token Basic auth. HTTPS
`*.atlassian.net` destinations only; redirects are refused, timeout is 30 seconds,
and Jira issue links are constructed from the validated destination, not
untrusted response URLs. Required custom fields may prevent issue creation;
configure a compatible Story/Task type before use.

Sprint assignment, epics/subtasks, bidirectional status sync, webhooks, OAuth,
automatic Jira ticket updates and MCP are not implemented. Ticket links open
Jira for tracking; KATALYST shows delivery status, not live sprint progress.
