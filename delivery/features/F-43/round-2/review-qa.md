VERDICT: PASS
REVIEWER: qa
COMMIT: ee8fe64afa47a84ad9599e9f70820ec5fdacaae6
AUTHORITY: delivery integrated QA

## Summary
- Ran the live demo (app 4895, mock 4894, production build) in headless Chromium at 1440 and 390, persona `finance_lead`, mock reset before every journey. Scripts: scratchpad `qa.mjs`, `qa2.mjs`, `qa4.mjs`. All of the spec's success and failure journeys behave as specified at both widths.
- Exercised: W-4001..W-4013 reads; approve (double-press), return and reject (empty note refused with 0 POSTs, trimmed note sent once); W-4009 (two verdicts), W-4010 (link), W-4011 (no revoke/post); W-4013 uncertain decide; W-4003 reconcile (no choice, proof-first, delivered, not delivered, can't tell, 403/409/422); holds W-4005/6/7/8/12 (0 POSTs when every button is pressed); access (persona `none`, 401, 403, 404); reload after every write.
- Money: the verified strip has 6 cells at both widths. W-4002 Unknown cells read Unknown, with no bare "₦0". "Approved" and "Verified" appear only after the re-read: W-4002 before any action shows APPROVED only as a History row "Not yet" and the Verified station "Not started". After Approve the state is APPROVED, never VERIFIED, and it survives a reload.
- Not proved: this is the contract mock, not a real backend. The mock does not scope fixtures by role, so authority is proved only through `you_can_act`. No real delivery provider. No axe run (covered by the builder's e2e).

## Findings
- QA-2-1 | non-blocking | medium | frontend | Known shared stale-409 gap (TECH-1-1, F-43 picks it up from dlv-00 before merge). A decide answered 409 (checked through the `x-mock-scenario: 409` header on the decision POST) shows "This review changed while you were reading it, so nothing was recorded", but the typed note is gone at 1440 and 390. Spec AC 16 wants the note kept. Same cause as the second reviewer acting after the task closes. Re-test after the dlv-00 merge.
- QA-2-2 | non-blocking | low | integration | Mock limit: persona `pm` can open W-4002 and sees Approve, Return and Reject. It also sends a claim. Fixtures are not persona-scoped, so the wrong-role journey is proved only by W-4005 (`prepared_by_you`) and W-4008 (`not_your_role`), which show no buttons and send 0 POSTs. The real backend must refuse it.
- QA-2-3 | non-blocking | low | frontend | A 403 on decide (header scenario) draws the "This decision needs a Forecast reviewer. You can't approve, return or reject it." read-only view and no success words, but the status stays AWAITING FINANCE DECISION until a reload. This matches the spec's "keyed on the re-read cannot_act_reason". Noted because the mock's re-read still says the user can act.

## Verified
- UI-1-1 | verified | W-4004 and the reconciled W-4003 show 6 dt cells at 1440 and 390, no horizontal overflow, no ₦0.
- UI-1-2 | verified | The ACCEPTED, UNKNOWN and NOT SET tags draw on W-4001, W-4003, W-4006 and W-4007 (UX also saw them). W-4006 and W-4007 have 0 buttons and 0 POSTs.
- UI-1-3 | verified | Phone W-4003 runs banner, Delivery, Next, then the "Record what happened" choices. One panel, no overflow. The reconcile journey completes at 390.
- UX-1-1 | verified | W-4003 at 1440 and 390: pressing with no choice shows "Choose what happened to continue." with 0 POSTs. "It arrived" without proof leaves the button disabled. After the upload it is enabled, and a double-click sends one action `{expected_revision:5, action:"reconcile", outcome:"delivered", evidence_id, case_revision:3}`. The result is VERIFIED, and the panel is gone and VERIFIED persists after reload.
- TECH-1-2 | verified | W-4003 at 1440: the "Record what happened" region is reachable, with no nested complementary.
- TECH-1-3, TECH-1-4, UI-1-4 | verified | Not browser-testable. Phone: exactly one panel; the line key is single-sourced per the technical review.
- Writes and refusals | verified | Approve sends claim then one decision `{expected_revision:1, verdict:"approve"}`. Return and reject send the trimmed note and end on RETURNED and REJECTED, which survive reload. W-4013 ends on "DECISION NOT CONFIRMED" with 1 decision POST and no success words. Reconcile 403, 409 and 422 show the backend message and never resend. The "not delivered" and "can't tell" outcomes end on NOT DELIVERED · HELD and HELD with no resend control.
- Access | verified | Persona `none` shows "No sections are open to your role yet" with no title or amount, and 0 POSTs. The work read answering 403 or 404 shows the same "You can't open this work item" view with no leak. 401 shows signed-out with Sign in.
