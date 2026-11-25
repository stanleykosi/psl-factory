STATUS: READY
COMMIT: 75c4ba80c3ab65c945b0d1e5306d259ec78cb9f7
BUILDER: builder
LANE: full

## Summary
- `/finance/month-end` reads the live `GET /api/v1/month-end?month=` (and `page` for Show more): task rows from `work[]`, counts including Stopped from `counts`, cash per project from `cash[]` and `workspaces[].cash_unavailable`, UPDATED from `as_of`.
- `/finance/payments` reads the live `GET /api/v1/payments?q=&state=&cursor=`: billed, received and owed with currency and basis, the strip per currency and basis (OWED with "known part + Unknown", OVERDUE, RECEIVED THIS MONTH, DATA DATE), the coverage line, the partial-result notice, row actions as returned links or disabled with a reason.
- Unknown money (null, malformed, or `cash_unavailable`) shows "Unknown", never 0; nothing is added across rows, currencies, bases or projects; no client-side money calculation. Read only: no POST, no v7 route.
- The finance mock now serves both reads in the live 1.24.0 shape, every reply checked against the live contract schema with Ajv; the v7 `E-MONTH-END` and `E-INVOICES` mock operations and their `contractBody` stripping are removed.

## Changes
- `frontend/src/features/finance/month-end/`: `types.ts` (live types, replaces `proposal.ts`), `model.ts` (period, counts, `cashView`, `taskTag`, `taskHref`), `useMonthEnd.ts` (liveApi, `showMore`), `MonthEndView.tsx` (5-cell strip, cash lines, TASK / STATE / UPDATED table and phone cards, Show more with inline retry; agent note, next action and "N of M" gone), `month-end.css`.
- `frontend/src/features/finance/payments/`: `types.ts` (replaces `proposal.ts`), `model.ts` (figures, strip values, coverage, overdue text, links, parse of `status`), `usePayments.ts` (liveApi, cursor paging), `PaymentsView.tsx` (columns BILLED / RECEIVED / STILL OWED / OVERDUE BY / actions, strip, notice, State filter from the five contract values; no note panel, row count, BANK DATA TO or sample label), `payments.css`.
- `frontend/mock/finance.mjs`, `frontend/mock/invoices.mjs`, `frontend/mock/fixtures/finance/*` (new live fixtures; old v7 fixtures and `fixtures/E-MONTH-END.json` removed). Variants: month-end cookie `psl_mock_month_end` = empty, one-page, cash-unavailable, two-currency, more-cash, unnamed, zero, error; payments cookie `psl_mock_invoices` = board, known, unknown, empty, paged, limited, currencies, links, error.
- `frontend/mock/server.mjs` (own commit 10f8a0e1): the two live paths wired before the v7 route table; `E-MONTH-END` and `E-INVOICES` removed from `M1_OPERATIONS`. `normaliseProjectPath` only rewrites `/api/v1/projects/...`, so no change was needed for the two project path forms; fixture project ids use the same UUIDs as `uuidOf('P-0101')` etc.
- Tests: `tests/finance-month-end.test.tsx`, `tests/payments.test.tsx` rewritten; new `tests/mock-live-finance.test.ts` (replaces `finance-month-end-mock.test.ts` and `payments-mock.test.ts`); `tests/mock-contract.test.ts` loses the two v7 entries; `e2e/finance-month-end.spec.ts`, `e2e/payments.spec.ts` (list parts) updated. The SCR-32 reminder specs in `payments.spec.ts` are unchanged.
- Shared files: none changed (`src/api`, `src/shell`, `src/features/workspace` untouched). Mock ids: no clash; the fixtures use project UUIDs and invoice ids 388 to 402 already used by the earlier mock.

## Fixes
- none (round 1)

## Acceptance criteria
1. [x] Month-end calls the live path with the month: vitest asserts the single call `GET /api/v1/month-end?month=2026-10`; e2e asserts the request log; `?period=2026-13` and the other bad values show "This page doesn't exist" and send no month-end request.
2. [x] Rows from `work[]`, counts with Stopped, no total: Done 2, Waiting 1, In progress 3, Stopped 1; tags read the returned `label`; no "of N".
3. [x] Show more requests `page=2`, appends, keeps counts; control gone when `next_page` is null; failed Show more keeps rows and offers retry.
4. [x] Cash: unavailable workspace reads "By project" with that line Unknown (amount ignored), missing row Unknown, returned `0.00` shows a zero, two currencies are two lines with no sum, `more_cash_groups` adds "More projects are not shown here", null name reads "Project not named"; unit test asserts no path returns 0 for missing, unavailable or malformed amounts.
5. [x] No agent note, next action, detail line, restricted text, "N of M" (month-end) and no BANK DATA TO, row count, filter count, note panel (payments): asserted in tests.
6. [x] Payments live path: `?q=kora&status=overdue` sends `q=kora&state=overdue`; Show more sends `cursor=c2`; `status=bogus` sends no `state` and no chip; no `/finance/invoices` call.
7. [x] Unknown with basis: `owed: null` row shows Unknown; known amounts show currency and basis; two currencies show two values.
8. [x] OWED: "₦7,300,000.00 gross + Unknown" with "1 invoice has no known balance"; non-null owed shows alone; both null reads Unknown.
9. [x] RECEIVED THIS MONTH (November 2026) from the read; empty totals read Unknown; two currencies two values; coverage "Received this month covers 2 of 3 projects; 1 could not be read." only when `workspaces_unknown` > 0; BANK DATA TO and `last_received_at` not shown.
10. [x] `limited: true` shows the partial-result notice; absent otherwise.
11. [x] Action links: returned URLs are plain anchors (only when they start with a single `/`); null shows the action disabled (`aria-disabled`, not an anchor) with "Not available to you for this invoice" tied by `aria-describedby`; "Draft ready" for `has_reminder_draft`; no form, no POST.
12. [x] OVERDUE BY: 9 -> "9 days overdue", 1 -> "1 day overdue", 0 -> "—", null -> Unknown; no due date shown or computed.
13. [x] pm/none get the no-access card on both pages; 401 shows the signed-out state; error variant shows the error card and Try again re-reads; a 200 missing `items`, `received_this_month`, `totals` (payments) or `work`, `counts`, `cash` (month-end) shows the error card.
14. [x] `tests/mock-live-finance.test.ts`: every fixture and each served variant validates against the live 200 schemas (Ajv strict, ajv-formats, `additionalProperties: false` in the contract); also checked inside the mock on every reply.
15. [x] No writes: source scan test finds no `POST`, `receipts`, `/receivables`, `finance/invoices` or v7 route in the two feature folders; the e2e asserts only GET requests.
16. [ ] design checks: the fidelity tool was not run (lean mode, D-210). The strip now has five cells (Stopped added), the task table has columns TASK / STATE / UPDATED (workspace as the second line), and the payments table has an extra actions column; these differ from the old board layout and need the design engineer's eye.
17. [ ] Against Django 8010: not run by the builder; left to the lane B integration owner.

## Held and why
- Not built, no live source: agent notes, next-action button, month-end "N of M", per-row detail line, BANK DATA TO, backend filter list, filter count, row count, Chidi's note (spec B14).
- Record payment is only a link or its disabled form; the record payment form and the reminder workspace are out of scope.
- Design fidelity run and Django integration (AC 16, 17) not done, see above.
- Layout choices I made where the spec is silent (please check): month-end task table is TASK (title link, workspace under it) / STATE / UPDATED (`at` as "12 Nov 09:10"); the month-end empty card title is "Nothing to close this month" as the spec words it; the cash-by-project list shows under the strip (also on phone, where the strip itself stays hidden as before); payments Show more is a plain button (live has no page size, so the rows-per-page footer is not used).
- Shared bug note: none found in shared code.

## Validation
- `npx tsc --noEmit`: clean. `npx eslint . --max-warnings 0`: clean. `node --check` on `mock/server.mjs`, `mock/finance.mjs`, `mock/invoices.mjs`: ok.
- `npx vitest run` (whole suite, includes next-config, demo-mock, mock-contract, mock-live-finance, payment-reminder): 192 files, 4434 tests passed. This feature: finance-month-end 37, payments 42, mock-live-finance 28.
- Playwright on the mock at ports 4940 (app) and 4941 (mock), desktop 1440 and phone 390, `e2e/finance-month-end.spec.ts` and `e2e/payments.spec.ts`: first run 53 passed, 5 failed (axe target-size on stacked action links, and two wrong test expectations); after the fix those 8 re-ran green (58 tests in total, all passing across the two runs). The Playwright servers stopped themselves; ports confirmed free.
- `delivery/checks.sh` not run locally (CI mode needs the pushed head; the coordinator's GitHub checks cover it).
