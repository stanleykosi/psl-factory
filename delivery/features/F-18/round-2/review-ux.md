VERDICT: PASS
COMMIT: 28c13dbcca5af9b6db6f276e2878c43a487a8958
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Re-walked the follow-up on W-2108 at 1440 and 390 (PM) and W-2113 (CEO persona, no send right), plus W-2102 and the outcome form hint. All six UX-1 findings are fixed.
- New edit behaviour works: emptying the box turns Send off and shows "The box is empty. Write the follow-up, or use the draft."; "Use the draft" returns to the drafted text with Send on; an edited send shows "Sent <date>" with focus on that line.
- No sideways scroll at either width. No dead ends.
- Fidelity scores (4 of 18 at 90) belong to the design reviewer, not counted here.

## Findings
- UX-2-1 | non-blocking | low | frontend | On W-2113 the card now shows both "You can't send this follow-up..." and the agent note "It goes only if you send it", which reads slightly contradictory for someone who cannot send. Hide the agent note when neither Send nor Edit is offered. `frontend/src/features/rfp/FollowupCard.tsx` (Checks showNote).

## Verified
- UX-1-1 | verified | after Send, document.activeElement is the .rfp-followup__status line (both widths).
- UX-1-2 | verified | "It goes only if you send it" gone after Sent (count 0).
- UX-1-3 | verified | "Use the draft" replaces Edit while editing; returns to the draft, no textarea, Send enabled.
- UX-1-4 | verified | W-2113 shows the reason line, no Send or Edit.
- UX-1-5 | verified | hint reads "Choose the result, when you learned it and who you are recording as, and add the proof, to record this."; Record stays disabled until complete.
- UX-1-6 | verified | W-2102 not-open page has an h1 ("Record team input") at both widths.
