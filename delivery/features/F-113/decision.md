RECOMMENDATION: AUTO_MERGE
COMMIT: 7ea09ba55efec2f90b009e55042ff1d54c9c80ab
APPROVER: approver

## Summary
- Read-only Delivery tab (SCR-43) on the live `GET /projects/{id}/delivery-overview`. It makes no writes and has no money, payroll, auth or restricted-data surface.
- The diff is 14 files, under the 15-file limit. It includes no migrations, lockfiles, `.github`, AGENTS.md or contract files. Risk is low.
- The round 3 gate, technical, UX, UI and QA reviews, and PMO and product acceptance all name 7ea09ba5. That head is the base 8573a7a1 merged in once (D-193, D-200). GitHub frontend-checks passed on it.
- Product decisions are board changes the design engineer accepted in batch (D-187, D-195, D-184). D-195 also signs the 26 fidelity items, and it signs the amber tone for an uncertain step.
- Open items are non-blocking: QA-2-1 (the live started row is unproven because the demo seed lacks commercial data) and the copy and wording notes QA-3-1 and PMO-3-2.

## Why
The change stays inside readiness's SCR-43-only, no-writes scope. The spec's assumptions are display mappings (row order, date shown, state words), not pricing or policy. Its public-copy items were accepted by the design engineer in D-187 and D-195. Nothing in the diff falls on the always-human lists. The one caveat is that the live started-row path was not exercised against real data.

## Acceptance criteria
1. One overview request on open: met. The hook and tab tests pass, and the PMO and QA reviews record it.
2. Six rows in fixed order even when shuffled: met. `delivery-model.test.ts` covers it, and I re-ran it.
3. A started row shows its fields and the title links to `/work/{id}`: met. Tests pass, and the round 3 fixtures 2501 to 2505 now answer 200.
4. A not-started row has no link, date or reference: met, covered in `delivery-tab.test.tsx`.
5. All states map to tags, and unknown values show UNKNOWN: met by the model test.
6. Hidden parts are absent: met. They are signed as exceptions under D-195.
7. Closure hold reasons: met by the component tests.
8. Closure reasons are silent when the checklist is ready or its read fails: met by the component tests.
9. The checklist call is skipped when it is not needed: met by test.
10. 403 and 404 show the same no-access panel: met by test.
11. 500 or network error shows the error panel, and Try again recovers: met by test.
12. A wrong-shape response shows the error state: met by the model test.
13. No non-GET calls and no write controls: met. The diff touches only reads.
14. Mobile 390px has no horizontal scroll: met per the round 2 fidelity run (mobile score 78.7, waived under D-83 and signed in D-195) and the UX review. I did not re-render it.

I spot-checked by running `delivery-model.test.ts` and `delivery-tab.test.tsx` in the worktree. 2 files and 47 of 47 tests passed. I called no Railway tools.

## For the human
Not applicable. Under D-184 the design engineer checks the merged screen on port 3000 afterwards, and anything they dislike becomes a fix.
