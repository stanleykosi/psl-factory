VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: d20fd9b2ccee7be267936cc2758358989ecdedbb
AUTHORITY: delivery technical review

## Summary
- I reviewed the diff 9ebc7cbc..d20fd9b2 (2 commits). It changes `Workspace.tsx`, `InlineDecide.tsx`, `WorkItemOverview.tsx`, `workspace.css`, two test files and the W-27xx fixtures. It does not touch `mock/*.mjs` or `backend/`.
- TECH-2-1 is fixed. `send` calls `onDeciding()` before `review.decide(...)`, which clears `flow.notice` and `decided`. The next `onDecided` is then always shown.
- `bannerTone` only changes on the income line. The expression for every other line is copied unchanged into the else branch, and a regression test covers it.
- W-2712 works on the existing mock path, so no server change was needed. No money rule regressed.
- `npx vitest run tests/income-schedule.test.tsx tests/income-schedule-mock.test.ts` on this head: 52 of 52 passed.

## Findings
None new.

## Verified
- TECH-2-1 | verified | `InlineDecide.tsx` `send` returns early when `!ready || busy || off`, so only a decide that is actually sent calls `onDeciding()`, and it does so before `review.decide`. `Workspace.tsx` `onDeciding` runs `flow.setNotice(null)` and `setDecided(null)`, with stable `useCallback` deps. `decidedShown` keeps its `flow.notice === null` guard, which no longer suppresses the decision notice, because the decide clears it. If the decide fails (409/403), only the earlier notices are cleared. The panel's own error still shows, and no outcome is claimed. Two tests cover this: a step's done notice followed by Approve shows "Schedule v1 is approved" and the step notice is gone, and the same sequence on W-2712 shows "Schedule v1: result not confirmed" with no outcome words.
- bannerTone | verified | The new `INCOME_LINE` branch gives problem when the status tone is `stopped` or `uncertain`, or any station is `stopped`. It gives success when the tone is `verified`, and warning otherwise. The tone comes from data only, never from the words. The non-income expression is identical to round 2. Tests: W-2703 and W-2702.reject draw problem, and W-2704 draws no banner. Another test checks other lines: weekly W-2209 draws warning, issue W-2412 problem, issue W-2414 success, and minutes W-2304 and document review W-2901 draw none.
- W-2712 fixture | verified | `mock/server.mjs:177-181` serves `work[<id>.<verdict>]` and answers `work_state: (decided ?? item).state`, and there is no `mock/` code diff. W-2712.json is W-2702.json with only the ids changed (W-2712/T-2712). Each sidecar has `state: effect_uncertain`, `view: effect_uncertain`, status "DECISION NOT CONFIRMED"/`uncertain` and revision 2. Its stations are left current/not started, not earned or verified, so no outcome is implied. Sidecars and items pass E-WORK-ITEM validation (mock test "twelve items and their sidecars"). The mock decide test answers 200 `effect_uncertain` for approve, return and reject, and the re-read is `effect_uncertain`.
- Reject consequence | verified | The only change is a `consequence` string added to the reject step in the fixtures W-2702, W-2703.next, W-2705, W-2707, W-2708 and W-2711. W-2711's step is malformed (`verdict: post`) and is not drawn. `InlineDecide` still renders `<Consequence step>` from the step and adds no text of its own. The test "UX-2-2" deletes the consequence and asserts that none is drawn.
- Money rules | verified | The src diff touches no amounts. It adds no `parseFloat`, `Number(`, `reduce(` or `compactAmount`, adds no buttons beyond the task's steps, and leaves `useDecision` unchanged: one send, never resent, and the claim and body are as before. The `AgentCard` `foot` is optional, so cards without it render exactly as before. The Ask Chidi link goes to `/assistant`, the same as `Links.tsx`, and is moved out of the links only on the income line while the agent is working (`agentSide`). The test checks that there is exactly one such link.
