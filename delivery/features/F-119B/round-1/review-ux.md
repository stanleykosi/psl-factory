VERDICT: PASS
COMMIT: 9d9b149c0eee33789567d9006229314f1224d6d0
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- AC 24 (UX-5-1) is met. At 390 the Tab walk from the top of the form to Save has no focused control under the fixed Save bar, including "Lessons for next projects".
- For every focused control, the bottom is at or above the bar top and `elementFromPoint` at its centre returns the control. Lessons now sits at 687-754 with the bar top at 762 (scrollY 21), and 659-726 against 735 when the bar is taller.
- Desktop (1440) tab order is unchanged: notes file, Save, "Add a decision". The save toast and the 422 message are still correct.
- The rest carries over from my F-119 round 1 to 5 reviews.

## Findings
None.

## Verified
- UX-5-1 | verified | 390, next dev 4992 and mock 4993, Tab walk from the Skip link on /projects/2001/retrospective?dossier=5001 with a valid form. 14 controls (Reference, the three boxes, both participants, notes file, Add a decision, Save) all clear and un-hit by the bar. 16 controls with a decision row added (Decision 1, its file, Remove, Add a decision) all clear. The same holds with touch emulation off and at 360x640. No bad control; the Save button itself is inside the bar.
- Desktop order | verified | 1440: Tab from the notes file goes to "Save retrospective", then "Add a decision".
- Save toast | verified | "Saved 17:10 WAT, version 1." at 390 and "Saved 17:11 WAT, version 1." at 1440; at 390 the toast is not hidden.
- 422 message | verified | With nobody picked: "Pick people who are on the project." at both widths.

## Notes
- At 1440 the Save bar is in the page flow, not fixed, so the covered check does not apply there. My script showed "Add a decision" as below the bar top only for that reason.
- Save is disabled until a notes file and a person are picked; that is expected.
- Servers: I started a mock on 4993 (PID 58808) and next dev on 4992 (PID 58809). Both were stopped by PID; the ports are free. 3000/3001 untouched.
- Scripts are in the scratchpad `ux5/` folder, none in the project.
