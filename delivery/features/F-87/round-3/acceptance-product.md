VERDICT: PASS
COMMIT: f296a554242b27ef690d2ec359765ff2669b5377
REVIEWER: design engineer (hunchoweb), accepted in batch, delegated under D-184
AUTHORITY: D-182 and D-183 (batch answers); D-184 (batch-approved board changes count as product acceptance)

## Basis
F-87's only product decisions are board changes the design engineer answered in question batches (`delivery/connect/questions-batch.md`, `delivery/OVERNIGHT-DECISIONS.md`):
- LC-Q2, after an uncertain send: one "Check what happened" button runs the lookup, and the state it comes back with is shown (D-182, "Hide, accept all recs"). The "Confirm what happened" panel returned with API 1.24.0 under D-185 and is F-93, which is parked under D-201.
- LC-Q5, the buttons the boards draw that this feature leaves out: as recommended (D-182).
- LC-Q12, where Resume, Cancel and Check what happened sit: a controls row under the header, shown only for controls the API lists, with a "Cancel this work?" confirmation (D-183, accepted as recommended).
- LC-Q13, pausing and continuing background work: both buttons show whenever `background` is listed, because live does not say whether background work is running (D-183).
Results of a press show as toasts and problems as callouts, because the D-151 design rule forbids success callouts.

Recorded by the lane C coordinator under D-184 ("accepted in batch, delegated under D-184"). This is not a fresh review of the running screen by the design engineer; D-184 says they check merged screens on port 3000 afterwards, and anything they dislike becomes a fix.

## Carried over under D-188 (sync with main only)
The acceptance above was recorded for 9f9dc026. Head f296a554 differs only by the coordinator merging origin/main eb100065: F-71 (#114), F-64 (#111), #115, F-61 (#112), F-88 (#110) and #117. The merge was clean, with no conflict and no F-87 file changed by it. Carried over under D-188 (sync with main only).

## Not covered
- The merge: F-87 is rated high risk (readiness.md: a repeated effect after an uncertain send; Cancel is hard to undo), so it is not a routine merge under D-180. It goes to the design engineer through `delivery/connect/merge-batch.md`.
- Live: Pause and Continue proved 202 on work 1. Check what happened, Resume, Cancel and the live error paths are unproven live (round-3/review-qa.md).

## Findings
