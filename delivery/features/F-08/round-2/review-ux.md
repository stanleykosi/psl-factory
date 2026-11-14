VERDICT: PASS
COMMIT: 568c0a407f78b39a3cb7cf33f0030cc3b0a6028c
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- I walked /overview as a Finance Lead on the shared build (localhost:3811, mock cookies for persona and the `status` variant) at 1440 and 390, with reduced motion, and through the 3D floor.
- Flat view matches SCR-06: mascot avatars load (no broken images), subtitles show, tag colours follow the status variant, and the order is totals, lines, exceptions with "See all exceptions" on the right, then legend. The phone shows the summary line and line cards, has no sideways scroll, and offers no 3D.
- 3D (concept 3, D-01): 40 station chips. Hover and keyboard focus both give the readout ("Pre-sale · Proposal · 0 items · needs a person"). Focus shows a visible 2px ring. Drag turns the board, and Reset view clears the readout. Flat removes the canvas. Reduced motion shows the hint and no 3D switch.
- One caveat: "See all exceptions" leads to the app's "This page doesn't exist" page on this branch, because /exceptions (F-06) is not merged. No finding is blocking, since D-18 defers the exceptions content. The link is only a dead end until F-06 lands.

## Findings
- UX-2-1 | non-blocking | low | product | "See all exceptions" (href /exceptions, no prefetch) opens a 404 page ("Go to My work" is offered, so it is not a trap) while F-06 is unmerged. Merge F-06 with or before F-08, or hide the link until then. Seen at frontend/src/features/overview/OverviewPage.tsx.

## Verified
- Round-1 UX review had no findings, so there is nothing to retest. The round-2 fixes in my lens (FID-1 flat fidelity, mascot avatars, 3D detection, 404 prefetch, concept-3 scene) were each walked and behave as the build report says. No 4xx occurs on load. The only 404s are from clicking the link.

## Notes
- Reloading while in 3D returns to Flat (the choice is not remembered). This is reasonable and keeps the heavy chunk opt-in.
- At 1440x900 the 640px 3D stage runs below the fold, so the last line (Payroll) is cut off until you scroll. This is by design (clamp 460-640).
- The phone "See all exceptions" link is 21px tall. It stands alone on its line, so the WCAG 2.5.8 spacing exception applies and axe is clean.
- The phone has no colour legend, which follows the board.
- Turning the 3D board is by drag only. Every station is still reachable and readable by keyboard.
- I did not walk 401 or 5xx. The component tests cover them.
