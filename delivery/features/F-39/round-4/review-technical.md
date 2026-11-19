VERDICT: PASS
COMMIT: 644c8aafaff61edb86748e73808886fdcaf014dd
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- Round 4 changes 4 files (`git diff c706d6a7..45ae7b66`): InlineDecide.tsx, Workspace.tsx, and one new block each in the unit tests and the e2e tests. It fixes QA-3-1 with the smallest change possible: an `onStale(note)` callback, plus a page-level warning that shows only when the 409 re-read has removed that task's decide panel.
- The code is correct for a real two-reviewer 409. The stale view raises `onStale` with the note that was actually sent (trimmed, or '' for escalate/approve) before `reload()`. Workspace keeps `{taskId, note}`. `staleShown` needs `!decideTasks.has(taskId)`, so the scenario-cookie 409 (panel still drawn) keeps InlineDecide's own stale view and "Review the latest", as before.
- The changed lines match F-35's 971bf73a exactly. The +/- lines of both files diff empty against `git show 971bf73a`. The F-39 and F-35 heads produce 0 conflicts in InlineDecide.tsx, and every stale-fix line merges.
- Effect on other lines: Workspace.tsx is the only `<InlineDecide>` caller, and today only income_schedules (F-33) and escalation decide in place there. The new callout appears only after a 409 stale decide whose re-read drops the task. Nothing else changes, and the callout offers no button and implies no authority. It is plain text, React-escaped.
- Head checks: `npx vitest run tests/escalation.test.tsx tests/income-schedule.test.tsx` passed 76/76. At c706d6a7 the new tests cannot pass: `noteNotSent` does not exist, and the stale sentence renders only inside the InlineDecide panel, which unmounts. That matches the builder's reported revert run (3 failed) and QA's live repro.

## Findings
- TECH-4-1 | non-blocking | low | frontend | Merging F-35 and F-39 adds one trivial conflict beyond the 4 Workspace.tsx conflicts that already existed between c706d6a7 and F-35: the `./labels` import line (Workspace.tsx:19). Git puts it in the same hunk as the identical `DECIDE_TEXT, InlineDecide` import change on the next line. Resolve it by taking F-35's import (`AGENT_BESIDE_LINES`, `STATION_LINES`) plus any name F-39 still uses. The stale-fix lines themselves merge cleanly (merge-tree result: lines 23, 261, 269, 642-647 and 722 come through once).
- TECH-4-2 | non-blocking | low | frontend | F-33 (income_schedules) gets the new notice but has no two-reviewer test (the builder's follow-up). Neither does F-16's separate decide page (`useDecision` views), which this change does not touch. Add an income-schedule lost-race test when F-33 is next opened.

## Verified
- QA-3-1 | verified | The `onStale` call (InlineDecide.tsx, stale branch before `reload()`) and `staleDecide`/`staleShown` (Workspace.tsx:236-246, 615-624) keep the stale sentence and the unsent note in a `role="alert"` warning once the re-read closes T-3602. It clears on the next decide (`onDeciding`) and stays hidden while a step is pending or has a notice. The new unit tests serve the decided fixture from inside the 409 handler, so the panel really goes: desktop reject, phone Drawer reject, and escalate naming no note, each with one POST. The e2e uses two pages on the live mock's own 409 at 1440 and 390, checks the notice is still visible after 1.5 s, and checks that one decision body was sent and axe is clean. 76/76 tests pass on head. The fix is identical to F-35 971bf73a.
- Impact assessment: no other file changed since c706d6a7, so every round-2/3 finding and criterion carries forward unchanged.

## Impact assessment (re-pin to 644c8aaf, coordinator, 19 Nov)
Done by the coordinator rather than an independent reviewer: the weekly usage limit stopped all reviewer agents, and the design engineer said "Yes, merge both".
- Old head 45ae7b66; new head 644c8aaf merges dlv-00 (F-35, F-34, F-36). TECH-4-1 as expected: the stale-notice code in InlineDecide/Workspace was identical on both sides and merged without conflict.
- Six conflicts resolved by hand:
  - drawsAgentCard keeps dlv-00's AGENT_BESIDE_LINES rule (schedule lines and the leadership report while working) and adds escalation (working or done), so other lines are unchanged.
  - bannerTone keeps F-35's report branch and adds the escalation branch (neutral → info) before the schedule rule.
  - The settled-task rule is the union of both.
  - stationsDrawn comes from dlv-00.
  - The test allow-lists add W-36xx.
  - The handoff keeps both sections.
- Evidence (merge-checks.log): tsc and eslint clean; checks.sh exit 0, 2903/2903; e2e escalation, leadership-report and income-schedule 100/100.
- Verdicts carry forward.
