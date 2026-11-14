VERDICT: PASS
COMMIT: 3c93fe030ff5ac81da343dc7a0917820c8803d7b
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Re-walked W-1201 on the shared build (app 3401, mock 3402) at 1440 and 390 as Ada Okafor. The mock was reset before every flow and again at the end.
- New "couldn't confirm" state, checked by failing the decide POST (aborted) and the item reload (503) with route interception. A warning callout reads "We couldn't confirm whether your decision was recorded. We also couldn't reload this item to check, so the decision buttons stay off. Try again reloads the item; it doesn't send your decision again." Approve, Return and Reject are disabled. Try again is the only live control. It was clear on both widths. Once reads succeed, Try again returns the actionable item with "We couldn't confirm your decision. We've reloaded this item so you can see whether it was recorded."
- Approve done view matches SCR-03 done. It has a green banner with "YOU APPROVED · time" and "Invoice v2 is approved", the earned-stations strip, a green next-step line, the Paid note, and "Open the work item" and "Back to my work". There is no sideways scroll at 1440 or 390.
- Return and reject done views (no board; for the design engineer's product check). Both use the same layout in a neutral grey banner ("YOU RETURNED / YOU REJECTED · time", "Invoice v2 was returned / rejected"), and APPROVED stays "Not yet". The next-step callout is info blue ("Bisi Ade corrects invoice v2 and resubmits it." / "Bisi Ade decides what to do with the rejected invoice."). They read as calm and clearly not approved. Reject uses the same grey as return, so the only difference is the wording.
- UX-1-1 fixed: W-1203 now reads "1 step".

## Findings
- UX-2-1 | non-blocking | low | frontend | In the unconfirmed state the Note textarea stays editable while all three decision buttons are off. Harmless, but it invites typing a note that cannot be sent. Optionally disable it or leave it, as the design engineer prefers. `frontend/src/features/decide/DecidePanel.tsx`.
- UX-2-2 | non-blocking | low | frontend | In the unconfirmed state the page heading still reads "Approve invoice v2" and the "Approving earns APPROVED only" hint stays visible. This is acceptable, because the warning is above it, but "Approve invoice v2" can read as if the approval happened. Consider keeping it as is, since it names the item.

## Verified
- UX-1-1 | verified | W-1203 shows "1 step".
- UX-1-2 | not in this round's Fixes | not retested, still non-blocking.
- UX-1-3 | not in this round's Fixes | not retested, still non-blocking.
- UX-1-4 | not in this round's Fixes | mock-only, unchanged.
