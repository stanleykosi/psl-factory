VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: c4bd4510133c0c807bf0ae1d2068f8b7a14b6ff8
AUTHORITY: delivery UI review

## Summary
- The 42-50 visual scores are mostly a capture/scoring limit (F-49 tall-sheet case): the built page is 2271/2684 px tall (full My work list under the scrim) against a 900/844 px board. Side-by-side shows the drawer/sheet itself is close to the board.
- Real, nameable differences remain: As of / Months stacked instead of side by side, Management preselected on board vs nothing preselected, "Optional" helper line vs "(optional)" in label, phone drawn as a sheet over My work instead of a page.
- Two exceptions (Optional, As of/Months label) cover drawable elements; the Optional exception hides a board element. Exceptions are builder proposals, not approved by the design engineer.
- Fidelity tool was not re-run (as instructed); judged from the four side-by-side images and a live check (1440 drawer opens for Finance, 5 lines listed, fixed assets and forecast on the phone menu).

## Findings
- UI-1-1 | blocking | medium | frontend | As of and Months sit side by side on both forecast boards (mobile board clearly) but stack in the build (forecast 390 side-by-side; desktop per build.md). Expected the board's two-column row; shared field layout in the start-work LineForm is not changed. Fix, or have the design engineer record it in fidelity-exceptions.json as a layout exception.
- UI-1-2 | blocking | medium | frontend | "Optional" is drawn by the boards as a separate muted line under Prior schedule and Accounting note (desktop and phone); the build puts "(optional)" in the label and draws no line. Exception 10 hides a missing drawable element and changes the label text ("Prior schedule" vs "Prior schedule (optional)"). Either draw the helper line or get an explicit design-engineer approval of the F-05 convention; the exception is not yet honest as a copy-only difference.
- UI-1-3 | blocking | low | product | Audience: board shows Management selected, build selects nothing. This is D-130 (accepted conflict); the segmented control otherwise matches (3 equal segments, black fill selected). Not a build fault; list it as an approved difference so the score gap is explained. No action by frontend.
- UI-1-4 | blocking | medium | frontend | Phone: board is a full page (back bar "← My work", "START" eyebrow, "+ Start" button, no step line, no close x); the build is F-05's bottom sheet with "Step 2 of 2 · change line", a drag handle and a close x, and the sheet is taller than the board (footer at ~800 px vs ~760 px on the board scaled). Exceptions 11 and 12 are honest about the missing bar items (frame), but the sheet-vs-page choice needs design-engineer approval; the "Step 2 of 2" line is an extra element with no board counterpart and is unlisted.
- UI-1-5 | blocking | low | frontend | Extra elements not on boards and not listed: the remove "x" on the proof card (needed behaviour, should be recorded as an approved extra), the calendar icon in As of (native date input), and the top-bar items Overview/Setup/Unassigned tab (frame, same family as exception 2/3). Record them in fidelity-exceptions.json or confirm they are tool-ignored extras.
- UI-1-6 | non-blocking | low | frontend | Exceptions 5-8 (typed dates, Months "6", chosen scenario and prior schedule text) hide data values only in the sense that the tool reads input values as no text; in the live captures all four values are visible ("31 Oct 2026", "6", "Base case · v4", "PPE-0005 · September"), so they are honest. Exceptions 4 and 6 (As of, Months labels) are also honest: both labels are visible above their inputs. "Tunde Bello · PMO" (exception 1) is honest per D-130 conflict 2.

## Verified
- Scores: real vs limit. The page capture is 2.5x to 3x the board's height, so the tool compares a mostly-list page to a mostly-empty grey board; that explains most of the drop, as in F-49. It does not explain UI-1-1, UI-1-2 or the phone sheet differences.
- Desktop drawer: width, header (START WORK eyebrow, title, "Line chosen from the Start work menu · change line"), Proof card with dashed border, selects, Cancel/Start schedule footer all match the board in side-by-side (type, spacing, colours, orange primary button, same token look as neighbouring drawers).
- Phone fixed assets: Proof card, selects, orange button match; no overflow seen at 390.
- Live: Finance persona sees 5 lines including "Fixed asset schedule" and "Cash forecast" on the phone menu; the 1440 drawer opens with the shared look.
- Not verified: a fresh pixel diff; uploaded and failed states on the live build (covered by the builder's axe/e2e only).
