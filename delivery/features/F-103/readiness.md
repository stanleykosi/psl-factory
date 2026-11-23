DECISION: READY
RISK: medium
SURFACES: ui, api, security
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 1 only (read and show) of SCR-56 cash forecast. Part 2 (reviews, disclosure, actuals matching, recovery writes) is F-103B and depends on this merging.
- Scope and data are settled; the backend answered E-25 and E-26 (API 1.24.0). No client question blocks it.
- Wait: the build start waits for the F-85 line adapter (PR #101) to reach main. This is not a readiness blocker. The spec is written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Read-only, but it shows group disclosure that could touch payroll-related rows, so it is rated medium with a security surface.

## Scope
Outcome: the cash forecast workspace (SCR-56, line `cash_forecast`, route `/work/{id}`, built on the v7 mock in F-43) reads the live API 1.24.0. The adapter mapping lives in this feature's folder. The shared frame in `frontend/src/features/workspace` is not changed. If a frame change is needed, name it as a dependency on lane C.

Task: FE-CONNECT-1, read side of W-4001..W-4013 and W-2004.

In (reads only):
- `GET /work/{id}/forecast`: stage, finding, audience (internal, management, group), result, jobs, disclosure, matches, review_roles.
- `GET /work/{id}/forecast/actuals/{month}`: rows, actuals, history, with more_actuals and more_history paging.
- `GET .../forecast/observations/{id}`: uncertain delivery state, can_restart and restart_policy_id, shown read-only.
- Group disclosure shown read-only, with only the permitted rows, fields and recipients.
- Loading, empty and uncertain states.

Result shapes (E-25): result has status, entity, currency, basis, as_of, findings, expected items, periods and actuals. jobs has ID, status, receipt IDs and retry/operate permissions. disclosure has configuration, permitted rows and recipients, evidence choices, selected fields and metadata. matches has ID, item_key, actual_id and amount.

Payroll in group disclosure (E-26):
- Show only what the API returns. Never build payroll detail from other reads.
- No staff names or individual pay on any group view.
- A payroll-related cash assumption appears only if the API lists it on the approved projection.

Out (belongs to F-103B):
- Review verdicts (approve, return, reject), withdraw and post.
- Record and match an actual, or leave it unmatched.
- `POST forecast/disclosure`, `POST forecast/observations`, `POST forecast/lifecycle`.
- Action controls render disabled or hidden, and nothing is sent.

Also hidden, with the gap stated (D-182):
- The "reviewer not set" warning, because the API has no field for it.
- Shortened phone money ("₦12.4M"), unless the formatter is already shared.

Rules: unknown money stays unknown, never 0. No invented approvers, attempt counts or amounts. Where the API does not supply something a board draws, hide it and say so.

## Risk
Medium. It is read-only and sends nothing, but it shows forecast money and group-disclosure content that could carry payroll-related assumptions (E-26), so the security surface applies. The sections of the forecast response are loosely typed, so the mapping must be tested against the live contract in `contracts/psl-factory.openapi.json`. Read-only screens can merge under D-180/D-184. If any payroll-related row can appear in the group view, route the merge to the design engineer's batch.
