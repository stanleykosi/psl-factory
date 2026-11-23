DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Lane B (D-180). Connects two already-built, approved Finance screens to live API 1.22.0: SCR-36 Month-end and the SCR-20 Payments list. Only the data source changes.
- Read-only. Recording a payment, verification, allocation and the short-payment decision are out. They are multipart and multi-step, and they hold money.
- The live reads lose fields the boards use (agent note, received this month, bank-data date, filter list, count). The coordinator's standing answers apply. Design gaps are batched, and the build uses the recommended default, which is to hide the missing part. Backend gaps are built on the best contract reading and flagged.
- FE-CONNECT-1 is the task id D-180 and LANES.md prescribe, so this is the explicit exception.
- Not run here: `design.py check`, `oa.py`, and a code read beyond file names. I rely on the connection map and the F-73 answers. The builder gate must run `design.py check`.

## Scope
Binding for the spec writer. Screens SCR-36 and SCR-20 (list part only), task FE-CONNECT-1. Connection map: delivery/connect/screens-e-finance-payroll.md. Frontend: src/features/finance/month-end and src/features/finance/payments (routes `/finance/month-end` and `/finance/payments`).

In, Month-end (SCR-36):
- `GET /month-end?month=` with `page` and `next_page`. Map `work[]` (title, workspace, state done|waiting|in_progress|stopped, label, at, url) onto the task list. Map `counts` onto the summary and show the new `stopped` count. Do not invent a `total`.
- Cash comes from `cash[]` per workspace, with currency and basis. When `cash_unavailable` is set, or an amount is null, show Unknown, never 0. Show `more_cash_groups` as more to load.
- The updated time comes from `as_of` (date-time).
- The per-project reads (`GET /projects/{case_id}/month-end` and `POST .../month-end/receivables`) are not in this feature. Receivables capture is a write and is held. It is not shown as available.
- The agent note, the next-action button, the restricted-row wording and per-task tone are hidden or neutral. The live API gives no source (default).
- The question of whether restricted payroll rows are hidden for non-HR readers (E-14) is a backend question. Render whatever `work[]` returns as a label, and invent no restricted-row wording.

In, Payments list (SCR-20):
- `GET /payments` with `cursor`, `q` and `state` (issued, part-paid, overdue, paid, unknown). Items give invoice_id, issue_id, case_id, reference, customer, contract, `face`, `paid`, `owed` (decimal string or null), currency, `basis` (gross or net), `status`, `label`, `reason` and `age_days`.
- Unknown money (null) shows as Unknown. Show `basis` beside figures. Show the `limited` flag as a plain "partial result" notice. The wording is the default, and the spec states it.
- `totals[]` per currency and basis (owed, overdue, null = unknown) fills the strip. No "known part plus Unknown" split is invented (E-10).
- `age_days` is not worded as "days overdue" until E-7 is answered. The build uses the best reading and flags it in the spec and the PR, or shows it as age only.
- "Received this month", "bank data as of", the coverage sentence, Chidi's note, the milestone label, the filter count and the row count are hidden. Live has only `as_of`, which is shown as the data date.
- The reminder, record-payment and review-payment links come from `reminder_url`, `record_payment_url` and `review_payment_url`. A null link means the action is not allowed and is shown disabled with a reason. The reminder link opens the line workspace, which waits for lane C's shared line adapter. It must not call the retired v7 routes against live.

Out:
- Record payment, reported amount, verification, allocations, the short-payment decision, financial-corrections and cash-lots (FE-PAYMENTS-RECEIPT, held).
- The payment reminder workspace (SCR-32) and every Finance line workspace.
- Receivables capture, any backend change, and the v7 mock for unconnected screens. If a mock moves to the live shape, validate it against the live contract.

Backend questions (flagged, not blocking the reads): E-7, E-9, E-10, E-11 (payments) and E-14, E-15, E-16 (month-end).

## Risk
Medium. The change is read-only and conforms to boards that are already approved. It still replaces a v7 route and response with a different live shape on two built Finance pages, which is a cross-layer contract change. The null-to-Unknown rule is a correctness risk if mapped wrong, because Unknown must never become 0. The high-risk writes (payments, allocation, short-payment, receivables capture) are excluded. Surfaces: ui, api, contract-change, and product-decision for the hidden-field defaults and the `limited` and `age_days` wording. Product acceptance is required because the client sees changed pages with fewer figures.
