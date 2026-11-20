VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: ea9718cd5eeb3fd267df59ebb13d7373165cd43e
AUTHORITY: delivery technical review

## Summary
- TECH-1-1 is fixed in the shared `useWorkspaceStep.ts`. On a 200 `done` or `queued`, the hook now runs `await page.reload()` before it sets the notice. The `effect_uncertain` branch is unchanged: it locks every step and shows its notice at once, then re-reads. `writing.current` and `pending` are held until after the re-read, so no step can send twice while it is in flight. `page.reload()` never throws (`usePageReload.ts:42-56`), so the notice is never lost.
- The hook change affects every line that submits through it (weekly, minutes, issue, engagement, release, income, payments, plus the assign and inline-decide neighbours). The only change those lines see is when the notice appears. Forms already closed only after the re-read, because `{kind:'done'}` was returned after it before this change too. All their test files pass unchanged.
- The merged `workspace.mjs` order is: F-31 `servedAs`, then F-28 `audience`, then F-41 `<id>.next.<step>`, then `<id>.next`. The only step-keyed files are `W-2301.next.internal` and F-41's three W-3801 sidecars, and the only `serve` script is `W-2601.steps.json`, which has no `.next.<step>` file. So F-31 and F-33 resolve as on dlv-00.
- Compared with dlv-00 (4059b84a), F-41 changes only the `inDrawer` condition in `Workspace.tsx`, adding `REMINDER_LINE`. The issue, engagement and income lines are unchanged. The money rules (decimal strings, Unknown is never 0, no computation) and the reminder lock (`allLocked` = press lock or `awaitingReconcile`; a failed send keeps that step locked) are the same code reviewed in round 1.
- No assertion was loosened. The only test line removed compared with dlv-00 is the `sample` check. It was replaced by the narrow W-3813 exemption already accepted in round 1. The other test changes are additions or the F-32 Delivery tab from the merge. Ran: 13 files (payments, payments-mock, payment-reminder, workspace-step, workspace, weekly, weekly-returned-received, minutes, minutes-end, issue-detail, engagement-planning, income-schedule, release-gates): **449 passed**.

## Findings
None.

## Verified
- TECH-1-1 | verified | `useWorkspaceStep.ts:117-124` now sets the done and queued notice after `await page.reload()`, and the uncertain path at lines 111-115 still locks before the re-read. The new test `payment-reminder.test.tsx` "TECH-1-1: no "Done: Send reminder." while the re-read is in flight" holds the second GET open. It asserts the exact notice text and SENT are absent, then lands the GET and asserts both appear. This closes round 1's regex gap. It passed here, along with the workspace-step, weekly, minutes, issue, engagement, income and release test files.
- TECH-1-2 | verified | No code change was made. The deviation is recorded in round-2 `build.md` under Fixes: a hung send stays busy, never resends, and the page does not move on by itself. A frame-level request timeout is noted for the backlog, and the backend's resend refusal (BACKEND-HANDOFF priority 1) is the guard. This is accepted as a record, with no change to its round-1 impact.
- TECH-1-3 | verified | `PaymentsView.tsx:364-368`: the submit applies `SEARCH_MIN_CHARS` to the trimmed text, or allows an empty box. The new `payments.test.tsx` case checks that Enter on "H" sends no read after 400 ms and Enter on "Ha" sends `q=Ha`. It passed here.

## Notes
- If the re-read after a 200 fails, the "Done" notice still shows next to the page's could-not-refresh state, and every step stays off through `page.refreshFailed`. This matches the F-33 InlineDecide precedent (`doneRead` includes `refreshFailed`) and is not a regression.
- The `model.ts` doc comment no longer quotes a board value ("<reference> · overdue <n> days").
