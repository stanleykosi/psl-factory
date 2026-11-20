VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 139eceeb05c331741f89d45b9b995c5175ca1fa0
AUTHORITY: delivery UX review

## Summary
- As pmo_lead on the running demo, Start work offers "Log a received RFP" (Pre-sale); the whole flow works end to end at 1440 and 390.
- Submit lands on /work/W-3351 with an Unassigned row added; 403 shows "You can't start this here."; uncertain keeps the form and offers Check again; a repeated reference is caught beside the field.
- Phone sheet keeps the same fields, Log RFP pinned, nothing overflows.
- Two low notes, no blockers.

## Findings
- UX-1-1 | low | medium | builder | In the uncertain state the form is locked and the chosen submission method loses its selected fill, so the PMO Lead cannot see what was chosen. Keep the selection visible when disabled.
- UX-1-2 | low | low | builder | The Received and Deadline controls are the browser's native date-time input (mm/dd/yyyy, am/pm); Nigerian users may expect day-first. Accepted by spec (conflict 6); consider help text or a later custom control.

## Verified
- Client picker: three existing clients plus search; no New client row by default (spec conflict 1, D-130); with the new-client overlay the row appears and is a plain choice that opens a name box, no promise of a register entry.
- Fields: reference (help "As written on their document"), received with help, method choice, submit to (optional), deadline Unknown/Stated/Not stated with date, note (optional) all accept input and send.
- RFP file: Choose a file turns into a file row with name and size and a remove x; submit waits for "Uploaded".
- Submit: lands on /work/W-3351 at both widths; Unassigned count rose.
- 403: banner "You can't start this here." with the entered client and reference kept.
- Uncertain: amber banner "We couldn't confirm the start...", button changes to Check again, footnote says it will appear in My work if it started.
- Duplicate reference for same client: "This RFP is already logged for that client." under the field, button disabled until changed.
- Phone sheet at 390: opens from Start, all fields reachable by scroll, Log RFP pinned, no horizontal scroll.

## Carried forward to round 2 (coordinator, D-123)
Round 2 drew the phone submission method as one row of four (CSS, scoped), removed six exceptions, fixed the fidelity driver, and merged test-only fixes from dlv-00 (#80, #81). No write, authority or journey path changed. Carried forward; the UI re-review covers the changes.
