DECISION: READY
RISK: high
SURFACES: ui, api, security, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-41 is FE-PAYMENTS. It covers the read-only Payments and follow-up list (SCR-20 default, desktop and phone) and the Payment reminder work item it links to (SCR-32, desktop and phone). That is 4 boards. Under the D-64 cap of 8, and one Finance flow (J-04: see what is owed, chase an overdue invoice), so one PR.
- What PSL is holding is the record-a-payment part only. FE-PAYMENTS-RECEIPT (SCR-20-desktop-record and SCR-20-mobile-record) has `gate_ids: ["D-RECEIPT-ALLOCATION"]`, and that decision is `open` at revision 1 (architecture/packages/v7/delivery.md:2416-2448; architecture/model.json:1781-1807). It is open because PSL has not said how a receipt is allocated, what a part payment does, or who records receipts. D14 in contracts/policy-slots.json:1137-1201 is UNCONFIGURED. FE-PAYMENTS itself has `gate_ids: []`, "Unresolved gates: none", and depends only on FE-WORKSPACE-FRAME (F-17, merged) (delivery.md:2384-2414). The coordinator's "SCR-20 held" means the record state (gaps-e-finance-payroll.md:128). The list does not need the held decision.
- The other gates are met. SCR-20 and SCR-32 are in the 13 Nov client approval, which covers the Finance canvas (design/review.json:33, 68, 109). D-89 changes only the frame. D-RECEIVABLES-VIEW (E-INVOICES, model.json:1578-1604) and D-LINE-WORKSPACE (model.json:1291-1318) are `proposed`. They count under the recorded exception (architecture/sources/decisions-2026-11-15.md:8-12, "receivables and clients", line workspace) on the same terms as F-17 to F-33: contract mock only, the backend developer may change or refuse any field, nothing is released. The M-7 gates (D-RECEIPT-ALLOCATION, D-DECISION-VARIANTS, D-RETURN, D-LINE-WORKSPACE) hold the milestone's exit, not this task.
- E-INVOICES (schema.d.ts:925-937, 6314-6461), E-WORK-ITEM, E-WORK-STEP and E-WORK-ACTION are all in frontend/src/api/schema.d.ts. The mock does not serve E-INVOICES yet, and no frontend code references it. Seven board items need additive contract proposals on a mock overlay (below). One policy value on SCR-32 (the 7-day second reminder) is not set anywhere, so it is not shown.
- I did not run `design.py check` because this role has no shell. The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a Finance person opens Payments and follow-up and sees every invoice they may see. Each row shows what was invoiced, what was received and what is still owed (Unknown where bank data is missing, never 0), its state and how overdue it is, with the backend's totals and bank-data coverage. From Chidi's note or the row, they open the reminder Chidi drafted for an overdue invoice. There they can edit it, send it, or set it aside, and they then see the delivery check. Contract mock only. Nothing reaches a client.

**Boards (4):** design/canvas/finance/project/
- `SCR-20-desktop` and `SCR-20-mobile`. Crumb "FINANCE / PAYMENTS". Summary strip: OWED TO PSL "₦7,300,000.00 + Unknown", OVERDUE, RECEIVED THIS MONTH, BANK DATA TO "10 Nov", and the coverage sentence. Search, Filter, the "State: Issued" chip and Clear all, "4 INVOICES". Table INVOICE / WORK / INVOICED / RECEIVED / STILL OWED / STATE / OVERDUE BY, with rows PART PAID, OVERDUE, BANK DATA MISSING (Unknown and Unknown) and PAID (known ₦0.00 owed). Chidi's note and "Open the reminder draft". The phone version uses cards.
- `SCR-32-desktop` and `SCR-32-mobile`. Crumb "FINANCE / PAYMENTS / INV-0391 · REMINDER", title "Payment reminder · Harmattan Bank", the consequence line "Nothing is sent until you press Send". To / Copy / Subject, the body text, the attachment, Send reminder / Edit / Not now. "This invoice" facts: Amount, Due, Overdue by, Reminders sent, Last payment. Chidi's note.

**Task, acceptance, endpoints:** FE-PAYMENTS (R-FINANCE). Frontend half of A-RECEIVABLES and A-WORKSPACE.
- E-INVOICES GET `/api/v1/finance/invoices` (q, status, client, cursor, limit). Permission is "finance.read; rows filtered by grants" (model.json:17768).
- E-WORK-ITEM GET `/api/v1/work/{work_id}`. Proposed line key `payment_reminder`, reached from the row's `reminder.work_id`.
- E-WORK-STEP POST `/api/v1/work/{work_id}/steps` for `edit_draft`, `send_reminder` (`sends: true`) and `set_aside`.
- E-WORK-ACTION reconcile after `effect_uncertain`.
- Route: the spec picks one beside `/finance/month-end` (e.g. `/finance/payments`). The boards draw no main-nav entry, so entry is by address and from links already in the response, as D-70 did for Clients.

**Reuse, not rebuild:** the F-17 workspace frame for SCR-32 (sections, facts, text, recipients with receipts, steps, consequence, uncertain lock and reconcile from F-17 D-66/D-67, phone action bar). The F-22 client-send pattern (sent-to receipts, no resend while uncertain). The F-26 money display rules and `components/format.ts`. The F-10 month-end `asOfLine` and Unknown display. The shared Table, filter panel, Tag, SampleLabel and EmptyState in `frontend/src/components/` (D-91 to D-93). Proposal readers go in `workspace/proposals.ts` or a new invoices proposals file. Fixture ids come from the W-38xx / T-38xx block (NIGHT-LOG 06:16).

**Contract proposals (mock overlay only; the builder records them in build.md for the backend developer and does not change schema.d.ts):**
- G-SCR20-1 (blocking for display): `totals_detail.{invoiced,received,owed} = {known{amount,currency}, has_unknown}`. The page shows "₦7,300,000.00 + Unknown" only from these fields. It never adds row amounts. If only the v7 `totals.owed` is sent and it is unknown, the page shows "Unknown".
- G-SCR20-2: `totals.overdue` and `totals.received_this_month` with `period`. G-SCR20-3: `bank_data_as_of` and `coverage` text. G-SCR20-4: `overdue_days` per row. The frontend never derives days overdue from `due.date`. If no value is sent, the cell shows "Unknown" for an open invoice whose due date is unknown, and "—" only where the backend says the invoice is not overdue (D-94 split).
- G-SCR20-5 `milestone_label`, G-SCR20-6 top-level `agent_note {agent, lines, work_id}`, G-SCR20-7 `filters[].group` and the applied-filter echo. Nice-to-have. Until confirmed, the WORK cell shows `client · project.title` as sent and the difference is listed.
- G-SCR32-1 (blocking for Edit): a step field `value` as the initial value of an editable text field, and `edit_draft` returning a new draft version. Send is bound to the exact version and `revision` shown.
- G-SCR32-3: an attachment item `{label, evidence_id|document_id, size_bytes}`. Until confirmed, the attachment shows only if sent and is otherwise a listed difference.
- G-SCR32-4: "Reminders sent: None yet" and "Last payment: None" render only as the backend's facts. When the last payment is not known, the page shows "Unknown", never "None".

**Out (and why):**
- `SCR-20-desktop-record` and `SCR-20-mobile-record`, E-RECEIPT, E-EVIDENCE-UPLOAD, any allocation input or short-payment preview (G-SCR20-8 to -11, -13). This is FE-PAYMENTS-RECEIPT, gated on D-RECEIPT-ALLOCATION and D14. The "Record a payment received" button on both default boards is **not rendered**. E-INVOICES sends no action for it, and the write is gated. It is a listed difference for the design engineer. The page does not draw a disabled button with frontend-written policy text.
- The short-payment decision link from the PART PAID row (G-SCR20-12). It belongs to FE-DECIDE-VARIANTS and D-DECISION-VARIANTS. The row shows the backend's state and owed amount only, and nothing suggests the shortfall is settled or written off.
- Chidi's "If there's no reply in 7 days I'll draft a second reminder" (G-SCR32-5). No configured value exists for it (no reminder key in contracts/policy-slots.json), so the fixture's agent note leaves the sentence out and the difference is listed. Who may send reminders, and copying the PM, are backend rules shown through the returned steps and recipients (gaps-e-finance-payroll.md:176-178).
- Any total, sum, balance, overdue count or tone the frontend derives. Real email sending. Backend, OpenAPI, schema.d.ts regeneration, `architecture/**`, `src/shell/**` (apart from a destination entry only if the spec shows one is needed).

## Binding rules for the spec
1. **Unknown is not zero (INV-UNKNOWN).** `unknown: true` or a missing amount shows "Unknown" in amber. It never shows as 0, blank or a dash. A known "₦0.00" is shown as sent (INV-0391 received, INV-0388 owed). Amounts are the backend's decimal strings with their currency, formatted without float conversion and not rounded on the phone.
2. **Invoices, receipts and allocations are separate (INV-FACTS).** INVOICED, RECEIVED and STILL OWED are three backend facts. STILL OWED is never computed as invoiced minus received. The state label and tone come from `status.{label,tone}`. PAID or PART PAID is never inferred from amounts.
3. **The frontend computes nothing.** That covers totals, "+ Unknown", the overdue total, days overdue, "4 INVOICES" (from `total`) and "received this month". Each comes from a response field or a proposal field, or the page shows the difference. Search and filter go to the server through `q`, `status` and `client`, never through client-side filtering of a page. Paging uses `next_cursor`.
4. **Agent work is not authority (INV-AGENT).** Chidi's notes render as agent text. The reminder is a draft until a person presses Send. Chidi's "I can't send messages to clients or change what is owed" is shown as returned.
5. **Controls only from the response (INV-ACCESS).** Send, Edit and Not now show only when the step is returned. A disabled step shows the backend's `disabled_reason` (e.g. no billing contact, G-SCR32-2). There is no role rule in the browser. A 403 and a 404 look the same and name no client or amount. Rows are whatever the backend returns for this person.
6. **Client send (external messaging).** Writes send CSRF, `expected_revision` as read and an `idempotency_key`, with one write per press and the same key on retry. On a timeout, 5xx or `effect_uncertain`, the page re-reads, shows the uncertain receipt and offers reconcile only. Send stays locked from the item's own state across reloads (F-17 D-67, INV-RESEND). "Sent" or "Delivered" appears only from `recipients[].receipt`. The mock sends nothing. A real send waits on the backend's resend refusal and idempotency (BACKEND-HANDOFF priority 1).
7. **Coverage and time.** `as_of` and the bank-data date are shown as returned. Sample data shows SampleLabel only where `sample` is set. No fixture names a real person as approver or sender beyond the board's sample names.
8. **Design (D-64, D-83, D-91 to D-95).** One fidelity run per round over the 4 boards. SCR-20 is a list, so it needs visual >= 90 with every element present after exceptions. SCR-32 is a line workspace, so D-83 applies: 100% coverage after exceptions, no fixable gap and visual >= 70, with a signed per-board waiver. Phone targets are 44px (D-92c), and links inside sentences are exempt (D-95). Axe runs at 390 and 1440.
9. **Tests.** v7-typed fixtures for: the four board rows; a page with a known part plus Unknown in the totals; every amount unknown; an empty list; a 403/404; a 500 with retry; a reminder with no send step (`disabled_reason`); send success; send `effect_uncertain` and reconcile after a reload; a stale 409; and edit producing a new version. Mock handlers validate against the schema. The request log proves no write without a press, one write per press, and no resend while uncertain.

## Risk
High. This is a money screen. A mistake here (an unknown shown as 0, an owed amount or total computed in the browser, a paid state inferred from amounts) breaks the product's core invariants (AGENTS.md; INV-UNKNOWN and INV-FACTS on E-INVOICES, model.json:17745-17768). SCR-32 also sends an email to a client, which cannot be undone. It is contained because the list is read-only, the receipt write and short-payment decision are excluded (D-RECEIPT-ALLOCATION, D-DECISION-VARIANTS, D14 UNCONFIGURED), and the send reuses the proven F-17/F-22 uncertain-send lock on the mock.

SURFACES:
- ui: 4 boards.
- api: E-INVOICES, E-WORK-ITEM, E-WORK-STEP, E-WORK-ACTION.
- security: a client-bound send with CSRF, revision, idempotency and no resend.
- external-messaging: the reminder to the client's billing contact.
- contract-change: G-SCR20-1 to -7, G-SCR32-1/-3/-4, D-RECEIVABLES-VIEW and D-LINE-WORKSPACE `proposed`.
- product-decision: the unset reminder interval, and who may send reminders and copy the PM.

PRODUCT-ACCEPTANCE is required. Finance's receivables view and client reminder flow are new to the client, and they involve money and client messaging.

## Questions
None for this feature. The record-a-payment part (FE-PAYMENTS-RECEIPT) waits on PSL for D-RECEIPT-ALLOCATION: how a receipt is allocated to invoices and stages, what a part payment does, and which role records receipts. These questions are already with PSL (OVERNIGHT-DECISIONS.md:26, COORDINATOR-HANDOFF.md:51). The backend questions at gaps-e-finance-payroll.md:150-154 and 175-178 hold the real write, not this mock build.
