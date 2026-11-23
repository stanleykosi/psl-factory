# A payroll operator sees where a payroll run stands, runs combine, match and aggregate, confirms the HR snapshot, and sees what was published, live

> Tasks: FE-FIN-PAYROLL-RUN (part 1). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the recorded exceptions in `design/review.json`; screens: SCR-59 part 1 (boards assigned below; the rest is F-110B).

## Summary
- `/work/{id}` for a payroll run (line `finance-payroll`) draws a "Payroll run" panel from the live `GET /work/{work_id}/payroll-operations`: where the run stands (stage, finding, work state), the two inputs with their row counts and checks, the combine, match and aggregate results with their counts, and the HR snapshot receipt.
- An admitted operator presses "Run combine", "Run match" or "Run aggregate" (`action: working`) and "Confirm I received it" (`action: receive_hr`, only when `can_acknowledge`). Each write is shown from a re-read, never from the answer alone.
- Once a publication exists the panel reads `GET /projects/{case_id}/payroll/reports/{publication_id}` and shows the eligible total as returned, the totals by business unit and the caller's own receipt. A cancelled run shows the prior receipt from `GET /work/{id}/payroll-recovery`.
- Everything the API does not supply is hidden, not faked (D-182): the "Gross pay + Unknown" split, "140 · 2 HELD", "Merge rule F16", per-recipient receipt rows, input review states, the snapshot staff count, "Written to HR records / Posted to the ledger". Unknown money stays unknown, never 0.
- Reviews, publish, withdraw, successor, restart, HR corrections and the recipient acknowledgement are F-110B. Waits (build start only, not readiness): F-85 shared adapter (lane C, PR #101); F-108 and F-109, which supply the inputs this run consumes. High risk, restricted payroll: merge goes to the design engineer's merge batch.

## Context
Lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend` (origin/main b8542c79, API 1.24.0). Paths marked (F-85) arrive when that merges.
- Work item page: `src/features/work-item/` and the live `LiveWorkItemView.tsx` with `PanelView` (F-85) draw `panels[]` through `adapterFor(key)`. Adapter contract (`PanelRef`, `LineContext`, `LineAdapter`, `CommandDescriptor`, `registerLineAdapter`, `adapterFor`, `makeCommand`) is in `delivery/features/F-85/spec.md`, file `src/features/workspace/adapter.ts` (F-85). Do not change it. `useWorkCommand` (press lock, uncertain lock, csrf, 409 re-read) is F-87's `src/features/workspace/useWorkCommand.ts`; F-104's spec names the optional `render(readback, ctx, reload)` slot for line forms. Reuse it if on main; if not, that slot is a dependency on lane C, named before the build starts.
- Shared UI by name: `Button`, `Callout`, `Tag`, `Select` in `src/components`, `Money` and `Unknown` in `src/components/Values.tsx`, section kinds in `src/features/workspace/labels.ts`, `liveApi`, `call`, `refreshSession` in `src/api/client.ts`, `ApiError` in `src/api/errors.ts`.
- No payroll code exists today. The v7 mock has no payroll run. Start work has no payroll entry (`src/features/start-work/labels.ts`).
- Overlap to settle: F-108's readiness also lists `payroll-operations` working and `receive_hr` (SCR-18). This feature owns the one client and panel for them (`src/features/payroll-run/`); F-108 reuses it and does not build a second. See Question 3.
- Live operations (viewer `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET <path> 3`; from the records checkout read `/Users/Hunchoo/psl-factory-worktrees/lane-d/contracts/psl-factory.openapi.json` directly):
  - `GET /api/v1/work/{work_id}/payroll-operations` (`payroll_sources_work_options`) and `POST` the same path.
  - `GET /api/v1/work/{work_id}/payroll-recovery` (`payroll_sources_recovery`).
  - `GET /api/v1/projects/{case_id}/payroll/{kind}/{record_id}/working-rows` (`payroll_sources_working_rows`; `kind` is `input` or `run`; query `page` 1 to 10000, `status` all, ready, held).
  - `GET /api/v1/projects/{case_id}/payroll/reports/{publication_id}` (`payroll_sources_report`).
  - `GET /api/v1/projects/{case_id}/payroll/requests/{request_id}/inputs` (provider names for the inputs).
  - `POST /api/v1/work` (`finance-payroll/v1`).

## Contract

### Read 1: `GET /api/v1/work/{work_id}/payroll-operations` -> 200
Required: `expected_revision` int, `case_revision` int, `request_id` int, `selected{input_ids: [int, int], hr_snapshot_id: int|null}`, `stage` string, `finding` string, `publication_id` int|null, `working[]` (max 3) of `{id, kind: "combine"|"match"|"aggregate", status: "complete"|"held", codes[], counts: {total, held, conflict, matched|null, unmatched|null}|null}`, `hr_receipt: {snapshot_id, receipt_id|null, can_acknowledge, proofs[{id, version, kind}]}|null`.
- Errors: 401 signed-out state linking to `/sign-in?next=<path>`; 403 `forbidden` and 404 both draw one no-access state, "This record is unavailable." with no staff names, pay values or ids (a 403 for a missing payroll grant and a 404 look the same to the person; the page never says which); 403 `csrf_failed` is not no-access (refresh the session, "Refresh your session and try again"); 409 and 422 show the server message; 429 and 503 "Try again shortly."; network "We couldn't reach the server." Reads may be retried; the panel keeps its last good read on a failed re-read and drops it on 401, 403 or 404.
- Permission rule: every read is as the signed-in person; no client role check decides anything. Controls come only from `working[]`, `stage`, `hr_receipt.can_acknowledge`. The panel is reached through `GET /work/{id}` `panels[]`; adapter key is the live key for this panel, confirmed on the first live payroll work item, with the URL suffix `/payroll-operations` as fallback match.

### Read 2: counts for each input and run (`working-rows`)
Used for counts only. For each id in `selected.input_ids` call kind `input`; for each `working[].id` with status shown call kind `run`. Request `page=1&status=all`; read `total`, `ready`, `held` and nothing else from the body. The response carries staff names and pay in `rows[]`: the panel never renders, stores in React state beyond the mapper, logs, caches by key, or puts in a URL or query string any `rows[]` value. (`working[].counts` already supplies total, held, conflict, matched, unmatched for runs; use it first and call `working-rows` for a run only when `counts` is null.)
- 403 for an admitted reader without the payroll grant, 404 for an invisible record: the one input row shows "Not available to you." with no counts; the other rows still draw.

### Read 3: input labels (`GET .../payroll/requests/{request_id}/inputs`)
Gives `request{reference, period, currency, providers[]}` and `inputs[{id, provider, version, accepted, status "complete"|"held", codes[], findings[{code,message}]}]` (max 25 per page; follow `next_page` until each selected id is found, at most 4 pages). The input row takes `provider`, `version`, and `status` from the entry whose `id` is in `selected.input_ids`; `request.period` and `request.reference` title the panel. An id not found draws "Input {n}" with no provider.

### Read 4: report (`GET .../payroll/reports/{publication_id}`), only when `publication_id` is not null
Required: `id, version, period, entity, currency, by_business_unit{<unit>: decimal string}, eligible_total (string), receipt_id|null, can_acknowledge, revision`. Show `eligible_total` as returned with the currency, through `Money`; no arithmetic, no rounding, no known-plus-unknown split (E-30: a confirmed decimal string, incomplete totals are held on the server and never reach this read). `by_business_unit` is one row per key in the API's order with the string as returned; a unit missing from the object is not drawn and no zero is invented (E-5). No staff counts. 403/404 here hides the report block only ("The totals aren't available to you.") and leaves the rest of the panel. `can_acknowledge` is not acted on in this feature (F-110B).

### Read 5: `GET /api/v1/work/{work_id}/payroll-recovery` -> 200
`{work_id, restart: {expected_revision, case_revision, request_id, selected, configuration_id}|null, previous_receipt: {publication, version, withdrawn_at, receipt_id|null, received_at|null}|null}`. Called only when the work `state` is `cancelled` or `followup_needed`. Part 1 draws `previous_receipt` only (the board's "Already delivered" slot): "Totals version {version} were withdrawn {withdrawn_at}." and, when `receipt_id` is set, "Receipt recorded {received_at}"; a null `receipt_id` reads "No receipt was recorded." and a null `received_at` is "Not recorded". `restart` is held for F-110B and drives no control here. The recipient's name is not on the read, so none is drawn.

### Mapping to the screen (adapter `payrollRunAdapter`, in `src/features/payroll-run/`)
| Part | Source | Rule |
|---|---|---|
| Panel title and period | `request.period`, `request.reference`; title, sample tag and state tag come from the work item (F-85) | |
| Where we are | `finding` as given, small label `stage` as given | empty string draws nothing; no invented words |
| Nine stations strip | none | Not drawn: no read says which of the nine stations the run is on. Stage and finding are shown instead (Question 2) |
| Inputs table | rows for each `selected.input_ids`: provider (Read 3), "Rows" = `total` (Read 2), "Checks" = "{held} held" when `held > 0`, "Passed" only when Read 3 `status === "complete"` and `held === 0`, else "Not recorded" | the board's STATE column (Needs you, Approved, Received) has no source and is hidden; the "See the problem rows" link is hidden (rows belong to F-108) |
| Combined, Match, Aggregate | one block per `working[]` entry in API order: label from `kind`, `status` as "Complete" or "Held", `codes` as plain text (known codes mapped, unknown shown raw) | `counts` null draws "Not recorded" |
| Match counts | `counts.matched`, `counts.unmatched`, `counts.conflict`, `counts.held`, `counts.total` | board words: Matched, Unmatched · ask HR, Conflict, Held from import. A null `matched` or `unmatched` draws "Not recorded", never 0. The board's "paid after leaving" reason is not supplied and is hidden |
| HR snapshot | `hr_receipt` null -> "No HR staff snapshot is assigned to you." (draws nothing if `selected.hr_snapshot_id` is also null); else "Snapshot {snapshot_id}", receipt: `receipt_id` set -> "Received" with the receipt id, null -> "Not confirmed" | no staff count |
| Held notice | work `state` and `working[].codes`; board "Matching can't start." shown when the `match` entry is `held` and `hr_receipt.receipt_id` is null and `hr_receipt.can_acknowledge` | other hold codes draw as plain text from the code; the board's "Other holds look the same: ..." list is not drawn |
| Report block | Read 4 | eligible total, by-unit rows, "Version {version}", receipt: "Your receipt: Recorded" when `receipt_id` set, else "Your receipt: None" |
| Cancelled | Read 5 | as above |
| Verified | work `state === "verified"` tag only | "Receipts 2 of 2", "Written to HR records", "Posted to the ledger" and the Finance sentence are hidden (no source) |
| Not drawn | station track, "Merge rule F16", "140 · 2 HELD", "Gross pay + Unknown", "Not matched · Unknown" row, per-recipient receipt rows, snapshot staff count, input review states, the decision card, Publish, Withdraw, Ask HR to correct, Start a corrected run | |

### Write 1: run a station (`working`)
Buttons "Run combine", "Run match", "Run aggregate". Only the button for the next station is on: the one whose kind is not yet in `working[]`, in the order combine, match, aggregate; the match button is off with the held notice when the HR receipt is unconfirmed. All are off while a press runs, and off when the read is not loaded (both tokens required). The API decides every rule; a refusal is shown, not predicted.
- `POST /api/v1/work/{work_id}/payroll-operations` body `{action:"working", expected_revision, case_revision, stage:"combine"|"match"|"aggregate"}`; tokens come from Read 1, never defaulted, never 0 or null. 200 `{work_id, state, revision, record_id}`.
- After 200: re-read Read 1 and the work item; the new `working[]` entry and the state tag come from the re-read. "Done" is told from the re-read.
- Errors: 403 non-csrf "You can't do this." plus the server message, then re-read; 409 re-read and "This changed while you were working. Showing the latest version."; 422 the server message and the first `fields[].message`; 403 `csrf_failed` refresh once, "Press the button again"; 429 and 503 "Try again shortly.".
- Uncertain (dropped connection, 5xx, or a work `state` of `effect_uncertain` or `awaiting_reconciliation` after a re-read): lock all station buttons, show "We couldn't confirm that this ran. Check the page before trying again.", re-read, and send nothing by itself. Buttons unlock only when the re-read shows a different `expected_revision` and the state is neither `effect_uncertain` nor `awaiting_reconciliation`. The panel offers no retry and no reconcile action here (F-87 owns "Check what happened").

### Write 2: confirm the HR snapshot (`receive_hr`)
Shown only when `hr_receipt` is not null, `hr_receipt.can_acknowledge` is true and `receipt_id` is null. Button "Confirm I received it". If `proofs[]` has more than one entry the person chooses one (radio, labelled `kind` and "version {version}", nothing preselected); with exactly one it is used without a choice; with none the button is off with "No receipt proof is available yet." and nothing is sent.
- `POST .../payroll-operations` body `{action:"receive_hr", expected_revision, case_revision, snapshot_id: hr_receipt.snapshot_id, evidence_id: <chosen proof id>}`. 200 as above; re-read; "Received" is told from `hr_receipt.receipt_id` now being set.
- Errors and uncertain handling as Write 1. Per the backend answer, if the snapshot was never received there is no receipt to confirm; the server's refusal is shown as given.

### Start of the line (`POST /work` `finance-payroll/v1`)
No SCR-59 board draws a start form (Question 4). This feature adds client function `startPayrollRun({caseId, caseRevision, requestId, inputIds, hrSnapshotId, reference})` with unit tests and a mock route only: `POST /api/v1/work` body `{line:"finance-payroll/v1", case_id, case_revision, idempotency_key:<new uuid per attempt>, intake:{request_id, inputs:{input_ids:[a,b], hr_snapshot_id:<int|null>}}, reference}`. It is not rendered by this feature.

### Idempotency and versioning
`payroll-operations` bodies have no idempotency key in the contract; the only guards are `expected_revision` and `case_revision`. Both come from the latest Read 1 and are re-read after every write and every 409. No write is sent twice by itself. `startPayrollRun` uses `idempotency_key`.

### Screen states
- Loading: the panel skeleton; the work header from F-85 shows already.
- Empty: a read with `working: []`, `hr_receipt: null` and `publication_id: null` shows the inputs table, `finding` and the combine button only; no empty headings.
- Error and no-access: as Read 1; a failed Read 2, 3, 4 or 5 degrades only its own block.
- Held: the held notice above; Match block `Held` with `codes`.
- Success: stage blocks, report block, state tag from the work item.
- Uncertain: lock text as Write 1.

| Board state | What the live read looks like |
|---|---|
| Input review | `working: []`, `stage` early; inputs table drawn, no decision card |
| Combine review | `working` has `combine` complete; counts drawn, no decision card |
| Match held | `working` has `match` held; `hr_receipt.receipt_id` null |
| Match review | `match` complete with counts |
| Receipts | `publication_id` set, work `state` waiting; report block |
| Verified | work `state` `verified`; report block |
| Follow-up | work `state` `cancelled` or `followup_needed`; `previous_receipt` set |

### Fixture examples (mock, port 4991; ids are the builder's, shapes are the contract)
All names are fictional and no row values appear in logs or fixtures beyond `rows: []`-style counts.
- `4601` input review: `stage:"input_review"`, `working:[]`, `selected.input_ids:[301,302]`, `hr_snapshot_id:303`; inputs 301 provider "SeamlessHR" total 142 held 2 status held, 302 provider "Pension provider" total 139 held 0 complete.
- `4602` combined: `working:[{id:401,kind:"combine",status:"complete",codes:[],counts:{total:140,held:2,conflict:0,matched:null,unmatched:null}}]`.
- `4603` match held, no receipt: `working` combine complete plus `{id:402,kind:"match",status:"held",codes:["hr_receipt_missing"],counts:null}`, `hr_receipt:{snapshot_id:303,receipt_id:null,can_acknowledge:true,proofs:[{id:77,version:1,kind:"hr_snapshot_receipt"}]}`.
- `4604` match complete: `counts:{total:139,held:2,conflict:1,matched:136,unmatched:2}`.
- `4605` published, waiting: `publication_id:501`; report `{id:501,version:1,period:"2026-10",entity:"PSL",currency:"NGN",by_business_unit:{Delivery:"61400000.00",Design:"19800000.00",Finance:"8100000.00",Other:"9900000.00"},eligible_total:"99200000.00",receipt_id:null,can_acknowledge:false,revision:3}`.
- `4606` verified: as 4605 with `receipt_id:9`, work `state:"verified"`.
- `4607` cancelled after publishing: `payroll-recovery` `previous_receipt:{publication:501,version:1,withdrawn_at:"2026-11-16T09:00:00Z",receipt_id:9,received_at:"2026-11-14T10:00:00Z"}`, `restart` set.
- `4608` null counts: `counts:null` on a run, `matched:null`.
- `4609` 404 for any caller. `4610` 403 (no payroll grant). `4611` returns 409 on the first write then succeeds after a re-read. `4612` `state:"effect_uncertain"`.
- The mock serves these reads and the two `payroll-operations` writes with the live shapes and checks the field names and tokens. v7 ids keep their answers. Any change to `frontend/mock/finance*` or the payments fixtures is named in build.md for lane B.

## Lanes
- Frontend lane (owner of this feature): `frontend/src/features/payroll-run/**` (`payrollRunAdapter.ts`, `PayrollRunPanel.tsx`, `StationButtons.tsx`, `HrReceiptForm.tsx`, `payrollRunApi.ts`, `labels.ts`, tests), `frontend/mock/payroll-run.mjs` and `frontend/mock/fixtures/payroll-run/**`, `frontend/e2e/payroll-run.spec.ts`, live types for these operations in `frontend/src/api/types.ts` from `live-schema.d.ts`.
- Backend lane: none. No backend, migration or contract change.
- Integration owner: lane D coordinator.
- Shared files and owners: `src/features/workspace/*` (lane C owns; this feature registers an adapter and calls `useWorkCommand`; a render slot, if missing, is a lane C dependency). `src/api/*` (shared; additions limited to live types). `mock/server.mjs` (shared; one import line to mount `payroll-run.mjs`). `src/components/*` used as is. F-108 reuses `payrollRunApi.ts`; F-110B extends the same folder.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
Ports: Next 4990, mock 4991, Django 8030 (Postgres per the lane D runbook, account with the payroll grant).
1. `/work/4601` (mock) shows two input rows with provider, rows (142 and 139), checks ("2 held" and "Passed"), the finding line and a "Run combine" button, and no station strip, no STATE column, no decision card — verify: open the page; e2e asserts absence.
2. `/work/4602` shows a Combined block "Complete" with total 140 and held 2, and "Not recorded" (never 0) for matched and unmatched — verify: page text; unit test on the mapper with `matched:null`.
3. `/work/4603` shows "Matching can't start." with a "Confirm I received it" button and "Run match" off; with two proofs the person must choose one first — verify: page; e2e.
4. Pressing "Confirm I received it" sends exactly one `POST /work/4603/payroll-operations` with `{action:"receive_hr", expected_revision, case_revision, snapshot_id:303, evidence_id:77}`, then re-reads, and the page shows "Received" only from the re-read — verify: network panel and mock request log.
5. `/work/4604` shows Matched 136, Unmatched 2, Conflict 1, Held 2 and no "paid after leaving" reason — verify: page; e2e.
6. Pressing "Run combine" on 4601 sends one `POST` with `{action:"working", stage:"combine", expected_revision, case_revision}` and no other fields; the next read shows the Combined block — verify: network panel; unit test on the body.
7. A body never contains a `null` or `0` token: with the read not loaded every control is off and nothing is sent — verify: unit test.
8. A write that gets 409 (`4611`) re-reads, shows "This changed while you were working. Showing the latest version.", and sends nothing again by itself — verify: mock scenario; count requests.
9. A dropped connection after a write, or `/work/4612` (`effect_uncertain`), locks every station button with "We couldn't confirm that this ran. Check the page before trying again." and sends no request until the re-read shows a new `expected_revision` and a settled state — verify: mock scenario; request count.
10. `/work/4605` shows "NGN 99,200,000.00" as the eligible total from `eligible_total` "99200000.00" through `Money`, the four business-unit rows, "Version 1", "Your receipt: None", and no "Unknown" split, no staff counts and no per-recipient rows — verify: page; e2e.
11. A business unit absent from `by_business_unit` has no row and no 0; an absent `eligible_total` cannot occur by contract, but a report 403 shows "The totals aren't available to you." and the rest of the panel still draws — verify: unit test; mock 403 on the report.
12. `/work/4606` shows the verified tag and the report block and does not show "Receipts 2 of 2", "Written to HR records" or "Posted to the ledger" — verify: e2e asserts absence.
13. `/work/4607` shows "Totals version 1 were withdrawn" with the date and "Receipt recorded" with the received time, and no "Start a corrected run" button — verify: page; e2e.
14. `previous_receipt` with null `receipt_id` and null `received_at` reads "No receipt was recorded." and "Not recorded" — verify: unit test.
15. `/work/4609` (404) and `/work/4610` (403) both show exactly "This record is unavailable." with no staff names, values or ids; neither shows a reason — verify: open both and compare text; unit test on the mapper.
16. A 403 `csrf_failed` on a write does not show the no-access state; it refreshes the session once and says "Press the button again"; no automatic second send — verify: unit test counts fetch calls.
17. A different signed-in user without the payroll grant, and a different tenant's work id, each get the no-access state and no `working-rows` or report call is made after the first denied read — verify: mock scenarios; request log; live check with two accounts against Django 8030.
18. No `rows[]` value from `working-rows` (employee, amount, bu, row_ref, sources) appears in the DOM, in `localStorage`/`sessionStorage`, in a URL, in a React Query or cache key, or in any `console` output — verify: unit test greps the mapper output; e2e dumps storage and the DOM and searches fixture employee names.
19. Against live Django 8030, for a real payroll work id the page shows the same `stage`, `finding`, `working[]` counts and `hr_receipt` state as `GET /api/v1/work/{id}/payroll-operations` — verify: compare with the `oa.py live` output or `curl` JSON using the session.
20. Against live Django, a run with a publication shows the same `eligible_total`, `by_business_unit` and `version` as `GET .../payroll/reports/{publication_id}` — verify: compare with the `curl` JSON.
21. The page makes no `POST /work/{id}/reviews`, `aggregate-receipt`, `corrections`, or `payroll-operations` with `publish`, `withdraw`, `successor` or `restart`, and shows no Publish, Withdraw, Approve, Return, Ask HR or Start-a-corrected-run control — verify: grep `liveApi.POST` in `src/features/payroll-run` shows only `working`, `receive_hr` and `startPayrollRun`; e2e asserts absence.
22. `startPayrollRun` sends `finance-payroll/v1` with `idempotency_key` and the two input ids, and `hr_snapshot_id` null stays `null` — verify: unit test against the mock; it is not imported by any page (grep).
23. An unknown `working[].codes` value and an unknown `stage` draw their raw text; a missing selected input in Read 3 draws "Input {n}" — verify: unit tests.
24. A failed Read 2 or Read 3 leaves the other blocks drawn and shows that block's error with Try again; a failed re-read after a write keeps the last good read — verify: mock scenarios.
25. Viewport check at 1440 and 390: the page matches the SCR-59 boards for the parts that remain; hidden parts leave no empty gap or empty heading — verify: screenshots at both widths reviewed against the SCR-59 desktop and mobile boards.
26. Tests exist for the mapper (all seven states), the two write bodies, the uncertain lock, the 409 path and the no-leak rule in criterion 18; `delivery/checks.sh` passes — verify: `npm test`; checks result.

## Board assignment (18 boards)
Part 1 draws only the read-only and working-step parts of its boards; the decision cards on those boards are F-110B.
| Board (desktop and mobile) | Part | What part 1 draws |
|---|---|---|
| SCR-59-input-review | F-110 | inputs table (provider, rows, checks); no STATE column, no Approve or Return |
| SCR-59-combine-review | F-110 | Combined block with counts; no decision card; "Run combine" |
| SCR-59-match-held | F-110 | held notice, HR snapshot receipt, "Confirm I received it" |
| SCR-59-match-review | F-110 | match counts; no Approve, Return or Ask HR to correct |
| SCR-59-receipts | F-110 | report block and own receipt; no per-recipient rows |
| SCR-59-verified | F-110 | verified tag and report block |
| SCR-59-followup | F-110 | prior receipt note; no "Start a corrected run" |
| SCR-59-totals-review | F-110B | whole board (decision with Withdraw approval); its table is not readable before a publication exists |
| SCR-59-publish | F-110B | whole board (Publish totals) |
Mobile boards mirror each desktop board and follow the same split: 14 boards part 1, 4 boards (totals-review, publish) F-110B.

## Questions
1. Per-recipient receipts (boards receipts, verified, followup draw "Finance Lead RECEIVED / CEO WAITING" and "2 of 2"). Options: (a) hide them; show only the caller's own receipt and the prior receipt (recommended, nothing in 1.24.0 lists recipients and the report is "your own receipt"); (b) ask the backend for a recipients list on the report or the payroll-operations read. Context: D-182 says hide what the API does not supply.
2. The nine-station strip on every board. Options: (a) hide it and show `stage` and `finding` as given (recommended, no read says the current station of nine); (b) derive a position from `working[]` (combine, match, aggregate) and draw the other six as unlabelled (inaccurate, not recommended); (c) ask the backend for a station field. Context: the boards were relabelled to nine stations on 13 Nov.
3. F-108 also lists `working` and `receive_hr` for SCR-18. Options: (a) F-110 owns the panel and client, F-108 reuses it and drops its copy (recommended, one implementation of a money-adjacent write); (b) F-108 builds it and F-110 reuses it; (c) both build, merge conflict risk. Context: whichever builds second must merge the other first.
4. Where payroll runs start (`POST /work` `finance-payroll/v1`, requires request and input ids from F-108). Options: (a) client function and mock only, rendered by F-108's inputs board (recommended); (b) add a Start-work entry here, which no board draws; (c) leave the start out until F-108 merges. Context: SCR-04 has no payroll form drawn.
5. Per-input state words (Needs you, Approved, Received) and the "See the problem rows" link. Options: (a) hide both (recommended, no read supplies review state; rows belong to SCR-09/18 in F-108); (b) show the import `accepted` flag as "Accepted" or "Held" in the STATE column (a different meaning from the board, risk of misreading). Context: review verdicts have no read in part 1.
6. The `payroll-recovery` prior receipt has a board slot (followup "Already delivered") but with names and dates per recipient. Options: (a) one line from `previous_receipt` with version and dates (recommended); (b) leave it off until a board draws one receipt. Context: readiness Question 1.
7. The "Gross pay ₦... + Unknown" wording and the "Not matched · Unknown" row on the totals board have no API source. Options: (a) show the confirmed total and unit rows only (recommended; E-30 says incomplete totals are held on the server); (b) ask the backend for a known-plus-unknown split, which conflicts with D-185. Context: affects F-110B's totals-review board; recorded here so one answer covers both parts.

## Conflicts with the boards
1. Nine-station strip (CMP-02) removed on all boards. Recommendation: Question 2 option (a).
2. Inputs table: STATE column and "See the problem rows" removed. Recommendation: Question 5 option (a).
3. Combined set: "Staff rows 140 · 2 HELD", "Gross pay ₦99,200,000.00 + UNKNOWN" and "Merge rule F16" removed; the counts drawn are those in `working[].counts`. Recommendation: hide (D-182).
4. Match review: "Conflict · paid after leaving" loses its reason; board label becomes "Conflict". Recommendation: hide the reason.
5. Match held: "139 STAFF" snapshot count and the line about the snapshot "sent to Ngozi Eze" removed (no source). Recommendation: hide; keep "Matching can't start." and the confirm button. The "Other holds look the same" line is not drawn.
6. Receipts, verified, follow-up: per-recipient rows, "2 OF 2", "Written to HR records NO", "Posted to the ledger NO" and the Finance sentence removed. Recommendation: Question 1 option (a).
7. Added that the boards do not draw: `stage` and `finding` lines; the report block (eligible total, business-unit rows, version, own receipt) on the receipts and verified states, because the API supplies it. Recommendation: keep; they need a board by the design engineer.
8. Decision cards, Publish, Withdraw approval, Ask HR to correct, Start a corrected run are not drawn here (F-110B). Recommendation: leave to F-110B.

## Out of scope
- Everything in F-110B: `POST /work/{id}/reviews` (approve, return, revoke, approve_draft_match), `payroll-operations` `publish`, `withdraw`, `successor`, `restart`, `POST /work/{id}/corrections`, `POST /work/{id}/aggregate-receipt` and the recipient acknowledgement. `payroll-recovery.restart` drives no control.
- Listing or opening `working-rows`, the problem-rows view, HR snapshot rows (`hr-disclosures/snapshots/{id}/rows`), name checks, attestations and HR questions (F-108, F-109).
- Showing any staff name or individual pay value; a recipient or group view of payroll rows (E-26).
- Reconcile or "Check what happened", resume, cancel (F-87).
- The SCR-13 field-visibility editor and D-PAYROLL-VISIBILITY.
- Whether SCR-57 reads the payroll aggregate or the match run (E-32; SCR-57 reads the match run).
- Rendering `startPayrollRun`; a Start work payroll entry.
- Backend, migrations, contract edits, changes to the F-85 frame.

## Assumptions
- Provider names, versions and the held/complete flag for inputs come from the request inputs read (Read 3). Reason: `payroll-operations` carries only input ids.
- "Checks" says "Passed" only when the input's own status is `complete` and its held count is 0; otherwise "{held} held" or "Not recorded". Reason: the board's "Passed" needs a positive source, and unknown is never a pass.
- The next-station button is derived from which `kind` values `working[]` already has, in the fixed order combine, match, aggregate. Reason: the contract lists these three stages and no "next stage" field; the server still refuses an invalid press.
- `evidence_id` for `receive_hr` is chosen from `hr_receipt.proofs[]`. Reason: that is the only evidence list the read supplies for the exact snapshot (backend answer E-6 says use the exact received snapshot and evidence ids).
- Money is drawn through `Money` with the report's `currency` code, with no formatting arithmetic. Reason: "show as returned" (E-30).
- The panel's adapter key is confirmed on the first live payroll work item; the URL suffix `/payroll-operations` is the fallback. Reason: the live `panels[].key` for this line is not in the contract.
- 403 and 404 draw the same no-access wording on this restricted screen. Reason: avoids saying whether a payroll record exists; the F-108 readiness wording ("not admitted" vs "not found") applies to its own screens.
- Mock fixture ids 4601 to 4612. Reason: free in the mock; live ids are integers.
- The board assignment treats the two decision-heavy boards (totals-review, publish) as F-110B. Reason: their content is the verdict or the publish write, and the totals table is unreadable until a publication exists.
