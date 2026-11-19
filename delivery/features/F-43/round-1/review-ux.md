VERDICT: CHANGES
REVIEWER: reviewer-ux
COMMIT: 59ce7dc1e6896a89a54ccd7e83cf2addf5b51937
AUTHORITY: delivery UX review

## Summary
- Walked W-4001..W-4013 at 1440 and 390 as finance_lead, plus pm and none; approve, return (note and Drawer), reconcile and the decide-uncertain path, against the live demo (app 4895, mock 4894).
- Money reads honestly: full amounts, Unknown on Jan IN and the Feb-Apr opening/closing (never 0 or blank), nothing shows approved, delivered or verified before the re-read. Holds and no-access paths have no controls and name no reviewer.
- One blocking gap: the desktop reconcile button is disabled with no reason given, so the spec's "Choose what happened to continue." never shows there.
- Phone reconcile heading differs from desktop; small wording and duplication points are non-blocking.

## Findings
- UX-1-1 | blocking | medium | frontend | AC 18 says pressing "Record and continue" with no choice sends nothing and shows "Choose what happened to continue." On desktop (1440) W-4003 the button is disabled from the start and no message or hint says why; on 390 the button is enabled and the message path applies. A disabled button with no explanation leaves a keyboard or screen-reader user with a dead control. Expected: the same behaviour at both widths, enabled and explaining, or a visible hint beside the disabled button. Actual: desktop silent. `frontend/src/features/response/ReconcilePanel.tsx`; the "It arrived" case (disabled until proof) has the same silence.
- UX-1-2 | non-blocking | low | frontend | Phone W-4003 panel heading reads "Confirm what happened before anything is resent." (the client-line phone wording), not the board's "Record what happened" used on desktop. Conflicts 4 scopes the heading to the line, so phone should match. `ReconcilePanel.tsx`/`labels.ts` phone branch.
- UX-1-3 | non-blocking | low | frontend | W-4004 shows the same "Next" sentence twice, in the header ("Next step. As months close, a person records actual cash...") and in the NEXT section ("...record actual cash against the forecast."), and says a person records actuals while no control exists (Record actuals is held to part 3). Wording is the fixture's; consider one sentence only. Same duplication on every state.
- UX-1-4 | non-blocking | low | frontend | Agent card on W-4002..W-4007 reads "DONE" with "Hand to calculation" ticked, while on the hold pages (W-4006/7) station 02 says "Stopped". Reads as a contradiction beside "SETUP NEEDED". Data/fixture wording; no code change needed if the backend sends a stopped agent step.
- UX-1-5 | non-blocking | low | frontend | Phone: "Skip to main content" (129x21) and "History" (42x24) are under the 44x44 target. Both are shared frame elements, not new in F-43; noted only. Not changed by this feature.

## Verified
- Not a fix round: no prior findings to verify.
- Checked and passing: W-4001 agent card with Started 08:40, Ask Chidi, no controls; W-4002 six-row table, full "₦22,600,000.00", Unknown cells, note as sent, table region focusable with a name; Return with empty note shows "Add a note to return it." (inline on desktop, in the Drawer on 390), then RETURNED from the re-read; Approve gives APPROVED/"Forecast v1 is approved" with "Nothing is published yet", never Verified; W-4003 banner, Delivery facts, Next, no cancel/resend; Can't tell yet gives HELD with no resend; W-4004 VERIFIED with six figures and limit sentence, no Record actuals; W-4005 and W-4008 show the prepared_by_you and not_your_role copy and no buttons; W-4006 and W-4007 are holds with NOT SET, no controls; W-4012 has no panel; W-4013 approve ends on "DECISION NOT CONFIRMED" and "result not confirmed"; persona none gets the not-open view; pm sees the same controls (no /me gating); no sideways page scroll at 390.
- Not exercised in the browser (covered by builder's component/e2e tests, not re-run): stale 409 and 403/422 on decide, and reconcile 500/timeout. I could not provoke a stale conflict through the UI with the mock's claim rules.
