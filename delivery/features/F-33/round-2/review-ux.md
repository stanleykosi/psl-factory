VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 9ebc7cbc98a2cedb7345180e50c1489ca0930d19
AUTHORITY: delivery UX review

## Summary
- Walked W-2701..W-2711 as finance_lead at 1440 and 390 on the build at :4883, then pressed decisions on W-2702 (mock reset afterwards). Spec criteria for the journey hold; no dead ends.
- Plain language: "Approve schedule", "Return with a note", "Reject" under "Decide · Schedules reviewer". The panel says "Approving doesn't post anything. Exporting it as an accounting adjustment is a separate step with its own approval." The verified page shows "Posted to the ledger: NO".
- Amounts: "₦12,400,000.00" in full at both widths. W-2707 shows "Unknown" for the report line and Detail rows, with no ₦0, blank or dash.
- Return without a note shows "Add a note to return it." and sends nothing. On phone a bottom bar opens a drawer with a labelled note field and Cancel. Approve moved W-2702 to Verified with "Schedule v1 is approved".
- Hold W-2706: SETUP NEEDED, "Who reviews schedules: NOT SET" and the next sentence, with no Decide panel and no reviewer named. W-2705 and W-2708 explain why there are no buttons. W-2709 offers two verdicts, W-2710 a single link "Open the review", and W-2711 draws no decide controls. The uncertain-result wording was not reproduced in the browser (no fixture); it is covered by the build's tests (not confirmed in the browser).

## Findings
1. UX-2-1 | non-blocking | low | frontend | /work/W-2706 (desktop): the hold shows a full-width "See all exceptions" button above the stations, so the hold page is not button-free and the control reads oddly. Expected: a hold with no action controls. Actual: one link-button, probably from the shared frame; confirm it is intended or remove it.
2. UX-2-2 | non-blocking | low | frontend | /work/W-2702 (desktop): Approve, Return and Reject act on one press with no confirmation and no stated consequence for Reject. Matches the approved F-29-style inline decide, so not blocking. Expected: Reject copy says what it does. Actual: only the Approve line explains "doesn't post anything".
