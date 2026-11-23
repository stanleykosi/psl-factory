DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, payments, external-messaging, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Blocked by a dependency: the shared line adapter (F-85, PR #101) is not on main, and lane D must build on it without changing the frame.
- 14 boards on SCR-56 is too big for one reviewable PR. Split into part 1 (read) and part 2 (write).
- No client question blocks it. E-25 and E-26 are answered by the backend (API 1.24.0).
- Risk is high: group disclosure can carry payroll-related rows, and the screen sends internal and group forecasts and records delivery outcomes.
- Once F-85 merges, part 1 is READY on its own. Part 2 needs part 1 merged first.

## Scope
Outcome: the cash forecast workspace (SCR-56, line `cash_forecast`, route `/work/{id}`, built on the v7 mock in F-43) reads the live API 1.24.0 and records its actions through the F-85 line adapter. The adapter mapping lives in this feature's folder. The shared frame in `frontend/src/features/workspace` is not changed. If a frame change is needed, name it as a dependency on lane C.

Task: FE-CONNECT-1. Tasks W-4001..W-4013 and W-2004 as in the connection map.

Split proposal (about 7 boards each):

**F-103a, part 1: read and show.**
- `GET /work/{id}/forecast`: stage, finding, audience (internal, management, group), result, jobs, disclosure, matches, review_roles.
- `GET /work/{id}/forecast/actuals/{month}`: rows, actuals, history, with more_actuals and more_history paging.
- `GET .../forecast/observations/{id}` (uncertain delivery state), can_restart and restart_policy_id.
- Group disclosure is shown read-only, with only permitted rows, fields and recipients.
- Empty, loading and uncertain states.

**F-103b, part 2: write.** Depends on F-103a being merged.
- `POST forecast` for review verdicts approve, return and reject, plus withdraw and post. These need role, evidence_id and reason.
- Record an actual and match it (item_key, actual_id, amount, operation_key, evidence_id). Leave unmatched with a reason.
- `POST forecast/disclosure`.
- `POST forecast/observations` (multipart: delivered, not_delivered or unknown, with proof). Show `unknown` as a choice.
- `POST forecast/lifecycle` (retry or cancel, with reason).

Result shapes (E-25): result has status, entity, currency, basis, as_of, findings, expected items, periods and actuals. jobs has ID, status, receipt IDs and retry/operate permissions. disclosure has configuration, permitted rows and recipients, evidence choices and selected fields and metadata. matches has ID, item_key, actual_id and amount.

Payroll in group disclosure (E-26): group recipients get a separate approved projection with only the selected row fields and metadata. The field list excludes staff names, individual pay records and raw payroll input. A payroll-related cash assumption must be explicitly included and reviewed on that exact projection.
- The UI shows only what the API returns and never builds payroll detail from other reads.
- The UI does not offer a payroll row as a selectable field unless the API lists it.
- A group reviewer view carries no staff names or individual pay.

Out: the "reviewer not set" warning (no field in the API, so hide it and say so, per D-182). Shortened phone money ("₦12.4M"): hide unless the formatter is already shared. Unknown money stays unknown, never 0. No invented approvers, attempt counts or amounts.

## Risk
High because the screen sits on money forecasts and actuals matching, group disclosure that may carry payroll-related assumptions (E-26, restricted payroll data), external or group delivery with uncertain-effect recovery (observations, retry or cancel), and untyped response sections (a contract-change risk). Part 1 alone is read-only. If it is shown separately and no payroll-related rows can be seen, it could be treated as medium. Part 2 moves to the design engineer's merge batch as high-risk (D-180, D-184).

PRODUCT-ACCEPTANCE is required: the client must see the changed review and disclosure flow and the wording on the delivery states.
