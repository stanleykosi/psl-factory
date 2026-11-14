VERDICT: PASS
COMMIT: cc3e185dd1ead6fc3079f9e15ef4f969b8b97fc8
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Walked pm and ceo at 1440 and 390 on the shared build with the contract mock. For ceo I opened all 8 lines, filled each form and checked the enabled primary button. `none` sees no Start control.
- UX-1-1 is fixed. Every enabled primary start button in the drawer and the phone sheet is rgb(200,64,28) (#C8401C, Start orange). It is 48px tall at 1440 and 50px at 390. Disabled it is grey, and Back/Cancel sit beside it at about half the width on desktop. The phone sheet has the full-width primary alone and the sheet top is 126px (70px below the phone bar).
- Invoice journey matches SCR-04: milestone is blocked until a project is chosen. The Harmattan 422 shows an alert callout (focus moves to it), the "1 thing to fix" subline, the red billing-contact box with the message, and a greyed button, at both widths. "What happens next" is one line with the red deciding role and the journey link.
- No dead ends found. The bottom sheet on phone is the approved D-02 behaviour.
- Not walked in the browser: the 409 and uncertain-result states (builder tests only), and a pixel comparison of every line board (I compared the invoice at both widths).

## Findings
None.

## Verified
- UX-1-1 | verified | enabled primary computed background rgb(200,64,28) on all 8 lines at 1440 and 390.
- UX-1-2 | verified | copy now reads "1 thing to fix" (eyebrow and callout).
- UX-1-3 | verified | after the 422 the primary is disabled until a field changes, as on the validation board.
- UX-1-4 | verified | the top-bar label reads "Start work" with a single space.
- UX-1-5 | verified | the phone sheet footer shows only the full-width primary, as on the mobile boards.
