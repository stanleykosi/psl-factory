VERDICT: PASS
COMMIT: 798c17f8b0b30f6aabf94dc0ff621a901b6df7e4
REVIEWER: reviewer-ui
AUTHORITY: delegated UI review

## Verified
- UI-1-1 | verified | Fixtures W-2201, W-2202, W-2204 no longer carry `byline`/`version`, and W-2202, W-2203, W-2204 no longer carry `subtitle` (diff 0036fe0a..798c17f8, build.md). In side-by-side SCR-25-desktop-assembling the intro band now sits at y ~255, where the board has it (round 1: 292). The default board keeps its subtitle and now has no "Written by" row. A test pins rows present/absent per state. I read the default and assembling side-by-sides; I did not re-run the check.
- UI-1-2 | verified | W-2204 P-2 and P-3 now have `cite_label` "ISS-0233" and "MIN-0141", the words the board draws. The MIN-0141 vs MTG-0140 question stays open for backend/PMO; it does not change what is drawn.

Coverage is 100% after approved exceptions on all 8 boards (raw coverage unchanged). Visual is 72.8 to 80.3, each under a signed D-83 waiver (>= 70); the waiver reasons in fidelity-exceptions.json carry the new numbers. report.json and side-by-side.png are in round-2/fidelity/<board>-<width>/.

## Why desktop default (75.3 to 72.8) and assembling (77.0 to 73.7) went down
- Removing the extra rows made the page shorter and moved content up, which is what UI-1-1 asked for, and the content now sits closer to the board's positions. The tool's visual score is a pixel comparison, and it fell. The builder says the page's bottom no longer lines up with the board's bottom. I read the images: the change is in the score only, not in any visible regression.
- Assembling: the board's right-hand card is a short blue "WORKING" checklist. The page draws a tall card with DONE / IN PROGRESS tags, a warning note and a Decide panel below it. Those differences were already covered by D-83, D-85 and the exceptions. With the page's top now aligned, they account for the remaining gap.
- Desktop default: the board has the form open as one panel beside a records column. The page has the Tabs bar, read-only sections stacked full width, and the Decide panel with the form open in the side column. The page is therefore much taller than the board. That is the frame layout and D-69, not fixture data.
- Still fixable inside F-21: no. The remaining gaps are frame layout (tabs, sections, the Decide panel, step buttons colours, a section note always drawn as a warning), phone wording, and D-69. All are covered by approved exceptions or D-83 and belong in the frame backlog.

## Findings
none

## Notes
- The cite-field hint ("Records you cited in the saved draft stay on it until you choose new ones.") repeats four times in the open form and lengthens it. This is a matter of taste, and the backend must confirm the behaviour. Consider showing it once.
- The disabled green "Send for PMO Lead review" button on assembling has very low contrast (same as UX-1-3, shared design-system button). Not an F-21 change.
- No CSS other than `data-form-open` on the phone Decide bar changed; no hard-coded colours added.
