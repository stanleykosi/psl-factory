VERDICT: CHANGES
REVIEWER: reviewer-ux
COMMIT: 32c97d3df9f2b6f5ae78bf523744c57ee74d83b4
AUTHORITY: delivery UX review

## Summary
- Walked W-3501 to W-3509 at 1440 and 390 as pm, ceo, finance_lead and none, with a request log. Nothing reads as submitted, sent or received before the re-read returns it. One decision POST per press, claim only on press, no resend control, controls locked after an uncertain send.
- Two fixture-level contradictions on the uncertain, not-delivered and submitted pages will mislead a person at the moment that matters (UX-1-1, UX-1-2). Both are fixture or shared-copy fixes.
- Demo note: app 4985 is built to proxy /api/v1 to port 4010, not the F-38 mock on 4984, so in the browser every W-35xx URL shows the invoice item W-1001. I routed the page's API calls to 4984 to review. Servers not touched.

## Findings
- UX-1-1 | blocking | medium | frontend | After an approve answers uncertain (W-3505.approve) and after Not delivered, the page still says "Next step. A document reviewer approves, returns or rejects this exact pack.", and the station track shows "Document review: Needs a person" and "REVIEWED In progress", while the timeline shows "Approved by document reviewer 26 Nov 14:58". The approval is already recorded, so the page tells a person a decision is pending and invites a second one. Expected: the fixture's `next_step`, stations and facts match the uncertain and not-delivered states. Actual: copied from the review fixture. Fix in `frontend/mock/fixtures/work/W-3505.approve.json`, `response/W-3505.not_delivered.json` and `.unknown.json`.
- UX-1-2 | blocking | medium | frontend | The submitted fixtures (W-3502.approve, W-3503, W-3504, W-3505.delivered) carry all six facts as "Earned 22 Nov 10:15", so "APPROVED", "SENT", "RECEIPT RECORDED" and "VERIFIED" read as earned four days before the timeline's 26 Nov 14:58 to 15:43. A fact claiming a send time earlier than the send is a false trust signal. Fix the `facts[].at` in those fixtures to the timeline times, or return no time (shows "Unknown").
- UX-1-3 | non-blocking | medium | frontend | The shared reconcile panel on the uncertain page says "so the client is never invoiced twice" and "before anything is resent", invoice wording on an RFP submission. Expected: wording for a submission pack. Actual: shared copy, outside this feature's lane; raise it with the shared owner or pass it through the fixture if the panel allows.
- UX-1-4 | non-blocking | low | frontend | The facts strip (DRAFTED, REVIEWED, APPROVED, SENT, RECEIPT RECORDED, VERIFIED) and the station stepper appear on every board state but are not on the SCR-40 boards, and no exception covers them. Check with the design engineer whether they are signed as shared frame.
- UX-1-5 | non-blocking | low | frontend | Small targets: at 390 "History" is 42x24 and the shell back link 41x44. At 1440 "Ask Tola" is 51x20 and "History" 50x15. The builder already listed the phone ones as shared items.
- UX-1-6 | non-blocking | low | integration | The demo app on 4985 proxies to 4010, so the demo cannot show F-38 states in a browser as handed over. Rebuild with `API_ORIGIN=http://127.0.0.1:4984` before the design engineer looks.

## Verified
- Pack and draft (W-3501): the frame, five tabs with Team input linked and Submission plain, four tagged pack parts, five checks with "FROM THE RFP, P.2", Tola's card, Ask Tola, Send for review and Edit cover letter. The letter text is already in the field. A blank letter is refused with "Add cover letter to continue." under the field and focus there, with no POST. At 390 the editor is a dialog.
- Send for review: one POST with CSRF and key. The page then shows "IN REVIEW" and "You prepared Submission pack v1, so someone else must review it.", with no step buttons. Nothing is claimed before the re-read.
- Reviewer (W-3502): Approve, Return and Reject with "Goes to procurement@...", the consequence and the full-pack link. Approve sends a claim and one decision with `{approve, expected_revision:1}`. "Submitted · delivery confirmed", the timeline, "Sent to ... RECEIVED" and "Record the outcome" appear only after the re-read. Return with an empty note sends nothing, shows "Add a note to return it." and focuses the note. With a note it posts once and shows "RETURNED TO PM" with no "Submitted". At 390, Return opens a dialog.
- Uncertain (W-3505): after approve the page shows "EFFECT UNCERTAIN", "Sent to ... UNCERTAIN, Time unknown" and the confirm panel. There is no Submitted, no Record the outcome and no send-again control, and the buttons are disabled. Not delivered shows "NOT DELIVERED", "FAILED" and no button.
- Holds and stale: W-3508 Approve is disabled with "A part still uses a test template." and Return and Reject are live. W-3507 Edit is disabled. W-3509 shows "Deadline UNKNOWN", no Company forms detail, the not-your-role copy and no controls. W-3506 409 re-reads to v2 and shows "Review the latest" with no second decision.
- Access: persona none shows "No sections are open to your role yet." with no controls. ceo and finance_lead see the same controls as pm.
- Phone: no sideways scroll on any state (scrollWidth 390), a single column, and the back link reads "← RFP" (the review item reads "Queue").
- Not run: the 403 and 404 mock scenarios, the 401 state, and a visual comparison against the boards, which belongs to the UI fidelity review.
