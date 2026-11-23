DECISION: READY
RISK: high
SURFACES: ui, api, security, payments, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 2 of SCR-56 cash forecast: the writes. Part 1 (F-103, read and show) owns every read, the section mapping and the uncertain-state display.
- Scope and data are settled. API 1.25.0 or later has all six forecast routes (forecast, disclosure, actuals/{month}, observations, observations/{id}, lifecycle). D-187 accepted the recommended options in the part 1 specs.
- Build-start waits, not blockers: F-103 on main, F-85 (line adapter, PR #101) and F-87 (the `Actions` slot and `useWorkCommand`). The coordinator holds the builder until all three are on main.
- High risk: it records review verdicts on money forecasts, sends a group disclosure, matches actuals to expected items, and records delivery outcomes and retry or cancel on an uncertain external delivery.
- Merge goes to the design engineer's batch (D-180, D-184). Client acceptance is required.

## Scope
Outcome: on the live cash forecast work page (`/work/{id}`, line `cash_forecast`), the authorised person can review the forecast, choose and send the group disclosure, record and match actuals, and recover an uncertain delivery. Each action goes through F-87's `useWorkCommand`. The forms are `ForecastActions.tsx` in `frontend/src/features/forecast/`, registered as the adapter's `Actions` slot after F-87 is on main. Nothing is added to `src/features/workspace`, and a frame change is named as a lane C dependency. Task: FE-CONNECT-1, write side of W-4001..W-4013 and W-2004.

In (writes only; the controls part 1 left absent):
- `POST /work/{id}/forecast`: review verdicts approve, return and reject, plus withdraw and post. These take role, evidence and reason as the contract requires, and `expected_revision` and `case_revision` as read, null kept as null.
- Record an actual and match it (item_key, actual_id, amount, operation_key, evidence_id), or leave it unmatched with a reason. Uses the month actuals read from part 1.
- `POST /work/{id}/forecast/disclosure`: choose rows, fields and metadata only from the lists the API returns (`row_keys`, `oracle_choices`, `decision_choices`), then send. Nothing payroll-related is offered unless the API lists it.
- `POST /work/{id}/forecast/observations` (multipart): delivered, not_delivered or unknown, with proof. `unknown` is a visible choice.
- `POST /work/{id}/forecast/lifecycle`: retry or cancel, with a reason. Shown only when the read says `can_retry`, `can_operate` or `can_restart`; the restart rule id comes from `restart_policy_id`.

Rules:
- Evidence (binding, PSL answer 1 and D-1): upload the file to the project, then use the action's own upload field or proof endpoint. Where an action has no proof route, the person picks from the evidence list the read supplies. Nothing is preselected and the button stays off when the list is empty. Never invent an evidence id. F-85's unconfirmed `fileToEvidence` is used only where neither exists, and flagged.
- Idempotency key and revision tokens follow F-85/F-87. Until TECH-1-1 lands, never put them in `inputs` to `makeCommand`.
- A retry or cancel of an uncertain delivery shows the recorded state first and is not resent blindly. The uncertain-effect order (record what happened, then retry or cancel) follows the API's `can_restart` and `restart_policy_id`. No invented approvers, attempt counts or amounts.
- Unknown money stays unknown, never 0. Group view still shows no staff names or individual pay (E-26). The disclosure form does not build payroll detail from other reads.
- Hidden, as in part 1 (D-182): the "reviewer not set" warning, and short phone money.
- A write blocked by an unanswered backend question is built on the best reading of the contract and flagged, or held and listed.

Out: all reads and display (F-103); any change to `src/features/workspace` or `work-item`; backend and contract edits; previewing or polling the proof file. Any change to `frontend/mock/finance*` or the payments fixtures is named in build.md for lane B.

Size: the write boards (decide panel and note drawer, group rows and group review verdicts, record actual and match, record what happened, retry and cancel) are about 7 boards, one reviewable PR. If the builder finds it larger, split recovery (observations and lifecycle) into F-103C.

Dependency order: F-103 merged, then F-85, F-87.

## Risk
High. These actions settle forecast review verdicts, match actuals to money items, send a group-facing disclosure that could carry payroll-related assumptions (E-26), and record or retry an uncertain external delivery (`forecast/observations`, `forecast/lifecycle`). That is the sensitive-data, external-messaging and hard-to-undo case in the Lane D rules. The product-decision surface applies because the wording and flow of the review and recovery states are new to the client. PRODUCT-ACCEPTANCE is required.

## Questions
None.
