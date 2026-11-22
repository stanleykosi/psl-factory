<!-- Part of the connection map: see README.md. Cluster E. Written 23 Nov 2026 from live OpenAPI 1.22.0 (main 9bac3109) and the frontend at f8b28059. -->

# Cluster E: Finance and Payroll screens (SCR-09, 18, 20, 32, 36, 37, 53 to 59)

Shorthand used below. "Live" = OpenAPI 1.22.0. Live work ids are integers (v7 uses strings such as `W-2702`). Every live line-work write carries `expected_revision` (work) plus `case_revision` (project) and most carry a required `evidence_id` (a human proof) and a `reason`. v7 steps carried `expected_revision`, `idempotency_key`, optional `note`. Money is a decimal string in both; live uses `null` for unknown (no `{amount, unknown}` wrapper). Live `GET /work/{work_id}` has no `workspace`/`steps`, so every Finance line below needs its own dedicated read (named in each section). Live finance lines start through `POST /work` with `line` = `finance-schedules/v1`, `finance-ppe/v1`, `finance-forecast/v1`, `finance-ledger/v1`, `finance-bu/v1`, `finance-accounts/v1`, `finance-payroll/v1`. There is no payment-reminder work line in live: a reminder belongs to an invoice (SCR-32).

### SCR-09 · Import and reconcile (restricted payroll inputs)
**Built today:** no. Task FE-FIN-PAYROLL-IMPORT; no feature, no route.
**Live operations:** `GET/POST /projects/{case_id}/payroll/requests`, `GET/POST /projects/{case_id}/payroll/requests/{request_id}/inputs`, `GET /projects/{case_id}/payroll/requests/{request_id}/start-choices`, `GET /projects/{case_id}/payroll/{kind}/{record_id}/working-rows`, `GET/POST /work/{work_id}/payroll-operations`, `POST /work` (`finance-payroll/v1`), `GET /projects/{case_id}/hr-disclosures/snapshots/{snapshot_id}/rows`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| The payroll request: month, currency, the two providers | not built | `payroll/requests` items `{id, reference, version, period, currency, providers[]}` (paged `page`/`next_page`) | new in live |
| Which files are accepted per provider, and file formats allowed | not built | `requests/{id}/inputs` → `provider_options[{provider, formats[]}]`, `inputs[{id, provider, version, accepted, status complete\|held, codes[], created_at, replaces_input_id}]` | new in live |
| Rows per file and "problem rows" | not built | `payroll/{kind}/{record_id}/working-rows?status=all\|ready\|held` → `total, ready, held`, rows `{position, employee, component, amount, bu, codes[], findings[], ready, row_ref, data_row, quarantined, source_amount}` | new in live |
| Why a file was refused ("we expected a sheet called Inputs") | not built | `inputs[].codes[]` (codes only; no "expected / found" text) | partly |
| Which earlier file a corrected one replaces | not built | `inputs[].replaces_input_id`, upload field `replaces_input_id` | new in live |
| Continue to matching with N rows, M held | not built | `start-choices` (accepted inputs plus HR snapshots); `payroll-operations` → `stage, finding, selected{input_ids, hr_snapshot_id}, working[]` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Start a payroll run | not built | `POST /work` `{line: finance-payroll/v1, case_id, case_revision, idempotency_key, intake}`; first `POST /payroll/requests {revision, reference, metadata{entity, period, currency, providers[2], purpose}, evidence_id}` | new in live (201) |
| Upload a provider file | not built | `POST .../requests/{id}/inputs` multipart `{revision, provider, operation_key, file, source_version, extracted_at, completeness, control_total, replaces_input_id}` → 201 `{revision, input}` | new in live |
| Combine, match, build totals | not built | `POST /work/{id}/payroll-operations {action, expected_revision, case_revision, stage: combine\|match\|aggregate}` → 200 `{work_id, state, revision, record_id}` | new in live |
| Approve or return an input | not built | `POST /work/{id}/reviews {kind, subject: input\|run, subject_id, verdict approve\|return\|revoke\|approve_draft_match, operation_key, evidence_id, note}` | new in live (no `reject`) |

**Design parts the live API cannot fill:**
- "Download template": no operation returns a template file (only `provider_options.formats`).
- Per-file row counts and the problem-row table with "P-0412 appears twice" text: only counts on a record plus `codes`/`findings`; the wording is not supplied.
- The "expected sheet X, found Sheet1" message on the error board: live gives codes, no expected/found detail (likely).
- A "Reject" verdict: live payroll reviews have approve, return, revoke only (matches the board's "Payroll has no Reject").

**Live data the design does not show yet:** control total and completeness (complete / partial / unknown) on upload; `replaces_input_id` lineage; exactly two providers per request; the quarantined flag on rows.
**Effort to connect:** L. Nothing is built; two-step start (request, then inputs) and a restricted-reader access model.
**Questions for the backend:**
1. E-1: Does `inputs[].codes[]` have a published list with plain-language text (and expected / found sheet names) so the error board can be written?
2. E-2: Is there an endpoint or file for "Download template" for each `provider_options.formats` entry?
3. E-3: Which `kind` values does `payroll/{kind}/{record_id}/working-rows` accept (input, combined run, match), and who gets 403 vs 404 when not an admitted reader?

### SCR-18 · Restricted payroll matching
**Built today:** no. Task FE-FIN-PAYROLL-IMPORT; no feature, no route.
**Live operations:** `GET/POST /projects/{case_id}/payroll/name-checks`, `POST .../payroll/name-attestations`, `GET/POST .../payroll/name-checks/{comparison_id}`, `GET/POST .../payroll/questions[/{question_id}]`, `GET/POST .../payroll/reports/{publication_id}`, `GET /work/{work_id}/payroll-operations`, `POST /work/{work_id}/aggregate-receipt`, `GET .../payroll/{kind}/{record_id}/working-rows`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| HR's view: the match results per person (matched / unmatched / conflict) | not built | `payroll-operations` → `working[]` (shape not typed), working-rows `ready`/`held`; name-check `result: awaiting_source\|same\|different` | reshaped (names compared one staff ID at a time, no 136/2/2 summary) |
| Finance's view: staff cost by business unit | not built | `payroll/reports/{publication_id}` → `by_business_unit` (object), `eligible_total`, `period`, `entity`, `currency`, `receipt_id`, `can_acknowledge` | new in live |
| A name difference sent on to HR | not built | `name-checks/{id}` → `followup`, `review: response\|correction_return\|correction_reject` | new in live |
| Questions to HR on a report and the replies | not built | `payroll/questions` → `can_ask, items[], topics[], reply_options[], deferred_questions[]` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Record each side's name as held | not built | `POST name-attestations {revision, side payroll\|hr, record_id, row_key, name, source_reference}` 201 | new in live |
| Compare the two names | not built | `POST name-checks {revision, run_id, input_id, row_key}` 201 | new in live |
| Send the difference to HR | not built | `POST name-checks/{id} {revision}` 200 `{followup_id, request_id}` | new in live |
| Ask HR a question / answer / acknowledge | not built | `POST questions {revision, report_id, topic report_coverage\|business_unit_basis\|staff_source_review, operation_key}` 201; `POST questions/{id} {revision, head, action dispatched\|received\|cancelled}` or `{reply staff_basis_confirmed\|source_review_needed\|more_detail_needed}` | new in live |
| Confirm the report was received | not built | `POST /work/{id}/aggregate-receipt {publication_id}` 200, or `POST .../reports/{id} {revision}` 200 | new in live |

**Access checks documented:** name-checks `can_compare`, `can_route_difference`, `configured` and `attestation_sides` tell the page what the viewer may do. Only the named recipient may open or acknowledge a report. A Finance reader gets aggregates and questions, never rows ("without private pay rows"). Out-of-scope records answer 404, not an empty shell.
**Design parts the live API cannot fill:**
- The "136 matched, 2 unmatched, 2 conflicts, 2 held" strip and the agent note: live offers no match summary (likely, `working[]` is untyped).
- Per-person HR record text ("Left 30 Sep") and a conflict reason: live compares names only.
- "Not yet allocated: Unknown, waiting for HR" row: unknown how `by_business_unit` marks an unmatched share (object, no typed unknown).
**Live data the design does not show yet:** the topic-limited question to HR (closed topics only); `deferred_questions` and `report_check_deferred` flags; the same/different name-check result.
**Effort to connect:** L. Different model from the board (name comparison per staff ID, not a match table).
**Questions for the backend:**
1. E-4: What are the fields of `payroll-operations` → `working[]` and `hr_receipt`, and do they carry matched / unmatched / conflict / held counts?
2. E-5: In `payroll/reports/{id}` → `by_business_unit`, how is a business unit with unmatched staff shown (null, a flag, or left out), and is a staff count included?
3. E-6: Is "I didn't receive the HR snapshot, confirm receipt" (`hr_receipt`) a POST on `payroll-operations` (which action value)?

### SCR-20 · Payments and follow-up
**Built today:** partly. F-41 (done): list only. Route `/finance/payments`, `src/features/finance/payments/*`. Recording a payment and the short-payment decision are not built (FE-PAYMENTS-RECEIPT held).
**Live operations:** `GET /payments`, `GET /projects/{case_id}/money`, `GET/POST /projects/{case_id}/invoices/{issue_id}/payments`, `GET .../payments/{receipt_id}`, `POST .../reported-amount`, `POST .../verification`, `POST .../allocations`, `GET/POST .../short-payment`, `GET/POST /projects/{case_id}/financial-corrections`, `GET /projects/{case_id}/cash-lots/{lot_id}`.

**Reads**
| What the screen shows | Today (v7) | Live | Fit |
|---|---|---|---|
| Invoice rows: reference, client, project | `GET /finance/invoices` → items `invoice_id (INV-0398), reference, client, project{case_id,title}` | `GET /payments` → items `invoice_id (int), issue_id, case_id, reference, workspace, customer, contract` | renamed / reshaped |
| Billed, received, still owed | `invoiced`, `received`, `owed` `{amount,currency,unknown}` | `face`, `paid`, `owed` (decimal string or null = unknown) plus `currency`, `basis` | renamed, unknown by null |
| Status chip | `status{label,tone}` | `status` enum issued, part-paid, overdue, paid, voided, unknown, plus `label`, `reason` | reshaped (tone gone) |
| Days overdue / issued / due date | `due{date,unknown}`, `overdue{days,unknown}`, `issued_on` | `age_days` (int or null; unclear if overdue days or invoice age); no dates | reshaped, partly missing |
| Strip: owed, overdue | `totals`, `totals_detail` (known part plus Unknown) | `totals[]` per currency/basis `{owed, overdue}` (null = unknown), `limited` | reshaped (no known + unknown split) |
| Received this month, bank data as of, coverage sentence | `totals_detail.received_this_month`, `bank_data_as_of`, `coverage` | `as_of` (date); nothing else | missing in live |
| Chidi's note, milestone label, filter list, row count | `agent_note`, `milestone_label`, `filters[]`, `total` | none | missing in live |
| Open reminder / record payment / review payment | `reminder.work_id` | `reminder_url`, `record_payment_url`, `review_payment_url` (null = not allowed), `has_reminder_draft` | new in live |
| Paging and filter | `cursor`, `limit`, `q`, `status` | `cursor` (not `page`), `q`, `state` (issued, part-paid, overdue, paid, unknown); no limit, no page size | renamed |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Record a payment | v7 `POST /finance/invoices/{id}/receipts {expected_revision, amount, received_on, evidence_id, idempotency_key}` (not built in frontend) | `POST /projects/{case_id}/invoices/{issue_id}/payments` multipart `{revision, customer, amount (optional), currency, amount_basis, received_at, source, transaction_ref, locator, file}` 201 | reshaped (private statement file required) |
| Supply a missing amount later | none | `POST .../{receipt_id}/reported-amount {revision, amount, locator, reason, file}` | new in live |
| Verify, then allocate | v7 allocation composed by backend | `POST .../verification {revision, role, confirmed}`; `POST .../allocations {revision, role, amount, key, reason}` (separate steps) | new in live |
| Short-payment decision | held | `GET .../short-payment` (position, balance, `treatments`: request_proof, record_exception, reject_exception) and `POST` `{action, revision, position, allocation_id, treatment, reason}` | new in live |

**Design parts the live API cannot fill:** "Received this month" figure; "Bank data to 10 Nov" and the Unknown explanation; Chidi's note and "Open the reminder draft" wording (link exists via `reminder_url`); filter count ("Filter 1"); milestone label; the "₦500,000 short" preview before saving (the short-payment GET gives it only after a receipt exists).
**Live data the design does not show yet:** `basis` (gross including tax or net excluding tax) on every amount; `limited` flag (partial result); receipts with reported / verified / allocated kept apart; reversal and cash-lot reads (`financial-corrections`, `cash-lots/{lot_id}`); `rule` and `setup` on short-payment (PSL rule held when unset).
**Effort to connect:** M for the list (rename, null handling, drop missing parts); L for record and short-payment (multi-step, multipart).
**Questions for the backend:**
1. E-7: Is `GET /payments` item `age_days` days overdue or days since issue, and where is the due date?
2. E-8: `POST .../payments` accepts a null amount with `amount_basis: unknown`. We had asked for a receipt to be refused when its amount is unknown (G-SCR20-11); is that intended?
3. E-9: Can `GET /payments` return `received this month` and a bank-data-as-of date, or should we use `/projects/{case_id}/money`?
4. E-10: When `totals[].owed` is null, is that the whole total unknown, or can a known part plus unknown be given?
5. E-11: Does `limited: true` mean the totals exclude rows, and how should the page word it?

### SCR-32 · Payment reminder
**Built today:** yes (v7 work line `payment_reminder`, W-3801..W-3813). F-41; route `/work/{id}`; `src/features/workspace/*`. The Payments page links to it.
**Live operations:** `GET/POST /projects/{case_id}/invoices/{issue_id}/reminder`, `POST .../reminder/actions`, `GET/POST /setup/{case_id}/payment-reminder-rules`, `GET /payments`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Invoice, balance, due | `workspace` facts section `invoice` | `reminders_detail` → `reference, balance{due_date, currency, amount_basis, owed}` | moved |
| To / copy and the drafted message | text section `message`, facts `message_to` | `recipient{id,name,email}\|null`, `suggested_subject`, `suggested_message`, `history[]` (draft text per reminder) | reshaped |
| Attachment (invoice PDF) | none | `attachments[]`, `history[].attachment_url` | new in live |
| Delivery check | `recipients` section `receipt` received/not_yet/uncertain/failed | `history[].dispatch{id, mode, scheduled_for, receipt}`; `receipt{delivered, recorded_at}`; `mode manual_evidence\|synthetic_mailbox` | reshaped |
| What stops sending | `setup_needed` state | `hold` (string or null), `can_prepare`, `can_schedule`, `can_confirm` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Edit the draft | `POST /work/{id}/steps {step: edit_draft, inputs{subject,message}}` | `POST .../reminder {revision, subject, message, attachment_id, attachment_checked}` 201 | reshaped (invoice scoped, not work scoped) |
| Send / schedule | `step: send_reminder` | `POST .../reminder/actions {action, draft_id, revision, scheduled_for?}` 200 | reshaped (scheduling) |
| Set aside | `step: set_aside` | same `actions` with `reason` | reshaped |
| Confirm a delivery that could not be read | reconcile | `actions` with `{dispatch_id, evidence_id, delivered, reference}` | new in live |
| Rules (days after due, minimum days between) | Setup screen | `POST /setup/{case_id}/payment-reminder-rules` 201 (draft for independent review) | moved |

**Design parts the live API cannot fill:** "Overdue by 21 days" (only `due_date`); "Reminders sent: None yet / Last payment" (unknown stays unknown; live has `history` but no last-payment); "If there's no reply in 7 days I'll draft a second reminder" (no such value; `days_after_due` and `minimum_days_between` exist in the rules).
**Live data the design does not show yet:** `mode` (manual evidence vs synthetic mailbox); `receipt_proofs`; scheduled send time; rule settings currently null until PSL sets them.
**Effort to connect:** M. Needs a page keyed by invoice rather than work id.
**Questions for the backend:**
1. E-12: What `action` values does `reminder/actions` take (release, schedule, reconcile, close, set aside)? The spec shows `action` untyped.
2. E-13: Does the 7-day follow-up sentence come from `settings.minimum_days_between`, and is it exposed to the reader?

### SCR-36 · Month-end
**Built today:** yes. F-10 (done); route `/finance/month-end`; `src/features/finance/month-end/*` (`useMonthEnd.ts`, `model.ts`).
**Live operations:** `GET /month-end`, `GET /projects/{case_id}/month-end`, `POST /projects/{case_id}/month-end/receivables`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Month chosen | `GET /finance/month-end?period=YYYY-MM` → `period` | `GET /month-end?month=` → `month`, `page`, `next_page` | renamed, moved |
| Each month-end task and where it stands | `tasks[{line, state, where, work_id, title, detail, status_label, tone, restricted}]` | `work[{title, workspace_id, workspace, state done\|waiting\|in_progress\|stopped, label, at, url}]` | reshaped (no tone, `restricted`, detail) |
| Done / waiting / in progress counts | `summary{done,waiting,in_progress,total}` | `counts{done, waiting, in_progress, stopped}` | reshaped (`stopped` new, no `total`) |
| Cash received, known plus Unknown | `cash_received_detail{known, has_unknown}` | `cash[{workspace_id, workspace, currency, basis, amount}]` per workspace; `cash_unavailable` per `workspaces[]` entry; `more_cash_groups` | reshaped |
| Updated time | `as_of`, `coverage` | `as_of` (date-time); no `coverage` | partly |
| Agent note and next action | `agent_note`, `next_action` | none | missing in live |
| Per project close | none | `GET /projects/{case_id}/month-end` → `stations[{key,title,django_url}]`, `periods[{entity,currency,at,status,values}]`, `receivables{status,cutoff,captured_date,snapshot_id}`, `can_capture` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Capture the day's receivables | none | `POST /projects/{case_id}/month-end/receivables {month, revision}` 201 `{id, as_of, sha256, revision}` | new in live |

**Design parts the live API cannot fill:** the agent note, the "next action" button, restricted-row wording ("HR roles only"), per-task tone.
**Live data the design does not show yet:** `stopped` count; company-wide list across workspaces; receivables capture date and cutoff; `cash_unavailable` (cash not computable), so the page should show Unknown there rather than 0.
**Effort to connect:** M. Response is a different shape (company list, then per workspace).
**Questions for the backend:**
1. E-14: Does `GET /month-end` hide payroll/restricted rows for non-HR readers, and does `work[]` include restricted lines as a label only?
2. E-15: What are `periods[].values` and `status` values (open, captured, closed)?
3. E-16: Is `cash[].amount` ever null when `cash_unavailable` is true, or is it "0.00"?

### SCR-37 · Payroll corrections (restricted)
**Built today:** no. Task FE-FIN-PAYROLL-CORRECTIONS.
**Live operations:** `GET /projects/{case_id}/hr`, `GET/POST /projects/{case_id}/hr-disclosures`, `GET .../hr-disclosures/{contract_id}`, `POST .../exports`, `GET .../hr-disclosures/snapshots/{snapshot_id}/rows`, `GET .../hr-disclosures/clarifications/{task_id}`, `GET /projects/{case_id}/department-handoffs`, `GET /work/{work_id}/department-handoff`, `POST .../finance-acknowledgement`, payroll questions.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| List of correction requests and who is waiting | not built | `hr-disclosures` → `needs[]`, `disclosures[]`, `actions[]`, `proofs{}`; `{contract_id}` → `corrections[]`, `decisions[]`, `snapshots[]`, `questions[]` (item shapes untyped) | new in live |
| Which fields HR shares with Finance | not built | `{contract_id}` → `fields[]` (employee_id, bu, effective_from, role, monthly_pay, currency, gross_pay, deductions, bank_account, home_address, date_of_birth), `entity`, `period`, `current_approval_id` | new in live |
| HR export visible to the named Finance reader | not built | `snapshots/{id}/rows` → `rows[]`, `fields[]`, `completeness`, `total`, `as_of` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| HR Lead approves, returns, rejects a correction | not built | `POST /hr-disclosures {action: decide_correction, revision, request_id, verdict approve\|return\|reject, successor_id, operation_key, evidence_id}` 200 | new in live |
| Request a correction | not built | `{action: correction, ...}` (shape untyped); name differences route via `payroll/name-checks/{id}` | new in live |
| Finance confirms receipt of the HR export | not built | `POST /work/{id}/department-handoff/finance-acknowledgement`; `{action: receive, snapshot_id, operation_key, evidence_id}` | new in live |

**Access checks documented:** only the named Finance recipient may open snapshot rows; the HR role sees handoff metadata; correction reviews, private exports and questions keep separate permissions.
**Design parts the live API cannot fill:** the masked staff reference (`S-●●●41`): masking rule not stated; the "3 corrections · 2 waiting" counts; "Approved 02 Nov" decided-at text (likely `decisions[]`, shape untyped).
**Live data the design does not show yet:** HR field visibility proposals (`GET/POST /setup/{case_id}/hr-field-visibility`), which settle the open payroll-visibility decision; scope clarification tasks.
**Effort to connect:** L. Item shapes are untyped, so build needs sample responses.
**Questions for the backend:**
1. E-17: What are the fields of `hr-disclosures` `needs[]`, `disclosures[]`, `decisions[]` and `corrections[]` items?
2. E-18: Is the correction list per disclosure only, or can a project-level list of waiting corrections be read?

### SCR-53 · Management accounts
**Built today:** no. Tasks FE-FIN-ACCOUNTS-INTAKE and -PUBLISH; no route.
**Live operations:** `POST /work` (`finance-accounts/v1`), `GET/POST /projects/{case_id}/accounting-intake`, `POST .../accounting-intake/{receipt_id}`, `POST .../accounting-sources/{source_id}/mappings`, `GET .../accounting-mappings/{mapping_id}`, `GET/POST /work/{work_id}/accounting`, `POST /work/{work_id}/accounting/corrected-extract`, `POST /tasks/{task_id}/claim`, `POST /tasks/{task_id}/decision`, `POST /work/{work_id}/actions`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Where the report is (investigating, reviews, drafting, publishing, uncertain, verified) | work `state` plus `workspace` | `accounting` → `state, next_action, finding, calculated_at, review_stations[], tasks[], delivery_jobs[], publication, can_reassess, can_recheck_reviewers, can_reconcile` | new in live |
| What is missing before publish | "NOT SET" facts | `setup_missing[]` | new in live |
| Quarantined file and findings | not built | intake response `status, findings[], can_confirm_units, successor_id` | new in live |
| Mapping rows / ledger posted | not built | `accounting-mappings/{id}` → `rows[], has_more_rows, ledger_posted, unit, status, findings[]` (`?after_row`) | new in live |
| Earlier versions | not built | `predecessor_id`, `successor_id`, `correction` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Upload the extract | not built | `POST accounting-intake {case_revision, idempotency_key, reference, evidence_id, context{entity, period, currency, accounting_basis, extracted_at, completeness, control_total (null = unknown), source_evidence_id}}` 201 | new in live |
| Confirm units | not built | `POST accounting-intake/{id} {action, case_revision, unit major\|thousands\|millions_currency, evidence_id, note}` 200 | new in live |
| Upload a corrected file | not built | multipart `.../accounting/corrected-extract` 201 | new in live |
| Review / publish / recover | not built | `POST /work/{id}/accounting {action, expected_revision}` 200; reconcile via `can_reconcile`; no resend | new in live |

**Design parts the live API cannot fill:** "Row 88: period is 2026-09" table (only `findings[]` strings); "3 accounts are new since September" basis detail; the reviewers' names and why nobody can review (owner-needed list).
**Live data the design does not show yet:** `ledger_posted` (always shown so the page does not claim a posting); `delivery_jobs` per recipient; `setup_missing`.
**Effort to connect:** L. Eleven states fed by three reads.
**Questions for the backend:**
1. E-19: What are the `action` values of `POST /work/{id}/accounting`, and what is in `review_stations[]` and `tasks[]`?
2. E-20: Is `findings[]` a code list or prepared sentences?

### SCR-54 · Income detail and schedules
**Built today:** yes. F-33 (done) plus F-52 fixes; route `/work/{id}` (line `income_schedules`, W-2701..W-2712); `src/features/workspace/*` (`InlineDecide.tsx`, `proposals.ts`).
**Live operations:** `POST /work` (`finance-schedules/v1`), `GET/POST /work/{work_id}/finance-schedule`, `POST /work/{work_id}/reviews`, `GET/POST /projects/{case_id}/accounting-adjustments/{adjustment_id}`, `POST .../accounting-sources/{source_id}/mappings`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Stage, finding, what Chidi found | `workspace.sections` (figures, facts), `status` | `finance-schedule` → `stage, finding, kind income\|inventory, income{entity, period, currency, report_line, rows[]}`, `result{status ready\|held, adjusted_total, parent_amount, additive_total, reclassification_total, findings[], missing_required[]}` | moved / reshaped |
| Duplicates held | `held` fixture | `duplicates[]` | new in live |
| Returned rows with the reviewer's note | text section `returned` | `returned{review_id, rows[]}` | reshaped |
| Review state and allowed verdicts | `tasks[].you_can_act`, `steps[].verdict` | `review_id`, `review_verdicts[]` (approve, return, reject, revoke), `can_export` | reshaped |
| Exports | none | `exports[{id, kind additive\|reclassification, adjustment_id}]`, adjustment detail with `review_verdict` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Approve / return / reject / withdraw | `POST /tasks/{id}/decision` or steps with verdict; note only on return | `POST /work/{id}/reviews {kind, expected_revision, case_revision, target_id, verdict (incl. revoke), evidence_id, note}`; likely the variant with `target_id` | reshaped (evidence and note now required, likely) |
| Correct and resubmit (row relationship) | `step correct_and_resubmit {row_12_relationship}` | `POST finance-schedule {action, ..., schedule_id, return_id, row_key, relationship disaggregation\|reclassification\|additive}` 201 | reshaped |
| Settle a duplicate | held | `{action, schedule_id, decisions[], evidence_id, reason}` | new in live |
| Export as an adjustment | held (part 2) | `{action, kind additive\|reclassification, evidence_id}` | new in live |

**Design parts the live API cannot fill:** "Who reviews schedules: NOT SET" (no explicit field; likely `setup_needed` state); "Posted to ledger: NO" (no field on this read).
**Live data the design does not show yet:** `inventory` kind with `coverage` and `missing_required`; adjustment mapping read; review `evidence[]`.
**Effort to connect:** M. The Decide panel and fields exist; the data source and write bodies change.
**Questions for the backend:**
1. E-21: Which `reviews` variant carries a schedule approval, and is `evidence_id` required for approve?
2. E-22: How is "schedule reviewer not set" signalled on `finance-schedule`?

### SCR-55 · Fixed asset (PPE) schedule
**Built today:** yes. F-42 (done); route `/work/{id}` (line `fixed_assets`, W-3901..W-3912).
**Live operations:** `POST /work` (`finance-ppe/v1`), `GET/POST /projects/{case_id}/asset-registers`, `POST .../asset-registers/{register_id}/dates`, `GET /work/{work_id}/assets`, `GET/POST /work/{work_id}/assets/opening-proof`, `GET /work/{work_id}/assets/date-proofs/{fact_id}`, `POST /work/{work_id}/reviews`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Stage and what was found | `workspace.sections` (facts `register`, `calculation`, `held`) | `assets` → `stage, finding, register{entity, provider, currency, period_start, period_end, completeness, assets[], events[], closing_controls}` | moved / reshaped |
| Calculated depreciation schedule | table | `schedule{status ready\|held, rows[], totals, scope, ledger_posted}` or null | reshaped |
| Who may review what | `steps approve_register / approve_dates` | `review_options[{target_id, purpose register\|basis\|schedule, verdicts[]}]`, `schedule_review_id` | reshaped (adds a "basis" review) |
| Unclear dates and proof | table `unclear_dates`, text `proof` | `date_attachment_ids[]`, `date-proofs/{fact_id}` (PDF), `has_opening_attachment`, `opening_return{target_id, review_id}` | reshaped |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Capture a register | start only | `POST asset-registers {case_revision, reference, evidence_id}` 201 | new in live |
| Record delivery / in-service dates with proof | `step` with inputs | `POST registers/{id}/dates` multipart `{case_revision, evidence_id, asset_id, delivery_date, in_service_date, fraction_basis, file}` 201 | reshaped |
| Attach opening proof after a return | step | `POST assets/opening-proof` multipart `{expected_revision, case_revision, target_id, review_id, reason, file}` 201 | reshaped |
| Approve / return / reject | decision | `POST /work/{id}/reviews {kind, target_id, purpose register\|basis\|schedule, verdict approve\|return\|reject\|revoke, evidence_id, note}` | reshaped |

**Design parts the live API cannot fill:** "Chidi never reads asset values" (no guarantee in the API); the accounting-note section (only `accounting_note_id`, no text); the phone short money form.
**Live data the design does not show yet:** the separate "basis" review; `native_source_verified`; `completeness` of the register.
**Effort to connect:** M.
**Questions for the backend:**
1. E-23: What is `purpose: basis` (calculation basis review) and when is it requested versus register and schedule?
2. E-24: Where does the reader get the accounting note text from `accounting_note_id`?

### SCR-56 · Cash forecast and actuals
**Built today:** yes. F-43 (done); route `/work/{id}` (line `cash_forecast`, W-4001..W-4013, W-2004).
**Live operations:** `POST /work` (`finance-forecast/v1`), `GET/POST /work/{work_id}/forecast`, `GET/POST /work/{work_id}/forecast/actuals/{month}`, `POST .../forecast/disclosure`, `POST .../forecast/observations`, `GET .../forecast/observations/{observation_id}`, `POST .../forecast/lifecycle`, `POST /work/{work_id}/actions`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Forecast months and figures | `workspace.sections` (table `forecast`, figures `january`, `payroll`, `milestones`) | `forecast` → `stage, finding, audience internal\|management\|group, result{...}, jobs[], disclosure, matches[], review_roles[]` (item shapes untyped) | moved |
| Actuals for a month | table `receipts` | `forecast/actuals/{month}` → `rows[], actuals[], history[], more_actuals, more_history` | reshaped |
| Delivery to the recipient and uncertain state | `recipients`, `effect_uncertain` | `jobs[]`, `observation{...}`, `can_restart`, `restart_policy_id` | reshaped |
| Group version rows | held | `disclosure{...}` | reshaped |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Approve / return / reject / withdraw / post | `steps` with tasks | `POST forecast {action, scenario_id, run_id, role, verdict approve\|return\|reject, evidence_id, reason}` 201; other actions for withdraw and post | reshaped (role, evidence and reason needed) |
| Record an actual and match it | held | `POST forecast {action, item_key, actual_id, amount, operation_key, evidence_id}`; `POST actuals/{month}` leave unmatched `{item_key, actual_id, reason}` 201 | new in live |
| Group disclosure rows and recipients | `group-rows` fixture | `POST forecast/disclosure {run_id, rows[], fields[], metadata[], recipients[], reviewer_roles[], publisher_roles[], ...}` 201 | reshaped |
| Record what happened to an uncertain delivery | `step` | `POST forecast/observations` multipart `{job_id, outcome delivered\|not_delivered\|unknown, proof}` 200 | reshaped |
| Retry / cancel a job | none | `POST forecast/lifecycle {action, job_id, operation cancel\|retry, reason}` 200 | new in live |

**Design parts the live API cannot fill:** the "reviewer not set" sample warning (field unknown); shortened money on phone ("₦12.4M").
**Live data the design does not show yet:** disclosure fields chosen (kind, amount, expected_on, original_due, commitment, residual, matched); an `unknown` delivery outcome as a choice.
**Effort to connect:** L. Several write variants and untyped sections.
**Questions for the backend:**
1. E-25: What are the shapes of `forecast` → `result`, `jobs[]`, `disclosure`, `matches[]`?
2. E-26: Do payroll rows in a group disclosure respect the restricted-payroll visibility (HR-only) before a group reviewer sees them?

### SCR-57 · Business-unit totals
**Built today:** no. F-44 BLOCKED (waiting on PSL); no route.
**Live operations:** `POST /work` (`finance-bu/v1`), `GET/POST /projects/{case_id}/business-unit-intake`, `GET/POST /work/{work_id}/business-units`, `POST /work/{work_id}/reviews`, `POST /work/{work_id}/aggregate-receipt`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Inputs and review gates | not built | `business-units` → `stage, finding, inputs, result, review_subjects[], proofs[], can_publish, can_correct, recipient_only` | new in live |
| Totals by business unit | not built | `totals`, `period`, `currency` (null until a result exists) | new in live |
| Published and received | not built | `publication_id`, `receipt_id`, `receipt_ids[]`, `verified_at` | new in live |
| Payroll staff match the BU totals depend on | not built | `business-unit-intake` → `payroll[]`, `events[]`, `rules[]`, `comparisons[]` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Supply the source events | not built | `POST business-unit-intake {case_revision, reference, operation_key, scope, export{source, unit, completeness, control_total, rows[]}}` 201 `{accepted, findings}` | new in live |
| Publish / correct | not built | `POST business-units {action, expected_revision, case_revision, ...}` 201 | new in live |
| Review a result | not built | `POST /work/{id}/reviews` (variant with `work_id` and `purpose`) | new in live |
| Recipient confirms | not built | `POST /work/{id}/aggregate-receipt {publication_id}` 200 | new in live |

**Design parts the live API cannot fill:** the minimum-group-size number ("Legal, 2 people, blocks publishing") unless inside `result`; recipient counts ("6 BU heads").
**Live data the design does not show yet:** `recipient_only` (a reader who is only a recipient sees a reduced view).
**Effort to connect:** L; and still blocked on PSL.
**Questions for the backend:**
1. E-27: What are the fields of `business-units` → `result` and `inputs`, and where is the small-group withholding reason?
2. E-28: Which `action` values does `POST business-units` accept?

### SCR-58 · Ledger source reference
**Built today:** yes. F-45 (done); route `/work/{id}` (line `ledger_sources`, W-4201..W-4213).
**Live operations:** `POST /work` (`finance-ledger/v1`), `POST /projects/{case_id}/incumbent-evidence`, `GET/POST /work/{work_id}/incumbent-reference`, `POST .../incumbent-reference/observations`, `GET .../observations/{check_id}`, `GET/POST /projects/{case_id}/incumbent-resolutions`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| The source record being referenced | facts `source`, `evidence` | `incumbent-reference` → `source{provider, realm, entity, source_reference, transaction_date, accounting_period, incumbent_user_reference, target_reference, outcome reported_posted\|uncertain}` | moved |
| What was observed in QuickBooks | facts `recorded` | `observation`, `check_id`, `can_observe`, `has_attachment` | reshaped |
| Duplicate lineage | `duplicate` fixture | `lineage_id, predecessor_id, conflict_id`; `incumbent-resolutions` → `claims[], resolutions[]` | reshaped |
| Review and verified | `steps approve/reject` | `review_options[]` (approve, reject), `latest_decision`, `verified` | reshaped |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Record what was found with proof | `step record_observation {found, proof}` | `POST incumbent-reference {action, lineage_id, evidence_id, outcome found\|not_found\|unknown\|multiple}` 201, or multipart `.../observations` with `file` | reshaped |
| Approve or reject | decision | `{action, check_id, evidence_id, verdict approve\|reject, reason}` 201 | reshaped (reason and evidence required; no return) |
| Resolve a duplicate | none | `POST incumbent-resolutions {action, selected_id, retired_ids, mode reference_correction\|duplicate_alias, evidence_id, reason}` then a confirm/return/withdraw review | new in live |
| Recheck / restart | none | `{action: recheck\|restart, reason}` | new in live |

**Design parts the live API cannot fill:** the month-end link for ledger sources (month-end lists no ledger line); "refused, nothing was posted" wording as a state.
**Live data the design does not show yet:** `outcome` of the source (reported posted or uncertain); `posting_evidence_id`; withdrawal of the resolution.
**Effort to connect:** M.
**Questions for the backend:**
1. E-29: Do `observation` and `latest_decision` carry the reviewer's name and time, and is "not the capturer, not the observer" an independent-review reason code?

### SCR-59 · Payroll run (restricted)
**Built today:** no. Task FE-FIN-PAYROLL-RUN; no route.
**Live operations:** `POST /work` (`finance-payroll/v1`), `GET/POST /work/{work_id}/payroll-operations`, `GET /work/{work_id}/payroll-recovery`, `POST /work/{work_id}/reviews`, `POST /work/{work_id}/aggregate-receipt`, `POST /work/{work_id}/corrections`, `GET .../payroll/{kind}/{record_id}/working-rows`, `GET/POST .../payroll/reports/{publication_id}`.

**Reads**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Nine stations and where the run is | `stations` (not in live) | `payroll-operations` → `stage`, `finding`; work `state` (includes `awaiting_reconciliation`, `followup_needed`, `effect_uncertain`) | reshaped |
| Inputs and their checks | not built | `selected.input_ids[]`, `working[]`, working-rows counts | new in live |
| HR snapshot received | not built | `selected.hr_snapshot_id`, `hr_receipt` | new in live |
| Published aggregate and recipient receipts | not built | `publication_id`; `reports/{id}` → `by_business_unit`, `eligible_total`, `receipt_id`, `can_acknowledge` | new in live |
| Cancelled run and its corrected successor | not built | `payroll-recovery` → `restart`, `previous_receipt` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Review each stage (input, combined set, match, totals) | not built | `POST /work/{id}/reviews {kind, subject input\|run, subject_id, verdict approve\|return\|revoke\|approve_draft_match, operation_key, evidence_id, note}` | new in live (no reject) |
| Run combine / match / aggregate | not built | `payroll-operations {action, stage}` 200 | new in live |
| Confirm the HR snapshot was received | not built | `payroll-operations {action, snapshot_id, evidence_id}` | new in live |
| Publish; withdraw and correct after publishing | not built | `{action, publication_id, evidence_id, reason}`; successor `{action, request_id, inputs, reason}` | new in live |
| Ask HR to correct from the match review | not built | `POST /work/{id}/corrections` or `payroll/name-checks/{id}` route | new in live |

**Access checks documented:** work detail, working rows and snapshot rows are for admitted readers only; the original recipient confirms through `aggregate-receipt` without reading pay rows; a successor match needs fresh independent review. Other readers get 403 or 404.
**Design parts the live API cannot fill:** "Gross pay ₦99.2M + Unknown": the report has `eligible_total` as one string, no known + unknown split; staff row counts "140, 2 held" beyond working-rows totals; "Merge rule F16" named rule (not on the read); the "Question for backend" about BU totals reading the payroll match vs publication.
**Live data the design does not show yet:** `payroll-recovery` (prior receipt), `approve_draft_match` verdict, `instruction_key` on corrected publication.
**Effort to connect:** L.
**Questions for the backend:**
1. E-30: Does `eligible_total` ever carry an unknown or excluded part, and how is it marked?
2. E-31: Which `action` values does `payroll-operations` accept, and what does `working[]` carry per station?
3. E-32: Can a BU totals run (SCR-57) read the published payroll aggregate, or the match run, as its payroll input?

## Cluster summary
- Month-end and Payments are the only built Finance pages that read a v7 route. Both are replaced by different routes: `/api/v1/month-end` plus `/projects/{case_id}/month-end` and `GET /payments`. Each loses fields the boards use (agent note, received this month, bank-data date, filter list, count).
- Live money is `null` for unknown, with `basis` (gross or net) and `currency` on every figure. Payments `totals` and Month-end `cash` have no "known part plus Unknown" shape, so that board wording has no source yet.
- The built Finance workspaces (SCR-32, 54, 55, 56, 58) lose the generic `workspace`/`steps` model: each reads its own endpoint and writes its own typed action with `case_revision`, `evidence_id` and `reason`. These screens need a new read adapter per line before any rewiring.
- Payments writes become a multi-step flow: private statement upload, then verification, then allocation, then a separate short-payment decision. Live accepts a receipt with an unknown amount, which we had asked to refuse.
- Payroll is a different model from the boards: request and two provider inputs, name-by-name comparison, reviewed aggregate for the named recipient, closed-topic questions. Matching summaries (136/2/2) and Finance BU counts are not typed. Several item shapes (`working[]`, `needs[]`, `result`) are untyped.
- Connect first: SCR-36, then SCR-20 list (smallest and already built). Then SCR-32. Hold SCR-57 (blocked) and the payroll screens until the untyped shapes and action lists are confirmed.
