VERDICT: PASS
COMMIT: 3f684410f771cf53c1103d40aaa7977b09c084b3
REVIEWER: pmo-acceptance
AUTHORITY: PMO delivery acceptance (not client/product acceptance, merge or release)

## Summary
- Delivery is accepted for FE-WORKITEM on this head. The gate passed (142 unit tests, lint, typecheck, build), and technical, UX, UI and QA all say PASS for round 3.
- Acceptance criteria 1-17 and 19-20 have passing QA evidence in `review-qa.md` on this head. Criteria 18 (fixture schema validity) and 21 (gate) rest on `checks.md` GATE: PASS, since QA did not re-run vitest. Hidden-tab polling and the history reload on a changed revision are covered by unit tests only, not by browser runs.
- Scope is clean. The 21 changed paths all sit in the F-03 lane: the work routes, `features/work-item`, the work fixtures, the work tests and e2e spec, plus the agreed additive edits to `frontend/mock/server.mjs` and `mock-contract.test.ts`. Nothing landed in `decide`, my-work, shell, api, styles or architecture.
- Every blocking finding is VERIFIED (UI-1-1, UI-1-2, UI-2-1). UI-1-1 was closed on the design engineer's recorded 14 Nov 2026 decision. No finding is an accepted risk, so none needs an authority.
- QA ran only against the contract mock, never against Django or PostgreSQL. Real access control, real `you_can_act`, real revision changes and agent progress are unproved and belong to the connect feature. Product acceptance is not required (`readiness.md`).

## Findings
- PMO-3-1 | non-blocking | low | pmo | `feature.json` has `operation_ids: []`, but the spec and readiness name E-WORK-ITEM and E-WORK-HISTORY as the operations in scope. Both are covered by the evidence, so the record is incomplete, not the delivery. The coordinator should fill `operation_ids` before merge.
- PMO-3-2 | non-blocking | low | pmo | The `feature.json` copy of acceptance criterion 4 still says "At 390px only the track scrolls sideways". `spec.md` line 202 already holds the 1080px rule, which is the authoritative version: list below 1080px, row from 1080px, checked at 390, 760, 900 and 1079, with no sideways scroll. This also settles UI-3-1, which is still OPEN in the record. Refresh the record's criterion and mark UI-3-1 fixed.
- PMO-3-3 | non-blocking | low | pmo | The traceability to carry forward: `feature.json` has no "carried forward" list. The open non-blocking items are QA-3-1 (mock persona does not vary `you_can_act`; retest wrong-user on the real backend), QA-3-2 (per-id history fixtures for W-1002, W-1003 and W-1005 before demos) and the contract gaps listed in `spec.md` (amount with `unknown=true`, per-station detail and times, history filter counts, Documents tab, CSV, "Ask for access"). The architecture v4 proposal covers the gaps. A-WORKITEM's "unknown amount" part is not met in this feature because the v3 schema has no amount field (PMO-0-1). The fact-level Unknown is shown instead. This is a known, routed contract gap and not a delivery defect.

## Notes
- Parent package claims stop at this slice. F-03 claims only FE-WORKITEM on the mock. It does not claim FE-CONNECT-1, FE-DECIDE or FE-M2. The decision link to `/work/<id>/decide?task=<id>` is a link only. It may 404 until F-04 lands.
- Merge note from the coordinator: F-02 will conflict with this branch in `frontend/mock/server.mjs` (both add a branch). The coordinator resolves it at merge. After the merge, the gate and the F-03 tests must be re-run.
- The error card reads "Reference server_error for support." when the mock supplies no reference. QA noted it. It is a mock limit and not a defect.
- Round limit is 3 and this is round 3. No further rework round is available, so any change after this point needs a coordinator decision.

## Verified
- UI-2-1 | verified | Confirmed in four round-3 files (UI, UX, technical, QA). The list layout holds below 1080px and the row from 1080px, with e2e at 760, 900, 1079, 1080 and 1440 and no sideways scroll.
- UI-1-1 | verified | Closed on the design engineer's decision on agent-station colour (blue), recorded in the spec and in `round-2/build.md`.
- UI-1-2 | verified | Permission board button and tag match the artboard (UI reviewer, round 2).
