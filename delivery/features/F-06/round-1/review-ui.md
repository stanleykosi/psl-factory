VERDICT: PASS
COMMIT: 808e022dd99ef05d39614d16acdfbe4fb0e44f55
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (visual consistency against SCR-10 boards and the design system, read-only)

## Summary
- `/exceptions` matches the SCR-10 desktop and phone boards: the h1 and sub-line, the four column headers, the kind tags in the board's amber and red tint pairs, "since" in mono, and the footer sentence.
- At 1440 the default list, the empty state and the "This list is for Leads" state all sit on the shared frame with no overflow (scrollWidth 1440). At 390 the rows become cards, and scrollWidth is 390 on the default list and the no-access view.
- Show more is 44px tall at 390 and 1440. The work item's "See all exceptions" link appears on W-1005 and is absent on W-1003.
- Tag and text colours resolve to the design tokens (`--waiting-tint`/`--waiting-ink`, `--signal-tint`/`--signal-ink`); no hard-coded colours in `exceptions.css`.
- No blocking visual findings. Items under Notes are taste only.

## Findings
None.

## Verified
None (round 1).

## Notes
- Board deviations that the spec records as approved, so not findings: the Search box, Filter button, "4 OPEN" total and per-row reference are not drawn (PMO-0-1). The phone "← Queue" back link is out of scope. The phone cards also show "since" and "Who acts", which the phone board omits.
- The "See all exceptions" link on the work item sits inside the amber Next-step callout, so it takes the callout's `--waiting-ink` colour and underline rather than the blue link colour used elsewhere. Contrast is about 7:1, so it passes; it is a taste question whether the link should stay blue.
- On phone the Show more control is a full-width text button with its label centred. It reads fine, but it is a different alignment from the left-aligned "Showing N" text on desktop.
- `exceptions.css` uses literal px font sizes (12/13/14px) and 14px card padding. There are no type-scale tokens in `tokens.css`, and `psl-bundle.css` uses the same px values, so this is not a token violation.
- Not checked visually by me: the 503/network error card with Try again, the Show more failure warning, the focus outline on tabbing, and the 20-row Show more expansion at phone width. The build reports these as covered by unit and e2e tests (mock results).
- Browser checks were run against the shared production build on localhost:3611 with the mock on 127.0.0.1:3612. Screenshots were taken as evidence and deleted after this file was written. The servers were left running.
