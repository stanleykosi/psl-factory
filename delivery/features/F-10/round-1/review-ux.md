VERDICT: PASS
COMMIT: 02db3e841a47c4d83ed907c5bba467ef3a05a164
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked /finance/month-end?period=2026-10 as Finance Lead on the shared build (4011, mock 4012) at 1440 and 390, against SCR-36 desktop and mobile. Order, wording, tags, strip and action match the boards.
- Cash reads "₦4.7M + Unknown" (default) and "Unknown" (unknown variant); never 0. Payroll row shows "HR only" with no link. No horizontal scroll at either width.
- States checked: empty ("No month-end tasks you can see for October 2026."), pm (NO ACCESS view with "Back to my queue", no figures or task names), bad period ("This page doesn't exist." with "Go to My work"). No console errors apart from the expected 403.
- Phone "← Finance" at top right (D-19) and the Import link going to the work item (D-07) are approved decisions, so not findings.
- Phone with default data shows a seventh Payroll card the board omits; this comes from the data, not the layout (cards render what the response returns).

## Findings
- UX-1-1 | non-blocking | low | frontend | Six identical "Open" links in the desktop table have no row-specific accessible name, so a screen-reader link list is ambiguous. The board draws "Open", so keep the visible text and add a visually hidden suffix or aria-label such as "Open Bank statements". frontend/src/features/finance/month-end/MonthEndView.tsx

## Notes
- Phone cards are not tappable (as drawn, PMO-0-5), so a phone user can only reach a task through the single bottom action. Matches the board; worth a product look later.
- Screenshots were taken in the scratchpad and deleted.
