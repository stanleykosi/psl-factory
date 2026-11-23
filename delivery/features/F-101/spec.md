# Income schedules: read the live schedule and record the review decision

> Tasks: FE-CONNECT-1 (line `income_schedules`, W-2701 to W-2712). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the recorded exception in `design/review.json` (D-173/D-181); screens: SCR-54 part 1 (boards `SCR-54-{desktop,mobile}-{investigating,held,review,returned,verified}`; the `export` boards are F-101B, the `withdrawn` boards are reached only through the `revoke` verdict below).

## Summary
- `/work/{id}` for an `income_schedules` item reads the live `GET /work/{work_id}/finance-schedule` through a new line adapter and draws stage, finding, income rows, the result, held duplicates and the returned rows with their reviewer's note.
- A reviewer records a decision with `POST /work/{work_id}/reviews` (kind `schedule`): approve, return, reject or revoke, offered only from `review_verdicts[]`, with a required evidence record and a note. This replaces the v7 `POST /tasks/{id}/decision` path for this line.
- "Reviewer not set" is drawn from `review_hold_code` (`reviewer_missing`, `review_rule_missing`) and nothing else. No reviewer name is invented.
- Not drawn: "Posted to ledger: NO" (no field), and all part 2 actions (correct and resubmit, settle a duplicate, export, accounting-adjustment pages, inventory coverage).
- Wait, not a blocker: the shared line adapter (F-85, lane C, PR #101) is not on main; the builder is held until it merges. This spec is written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.

## Context
Lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend` at origin/main (API 1.24.0).
- Frame: `src/features/workspace/` (`Workspace.tsx`, `Sections.tsx`, `Steps.tsx`, `StepForm.tsx`, `InlineDecide.tsx`, `proposals.ts`, `useWorkspaceStep.ts`, `labels.ts`). After F-85: `adapter.ts` (`LineAdapter`, `CommandDescriptor`, `registerLineAdapter`, `adapterFor`), `EvidencePicker.tsx`, `evidence.ts`, and the live `/work/[id]` page in `src/features/work-item/`. Lane C owns these; this feature does not edit them.
- The v7 build (F-33): fixtures `mock/fixtures/work/W-2701` to `W-2711` and `mock/workspace.mjs`; the review was `InlineDecide.tsx` through `useDecision` (`src/features/decide/`). That path is not used for the live item.
- Live read `GET /work/{work_id}/finance-schedule` (viewer: `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/work/{work_id}/finance-schedule 3`). Required fields: `expected_revision`, `case_revision`, `schedule_id|null`, `kind` (`income|inventory`), `stage`, `finding`, `duplicates[]` (strings), `returned{review_id, rows[{key, relationship}]}|null`, `review_id|null`, `review_verdicts[]`, `can_export`, `review_hold_code` (`review_rule_missing|reviewer_missing|null`), `evidence[{id, version, kind}]` (max 35), `exports[{id, kind, adjustment_id}]`, `income|null`, `inventory|null`, `result|null`.
  - `income`: `entity, period (YYYY-MM), currency, report_line, source_unit, target_unit, rows[{key, relationship, amount (string|null), unit, source_accounts[], evidence_id, duplicate_state (not_assessed|already_represented|separately_justified), duplicate_resolution_evidence_id|null, adjustment_lines[{account, amount}]}]` (1 to 100 rows).
  - `result`: `status` (`ready|held`), `findings[]`, `adjusted_total`, `parent_amount`, `additive_total`, `reclassification_total`, `target_unit`, `coverage`, `complete_inventory`, `missing_required[]`, `included_schedules[{key, included, gaps[]}]`; money fields are strings or null.
  - `inventory`: `workbook_evidence_id, coverage (partial|declared_complete), schedules[{key, purpose, owner_id, dependencies[], source_evidence_ids[], formula_evidence_ids[], manual_cell_evidence_ids[], consumer_refs[], restricted, validation_package_id, gaps[]}]`.
- Live write `POST /work/{work_id}/reviews` variant `kind: "schedule"`: `{kind, expected_revision, case_revision, target_id, verdict (approve|return|reject|revoke), evidence_id, note}`, all required; `note` is a string up to 4000 characters. Answers 200 `{work_id, state, revision, review_id|null}`; errors 400, 401, 403, 404, 409, 413, 415, 422, 429, 503. E-21 and E-22 (`/Users/Hunchoo/psl-factory/delivery/connect/backend-answers.md`, `### SCR-54`) settle the variant, the evidence rule and the hold code.

## Contract

### Adapter (this feature's mapping)
New file `src/features/workspace/incomeSchedulesAdapter.ts` (registered as panel key `income-schedules`, the key the work item's `panels[]` carries for this line; if the live work item carries a different key for `line: income_schedules`, use that key and say so in the build note), built to F-85's `LineAdapter` interface. `read` is `GET panel.url` (the finance-schedule URL); `sections` draws the parts below with existing section kinds; `commands` returns one descriptor `income-schedules.review` (method POST, url `/api/v1/work/{id}/reviews`, tokens `expected_revision` and `case_revision` from the read body, `idempotency.field: null`, `body()` adds `kind:"schedule"`, `target_id`, `verdict`, `evidence_id`, `note`, `disabledReason` from the read). The adapter registration is the only line of wiring in the shared frame; if F-85 gives no other way to register than editing `src/features/workspace/*`, name that as a dependency on lane C and do not edit the frame. The review form is a component in this feature's own files (see Lanes) rendered through the adapter's section for the decision.

Tokens come from the finance-schedule body (`expected_revision`, `case_revision`), not from `GET /work/{id}`; a `null` token is passed on as `null`, never 0. The review `target_id` is the body's `schedule_id` (Assumption 1).

### Read mapping (presentation only; nothing here decides access)
| Page part | Source |
|---|---|
| Stage and finding sentences | `stage`, `finding` as returned |
| Schedule header | `income.entity`, `income.period`, `income.currency`, `income.report_line`, `income.source_unit` to `income.target_unit` |
| Income rows table (key, relationship, amount, unit, source accounts, duplicate state) | `income.rows[]`; relationship words Disaggregation / Reclassification / Additive; `amount` null shows "Unknown", never 0; amounts are the backend's strings formatted by `formatAmount` (`src/components/format.ts`), no float arithmetic; `adjustment_lines` are not drawn |
| Result | `result.status` as a tag (`ready` "Ready", `held` "Held"); `adjusted_total`, `parent_amount`, `additive_total`, `reclassification_total` as money (null shows "Unknown"); `findings[]` and `missing_required[]` as listed lines with the code text as returned (lightly capitalised, the unknown text never dropped); `result` null draws no result block |
| Held duplicates | `duplicates[]`: one line per string as returned, under a "Possible duplicates" heading, read only. When `duplicates` is empty the heading is absent |
| Returned rows and reviewer's note | `returned.rows[]` (key, relationship). The note text is NOT on this read (only `returned.review_id`); the page says "Returned for correction" with the row list and shows no quoted note unless a note field exists on the read at build time (Questions 2) |
| Reviewer not set | `review_hold_code` `reviewer_missing`: "Nobody is set to review schedules yet. The review starts when an admin sets who reviews schedules." `review_rule_missing`: "The schedule review rule isn't set up yet. The review starts when an admin sets it up." No Decide panel, no reviewer name, no Setup link. The wording is frontend copy (Assumption 4) |
| Decide panel | shown only when `review_id` is not null, `review_hold_code` is null and `review_verdicts[]` is not empty; one button per verdict in `review_verdicts[]` in the order approve, return, reject, revoke, labelled Approve, Return, Reject, Withdraw approval; an unknown verdict string from the API gets no button |
| Verified or finished state | the work item header tag from `GET /work/{id}` (`state`); the page never decides "verified" from this read |
| Exports | `exports[]` and `can_export`: not drawn (F-101B) |
| Evidence | `evidence[]` feeds the evidence choice in the review form only |
| Inventory kind | when `kind` is `inventory`: stage, finding, `inventory.coverage` as "Partial" or "Declared complete", and `inventory.schedules[]` as key, purpose and `gaps` lines, read only; no actions, no coverage claim beyond the returned value. `restricted: true` schedules show their key only |

Not drawn, with no placeholder: "Posted to the ledger: NO" (D-182; the read has no field. Say so in the build note), "Verification scope", "Prepared by" and "Approved by ... 13 NOV" (no fields on this read), the correct-and-resubmit step, the duplicate-settlement board, the Export board, and the v7 agent card steps.

### Review decision
- Request: `POST /api/v1/work/{work_id}/reviews`, header `X-CSRFToken` from the shared client, body:
  `{"kind":"schedule","expected_revision":<n>,"case_revision":<n>,"target_id":<schedule_id>,"verdict":"approve|return|reject|revoke","evidence_id":<id>,"note":"<text>"}`.
- The form: a required evidence choice (a select of `evidence[]` rows, each shown as its kind and "version N"; see Assumption 2), a Note field (Note is required for every verdict in the schema's required list; the page requires 1 to 4000 characters after trimming, checked before any request), and the verdict buttons. The buttons are disabled with "Choose the evidence this decision rests on." until an evidence row is chosen and "Add a note." until a note is typed. Approve also needs both (E-21).
- Evidence is never typed by hand and never an `upload_id`; `EvidenceId` and `UploadId` stay distinct types from F-85. If `evidence[]` is empty the form shows "There is no evidence on this schedule to cite, so a decision can't be recorded yet." and no button.
- One write at a time; the buttons are disabled while it runs. Success (200): re-read `GET /work/{id}` and the finance-schedule; the page shows the new state from the re-read, never from the write's own body. No optimistic state.
- Idempotency: the route has no key field (`idempotency.field: null`). A press is sent once and never retried automatically. After a network failure or 5xx/503 the form says "We couldn't confirm whether your decision was recorded. Check the schedule before trying again." and re-reads both resources; buttons stay disabled until the re-read returns. If the re-read shows `review_id` null or `review_verdicts` empty, the decision stands; otherwise the person may press again.
- Versioning: 409 means the schedule changed; the page says "This schedule changed while you were reading it, so nothing was recorded." and re-reads (the person's note and chosen evidence stay in the form).
- Errors: 400/422 show the first `fields[].message` (else `message`) next to the form; 401 signed-out state with `/sign-in?next=<path>`; 403 `csrf_failed` refreshes the session and says "Press the button again" (nothing was sent); other 403 "You can't review this schedule."; 404 "This record is unavailable." (the same words for missing and not yours); 413/415 "That request couldn't be sent."; 429 and 503 "Try again shortly."; network "We couldn't reach the server."
- Permission and tenant: the backend decides (separation of duties, role, case access). The page shows controls only from `review_verdicts[]` and `review_hold_code` as returned; no client-side role check, no `/me` read. The `target_id` and tokens are never typed by the person. A forbidden or hidden schedule shows no title, no figure and no further call.

### Screen states
- Loading: existing `WorkItemStates` loading while either read is in flight; the section list for this line shows a loading row.
- Empty: `income` null and `result` null (nothing read yet): show stage and finding only.
- Error: finance-schedule read errors map as above with Try again (reads only); a failed finance-schedule read leaves the work item header visible.
- Success: the read mapping above, per board state: investigating (`stage`/`finding`, rows, no Decide panel, `review_id` null), held (`result.status: held`, `missing_required`, duplicates), review (Decide panel), returned (returned rows), verified (header tag from `state`, no Decide panel since `review_verdicts` is empty), reviewer-not-set (hold code).
- Polling: follows the work item page (F-85): re-read while `current_activity.watching` or `state === 'processing'`; the finance-schedule read is re-read with it.

### Fixtures (mock serves live-shaped bodies for numeric ids; `W-xxxx` v7 ids unchanged)
Builder creates mock fixtures; the shapes are the contract, numbers are free:
- `4201` investigating: `kind:"income"`, `stage`, `finding`, `income` with 3 rows (one `amount:null`), `result:null`, `review_id:null`, `review_verdicts:[]`, `review_hold_code:null`.
- `4202` held: `result.status:"held"`, `missing_required:["report_line"]`, `duplicates:["Row 7 may repeat row 3"]`.
- `4203` review: `review_id:41`, `review_verdicts:["approve","return","reject"]`, `schedule_id:9`, `evidence:[{id:61,version:1,kind:"document"}]`, `expected_revision:5`, `case_revision:12`.
- `4204` returned: `returned:{review_id:40, rows:[{key:"row-12",relationship:"disaggregation"}]}`.
- `4205` verified: `review_id:null`, `review_verdicts:["revoke"]` (the Decide panel offers only Withdraw approval).
- `4206` reviewer not set: `review_hold_code:"reviewer_missing"`, `review_verdicts:[]`.
- `4207` inventory: `kind:"inventory"`, `income:null`, `inventory.coverage:"partial"`.
- Mock `POST /work/4203/reviews`: 200 `{work_id:4203,state:"verified",revision:6,review_id:41}` for a valid body (it validates all seven fields and 422s a missing `evidence_id` or `note`), 409 once when asked by scenario, `?scenario=` for 403 `csrf_failed`, 429, 503 and a dropped connection. `4299`: 404 for any caller.

## Lanes
- Frontend lane (owner): `frontend/src/features/workspace/incomeSchedulesAdapter.ts`, `workspace/IncomeScheduleReview.tsx` (the review form) and tests next to them; the live finance-schedule types in `frontend/src/api/types.ts` (generated from `live-schema.d.ts`, no hand-written shape); `frontend/mock/**` (live-shaped finance-schedule and reviews routes and the fixtures above); `frontend/e2e/income-schedules.spec.ts`; fixture edits for the fidelity exceptions this feature needs.
- Backend lane: none. No backend, migration or contract change.
- Integration owner: lane D coordinator. Shared files: `src/features/workspace/{adapter.ts,Workspace.tsx,Sections.tsx,labels.ts,EvidencePicker.tsx,evidence.ts}`, `src/features/work-item/**`, `src/api/*` belong to lane C (F-85); this feature only adds files beside them and calls `registerLineAdapter`. A frame change is a dependency on lane C, named in the build note.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4203` (Next 4990, mock 4991) shows the stage and finding, the income rows with their amounts, the result block and the Decide panel with exactly Approve, Return and Reject buttons — verify: open the page; `frontend/e2e/income-schedules.spec.ts`.
2. Against live Django (8030) a real `income_schedules` work item shows the same stage, finding, row keys and result totals as `GET /api/v1/work/{id}/finance-schedule` — verify: compare the page with `curl` JSON using the session.
3. A row with `amount: null` and a result total of null show "Unknown", never 0 or an empty cell — verify: `/work/4201` and a unit test on the row mapper.
4. The page performs no arithmetic on money: no total, difference or count is computed (`grep` for `parseFloat|Number(` on amounts in the new files returns nothing) — verify: grep and code review.
5. The Decide panel shows only the verdicts in `review_verdicts[]`: `4203` shows three buttons, `4205` shows only "Withdraw approval", `4201`, `4204` and `4206` show none; an unknown verdict string draws no button — verify: unit test and e2e.
6. With `review_hold_code: "reviewer_missing"` (`4206`) the page says nobody is set to review schedules and shows no Decide panel, reviewer name or Setup link; `review_rule_missing` shows its own sentence — verify: e2e and unit test on both codes.
7. A decision is not sent without a chosen evidence record and a note; Approve is no exception, and the buttons stay disabled with the reason shown — verify: unit test asserts no fetch call; e2e tries Approve with each missing.
8. Pressing Approve on `4203` with evidence 61 and a note sends exactly one `POST /api/v1/work/4203/reviews` with `{kind:"schedule", expected_revision:5, case_revision:12, target_id:9, verdict:"approve", evidence_id:61, note}` and the `X-CSRFToken` header — verify: network panel and unit test on `body()`.
9. After a 200 the page re-reads and shows what the re-read says; it does not show "verified" from the write response alone — verify: mock where the re-read returns the old state; unit test.
10. A 409 shows "This schedule changed while you were reading it, so nothing was recorded", re-reads, and keeps the person's note and evidence choice — verify: mock scenario.
11. A dropped connection or 503 after the press shows the unconfirmed notice, keeps the buttons disabled until the re-read returns, and sends the decision once only — verify: mock scenario; count POST calls.
12. A 403 `csrf_failed` refreshes the session once, says to press again, and does not show the no-access state or retry by itself — verify: mock scenario; count calls.
13. A 404 on the read or the write shows "This record is unavailable." with the same words for a missing and a not-yours schedule (`4299`), no title and no further call — verify: both cases side by side.
14. A 422 with `fields[]` shows the first field message next to the form and keeps the input — verify: mock scenario.
15. `evidence[]` empty shows the "no evidence to cite" message and no buttons; the evidence select offers only `evidence[]` rows and the page has no file input or free-text evidence id — verify: component test.
16. `4204` shows the returned rows and "Returned for correction" and no correct-and-resubmit control; no quoted note appears unless the read carries one — verify: e2e; grep the new files for `correct_and_resubmit` and `liveApi.POST` (only the reviews call).
17. `duplicates[]` lines are shown read only under "Possible duplicates"; there is no settle control — verify: `4202` e2e.
18. An `inventory` item (`4207`) shows coverage as returned and its schedules read only with no button; an `income` read draws no inventory block — verify: e2e.
19. "Posted to the ledger", "Export as an adjustment" and "Withdraw approval" text for export appear nowhere except the revoke button, and the build note says "Posted to ledger: NO" is hidden because the read has no field — verify: grep of the new files; `build.md`.
20. A hold code or verdict list is never invented: with `review_hold_code: null` and `review_verdicts: []` (`4205` without revoke) the page shows no panel and no "reviewer not set" text — verify: unit test.
21. Viewport check at 1440 and 390 against the SCR-54 investigating, held, review, returned and verified boards: parts that remain match; hidden parts leave no empty heading or gap — verify: screenshots at both widths against `design/screens.md` SCR-54.
22. New tests exist for the adapter's `sections` and `commands` (including null tokens staying null), the note and evidence gate, and each error mapping — verify: `delivery/checks.sh` runs them green, with `api-live-schema-drift` still passing.

## Out of scope
- Correct and resubmit, settle a duplicate, export as an adjustment, `accounting-adjustments` pages, source mappings and the inventory kind's actions and coverage claims (all F-101B).
- The v7 `POST /tasks/{id}/decision` flow and `InlineDecide` for this line.
- Changes to `src/features/workspace` shared files, `src/features/work-item/**` and `src/api/*` (lane C).
- File upload or `fileToEvidence` for the review; creating evidence records.
- Reading a reviewer note from anywhere but the finance-schedule body; a Setup link; naming reviewers.
- New business rules, approvers or computed totals; backend, migrations, contract edits.

## Assumptions
1. `target_id` is the read's `schedule_id`. The reviews body names `target_id` and the read has `schedule_id` and `review_id`; the schedule is the exact subject. If `schedule_id` is null the Decide panel is not shown.
2. The evidence choice is a pick from `evidence[]` on the read, not an upload. The picker from F-85 only yields an `upload_id`, and its path to an evidence id is an unconfirmed proposal.
3. Note is required for every verdict, including Approve. The schema lists `note` as required for the schedule variant; the empty string is not asserted to be valid.
4. The "reviewer not set" and "rule not set" sentences are frontend copy keyed on the hold code. The read has no sentence, and the v7 sentence is on the board's held state.
5. The panel key `income-schedules` is the work item's `panels[].key`; confirm against a live work item and use the real key.
6. The finance-schedule read is polled with the work item, not on its own timer, so there is one polling rule per page.
7. Mock ids 4201 to 4207 are free numbers; the v7 `W-27xx` fixtures stay for pages not yet moved.

## Conflicts with the boards
1. Boards draw "Posted to the ledger: NO", "Verification scope: THESE 38 ROWS ONLY", "Prepared by" and "Approved by ... 13 NOV" on the verified state; the read supplies none of these. Hidden (D-182).
2. Boards draw the Decide panel with Approve, Return and Reject and a note needed only for return and reject; live requires an evidence record and a note for every verdict, including Approve, and offers Withdraw approval from `review_verdicts[]`. The panel gains an evidence choice and a note that is always required.
3. Boards draw the reviewer's quoted note on the returned state; the read carries `returned.review_id` and rows only. The quote is not drawn.
4. The review-state board draws "You didn't prepare it, so you can review it."; there is no basis sentence on the read. Not drawn.
5. Boards draw the returned state's "Correct and resubmit" form and the held board's duplicate settlement; both are F-101B and absent here, so the returned board shows no action.
6. The agent card with steps and sources is not drawn on the live item (F-85, LC-Q1).

## Questions
1. Evidence on the review form (boards draw only a Note).
   - Option A (recommended): a select of the schedule's own `evidence[]` rows, labelled by kind and version, placed above the Note.
   - Option B: hide the Decide panel until lane C confirms the upload-to-evidence path (F-85 backend question 1) and use the picker.
   - Context: live requires `evidence_id` for every verdict (E-21), and the picker returns only an upload id.
2. The reviewer's note on a returned schedule (board quotes it; the read has no text field).
   - Option A (recommended): show the returned rows only and no quote; ask the backend whether `returned` can carry the note (new backend question).
   - Option B: show "Returned for correction. See the review history" linking to `/work/{id}/history`.
   - Context: history rows carry `reason` for decisions, but not a link to this return.
3. Note on Approve (the board shows the note needed only for return and reject).
   - Option A (recommended): require a note for every verdict, as the schema's required list reads.
   - Option B: send an empty string for Approve; risk: the backend may reject it with 422.
   - Context: confirm with a live approve in the acceptance run before choosing B.
4. Wording for the two hold codes (the board draws "Who reviews schedules: NOT SET").
   - Option A (recommended): the two sentences in the read mapping.
   - Option B: one sentence "Schedule review isn't set up yet" for both codes.
   - Context: the codes differ (no reviewer versus no rule); setup owners fix different things.
5. Withdraw approval is offered whenever the read lists `revoke`, which the board draws only on the withdrawn state.
   - Option A (recommended): offer it as a quiet secondary button on the verified state.
   - Option B: hide `revoke` in this part and take it with F-101B.
   - Context: readiness puts `revoke` in scope; the board has no Withdraw button on verified.
