VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 5fd62b4c65d9c80c66ebf0f6e3dd37bb0ddb8dc0
AUTHORITY: delivery technical review

## Summary
- The source change is small. A new `scheduleLine()` in `labels.ts` covers `{income_schedules, fixed_assets}` and replaces each of F-33's five `INCOME_LINE` / `'income_schedules'` checks one for one (`Workspace.tsx`, `WorkItemOverview.tsx`). For `income_schedules` it gives the same result as before, so F-33's income line behaves exactly as it did. `income-schedule.test.tsx` and `income-schedule-mock.test.ts` pass, and `InlineDecide.tsx`, `proposals.ts`, `Sections.tsx`, `src/api/**` and `mock/server.mjs` are untouched.
- Money rules:
  - Every `cells[].money` across the 21 W-39xx files is a decimal string (31 cells with `unknown:false`).
  - The W-3910 Hilux cell has no `amount` and `unknown:true`. The test confirms it reads "Unknown".
  - The diff adds no `parseFloat`, `Number(`, `.reduce(` or compact amount.
  - All 21 files are `sample: true`.
- Holds:
  - W-3907, W-3908 and W-3909 are `setup_needed` with "SETUP NEEDED" `stopped`, no steps, and no task the person can act on.
  - The `next` sentence names Setup in words.
  - W-3909 stops at station 4.
- Decide path:
  - Controls come only from `tasks[].you_can_act` and the steps (W-3905, W-3906 and W-3912 have none). Nothing reads `/me`.
  - Success shows only after the re-read. A 200 whose re-read is unchanged never says approved.
  - W-3911 and network or 500 failures read "result not confirmed" with one POST.
  - The Calculate station is `waiting`, which `currentStationIndex` treats as current (P-4, recorded in BACKEND-HANDOFF).
- The changed F-33 assertion only adds the new id range (`/^W-(27|39)/`), and W-2706's hold checks are untouched. Nothing else is loosened. The mock-contract links allow-list adds only `W-3901.json`.
- I re-ran `asset-schedule.test.tsx`, `asset-schedule-mock.test.ts`, `income-schedule.test.tsx` and `income-schedule-mock.test.ts`: 98/98 passed.

## Findings
1. TECH-1-1 | non-blocking | medium | frontend | **Fixture lifecycle facts go backwards.**
   - **Problem:** the `facts` lifecycle moves backwards in the later fixtures. `W-3902.json` has drafted `earned` and reviewed `current`. `W-3902.approve.json` has drafted and reviewed `earned`. But `W-3903.approve.json` and `W-3904.json`, the calculating state reached after both approvals, have drafted, reviewed and approved all `not_yet`. `W-3909.json` (held at Calculate after both reviews) has reviewed `not_yet`.
   - **Why it matters:** on the schedule line the facts strip is screen-reader only (`WorkItemOverview.tsx:706`). A screen-reader user who approves the dates hears "Drafted: not yet, Reviewed: not yet". That contradicts the stations and the re-read the page draws.
   - **Expected:** later states keep or advance the earlier facts, for example drafted and reviewed `earned` on W-3903.approve, W-3904 and W-3909, or whatever the backend item says.
   - **Actual:** the paths are `frontend/mock/fixtures/work/W-3903.approve.json`, `W-3904.json` and `W-3909.json`, all under `.facts`. This is sample data only and the page logic is correct, so the finding is non-blocking.

## Notes
- `SCHEDULE_LINES` in `labels.ts:71` is a second home for the schedule-line set until F-35 merges. The builder flags this, and whichever feature merges second should keep a single set.
- On the date-review fixtures the register task is `T-3931` (as the spec's table says), not `T-3902`. The handoff text names no id there, so nothing contradicts it.
