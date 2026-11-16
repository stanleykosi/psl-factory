VERDICT: PASS
COMMIT: 0f94b4b21e40889bb0300b3cf6891bab76829677
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Reviewed from the builder's round-2 fidelity screenshots (mobile home, mobile draft-started) and build.md; no servers started (disk).
- Phone home: "← Home" and "5 earlier" in the bar, agent chips, hello and ability, composer docked at the bottom. Clear path, nothing overlaps.
- Phone after start: "← Assistant" on one line, title ellipsised, "Started INV-0415. Open the work item" plus a full-width "Open INV-0415" footer; no start button, no approve/send/pay.
- Not re-walked live: keyboard order and the second-tab 409 (builder's e2e passes; round 1 walk was fine).

## Findings
- UX-2-1 | non-blocking | phone home bar | "5 earlier" reads as plain monospace text beside the bell; add a visible button affordance (border or underline) so it is discoverable as tappable. | frontend

## Verified
- UX-1-1 | verified | phone bar screenshot: back label on one line, title ellipsised with a gap, no collision.
- UX-1-2 | verified | composer is in flow with scroll padding (code and builder e2e: focused draft button above composer); draft-started phone shows the full card and footer unobstructed.
- UX-1-3 | verified | code: 409 now triggers a thread re-read (onConflict); builder's second-tab e2e passes. Not live-tested.
