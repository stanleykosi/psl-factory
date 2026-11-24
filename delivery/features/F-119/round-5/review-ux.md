VERDICT: CHANGES
COMMIT: 53c24b19059ece9c6d4e8a9bf3eb086a7cba1405
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- UX-4-2 is fixed: at 1440, Tab from the notes file lands on Save, then on "Add a decision". Save is in the DOM before Decisions.
- UX-4-1 is only partly fixed: at 390 the Lessons field is still partly under the fixed Save bar when focused (Tab or focus()), and the hit test at its centre returns the bar.
- The "Tunde Bello" and "Ada Obi" checkboxes, the notes file and "Add a decision" are all clear of the bar.
- A valid save still toasts "Saved 16:39 WAT, version 1." and the 422 still shows "Pick people who are on the project."

## Findings
- UX-5-1 | blocking | low | frontend | Phone (390): the focused "Lessons for next projects" field is still under the fixed Save bar. Expected: a focused control is scrolled fully clear of the bar (WCAG 2.4.11, AA, in the e2e axe tags). Actual: Tab from "What didn't" (and focus()) leaves scrollY 0 with the field at y 708-775 and the bar top at 735; elementFromPoint at the field centre (741) returns the bar. The computed `scroll-padding-bottom` is 110px on html, so the rule applies, but Chrome does not scroll because the field is already inside the viewport. It reproduces with and without touch emulation and on projects 2001 and 5001. The builder's e2e check passes, so it does not catch this state. Path: `frontend/src/features/retrospective/retrospective.css` (phone `.retro__savebar`, `html:has(.retro__savebar)` rule). Suggested fix: give the form or page enough bottom space and scroll the focused control with `scrollIntoView({block:'nearest'})` on focus at phone width. Or add a `focusin` handler that scrolls the target above the bar's top. Re-check at scroll 0 on a fresh load, where the Lessons field starts partly hidden.

## Verified
- UX-4-2 | verified | 1440 on next dev 4992 and mock 4993: Tab from the notes file goes to "Save retrospective", then "Add a decision". Only one Save is rendered.
- UX-4-1 (part) | verified for the checkboxes | 390: after Tab, "Tunde Bello" sits at y 357-377 (page scrolled 478) and "Ada Obi" at 405-425, "Choose the notes file" at 479-523 and "Add a decision" at 568-612, all above the bar (top 735). The page has scrolled to clear them. The last checkbox is fine.
- Save toast | verified | "Saved 16:39 WAT, version 1." appears after a valid save.
- 422 | verified | reference "Retrospective 2026-11-21" with nobody picked shows "Pick people who are on the project."

## Notes
- At 390 with a clean form Save is disabled, so it is skipped in the Tab walk; that is expected.
- The e2e `Lessons` check passes for the builder but fails in my walk, so the check should be made to start at scroll 0 after a fresh load.
- Servers: I started a mock on 4993 (PID 16679) and next dev on 4992 (PIDs 16680 and child 16832). All were stopped by PID; the ports are free. I did not touch 3000/3001 or any process from the main checkout.
- Scripts are in the scratchpad `ux5/` folder, none in the project.
