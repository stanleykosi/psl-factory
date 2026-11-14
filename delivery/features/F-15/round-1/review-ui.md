VERDICT: CHANGES
COMMIT: 07d078ef95aed97f36a412c6214ee8bc778ab9d0
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (visual consistency against concept 3 of design/concepts/alerts-bell-concepts.html as decided in D-53/D-54, SCR-15 row styling, CMP-01 bars and tokens, at desktop and phone width)

## Summary
- At 1440 and 390 the drawer and sheet match concept 3. Order, wording, group headers, filled and outlined Open, footer, tabs, grab bar and sizes all meet the spec's contract (measured on the shared build at :4811 with `needs-you`). The only differences are the ones the spec accepts: the 56px bar, 40px mascot avatars, a sans meta line and the SCR-15 unread tint.
- Blocking: on phones narrower than about 366px, the bell's 44px box overlaps the PSL FACTORY wordmark. At 320px the bell and badge sit on top of "FACTORY". Before F-15 this bar fitted at 320 (UI-1-1).
- Blocking: the header tightening at 720–1079px squeezes the nav links to 2px padding and puts the bell flush against the name. That tightening is only needed near 720px, but it is applied all the way to 1079, where about 360px of the bar stays empty (UI-1-2).
- 1080–1440 desktop bar: nothing is cut. Order is links, bell, chip touching the bell, name and role, then Start work last with the 28px gutter kept. The 1080–1279 link padding of 10px looks fine.
- The My work header has not regressed. Fidelity on SCR-01-desktop at 1440 passes with the F-02 exceptions (coverage 100, visual 90.9; F-02 had 92.2). SCR-01-mobile at 390 scores coverage 100 and visual 81.8, the same as F-02's accepted 81.1 (D-20). The only new items are the bell (extra) and the name placed before Start work, which D-54 approved.

## Findings
- UI-1-1 | blocking | high | frontend | The phone bar overlaps below about 366px. The bell sits in `.sw-phoneslot` beside "+ Start", but the wordmark keeps its place, so the two collide on narrow phones. Measured on `/my-work` with the wordmark ending at x=216: at 375 the bell box starts at 225 (9px gap), at 360 it starts at 210 (6px overlap), and at 320 it starts at 170 (46px overlap). At 320 the bell icon and the red "4" badge are drawn over "FACTORY". Before F-15, the same bar at 320 had the wordmark at 60–216 and Start at 222, so it fitted. 360 is a common Android width, and 320 is the WCAG reflow width. Expected: no overlap down to 320. Options are to let the wordmark shrink or ellipsize, or to tighten the bar's side padding, Menu and "+ Start" spacing below about 370px, using tokens. Paths: `frontend/src/styles/shell.css` section (g), the `.psl-phonebar.shell-phonebar--bell` and `.sw-phonebar.shell-phonebar--bell` padding rules. See `round-1/visual-review/phone-bar-narrow.png` (before and after at 390, 375, 360 and 320).
- UI-1-2 | blocking | medium | frontend | The 720–1079px bar is crowded across its whole range, but the tightening is only needed near 720.
  - The `@media (min-width: 720px) and (max-width: 1079.98px)` block in `shell.css` (g) cuts the link padding to 2px, where it was 4px before F-15. Link labels are now about 4px apart, the same as the space inside "My work", so "My work Projects Overview Assistant Setup" reads as one line of text.
  - The same block puts negative margins on both sides of a 32px bell. The bell box ends exactly where "Ada Okafor" starts (509/509 at 720), and the badge almost touches the "A".
  - At 900 and 1079 the same squeeze applies, yet the links end at x=471 and the bell starts at 657 (900) or 836 (1079). That is 190–365px of free bar.
  - Expected: links keep their earlier 4px padding, and there is a visible gap of at least `--space-1` between the bell and the name, wherever that fits. By the numbers, the earlier spacing needs about 36px more than 720 gives, so it fits from about 760px. Limit the tight variant to a narrow band at the bottom (for example 720–~760px). Within that band, keep at least a small gap between the bell and the name, for example by taking it from link padding rather than from the bell.
  - Paths: `frontend/src/styles/shell.css` (g), the block commented "720px up to bp-desktop". See `round-1/visual-review/bars-720-1440.png`, which compares the build before F-15 (`fix-e2e` build on :4901) with this build at 720, 1079, 1080 and 1440.

## Verified
None (round 1).

## Notes
- Scrim colour: the drawer uses `rgba(20, 24, 26, 0.4)`, the concept value the spec fixes. The design system already has `--scrim` (`rgba(31,36,39,0.45)`) and a `.psl-scrim` class in `psl-bundle.css`. The spec makes this compliant, but using the token would keep every overlay in the product the same. Worth settling with the design engineer.
- In the drawer, unread rows use the SCR-15 signal tint (accepted in the spec, Conflicts 3). As a result the three Needs you rows share a colour family with their red-tint group header, and the unread For your information row (UAT) is tinted the same red. Concept 3 used the blue action tint, which kept "needs you" (red) and "unread" (blue) apart. This is a matter of taste and not blocking.
- The badge, chip and bell sizes in `shell.css` (g) are literal px values (17px, 9px radius, 11px and 12px text, 36px and 32px bell). They copy concept 3 exactly, and no token exists for these sizes. Colours all come from tokens. White text on `--signal` (#C8401C) is about 4.9:1, so it passes.
- Screens checked at 1440×900 (closed and open), 1280, 1279, 1080 (on `/my-work` and `/notifications`), 1079, 900, 720 (on `/my-work` and `/projects`), and 390, 375, 360 and 320. There is no horizontal scroll at any of these widths.
- Fidelity runs used `software-factory/packages/design/fidelity/fidelity.mjs` with `--exceptions delivery/features/F-02/fidelity-exceptions.json` and the cookie `psl_mock_worklist=board`, against `http://localhost:4811/my-work`. Results: SCR-01-desktop at 1440 exited 0 (pass). SCR-01-mobile at 390 exited 1 on visual 81.8 only, the same cause and level as F-02's accepted 81.1. Reports were kept in the scratchpad, not committed.
- Images: `round-1/visual-review/sbs-1440-open.png` (concept 3 desktop mock-up next to the build at 1440), `sbs-390.png` (concept phone mock-up next to the build with the sheet open and closed), `bars-720-1440.png` and `phone-bar-narrow.png`.
- No server was started or stopped. All captures used the shared build on :4811 and :4812, plus the read-only `fix-e2e` build on :4901 as the before-F-15 reference.
