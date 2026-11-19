VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 4dba97ab6ee7dd7c97f33f51a63d28750636cb58
AUTHORITY: delivery UX review

## Summary
- Walked W-4201 to W-4211 and W-4212 at 1440 and 390 as finance_lead, plus persona none, in a real browser against the demo (4955/4954). No sideways scroll anywhere.
- Journey matches the spec: observe form opens with nothing chosen, Proof is required, validation is announced, the upload "×" is 48px on the phone, and the observer sees "You prepared LED-0052 v1, so someone else must review it." after the re-read.
- Review: Approve reference and Reject sit under "Decide · Ledger reviewer", with the label "Note (needed to reject)" and no Return. Verified and rejected appear only after the re-read. W-4212 reads CHECKING. W-4205, W-4206, W-4207 and W-4209 show no controls.
- No amount or currency appears on any page. Persona none gets the not-open page with no title or facts.
- One non-blocking item (the shared milestone strip).

## Findings
- UX-1-1 | non-blocking | low | integration | Every ledger page shows the shared work-item milestone strip "DRAFTED / REVIEWED / APPROVED / SENT / RECEIPT RECORDED Unknown / VERIFIED" with "Earned 14 Nov 16:30". The SCR-58 boards do not draw it, and "SENT" and "RECEIPT" are invoice words that mean nothing for a ledger reference. It comes from shared work-item code, not from the F-45 fixtures. It never claims approval early (APPROVED reads "Not yet" until the re-read). Suggest that the coordinator decide whether ledger_sources should hide it, as a shared change outside F-45.

## Verified
- Round 1, so no earlier findings to verify.
- Not exercised by me, and relied on the builder's tests: the stale 409 note, the 5xx on decide and the W-4213 retry. The Unknown path (W-4208) and the Reject-with-note path ran only up to a partial drive.
