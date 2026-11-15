VERDICT: PASS
COMMIT: 352893425c8d197b3de15ab04eac6c68d1d05782
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked team input (W-2101, W-2102), the outcome form for all four results (W-2103, W-2104, W-2110), the four recorded states (W-2105 to W-2108), the follow-up states (W-2113, W-2114) and not-open (W-2109) on the mock at 1440 and 390, as the PM and as a role with no sections. No dead ends, no sideways scroll, one h1 on every state except W-2102.
- The journeys match the spec and D-60: the frame shows on desktop only, phones show "← RFP" and the bar note, unbuilt tabs are plain text, and the keyboard goes straight to Team input past them.
- Send follow-up is only a button click. Edit then Send works, and the card shows "Sent <date>" with no buttons. The uncertain state shows the callout and "Check again" only.
- Empty, not-open and no-access states say something useful and offer a way back. The no-section role sees the shell's generic message and no RFP detail.
- Visual fidelity is under 90 on 14 of 18 boards (scores.txt). That belongs to the design reviewer's gate and is not counted here.

## Findings
- UX-1-1 | non-blocking | low | frontend | After "Send follow-up" succeeds, the button is removed and keyboard focus drops to the page body, so a keyboard or screen-reader user loses their place. Expected: focus moves to the "Sent" status line or the card. Actual: document.activeElement is body. `frontend/src/features/rfp/FollowupCard.tsx`.
- UX-1-2 | non-blocking | low | frontend | The line "It goes only if you send it" still shows after the follow-up has been sent, which reads as stale. Same file.
- UX-1-3 | non-blocking | low | frontend | The Edit view has Send but no Cancel or "Use the draft", so a person who opens Edit by mistake cannot return to the drafted text without reloading. Same file.
- UX-1-4 | non-blocking | low | frontend | On W-2113 (no send or edit right) the card says "It goes only if you send it" but shows no buttons and gives no reason. A short line saying who can send it would help. Same file.
- UX-1-5 | non-blocking | low | frontend | The outcome form's disabled hint names only some missing items (for example "Choose when you learned it and who you are recording as", without proof), so the hint can clear while Record stays off. `frontend/src/features/rfp/OutcomeForm.tsx`.
- UX-1-6 | non-blocking | low | frontend | The not-open response on W-2102 (team input) has no h1 on either width. The spec's one-h1 rule covers 403/404 only, so this is a note, not a spec break.

## Verified
