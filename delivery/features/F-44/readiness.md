DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: D-PAYROLL-VISIBILITY
REVIEWER: readiness

## Summary
- **BU totals are payroll data.** All 14 SCR-57 boards are the staff mode. The header reads "Staff cost by business unit · October". The source is the payroll staff match PAY-0010 (source-review board, "Payroll staff match · Oct | Payroll PAY-0010 | NEEDS YOU"). Every figure on the boards comes from that restricted match: 136 staff, 6 BUs, "Legal (2 people)", staff count and staff cost per BU. No Event-mode board is drawn. So no slice can avoid D-PAYROLL-VISIBILITY.
- **D-PAYROLL-VISIBILITY is open** (architecture/model.json:1694, revision 1, owner business owner) and it is already with PSL (delivery/OVERNIGHT-DECISIONS.md:26). The backend handoff names it as SCR-57's gate (delivery/backend-handoff/gaps-f-finance-workspaces.md:41, 141, 149). It also says that until PSL decides, "BU staff counts" and per-BU staff and cost leave HR for nobody, "not even a count" (gaps-e-finance-payroll.md:9-16). The task's `gate_ids: []` (architecture/packages/v7/delivery.md:2792) does not match this, as the handoff notes at :41. The upstream payroll import and run are also held by PSL (NIGHT-LOG-2026-11-18.md:29), and the month-end fixture shows this line as "Waiting for payroll matching" (frontend/mock/fixtures/E-MONTH-END.json:18).
- **Scoping around the hold does not give a real outcome.** With every payroll-derived value shown as `restricted`, the boards would show nothing. That fails fidelity and still guesses what Finance may see. Building the drawn figures on the mock would show Finance payroll aggregates whose visibility PSL has not decided. That is the one leak INV-RESTRICTED exists to prevent.
- **"Publish" and "receipts" send money to people outside Finance.** The totals go to the CEO and the BU heads: per-BU staff counts and staff cost, each BU head seeing only their own BU, in the app ("Only totals are sent; never names or pay"). Each recipient then confirms receipt. All of it is held, for three reasons: no decision id covers sending internal reports that contain amounts (G-C-7; I-ALERTS forbids amounts); a non-Finance recipient has no read or receipt operation (G-C-8, G-57-3); and the publisher rule is missing (G-57-7).
- Everything else is in place. SCR-57 is in the 13 Nov client approval (design/review.json:65, 109). FE-WORKSPACE-FRAME (F-17) is merged. The endpoints exist in frontend/src/api/schema.d.ts (E-WORK-ITEM, E-TASK-CLAIM/DECIDE, E-WORK-STEP, E-WORK-ACTION). I did not run `design.py check`, because this role has no shell.

## Scope
**Proposed split, once unblocked (D-64, at most 8 boards each):**
- **F-44 part 1, "the BU totals result is approved" (8 boards):** `SCR-57-{desktop,mobile}-{source-review,investigating,held,result-review}`. These cover the source and exception-rule review (approve or return, no Reject), Chidi's counts-only check, the small-group hold, and the result review (a table of BU, staff and staff cost as `money`). Nothing is sent.
- **F-44B, "totals published and received" (6 boards):** `SCR-57-{desktop,mobile}-{publish,receipts,verified}`, which is the publish step (`sends: true`), recipient receipts, the verified negatives and cancel-after-publish.

**F-44 part 1 needs, before a spec:**
1. **D-PAYROLL-VISIBILITY (PSL).** May Finance, the BU reviewer and Chidi see staff count and staff cost per BU as aggregates? That is the line's whole content (gaps-e-finance-payroll.md:14).
2. **G-SCR59-9 (backend).** Does BU totals take the payroll match or the published payroll totals? (gaps-e-finance-payroll.md:223.)
3. **G-57-1 (backend).** May a Finance reviewer approve an HR-owned match as the source at all? Only counts cross, and the row has no link.
4. **G-57-6 and G-C-1.** What "Withdraw approval" does on result-review, or whether part 1 leaves it out. Plus `steps[].verdict` for "no Reject".
5. **G-57-4 (design engineer).** The boards say 6 BUs in some places and 4 in others, and 7 recipients in some places and 6 in others. This must be settled before fixtures are written.

**F-44B also needs:** G-C-7 (a decision id for internal report delivery: in app, plus an alert with no amounts), G-C-8 and G-57-3 (the recipient's own-BU view and a `confirm_receipt` step), G-57-7 (the BU publisher rule), G-C-5 (reconcile one recipient), and the Disclosure rules and recipients value.

**Dependency when unblocked:** part 1 reuses F-33's InlineDecide, `stepVerdict`, the `steps[].verdict` overlay and the "reviewer not set" hold fixture (branch `fe-fin-schedules-income-detail-review`, head d20fd9b2, not merged; delivery/features/F-33/spec.md). The spec is written against that head, and the build waits for F-33 to merge into dlv-00. Fixtures W-41xx and T-41xx, with W-1606 and the month-end row left unchanged (F-42 precedent).

**Binding rules for any later spec (recorded now):**
- **Money.** Amounts are the backend's `money.amount` decimal strings. The page computes no total, count, sum or percentage: no `parseFloat`, `Number(`, `reduce(` or `compactAmount`. Unknown shows "Unknown", never 0.
- **Holds.** All four `finance.bu_totals.*` rules are NOT SET (frontend/mock/fixtures/setup/finance.desktop.json:269-337): staff_allocation, event_source, reviewer and disclosure. Each one holds as `setup_needed`, with no control, no reviewer named and no minimum group size invented.
- **Restricted data.** No name, staff ID or individual pay appears in any fixture. A payroll row has no link, and 403 and 404 look the same.
- **Agents.** Chidi's "counts only" is a backend guarantee, not frontend copy. Agent text is never shown as approval or publication.

**Out (always):** Event mode (no board), the payroll run itself (FE-FIN-PAYROLL-RUN, held), Setup editing, backend, OpenAPI, `architecture/**`, `src/shell/**`.

## Risk
High. This line moves payroll-derived money aggregates out of HR to Finance, and then on to the CEO and BU heads. A small-group leak or a wrong recipient would disclose individual pay, and a disclosure cannot be undone. SURFACES:
- security and auth: restricted payroll data, a per-recipient view, and the reviewer and publisher authority.
- api and contract-change: the `bu_totals` line, `steps[].verdict`, G-C-7 and G-C-8.
- product-decision: D-PAYROLL-VISIBILITY and the four unset BU rules.

Payments is not ticked, because nothing is invoiced, paid or posted.

## Questions
None asked here. D-PAYROLL-VISIBILITY is already with PSL (OVERNIGHT-DECISIONS.md:26). The backend items are listed above and in gaps-f-finance-workspaces.md:157-161.
