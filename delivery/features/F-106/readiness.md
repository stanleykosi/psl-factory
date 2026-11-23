DECISION: READY
RISK: high
SURFACES: ui, api, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- READY: one outcome, SCR-53 review, drafting, publishing, uncertain and verified boards fed by the live `GET/POST /work/{id}/accounting` read and write.
- Build-start wait: F-105 (SCR-53 intake boards) must be on main first, and F-85 (shared line adapter, PR #101) too. Neither blocks readiness; the coordinator holds the builder.
- Backend answers E-19 and E-20 settle the data. POST accounting accepts only `recheck_reviewers` and `reassess`. Review and claim writes go through `/tasks/{id}/claim` and `/tasks/{id}/decision`. Recovery goes through `can_reconcile`.
- Parts of the boards the API does not supply are hidden under the D-182 rule and named below.
- HIGH risk because the screen drives publication to external recipients and uncertain-effect recovery. Merge goes to the design engineer's batch.

## Scope
Outcome: a person can follow a management accounts report through reviews, drafting, publishing, an uncertain publication and the verified result, on live API 1.24.0.

In scope (about 6 to 8 boards, state-driven from `accounting.state`):
- Reviews board: `review_stations[]` (label, subjects with id, status, review_id, evidence_id, reviewed_at) and `tasks[]` (id, revision, label, can_claim, can_decide, allowed verdicts). Writes: `POST /tasks/{id}/claim`, `POST /tasks/{id}/decision` (verdict from `tasks[]`, never invented), and `POST /work/{id}/accounting {action: recheck_reviewers, expected_revision}` when `can_recheck_reviewers`.
- Reassess: `{action: reassess, expected_revision}` when `can_reassess`.
- Drafting board: `state`, `next_action`, `finding`, `calculated_at`, `setup_missing[]` (what is missing before publish).
- Publishing board: `publication` and `delivery_jobs[]` per recipient.
- Uncertain board: reconcile only through `can_reconcile`. There is no resend control. Reconcile before any retry, per AGENTS.md.
- Verified board: shown only when the API reports the publication verified, not on a job success claim. Always show `ledger_posted` as returned, so the page never claims a posting.
- Findings: render `findings` / `finding_details` (stable code, original message, line or field where known) per E-20. Show unclassified legacy messages as they are.
- Earlier versions via `predecessor_id`, `successor_id` and `correction`, read-only.
- Task: FE-FIN-ACCOUNTS-PUBLISH. Endpoints: `GET/POST /work/{work_id}/accounting`, `POST /tasks/{task_id}/claim`, `POST /tasks/{task_id}/decision`, `POST /work/{work_id}/actions` where the connection map lists it.
- The line mapping lives in this feature's own adapter folder. It follows F-85's spec and does not change the shared frame in `frontend/src/features/workspace`. A frame change is named as a dependency on lane C.

Out of scope: intake, unit confirmation, mapping rows and corrected-extract upload (F-105); any other line; backend changes.

Hide, and say so in the spec (D-182): the "Row 88: period is 2026-09" row table, the "3 accounts are new since September" basis detail, and reviewer names and the why-nobody-can-review owner-needed list. The API supplies none of these. Never invent attempt counts, approvers or amounts. Unknown money stays unknown, never 0.

Not yet verified at the endpoint level: the request body of `POST /work/{id}/actions` and the exact `publication` and `delivery_jobs[]` field shapes (E-19 names only the review fields). The spec writer reads these from `contracts/psl-factory.openapi.json` in the lane-d worktree. If the contract does not define them, hold only that write and list it for the batch.

## Risk
High: publication sends the report to external recipients (`delivery_jobs` per recipient). The screen has an uncertain-effect state where a wrong retry would double-send, and review decisions are accountable approvals. Merge goes to the design engineer's merge batch, not D-180/D-184. Surfaces are ui and api (live contract, `accounting` read and write) plus external-messaging. No money posting happens on this screen (`ledger_posted` is read-only). Product acceptance is required because the client sees new publication and recovery flows and their copy.
