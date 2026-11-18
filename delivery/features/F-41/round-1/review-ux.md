VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: ea9718cd5eeb3fd267df59ebb13d7373165cd43e
AUTHORITY: delivery UX review

## Summary
- I walked the payments list (`/finance/payments?status=issued`) and the reminders W-3801 and W-3803 as `finance_lead` at 1440 and 390, against spec.md and the SCR-20 and SCR-32 boards. Conflicts are provisional under D-115.
- The list reads clearly. Invoiced, received and still owed are three cells with full amounts as returned (₦6,800,000.00, ₦0.00 for known zeros). INV-0402 shows amber "Unknown" with "amount not known" spoken, never 0. Overdue shows "9 days", "—" or the backend's value. No wording suggests a debt is erased or settled.
- Search sends nothing for one character and one `q=Harm` request after the pause. The result keeps the strip, and "No invoices match" offers Clear filters. Neither width scrolls sideways.
- On W-3801, Edit opens a dialog at 390 with Subject focused and the fields filled; Escape closes it and returns focus to Edit. On desktop an empty Message puts focus on the Message field with an error. Phone buttons are 44 px tall.
- Send made exactly one POST, then showed "SENT · CHECKING DELIVERY" with "Not yet" per recipient. Nothing said Delivered. On W-3803 (uncertain), the phone view shows "DELIVERY UNCERTAIN" and each recipient "UNCERTAIN". Send, Edit and Not now are disabled, and they stay disabled after a reload. There is no resend. The mock was reset afterwards.

## Findings
- UX-2-1 | non-blocking | low | frontend | On W-3803 (uncertain), the subtitle still reads "Nothing is sent until you press Send." and "This sends to the client." sits under the disabled buttons. Both are stale next to "Delivery uncertain". This comes from the shared frame and fixture text, not the F-41 page. Consider updating the fixture subtitle for uncertain items.
- UX-2-2 | non-blocking | low | frontend | The phone list cards show only "Still owed", state and overdue days, not invoiced or received. This matches the SCR-20-mobile board, but a person on a phone cannot see billed and received without the desktop table. Needs a design-engineer decision if wanted.
- UX-2-3 | non-blocking | low | frontend | The Edit drawer's submit button is labelled "Edit", the same as the step that opened it. Use "Save draft" if the backend sends a label.

## Verified
None. This is the first UX review, so there were no earlier findings to check.
