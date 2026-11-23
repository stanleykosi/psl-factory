# Income schedules, part 2: correct returned rows, settle duplicates, export as an adjustment

> Tasks: FE-CONNECT-1 (line `income_schedules`, W-2701 to W-2712). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0 (the write bodies below are unchanged from 1.24.0). Design: approved 13 Nov canvas under the recorded exception in `design/review.json` (D-173/D-181); screens: SCR-54 part 2, boards `SCR-54-{desktop,mobile}-{held,returned,export}`. The `withdrawn` boards are reached only through F-101's `revoke` verdict and are not drawn here beyond what the read supplies.

## Summary
- On a live `income_schedules` item, a returned schedule gets a "Correct and resubmit" form per returned row, a held schedule gets a duplicate settlement form, and a schedule with `can_export: true` gets "Export as an adjustment". All three are `POST /work/{work_id}/finance-schedule` (201) and are drawn from the same `GET` that F-101 reads.
- The three forms live in a new `IncomeSchedulesActions.tsx`, rendered by F-87's `Actions` slot and sent through `useWorkCommand`. Nothing is sent by load, polling or navigation; one press sends one request with no automatic retry.
- After an export, `exports[]` is listed and each entry links to a new read page for the adjustment (`GET /projects/{case_id}/accounting-adjustments/{adjustment_id}`): reference, version, kind, lines and the review verdict as served.
- Evidence ids are always chosen from the read's `evidence[]`, nothing preselected, and the button stays off when the list is empty. Unknown money stays "Unknown"; the page adds, counts and compares no amounts.
- Held, not built: the adjustment review form (`POST .../accounting-adjustments/{id}` needs a `role` string no source supplies, Question 1) and creating source mappings. Waits, not blockers: F-101 (part 1), F-85 (shared adapter) and F-87 (the `Actions` slot and `useWorkCommand`); the coordinator holds the builder until all three are on main.

## Context
Lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend` (API 1.25.0). Nothing for these writes exists today: `grep -rn "accounting-adjustments" frontend/src frontend/mock` finds only the generated `src/api/live-schema.d.ts`.
- F-101 (`/Users/Hunchoo/psl-factory-main/delivery/features/F-101/spec.md`) builds `src/features/workspace/incomeSchedulesAdapter.ts` (panel key `income-schedules`, read of the finance-schedule URL, tokens `expected_revision` and `case_revision` taken from that body), the read mapping and the review form. This feature extends that adapter additively and reuses its types and row mapper. It does not change F-101's behaviour.
- F-85 (`/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`): `LineAdapter`, `CommandDescriptor`, `makeCommand`, `LineContext {workId, caseId, revision, caseRevision}`, `EvidenceId` and `UploadId` kept distinct. F-87 (`.../F-87/spec.md`): `Actions?: ComponentType<LineActionsProps>` with `LineActionsProps = { readback, ctx, commands, reload }`, and `useWorkCommand` (press lock, uncertain lock, error words). F-89's `WeeklyReportActions.tsx` is the example for a form component.
- Live read `GET /work/{work_id}/finance-schedule` is as in F-101's Context. Fields used here: `expected_revision`, `case_revision`, `schedule_id`, `kind`, `income.rows[].{key, relationship, amount, duplicate_state, duplicate_resolution_evidence_id}`, `returned{review_id, rows[{key, relationship}]}`, `can_export`, `exports[{id, kind, adjustment_id}]`, `evidence[{id, version, kind}]`, `result.{additive_total, reclassification_total}`.
- Live write `POST /api/v1/work/{work_id}/finance-schedule`, header `X-CSRFToken`, one of three bodies (all `additionalProperties: false`, all fields required). Answer 201 `{work_id, state, revision, record_id}`; errors 400, 401, 403, 404, 409, 413, 415, 422, 429, 503.
  - `{"action":"resubmit_row","expected_revision","case_revision","schedule_id","return_id","row_key","relationship":"disaggregation|reclassification|additive"}`
  - `{"action":"resolve_duplicates","expected_revision","case_revision","schedule_id","decisions":[{"key","treatment":"already_represented|separately_justified"}] (max 100),"evidence_id","reason" (1 to 2000 characters)}`
  - `{"action":"export_adjustment","expected_revision","case_revision","schedule_id","kind":"additive|reclassification","evidence_id"}`
- Live reads `GET /projects/{case_id}/accounting-adjustments/{adjustment_id}` returns `{id, source_id, reference, version, kind, lines[{account, amount (string)}], evidence_id, review_id|null, review_verdict (approve|return|reject)|null, case_revision}`. `POST` of the same path takes `{case_revision, role, verdict, evidence_id, note}` (201 `{id, case_revision}`); `POST .../accounting-sources/{source_id}/mappings` takes `{case_revision, adjustment_ids[]}`; `GET .../accounting-mappings/{mapping_id}` reads a mapping. Only the first GET is used here.
- The board strings come from `/Users/Hunchoo/psl-factory-main/design/canvas/finance/project/SCR-54-{desktop,mobile}-{held,returned,export}.dc.html`. Backend answers E-21 and E-22 (`/Users/Hunchoo/psl-factory/delivery/connect/backend-answers.md`, `### SCR-54`) do not cover these writes; the contract is the source.

## Contract

### Commands (added to F-101's adapter `commands(readback, ctx)`)
Three descriptors, all method POST, url `/api/v1/work/{id}/finance-schedule`, tokens `expected_revision` and `case_revision` from the finance-schedule body (a `null` token stays `null` and the command shows its `disabledReason`, never 0), `idempotency.field: null` (no key field on these bodies), `successStatuses: [201]`. `schedule_id` is passed as an input and is never typed by the person. The `action` value is the one in the table, set by `makeCommand`. Never put a token inside `inputs` (TECH-1-1).

| id | action | offered when (all from the read) | inputs |
|---|---|---|---|
| `income-schedules.resubmit` | `resubmit_row` | `returned` not null and `schedule_id` not null; one form per `returned.rows[]` entry | `schedule_id`, `return_id` = `returned.review_id`, `row_key` = that row's `key`, `relationship` |
| `income-schedules.resolve-duplicates` | `resolve_duplicates` | `kind: income`, `schedule_id` not null and at least one `income.rows[]` with `duplicate_state: "not_assessed"` | `schedule_id`, `decisions[]`, `evidence_id`, `reason` |
| `income-schedules.export` | `export_adjustment` | `can_export: true` and `schedule_id` not null | `schedule_id`, `kind`, `evidence_id` |

When the read does not offer a command, its form is absent (no disabled placeholder). `disabledReason` is used only for what the read says (a `null` token, an empty `evidence[]`).

### Correct and resubmit (boards `SCR-54-*-returned`)
- Under the returned rows already drawn by F-101: for each `returned.rows[]` entry a form headed by the row `key`, with the current `relationship` shown as "Currently: Disaggregation" (words as F-101), and a three-choice `Segmented` control (Disaggregation, Reclassification, Additive) with nothing selected, then the button "Correct and resubmit". The button is off until a choice is made; the message is "Choose how this row should be treated."
- Body: `{action:"resubmit_row", expected_revision, case_revision, schedule_id, return_id, row_key, relationship}`. No evidence and no note: the body has neither.
- The page does not stop a person resubmitting the same relationship as the current one; the server decides.
- Several returned rows give several forms; one press sends one row. After a 201 the page re-reads and draws what the re-read says (the row may leave `returned.rows[]`, or the whole `returned` may become null); it never says "resubmitted" from the 201 alone.
- Mobile: the form is in the page flow in one column, at 390 with 44 by 44 px targets (D-92c). No Drawer is needed (no note field).

### Settle duplicates (boards `SCR-54-*-held`)
- Under F-101's "Possible duplicates" lines, a "Rows to resolve" table with one line per `income.rows[]` entry whose `duplicate_state` is `not_assessed`: key, relationship, amount (null shows "Unknown") and a two-choice `Segmented` control "Already in the accounts" (`already_represented`) / "Separately justified" (`separately_justified`), nothing selected. Rows with `already_represented` or `separately_justified` show that state as read-only text (and "Evidence {id}" only when `duplicate_resolution_evidence_id` is set); `adjustment_lines` are not drawn.
- Below the table, one evidence choice (a select of `evidence[]`, each shown as its kind and "version N", nothing preselected) and a required Reason field (1 to 2000 characters after trimming, checked before any request), then the button "Save and prepare again" (the board's label).
- The button is off until every `not_assessed` row has a choice, an evidence row is chosen and a reason is typed, with the reasons "Choose a treatment for every row.", "Choose the evidence this rests on." and "Add a reason." If `evidence[]` is empty the form shows "There is no evidence on this schedule to cite, so duplicates can't be settled yet." and no button.
- Body: `{action:"resolve_duplicates", expected_revision, case_revision, schedule_id, decisions:[{key, treatment}] (one per `not_assessed` row, in row order), evidence_id, reason}`.
- The board's sentence "2 additive rows are marked 'not assessed' for duplicates" is drawn only as the table's own heading ("Rows to resolve"); no count or "2 of 2" is computed on the page.

### Export as an adjustment (boards `SCR-54-*-export`)
- Shown only when `can_export` is true and `schedule_id` is not null. A `Segmented` choice of kind (Additive, Reclassification), nothing selected. After the choice the page lists the `income.rows[]` whose `relationship` equals the kind (key, amount as read, "Unknown" for null) and shows the matching read total (`result.additive_total` or `result.reclassification_total`, "Unknown" when null or when `result` is null) as given by the backend, never summed by the page.
- One evidence choice from `evidence[]`, as above, then the button "Export adjustment". Off until a kind and an evidence row are chosen; same empty-list message ("There is no evidence on this schedule to cite, so it can't be exported yet.").
- Body: `{action:"export_adjustment", expected_revision, case_revision, schedule_id, kind, evidence_id}`. No note field is drawn: the body has none.
- A short consequence line from the board, "It reaches the accounts only after another Finance person approves the adjustment.", is NOT drawn: no field on the read says who approves or whether it reaches the accounts. (Conflict 3.)
- After a 201 the page re-reads. `exports[]` is then drawn as a list under "Exports": kind in words and a link "View adjustment {adjustment_id}" to `/projects/{case_id}/accounting-adjustments/{adjustment_id}` (the work item's `case_id` from `LineContext`). `exports[]` also shows on any later visit when non-empty, whatever `can_export` says. "Posted to the ledger" is not drawn (no field).
- Idempotency: there is no key. The press lock plus the revision check stop a repeat; an export is sent once per press.

### Adjustment page (new read)
- Route `/projects/[caseId]/accounting-adjustments/[adjustmentId]` (new files under `src/app/projects/...` calling a component in `src/features/accounting-adjustment/`; Question 5). Request `GET /api/v1/projects/{case_id}/accounting-adjustments/{adjustment_id}` through `call(liveApi.GET(...))`.
- Draws: reference, "Version {version}", kind in words, lines as account and amount string exactly as served (amounts are strings; the read has no currency, so none is drawn and none is invented; no arithmetic, no total), "Based on evidence {evidence_id}" with a link only if the shared client already has an evidence route, and the review state: `review_verdict` null and `review_id` null reads "Not reviewed yet"; a verdict reads "Approved", "Returned" or "Rejected". A link back to the work item is drawn only when the page was opened from it (a `?work=` query carrying the work id; otherwise none).
- States: loading; 404 "This record is unavailable." (same words for missing and not yours, no title and no further call); 401 signed-out with `/sign-in?next=`; 403 "You can't view this adjustment."; 429 and 503 "Try again shortly." with Try again (reads may retry); network "We couldn't reach the server."; empty `lines[]` shows the reference and "No lines." Success as above.
- The review form, the source-mapping form and mapping reads are not built (Out of scope).

### Sending, versioning and recovery (all three writes)
- Request through `useWorkCommand` (F-87): `liveApi.POST` with `X-CSRFToken`; one write at a time; the buttons of every form on the panel are disabled while one runs; no automatic retry.
- Success (201): `reload()` re-reads the work item and the finance-schedule; the page shows state from the re-read only. If the re-read fails: "Sent. We couldn't reload the item; reload the page to see its state." and the controls stay off until a read succeeds.
- Network failure, dropped connection, 5xx or 503: the effect may have happened. Say "We couldn't confirm that this was recorded. Check the schedule before trying again.", re-read both, and keep that form's button off until the re-read shows a different `expected_revision` than the one sent (the decision stands; draw the new state) or the person reloads the page. If the revision is unchanged after the re-read, the person may press again.
- 409: re-read, say "This schedule changed while you were reading it, so nothing was recorded.", keep the person's choices, evidence and reason in the form (re-mapped onto the new rows by `key`; a choice for a row that is gone is dropped and says so).
- 400/422: first `fields[].message`, else `message`, next to the form; input kept. 401 signed-out state. 403 `csrf_failed`: refresh the session once, say "Press the button again", send nothing by itself. Other 403: "You can't do this." plus the server's message, then re-read. 404 "This record is unavailable." (no leak). 413/415 "That request couldn't be sent." 429 and 503 "Try again shortly." (503 is also uncertain as above).
- Permission and tenant: the backend decides role, separation of duties and case access. The page has no role check and no `/me` read; it shows a form only when the read supplies its trigger (table above). A hidden schedule shows no title, no figure and no further call.

### Screen states
- Loading, error, empty: as F-101 (a failed finance-schedule read leaves the work item header visible; `income` null shows stage and finding only). No form is drawn without the read.
- Success per board: held (`SCR-54-*-held`: reason, rows to resolve, evidence, button), returned (`SCR-54-*-returned`: rows and forms), verified with `can_export` (`SCR-54-*-export`: export block), verified with `exports[]` (list and links). Forms that do not apply leave no empty heading or gap.
- Inventory kind: unchanged from F-101, read only, no action.

### Fixtures (mock serves live-shaped bodies for numeric ids; numbers are free but must not clash with F-101's 4201 to 4207)
- `4210` held duplicates: `schedule_id:12`, `expected_revision:7`, `case_revision:20`, `evidence:[{id:61,version:1,kind:"document"},{id:62,version:2,kind:"note"}]`, `income.rows` with `row-36` (additive, amount "600000.00", `duplicate_state:"not_assessed"`), `row-37` (additive, amount null, `not_assessed`) and `row-38` (`separately_justified`, `duplicate_resolution_evidence_id:61`).
- `4211` returned, two rows: `returned:{review_id:40, rows:[{key:"row-12",relationship:"disaggregation"},{key:"row-14",relationship:"additive"}]}`, `schedule_id:12`, tokens as above.
- `4212` export ready: `can_export:true`, `exports:[]`, rows of both relationships (one `amount:null`), `result` with `additive_total:"600000.00"`, `reclassification_total:null`, evidence as above.
- `4213` exported: `can_export:false`, `exports:[{id:71,kind:"additive",adjustment_id:71}]`.
- `4214` null tokens: `expected_revision:null`, `case_revision:null` with `returned` set (forms show their disabled reason and send nothing).
- `4215` no evidence: `evidence:[]` with duplicates held and `can_export:true`.
- Adjustment mock: `GET /projects/{caseId}/accounting-adjustments/71` returns `{id:71, source_id:5, reference:"ADJ-0071", version:1, kind:"additive", lines:[{account:"4100",amount:"600000.00"},{account:"4200",amount:"-600000.00"}], evidence_id:61, review_id:null, review_verdict:null, case_revision:21}`; `.../72` has `review_verdict:"approve"`; `.../73` is 404 for any caller.
- Mock `POST /work/{id}/finance-schedule`: validates the exact body for each `action` (rejects extra or missing fields with 422 `fields[]`), answers 201 `{work_id, state, revision:<expected_revision+1>, record_id}`; scenarios by `?scenario=` for 409 once, 403 `csrf_failed`, 422, 429, 503 and a dropped connection; a scenario where the 201 is sent but the re-read is old.

## Lanes
- Frontend lane (owner): `frontend/src/features/workspace/IncomeSchedulesActions.tsx` (the three forms) and its CSS beside `workspace.css` additions (tokens only); `frontend/src/features/workspace/incomeSchedulesAdapter.ts` (additive: three descriptors in `commands()` and `Actions: IncomeSchedulesActions`); `frontend/src/features/accounting-adjustment/**` and its route files under `frontend/src/app/projects/[caseId]/accounting-adjustments/[adjustmentId]/`; live types for the new bodies and reads in `frontend/src/api/types.ts` (taken from `live-schema.d.ts`, no hand-written shape); `frontend/mock/**` (the finance-schedule POST, the adjustment GET and the fixtures above); tests next to the new files; `frontend/e2e/income-schedules-actions.spec.ts`.
- Backend lane: none. No backend, migration or contract change.
- Integration owner: lane D coordinator. Shared and not edited here: `frontend/src/features/workspace/{adapter.ts,useWorkCommand.ts,Workspace.tsx,Sections.tsx,EvidencePicker.tsx,evidence.ts}`, `src/features/work-item/**`, `src/api/*` other than additive live types (lane C). Registering `Actions` is the adapter's own field; if the slot or `run(descriptor, inputs)` is missing from `useWorkCommand` on main, name it as a dependency on lane C in `build.md` and do not add it. Any change to `frontend/mock/finance*` or payments fixtures is named in `build.md` for lane B.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4211` (Next 4990, mock 4991) shows "Correct and resubmit" for `row-12` and `row-14`, each with its current relationship and a three-way choice with nothing selected, and the button is off until a choice is made — verify: open the page; `frontend/e2e/income-schedules-actions.spec.ts`.
2. Choosing Reclassification for `row-12` and pressing the button sends exactly one `POST /api/v1/work/4211/finance-schedule` with `{action:"resubmit_row", expected_revision:7, case_revision:20, schedule_id:12, return_id:40, row_key:"row-12", relationship:"reclassification"}` and `X-CSRFToken`, and no other field — verify: network panel; unit test on the descriptor `body()`.
3. After the 201 the page shows what the re-read says and never "resubmitted" from the write alone; with a mock where the re-read still returns the old state, the page still shows the returned rows — verify: mock scenario; unit test.
4. `/work/4210` lists only `row-36` and `row-37` under "Rows to resolve" with a choice each and an amount of "Unknown" for the null one; `row-38` shows as settled with its evidence id; the button stays off until both rows have a choice, an evidence row is chosen and a reason is typed — verify: e2e; unit test of the gate.
5. Saving on `/work/4210` sends one `POST` with `{action:"resolve_duplicates", expected_revision:7, case_revision:20, schedule_id:12, decisions:[{key:"row-36",treatment:...},{key:"row-37",treatment:...}], evidence_id, reason}` and nothing for `row-38` — verify: network panel; unit test.
6. `/work/4212` shows "Export as an adjustment" with a kind choice and an evidence choice, both unselected; choosing Reclassification lists only reclassification rows and shows "Unknown" for the null total; the page adds up nothing — verify: e2e; `grep -n "parseFloat\|Number(\|reduce(" ` on the new files returns nothing on amounts.
7. Pressing Export on `/work/4212` sends one `POST` with `{action:"export_adjustment", expected_revision, case_revision, schedule_id, kind, evidence_id}` and no note; the export form is absent when `can_export` is false (`4213`, `4210`, `4211`) — verify: network panel; e2e on all four.
8. After a successful export the re-read shows `exports[]` as a list with a link to `/projects/{case_id}/accounting-adjustments/71`; `/work/4213` shows the list and no export form — verify: e2e.
9. With `evidence: []` (`4215`) the duplicates form and the export form each show their "no evidence" message and no button; no evidence select offers anything but `evidence[]` rows; the page has no free-text evidence id and no file input; nothing is preselected — verify: component test and e2e.
10. With `expected_revision: null` and `case_revision: null` (`4214`) every form shows its reason and no request is sent; the null is never sent as 0 — verify: unit test asserts no fetch call.
11. A dropped connection or 503 after a press shows "We couldn't confirm that this was recorded…", re-reads both, keeps that button off until the re-read shows a different `expected_revision`, and sends the write once — verify: mock scenario; count POST calls.
12. A 409 shows "This schedule changed while you were reading it, so nothing was recorded", re-reads, and keeps the person's choices, evidence and reason (a choice for a row that is gone is dropped and says so) — verify: mock scenario.
13. A 403 `csrf_failed` refreshes the session once, says "Press the button again" and does not retry by itself; any other 403 shows "You can't do this." with the server's message; a 404 shows "This record is unavailable." — verify: mock scenarios; count calls.
14. A 422 with `fields[]` shows the first field message beside the form and keeps the input; a reason over 2000 characters or empty is stopped before any request — verify: mock scenario; unit test.
15. A double click on any button makes one request; while one write runs every form on the panel is off — verify: unit test with a recording fetch.
16. `/projects/{caseId}/accounting-adjustments/71` shows reference "ADJ-0071", "Version 1", kind, both lines with their amount strings unmodified and "Not reviewed yet"; `/72` shows "Approved"; `/73` shows exactly "This record is unavailable." with no title; no review form, no mapping control and no currency symbol appear — verify: e2e; grep the new files for `role:`, `mappings` and `liveApi.POST` (only the finance-schedule writes through `useWorkCommand`).
17. Against live Django (8030) a real returned, held or export-ready `income_schedules` item shows forms exactly when the read says (`returned`, a `not_assessed` row, `can_export`), and a person the server refuses sees the server's 403 message with no access control invented — verify: compare the page with `GET /api/v1/work/{id}/finance-schedule` JSON for each case and a second signed-in role.
18. A wrong tenant: a work id or adjustment id of another case gives the same "This record is unavailable." as a missing one, with no title and no further call — verify: live or mock `4299` and adjustment `73`.
19. No write happens on load, polling or navigation; the only `POST`s to `finance-schedule` come from a press — verify: e2e asserts zero POSTs on load of each fixture.
20. "Posted to the ledger", the board's "Units match the accounts", "A different Finance person must approve…" and the export Note field appear nowhere in the new files; `build.md` says each is hidden because the read supplies nothing — verify: grep; `build.md`.
21. Viewport check at 1440 and 390 against the held, returned and export boards (SCR-54 desktop and mobile): remaining parts match, hidden parts leave no empty heading or gap, controls are at least 44 by 44 px on the phone — verify: screenshots at both widths against `design/screens.md` SCR-54.
22. New tests exist for the three descriptors (ids, urls, bodies, null tokens staying null, no key field), each form's gate, the uncertain lock, each error mapping and the adjustment page mapper; the F-101 tests and `api-live-schema-drift` still pass — verify: `delivery/checks.sh` runs them green.

## Out of scope
- The review decision and the finance-schedule read mapping (F-101), "Withdraw approval" and the withdrawn board's "flagged for Finance" (no field), changes to the shared frame or `useWorkCommand` (lane C), the inventory kind's actions.
- The adjustment review form (`POST .../accounting-adjustments/{id}` with `role`), creating source mappings (`POST .../accounting-sources/{source_id}/mappings`), and mapping reads (no read here supplies a mapping id).
- File upload or `fileToEvidence`, creating evidence records, free-typed ids, a note on export or correction.
- Any total, count, difference or currency formatting computed by the page; new business rules, approvers or "reaches the accounts" claims; backend, migration or contract edits.
- Retrying a failed write automatically, optimistic state, polling on its own timer.

## Assumptions
1. The `action` names are the contract's `resubmit_row`, `resolve_duplicates`, `export_adjustment`; the readiness shorthand ("correct and resubmit", "settle a duplicate") names the same operations. The contract is the source.
2. `return_id` is `returned.review_id`: it is the only return identifier on the read, and the body field is named for the return.
3. A duplicate settlement decides every `not_assessed` row at once, because the held board says to resolve all rows and the body takes one evidence and one reason for the set. The page does not allow a partial save; if the server accepts partial lists this is stricter than needed and harmless.
4. Rows are matched to `duplicates[]` text by nothing: the form is driven only by `income.rows[].duplicate_state`, because `duplicates[]` entries are free strings.
5. An export is one `kind` per press, as the body allows; the board's single mixed "7 rows" export cannot be sent as drawn (Conflict 1).
6. After an uncertain failure the form unlocks only on a changed `expected_revision`, following F-87's rule for keyless writes; no other signal is on the read that proves the effect.
7. The adjustment page shows amounts as the served strings with no currency, because the adjustment read has none and the page must not import one from another read.
8. The adjustment route is `/projects/[caseId]/accounting-adjustments/[adjustmentId]` under the existing `src/app/projects` area; the `exports[]` link and `LineContext.caseId` are enough to build it, and no existing page already owns that path.
9. A `?work={id}` query carries the back link to the work item; without it no back link is drawn.
10. Mock ids 4210 to 4215 are free numbers; v7 `W-27xx` fixtures stay.

## Conflicts with the boards
1. Export board draws "Export these 7 rows as one adjustment" mixing reclassification and additive rows with one combined total ("5 more rows - ₦2,140,000.00"). Live exports one kind per press, and the page may not sum amounts. Recommendation: kind choice first, rows and the backend's own kind total shown, no combined total. Option 2: two buttons "Export additive rows" and "Export reclassification rows" with no choice step. Option 3: hold the export block until a combined export exists.
2. Export board draws a Note field ("needed to return, reject or withdraw") and a Cancel button; the export body has no note. Recommendation: no note field; no Cancel (the form is on the page, leaving it cancels). Option 2: keep Cancel as a clear-form button.
3. Export board draws "Units match the accounts (naira, factor 1)", "Decide · Finance adjuster" with "A different Finance person must approve the adjustment before it reaches the accounts" and "It reaches October's management accounts on their next re-check." No field supplies any of these. Hidden (D-182), with the header's `source_unit` to `target_unit` already shown by F-101.
4. Export board draws row labels such as "Row 12 · training income" and "Row 36 · training fee" and the naira sign; the read has the row `key`, relationship and amount only. Key shown, no description invented; currency from `income.currency` through F-101's money formatter.
5. Returned board draws a select "Reclassification ▾" for one row; live returns a list of rows and no preset choice. Recommendation: one `Segmented` per returned row, nothing selected (F-33 precedent). Option 2: a select as drawn.
6. Returned board draws the reviewer's quote and "Ada Okafor returned it on 13 Nov"; the read has no note (F-101 Conflict 3). Not drawn.
7. Held board draws a per-row "Already in / Justified" pair with no evidence or reason; live requires one evidence and one reason. The form gains an evidence choice and a Reason below the table.
8. Held board draws "Next: Resolve both rows, then the schedule is prepared again." as a sentence; the button label "Save and prepare again" carries it and no separate sentence is drawn.
9. Withdrawn board's "Exported adjustment: FLAGGED FOR FINANCE" has no field on the read or on the adjustment read. Not drawn.

## Questions
1. The adjustment review form (`POST /projects/{case_id}/accounting-adjustments/{adjustment_id}` needs `role`, a 1 to 50 character string; no read says which role string the server expects).
   - Option A (recommended): do not build the form now; the adjustment page is read only and shows the verdict as served. Ask the backend which `role` values are valid and who may send them (new backend question).
   - Option B: build the form with a role choice drawn from a list the backend supplies once it exists.
   - Option C: a free-text role field. Not recommended: it invents a value the server may treat as authority.
   - Context: readiness lists this write, but `role` has no source; the board's "Finance adjuster" panel is the only hint.
2. Source mappings (`POST .../accounting-sources/{source_id}/mappings`, `GET .../accounting-mappings/{mapping_id}`).
   - Option A (recommended): not built here; the adjustment's `source_id` is shown as read, and mappings belong with the ledger source and management accounts screens (SCR-58, SCR-53).
   - Option B: a "Map to accounts" control on the adjustment page.
   - Context: no read here gives a mapping id, and choosing which adjustments go into a mapping is a Finance accounts decision.
3. Combined export (Conflict 1).
   - Option A (recommended): kind choice first, one export per kind.
   - Option B: two kind buttons.
   - Option C: hold the export block.
   - Context: the board shows one adjustment of 7 mixed rows; the body takes one kind.
4. Partial duplicate settlement.
   - Option A (recommended): all `not_assessed` rows must be decided in one save.
   - Option B: allow a partial save of only the chosen rows, if the backend confirms it accepts partial `decisions[]`.
   - Context: the held board says "Resolve both rows" and the schedule "can't be approved while held".
5. Where the adjustment page lives.
   - Option A (recommended): a new route under `/projects/[caseId]/accounting-adjustments/[adjustmentId]`, linked from `exports[]`.
   - Option B: a side panel (Drawer) on the work item, no new route.
   - Context: no board draws an adjustment detail page; the export board ends at the button.
