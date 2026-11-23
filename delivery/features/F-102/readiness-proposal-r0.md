DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none

REVIEWER: readiness

## Summary
- Two gates fail. The shared line adapter F-85 (lane C, PR #101) is not on main, and SCR-55 has 14 boards, which is too many for one reviewable PR.
- The backend answers are in: E-23 (basis review) and E-24 (accounting note link) are both answered. No client decision blocks the feature.
- The live API 1.24.0 supplies the reads and writes the screen needs. The connection map rates effort M.
- Risk is medium. The screen is a read-mostly schedule with finance review decisions. It moves no money and posts nothing to the ledger (`ledger_posted` is read-only), and it has no restricted payroll data.
- Proposed split: part 1 is F-102a (read side), part 2 is F-102b (writes). Part 1 can start once F-85 merges.

## Scope
Outcome: the fixed asset (PPE) schedule workspace (line `fixed_assets`, W-3901..W-3912, task FE-CONNECT-1) reads the live register and schedule and records its reviews through the F-85 line adapter. The adapter mapping is built in this feature's folder. The shared frame in `frontend/src/features/workspace` is not changed. If a frame change is needed, it becomes a dependency on lane C.

Part 1, F-102a (reads, about 7 boards):
- `GET /work/{work_id}/assets`: stage, finding and the register (entity, provider, currency, period, assets, events, closing controls).
- The depreciation schedule, either ready or held, with its rows, totals and scope.
- The review options and who may review what.
- The unclear dates and proof states, including the date-proof PDF (`GET /work/{work_id}/assets/date-proofs/{fact_id}`).
- The accounting-note link (E-24): shown only when the person can read the exact Finance mapping.
- Show `completeness` and `native_source_verified`, which are live data the design does not draw yet.
- Start a case with `POST /work` (`finance-ppe/v1`).

Part 2, F-102b (writes, about 7 boards):
- Capture a register: `POST /projects/{case_id}/asset-registers`.
- Record dates with proof: `POST .../asset-registers/{register_id}/dates` (multipart).
- Opening proof after a return: `POST /work/{id}/assets/opening-proof`.
- Reviews: `POST /work/{id}/reviews`, with purpose `register`, `basis` or `schedule` and verdict approve, return, reject or revoke.
- The basis review (E-23) is a separate justification review for the chosen date or calculation basis. It is offered only when `review_options` lists it.

The exact board split should be confirmed against the 14 boards in F-42 before the spec.

Out of scope, hidden per D-182 and listed as not supplied by the API:
- "Chidi never reads asset values" (no API guarantee).
- The accounting-note text (the API gives only a link).
- The phone short money form.

Rules:
- Unknown money stays unknown, never 0.
- Do not invent approvers or business rules.
- Offer a review only where `review_options` allows it.

## Risk
Medium. The change is cross-layer: it reshapes reads, adds a basis review, and adds multipart upload writes. It also records finance approval decisions, which makes `auth` a surface (per-record review authority). It touches no money movement, no ledger posting and no restricted payroll data, so routine merge under D-180/D-184 is possible. Part 2 (review decisions and uploads) deserves closer review. The product acceptance is required because the basis review is a new flow and some boards are hidden.
