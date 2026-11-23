DECISION: READY
RISK: medium
SURFACES: ui, api, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 1 only: SCR-54 income detail and schedules, read and review, reconnected from the v7 mock to live API 1.24.0. Part 2 is F-101B.
- Wait, not a blocker: the shared line adapter (F-85, lane C, PR #101) is not yet on main. The coordinator holds the builder until it merges. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- E-21 and E-22 are answered in backend-answers.md, so no client decision blocks this part.
- The v9 architecture package and the 13 Nov design approval (with the D-173/D-181 exceptions in `design/review.json`) cover SCR-54, as for lanes A to C.
- The review decision is an auth-checked write with evidence and revision checks. It is not a ledger or money-moving action, but product acceptance is required because it is a changed flow.

## Scope
Binding for the spec writer. Task FE-CONNECT-1, line `income_schedules` (W-2701 to W-2712), route `/work/{id}`, screen SCR-54, about 7 boards. The adapter mapping lives in this feature folder. Do not change `src/features/workspace` (lane C owns it). If the shared frame needs a change, name it as a dependency on lane C.

In:
- Read `GET /work/{work_id}/finance-schedule`. Show stage, finding, kind (income or inventory), income rows, and the result (ready or held, adjusted total, parent amount, additive and reclassification totals, findings, missing_required). Show held `duplicates[]` and `returned{review_id, rows[]}` with the reviewer's note.
- Review decision: `POST /work/{id}/reviews` with kind `schedule`, the exact `target_id`, current `expected_revision` and `case_revision`, verdict (approve, return, reject, revoke) and note.
  - `evidence_id` is required, including for approve (E-21).
  - Offer only the verdicts listed in `review_verdicts[]`.
- Show "Reviewer not set" from the approval hold code on the read (E-22). Do not invent a field.
- Hide design parts the API cannot fill (D-182). "Posted to ledger: NO" has no field on this read, so hide it and say so in the build note.
- Unknown money stays unknown, never 0.

Out (F-101B):
- Correct and resubmit rows.
- Settle a duplicate.
- Export as an adjustment, and `accounting-adjustments` and source mappings.
- The inventory kind with coverage. Show inventory only as far as the read supplies it, with no actions.
- Also out: new business rules and any invented approver.

## Risk
Medium. The change is cross-layer (v7 mock to live bodies) and the review write goes through auth, evidence and revision checks (`reviews`), but it does not post to the ledger or move money. The high-risk actions (duplicate settlement, adjustment export) sit in F-101B. Merge goes to the design engineer's batch if the reviewers treat the finance review write as money-adjacent (D-180/D-184). Otherwise it can merge routinely. Source: connection map `### SCR-54`, backend answers E-21 and E-22.
