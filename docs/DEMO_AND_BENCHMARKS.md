# KATALYST — 3-minute presentation and evaluation

## Storyboard

| Time | Script / action | Evidence |
|---|---|---|
| 0:00–0:20 | Enterprise pain: requirements lose context across handoffs | One-slide overview |
| 0:20–0:50 | Enter the employee onboarding brief; review atomic requirements | Original source IDs, gaps and G0 approval |
| 0:50–1:20 | Produce reviewed stories and Given/When/Then criteria | Traceability and G1 approval |
| 1:20–2:15 | Generate two concepts, open actual clickable prototype | Register employee → approve → provision checklist |
| 2:15–2:40 | Approve the prototype and export the handoff | ZIP files plus approval audit |
| 2:40–3:00 | Explain measured benefit, safeguards and roadmap | Actual benchmark results, not imagined savings |

## Practice prompts

Employee onboarding: "Build an employee onboarding portal. HR registers new joiners with name, email, start date and department. Managers approve or request changes. IT tracks equipment and access provisioning."

Second evaluation prompt: "Build a purchase request approval application where employees request office supplies, managers review requests, and operations track fulfilment."

Third evaluation prompt: "Build an internal equipment request portal where staff create requests, leads approve, and facilities tracks completion."

## Repeatable live evaluation

Install the live dependencies with 64-bit Python, then use this staged sequence
from the project root:

```powershell
.\start-live.ps1 -Evaluate -Plan
.\start-live.ps1 -Evaluate
.\start-live.ps1 -Evaluate -Provider adk
.\start-live.ps1 -Evaluate -AllCases -BothProviders -Plan
.\start-live.ps1 -Evaluate -AllCases -BothProviders
```

The default trial is one **purchasing** brief with Gemini: three generation calls.
The second trial uses the same brief with ADK. Only the explicit full run evaluates
all four briefs (onboarding, purchasing, facilities, training) through both
providers, for 24 planned calls. Choose one with `-Case training`, for example.
`-Plan` needs no credentials and makes no model calls or files. Live runs prompt
privately for a Developer API key when needed.

Use `-Model 'YOUR_ELIGIBLE_MODEL_ID'` to select a model with free-tier access shown
in your AI Studio project. The configured default is not a guarantee of eligibility.
Eligible free-tier use can cost $0; the runner cannot verify billing tier or
guarantee zero cost. A Gemini chat subscription is separate from API access.
Use synthetic briefs only; free-tier content may improve Google products.

By default, evaluation generation starts are spaced at least 12 seconds apart
(5/minute). Set `-RequestsPerMinute` based on your **actual** AI Studio limits and
leave headroom for other project users. This is local pacing, not enforcement of
project-wide token/day limits. Both providers share applicable project/model
quota. Both SDK adapters make one HTTP attempt, with no automatic retries.
HTTP 429 stops remaining cases and providers; reports list attempted calls and
skipped cases, and exit code 3 identifies quota exhaustion. Check the relevant
quota window before starting another run in a fresh output directory.

The runner never activates demo mode. Inspect each provider's `report.json`,
per-case project JSON and successful handoff ZIPs under the timestamped
`data\live-evaluation` directory. A failed generation or validation is a failed
case and a nonzero process exit, not a template-based success. Each stage has a
120-second model-call deadline.
Pacing waits occur before that deadline. Other generation failures return HTTP
502; only explicit Google quota/rate-limit failures return HTTP 429.

The equivalent direct runner supports `--provider gemini|adk|both`,
`--case onboarding|purchasing|facilities|training` or `--all-cases`,
`--requests-per-minute N`, `--model ID`, and `--plan`. Provide `--output PATH`;
plan mode prints the planned budget without creating that directory.

Automated success requires valid source IDs, 100% requirement coverage in stories,
Given/When/Then criteria, supported screen order, two concepts, enforced gates,
working submit/approve/request-changes/checklist API actions and matching exports.
The runner's approvals are marked automated synthetic evaluation, not human review.
Its regression tests mock AI output and do not count as live evidence.

### Human usefulness review (required for every brief and provider)

Review the original brief alongside generated requirements, stories and prototype.
Score each dimension **0** (wrong/missing), **1** (needs substantial edits), or
**2** (usable with minor edits):

| Dimension | What to check |
|---|---|
| Grounding | No invented policies, limits, roles or facts; gaps are questions/assumptions |
| Requirement completeness | Every requested business action and data field is represented |
| Story usefulness | Correct actors, actionable goals, meaningful benefits and links |
| Acceptance quality | Concrete, testable outcomes, including relevant invalid/rejected paths |
| Prototype fit | Domain-appropriate titles/fields; no claims of unsupported behavior |

Acceptance target: **at least 8/10 per case**, no zero dimension and no critical
invented policy. Record the reviewer, score, required edits and decision separately;
the automated report intentionally leaves human usefulness review pending.
Repeat failed cases after fixes in a fresh output directory. Do not average away a
failed domain or provider.

Manually open each brief in the browser and verify screen navigation, both visual
concepts and request action state before claiming browser readiness. The current
checklist is fixed to equipment/access/welcome tasks, even outside onboarding;
record this mismatch explicitly. Mechanical success does not establish useful
domain-specific fulfilment, general-purpose app generation or human design quality.

## Evaluation worksheet (fill only after running trials)

| Metric | Baseline/manual | KATALYST | How measured |
|---|---|---|---|
| Median minutes to 3-screen prototype | ___ | ___ | Start → reviewable working app |
| Story accuracy | ___ | ___ | Blind expert review of 3 briefs |
| Acceptance criteria completeness | ___ | ___ | Checklist: Given/When/Then, role, outcome |
| Traceability coverage | ___ | ___ | Mapped approved stories / all stories |
| End-to-end success rate | ___ | ___ | Completed trials / attempted trials |
| Review edits needed | ___ | ___ | Count of changes before approval |

Do **not** claim the demo mode used Gemini. Only call the workflow "AI powered" after live Gemini/ADK integrations have been successfully tested with current credentials.

## Demo readiness checklist

- Confirm Gemini credentials, model ID, quotas and project billing before switching AI mode.
- Run backend test suite and at least three complete rehearsals.
- Confirm generated prototype is navigable and maintains action state.
- Verify accurate provenance of generated statements and test story references.
- Demonstrate failure behavior and the ability to stop an unapproved action.
- Record a backup video; verify GitHub public repo and Cloud Run URL work without privileged developer-only tools.
- Capture screenshots and actual performance measurements for the official slide template.
