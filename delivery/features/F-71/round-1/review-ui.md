VERDICT: CHANGES
COMMIT: 3df5462d49c464d12d789486760215fb1df62304
REVIEWER: ui-reviewer
AUTHORITY: UI design reviewer

## Summary
- The fidelity gate fails on all six board and width runs. Coverage is 36% to 79% and visual is 78 to 84 (need 100% and 90). No `fidelity-exceptions.json` exists for F-71, so even the spec's accepted hides count as missing. Only the design engineer can approve that file.
- The live screens are close to the boards in type, colour, table and card surfaces and header. Both tabs, every state (empty, limited, Unknown, bad body, 500, 403/404, no-access) and both widths render without sideways scroll.
- Two visible faults of the build's own: figures break mid-amount in the Paid column on desktop, and the Money side panel shows an empty bordered strip before a figure is chosen.
- "Unknown" is a yellow tag on the Milestones tab and plain bold brown text on Money and on the boards.
- Fresh screenshots on this head (D-192) are in the session scratchpad `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/shots/` (every state at 1440 and 390) and fidelity reports in `.../scratchpad/fidelity/<board>-<width>/` (report.json, side-by-side.png).

## Findings
- UI-1-1 | blocking | high | design engineer (exceptions file) and frontend | Fidelity gate fails on every run, and there is no `delivery/features/F-71/fidelity-exceptions.json`. Expected: coverage 100% after approved exceptions, visual >= 90. Actual (P-0101, finance_lead for Money, pm for Milestones): SCR-12 desktop 1440 coverage 55.1% (27/49), visual 83.4, missing 22, moved 5, extra 11; SCR-12 mobile 390 coverage 36.4% (8/22), visual 82.0; SCR-38 desktop 1440 coverage 65.1% (28/43), visual 81.9, missing 15, moved 5; SCR-38 desktop-changed 1440 coverage 78.6%; SCR-38 mobile 390 coverage 59.1% (13/22), visual 79.1; SCR-38 mobile-changed 390 coverage 75% (3/4), visual 81.1. Frontend must list each spec-accepted hide (spec "Conflicts with the boards" 1 to 7) and the other differences below as exception proposals, and the design engineer approves them; then rerun. Visual below 90 stays blocking even then, and the table and cards need the fixes in UI-1-2 to UI-1-4 to close it.
- UI-1-2 | blocking | medium | frontend | Money tab, desktop 1440: the Paid column breaks figures in the middle ("Paid NGN / 2,000,000.00 · Owed / NGN 500,000.00"), separating the currency code from the amount and making Paid and Owed figures hard to pair. The board shows one short value per row. Keep each "<code> <amount>" unbroken (no-wrap on the figure, one "Paid ... · Owed ..." pair per line) or give the column more width. The same wrapping appears in the Milestones table PAID column (kick-off row). Path: `src/features/projects/MoneyCells.tsx`, `money.css`, `project-tabs.css`.
- UI-1-3 | blocking | low | frontend | Money tab, desktop: before a figure is chosen the right panel is a blue header strip "Choose an amount to see where it comes from." followed by an empty bordered box. The board's panel has a header and body content. An empty body strip reads as a broken panel. Show the prompt as the panel body with no empty second box (`shots/money-limited-1440.png`). Path: `money.css`.
- UI-1-4 | blocking | low | frontend | "Unknown" is drawn two ways: the board and the Money tab use bold brown text; the Milestones tab (desktop CONTRACT AMOUNT and PAID, and phone cards) uses a yellow filled tag. The board SCR-38 shows plain bold brown "Unknown". Use the same treatment as Money and the board. Path: `src/features/projects/MilestonesTab.tsx`, `project-tabs.css`.
- UI-1-5 | non-blocking | low | frontend | Amounts read `NGN 3,000,000.00` where the boards draw `₦3,000,000`. The spec's acceptance criterion requires the currency code from the item, so this is intended, but it is a board difference and must be in the exceptions file (UI-1-1).

## Notes
- Accepted hides, not findings: report title and Chidi card, "figures differ" check, paid word and worked owed, composed invoice status, `amount_note`, "Mark milestone N complete", change text as a link.
- Tab counts (Milestones 4, Documents 6 and so on) and the breadcrumb on the Money board come from the shared project header (F-70), not this feature.
- Items the build adds beyond the boards and are spec-approved (limited callout, Due line, stacked invoices, non-stage rows, Recorded completions, no-access line) use existing surfaces, tokens and spacing and look at home. The limited callout is readable.
- No sideways scroll on either tab at 390 or 1440 in any state checked. Phone cards match the board's card style. The phone figure sheet opens as a bottom sheet with a close button.
- Error cards (bad body, 500) use the shared error card; on Milestones two cards stack (milestones and completions), each with its own Try again. Acceptable.
- The fidelity artefacts could not be copied into `round-1/fidelity/` (shell write to the project folder was refused); they remain in the scratchpad paths above.

## Verified
