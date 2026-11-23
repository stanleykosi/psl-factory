DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- One outcome: SCR-52 leadership report line workspace (setup, drafting, review, Tuesday, received) on lane C's shared work-item page and line adapter (F-85, PR #101, e2f44656).
- Five boards (10 artboards, desktop and mobile), within the 8-board limit. No split needed.
- D-33, D-34 and D-35 are answered in backend-answers.md (API 1.24.0). Design is client-approved (13 Nov) with the recorded design-engineer exception.
- Not independently verified: the F-85 code (the paths in the brief are not in the project checkout I could read), and architecture approval status. The builder must confirm both at start and stop if either is missing.
- Medium risk: it is a UI-only contract change with a new adapter and a send-and-receipt path. It has no data migration and no money.

## Scope
Task FE-LEADERSHIP-REPORT. In scope:
- **Setup board.** Show the report type (Tuesday or monthly) and the period (`start_at`/`end_at`). Per D-33 the backend chooses the project list, so do not ask for record ids. Read `GET /projects/{case}/leadership-report-intake` for `templates[]`, `all_projects_available`, `setup_actions[]`, `owner_evidence[]` and `sources[]`. Start with `POST .../leadership-report-intake`. When `all_projects_available` is false, show a plain no-access note and the limited scope. Do not build record pickers or invent include flags.
- **Drafting board.** Use `GET /work/{id}` `state`. Per DC-3 there is no live `progress`, so show state only and do not invent steps.
- **Review board (monthly).** Show `editable_sections` (delivery_health, risks, performance, escalations, critical_incidents), each with text, evidence_ids and coverage (supported, partial, unknown, not_applicable). Show `scope`, `selection` and `review_verdicts[]`. Headline counts are per-source counts from the selection manifest, with capture time and coverage (D-34). Never compute or fill in a figure that is unknown, and never show an unknown as zero. Edit with `POST /work/{id}/leadership-report` using `expected_revision`, `case_revision` and a reason. Approve or return with `POST /work/{id}/reviews` `{kind:"document", version_id = document_version_id, verdict, note}`.
- **Review request (D-35).** The system or worker requests review while drafting. Offer a request-review action only when the work exposes it as eligible. No PM step.
- **Tuesday board.** Sections: progress, risks, blockers, dependencies. It uses its own review rule, so do not apply the monthly rule.
- **Received board.** Show `recipients[] {name, status, receipt_id, recorded_at}` and `next_action`. Uncertain delivery is checked with `POST /work/{id}/actions {expected_revision, action:"reconcile"}`, which returns 202. Do not retry before reconciling.
- **History.** `GET /work/{id}/history`.

Out of scope:
- Any approver, reviewer or audience rule not supplied by the API. Setup drafts are reviewed separately before they take effect; show that state and do not choose a reviewer.
- Cross-project selection beyond what the backend returns. The all-projects automatic selection for the PMO Lead and Finance Lead is backend work, not yet confirmed shipped. Until it ships, show the limited or project-scoped state truthfully and report the gap.
- Design parts the live API cannot fill: free-text period and design-only figures.
- New backend work.

## Risk
Medium. The builder has to reshape three setup choices into the live intake (D-33), render narrative sections with coverage, and drive review, send and reconcile on a shared adapter. That is a cross-layer contract (design/screens.md SCR-52, connect map section SCR-52). It is not high risk because it adds no data, money, identity change or migration, and the backend enforces permissions and delivery. Surfaces include external-messaging (the report is sent to recipients) and product-decision (the meaning of the counts and coverage markers). The design is approved under the recorded exception in design/review.json, which covers only the design engineer's upload-concepts change and not SCR-52. Client acceptance is required because it is a new flow with new copy.
