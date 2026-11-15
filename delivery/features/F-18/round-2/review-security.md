VERDICT: PASS
COMMIT: 28c13dbcca5af9b6db6f276e2878c43a487a8958
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Round 2 (352893..28c13db) changes 8 frontend files only. It adds no packages, no backend code, no mock or fixture changes and no secrets.
- The follow-up is still sent only when a person clicks Send. The new focus effect only moves focus. "Use the draft" only sets `editing` to false. Neither one calls `send`, and no load, reload or timer calls it.
- Send is now off while the edit box is empty, and `send()` also returns early when it is blank. A blank body can no longer cause the original draft to go out unseen. This closes round-1 security note 3.
- Nothing resends after effect_uncertain. The draft has no Send or Edit button, since `open` needs `drafted`. The `send()` guard still checks `status !== 'drafted'` and `unconfirmed`. "Check again" and "Try again" still only reload.
- Idempotency keys are still made only in `send()`, never when switching between the draft and edited text. Going back with "Use the draft" sends the same payload (no `body`) under the same key. Edited text gets a new key, as the spec says. The tests for reusing the key after a network error or 502, and for a new key after a 409, are unchanged.

## Findings
None.

## Verified
- Round-1 security note 3 (non-blocking, bundled with UX-1-3) | verified | `useFollowup.ts:52` `blank = editing && text.trim() === ''`, also checked in the `send()` guard at :66. `FollowupCard.tsx:169` turns Send off while the box is blank. In the test "Edit saves nothing; an empty box keeps Send off..." (`tests/rfp.test.tsx`), a click on the disabled Send makes 0 POSTs. "Use the draft" then turns Send back on, and the edited send carries `body`. Builder reports 53 rfp tests and 69 e2e tests passing, and the gate passed at 28c13db.

## Notes
- Impact assessment, carried forward from round 1. RecordedView now uses a different layout on phone and desktop. The links still come from `work()` with `encodeURIComponent` (RecordedView.tsx:16) or are the fixed `/projects`. "Record the outcome" still depends on `again` (pending or unknown, with `results` from the backend). The new "You can't send this follow-up" line only reports the backend's `can_send`/`can_edit` flags and grants nothing. Moving the CSS import order, adding an h1 with the task title as plain text, and the hint wording change nothing for security. The test for the outcome request with one proof file only confirms the request carries one `evidence_id`.
- Still open from round 1, for the backend. The mock replays a reused `idempotency_key` even when the body or version differs. Protection against a second email still depends on the server moving the draft to `sending` or `effect_uncertain`, not on the key alone. "Use the draft" makes the edit-and-change-back case reuse the key. Typing new text after an uncertain send still gets a new key, as specified.
- Still not checked here, for the backend. Permission and tenant checks for recording outcomes and sending follow-ups exist only as mock flags until T-RESPONSE / D-RFP-OUTCOME is built.
