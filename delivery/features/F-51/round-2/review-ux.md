VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: ef0362f8cfe0fd7dab7e1ce57eb419db93395954
AUTHORITY: delivery UX review

## Summary
- Both round-1 blocking items are fixed and behave as the build record says, checked live (4965 app, 4964 mock) as the Finance persona at 1440 and 390.
- The Finance persona is not offered the RFP line, so I checked the same shared behaviour on the income schedule line (F-47); the F-49 RFP line rests on the builder's added test (rfp-intake.test.tsx).

## Findings
- UX-2-1 | non-blocking | low | coordinator | Shared change: F-05, F-47, F-49 and F-51 lines now all show the required messages and focus the first field on Start. Contract has no field for a choice default (builder used the field-level `value`). Coordinator may want it defined.

## Verified
- UX-1-1 | verified | Fixed asset schedule with no proof: "Proof is required." on the page, focus on the Proof control, no POST sent. Cash forecast: Scenario, As of and Months each name their error, focus on Scenario, nothing sent. Income schedule line: Kind, Reference, Mapping note, Proof named, focus on Kind, nothing sent. Same at 390.
- UX-1-2 | verified | Accounting note is a select with exactly two options, "Sample: note A" and "Sample: note B", clearly marked as samples, at 1440 and 390.
- Upload and start | verified | Proof upload shows "Uploaded · 96 KB" at both widths; Start schedule then sends the evidence POST and the work POST, the drawer closes and "Started" appears.
- UX-1-3 | verified | Sheet extras (Step 2 of 2, handle) are recorded in the exceptions; acceptable.
- UX-1-4 | carried | Mock-only refusal wording, already in BACKEND-HANDOFF.md; not a UI matter.
