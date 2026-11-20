VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 7fa112fbc1c004292685163cfe2e8a25ad525c54
AUTHORITY: delivery technical review

## Summary
- All 7 fixes are scoped to their line or the shared header; the diff touches no other line's logic.
- Income line reuses F-45's re-read rule through one helper; leadership-report notice change is keyed to line_key.
- Mock fixes are fixture-only; the generic handlers already did the work.
- Tests assert the new behaviour and the old assertion "is approved" was corrected, not weakened.

## Findings
None.

## Verified
- AC1 | verified | Workspace.tsx `waitsForReread` (ledger + income_schedules) now drives notMovedOn and onDecided; a 200 whose re-read still offers the decide task reads "Schedule v1: result not confirmed". Old code set the settled "is approved" text at once, so the new test fails on it. A decided re-read removes the task from decideTasks, so "is approved" still shows (second test). The one old assertion changed (income-schedule.test.tsx:341) was wrong by the spec, not weakened.
- AC2 | verified | Test closes the task (served = W-2702.approve) then 409s; asserts stale sentence, unsent note, no .ws-idecide and no decide buttons, one POST. It covers behaviour the old code already had, as the spec asked.
- AC3 | verified | staleNext keyed to REPORT_LINE only; sentence, tabIndex -1, focus effect. The test checks the text and document.activeElement is the role=alert node; the old code had neither. Other lines' stale notices are unchanged.
- AC4 | verified | W-3602.steps.json and W-3602.next.send_for_review.json; workspace.mjs picks `<id>.next.<step>`. Mock test and component test added; the sidecar filter regex and expected file list updated to match, no test removed.
- AC5 | verified | No handler change needed: response.mjs already reads `<work>.recorded` and returns 501 only when it is missing. The new W-3401.recorded.json is the fix. Mock test checks 200, proof_count 1 and Security given; the component test draws the state. Fixture is large but copies W-3401 with Security given.
- AC6 | verified | CSS only inside max-width 719.98px; desktop rule untouched. The e2e measures two lines at 390 and 1440 (builder reports it passing).
- AC7 | verified | The beforeEach retries a failed reset up to 3 times and rethrows; no assertion changed. Builder reports 8 clean runs.
- AC8 | verified | checks.md GATE: PASS on this head; no protected paths changed. Builder reports e2e for the five lines plus history-link passing.
