# Restricted payroll inputs are imported, compared and matched live, and people without payroll access see a clear refusal

> Tasks: FE-FIN-PAYROLL-IMPORT. Architecture: v9 package (`architecture/packages/v9`, revision pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas (Finance and Payroll canvas), exceptions in `design/review.json`; screens: SCR-09 (artboards SCR-09-desktop, -mobile, -desktop-error, -mobile-error), SCR-18 (SCR-18-desktop, -mobile, -desktop-permission, -mobile-permission).

## Summary
- SCR-09 lets an admitted payroll operator create a payroll request, download the provider template, upload the two providers' files (with `replaces_input_id` for a corrected file), see which files were accepted, held or refused, and start the run.
- SCR-18 shows the match stage (combine, match, aggregate counts), the private rows to the people the API admits, the name check and HR question flows, and the recipient report. A Finance reader gets business-unit totals and questions only.
- Every control is driven by a flag the API sends (`can_compare`, `can_route_difference`, `can_ask`, `can_acknowledge`, `can_send`, ...). No client role check decides access. 403 reads "not admitted", 404 reads "not found", never an empty shell.
- Nothing the API does not supply is drawn (D-182): the per-person HR record text ("Left 30 Sep"), the conflict reason, any match summary beyond `working[].counts`, and the "expected X, found Sheet1" wording beyond E-1. A Finance reader never gets staff names, pay or staff counts.
- Waits on F-85 (lane C, PR #101) for the shared line adapter; this delays the builder start only. Risk is high (restricted payroll data); the merge goes to the design engineer's merge batch.

## Context
Lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend` at origin/main (API 1.24.0).
- Nothing payroll exists in the frontend except the Setup field-visibility editor `src/app/setup/(tabs)/payroll-visibility/page.tsx` (SCR-13, not touched). No route, feature folder or mock exists for SCR-09 or SCR-18 (`src/features/` has no payroll or finance-payroll folder; `src/features/finance/` holds `month-end` and `payments` only).
- Shared frame (lane C, not edited here): `src/features/workspace/` (`Workspace.tsx`, `Sections.tsx`, `labels.ts`, `useWorkspaceStep.ts`) and, after F-85, `adapter.ts` (`PanelRef`, `LineContext`, `LineAdapter`, `CommandDescriptor`, `makeCommand`, `registerLineAdapter`), `EvidencePicker.tsx`, `evidence.ts`, and the live `/work/[id]` page in `src/features/work-item/`.
- API client `src/api/client.ts` (`liveApi`, `call()`), live types `src/api/live-schema.d.ts`, error mapping `src/api/errors.ts` (`forbidden`, `not_found`, `csrf`, `read_limited`, `invalid`; 403 `csrf_failed` is its own kind). Upload field `src/components/FileUpload.tsx` (D-171).
- Mock `frontend/mock/server.mjs` with `mock/finance.mjs`, `mock/workspace.mjs`, `mock/session.mjs` as models. Lane B owns the payments fixtures; this feature adds new files and names any shared edit in build.md.
- Existing line specs to mirror: `delivery/features/F-101/spec.md` (adapter registered by panel key, `reviews` descriptor, hold wording).

Live operations (1.24.0, all verified in the contract):
| Operation | Shape |
|---|---|
| `GET /projects/{case_id}/payroll/requests?page` | `{revision, items[{id, reference, version, period, currency, providers[]}], next_page}` |
| `POST /projects/{case_id}/payroll/requests` | body `{revision, reference, metadata{entity, period, currency, providers[], purpose}, evidence_id}` -> 201 `{revision, request}` |
| `GET .../requests/{request_id}/inputs?page` | `{revision, request, provider_options[{provider, formats[json\|csv\|xlsx], templates[]}], inputs[{id, provider, version, accepted, status complete\|held, codes[], created_at, replaces_input_id\|null, findings[]}], next_page}` |
| `POST .../requests/{request_id}/inputs` | multipart `{revision, provider, operation_key, file, source_version?, extracted_at?, completeness? complete\|partial\|unknown, control_total?, replaces_input_id?}` -> 201 `{revision, input{..., findings[{code, message}]}}` |
| `GET .../requests/{request_id}/template?provider&format` | 200 `application/octet-stream` (the blank template); this is E-2's "Download template" operation and exists in 1.24.0 |
| `GET .../requests/{request_id}/start-choices` | `{case_revision, request, inputs[{id, provider, version}], hr_snapshots[{id, captured_at, period}]}` |
| `POST /work` | `line: finance-payroll/v1`, `intake{request_id, inputs{input_ids[], hr_snapshot_id\|null}}`, `reference`, `case_id`, `case_revision`, `idempotency_key` -> 200 `{work_id, state, revision, background}` |
| `GET .../payroll/{kind}/{record_id}/working-rows?status=all\|ready\|held&page` | `kind` is `input` or `run` (E-3). `{record_id, currency, period, status, rows[{position, employee, component, amount\|null, bu\|null, codes[], findings[], ready, row_ref\|null, data_row\|null, quarantined, has_source_amount, source_amount\|null, source_currency\|null, sources[]}], total, ready, held, next_page}` |
| `GET /work/{work_id}/payroll-operations` | `{expected_revision, case_revision, request_id, selected{input_ids[], hr_snapshot_id\|null}, stage, finding, publication_id\|null, working[{id, kind combine\|match\|aggregate, status complete\|held, codes[], counts obj\|null}], hr_receipt{snapshot_id, receipt_id\|null, can_acknowledge, proofs[]}\|null}` |
| `POST /work/{work_id}/payroll-operations` | this feature sends `{action:"working", expected_revision, case_revision, stage: combine\|match\|aggregate}` and `{action:"receive_hr", expected_revision, case_revision, snapshot_id, evidence_id}` -> 200 `{work_id, state, revision, record_id}`. `publish`, `withdraw`, `successor`, `restart` belong to F-110 |
| `POST /work/{work_id}/reviews` | payroll variant `{kind, expected_revision, case_revision, subject: input\|run, subject_id, verdict approve\|return\|revoke\|approve_draft_match, operation_key, evidence_id, note}` -> 200 `{work_id, state, revision, review_id\|null}` |
| `GET/POST .../payroll/name-checks`, `POST .../name-attestations`, `GET/POST .../name-checks/{comparison_id}` | see Contract |
| `GET .../payroll/reports/{publication_id}`, `POST` (acknowledge), `POST /work/{work_id}/aggregate-receipt` | see Contract |
| `GET/POST .../payroll/questions`, `GET/POST .../questions/{question_id}` | see Contract |
| `GET .../hr-disclosures/snapshots/{snapshot_id}/rows?page` | HR snapshot rows (`employee_id`, `bu`, dates and optional pay fields); read-only, shown only where the API admits it |

## Contract

### Routes and adapter
- Project-level route `/projects/[caseId]/payroll` (SCR-09, before and after the run starts: requests, inputs, start choices). New Next route `src/app/projects/[caseId]/payroll/page.tsx` and `.../payroll/[requestId]/page.tsx` (request detail with inputs and start). Project crumb from the project title only.
- Work-item panel: adapter key `payroll-matching` (use the real `panels[].key` from a live `finance-payroll/v1` work item if it differs, and say so in build.md) registered through F-85's `registerLineAdapter`. `read` = `GET /work/{id}/payroll-operations`. Sections: stage and finding, the three `working[]` rows, selected inputs, HR receipt, and links to the private rows and the report.
- Report and questions route `/projects/[caseId]/payroll/reports/[publicationId]` (SCR-18 Finance view) with the questions list on the same page.
- Private rows route `/projects/[caseId]/payroll/runs/[runId]` (SCR-18 HR view) reading `working-rows` with `kind=run`; input rows at `/projects/[caseId]/payroll/inputs/[inputId]` with `kind=input`.
- Commands are built with F-85's `makeCommand`. The idempotency key and revision tokens are never passed inside `inputs` (lane C rule until TECH-1-1 lands). Frame changes are a dependency on lane C; none is made here.

### SCR-09 states
| State | Rule |
|---|---|
| Loading | existing loading pattern; no table skeleton with row counts |
| Empty (no requests) | "No payroll requests yet." plus "Start a payroll request" only when the person is admitted (the first request read answered 200); a 403 shows the refusal state, not this one |
| Default (a request with inputs) | header: reference, period, currency, the two providers. One row per provider: file name is not served, so the row shows provider, version, accepted or held, `created_at`, "Replaces version N" when `replaces_input_id` is set, and the `codes[]` as the safe wording below. Rows, "problems" and a "Checked" count come from `working-rows` counts (`total`, `ready`, `held`) for that input and are shown only when that read answered 200 |
| Problem rows | the "2 rows need HR before matching can finish" table comes from `working-rows?status=held`: row (`data_row` or `position`), what is wrong (`findings[]`/`codes[]` text as served, never composed), what happens ("Held"). Staff ID and amount columns are shown only on this protected read; a `quarantined` row shows "Held" and its `source_amount` as served; an unknown amount reads "Unknown", never 0 |
| Validation (upload form) | 422 `fields[]` shown next to the field; client refuses before sending a file over `PROOF_MAX_BYTES` or a format outside the provider's `formats[]` |
| File error board (SCR-09-error) | shown when the upload answers 201 with `input.accepted: false` or a 422: the safe explanation from `provider_options[].templates[]` and `input.findings[{code, message}]`, "Nothing was imported and nothing was changed." (shown only when the response confirms the input is held or refused), "Upload again" and "Download template". The "What we expected / What we found" two-column block is drawn only from fields the API returns; if `templates[]`/`findings[]` carry no sheet names it is hidden (Questions 2) |
| Continue to matching | button "Continue to matching" appears from `start-choices`: the accepted inputs for both providers and optional `hr_snapshots`. It never reads "· 140 rows" unless a `ready` count was served for the selected inputs; the "2 held rows wait" sentence appears only with a served `held` count |
| Permission | 403 -> "You aren't admitted to payroll inputs for this project." with no data and no controls; 404 -> "This payroll record wasn't found." (see Failure journeys) |
| Error | 401 signed out with link to `/sign-in?next=`; 403 `csrf_failed` -> refresh session, "Press the button again"; 409 -> "This changed while you were working. Reload to see the latest." and the form is kept; 413, 415, 429, 503, network each plain wording with Try again, same mapping as F-85 |

### SCR-09 writes
| Action | Request | Rules |
|---|---|---|
| Create request | `POST /projects/{case_id}/payroll/requests` `{revision, reference, metadata{entity, period, currency, providers[2], purpose}, evidence_id}`. `revision` is the `revision` of the last `GET requests` read | exactly two providers; `evidence_id` comes from the evidence picker (an upload id is not an evidence id; F-85 `fileToEvidence` proposal is used only if lane C confirms it); the form shows no free-text provider names that were not offered by the API (Assumption 3). Idempotency: the request reference is the dedupe the API uses; the form disables submit while a request is in flight and a 409/422 reference clash is shown as "A request with this reference already exists." |
| Upload input | multipart `POST .../requests/{id}/inputs` with `revision`, `provider`, `operation_key` (one uuid per attempt, reused on a retry of the same attempt), `file`, optional `source_version`, `extracted_at`, `completeness` (complete, partial or unknown, default left unset), `control_total` (string, unknown stays empty), `replaces_input_id` (set only when the person picks "This replaces an earlier file") | do not set `Content-Type` by hand; refuse client-side as above; an uncertain outcome (timeout) is not retried automatically, the form says "We couldn't confirm the upload. Check the list before sending it again." and re-reads `GET inputs` |
| Download template | `GET .../requests/{id}/template?provider=<p>&format=<json\|csv\|xlsx>` | only formats in that provider's `formats[]`; saved as a file, never rendered in the page or logged; 403/404 shown as for reads |
| Start run | `POST /work` `{line:"finance-payroll/v1", case_id, case_revision (start-choices.case_revision), idempotency_key (uuid per attempt), reference, intake{request_id, inputs{input_ids, hr_snapshot_id}}}` | one input per provider required before the button is enabled (the two providers named on the request); HR snapshot optional, chosen from `hr_snapshots`; on 200 go to `/work/{work_id}` |
| Review input or run | `POST /work/{work_id}/reviews` `{kind:"payroll", expected_revision, case_revision, subject, subject_id, verdict, operation_key, evidence_id, note}` (use the `kind` value the contract's payroll variant requires; confirm against `live-schema.d.ts`) | verdicts offered: Approve, Return, Withdraw approval (`revoke`), and "Approve draft match" (`approve_draft_match`) only for the match run, each only when the read says it is allowed; there is no Reject (matches the board's "Payroll has no Reject"); the person who uploaded is not offered a verdict the API refuses (the API's 403 is shown as the person's message, not hidden) |

Safe wording for `codes[]` comes from `provider_options[]`/`findings[]`; an unknown code is shown as the raw code in a muted label, never dropped and never given invented wording.

### SCR-18 states
| State | Rule |
|---|---|
| Loading / error | as above |
| HR view default | the match station: stage and finding, then the counts from `working[]` (for kind `match`, `counts` when not null: show the keys the API names for matched, unmatched, conflict and held, each with its own number; any key not present is not drawn; `counts: null` shows "Counts aren't available yet.") and the private row table from `working-rows` with `kind=run` and the match run's id. Columns: Staff (employee), Component, Amount, Business unit (`bu`, unknown reads "Unknown"), Result. Result is derived only from `ready`, `quarantined`, `codes[]` and `findings[]` as served; "Matched / Unmatched / Conflict" labels appear only where the API labels them in `codes[]` (Questions 3) |
| Name check | `GET name-checks`: shown only when `configured` is true; "Compare the two names" appears for a row only when `can_compare` is true; "Send the difference to HR" only when `can_route_difference` is true and the check's `result` is `different`; the attest controls appear per `attestation_sides` (a side not listed is not offered). Result words: awaiting_source "Waiting for the other side's name", same "Names match", different "Names differ". `review` and `followup` shown as "Sent to HR" / "HR replied" / "HR returned the correction" / "HR rejected the correction" per `review` |
| HR receipt | `hr_receipt` non-null and `can_acknowledge` true: "Confirm HR snapshot received" (`action: receive_hr`, with `snapshot_id` and `evidence_id`); `can_acknowledge` false or `hr_receipt` null: nothing, with no "not received" claim |
| Finance view default (permission board) | `GET payroll/reports/{publication_id}`: heading "<period> staff costs by business unit", one row per key of `by_business_unit` with its served amount, then "Total (eligible)" = `eligible_total`. No staff count column (E-5: the API gives none). A business unit the API does not list is not invented; an "Not yet allocated" row is drawn only when the API names one (Questions 1). The "Individual pay is restricted" note is always shown on this view. If `can_acknowledge` is true, a "Confirm you received this report" button is shown (POST report, `{revision}`); otherwise no button and no unacknowledged warning |
| Questions | `GET payroll/questions`: if `can_ask` is true, "Ask HR a question" with a closed `topics[]` select (no free text); each `items[]` row shows its `question`, `state`, `reply` (when set) and only the buttons its flags allow (`can_send` -> "Send to HR", `can_cancel` -> "Cancel question", `can_answer` -> one button per `reply_options[]`, `can_receive` -> "Mark as received"). `deferred_questions` ids and `report_check_deferred` show "Waiting for the report check" |
| Empty questions | "No questions yet." only when `can_ask` is true; otherwise nothing |
| Permission board | see Failure journeys |

### SCR-18 writes
| Action | Request |
|---|---|
| Run a stage | `POST /work/{id}/payroll-operations` `{action:"working", expected_revision, case_revision, stage}`; button per stage only while the readback `stage` shows that stage is next; answers 200 `{state, revision, record_id}`; the page re-reads `payroll-operations` |
| Attest a name | `POST name-attestations` `{revision, side, record_id, row_key, name, source_reference}` -> 201; `side` is limited to `attestation_sides` |
| Compare names | `POST name-checks` `{revision, run_id, input_id, row_key}` -> 201 `{id, result}` |
| Send difference to HR | `POST name-checks/{comparison_id}` `{revision}` -> 200 `{followup_id, request_id, revision}` |
| Ask a question | `POST questions` `{revision, report_id, topic, operation_key}` -> 201 |
| Act on a question | `POST questions/{id}` `{revision, head, action: dispatched\|received\|cancelled}` or `{revision, head, action:"answered", reply}` (confirm the literal action for a reply against the contract; the variant sends `reply` with `action`) -> 200 `{revision, head, state}` |
| Acknowledge the report | `POST payroll/reports/{id}` `{revision}` -> 200 `{receipt_id, revision}`, or `POST /work/{id}/aggregate-receipt` `{publication_id}` when the page is the work item; the report page uses the first; the two are never both sent for one press |
| Receive HR snapshot | `POST payroll-operations` `{action:"receive_hr", expected_revision, case_revision, snapshot_id, evidence_id}` |

Every write sends the current `revision` / `expected_revision` and `case_revision` as last read, a fresh uuid `operation_key` / `idempotency_key` per attempt where the body has one, and disables its button while in flight. A 409 shows the stale message and keeps the person's input; the page re-reads, it does not retry silently. Null tokens stay null (unknown, never 0).

### Failure journeys (people without payroll access)
Access is enforced by the API per record. The page never decides it, never calls a payroll route "just to see", and never renders a row it did not receive.
1. **Admitted workspace reader without the payroll grant (403).** Opening `/projects/{caseId}/payroll`, an input or run rows route, or a report: the page shows one block, "Payroll is restricted. You aren't admitted to this payroll record." with a link back to the project. No table, counts, file names, provider names, button, "ask HR" control or section heading that implies content. This is the permission board's intent (it draws the Finance view; the refusal itself is not drawn, see Questions 1).
2. **Invisible workspace or absent record (404).** "This payroll record wasn't found." No difference in wording or layout between a missing record and one the person cannot see, and no hint of whether it exists.
3. **Finance reader (admitted for aggregates).** The report page loads (200) with totals and questions only. The `working-rows`, `name-checks` and `hr-disclosures/snapshots/.../rows` routes are never requested by this view; if a deep link to them is opened, the 403/404 journeys above apply and the page shows nothing from a cache.
4. **A report that is not for this person.** A non-recipient opening a report gets the API's 403/404 and the same two states; "Confirm you received this report" appears only for `can_acknowledge: true`.
5. **Signed out (401).** Sign-in link with `next=`; no payroll content stays on screen.
6. **Partial: rows read answers 403 while counts read answers 200.** The counts shown are exactly what the 200 read returned; the row area shows the refusal block. Never infer counts from an unreadable row set.
7. **Provider failure (503/`read_limited`, network, or upload 5xx).** Plain wording with Try again; an upload failure never says "uploaded" and never retries by itself.

Leak controls (apply to every journey):
- Staff names, staff IDs, amounts and business-unit pay values are only held in the component state of the protected page that fetched them. They are not written to logs, `console`, error messages, toasts, analytics, the URL (path or query string), `localStorage`/`sessionStorage`, a service worker, or the React Query/SWR cache key; row-level reads are not cached across sessions or users (`cache: 'no-store'`, or a query cache entry removed on unmount and on sign-out). The `row_key`/`row_ref` appear only in request bodies, never in a URL.
- Error text from a payroll call shows the API `message` only for 422 field errors on the person's own form; it is never interpolated with a row, name or amount. An error boundary around these routes renders the plain refusal or "Try again" and does not print the thrown value.
- The mock serves rows only for the admitted persona; it serves 403 for the Finance persona on rows routes, so a missing guard fails a test rather than leaking a fixture.

### Fixture examples (mock, ids are the builder's to number; the shapes are the contract)
- Request `PAY-0010`, period `2026-10`, currency `NGN`, providers `["Payroll provider", "HR system"]` (names are fixture values).
- Input A: `accepted: true, status: "complete", codes: []`; input B: `accepted: true, status: "held", codes: ["row_held"]`; input C: `accepted: false, codes: ["sheet_missing"], findings: [{code: "sheet_missing", message: "..."}]`.
- Working rows: one ready row, one held row with `amount: null`, one `quarantined` row with `source_amount` and `bu: null`.
- `payroll-operations`: stage `match`, `working[]` with a `combine` complete, a `match` held with `counts` `{matched: 136, unmatched: 2, conflict: 2, held: 2}` (key names from the live mock of a real response, to be confirmed; fixture names are not a contract), an `aggregate` absent; one fixture with `counts: null`; one with `hr_receipt{can_acknowledge: true}`.
- Name check: `{configured: true, can_compare: true, can_route_difference: false, attestation_sides: ["payroll"]}`; and one `configured: false`.
- Report: `by_business_unit: {"Delivery": "31200000.00", "Design": "12900000.00"}`, `eligible_total: "44100000.00"`, `can_acknowledge: true`; another with `can_acknowledge: false` and `receipt_id: 7`.
- Questions: `can_ask: true`, `topics[{value: "report_coverage", label: "Is the coverage complete?"}]`, one item in each of `recorded`, `answered`.
- Personas: HR/payroll operator (admitted), Finance Lead (aggregates only), another member (403), an outsider (404).

## Lanes
- Frontend lane (owner of all of this feature): `frontend/src/features/finance/payroll/**` (new: request form, inputs list, upload, error board, start, matching panel, rows table, name checks, report, questions, `payrollAdapter.ts`), `frontend/src/app/projects/[caseId]/payroll/**` (new routes), live payroll types re-exported from `frontend/src/api/types.ts` (generated from `live-schema.d.ts`, no hand-written shapes), `frontend/mock/payroll.mjs` and `frontend/mock/fixtures/payroll/**` (new files), a one-line registration in `frontend/mock/server.mjs`, tests next to the code and `frontend/e2e/payroll-import.spec.ts`.
- Backend lane: none. No backend, migration or contract change.
- Integration owner: lane D coordinator. Shared files owned by lane C (F-85): `src/features/workspace/*`, `src/features/work-item/**`, `src/api/*`; this feature adds files beside them and calls `registerLineAdapter` only. `frontend/mock/finance*` and the payments fixtures belong to lane B; any edit there is named in build.md.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
Ports: Next 4990, mock 4991, Django 8030. Mock personas as in Fixture examples.
1. As the payroll operator, `/projects/{caseId}/payroll` lists the requests from `GET .../payroll/requests` and "Start a payroll request" creates one with two providers; the new request opens its detail page — verify: open the page on 4990; `frontend/e2e/payroll-import.spec.ts`; network panel shows one `POST` with `{revision, reference, metadata, evidence_id}`.
2. The request detail shows one row per provider with version, accepted or held, created time and "Replaces version N" when `replaces_input_id` is set, from `GET .../inputs` — verify: e2e on the three fixture inputs; unit test on the row mapper.
3. Uploading a CSV for a provider sends one multipart `POST .../inputs` with `revision`, `provider`, `operation_key`, `file`, no hand-set `Content-Type`, and `replaces_input_id` only when "This replaces an earlier file" is chosen — verify: network panel; unit test on the body builder; header `X-CSRFToken` present.
4. A file over `PROOF_MAX_BYTES` or a format not in the provider's `formats[]` is refused before any request — verify: unit test asserts no fetch call.
5. A refused upload (fixture C) shows the file error board with the safe explanation and "Nothing was imported and nothing was changed", "Upload again" and "Download template"; the "What we expected / What we found" block is drawn only when the response carries sheet names, else it is absent with no empty heading — verify: e2e on both fixtures.
6. "Download template" calls `GET .../template?provider=&format=` and saves the file; it offers only formats listed for that provider; the response body is not rendered or logged — verify: network panel and unit test; grep for `console.` in the payroll folder returns nothing.
7. Held rows appear in a "rows need HR" table from `working-rows?status=held`; an unknown amount reads "Unknown", never 0; a `quarantined` row says Held — verify: e2e and unit test on the row mapper with `amount: null`.
8. "Continue to matching" is disabled until one accepted input per provider is selected, sends `POST /work` with `line:"finance-payroll/v1"`, `case_revision` from `start-choices`, a fresh `idempotency_key`, and goes to `/work/{work_id}`; the "N rows" text appears only when a `ready` count was served — verify: e2e; unit test on the body; one POST on a double click.
9. On a `finance-payroll/v1` work item the payroll adapter draws stage, finding, selected inputs and the `working[]` rows; counts appear only for keys the API sends, and `counts: null` shows "Counts aren't available yet." — verify: e2e on the two fixtures; unit test on the adapter's `sections`.
10. The combine, match and aggregate buttons send `POST /work/{id}/payroll-operations` with `{action:"working", expected_revision, case_revision, stage}` and appear only for the next stage; no `publish`, `withdraw`, `successor` or `restart` is sent from this feature — verify: unit test on descriptors; grep `payroll-operations` bodies in the feature for those four words returns nothing.
11. The review controls offer Approve, Return and Withdraw approval (plus Approve draft match on the match run) and no Reject, each only when allowed; the body carries `subject`, `subject_id`, `operation_key`, `evidence_id`, `note` and both revision tokens — verify: unit test on `body()`; e2e that "Reject" text is absent.
12. HR view rows (`working-rows`, `kind=run`) render employee, component, amount, business unit and result from served fields only; no "Left 30 Sep" text, conflict reason, or "136 matched" strip is drawn unless built from served counts — verify: e2e DOM text search.
13. Name checks: with `configured: false` nothing is shown; `can_compare: false` hides the Compare control; `can_route_difference: false` hides "Send the difference to HR"; a side absent from `attestation_sides` has no attest form — verify: unit tests on each flag combination; e2e.
14. Comparing names sends `POST name-checks {revision, run_id, input_id, row_key}`; a `different` result offers "Send the difference to HR" only when allowed and sends `POST name-checks/{id} {revision}` once — verify: network panel; unit test.
15. `receive_hr` is offered only when `hr_receipt.can_acknowledge` is true and sends `{action:"receive_hr", expected_revision, case_revision, snapshot_id, evidence_id}`; with `hr_receipt: null` nothing about HR receipt is drawn — verify: unit test and e2e.
16. As the Finance Lead, the report page shows business units with their served amounts and the eligible total, no staff count column and no names; the "Individual pay is restricted" note is shown; no request is made to `working-rows`, `name-checks` or `hr-disclosures` — verify: e2e on the report fixture with a request logger that fails on those URLs.
17. A business unit the API does not return is not shown, and no row or total is shown as 0 when the API sent none — verify: unit test on the report mapper with a missing unit and a null-like amount.
18. "Confirm you received this report" appears only with `can_acknowledge: true`, sends exactly one `POST payroll/reports/{id} {revision}`, and afterwards shows the receipt state from the re-read — verify: e2e; network panel (no `aggregate-receipt` call from the report page).
19. Questions: "Ask HR a question" appears only when `can_ask` is true with a select of `topics[]` and no free-text field; each row shows only the buttons its `can_*` flags allow, and a reply button per `reply_options[]` — verify: unit tests per flag; e2e.
20. Failure journey 1: with the member persona (403 on rows, inputs and reports) every payroll route shows the "not admitted" block and nothing else — no table, counts, provider names, buttons or hidden DOM nodes holding payroll text — verify: e2e asserts the page text and `document.body.innerHTML` contain none of the fixture staff names, staff IDs, amounts or provider names.
21. Failure journey 2: the outsider persona (404) shows "This payroll record wasn't found." with the same layout as an absent record id; the text of both cases is identical — verify: e2e compares the two pages.
22. Failure journey 3: opening `/projects/{caseId}/payroll/runs/{runId}` as the Finance Lead shows the not-admitted block, and a deep link to an input rows route as the Finance Lead likewise — verify: e2e; the mock answers 403 and the page renders no fixture data.
23. Failure journey 6: with counts 200 and rows 403 the counts are shown and the row area shows the refusal; no count is derived from rows — verify: e2e with a mock scenario.
24. Leak control: after visiting HR rows as the operator, signing out and signing in as the Finance Lead, no staff name or amount from the earlier session appears in the DOM, `localStorage`, `sessionStorage` or the data cache, and none appears in any request URL or query string — verify: Playwright test reads storage and the network log; unit test that cache keys contain no `row_key`, name or amount.
25. No staff name, staff ID, amount or `row_ref` appears in any `console.*` output, thrown error message, toast or error boundary text during the error scenarios (403, 404, 409, 422, 503, network) — verify: Playwright console listener and a unit test of the error boundary with a thrown error that contains a fixture name.
26. Stale writes: a 409 on upload, start, review, stage, attest, question or acknowledge shows the stale message, keeps the person's typed values, re-reads and does not auto-retry — verify: unit tests with the mock `409` scenario; fetch count is one.
27. An upload that times out is not resent automatically; the form tells the person to check the list and re-reads `GET inputs` — verify: unit test counts fetch calls (one POST).
28. 401 shows the signed-out state with a link to `/sign-in?next=<current path>`; 403 `csrf_failed` refreshes the session once and says "Press the button again" — verify: unit tests and mock scenarios.
29. Viewport check at 1440 and 390: SCR-09 default and error, SCR-18 default and permission match the boards for the parts that remain, and the hidden parts leave no empty heading or gap — verify: screenshots reviewed against `design/screens.md` SCR-09 and SCR-18 artboards.
30. The feature makes no request to a v7 mock-only payroll route and imports types from `live-schema.d.ts`, not `@/api/schema` — verify: `grep -rn "api/schema'" frontend/src/features/finance/payroll` returns nothing.
31. Against live Django (8030) as an admitted payroll operator on a real request, the inputs list and template download match `oa.py live GET` output for `inputs` and `template`; as a Finance reader the report matches `GET .../reports/{id}` and the rows route answers 403 — verify: compare page and curl JSON (session cookie); record the 403.
32. `npm run lint`, `npm run typecheck`, `npm test` pass and `api-live-schema-drift.test.ts` still passes — verify: `delivery/checks.sh`.

## Out of scope
- SCR-37 payroll corrections (F-109), SCR-59 payroll run: publish, withdraw, successor, restart and recipient receipts (F-110), SCR-57 BU totals (F-107), the SCR-13 field-visibility editor and D-PAYROLL-VISIBILITY.
- A "Reject" verdict, any new payroll rule, approver, attempt count or amount.
- A group projection of payroll rows or any staff count shown to a recipient; group disclosures exclude names and pay (E-26).
- The per-person HR record text and conflict reason, any match summary not in `working[].counts`, and "expected X, found Sheet1" wording beyond what the API returns (hidden per D-182).
- HR snapshot capture and export (`POST hr-disclosures/.../exports`); only the snapshot rows read and `receive_hr` here.
- Editing `src/features/workspace/*` or `src/api/*` beyond generated types.
- Backend changes, a staff search, exporting or printing rows, and notification sending.

## Assumptions
1. Routes under `/projects/[caseId]/payroll/**` plus an adapter panel on the work item. Reason: requests and inputs exist before a work item does (two-step start), so a project-level page is needed; the readback after start is a panel.
2. Adapter key `payroll-matching`. Reason: the real `panels[].key` for `finance-payroll/v1` is not in the contract; the builder confirms it on a live item and notes it.
3. Provider names come only from the request and `provider_options`, never typed freely. Reason: the API serves exactly two providers per request and no provider list for a new request; the create form takes the two names as text if the API offers no list, and the builder notes that in build.md.
4. The create-request `evidence_id` is chosen through F-85's evidence picker. Reason: the body requires `evidence_id` and F-85 owns how an upload becomes evidence (backend question 1, still unconfirmed).
5. The review `kind` string is taken from the payroll variant in `live-schema.d.ts`. Reason: the contract lists `kind` as a plain string for this variant.
6. The `answered` action literal for a reply is confirmed against the contract before build. Reason: the generated type shows `action: any` with `reply`.
7. A partial-read page (counts 200, rows 403) shows each part by its own read. Reason: access is per record (E-3).
8. Rows are held in component state only and the data cache is cleared on unmount and sign-out. Reason: restricted payroll data must not outlive the session (E-3, E-26).
9. `counts` key names are read from a real 1.24.0 response before the mock fixture is fixed. Reason: the contract types `counts` as an untyped object.

## Questions
1. SCR-18 permission board: the Finance view draws a "Staff" count per business unit and a "Not yet allocated · 4 · Unknown, waiting for HR" row. E-5 says the recipient report has no staff counts and gives an unmatched row no BU entry, so the count column and the allocated row cannot be filled. The board also has no refusal state for a person with no payroll access (403/404).
   1. (Recommended) Drop the Staff column; draw only BU and cost; add a "Not yet allocated" row only when the API names one; add one refusal block ("Payroll is restricted. You aren't admitted to this payroll record.") and one not-found block, drawn by the design engineer.
   2. Keep the board's Staff column but show it blank; rejected because it implies a number exists.
   3. Hold the permission screen until the board is redrawn.
2. SCR-09 error board: the "What we expected / What we found" block (sheet "Inputs" and columns; "Sheet1, Summary") depends on `templates[]` / `findings[]` carrying those names. The contract types them only as objects.
   1. (Recommended) Draw the block from whatever sheet and column names the API returns; if it carries none, show the safe explanation and codes only and hide the block.
   2. Always draw a generic "Download the template and check the sheet names" hint instead.
   3. Hold the board until the backend publishes the fields.
3. SCR-18 default board: the 136/2/2/2 strip, the per-row result labels ("Matched · name differs", "Conflict · paid after leaving"), the HR record column and Zainab's note are not in the API (`counts` is an untyped object; rows carry `codes[]`/`findings[]` only).
   1. (Recommended) Draw counts only for keys the API sends, results only from served codes, no HR record column and no agent note; the table keeps Staff, Amount, Business unit, Result.
   2. Draw labels from a client-side mapping of codes written by the design engineer.
   3. Hold SCR-18 default until the backend answers E-4 with named keys.
4. The board's SCR-18 default view is titled for HR roles with a top-bar persona "HR Lead" and "Ask Zainab a question" / "Review the 4 problems" buttons. The API drives "Ask HR a question" through closed topics and the review through `reviews`.
   1. (Recommended) Use "Ask HR a question" with the closed topic list and a "Review the problems" control that opens the held rows; no agent name.
   2. Keep "Ask Zainab" wording.
   3. Add a free-text question box; rejected because the API accepts closed topics only.
5. Presentation: the start of a request needs a form the boards do not draw (SCR-09 shows only the finished import).
   1. (Recommended) A small form using existing form components on the SCR-09 page (reference, period, currency, two providers, purpose, evidence), reviewed by the design engineer after build.
   2. The design engineer draws the form first.

## Conflicts with the boards
The approved boards would be changed in these places; the design engineer decides once before build (entered under Questions above).
1. SCR-18 permission board: Staff count column and "Not yet allocated" row removed or conditional (Question 1); a refusal state added that is not drawn.
2. SCR-18 default board: match-count strip, HR record column, result reasons and the agent note hidden or reduced to served data (Questions 3 and 4).
3. SCR-09 default board: file name and "uploaded by" are not served, so the file row is provider and version instead; per-file row and problem counts come only from `working-rows` counts; the "Continue to matching · 140 rows" label loses the number when no `ready` count is served.
4. SCR-09 error board: the expected/found block is conditional (Question 2).
5. Added to the boards: the request form, the replaces-an-earlier-file choice, the control total and completeness fields, name-check and question controls, and the refusal blocks (Questions 1 and 5).
