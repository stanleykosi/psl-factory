VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: bad2bb2dd6f6d198aa7c72719cec51a8c1db6c11
AUTHORITY: delivery UI review

## Findings
- UI-2-1 | blocking | low | frontend | UI-1-5 is only half fixed. At 390 the stacked table still draws a short loose rule under each select-box cell and under the header box (screenshot scratchpad/ui/r2-W-3402-390.png). Tags are now natural width, but the checkbox cell border remains. Expected: no stray rule; fix in `workspace.css` for `.ws-table--stack` and re-check the F-30/F-31 stacked tables, which the builder did not look at.
- UI-2-2 | blocking | low | fixtures | Exceptions "From PSL's past answer: Harmattan Bank RFP 2025 · R-12 · that bid was won" and the "Harmattan Bank RFP 2025 · R-12" link are filed as `missing` because "no field returns the bid result or link". The board draws both, and the contract says a missing field is built with mock data, not omitted. Expected: add the result text and link to the W-3402/W-3403 fixtures and remove those two exceptions (and the phone "From Harmattan…" one), or have the design engineer approve them as a drawable-element waiver.

## Verified
- UI-1-1 | verified | live W-3402 at 1440 and 390: "Accept selected" is grey secondary (rgb 201,205,199); "Accept answer" is the only blue primary in the review panel.
- UI-1-2 | verified | W-3401 at 1440: Tola's note sits directly after Progress, before Before review and Decide.
- UI-1-3 | verified | W-3402 shows only the table and "Review Tola's suggestion"; no note or Before review checklist at either width.
- UI-1-4 | verified | panel names Tola once (name line; the tag no longer repeats it). The Status exception now separates the review boards (missing control, Conflicts 4) from edit/reject (shared form label, Conflicts 12). Honest.
- UI-1-5 | partly | tags 136px on W-3402 at 390 (natural width); loose rule remains, see UI-2-1.

## Notes
- No horizontal overflow at 390 or 1440 on W-3401 or W-3402. Scores 70.5 to 74.7, coverage 100% with 51 exceptions, all unsigned waivers (not blocking).
- Other exceptions checked: none hide a data value; counts, file names and filters are on the page in another form.
- At 390 the blue "Record team input" button sits above the review on W-3402 beside "Accept answer"; it is in the shared Decide panel and has its own exception, so not raised.
