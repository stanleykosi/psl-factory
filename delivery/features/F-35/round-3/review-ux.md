VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: eefaf6c5e7f37793673e3d57fce297a55358fad1
AUTHORITY: delivery UX review

## Summary
- Walked the two-reviewer race live on W-3202 at 1440 and 390 (A = ceo approves, B = pm returns with "Stale tab note"). B sees the sent state, an amber alert "This review changed while you were reading it, so nothing was recorded." and "Your note wasn't sent: "Stale tab note"". No decide controls remain, so no dead end and no false "returned" claim. Mock reset after.
- QA-2-1 is fixed. No regressions seen.

## Findings
- UX-3-1 | non-blocking | low | frontend | The notice does not say what happened instead or what to do. It never says the report was already approved and sent, and the Next card talks only about delivery. A line such as "Another reviewer already approved it. Copy your note and tell them if it still matters." would make the next step obvious.
- UX-3-2 | non-blocking | low | frontend | The notice is lasting only until reload. After reload it and the note are gone (checked). This is acceptable for a page-state notice, but the note is not copyable-by-design beyond that. Fold into UX-3-1 if the copy is revisited.
- UX-3-3 | non-blocking | low | frontend | Focus stays on body after the dialog closes at 390. The alert role announces the notice, but moving focus to it would help keyboard users.

## Verified
- QA-2-1 | verified | Live at both widths; the stale sentence and note stay visible, one decision write (also asserted by the new e2e).
- W-3209 approve | verified | "SENT · DELIVERY NOT CONFIRMED", no Approve button, no received claim, both widths.
- W-3207 hold | verified | "NOT SET", no Approve button, both widths.
- W-3210 | verified | "3 OF 5", still decidable, both widths.
- W-3203 | verified | partial delivery, no Approve button and no received claim; send flow (W-3202 approve) works.
