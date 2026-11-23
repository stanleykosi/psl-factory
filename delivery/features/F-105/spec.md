# A person uploads a management-accounts extract, sees it held with its findings, confirms its units and follows the investigation

> Tasks: FE-FIN-ACCOUNTS-INTAKE. Architecture: v9 package; contract `contracts/psl-factory.openapi.json` API 1.24.0. Design: approved 13 Nov canvas under the recorded exception in `design/review.json`; screens: SCR-53 states quarantined, units, investigating, owner-needed, setup-needed, returned (desktop and phone boards, 12 artboards, in `design/canvas/finance/project/SCR-53-*.dc.html`).

## Summary
- A new intake page for one project: pick or upload a trial balance, declare entity, period, currency and basis, submit. A file that fails checks is shown as held, with its findings and the way to a corrected file.
- A held file that needs its units gets the unit declaration (naira, thousands, millions) and a confirmation, which creates a successor submission. A clean source can then start the "Management accounts" line.
- The work page shows the investigation and its holds (investigating, owner needed, setup needed, returned for rework) from `GET /work/{id}/accounting`, through the shared line adapter from F-85.
- A corrected extract is uploaded from the returned state. Recheck reviewers and reassess are offered only where the backend allows them.
- Nothing is posted and no money moves. `ledger_posted` is always shown as "Not posted to the ledger". Review, claim, decision, publish, delivery and recovery are F-106.
- Waits on F-85 (lane C, PR #101) for `workspace/adapter.ts`, `EvidencePicker` and `evidence.ts`. The coordinator holds the builder until it is on main.

## Context
Where this lives today (lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`, main `b8542c79`):
- There is no SCR-53 route and no accounts code. `grep` for `accounting` or `finance-accounts` in `src/features` returns nothing. The Start work drawer (`src/features/start-work/*`) has no accounts line form; this feature does not add one (see Out of scope).
- Work page: `src/app/work/[id]/(item)/page.tsx` renders `WorkItemOverviewPane` (`src/features/work-item/WorkItemView.tsx`). After F-85, `panels[]` entries `{key, url}` are drawn through `adapterFor(key)` (`src/features/workspace/adapter.ts`, `weeklyReportAdapter.ts` is the reference).
- Setup pages that the holds link to exist: `/setup/rules/finance` (`src/features/setup/FinanceRulesView.tsx`) and `/setup/delegation` (`src/features/setup/DelegationView.tsx`).
- Project pages: `src/app/projects/[caseId]/(tabs)/[tab]/page.tsx`. The new intake page sits beside it.
- Shared client and mapping: `src/api/` (`call`, `liveApi`, `live-schema.d.ts`, generated from the live contract). Mock: `frontend/mock/*.mjs` (`server.mjs`, `finance.mjs`).
- Live operations (all read with `python3 delivery/connect/oa.py live <METHOD> <path> 5`): `accounting_intake_options`, `accounting_submit`, `accounting_resume`, `accounting_mapping`, `accounting_work_detail`, `accounting_work_command`, `accounting_work_upload_correction`, `intake_start`. File upload to a case: `POST /cases/{case_id}/files` (F-85 picker).

## Contract

### Routes (new)
- `/projects/[caseId]/accounts` (intake page; `caseId` is the case uuid). Entry link: a "Management accounts" action on the project's Finance area is not added; the page is reached from the work page links and by URL (see Assumptions A1).
- Work page panel `accounting` on `/work/[id]`: adapter `accountingAdapter` (key `accounting`, url `/api/v1/work/{id}/accounting`).

### Intake read
`GET /api/v1/projects/{case_id}/accounting-intake` returns `{case_revision, sources[{id,version,kind}], extracts[{id,version,kind}], submissions[{id, case_revision, status, findings[], finding_details[{code,message,field|null,line|null}], batch_id|null, source_id|null, work_id|null, can_confirm_units, successor_id|null}]}`. The page lists `submissions` newest first (highest `id` first) with their status in words. `extracts[]` are the supplied files the person may choose; `sources[]` are accepted sources (kept for the "start the line" step).
- Status words: `status` is free text from the backend. Show it as sent, in plain case-corrected wording only when it is one of the values listed in the contract; otherwise show the raw text. No state is derived from `status` other than the flags `can_confirm_units`, `successor_id`, `source_id`, `work_id`.
- A submission with `successor_id` set is "Replaced by a newer submission" and links to that submission; it is read only.
- A submission with `work_id` links to `/work/{work_id}`.

### Submit a trial balance
`POST /api/v1/projects/{case_id}/accounting-intake`, header `X-CSRFToken`.
- Body: `{case_revision, idempotency_key, reference, evidence_id, context{entity, period, currency, accounting_basis, extracted_at, completeness, control_total, source_evidence_id}}`; `correction` is not sent from this form.
- Form fields: file (EvidencePicker, uploads to `POST /cases/{case_id}/files`, giving `upload_id`), reference (text, 1 to 160), entity, period (`YYYY-MM`), currency (3 capital letters), accounting basis (text), extracted at (date and time, sent as ISO), completeness (complete, partial, unknown; no default), control total (text, optional; empty is sent as `null` and means "Not given", never `"0"`).
- `evidence_id` and `source_evidence_id` are evidence ids, not upload ids (F-85 keeps `UploadId` and `EvidenceId` distinct). The person picks the file's supplied evidence from `extracts[]` where one exists; where only an `upload_id` exists the form cannot submit and says "This file is not yet recorded as evidence" (the upload to evidence step is backend question LD-1, Assumption A2).
- `case_revision` comes from the intake read just made. `idempotency_key` is made once per attempt with `newIdempotencyKey()` and reused if the same attempt is retried after a network failure; a fresh form submit makes a new key.
- Response 201: a submission (shape above). Errors: 400 and 422 show `fields[].message` against the named field and the message at the top; 409 re-reads the intake and says "This changed while you were working. Check and submit again." (the person's inputs stay); 413, 415, 429, 503 as F-85's error mapping; 403 `csrf_failed` refreshes the session and says "Press submit again"; 401 signed-out state; 404 "This record is unavailable."
- Never retry a write automatically. A 503 or network error on submit tells the person to refresh the list before trying again, because the submission may exist.

### Held file (quarantined board)
Drawn for a submission whose `finding_details` or `findings` is non-empty and which has no `source_id`.
- Heading "The file wasn't accepted." and the plain count line from the number of findings ("{n} findings. Nothing has started."). Do not print "2 rows" or any count the response does not carry as a list length.
- Findings list: one row per `finding_details[]` item: stable `code` shown secondary, `message` as written, and "Line {line}" or "Field {field}" when present. When `finding_details` is empty but `findings[]` has strings, show each string as text. Unknown codes show their raw message; nothing is dropped.
- Next: "Upload a corrected file" opens the submit form with the entity, period, currency and basis fields kept (read only copy of what was declared is not available beyond what the person typed; the form keeps what is still on the page).
- Not drawn (D-182): the "ROW / WHAT'S WRONG / WHAT HAPPENS" table with row numbers and "Period is 2026-09, you declared 2026-10" (only strings exist) and the "File held until corrected" column.

### Units (units board)
Drawn when a submission has `can_confirm_units: true`.
- `POST /api/v1/projects/{case_id}/accounting-intake/{receipt_id}`, body `{action:'confirm_units', case_revision, unit, evidence_id, note}`; `unit` is one of the live values `major_currency`, `thousands_currency`, `millions_currency` (the board's "Naira / Thousands / Millions"). `action:'resume'` with `{case_revision}` is not built (the contract has it for a held import; Assumption A3).
- Radio group, no default. Labels "Naira" only when the currency declared is `NGN`, else "Whole units"; "Thousands" and "Millions" follow. Note (required, text). Evidence (required): a supplied evidence that shows the total in the source, chosen from `extracts[]` or the picker result (A2). The board's line "check one total against the source" is shown as the field help text.
- 200 returns the successor submission; the page then shows it, and the first one as "Replaced by a newer submission". The board's footnote "This is a new submission of the same file; the first one stays held." is drawn.
- Errors as above; 409 re-reads and keeps the form; 422 shows `fields[]`.
- Confirm is disabled until a unit, a note and an evidence are chosen, and while sending (no double send).

### Start the line
When a submission has `source_id` and no `work_id`, a "Start management accounts" button calls `POST /api/v1/work` `{line:'finance-accounts/v1', case_id, case_revision, idempotency_key, reference, intake:{source_id, adjustment_ids:[]}}` (`adjustment_ids` is empty; adjustments belong to SCR-54, Assumption A4). 200 `{work_id, state, revision, background}`; the page then links to `/work/{work_id}`. `background` is not sent. A second press with the same key returns the same work (idempotent); a 409 re-reads.

### Mapping read (shown from the work page and the intake page)
`GET /api/v1/projects/{case_id}/accounting-mappings/{mapping_id}?after_row=` returns `{id, source_id, entity, period, currency, unit, status, findings[], finding_details[], rows[{account, amount|null, source_line|null, source_evidence_id, report_line|null, origin}], has_more_rows, ledger_posted}`.
- Rows table (account, report line, amount, source line); `amount: null` shows "Not recorded", never 0. "Show more rows" appears when `has_more_rows` and requests `after_row` with the last row's `source_line` where it is a number; if the last row has no numeric `source_line` the control is not drawn and a note says "More rows exist and can't be paged from here" (A5).
- `ledger_posted` is always shown on the page as "Not posted to the ledger" when `false`. Any other value is shown as "Ledger status unknown". The unit is shown in words.
- Reached only when `mapping_id` is not null on the accounting read.

### Accounting read (investigation and holds)
`GET /api/v1/work/{work_id}/accounting` returns `{expected_revision, case_revision, state, next_action, finding, source_id, mapping_id, allocation_id, formula_id, report_version_id, publication, tasks[], calculated_at|null, review_stations[], delivery_jobs[], can_reassess, can_recheck_reviewers, can_reconcile, sources[], setup_missing[], correction|null, predecessor_id|null, successor_id|null, review_evidence[]}`. The `accounting` panel renders these sections by `state` from the work read (`GET /work/{id}`), which owns the state tag (F-85):
| State | Board | Draws |
|---|---|---|
| `processing` | investigating | Heading "Chidi is investigating the accounts." from `finding` (as sent) and `next_action`; "Calculated {calculated_at}" when not null, else nothing; mapping rows link when `mapping_id` set; "Not posted to the ledger" |
| `owner_needed` | owner-needed | Heading "No one can review." plus `finding` as sent; "Next" from `next_action`; links to `/setup/delegation` ("Open delegation") only |
| `setup_needed` | setup-needed | Heading "Calculation is held." plus `finding`; "Missing settings" = one row per `setup_missing[]` string, each with "Not set" (the strings are shown as sent); "Next" from `next_action`; link "Open Finance rules" to `/setup/rules/finance` |
| `action_needed` with `correction` not null | returned | The returned-for-rework panel below |
| any other state | none | `finding` and `next_action` only, and a link to F-106's review area is not drawn |
- Earlier versions: `predecessor_id` shows "Replaces an earlier version" and `successor_id` "Replaced by a newer version", each as a link to `/work/{id}`; null shows nothing.
- `review_stations[]`, `tasks[]`, `delivery_jobs[]`, `publication`, `review_evidence[]`: not drawn here (F-106). They are typed in the adapter and tested for shape only.
- Empty `setup_missing` in `setup_needed` shows the `finding` only (no invented list).

### Returned for rework
Drawn when `correction` is not null (state `action_needed` or the line is stopped; the field, not the state word, decides).
- Draws `correction.status_reason` as the returned reason (as sent, in quotes, no reviewer name and no date; D-182), "This run: stopped" only if the work `state` says so, and the declared scope (`entity`, `period`, `currency`, `accounting_basis`) read only.
- "Reviews already given: kept in history" is not drawn (no field says so).
- Upload form, `POST /api/v1/work/{work_id}/accounting/corrected-extract` multipart: fields `case_revision`, `head_id` (= `correction.head`), `decision_id` (= `correction.decision`), `source_evidence_id` (A6), `idempotency_key`, `reference`, `extracted_at`, `completeness`, optional `control_total`, `file`. Entered by the person: reference, extracted at, completeness, control total, file. Do not set `Content-Type` by hand. 201 returns a submission; the page shows it as in the intake list and links to its `work_id` when set. Errors as above plus 413 and 415 on the file.
- Button "Upload corrected extract" (the board's "Correct and resubmit"). It is disabled with its reason when `correction` is null.

### Commands (recheck and reassess)
`POST /api/v1/work/{work_id}/accounting` header `X-CSRFToken`.
- "Recheck reviewers": body `{action:'recheck_reviewers', expected_revision}`; shown only when `can_recheck_reviewers` is true. "Reassess": body `{action:'reassess', expected_revision, case_revision, source_id, adjustment_ids:[], reason}`; shown only when `can_reassess` is true and `source_id` is not null; `reason` required text; `adjustment_ids` is empty (A4). `expected_revision` and `case_revision` come from the last read and are passed on; a null stays null and disables the button.
- 200 `{work_id, state, revision}` then re-read. 409: re-read and say "This changed while you were working. Check and try again." No automatic retry.
- `can_reconcile` is not drawn (F-106).

### Permission and tenant rules
Every call is made as the signed-in person. A work id or case id the person cannot see answers 404 and the UI shows "This record is unavailable." with no difference between missing and not yours. `case_id` for writes is the page's own route value; `work_id` is the page's own id. No client-side role check decides access; buttons appear from backend flags only. Writes carry `case_revision` or `expected_revision` and an idempotency key where the contract has one (intake submit, line start, corrected extract). The intake commands `confirm_units`, `recheck_reviewers` and `reassess` carry revisions and are naturally idempotent against them.

### Screen states
- Intake page: loading skeleton; empty ("No trial balances submitted yet." with the form); error per F-85 mapping with Try again (read only); success list plus form.
- Accounting panel: loading, error (mapped), success by state as above; an unknown `state` shows `finding` and `next_action` only.
- Phone: each board has a phone pair; the same content in one column, form fields stacked, buttons full width; row tables become stacked cards.
- Sample data tag (CMP-16) when the work read says `sample`.

### Fixture examples (mock, Next 4990, mock 4991)
- Case `c0000000-0000-4000-8000-000000000053`: `GET .../accounting-intake` returns `case_revision: 7` and submissions:
  - `id 9001` held: `status:"held"`, `finding_details:[{code:"period_mismatch", message:"Row period 2026-09 differs from declared 2026-10", field:null, line:88}, {code:"currency_mismatch", message:"Currency USD, declared NGN", field:"currency", line:212}]`, `findings` the same two messages, `source_id:null`, `can_confirm_units:false`.
  - `id 9002` units: `status:"held"`, `can_confirm_units:true`, `finding_details:[{code:"unit_missing", message:"The amounts have no stated unit", field:null, line:null}]`, `successor_id:null`.
  - `id 9003` accepted: `source_id:501`, `work_id:null`, `findings:[]`.
  - `id 9004` legacy: `findings:["Control total did not match"]`, `finding_details:[]` (shown as text).
- Work `5301` `processing`: accounting read with `finding:"Investigating October's accounts"`, `mapping_id:61`, `calculated_at:null`, `setup_missing:[]`.
- Work `5302` `owner_needed`; `5303` `setup_needed` with `setup_missing:["Statement contract","BU metrics for allocation"]`; `5304` `action_needed` with `correction:{work:5304, head:77, decision:88, source:501, batch:12, status_reason:"Account 4105 includes October rent twice", entity:"PSL Ltd", period:"2026-10", currency:"NGN", accounting_basis:"IFRS"}`; `5305` `can_recheck_reviewers:true, can_reassess:true`.
- Mapping `61`: three rows, one with `amount:null`, `has_more_rows:true`, `ledger_posted:false`, `unit:"major_currency"`.
- Failures: submit on case `...0054` answers 409; case `...0055` answers 422 with `fields:[{name:"period", message:"Period must be YYYY-MM"}]`; work `5399` answers 404.

## Lanes
- Frontend lane (owner, all code in this feature): `frontend/src/features/accounts-intake/**` (new: intake page, forms, held and units views), `frontend/src/features/accounts-intake/accountingAdapter.ts` (adapter for key `accounting`, registered the way F-85's `weeklyReportAdapter.ts` is), `frontend/src/app/projects/[caseId]/accounts/page.tsx`, `frontend/mock/accounts.mjs` and its route entries in `frontend/mock/server.mjs`, `frontend/src/api/types.ts` (live types for these operations only), tests under `frontend/src/**` and `frontend/e2e/accounts-intake*.spec.ts`.
- Backend lane: none. No backend change. Backend question LD-1 (below) is in `delivery/connect/backend-questions.md`.
- Integration owner: lane D coordinator. Shared files and owners: `src/features/workspace/*` (lane C owns; this feature uses `adapter.ts`, `EvidencePicker`, `evidence.ts` unchanged and adds only its adapter in its own folder); `src/api/*` (shared; edits limited to these types); `src/features/work-item/*` (lane C; not touched); `src/features/setup/*` (not touched; links only).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/projects/c0000000-0000-4000-8000-000000000053/accounts` on the mock (Next 4990, mock 4991) lists the four fixture submissions newest first, with the held one showing both findings with their code, message and "Line 88" and "Line 212" — verify: open the page; `frontend/e2e/accounts-intake.spec.ts` asserts the rows.
2. The held board shows no row table with "Period is 2026-09, you declared 2026-10" wording and no "File held until corrected" column; a legacy submission with only `findings` strings shows its text — verify: DOM assertion in the e2e spec and a unit test of the findings renderer with `finding_details:[]`.
3. Submitting the form with a blank control total sends `control_total: null`, never `"0"`, and the page shows "Not given" for it — verify: unit test on the body builder and a captured mock request.
4. A submit sends `case_revision` from the latest intake read and one `idempotency_key`; a network failure then Retry reuses the same key, and a new submit makes a new one — verify: unit test with a mocked client.
5. 409 on submit shows the changed-while-working message, re-reads the list and keeps the typed values; 422 shows the field message beside `period` — verify: mock cases `...0054` and `...0055`, e2e spec.
6. A 403 `csrf_failed` does not show no-access; it refreshes the session and says to press again; a 401 shows the signed-out state — verify: unit tests as F-85 criteria 7 and 8.
7. A submission with `can_confirm_units: true` shows the unit group with no unit preselected; Confirm stays disabled until unit, note and evidence are set, and sends `{action:'confirm_units', case_revision, unit, evidence_id, note}` with `unit` one of `major_currency|thousands_currency|millions_currency` — verify: unit test and e2e on the captured request.
8. After a unit confirmation the successor is shown and the first submission reads "Replaced by a newer submission" and is read only — verify: e2e on the mock.
9. A submission with `source_id` and no `work_id` offers "Start management accounts"; pressing it sends `POST /work` with `line:'finance-accounts/v1'`, `intake:{source_id, adjustment_ids:[]}`, a `reference` and one `idempotency_key`, then links to the work page — verify: captured request in e2e.
10. `/work/5301` shows "Chidi is investigating the accounts." text from `finding`, the "Not posted to the ledger" line and no review, delivery or publish control — verify: open the page; e2e asserts those controls are absent.
11. `/work/5302` shows the `finding`, `next_action` and a link to `/setup/delegation`, and no reviewer names or reason text beyond what `finding` carries — verify: open the page; DOM assertion.
12. `/work/5303` lists "Statement contract" and "BU metrics for allocation" each marked "Not set", with the link "Open Finance rules" to `/setup/rules/finance`; when `setup_missing` is empty no rows are invented — verify: open the page and a unit test with an empty list.
13. `/work/5304` shows `status_reason` in quotes with no reviewer name or date, the declared scope read only, and an upload form; the upload sends multipart with `head_id` 77, `decision_id` 88, `idempotency_key` and the file, and no `Content-Type` header set by hand — verify: captured request in e2e and a unit test of the form-data builder.
14. "Recheck reviewers" appears only when `can_recheck_reviewers` is true and "Reassess" only when `can_reassess` is true and `source_id` is not null; reassess needs a reason; neither button appears on `/work/5301` — verify: e2e on `5305` against `5301`.
15. Mapping `61` renders three rows with the null amount as "Not recorded", "Show more rows" requests `after_row` only when the last row has a numeric `source_line`, and `ledger_posted:false` shows "Not posted to the ledger" — verify: unit test and open the page.
16. `/work/5399` and a live work id the account cannot see both show exactly "This record is unavailable." — verify: open both and compare.
17. Unknown values: an unrecognised `state` or finding code shows its raw text and nothing is dropped; a null `calculated_at`, `unit` or amount is never drawn as 0 or as a date — verify: unit tests on the adapter.
18. Against live Django (8030) with an account that may use Finance, a held-file upload, units confirmation and `GET /work/{id}/accounting` match what the page shows — verify: compare with `python3 delivery/connect/oa.py live GET /api/v1/work/{work_id}/accounting 3` and the JSON from `curl` with the session.
19. No write is sent by `accountingAdapter.commands()`; descriptors carry `case_revision` and `expected_revision` with nulls kept null — verify: adapter unit test.
20. The phone boards (width 390) show the same content in one column with no horizontal scroll for the findings, the unit group and the forms — verify: Playwright at 390 px on each state.

## Out of scope
- Review stations, claim and decide, tasks, publish, delivery jobs, publication receipts, reconcile and recovery (F-106). `review_stations`, `tasks`, `delivery_jobs`, `publication`, `review_evidence`, `can_reconcile` are not drawn.
- Boards drafting, reviews, publishing, uncertain, verified.
- Changes to `src/features/workspace` or `src/features/work-item`. If the panel registry or the work page needs one, it is a dependency on lane C.
- An accounts form in the Start work drawer; adjustments (SCR-54) and `accounting-sources/{source_id}/mappings` (preparing a note); the `resume` action.
- Reviewer names, "prepared it" and "no review rights" rows, who could review and why nobody can (not in the API; D-182).
- "3 accounts are new since September", row counts such as "412 rows", "Control total ₦0.00 · BALANCES", the "Adjustments none yet" fact, the agent card with its steps and the seven-station track (not supplied; F-85 hid the track, LC-Q1).
- "Reviews already given: kept in history" and the returning reviewer's name and date.
- Posting to the ledger; any amount calculation or unit conversion on the page; any retry that the person did not press.

## Questions
1. Investigating board: the 7-station track, agent card (steps, "Ask Chidi"), and the facts "412 rows", "Control total balances", "Adjustments none yet" have no data in API 1.24.0. Options: (1) hide them all, as F-85 did for the work page (recommended; no invented figures); (2) draw the station track statically from the line definition with the current station from `state`; (3) ask the backend for the counts and steps. Context: the board's heading, state tag and Next line remain.
2. Returned board: it quotes a named reviewer and date ("Ada Okafor returned the source on 13 Nov"). The API gives only `status_reason`. Options: (1) show the reason only, with no name or date (recommended, D-182); (2) show "Returned by a reviewer" as a neutral label; (3) ask the backend to add reviewer and returned-at. Context: avoids inventing an approver.
3. Owner-needed board: the "Who could review" table (names, prepared it, no rights) is hidden. Options: (1) show `finding` and a single "Open delegation" link (recommended); (2) show a plain sentence "A Lead must give another person Finance review rights or set a delegate" from the board; (3) hold the board. Context: the board's own sentence is product text, not API text.
4. Units board: unit labels "Naira / Thousands / Millions" are currency-specific. Options: (1) "Naira" only when declared currency is `NGN`, else "Whole units" (recommended); (2) always "Naira"; (3) show the code `major_currency`. Context: the live enum has no currency.
5. Intake page entry point: SCR-53 has no start route and the board's start is the Start work drawer (SCR-04), which has no accounts form. Options: (1) new page `/projects/[caseId]/accounts` reached from the work page and a link added by the design engineer later (recommended, smallest); (2) add the accounts line to the Start work drawer in this feature (larger, touches lane C files); (3) a "Management accounts" tab on the project page. Context: needs a board decision on where the person begins.
6. Board "Upload a corrected file" on the held board also says "or change the declared period or currency if the file is right". Options: (1) the form keeps the declared fields editable on the same page, so both paths are one form (recommended); (2) two buttons; (3) only upload. Context: the API has one submit with a context.

## Assumptions
- A1. The intake page is a new route and the project page gets no new tab or link in this feature, because no board draws the entry (Question 5).
- A2. `evidence_id` and `source_evidence_id` are chosen from the `extracts[]` the intake read supplies. The upload to evidence conversion is the F-85 proposal `fileToEvidence`, which is unconfirmed (backend question 1). Where no evidence exists the form blocks and says so. Backend question LD-1 asks which step turns an uploaded file into the evidence id these fields take.
- A3. `action:'resume'` is left unbuilt because no board draws it and nothing says when it applies.
- A4. `adjustment_ids` is `[]` on line start and reassess: adjustments come from SCR-54 and are not selectable here.
- A5. `after_row` is the last row's `source_line` when numeric, because the contract names the parameter but not its meaning; otherwise paging is not drawn.
- A6. `source_evidence_id` for the corrected extract is taken from the evidence picked in the form (default: the evidence of the original source, if the intake read supplies one); `correction.source` is a source id and is not reused as an evidence id. This is the second part of LD-1.
- A7. The `accounting` panel key and url are taken as `panels[{key:'accounting', url:'/api/v1/work/{id}/accounting'}]` for a `finance-accounts/v1` work item; if live uses another key, only the adapter registration changes.
- A8. The returned board is chosen by `correction` not null; owner-needed and setup-needed by the work `state`, as the API documents no other field.
- A9. Status words from the backend are shown as sent (capitalised); the spec adds no mapping of values it was not given.
