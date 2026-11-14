VERDICT: PASS
COMMIT: ea088f9b0606c0e8e5fdfa1d047cd46619a96d13
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design system and approved SCR-06 artboards)

## Summary
- The /overview screen matches SCR-06 in layout, type, surfaces and tokens at 1440 and 390 (and 768). Flat, 3D, empty, all-zero, reduced-motion and phone states all render with nothing overflowing (scrollWidth equals innerWidth in each).
- The totals (18 / 5 / 3 / 28) and the eight lines with their station squares match the fixture, and the page does not sum or derive any figure.
- Tag colours and the line avatars/subtitles differ from the approved artboard. The spec records this (PMO-0-4, spec.md lines 84, 91, 222) and flags it for product acceptance, so it is listed as a non-blocking product item, not a block.
- The 3D floor shows the same figures as the flat view. Its token cubes overlap each other and the count sprites in places; that is a low-severity polish item.
- No hard-coded colours in the overview or floor CSS or TSX; the 3D scene reads tokens from CSS custom properties at mount.

## Findings
- UI-1-1 | non-blocking | low | frontend | 3D floor: token cubes collide with each other and with the count sprite at busy stations (visible at 1440 on Invoices, Pre-sale and Planning). Expected: tokens sit clear of the sprite and the neighbouring block. Actual: the two-row token grid (`frontend/src/features/floor/scene.ts:140-143`) runs into the sprite placed at `scene.ts:135` and the adjacent block. The sprite text stays legible at 2x.
- UI-1-2 | non-blocking | medium | product | Tag tones and line identity differ from the approved SCR-06 artboard. The artboard shows ON TRACK in green, WAITING in amber, STOPPED and UNCERTAIN in red, and an avatar and subtitle per line (e.g. "RFP · commercial"). The build draws every tag neutral (ON TRACK, the 2 PROBLEMS in the zero variant) or in the signal tint (WAITING, STOPPED, UNCERTAIN, 2 PROBLEMS), and omits avatars and subtitles, because E-OVERVIEW has no fields for them. This follows the recorded PMO-0-4 decision (spec.md lines 84, 91; readiness.md line 25), which is flagged for product acceptance. Expected: product confirms or supplies the tone rule before merge. Actual: as described, in `frontend/src/features/overview/OverviewPage.tsx` (`LineRows`, the `psl-tag` class choice). If product does not accept the recorded decision, this becomes blocking.

## Verified
None (round 1).

## Notes
- Screens checked (shared build on localhost:3811, mock on 127.0.0.1:3812; viewed only, not stopped): flat and 3D at 1440 (3D canvas drawn, count sprites legible at 2x); flat at 390 (2 x 2 totals, stacked rows, names and tags visible, no sideways scroll); flat at 768; cookie variants `empty`, `zero` and `changed`; `prefers-reduced-motion` at 1440 (hint shown, no View switch). The 390 3D option and the no-WebGL state were not captured; the 3D state at 390 is absent by design (spec state 8).
- Zero variant: every station is empty, but the notes still read "1 WAITING", "1 STOPPED" and similar. That is verbatim fixture content, so it is consistent with the rule, but it looks odd in the all-zero case. Fixture authors may want to align the sample notes.
- Totals and station squares are shown as returned; the station counts sum to 21 while in_progress is 18. This is by design (spec: never sum), so product should not read the squares as a breakdown of the totals.
- The 3D floor's count sprites are about 10 px at 1x. Readable, but small; the flat list (in `.overview__sr`) carries the figures for screen readers, and the flat view carries them visually.
- The 768 px shell header (nav items crowding the logo) is part of the shell, not F-08. Not in this round's lane; noted for information only.
- The approved board shows a "Start work" button and an exceptions table on the page. The spec defers the exceptions preview to F-06 follow-up (a) and the Start work button is shell, so neither is a finding here.
- Keyboard focus rings, axe and the e2e suite were not re-run by this reviewer; the builder's checks.md records them (93 e2e passed, zero axe violations at 1440 and 390).
