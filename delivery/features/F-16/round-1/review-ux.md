VERDICT: PASS
COMMIT: 713e628b94ce0babdd045dbb45f17ac85cafb507
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Walked W-1901 (decide), W-1902 (stale), W-1903 (not yours) and W-1904 (own) on the shared build at 1440 and 390 as finance_lead, plus W-1903 as ceo and pm. Approve, Return (with and without a note) and Reject were all driven through the real page.
- Journeys match SCR-03 and spec.md: trail, h1 (40px / 26px, one h1), phone back link ("Decisions" on decide, stale and done; "Queue" on not-yours, own, not-open, error, 401 and no-access), done banner, Next decision link, stale table (desktop) and stacked cards (phone), no sideways scroll at either width.
- D-55 holds: the not-yours comment box is disabled, labelled, tied by aria-describedby to "Comments aren't available yet.", skipped by Tab, and a click sent no write. Persona (finance_lead, ceo, pm) made no difference, as specified.
- Keyboard: Tab order is Decisions, See his steps, Note, Approve, Return, Reject, each with a visible ring; the phone Note is reachable above the pinned bar and Approve is 54px.
- Two small accessibility and layout points below; none blocks.

## Findings
- UX-1-1 | non-blocking | medium | frontend | After Approve (Enter on the focused button) focus falls to `BODY` and the done view has no live region (`role=status`/`aria-live` absent; the stale view does have `role=alert`). A keyboard or screen-reader user is not told the approval was recorded and loses their place. Expected: move focus to the done heading or announce the banner. Not checked against the base build, so it may predate F-16. `frontend/src/features/decide/DecideStates.tsx` (DoneView).
- UX-1-2 | non-blocking | low | frontend | The 5xx error card and the 401 signed-out view render no `h1` (the title is absent), unlike no-access, stale and done, which have one. Criterion 6 only names those three, so this is a gap in the same intent. `DecideView.tsx` error branch.
- UX-1-3 | non-blocking | low | frontend | At 390 the not-yours board pins a permanently disabled "Add comment" bar to the bottom of a read-only page, so it reads as a primary action that never works and takes a strip of screen. It follows the board and the visible explanation sits above it; consider an inline button on the phone when the box is disabled.

## Notes
- One run at 390 showed the stale view ("Review version 2") after Approve on W-1901. Three repeats, with and without Tab and a failed Return first, all gave the done view with one claim and one decision at revision 2. I take it as another reviewer resetting or deciding on the shared mock at the same moment, not a defect.
- The mock answers any unknown id (W-9999) with the item, so I could not see a real 404. 403, 401 and 500 were simulated by intercepting the item request; each showed the expected view with "← Queue" and no id or title (403).
- persona `none` gives the frame's "No sections are open to your role yet" on every page, which is the frame's behaviour, not this page's.
- Fidelity scores are the UI reviewer's lens; not judged here.
