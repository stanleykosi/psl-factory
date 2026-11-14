VERDICT: CHANGES
COMMIT: 02db3e841a47c4d83ed907c5bba467ef3a05a164
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (round 1, design-fidelity gate)

## Summary
- The design-fidelity gate passes on both boards against the shared build on :4011. Desktop SCR-36 at 1440 has 100% coverage once the exceptions are applied, with a visual score of 98. Phone SCR-36 at 390, using the `board-phone` data, has 100% coverage and a visual score of 97.8.
- On both boards the page matches the drawing element for element: the strip colours, the table, Chidi's note and avatar, the tags and the pinned phone action. The CSS uses token variables only, with no hard-coded colours, and no shared CSS file was edited.
- Unknown money never shows as 0. The cash cell reads "₦4.7M + Unknown" by default, "Unknown" in the `unknown` and `contract` cases and "₦4.7M" (white cell) in the `known` case. The full value is exposed through `aria-describedby`. The restricted Payroll row shows "HR only" with no link at both widths.
- One blocking problem: on phones, the empty state's white panel stretches to fill the whole screen, 690px tall for a single sentence.
- Nothing scrolls sideways at 390 or 1440 in any state I captured.

## Findings
- UI-1-1 | blocking | low | frontend | On a phone with no tasks (`psl_mock_month_end=empty`, 390 x 844), the "No month-end tasks you can see for October 2026." panel is a 690px-tall white box running from under the summary line to the bottom of the screen. Expected: a panel sized to its text, as on desktop and on the other empty states in the app. Cause: on phones `.monthend-row` is `display: contents`, so `.monthend-empty` becomes a direct child of the `.monthend` column, which has a full-screen `min-height`. The empty panel's desktop sizing `flex: 999 1 600px` then makes it grow to fill that height (computed height 690.25px, flex `999 1 600px`). Fix: inside the phone media query give `.monthend-empty` `flex: none` (or restrict the 999 rule to the desktop row). `frontend/src/features/finance/month-end/month-end.css:23`; see round-1/fidelity-review/states/empty-390.png.

## Verified
- None (round 1).

## Notes
- **How the gate was run.** The prompt named `design/canvas/project/SCR-36-*.dc.html`, but the SCR-36 boards are only in `design/canvas/finance/project/` (as the spec says), so the gate ran on those. I used the worktree's `delivery/features/F-10/fidelity-exceptions.json` (Start work and More ways to start). The tool's `--cookies` sets cookies for the page's path, so I passed it a small Playwright wrapper that sets them on path `/` instead. This time the phone run did get the six `board-phone` cards (97.8, compared with the builder's 94.9 on the default seven). Reports: `round-1/fidelity-review/SCR-36-desktop-1440/` and `…/SCR-36-mobile-390/`.
- **Desktop.** 41 of 43 elements matched. The 2 missing are the frame's Start work items, which are covered by exceptions. The only move the tool reports is "Import the missing statement", and that is a reading-order note only: the box is 1px lower. The board's Chidi image is a `/_blob/` with no map entry, so it shows as broken on the board side, and the page uses `/agents/chidi.png` (D-14).
- **Phone.** 23 of 23 elements matched. "← Finance" sits top right, level with the h1, instead of in the phone bar. D-19, with D-08 and D-13, approves this placement for now. The tool's two extras (Menu and PSL FACTORY) belong to the frame's phone bar.
- **States screenshotted at 1440 and 390** (saved in `round-1/fidelity-review/states/`): default, board-phone, unknown, known, empty, contract and pm (no access).
  - Contract: Unknown in all four cells, STATE_TAGS words, six Open links, and an empty last cell on the Payroll row.
  - Default phone: 7 cards, including "Payroll · WAITING ON HR · Restricted · HR's work" with no link.
  - Restricted row: 0 `<a>` elements in the Payroll row and card in every state.
- **Contrast.** The ink/tint pairs all come from tokens, and each one is readable. In-progress #626B6F on white is about 5.3:1, waiting ink #6E4700 on #FFF1D6 is above 7:1, and white on #22764A is about 5.6:1.
- **Taste, not blocking.**
  - On the v4-only (`contract`) body, the DONE cell stays solid green while it reads "Unknown". The spec requires this (DONE always green), but a green "Unknown" reads as good news. The design engineer may want a neutral tint when the count is unknown.
  - The NO ACCESS tag on the no-access card stretches to the card's full width instead of sizing to its text.
