STATUS: READY
COMMIT: 9ebc7cbc98a2cedb7345180e50c1489ca0930d19
BUILDER: builder
LANE: full

## Summary
- **Notices only for a settled decision.** After a 200 decide, the page shows an "approved / returned / rejected" notice only when the decide's `work_state` is not `effect_uncertain` and the page's re-read item is neither `effect_uncertain` nor awaiting a `reconcile`. This is the F-16 `DoneView` rule. Otherwise the page shows a warning "Schedule v1: result not confirmed", and the re-read item's uncertain or reconcile view leads.
- **The notice is tied to the re-read revision.** It disappears once the item moves on or another step is sent or answered.
- **One page re-read after an uncertain decide.** It happens only after `useDecision`'s reconcile has settled.
- **The read-only branch keeps the income line's stations and agent card.** When `workspace.revision` is absent, the stations and the working agent card are still drawn, so no data is dropped.
- **Board layouts are unchanged**, so no fidelity run this round: the round-1 run and scores stand (`round-1/fidelity/scores.txt`). The changes touch only notices after a write and the read-only branch, which no board fixture uses.

## Changes
- `frontend/src/features/workspace/InlineDecide.tsx`
  - The settle effect waits for `useDecision`'s own re-read (`reloaded` or `refreshFailed`).
  - It then runs `page.reload()` and calls `onDecided({text, settled, revision})`.
  - `settled` is false when the result's `work_state` is `effect_uncertain`, when the page's re-read item is `effect_uncertain` or has a `reconcile`, or when either re-read failed.
  - An uncertain write now triggers the page re-read only once the reconcile has finished (`uncertain && submit.status === 'idle'`).
  - New wording `notConfirmed`, the same as F-16's "<label>: result not confirmed".
- `frontend/src/features/workspace/Workspace.tsx`
  - `decided` now holds `{text, settled, revision}`. It is shown only while its revision equals `workspace.revision` and no step write is pending or answered.
  - A settled notice is a success callout in the live region. An unsettled one is a warning callout with `role="alert"`.
  - The read-only `Workspace` branch draws `LineStations` and `LineAgent` for the income line.
- `frontend/tests/income-schedule.test.tsx`: 9 new tests (37 in total).

## Fixes
- TECH-1-1 | 9ebc7cbc | A 200 decide is worded as an outcome only when the result's `work_state` is not `effect_uncertain` and the page's re-read is neither `effect_uncertain` nor carrying a `reconcile`. Otherwise "Schedule v1: result not confirmed" (warning), and the re-read item's uncertain notice leads. Tests cover approve, return and reject with `work_state: effect_uncertain`, plus a 200 "verified" whose re-read is `effect_uncertain` with a `reconcile`. All 4 fail on round-1 code.
- TECH-1-3 | 9ebc7cbc | The decision notice carries the revision of the item re-read after it. It is hidden once `workspace.revision` changes or a step write is pending or answered. Test: Return, then Correct and resubmit leaves no "was returned" notice (fails on round-1 code).
- TECH-1-4 | 9ebc7cbc | After a 5xx or network failure, the page re-reads once, after the reconcile settles. Test with slowed item reads: exactly 2 item GETs after the decision, the reconcile then the page. Round-1 code made 3.
- TECH-1-2 | 9ebc7cbc | The read-only branch (no `workspace.revision`) draws the income line's stations and working agent card, so the screen-reader copies `WorkItemOverview` skips are still on the page. Test: W-2701 without a revision has 5 stations, one "Stations" region and one "Agent at work" region (fails on round-1 code).
- TECH-1-5 | 9ebc7cbc | Coordinator accepted the two `WorkItemOverview.tsx` edits in this lane. New tests show other lines are unchanged:
  - W-2304 decided (minutes) still draws "Only a PMO Lead can decide." and its screen-reader station track, with no income station row.
  - W-2411 (issue) keeps its screen-reader station track and agent card, and draws none of the income line's.

## Acceptance criteria
Unchanged from round 1 (`round-1/build.md`). Criteria 9 and 14 are strengthened:
- An unsettled 200 never says approved, returned, rejected or verified.
- An uncertain decide makes one page re-read and no resend.

All 25 criteria are still met; evidence is under Validation.

## Validation
- `cd frontend && npx vitest run tests/income-schedule.test.tsx`: 37 passed.
- The same file run against round-1 `src` (stash): the 6 new TECH-1-1/1-2/1-3 tests fail. The TECH-1-4 test fails with 3 reads instead of 2. The two TECH-1-5 tests pass, as intended.
- `npx vitest run` on workspace, workspace-step, issue-detail, minutes, minutes-end, work-item, document-review and decide: 8 files, 316 passed.
- Lint (`--max-warnings 0`) and `tsc --noEmit` on the changed files: clean.
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh`, run under the shared lock with load 13.3: exit 0.
  - Django check found no issues.
  - Lint, typecheck and build succeeded.
  - 102 test files, 2312 tests passed. No load flakes.
- `cd frontend && E2E_PORT=4881 MOCK_PORT=4880 npx playwright test e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/finance-month-end.spec.ts`: 105 passed (3.2 min).
- No fidelity run this round: layout unchanged, round-1 scores stand.

| Board | Coverage | With exceptions | Visual |
|---|---|---|---|
| SCR-54-desktop-investigating | 83.3 | 100 | 87.8 |
| SCR-54-desktop-review | 86.1 | 100 | 76.6 |
| SCR-54-desktop-returned | 75 | 100 | 72.9 |
| SCR-54-desktop-verified | 87.1 | 100 | 75.9 |
| SCR-54-mobile-investigating | 77.8 | 100 | 84.7 |
| SCR-54-mobile-review | 75 | 100 | 80.5 |
| SCR-54-mobile-returned | 71.4 | 100 | 83.2 |
| SCR-54-mobile-verified | 66.7 | 100 | 85.1 |

All 8 boards have D-83 waivers, as in round 1.

## Open
- Security note for the backend (from the round-1 security review): E-TASK-DECIDE has no idempotency key. The page never resends on its own, but please add it to the backend items.
- Still open from round 1:
  - The frame's phone History link is 42×24.
  - All exceptions and waivers are pending the design engineer.
  - F-31 and F-32 overlap in `Workspace.tsx`, `proposals.ts`, `workspace.css` and `mock-contract.test.ts`.
