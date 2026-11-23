DECISION: READY
RISK: high
SURFACES: ui, api, security, auth, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-107 is part 1 of SCR-57 (business-unit totals): the 8 boards through the approved result. The 6 publish, receipt and verified boards become F-107B.
- The earlier block (D-PAYROLL-VISIBILITY, F-44) is resolved for build by D-187 / LD-Q1 "Build on the API": show exactly what the API serves each person, hide any board figure it does not give that person, and send the merge to the design engineer's merge batch.
- The backend answers settle the data. E-32: staff BU totals use the exact eligible payroll match run, not the published aggregate. E-27: `inputs` and `result` fields are known, and a recipient does not get private staff counts. E-28: `POST business-units` takes prepare_rule, publish and restart. Independent approval goes through `/reviews` with kind business_unit. E-26 and E-30 keep group and recipient views to approved projections.
- Waits, not blockers: F-85 (shared line adapter, PR #101) and F-108/F-110 (the payroll match SCR-57 reads) must be on main before the build starts. The coordinator holds the builder until then.
- I did not run `design.py check` (no shell in this role). The client approval and the D-173/D-181 exceptions in `design/review.json` are taken as recorded in the lane D context.

## Scope
Outcome: a permitted Finance reviewer sees the BU totals line, reviews its source and exception rule, and approves the result, showing only what the API serves to that person. Nothing is sent in this feature.

In (8 boards): `SCR-57-{desktop,mobile}-{source-review,investigating,held,result-review}`.
- Source and exception-rule review: approve or return (no Reject), recorded through `POST /work/{id}/reviews` with kind business_unit.
- The counts-only check and the small-group hold. The hold shows the authorised staff-facing finding from `result.codes`. No minimum group size is invented.
- Result review: BU, staff and staff cost as `money` decimal strings from `totals`, with `period` and `currency`. Unknown shows "Unknown", never 0. The page computes no sum, count or percentage.
- Reads: `GET /work/{id}/business-units` (`stage, finding, inputs, result, review_subjects[], proofs[], can_publish, can_correct, recipient_only`) and `GET /projects/{case_id}/business-unit-intake` (`payroll[]`, `events[]`, `rules[]`, `comparisons[]`). Writes: `POST /work` (`finance-bu/v1`), `POST business-units` with `prepare_rule` and `restart` only, and the review above. Task: FE-FIN-BU.

Hidden, not invented (D-182 rule, D-187): any figure the API does not give that person, for example "Legal (2 people)" for a reader who is not entitled to it, the minimum-group-size number unless inside `result`, and recipient counts ("6 BU heads"). When `recipient_only` is true, show the reduced view only. Say so in the spec and PR.

Out, for F-107B (depends on F-107 merging): `SCR-57-{desktop,mobile}-{publish,receipts,verified}`: the `publish` action (sends to the CEO and BU heads), `POST /work/{id}/aggregate-receipt`, recipient confirmation, verified states and cancel-after-publish. Also out: the Event mode (no board), the payroll import and run (F-108/F-110), Setup editing, backend, OpenAPI, shared frame changes in `frontend/src/features/workspace` (lane C owns that).

Binding for the spec:
- Authority comes from the server (`can_publish`, `can_correct`, `recipient_only`, `review_subjects[]`). The UI infers no role.
- No names, staff IDs or individual pay in any fixture or the DOM. A restricted payroll row has no link, and 403 and 404 look the same.
- Send the revision tokens and idempotency key as lane C's rules require, never inside `inputs`.
- Board conflicts to settle in the spec, not in the API: G-57-4 (6 vs 4 BUs, 7 vs 6 recipients). Build to the live data and flag any board count that the API does not supply.
- Name any change to `frontend/mock/finance*` in build.md, so the coordinator can tell lane B.

## Risk
High: the screen shows payroll-derived money aggregates (restricted payroll, INV-RESTRICTED) and sits one step from sending them to people outside Finance. A wrong per-person view or a small-group leak cannot be undone. Surfaces are ui, api, security and auth (a per-person disclosure view with server-decided authority) and product-decision (D-187 chose to build on the API's disclosure; PSL has not recorded D-PAYROLL-VISIBILITY itself and can overrule). The merge goes to the design engineer's merge batch, not the routine route. Payments is not ticked because F-107 invoices and posts nothing.
