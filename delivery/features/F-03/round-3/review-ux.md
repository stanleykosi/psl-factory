VERDICT: PASS
COMMIT: 3f684410f771cf53c1103d40aaa7977b09c084b3
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked W-1003 and W-1005 at 390, 760, 1079, 1080 and 1440 on a scratch copy of frontend/ at this head (app 3211, mock 3212, both stopped after).
- Below 1080px (390, 760, 1079) the 7 stations are a vertical list with status on the right, the same left edge, nothing clipped, no scroll in the track and no sideways page scroll. Only the current row is tinted.
- From 1080px (1080 and 1440) the stations are one row, all 7 inside the track, with no scroll anywhere.
- The effect-uncertain station is solid amber (rgb 138,90,0) with white text from 1080px, and the pale amber row (rgb 255,241,214, text 110,71,0) below it. This matches the 14 Nov design-owner decision. The agent station on W-1003 stays blue at all widths.
- The decision, the next-step callout and the read-only agent card are unchanged and read correctly at 760 and 1080.

## Findings
None.

## Verified
- UI-2-1 (stations clipped between 720 and 1080px; UI lens, checked here too) | verified | at 760 and 1079 the list is stacked with page scrollWidth equal to the viewport, and the row appears only at 1080.
- UI-2 note (solid amber effect-uncertain station) | verified | computed colours measured at 1080 and 1440 (solid) and 390, 760 and 1079 (pale).

## Notes
- spec.md Screen states item 5 and AC 4 now say 1080px, but spec.md line 202 (AC 4) still says only "At 390px"; the builder asked the coordinator to widen it.
