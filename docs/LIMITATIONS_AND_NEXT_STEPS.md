# Restrictions, limitations and next steps

The current deliverable is a requirements-to-prototype and engineering-handoff
hackathon application. See the [README](../README.md) for reproducible run commands,
judge access instructions, feature scope, costs and troubleshooting.

## Implemented versus proposed

Implemented: Firebase private projects, Gemini artifact drafting, manual editing,
G0/G1/G2 approvals, optional SRS revision/review/PDF, fixed three-screen interactive
prototype, ZIP handoff, explicitly confirmed Jira REST delivery and SMTP email.
The read-only Gemini Live panel is deployed as an allowlisted pilot.

Not implemented:

- Voice requirement drafts/saves, voice-triggered approvals or external writes.
- General engineering-task backlog, sprint assignment or live Jira workflow sync.
- Per-user Jira/Gmail OAuth, MCP delivery or project collaboration/reviewer roles.
- Google Stitch, Document AI OCR, DOCX parsing, meeting diarization or video analysis.
- Enterprise vector RAG, a fourteen-agent organization or deployed ADK Agent Runtime.
- Production source-code generation, sandboxed generated code or full SDLC automation.
- App-level per-user limits on ordinary artifact generation, admin reconciliation UI,
  durable background jobs, immutable audit storage or transactional artifact editing.
- SSO/SAML/SCIM, organizational tenancy, load/penetration testing, high-availability
  SLA, security certification or accessibility certification.

GitHub Actions exists for repository tests/builds; KATALYST does not generate
downstream GitHub pull requests or deploy the application automatically on push.
ADK stage-agent source is present and mocked in tests; real end-to-end ADK acceptance
is not established.

## Evaluation access and privacy

- New accounts own only their own projects. Shared demo projects do not appear.
- Voice, Jira and email sender access each require exact Firebase UID allowlisting.
  There is no automatic grant to all registered users or admin UI.
- Allowlists do not create organization roles or shared project access.
- Email recipients must be active users of the same Firebase Authentication project;
  email grants a copy of exported contents, not access to the private project.
- Use synthetic data only. Briefs, artifact text and contact fields can be sensitive.
  Gemini free-tier processing may use submitted content to improve Google products.
- Voice consent shares microphone audio and a saved project snapshot. KATALYST
  does not persist raw audio/transcripts; Google's own processing terms still apply.
- Audit records are mutable project data, not tamper-proof compliance evidence.
- Demo auth is one shared unauthenticated identity. Never expose it publicly.

## Functional and persistence boundaries

- Prototype structure is exactly intake/approval/checklist with two concepts;
  checklist actions retain equipment/access/welcome demonstration labels.
  Domain-specific text/fields do not make it an arbitrary application generator.
- Requirements/stories permit empty drafts, but not empty approvals. Upstream
  edits invalidate downstream work. Previously exported/delivered artifacts are
  not updated automatically.
- Requirements/stories: at most 30 each. Upload: 6 MB; PDF: 50 pages.
  Extraction/context are bounded and are not OCR or exhaustive document retrieval.
- Optional SRS has eight sections, at most 24,000 content characters, ten retained
  revisions and 400,000 UTF-8 JSON bytes. Further revisions fail at capacity;
  old revisions are not silently discarded.
- Whole projects are saved in Firestore documents with the service's document-size
  limit. There is no general compare-and-swap editing; concurrent updates can
  overwrite each other. This is not production collaborative editing.
- Voice is a read-only session-start snapshot, not a live query service. Exact
  supplied counts are grounded inputs, not a guarantee of perfectly accurate speech.
  Detail omission is explicit above the context size limit.

## Delivery and cost boundaries

- Jira/email preview and approvals alone do not perform external writes.
- Atomic claims and independent ledgers prevent blind concurrent/repeated identical
  deliveries, but cannot guarantee exactly-once writes across provider and database.
- Partial refusal, timeout or crash may leave pending/blocked records after external
  success. Administrators must reconcile that single claim before any retry.
  Do not reset all records or change draft text to evade an uncertain delivery.
- Jira delivery does not update existing tickets, attach ZIPs, assign sprints or
  synchronize Jira workflow status. Do not reuse a delivered story ID for unrelated work.
- SMTP acceptance is not inbox receipt. No bounce tracking is implemented.
- Voice tokens are single-use, short-lived and constrained. A transactional per-UID
  cooldown allows one attempt every five minutes; UI sessions expire in three minutes.
  This is not a hard account-wide cost cap, and ordinary generation lacks equivalent
  per-user limits.
- Cloud Run free allowances, Gemini free-tier quotas and optional service fees are
  separate. Budget alerts and maximum instances do not stop all spending.

## Evidence boundaries

Real-service checks reported by the submitter include Firebase login/Google sign-in,
persistence, Gemini artifacts/SRS, Jira links and received SMTP handoff attachments.
Cloud Run health/configuration and anonymous API protection were independently checked.
User-confirmed direct and constrained-token Live handshakes used synthetic instructions.

Real microphone answers, complete hosted flow after key replacement, systematic
multi-domain quality measurements, load capacity and business ROI remain unverified.
Tests using mocked SDK/Firestore/Jira/SMTP/Live responses must not be represented as
those real external services executing.

## Recommended next milestones

1. Finish hosted acceptance with a fresh account and one real voice question.
2. Evaluate multiple business domains for captured rules, exclusions, unsupported
   assumptions, traceability and corrections; record results without invented KPIs.
3. Add bounded, reviewable voice requirement drafts using existing invalidation rules.
4. Add per-user generation budgets and evaluator access administration.
5. Normalize Firestore artifacts and add transactional edit conflict handling.
6. Expand prototype runtime with genuine domain-specific interactions.
7. Add organizational permissions, retention, operational monitoring and measured
   load/accessibility checks before describing the product as production-ready.
