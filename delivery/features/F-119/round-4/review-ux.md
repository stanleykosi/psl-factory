VERDICT: CHANGES
COMMIT: ca44c3775de717cd923cfa569ad85c68460bc85f
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- UX-3-1 is fixed: at 390 the Save bar sits at the screen foot (x 0, width 390, bottom 844) at every scroll position I tried, down to the page end, and a valid save toasts "Saved 15:48 WAT, version 1."
- The bar does not hide the last field or the 422 message: "Add a decision" ends 263px above the bar at the page end, and the form-level 422 ends 689px vs bar top 762 at scroll 0.
- New phone problem: a keyboard-focused control can sit under the fixed bar. The "Tunde Bello" checkbox is fully hidden behind it (hit test returns the bar), and "Lessons for next projects" is partly hidden. This breaks WCAG 2.4.11 Focus Not Obscured (AA), which the e2e axe tags include.
- New desktop regression at 1440: Save is visually above Decisions but comes after it in the DOM, so Tab goes Notes file, Add a decision, then Save. This breaks WCAG 2.4.3 Focus Order (Level A). Round 3 had DOM order matching the screen.
- Desktop placement and size are unchanged (Save 300x50 above the Decisions heading).

## Findings
- UX-4-1 | blocking | medium | frontend | Phone (390): the fixed Save bar covers focused controls. Expected: a control that receives keyboard focus is scrolled fully above the bar (WCAG 2.4.11). Actual: after Tab or focus() the "Tunde Bello" checkbox sits at y 824-844 with the bar at 735-844, and elementFromPoint at its centre returns the bar (fully obscured). "Lessons for next projects" (708-775) is partly under the bar. Browsers only scroll into view within the full viewport, so the bar hides the element. Path: `frontend/src/features/retrospective/retrospective.css` (phone `.retro__savebar` fixed bar, `.retro__page` padding); suggested fix: set `scroll-padding-bottom` on the form or page at phone width to the bar height plus a margin (about 130px), so focus scrolls above it, and re-check the Tab walk.
- UX-4-2 | blocking | medium | frontend | Desktop (1440): keyboard focus order does not follow the screen. Expected: Save (visually after the notes file and before Decisions, as on the board) is reached right after the notes file, as in round 3. Actual: DOM order is notes file, Decisions rows, "Add a decision", then Save, so Tab goes past the Decisions block (y 1009) and back up to Save (y 840). Caused by `.retro__decisions { order: 2 }` and `.retro__savebar { order: 1 }` on desktop, which change the screen order but not the DOM order. Path: `frontend/src/features/retrospective/RetroForm.tsx` (Save row placed after the Decisions block) and `retrospective.css` (desktop `order` rules). Suggested fix: keep Save before Decisions in the DOM at all widths, and keep the phone bar fixed so its screen position at the foot is unchanged; or keep the phone order and make the desktop order match the DOM. Either way, DOM order must match the desktop screen order.

## Verified
- UX-3-1 | verified | Save bar pinned at 390 on next dev 4992 + mock 4993 (Playwright, phone emulation): bar at y 734.5-844 (x 0, width 390) at scroll 0, 150, 300, 500, 800, 827 (page end). It never moves off the foot. "Add a decision" bottom 263 at end vs bar top 734. The 422 "Pick people who are on the project." bottom 689 vs bar top 762 at scroll 0, and above the bar after scrolling to the end. Valid save shows "Saved 15:48 WAT, version 1." after the re-read (screenshot checked).
- Desktop 1440 (not a finding, carried from round 3): Save at x 104, y 840, 300x50, above the Decisions heading (y 902), toast and layout unchanged.

## Notes
- Dev-only overlays are visible in the walk (the N dev indicator and the "Demo" button from the mock demo bar). They are not product UI and were not counted.
- Phone keyboard focus was walked with Tab from "What went well" through the form, the header and back. Only the two blocking items above were found; the header and skip link were not affected.
- Not checked: screen reader announcement order, the 2002 and 2004 cases, and the follow-up action area at 390 (no change in round 4).
- Servers: started by me, PIDs 1091 (mock on 4993), 1093 (next dev on 4992) and 1098 (its next-server child). All three were stopped by PID; ports 4992 and 4993 are now free. I did not touch 3000/3001 or any process from the main checkout. Disk: about 6.8 GB free after the walk.
- Scripts and screenshots are in the scratchpad `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/f3d2f47a-b311-4962-a74a-1c6348f1d696/scratchpad/ux4/`, none in the project.
