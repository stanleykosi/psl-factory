VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 435ef7d9d8d5d407902dffba40b1efcb8bc9bc7f
AUTHORITY: delivery UX review

## Summary
- Walked W-3401 to W-3404 on the live demo (app 4995, mock 4994) at 1440 and 390 as persona pm, finance_lead and none, in a browser.
- Accept, edit and accept, write my own, select-all, discard question, record team input, add requirement, uncertain and read-only states all behave as the spec says. No blocking UX problem found.
- Visual fidelity scores and the unsigned exceptions are the UI gate's lens, not reviewed here.
- Five small non-blocking items below.
- Not exercised: the 409 and 500 paths (the mock scenario cookie did not trigger), and the reject/return flow (part 2, out of scope).

## Findings
- UX-1-1 | non-blocking | low | frontend | Record team input drawer at 1440 (height 844): the "Record input" button sits over the Note field, so the field is cut off until you scroll. Shared F-18/F-31 drawer, not part-1 code. Seen in a screenshot, not confirmed at other heights.
- UX-1-2 | non-blocking | low | frontend | The Add requirement empty-field message reads "Add rfp page to continue." (lowercase "rfp", built from the field label). Expected "Add the RFP page to continue." Shared StepForm.
- UX-1-3 | non-blocking | low | frontend | Phone, W-3402: a red "RECORD TEAM INPUT" card says "Only a PM can decide. You are PM." above the table, which desktop does not draw. It repeats the Record buttons and the wording is unhelpful. The phone header also shows "revision 7", a technical detail.
- UX-1-4 | non-blocking | low | frontend | Phone: the select-all row is an empty bordered box with a lone checkbox, with no visible label. The accessible name is "Select all shown rows". A visible "Select all" would be clearer.
- UX-1-5 | non-blocking | low | frontend | After "Accept selected" or a single accept, the "N selected" count carries over (4 selected, then 3 selected after R-07 is accepted) while the accepted row stays in the list. Fixture-driven but could confuse. Clearing the ticks after a successful write would be safer.

## Verified
- Accept answer: one request, notice "R-07 accepted under your name.", focus moved to the "Review Tola's suggestion" heading, next suggestion R-08 shown (both widths).
- Edit and accept: opens with Tola's text and Addressed, submit "Save and accept". Escape after a change asks "Discard your changes?" with Discard and Keep editing, and Keep editing returns the typed text. Phone uses a full-height drawer.
- Write my own: an empty save names the field (one invalid field, drawer stays open). Status radios are present.
- Select-all ticks only the 4 rows shown, with "4 SELECTED" and Accept selected enabled. Target is 20px but its label row is large on phone.
- Record team input: Record on Security and Product opens the shared drawer, with the "don't log in; you record their input with proof, and the record keeps your name" copy, the team picker on Security, and a proof upload.
- Send for review: disabled, with the backend's reason visible.
- Uncertain (W-3403): the "being checked, nothing was sent again" notice shows and Accept, Edit and Write my own are disabled.
- W-3404 (read only): no Record, Add or Send, only Show more.
- Persona none: "No sections are open to your role yet", with no RFP data. finance_lead gets the same controls as pm (nothing comes from role).
- No sideways scroll at 390.

## Carried forward to round 2 (coordinator, D-123)
Round 2 changed layout and styling (UI-1-1..1-5) and scoped the desktop task-panel hiding to the team-input task (TECH-1-1); the journeys this review walked are unchanged. Carried forward without a fresh UX review; the UI and technical reviews cover the changes.

## Carried forward to round 3 (coordinator, D-123)
Round 3 changed the stacked-table CSS at 390, added the past-answer result and link to the W-3402/W-3403 fixtures (drawn from data), and made a 44px link fix. No write, authority or journey path changed. Carried forward; the UI re-review covers the changes.
