STATUS: READY
COMMIT: 7fa112fbc1c004292685163cfe2e8a25ad525c54
BUILDER: builder
LANE: full

## Summary
- Income schedule now waits for the re-read before saying "approved" (same rule as the ledger line); a real two-reviewer 409 test is added.
- Leadership report stale notice adds the next-step sentence and takes focus.
- Escalation mock completes W-3602 "Send for review"; response mock completes T-3401 team input with proof.
- History link is a 44 by 44 target at 390 (desktop unchanged); rfp-intake-mock ECONNRESET fixed by a retried reset.
- No fidelity run: no board changes except the History link size on phones.

## Changes
- frontend/src/features/workspace/Workspace.tsx: `waitsForReread` (ledger + income_schedules) replaces the ledger-only check for "result not confirmed" and the decided hand-off; the stale notice for `leadership_report` only gets the extra sentence, tabIndex -1 and focus. Shared file: every change keyed to the line.
- frontend/src/features/workspace/InlineDecide.tsx: `DECIDE_TEXT.staleNext`.
- frontend/mock/fixtures/work/W-3602.steps.json, W-3602.next.send_for_review.json: send_for_review answer and next state.
- frontend/mock/fixtures/response/W-3401.recorded.json: T-3401 team_input recorded state (Security in, 3 OF 4).
- frontend/src/features/work-item/work-item.css: phone History link min 44x44.
- Tests: income-schedule, leadership-report, escalation, escalation-mock, response-mock, rfp-requirements, rfp-intake-mock; new e2e/history-link.spec.ts.

## Fixes
- F-52-1 | income "approved" waits for the re-read | 489e08de
- F-52-2 | two-reviewer stale test on the income line | 489e08de
- F-52-3 | next-step sentence and focus (UX-3-1, UX-3-3) | 98414b6d
- F-52-4 | W-3602 send-for-review fixture (QA-4-1) | c9e3e580
- F-52-5 | T-3401 team_input handler (QA-3-1) | ceae7b8c
- F-52-6 | History link 44px on phones | fa45bd82
- F-52-7 | rfp-intake-mock reset retry | 7fa112fb

## Acceptance criteria
1. [x] Income "approved" only after re-read: new test "a 200 whose re-read still serves the review reads result not confirmed" fails on the old code and passes now; the old test that asserted "is approved" was corrected; a decided re-read still says approved.
2. [x] Income two-reviewer: the task closes, the 409 keeps the stale sentence, the unsent note and no decide buttons (income-schedule.test.tsx).
3. [x] Leadership stale: leadership-report test checks the sentence "Read the current version above; nothing was recorded for you." and that document.activeElement is the notice.
4. [x] Escalation: escalation-mock test (send_for_review completes, re-read WAITING FOR REVIEW; fails without the fixtures) and a component test in escalation.test.tsx.
5. [x] Response mock: T-3401 team_input returns 200 with proof_count 1 and W-3401 serves Security as given; component test in rfp-requirements.test.tsx draws the completed state. Note: the recorded sidecar drops the Record control (schema validity).
6. [x] History link: e2e/history-link.spec.ts on W-2702 and W-3202: at 390 width and height >= 44; desktop height < 44. Passes.
7. [x] rfp-intake-mock: reset retried up to 3 times; 8 runs in a row passed (before the fix 2 of 5 failed).
8. [x] checks.sh exit 0 (3300 unit tests in 134 files, which include the F-33, 35, 37, 39, 42, 43, 45 tests); e2e passed for income-schedule, leadership-report, escalation, rfp-requirements, response and history-link (146 passed, ports 4941/4942).

## Validation
- delivery/checks.sh under the shared lock: exit 0. Lock released by rmdir (trap).
- npx playwright test (the six specs above): 146 passed.
- Demo running: app http://localhost:4935 (API_ORIGIN http://127.0.0.1:4934), mock on 4934.
- Fidelity: not run (no board changes beyond the History link size).
- Not changed: the RFP frame's History link (desktop only).
