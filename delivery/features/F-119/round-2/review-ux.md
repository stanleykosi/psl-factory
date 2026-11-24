VERDICT: PASS
COMMIT: f39d6dda8b095d99f19a3f9c809a2c97b71eba27
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Walked /projects/<case>/retrospective at 1440 and 390 as the PM persona on next dev 4992 + mock 4993: empty and filled form, save toast, unplaced 422, stale 409, and 503 "not confirmed".
- Layout now follows the board: no panel title bar, Save straight after the Notes file (300x50 on desktop, full width on phone), then the optional Decisions block; no sideways scroll at 390; chip colours read correctly (green Closed/Recorded, red-orange Not yet, amber Unknown).
- An unplaced 422 shows "Pick people who are on the project." as a form-level message above Save; "Check the highlighted fields." is gone; Save stays usable.
- 409 shows "This changed while you were editing. Reload and try again." with a Reload link and keeps typed values; the 503 shows "We couldn't confirm it saved. Nothing is sent again by itself. Check again", then "It was not saved. Press Save again." and Save returns.
- Save toast "Saved 15:00 WAT, version 1." appears after the re-read.

## Findings
None.

## Verified
- UX-1 (no findings in round 1) | verified | nothing to retest.
- UI-1-1 to UI-1-4 (layout, in my lens only for flow) | verified | Save position/size and phone one-column cards seen at both widths.
- TECH-1-1 | verified | unplaced 422 shown as form-level message at both widths.

## Notes
- Phone: the info note about closure sits below the form, as on the board's mobile layout.
- Not checked: criterion 21 (live Django, no credentials). Servers started by me (PIDs 63933 next, mock) were stopped; ports 4992/4993 are free.
