VERDICT: CHANGES
COMMIT: 0517372f2319ecf958c8db0123b884264ab748f6
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Journey and content match the spec. I walked it in a browser on the mock (Next 4990, mock 4991), at 1280px and 390px. Six rows appear in order 01 to 06 with correct tags and "Updated" dates. Not-started rows are empty with no links. Closure shows "Closure waits on:". The static rule sentence shows on desktop only. 403 shows the no-access panel with no project name. There is no horizontal scroll at 390px.
- The row layout is broken. The state tag overlaps the "Updated" date text on every started row, at desktop and phone width. "ACTION NEEDED" is printed over "Updated 20 Nov", which is unreadable.
- The row content sits flush against the panel's left and right edges, so the row padding and column grid in `delivery.css` are not taking effect. The desktop board draws one aligned row, but the page wraps the tag and date onto a second line.
- Not walked: the error panel with "Try again" (a mock 500). The builder's component tests cover it. I did not run the live API journey, because this feature is read-only and the mock fixtures cover it.

## Findings
- UX-1-1 | blocking | high | frontend | The row layout breaks the approved SCR-43 board (desktop and mobile). Expected: one aligned row with number, title, reference, tag, date and Open, padded inside the panel (the `.delivery__row` grid, `frontend/src/features/projects/delivery.css:3`). Actual, at 1280px and 390px on P-0101: the tag renders at the left edge and overlaps the "Updated <date>" text. "ACTION NEEDED" over "Updated 20 Nov" is unreadable. The reference sits far right on its own line on desktop, and rows touch the panel border. The grid columns and padding seem not to apply, or the Tag's inline-flex width fights the `auto` track. Fix the layout so no cells overlap and rows are padded. Re-check at both widths. Screenshots (no sign-in involved): /private/tmp/claude-501/ux/d-P-0101.png and /private/tmp/claude-501/ux/m-P-0101.png.
- UX-1-2 | non-blocking | low | frontend | The closure reason joins the check title and its finding with only a space ("Handover to Support Support listed 2 gaps."). Add a separator such as an en dash, or put the finding on its own line, so the two read as separate parts (`frontend/src/features/projects/DeliveryTab.tsx`, the `delivery__finding` span).
- UX-1-3 | non-blocking | low | frontend | The 390px row stacks reference, tag and date on separate lines with large gaps (about 90px per row), so six rows take over 1100px. SCR-43-mobile puts reference and date under the title and groups them tightly. Tighten the row gap once UX-1-1 is fixed.

## Verified
None (round 1).
