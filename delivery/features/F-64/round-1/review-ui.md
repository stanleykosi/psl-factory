VERDICT: CHANGES
COMMIT: 7318a3fc23558a60d535835417ef644a320f22bf
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer

## Summary
- Judged the builder's round-1 fidelity reports and side-by-side images (not re-run, D-180) for default, done, stale and not-yours at 1440 and 390. The own board is unreachable by design (Q2/Q12) and was not judged.
- Every visual score is under 90 (64 to 86). Most of the gap comes from approved D-182 removals: facts strip, Chidi card, basis and change rows, project and invoice lines, Chidi next step. Page height is much shorter than the board.
- Scores are not all explained by exceptions. Real defects remain in stale (table semantics and labels), mobile not-yours (white gap in the strip) and the done desktop side panel landmark.
- The amount "missing" on 6 boards is a tool false-negative: "₦4,250,000.00" is visible and styled like the board (mono, bold) on every one. Coverage cannot reach 100% until the tool matches it or the design engineer waives it.
- Same tokens, type and surfaces as the boards. Nothing overflows at 390.

## Findings
- UI-1-1 | blocking | medium | frontend | Stale compare (SCR-03-desktop-stale) is a grid, not a table. The tool reports the table and both column headers ("VERSION 2 · REPLACED", "VERSION 3 · CURRENT") missing, and they are not excepted. Restore table, columnheader and row semantics. Board rows are about 34px with 12px padding, the page rows about 24px. Board highlights only the changed row (Send to), the page highlights Amount. Board label is "Send to", page shows "Send to" on desktop but "To" is missing on the phone board. Expected: board structure and row rhythm. Actual: grid with tighter rows. Path: frontend/src/features/decide/LiveContent.tsx and decide.css (compare block).
- UI-1-2 | blocking | medium | frontend | Stale phone (SCR-03-mobile-stale-390) differs from the board. Board shows a one-line grey replaced card "Invoice v2 · ₦4,250,000.00 · REPLACED", then one current card with "To" and a "changed"/"unchanged" tag. Page shows two full cards with "VERSION 2 · REPLACED" and "VERSION 3 · CURRENT" headers. The tool lists "REPLACED" and "To" as missing, not excepted. Build the board's compact replaced card and its "To" label, or ask the design engineer for an exception.
- UI-1-3 | blocking | medium | frontend | Phone not-yours (SCR-03-mobile-not-yours-390): the facts strip is a 2-cell row (Amount, Waiting for) with an empty white cell at the right, where the board has a full 3-column strip with no gap. Fill the row or make the Waiting cell span the remaining width, as the desktop does. The Add comment bar is inline under the text, not the bottom-pinned bar on the board; align it or record an exception.
- UI-1-4 | blocking | low | frontend | Done desktop (SCR-03-desktop-done-1440): the "What happens next" panel is not exposed as a complementary landmark (the board has one), and the tool reports it missing without an exception. Render it as aside. The same applies to the phone done and default pages if they use a plain div.
- UI-1-5 | non-blocking | low | frontend | The page title is drawn twice on every board: the large heading, then the same text again as a small sub-line ("Invoice 3 for the Lekki handover" twice). The boards have no sub-line. Hide the sub-line when it equals the title; in live data the two may differ.
- UI-1-6 | non-blocking | low | frontend | Extra elements not on the boards: a "0 / 2000" counter, an "Open the work item" link under the not-yours comment, and "Approving earns APPROVED only." replacing the board's longer footnote. The default board's Approve is grey (disabled) until evidence is picked, because the evidence picker is required by the spec, so the board's blue Approve is expected to differ. Confirm with the design engineer; none breaks layout.

## Verified
None (round 1).

## Notes
- Visual-score reading. Explained by approved exceptions: desktop default 71, desktop done 70.5, mobile default 65, mobile done 64.3, desktop not-yours 78.8 and mobile not-yours 85.8 (the Basis cell and the strip are gone, so the remaining cells are wider). Partly explained: desktop stale 74.1 and mobile stale 77.5, where the removed Chidi card and drafted-time text account for much of it, but UI-1-1 and UI-1-2 add real differences. Not one of the eight is a layout break, wrong colour, wrong type or wrong radius.
- Header, nav and the bell with its badge come from the shell, not SCR-03, and were not raised. The "Your decision was recorded." toast is transient and was not counted.
- The tool's position and colour notes on "My work" (white text with orange bar on the board, grey without it on the page) belong to the shell and are not an F-64 finding.
