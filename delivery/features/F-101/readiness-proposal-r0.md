DECISION: NOT-READY
RISK: high
SURFACES: ui, api, auth, contract-change, data-migration
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-54 (income detail and schedules, built in F-33 on the v7 mock) is to be reconnected to live API 1.24.0 through the shared line adapter.
- Blocked on a dependency: the shared adapter (F-85, lane C, PR #101) is not on main. Lane D must not change the shared frame, and F-101 cannot map against it until it merges.
- Too big for one PR: 14 boards, with reads, reviews, row corrections, duplicate settlement and adjustment export. Split into part 1 and part 2 below.
- No client decision blocks it. E-21 and E-22 are answered in backend-answers.md. Re-rate to READY once F-85 is merged and the scope is cut to part 1.
- The architecture and design approval gates were not re-verified for this note. The brief names no task IDs beyond FE-CONNECT-1, and no `architecture/` or `design/` evidence was supplied in the feature folder.

## Scope
Binding for the spec writer once F-85 is on main. Task FE-CONNECT-1, line `income_schedules` (W-2701 to W-2712), route `/work/{id}`. The adapter mapping lives in this feature folder.

**Part 1 (this feature, F-101): read and review.** About 7 boards.
- Reads: `GET /work/{work_id}/finance-schedule` showing stage, finding, kind (income or inventory), income rows, result (ready or held, adjusted total, parent amount, additive and reclassification totals, findings, missing_required), `duplicates[]` held, and `returned{review_id, rows[]}` with the reviewer's note.
- Review decision: `POST /work/{id}/reviews` with kind `schedule`, the exact `target_id`, current `expected_revision` and `case_revision`, verdict (approve, return, reject, revoke) and note.
  - `evidence_id` is required, including for approve (E-21).
  - Show only verdicts listed in `review_verdicts[]`.
- "Reviewer not set" is shown from the approval hold code on the read (E-22). Do not invent a field.
- Hide design parts the API cannot fill, per D-182. "Posted to ledger: NO" has no field on this read. Say so in the build note.
- Unknown money stays unknown, never 0.

**Part 2 (new feature, after part 1 merges). The other boards.**
- Correct and resubmit: `POST finance-schedule` with `{action, schedule_id, return_id, row_key, relationship}`.
- Settle a duplicate: `{decisions[], evidence_id, reason}`.
- Export as an adjustment: `{kind additive|reclassification, evidence_id}`.
- `GET/POST /projects/{case_id}/accounting-adjustments/{adjustment_id}` and the source mappings.
- The inventory kind with coverage.

Out: changes to `src/features/workspace` (lane C owns it), new business rules, and any invented approver.

## Risk
High because part 2 exports accounting adjustments and settles duplicates, which change ledger-bound records and are hard to undo. Part 1 alone is a review decision on Finance schedules (`reviews` with evidence and revision checks), so it carries auth and a cross-layer contract change (v7 mock to live bodies), and it is medium on its own. Merge goes to the design engineer's batch (D-180/D-184: money-adjacent). Source: connection map `### SCR-54`, backend answers E-21 and E-22.
