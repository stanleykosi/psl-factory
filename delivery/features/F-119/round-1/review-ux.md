VERDICT: PASS
COMMIT: 3b782e399d96666f02e5efbaf52ff86a8f590e0a
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Walked /projects/<case>/retrospective on the contract mock (next dev 4992, mock 4993) at 1440 and 390 as the PM persona: empty (2001), saved with checklist (2002), read-only (2003), no participants/proofs (2004), unknown case (2008), signed out.
- Matches SCR-33 desktop and mobile boards apart from the hidden parts the spec allows (Cites, Save draft, Tola panel, upload chip, API checklist words) and the added required fields.
- States say something useful: Save off with its reason shown, "Not recorded" for blanks, "This record is unavailable.", sign-in link with next=, saved result shown as a toast after the re-read (D-151).
- Accessibility basics hold: labelled fields, fieldset/legend for Who took part, real buttons, phone is one column with no sideways scroll.
- Not checked in the browser: stale 409, 503 unconfirmed save, and criterion 21 (live Django); the builder's e2e covers the first two on the mock, and I had no live login by rule.

## Findings
None.

## Notes
- A new empty decision row shows its red "Write the decision" error before anyone has typed; taste only.
- Breadcrumb ends "Closure" on a page titled Project retrospective, as on the board.
