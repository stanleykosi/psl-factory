VERDICT: PASS
COMMIT: 2075d4aa29aa4d09b9adc118b4955ad7e5c29af3
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Read-only review from the round-3 fidelity screenshots, build.md and assistant.css; no servers.
- "5 earlier" in the phone home bar is now underlined and reads as tappable.
- The "Open INV-0415" button is docked at the bottom like the composer (sticky, own surface, top rule). It is sticky in flow, so at the end of scroll it sits below the draft card and hides nothing.

## Findings
None.

## Verified
- UX-2-1 | verified | mobile home screenshot: "5 earlier" underlined next to the bell.
- Docked Open button | verified | CSS `.as__open` sticky bottom, in flow, with scroll-padding-bottom on phones; the draft-started capture is a full-page image where the sticky bar appears mid-page (capture artefact, same as the composer); builder's e2e asserts it sits at the viewport bottom. Not live-tested.
