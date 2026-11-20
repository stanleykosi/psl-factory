VERDICT: PASS
REVIEWER: qa
COMMIT: 139eceeb05c331741f89d45b9b995c5175ca1fa0
AUTHORITY: delivery integrated QA

## Summary
- Drove the running demo (app 4965, contract mock 4964) at 1440 and 390 in Playwright as pmo_lead, resetting the mock before each run. Scripts are in the session scratchpad (qa/qa.mjs, dbg.mjs, dbg2.mjs).
- Journey passes at both widths: the picker lists three clients and no New client row; the upload sends once; a double press sends one start with an idempotency key (case_revision 6); it lands on /work/W-3351; Unassigned goes 6 to 7 with the typed reference and client, and the row survives reload.
- 403 shows "You can't start this here." and keeps the form; 409 shows the changed-record message with entries kept; 500 and uncertain show "We couldn't confirm the start" with Check again; none claims success. Check again replays the same key and lands on W-3351.
- Submission method is one row of four at 390 (all four tops equal). Persona none: no RFP line and options answer 404. Invoice line form is unchanged.
- Not proved: a real backend (new client, shared case contention, duplicate refusal are mock only); the 409 and 403 were injected with page.route, not produced by the mock; the work page shows the mock's fixed W-3351 fixture (TL-RFP-2026-014), not the typed reference.

## Findings
- QA-2-1 | non-blocking | low | frontend | Pressing "Log RFP" with every required field empty sends a start with `intake: {}` and relies on the mock's 422 ("6 things to fix") for the required messages. The spec says the required message shows and nothing is sent. This is likely the shared F-05 behaviour (not checked on another line); no write results, so it is harmless against the mock, but confirm the intent.

## Verified
- UI-1-3 | verified | method radios share one top (536 at 1440, 620 at 390); choices Email / Client portal / By hand / Not stated.
- TECH-1-2 | verified | not exercised by a browser path I could trigger; not retested.
- Client picker, New client row | verified | options Tamarind Loans Ltd, Harmattan Bank, Kora Logistics; no New client row, no write.
- Deadline Unknown / Stated / Not stated | verified | Stated sent deadline_at as an instant; Unknown sent no deadline_at (second run).
- Upload and start | verified | 1 upload, 1 start despite dblclick; body has client, rfp_reference, rfp_document EV-SW-C-RFP-INTAKE-1, received_at, submission_method, deadline_status, note.
- Errors and uncertain | verified | 403, 409, 500, start_uncertain as in Summary.
