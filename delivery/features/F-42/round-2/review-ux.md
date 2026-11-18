VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 8779c5f30c05ed760fc1cbfe3a2dddf790daca1e
AUTHORITY: delivery UX review

## Summary
- Both blocking UX findings are fixed and stay inside this line. The F-30 rule in `WorkItemOverview.tsx` that hides the exceptions button now also excludes `fixed_assets`, the app shell is unchanged, and other lines still draw the button. The waiting wording after "Approve register" now says what is missing.
- Non-blocking UX-1-3 to UX-1-6 are carried forward for the owners named in round-2/build.md. UX-1-4 is partly fixed by TECH-1-1.
- Vitest at 8779c5f30c05ed760fc1cbfe3a2dddf790daca1e, run one file at a time: asset-schedule 37, asset-schedule-mock 11, income-schedule 44, income-schedule-mock 8, work-item 46, work-item-board 81, workspace 37, workspace-step 47, workspace-mock 7, all passed. A first combined run under load average 30 to 150 timed out in work-item-board and the *-mock files failed to start; each of those passed when run alone, and none of them is touched by this diff.

## Findings
None.

## Verified
- UX-1-1 | verified | The new condition is `line_key !== 'issue_followup' && line_key !== 'fixed_assets'`, so it applies only to this line. The test "UX-1-1: no hold or uncertain state…" checks that W-3907, W-3908, W-3909 and W-3911.approve have no "See all exceptions" link, and that W-2706 (F-33) still has one. work-item, work-item-board and workspace tests pass, so other pages keep the shell button where they had it.
- UX-1-2 | verified | In W-3902.approve.json, `next_step` and `workspace.next` now read "Waiting for someone to explain the 3 unclear in-service dates and attach the proof. The date review starts after that.", and station 3 is `waiting` instead of `current_person`. The test checks the new text and that "dates are explained" is absent. There is still no panel and no control on this state. Who explains the dates stays with the design engineer (G-55-1).
