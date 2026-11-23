DECISION: NOT-READY
RISK: high
SURFACES: ui, api, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-58 (ledger source reference, F-45, 12 boards) is to move from the v7 mock to live API 1.24.0 through the shared line adapter.
- Blocked by a dependency: the shared line adapter F-85 (lane C, PR #101) is not on main, and lane D features must not change the shared frame.
- Too big for one PR: 12 boards against a guideline of about 8, and it mixes reads with three separate write families.
- Backend answer E-29 is settled: the protected Ledger response gives the latest decision's reviewer and date, and a stable hold code when the independent-reviewer rule blocks the person.
- Re-submit as two features once F-85 is merged.
- Not assessed: `feature.json` has no approval evidence, `design/review.json` was not read, and `design.py check` was not run. The unmerged F-85 alone blocks this feature.

## Scope
Binding for the spec writer once F-85 is on main. Task FE-CONNECT-1, route `/work/{id}`, line `ledger_sources` (W-4201..W-4213).

Proposed split:
- **F-104a, read and record (about 6 boards).**
  - Reads: `GET /work/{work_id}/incumbent-reference` (source, observation, `check_id`, `can_observe`, `has_attachment`, lineage ids, `review_options`, `latest_decision`, `verified`), plus the source `outcome` (`reported_posted` or `uncertain`).
  - Writes: `POST /work` (`finance-ledger/v1`), `POST /projects/{case_id}/incumbent-evidence`, `POST incumbent-reference` (`found|not_found|unknown|multiple`), multipart `.../observations`, `GET .../observations/{check_id}`, and approve or reject (reason and evidence required).
  - Also in 104a: the reviewer name and date from E-29, and the hold code for the independent-reviewer rule.
- **F-104b, duplicates and recovery (about 6 boards).**
  - `GET/POST /projects/{case_id}/incumbent-resolutions` (`claims[]`, `resolutions[]`, `reference_correction|duplicate_alias`, then confirm, return or withdraw).
  - `recheck|restart`, and the lineage display.

Rules for both parts:
- Hide what API 1.24.0 does not supply and say so (D-182): the month-end link for ledger sources, and the "refused, nothing was posted" state.
- Unknown money stays unknown, never 0.
- No invented approvers.
- The adapter mapping lives in the feature folder. Any frame change is a dependency on lane C.

Out of scope: payroll (SCR-59), SCR-53 and SCR-57.

## Risk
High. The screen writes evidence and approve/reject verdicts that gate a ledger reference. Duplicate resolution retires records, which is hard to undo. The independent-review rule ("not the capturer, not the observer") is an authority control (`auth`). The reshaped payloads change the contract against the v7 mock (`contract-change`). Merge goes to the design engineer's batch. The client must see the changed review and duplicate flows, so acceptance is required.
