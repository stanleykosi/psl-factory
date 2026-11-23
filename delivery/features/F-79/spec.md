# Month-end and the payments list read the live Finance data

> Tasks: FE-CONNECT-1. Architecture: v9 package (D-SIGNIN r2 revision on main); live contract `contracts/psl-factory.openapi.json` 1.22.0 (operations `finance_operations_company_close` = `GET /month-end`, `finance_operations_payments` = `GET /payments`). Design: approved SCR-36 and SCR-20 boards (F-10 and F-41, DONE); screens: SCR-36 Month-end, SCR-20 Payments and follow-up (list part only).

## Summary
- `/finance/month-end` reads `GET /month-end?month=&page=` (company close across workspaces): task list from `work[]`, counts from `counts` (with the new `stopped`), cash per workspace and currency, updated time from `as_of`.
- `/finance/payments` reads `GET /payments?q=&state=&cursor=`: invoice rows with billed, received and owed, the strip from `totals[]` per currency and basis, "Show more" by `cursor`.
- Unknown money is `null` (or `cash_unavailable`) and shows "Unknown", never 0, never summed into a known total. Every figure is shown with its currency and basis.
- Parts the live reads cannot fill are hidden (defaults B14 to B16 below): agent notes, next-action button, restricted-row wording, per-row tone, "received this month", "bank data to", coverage sentence, backend filter list, filter count, row count, milestone label.
- Read only. Record payment, verification, allocation, short-payment, receivables capture and the reminder workspace are out. The v7 mock serves both reads in the live shape, checked by an Ajv test against the live contract.

## Context
- Month-end: route `frontend/src/app/finance/month-end/page.tsx`; `frontend/src/features/finance/month-end/{MonthEndView.tsx, MonthEndStates.tsx, model.ts, proposal.ts, useMonthEnd.ts}`. Today it calls `api.GET('/api/v1/finance/month-end', {period})` (v7 `E-MONTH-END`) and reads `tasks`, `summary`, `cash_received_detail`, `agent_note`, `next_action`, `coverage`. Helpers to reuse: `parsePeriod`, `periodNames`, `compactAmount`, `formatClock`, `STATE_TAGS`.
- Payments: route `frontend/src/app/finance/payments/`; `frontend/src/features/finance/payments/{PaymentsView.tsx, model.ts, proposal.ts, usePayments.ts}`. Today it calls `/api/v1/finance/invoices` (v7 `E-INVOICES`) with `q`, `status`, `limit`, `cursor`. Helpers to reuse: `knownAmountText`, `formatDayMonth`, `SampleLabel`, `StateFilter`, the existing no-access and error cards.
- Mock: `frontend/mock/finance.mjs` (`monthEnd`), `frontend/mock/invoices.mjs` (`invoices`), fixtures under `frontend/mock/fixtures/finance/`, wired in `frontend/mock/server.mjs` (lines for `E-MONTH-END`, `E-INVOICES`).
- Live types: `frontend/src/api/live-schema.d.ts`, client `liveApi` in `frontend/src/api/client.ts` (as F-73 uses). Pattern for the contract test: `frontend/tests/mock-live-me.test.ts`.

## Contract
All reads use `liveApi` through `call(...)`: session cookie, same origin, no CSRF for reads, one request per page open and per "Show more" (no polling). 401 shows the existing signed-out state; 403 shows the existing no-access card (nothing about records is revealed); 404, 5xx, 503 and network failure show the existing error card with Try again. A 200 missing a required field below is `unexpected_response`.

### `GET /api/v1/month-end`
Query: `month` (`YYYY-MM`, pattern `^[1-9][0-9]{3}-(0[1-9]|1[0-2])$`), `page` (1 to 10000). The URL keeps `?period=YYYY-MM` as today; `parsePeriod` still gates it (an invalid value sends no request) and the request sends it as `month`. Pages are read with `page`; "Show more" requests `next_page` while it is non-null and appends `work[]`.
Response 200 (required): `month`, `as_of` (date-time), `workspaces[]` (max 12), `page`, `next_page` (int or null), `work[]`, `cash[]` (max 12), `more_cash_groups` (bool), `counts {done, waiting, in_progress, stopped}`.
- Task list: one row per `work[]` item `{title, workspace_id, workspace, state done|waiting|in_progress|stopped, label, at, url}`. Row shows `title`, the workspace name `workspace` as the second line, the tag with text `label` and the tone of the existing state tag for `state` (`done`, `waiting`, `in_progress` reuse `STATE_TAGS`; `stopped` reuses the existing "stopped" tone), and `at` as the time. The title links to `url` as returned when it starts with `/` (plain anchor, full navigation, because it may be a Django page); any other `url` is not linked. Rows are shown in returned order; the page never filters, sorts, counts or buckets them.
- Counts: DONE, WAITING, IN PROGRESS from `counts`, plus STOPPED from `counts.stopped`. There is no `total`: the "N of M" line is dropped and each count stands alone. A count is shown as returned; a missing count shows Unknown (never 0).
- Updated time: `UPDATED <formatClock(as_of)>` (Lagos). No coverage sentence.
- Cash received: from `cash[]` items `{workspace_id, workspace, currency, basis, amount}` and `workspaces[].cash_unavailable`. The strip cell shows the single amount when `cash[]` has exactly one item, `more_cash_groups` is false and no workspace has `cash_unavailable: true`; in every other case it reads "By project" and a list under the strip shows one line per `cash[]` item: workspace name, `compactAmount` with currency, and the basis ("gross" or "net"). A workspace with `cash_unavailable: true` (matched by `workspaces[].workspace.case_id` equal to `workspace_id`) shows a line "Unknown", never 0, and its amount is ignored even if present. An amount that is not a decimal with two places is "Unknown". The page never adds amounts across workspaces, currencies or bases. `more_cash_groups: true` adds the line "More projects are not shown here" (neutral text, no control, because live offers no way to page cash).
- Hidden: agent note, next-action button, restricted-row wording, per-row tone and detail line, receivables capture (`can_capture`, `receivables`, `stations`, `periods` are not read; they belong to `GET /projects/{case_id}/month-end`, not in this feature).
- Permission and tenant: the server returns only what the person may see. The page adds no filtering and makes no role check. Whatever restricted rows `work[]` returns (E-14) are shown as returned (title and `label`), with no invented "HR roles only" text.
- Idempotency/versioning: read only.

Screen states (SCR-36): loading (existing `LoadingState`), empty (`work: []` with all counts 0: existing empty card "Nothing to close this month" wording as built; counts still show), error (existing error card, Try again), success. The month switcher keeps working and re-reads on change; answers to a superseded month are dropped (existing behaviour in `useMonthEnd`).

Fixture, success (also the mock default):
```json
{"month":"2026-10","as_of":"2026-11-12T09:42:00Z","workspaces":[],"page":1,"next_page":2,
 "work":[{"title":"Receivables snapshot","workspace_id":"0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b10","workspace":"Kora Foods portal","state":"waiting","label":"Waiting for review","at":"2026-11-12T08:10:00Z","url":"/projects/0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b10"}],
 "cash":[{"workspace_id":"0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b10","workspace":"Kora Foods portal","currency":"NGN","basis":"gross","amount":"4700000.00"}],
 "more_cash_groups":false,"counts":{"done":2,"waiting":1,"in_progress":3,"stopped":1}}
```
Other fixtures: `cash_unavailable` workspace (cash cell "By project", that line Unknown); two currencies; `more_cash_groups: true`; a second page; empty; a month with a restricted-looking label.

### `GET /api/v1/payments`
Query: `q` (max 100), `state` (`issued|part-paid|overdue|paid|unknown`), `cursor` (1 to 1024 chars). No page size. The address keeps `?q=` and `?status=`; the request sends `status` as `state`. A `status` not in the five values sends no `state` and shows no filter chip.
Response 200 (required): `as_of` (date), `items[]` (max 25), `totals[]` (max 25), `cursor` (string or null), `limited` (bool). Item (all required): `invoice_id`, `issue_id` (int or null), `case_id`, `reference`, `workspace`, `customer`, `contract`, `currency`, `basis`, `status` (issued, part-paid, overdue, paid, voided, unknown), `label`, `records_url`, `record_payment_url`, `review_payment_url`, `reminder_url` (urls or null), `age_days` (int or null), `paid`, `owed`, `face` (decimal string or null), `reason` (string or null), `has_reminder_draft`.
- Row: reference (links to `records_url` when it starts with `/`), second line `customer · contract` (a blank part is left out; both blank reads Unknown); BILLED = `face`, RECEIVED = `paid`, STILL OWED = `owed`, each as `knownAmountText` with the currency and followed by the `basis`; `null` or a non-decimal string is "Unknown". Status chip text is `label` (tone from `status` using the existing chip tones; `voided` and `unknown` neutral); `reason`, when present, is the chip's helper text. AGE column shows `age_days` as "N days" (null is Unknown) and is not worded "overdue by" (default B15). `SampleLabel` is not shown (no `sample` in live).
- Strip: OWED TO PSL and OVERDUE each list one value per `totals[]` entry as "<amount> <basis>" with currency (for example "₦4,700,000.00 gross"); `null` is "Unknown". Entries are never added together, and no "known part + Unknown" is made (E-10). With zero entries both read Unknown. A third cell DATA DATE shows `as_of` as a day and month ("12 Nov").
- `limited: true` shows a callout above the table: "Partial result. This list and its totals may not include every invoice." (default B16; E-11 open).
- Actions per row: `reminder_url` non-null shows "Open the reminder" as a plain anchor to the returned URL (the reminder workspace belongs to lane C's line adapter; the page makes no v7 reminder or work call). `record_payment_url` and `review_payment_url` show "Record a payment" and "Review the payment" the same way. A null link shows that action disabled (`aria-disabled`, not a link) with the reason "Not available to you for this invoice" (phone: same text). `has_reminder_draft` true adds "Draft ready" beside the reminder link.
- Paging: first page on open or on a changed `q`/`status`; "Show more" requests `cursor` while non-null and appends items, keeping page 1's `totals`, `limited` and `as_of`. No row count or "N INVOICES" line.
- State filter: options come from the five contract values with plain labels (Issued, Part-paid, Overdue, Paid, Unknown) held in `model.ts`; the filter count and any backend `filters[]` are not read (default B14).
- Permission and tenant: the server decides which invoices appear; a person without access gets 403 and the no-access card. No client-side role check.
- Idempotency/versioning: read only; `cursor` is opaque and passed back unchanged.

Screen states (SCR-20): loading, empty (`items: []` with no filter: "No invoices yet"; with a filter or `q`: "Nothing matches your search and filters." and Clear filters, as built), error (Try again; a failed "Show more" keeps the rows and offers retry), success.

Fixture, success:
```json
{"as_of":"2026-11-12","limited":false,"cursor":"c2",
 "totals":[{"currency":"NGN","basis":"gross","owed":"6200000.00","overdue":null}],
 "items":[{"invoice_id":398,"issue_id":41,"case_id":"0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b10","reference":"INV-0398","workspace":"Kora Foods portal","customer":"Kora Foods","contract":"Phase 1","currency":"NGN","basis":"gross","status":"part-paid","label":"Part paid","records_url":"/projects/0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b10","record_payment_url":null,"review_payment_url":"/finance/review/41","reminder_url":"/work/new?invoice=398","age_days":9,"paid":"1500000.00","owed":"3500000.00","face":"5000000.00","reason":null,"has_reminder_draft":false}]}
```
Other fixtures: `owed: null` row (Unknown, with `basis`); `face: null`; two currencies in `totals`; `limited: true`; `age_days: null`; all three links null; `voided` row; empty; second page; error.

### Mock
`mock/finance.mjs` and `mock/invoices.mjs` serve `GET /api/v1/month-end` and `GET /api/v1/payments` in the live shape (query `month`/`page`, `q`/`state`/`cursor`; `cursor` as an opaque string such as `c2`). Existing cookie variants keep their names (`psl_mock_invoices` = board, known, unknown, contract, empty, paged, error; month-end persona and period handling as today). Personas without finance access get 403 as now. The v7 `E-MONTH-END` and `E-INVOICES` validators and the `contractBody` stripping are removed; every reply is validated against the live response schema. Other mock operations are unchanged.

## Lanes
- Frontend lane (builder): `frontend/src/features/finance/month-end/**`, `frontend/src/features/finance/payments/**`, `frontend/src/app/finance/**`, `frontend/mock/finance.mjs`, `frontend/mock/invoices.mjs`, `frontend/mock/fixtures/finance/**`, `frontend/tests/finance-month-end*.test.*`, `frontend/tests/payments*.test.*`, new `frontend/tests/mock-live-finance.test.ts`, and the matching `frontend/e2e/` specs if present.
- Backend lane: none. No backend change. E-7, E-9, E-10, E-11, E-14, E-15 and E-16 stay open in `delivery/connect/backend-questions.md`.
- Integration owner: the lane B coordinator. Checks both pages against Django 8010 (Postgres 55433) with a Finance account and a non-Finance account.
- Shared files: `src/api/**` and `src/shell/**` are lane A's; `src/features/workspace/**` is lane C's. No change is expected there; one that proves necessary (for example a type export) is a separate small commit named in `build.md`. `mock/server.mjs` is shared: change only the `E-MONTH-END` and `E-INVOICES` route wiring, as its own small commit. `src/features/finance/payments/PaymentsView.tsx` reuses `PaymentReminder` files unchanged (`payment-reminder.test.tsx` must still pass; that workspace is not touched).

## Acceptance criteria
1. Month-end calls the live path with the chosen month — verify: with the mock running, open `/finance/month-end?period=2026-10`; the request log shows `GET /api/v1/month-end?month=2026-10` and no `/api/v1/finance/month-end`; `?period=2026-13` sends no request and shows the existing "month not recognised" state.
2. Task rows come from `work[]` with label, workspace and time, and counts include Stopped — verify: page shows the fixture's rows, tags read the returned `label`, and the counts read Done 2, Waiting 1, In progress 3, Stopped 1; no "of N" total appears.
3. Show more appends the next page — verify: with `next_page: 2` the page requests `page=2`, appends rows, keeps page 1's counts; the control disappears when `next_page` is null.
4. Cash is never 0 and never summed — verify: fixture with a `cash_unavailable` workspace shows "By project" and that workspace's line reads "Unknown"; the two-currency fixture shows two lines and no combined figure; `more_cash_groups: true` shows "More projects are not shown here"; a unit test of the cash view asserts no path returns "0" or "₦0" for a missing, unavailable or malformed amount.
5. Hidden parts are absent — verify: month-end shows no agent note, no next-action button and no restricted-row text; payments shows no RECEIVED THIS MONTH, BANK DATA TO, "N INVOICES" or note panel (assert in tests).
6. Payments calls the live path — verify: `/finance/payments?q=kora&status=overdue` requests `GET /api/v1/payments?q=kora&state=overdue`; "Show more" requests `cursor=c2` and appends; `status=bogus` sends no `state`; no request goes to `/api/v1/finance/invoices`.
7. Unknown money shows Unknown with its basis — verify: the `owed: null` row shows "Unknown" in STILL OWED (not "0.00"), and the `totals[].owed` null shows "Unknown" in OWED TO PSL; known amounts show currency and basis; a two-currency `totals` shows two values, not one sum.
8. `limited` shows the partial-result callout — verify: fixture with `limited: true` shows "Partial result. This list and its totals may not include every invoice."; with `false` it is absent.
9. Action links follow the API — verify: a row with `reminder_url` shows "Open the reminder" linking to that URL; a row with null `record_payment_url` shows "Record a payment" disabled with "Not available to you for this invoice" and it is not an anchor; pressing it does nothing; no test or page code calls `/api/v1/finance/invoices/*` or `/api/v1/work` for these actions.
10. AGE is not worded as overdue — verify: the column header reads AGE and rows read "9 days"; no cell or card says "overdue by" or "days overdue".
11. Wrong user and failures — verify: persona without finance access gets 403 on both pages and shows the no-access card with no invoice or task data; 401 shows the signed-out state; mock `error` variant shows the error card, and Try again re-reads; a failed "Show more" keeps the rows and shows an inline retry; a 200 body missing `items` or `counts` shows the error card.
12. Both mock routes match the live contract — verify: `npx vitest run tests/mock-live-finance.test.ts` validates every month-end and invoices fixture and each served variant against the live `200` schemas of `/api/v1/month-end` and `/api/v1/payments` with Ajv (`strict: true`, `ajv-formats`, as `tests/mock-live-me.test.ts`), and asserts no field outside the contract is served (`additionalProperties: false`).
13. No writes — verify: grep the two feature folders for `api.POST`, `liveApi.POST`, `receipts`, `/receivables`, `/payments/` with a path parameter: none; both pages send only GET.
14. The existing design checks still pass — verify: `python3 delivery/design.py check` (run from the worktree's project root as the gate does) and the existing SCR-36 and SCR-20 fidelity checks show the same layout, with only the parts hidden by the defaults missing.
15. Against Django 8010 (integration owner, recorded in `build.md`) — verify: signed in as a Finance user, `/finance/month-end` and `/finance/payments` render the live data without console errors; as a non-Finance user both show the no-access card.

## Out of scope
- Recording a payment, reported amount, verification, allocation, the short-payment decision, financial corrections and cash lots (FE-PAYMENTS-RECEIPT, held).
- The payment reminder workspace (SCR-32) and every Finance line workspace; the reminder link only navigates.
- `GET /projects/{case_id}/month-end` and `POST .../month-end/receivables`; receivables capture is not offered and no "can capture" hint is shown.
- Any backend change, any answer to E-7, E-9, E-10, E-11, E-14, E-15, E-16, and `GET /projects/{case_id}/money` (a replacement for "received this month" is not built).
- Adding up amounts, counting rows, inferring a due date or overdue days, a row-count line, a new search box, or any v7 route for unconnected screens.
- Changing `src/api`, `src/shell` or `src/features/workspace`.

## Assumptions
- Live `url`, `records_url`, `reminder_url`, `record_payment_url`, `review_payment_url` are navigated as returned, only when they start with `/`; the sources do not say whether they are app or Django pages, so a plain anchor is the safe choice.
- `age_days` is shown as age (days since something the API does not name), because E-7 is unanswered.
- A money string that is not a two-decimal number reads Unknown rather than being printed raw, to keep Unknown from turning into a made-up figure.
- The `stopped` tone reuses the existing "stopped" tag tone, because the boards already draw it for stopped tasks.
- The month-end cash cell falls back to "By project" instead of choosing a figure when there is more than one group, to avoid summing.
- `workspaces[]`, `periods`, `stations` and `receivables` in the month-end body are validated by the mock but not shown, since they serve the per-project read.
- `voided` has no filter value in live, so it appears only as a row label under Any state.

## Conflicts with the boards
Defaults are option 1; the design engineer confirms once before the build (batched as B14 to B16 in `delivery/connect/questions-batch.md`).

- **B14. Parts the live reads do not supply.** Boards draw them; live has no source: Chidi/Tola/Zainab note and "next action" button (SCR-36); RECEIVED THIS MONTH, BANK DATA TO, coverage sentence, "N INVOICES", milestone label, filter count, Chidi's note (SCR-20); per-task tone, detail line and "HR roles only" (SCR-36); the "N of M" done line (SCR-36).
  1. (Recommended, build default) Hide them. The strip keeps OWED TO PSL and OVERDUE and gains DATA DATE; the State filter keeps working from the five contract values.
  2. Keep each as a "Not available in the live data yet" placeholder.
  3. Hide the State filter as well until the backend serves a filter list.
- **B15. OVERDUE BY column.** Board shows "9 days overdue"; live gives only `age_days`, meaning not stated (E-7).
  1. (Recommended, build default) Rename the column AGE and show "N days"; no "overdue" wording until the backend answers.
  2. Show "N days overdue" as drawn, on the reading that `age_days` counts overdue days.
  3. Hide the column.
- **B16. Partial result and the cash and totals layout.** Board has no "partial result" notice, no basis labels and a single-figure cash and owed strip; live returns per-currency, per-basis totals and a `limited` flag, and per-project cash.
  1. (Recommended, build default) Add the plain notice "Partial result. This list and its totals may not include every invoice.", show basis beside each figure, list one value per currency and basis, and show cash "By project" when it cannot be a single figure.
  2. Show only the first total per strip cell and no notice (hides data that exists).
  3. Draw the multi-value strip and cash list on the canvas first, then build.
- **B17. Disabled actions.** Board shows the reminder, record-payment and review-payment actions always on; live returns null when not allowed.
  1. (Recommended, build default) Show them disabled with "Not available to you for this invoice".
  2. Hide them when null.
