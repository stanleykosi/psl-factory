VERDICT: PASS
COMMIT: cfc3c462382095787d1edf2bbda089f7140d28cc
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer (lighter panel, D-180)

## Summary
- Retested UX-1-1 to UX-1-3 at 1440 and 390 on head cfc3c462 against the shared dev server (Next 4970, mock 4971), default finance lead, project P-0101. All three are fixed.
- Re-walked both tabs for regressions in what round 2 touched: Money figures stay on one line (for example "Paid NGN 2,000,000.00 ·" then "Owed NGN 500,000.00"), the idle side panel reads "Where a figure comes from / Choose an amount to see where it comes from.", and Unknown is the same bold brown text on both tabs.
- Unknown money is still Unknown: no zero-money pattern on either tab, no totals, Go-live amount reads Unknown with its reason, and null Paid/Owed read Unknown. No horizontal scroll at either width; the page made no non-GET requests.
- Fresh screenshots are in /private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/ux2/ (money-1440.png, money-390.png, panel-1440.png, sheet-390.png, after-escape-390.png, ms-1440.png, ms-390.png).

## Findings
None.

## Verified
- UX-1-1 | verified | At 390 on /projects/P-0101/money?figure=kickoff the sheet is a dialog with focus on the sheet; with focus blurred, pressing Escape removes the dialog and the URL returns to /projects/P-0101/money (after-escape-390.png).
- UX-1-2 | verified | Money has h2 "Billing by contract stage" and the desktop table is captioned with the same text; Milestones has h2 "Contract milestones" and h2 "Recorded completions" with the table captioned "Milestones". Same headings at 390 (the phone cards have no table, so no caption there, which is fine).
- UX-1-3 | verified | Proof buttons report aria-expanded="false", flip to "true" on press and return to "false" on a second press, at both 1440 and 390.
