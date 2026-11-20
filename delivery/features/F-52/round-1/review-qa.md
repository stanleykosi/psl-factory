VERDICT: PASS
REVIEWER: qa
COMMIT: 523029ab661c7bc84edc76060a7e30aa9e46ef0e
AUTHORITY: delivery integrated QA

## Summary
- Drove the running demo (app 4935 to mock 4934, persona cookie, mock reset before each run) with Playwright at 1440 and 390: criteria 1 to 6 all behave as specified; API calls went through the app and returned 200 or the expected 409.
- Regression look at the ledger (W-4203) and forecast (W-4002) lines: claim and decision 200, "is approved" shown after the re-read, at both widths.
- Not exercised: a real backend (the mock stands in), the unit suite and checks.sh (left to the builder and technical review), criterion 7 repeat runs, F-35 notice surviving reload (out of scope).
- Scripts were kept in the scratchpad; worktree untouched, mock reset at the end.

## Findings
None.

## Verified
- AC1 income approved-after-re-read | verified | W-2702 as finance_lead: Approve schedule posts claim then decision (200 each); page reads "Schedule v1 is approved". With the work re-read forced to keep serving the pre-decision review (route intercept), page shows "Schedule v1: result not confirmed" at 1440 and 390; no "is approved" sentence (the only APPROVED/VERIFIED strings are the fact labels reading "Not yet").
- AC2 income two reviewers | verified | Tab A approves, tab B returns with note "Stale note QA": stale notice "changed while you were reading" stays, the unsent note is shown, 0 decide buttons in the workspace; same at 1440 and 390 (phone via the dialog).
- AC3 F-35 notice | verified | W-3202 as ceo, tab A approves and sends, tab B returns: 409, role=alert notice reads "This review changed while you were reading it, so nothing was recorded. / Read the current version above; nothing was recorded for you." and document.activeElement is that alert, at 1440 and 390. The unsent note shows beneath. See the UX-1-1 wording point (spec's exact sentence, product owner's call).
- AC4 W-3602 | verified | As pm: Escalate to the client (claim, decision 200), then Send for review: POST /api/v1/work/W-3602/steps 200, state WAITING FOR REVIEW, the button is gone, at both widths.
- AC5 T-3401 | verified | /work/W-3401/respond?task=T-3401 as pm: Security selected, estimate 12, "what they gave", proof file, attestation, received date, Record input: evidence 200, claim 200, POST /api/v1/tasks/T-3401/response 200 (not 501); page reads "Response recorded. Security's input, received on 11 Nov, recorded by Tunde Bello ... with 1 proof file." Both widths.
- AC6 History link | verified | getBoundingClientRect on W-2702 and W-3202: 44 x 44 at 390; 41.875 x 17 at 1440 (unchanged).
- AC8 other lines | verified | W-4203 and W-4002 approve flows as above.
