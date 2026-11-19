VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: eefaf6c5e7f37793673e3d57fce297a55358fad1
AUTHORITY: delivery technical review

## Summary
- Fix round for QA-2-1. The diff from 15db6f7 has three parts. `InlineDecide` remembers the note the last decide carried and reports a 409 through a new `onStale(note)`, before its re-read. `Workspace` keeps `{taskId, note}` and shows the stale sentence plus "Your note wasn't sent: ..." only after the re-read has dropped that task's decide panel. The diff also adds two unit tests and one two-reviewer e2e.
- Two-reviewer 409 after the task closed: correct. `onStale` fires before `reload()`, so the page notice is set before the panel unmounts. `staleShown` needs `!decideTasks.has(taskId)`, so the stale message never shows twice. While the task is still actionable (the scenario-cookie 409), the panel's own stale view and kept note still apply, as before.
- Scope: `<InlineDecide>` is rendered only at `Workspace.tsx:693`. The change is additive and fires only on a decide 409 whose re-read closes the task. Other lines (F-30, F-33, F-34, F-36, F-41, F-42, F-47) behave the same except in that exact race. There they now get the same correct stale notice instead of a silent page, which matches the shared stale contract. `checks.sh` passed on this head.
- Authority: none is implied. The notice is a plain warning callout and has no buttons. The re-read item has no decide steps, so no decision control is drawn for the closed task. A stale reviewer acts on the new state only through steps the backend returns on the re-read. Nothing is resent automatically: one decision write in both tests. The note is rendered as React text, so it is escaped.
- The new tests truly fail without the fix. I copied 15db6f7's `Workspace.tsx` and `InlineDecide.tsx` over the worktree and ran `tests/leadership-report.test.tsx`: 2 failed (both QA-2-1 tests) and 34 passed. I restored with `git checkout --`, and the worktree is clean at 971bf73a. With the fix, the QA-2-1 tests pass 2/2.

## Findings
- TECH-3-1 | non-blocking | low | frontend | `staleDecide` is cleared only by `onDeciding`. Unlike `decided`, it is not tied to `workspace.revision`, so the stale notice would stay through a later re-read that moves the item on again. Expected: it goes when the item moves on, like `decidedShown`. Actual: it stays until the next decide on this page. `frontend/src/features/workspace/Workspace.tsx:244`.

## Verified
- QA-2-1 | verified | Re-ran `npx vitest run tests/leadership-report.test.tsx -t QA-2-1`: 2/2 pass. Both tests assert the sent or returned re-read state, the stale sentence, the unsent note (return only), no `.ws-idecide` panel and exactly one `/decision` POST. The same tests fail 2/2 against the round-2 `Workspace.tsx` and `InlineDecide.tsx`. The e2e reproduces QA's two-tab race at both viewports. I did not re-run it; `checks.sh` exit 0 covers it.

## Notes
- Carried forward without re-review: round 1 and 2 assessments of reuse, the income line, no `/me` reads and no resend path. Only `InlineDecide`/`Workspace` decide-outcome code changed here, so they are unaffected.

## Impact assessment (re-pin to eefaf6c5, coordinator, 19 Nov)
Done by the coordinator rather than an independent reviewer: the weekly usage limit stopped all reviewer agents, and the design engineer said "Yes, merge both".
- Old head 971bf73a; new head eefaf6c5 = merge of dlv-00 (F-34 hypercare, F-36 RFP intake), plus a guard-test allowance for the W-32xx fixtures.
- Conflicts re-resolved in WorkItemOverview.tsx, Workspace.tsx, labels.ts, mock-contract.test.ts, income-schedule-mock.test.ts and BACKEND-HANDOFF.md. Checked against dlv-00: STATION_LINES equals the old schedule set, so F-33/F-42 keep stations; AGENT_BESIDE_LINES adds only leadership_report (this feature's own line); the settled-task rule extends only to that line. The other src differences from dlv-00 are F-35's own feature (stale notice, Sections, InlineDecide).
- Evidence (merge-checks.log): coordinator clean re-run checks.sh exit 0, 2863/2863; e2e leadership-report, delivery-hypercare and rfp-assign 85/85.
- Verdicts carry forward.
