# The cash forecast page lets the right person review, share, match actuals and recover a delivery, live

> Tasks: FE-CONNECT-1 (write side of W-4001..W-4013 and W-2004; part 2 of 2, part 1 is F-103). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0 or later. Design: approved 13 Nov canvas with the D-173/D-181 exceptions in `design/review.json`; screens: SCR-56 (review, group-rows, group-review, actuals, uncertain; desktop and mobile; `design/canvas/finance/project/SCR-56-*.dc.html`). Builds on F-103 (`/Users/Hunchoo/psl-factory-main/delivery/features/F-103/spec.md`), F-85 and F-87; the build starts when all three are on main.

## Summary
- On the live `cash_forecast` work page the person can record a review verdict (approve, return, reject) on the forecast and on the group version, with a role, one evidence item and a note.
- They can choose group disclosure rows, fields and metadata only from the lists the read returns, and send the draft. They can record an actual and match it to an expected item, or leave it unmatched with a reason.
- On an uncertain delivery they first record what happened (delivered, not delivered, or unknown, with proof), and only then retry or cancel a job the read says can be retried or operated.
- Every form is `ForecastActions.tsx`, registered as the forecast adapter's `Actions` slot and sending through F-87's `useWorkCommand`. Nothing is sent by loading, polling or navigating. Unknown money stays unknown; no staff name or individual pay is drawn or offered.
- Withdraw, post and the restart form are held (no contract route or no readable input; see Questions 2 and 3).

## Context
Where this lives after F-103 is on main (worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`):
- `frontend/src/features/forecast/forecastAdapter.ts` (F-103) registers the read-only forecast adapter and returns no commands. F-103B adds `Actions` to it and descriptors in a new file. The forecast read (`GET /work/{id}/forecast`) supplies `expected_revision`, `case_revision`, `scenario_id`, `run_id`, `version_id`, `review_roles[]`, `audience`, `jobs[]`, `disclosure`, `observation`, `can_restart`, `restart_policy_id`, `matches[]`; the month read supplies `rows[]`, `actuals[]`, `history[]`.
- F-85: `workspace/adapter.ts` (`LineAdapter`, `CommandDescriptor`, `makeCommand`), `workspace/EvidencePicker.tsx` and `evidence.ts` (`UploadId` and `EvidenceId` kept distinct; `fileToEvidence` is an unconfirmed proposal). F-87: `workspace/useWorkCommand.ts` (one write at a time, re-read after success, uncertain lock, error words), the `Actions?: ComponentType<LineActionsProps>` slot (`{ readback, ctx, commands, reload }`) rendered by `PanelView` under the panel's sections. F-89's `WeeklyReportActions.tsx` is the pattern.
- Live writes in contract 1.25.0, all with `X-CSRFToken` added by the shared client:
  - `POST /work/{id}/forecast` (201 `{work_id, state, revision, record_id}`), body is one of `action`: `review`, `group_review`, `actual`, `match` (this feature), and `priority`, `support`, `verify`, `unmatch` (not built here). There is no `withdraw` or `post` action in the union.
  - `POST /work/{id}/forecast/actuals/{month}` (201) leave unmatched `{expected_revision, case_revision, item_key, actual_id, reason}`.
  - `POST /work/{id}/forecast/disclosure` (201).
  - `POST /work/{id}/forecast/observations` multipart (200).
  - `POST /work/{id}/forecast/lifecycle` (200): `cancel`, `lookup`, `operate` (`job_id`, `operation` cancel|retry, `reason`), `restart`.
  - Errors on all: 400, 401, 403, 404, 405, 409, 413, 415, 422, 429, 500, 503; `{code, message, fields[]}` on 400/409/422.
- Backend answers: E-25 (read shapes), E-26 (group projection excludes staff names, individual pay and raw payroll input; a payroll-related assumption needs explicit inclusion and review on that exact projection).

## Contract

### Shared form rules
- Tokens: every body takes `expected_revision` and `case_revision` as read from the forecast readback (`ctx`), `null` kept as `null`. If either is null the form sends nothing and shows its disabled reason ("This page can't be changed until it has finished loading"). Until TECH-1-1 lands, neither revisions nor any idempotency key go into `inputs` to `makeCommand`; the descriptor reads them from `ctx`. The one exception is `operation_key` on match (see Assumptions): it is a field of the body that the contract defines, built inside `body()`.
- Roles: the `role` of a review is chosen from the read's `review_roles[]` only. One entry is shown as fixed text; several are a select with nothing preselected; none means no review control is drawn (no "reviewer not set" warning, D-182). The page never lists roles from the contract enum for a verdict.
- Evidence (binding, PSL answer 1 and D-1): the verdict, the record-actual and the match forms need `evidence_id`. The forecast read lists none and these routes have no upload field, so the person picks from the evidence the work already holds: `GET /work/{id}/history?kind=evidence` rows that carry an `evidence_id` (F-85), each labelled by time, station and status, never by id alone. Nothing is preselected and the send button stays off when the list is empty or none is picked. A new file may be added through the F-85 `EvidencePicker` and `fileToEvidence` only where the list has nothing the person can use; that path is labelled "proposal, backend question 1, unconfirmed" in code and PR, and a `null` result means "not evidence yet" and keeps the button off. The page never invents an evidence id. See Question 1.
- Notes: every verdict sends `reason` (1 to 4000 characters, as the contract requires it for approve too).
- Sending: through `useWorkCommand` only. One write at a time, every button in `ForecastActions` disabled while one runs, a double click makes one request. On success the forecast read (and the month read if open) is reloaded and the words come from the re-read, never from the 201/200 alone. Errors use F-87's mapping (401 sign-in, 403 "You can't do this" with the server message, 403 `csrf_failed` "Press the button again", 404 "This record is unavailable.", 409 reload and "This changed while you were working. Showing the latest version.", 422 server message and first field message, 429/503 "Try again shortly", network/5xx uncertain: re-read, lock that command and say "We couldn't confirm that this happened. Check the page before trying again." until the revision changes or the page is reloaded). A failed send never clears what the person typed except after success.
- Group view: no field in any form offers a staff name, an individual pay figure or a payroll row unless the API lists that exact key in `row_keys`; the page labels only keys the API sent and adds nothing derived.

### 1. Review verdicts (`POST /work/{id}/forecast`)
Drawn when `review_roles[]` is non-empty, `result` is not null and `run_id` is not null. Audience `internal` or `management`:
```json
{ "action": "review", "expected_revision": 7, "case_revision": 12, "scenario_id": 3, "run_id": 41,
  "role": "Finance", "verdict": "approve", "evidence_id": 88, "reason": "Checked against the November bank statement." }
```
Audience `group` with a non-null `version_id` sends `{ "action": "group_review", expected_revision, case_revision, scenario_id, version_id, role, verdict, reason }` (no evidence field on that body, so no picker is drawn for it). Three buttons: "Approve forecast" / "Approve group version", "Return with a note", "Reject". The note box is always shown and always required (Conflicts, item 3).
Response 201 `{work_id, state, revision, record_id}`. Errors: 403 not the person's role or an independence rule (server message shown as given); 409 stale revision; 422 field errors. Idempotency: a new descriptor per press; after an uncertain failure the same press is not repeated without a re-read. Permission and tenant: the server decides; the page shows what comes back.

### 2. Record an actual and match it
Month actuals come from `GET /work/{id}/forecast/actuals/{month}` (F-103). Per row whose `status` is not matched, three actions:
- Record an actual: `{action:"actual", expected_revision, case_revision, scenario_id, evidence_id, lot_id:null}`. `lot_id` is always `null` (no lot list is supplied). The person picks the evidence (see rules). The page shows the new `actuals[]` entry from the re-read; it never computes an amount.
- Match: `{action:"match", expected_revision, case_revision, scenario_id, item_key, actual_id, amount, operation_key, evidence_id}`. `item_key` is the row's `key`. `actual_id` is chosen from the month read's `actuals[]` (nothing preselected). `amount` is typed as a decimal string; it is checked as a decimal only (`^\d+(\.\d{1,2})?$`), left exactly as typed, and never summed, rounded or defaulted from the row. A blank amount keeps the button off ("Unknown" is not a value that can be sent). `operation_key` is generated once per open form and replaced after a success or a re-read, so a retry of the same press carries the same key.
- Leave unmatched: `POST /work/{id}/forecast/actuals/{month}` `{expected_revision, case_revision, item_key, actual_id, reason}` with the month from the selected `?month=` and a required reason. A different person verifies actuals; `verify` is not built (Out of scope).
After success the month read and the forecast read are reloaded.
Fixture:
```json
{ "action":"match","expected_revision":7,"case_revision":12,"scenario_id":3,"item_key":"kola-receipt",
  "actual_id":5,"amount":"1000000.00","operation_key":"m-7f3c...","evidence_id":88 }
```

### 3. Group disclosure (`POST /work/{id}/forecast/disclosure`)
Drawn when `disclosure` is not null and `run_id` is not null. Body:
```json
{ "expected_revision":7,"case_revision":12,"run_id":41,"base_configuration":9,
  "rows":["rent","loan"],"fields":["kind","amount"],"metadata":["entity"],"recipients":[3,4],
  "reviewer_roles":["Finance"],"publisher_roles":["Finance"],"allow_preparer_review":false,
  "oracle":14,"decision":15,"effective_from":"2026-11-30T09:00:00Z" }
```
- `base_configuration` is `disclosure.configuration_id`. `rows` are tick boxes only from `row_keys[]`; `recipients` only from `recipient_ids[]`; `oracle` and `decision` are one-of lists from `oracle_choices[]` and `decision_choices[]` (nothing preselected, labels only as the API sends them). Pre-ticked state is the read's `selected_rows`, `selected_fields` and `selected_metadata`, as the group's current version.
- `fields` are offered only from the contract list (`kind, amount, expected_on, original_due, commitment, residual, matched`) and `metadata` only from (`entity, currency, basis, as_of`); this closed list is the E-26 projection, so no pay or staff field exists. A payroll row appears only if its key is in `row_keys`, and is then shown by its key text.
- `reviewer_roles` and `publisher_roles` are chosen by the person from the contract's role list with nothing preselected and at least one each; `allow_preparer_review` is an unticked box; `effective_from` is a date-time the person enters. The page proposes no approver. See Question 3.
- "Save rows" and "Send for group review" are one press: it sends the draft and the server moves it to group review. The page says "Sending this for review does not send anything to the group." (the board's "What happens next" line, only as far as it is true; nothing else about next steps is drawn).
- Response 201. Errors: 409 stale (reload, selections kept), 422 shows field messages next to the matching control (`fields[].name` mapped to the control, unmapped ones listed above the form).

### 4. Record what happened (`POST /work/{id}/forecast/observations`, multipart)
Drawn per job whose status the API shows as not finished, or when `observation.outcome` is `unknown`, and the person may act (server decides). Fields: `expected_revision`, `case_revision`, `job_id`, `outcome` (`delivered`, `not_delivered`, `unknown`; all three visible, "I can't tell yet" for `unknown`, nothing preselected), `proof` (file). A file is required for `delivered` and `not_delivered` and optional for `unknown`; the multipart is built with `FormData`, the file name and size are shown after choosing, and the file is not previewed. The proof is the action's own upload field, so no evidence picker is drawn here. Response 200 `{work_id,state,revision}`. A recorded observation never resends anything; the form says so. After success the page shows the recorded outcome and "Proof on file" from the re-read.

### 5. Retry and cancel (`POST /work/{id}/forecast/lifecycle`)
Drawn per job: "Retry" when that job's `can_retry` is true, "Cancel delivery" when its `can_operate` is true. Body `{ "action":"operate", "expected_revision":7, "case_revision":12, "job_id":2, "operation":"retry"|"cancel", "reason":"..." }`. Rules:
- The recorded state is shown first, in the form: the job's status, the observation outcome and proof line, "Nothing has been resent from this page."
- When `observation` is null, both buttons are off with "Record what happened first." (the uncertain-effect order). When it is recorded as `delivered`, retry is off with "It was recorded as delivered." (it would send a second copy); cancel follows `can_operate`.
- Each press opens a confirm step that names the action and the job and needs the typed reason; only the confirm sends. No attempt count, remaining retries or cost is shown, because the read carries none.
- `can_restart` and `restart_policy_id` stay the read-only line from F-103. No restart control is drawn (Question 2). `lookup` and the whole-work `cancel` action are not built.
- Response 200. 409 stale re-reads and shows the new state; 422 shows the server message.

### Screen states
- Loading: F-103's loading state; no form is drawn until the readback is present.
- Empty: nothing to act on draws no action area and no heading (a review with `review_roles: []`, a read with no jobs, no `disclosure`, a month with no rows). An empty evidence list draws "No evidence is on file for this work yet." with the buttons off.
- Error: per the shared rules; field errors beside the control; a failed send keeps the typed values.
- Success: "Done." plus the state words from the re-read; the form closes and the sections update. Nothing is shown as done until the re-read confirms it.
- Uncertain send (network/5xx): the lock above; the person is told to check the page, and the form is not re-armed until the revision changes.
- At 390 px every form is one column, buttons stack and are at least 44 px high, and the confirm step is a full-width sheet; the periods table keeps scrolling only inside its own region.

### Fixture examples (mock serves live shapes for numeric ids; new files only)
- `4302` (F-103 review) gains `review_roles:["Finance"]` handling and evidence rows in `history?kind=evidence`: `[{at,station,status,evidence_id:88},{...,evidence_id:89}]`; the mock accepts the review body and returns 201 and a changed `revision`, or 409/422/403 scenarios by a header or a magic reason text the e2e sets.
- `4308` group review: `audience:"group"`, `version_id:51`, `review_roles:["Finance"]`.
- `4309` disclosure draft: `disclosure` with `row_keys:["rent","loan","payroll-cash"]`, `oracle_choices`, `decision_choices`, `recipient_ids:[3,4]`; the mock also serves a variant whose row objects carry a staff name and a pay figure (neither may be drawn).
- `4305` (F-103 uncertain) is the recovery fixture: observation null variant (retry/cancel off) and `unknown` variant (retry/cancel on, `can_retry:true`, `can_operate:true`, `can_restart:true`).
- Month read `2026-11` with a row needing a match and an actual with a null amount.

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/forecast/ForecastActions.tsx`, `ReviewForm.tsx`, `DisclosureForm.tsx`, `ActualsForms.tsx`, `RecoveryForms.tsx`, `forecastCommands.ts` (descriptors and body builders), `useForecastEvidence.ts`, tests under `frontend/src/features/forecast/`; the `Actions` registration line in `forecastAdapter.ts` (file created by F-103; edited here only after F-103 is on main); mock write routes and fixtures `frontend/mock/**` for ids 4302, 4305, 4308, 4309 and the month read (new files; v7 `W-4001..W-4013` fixtures kept); `frontend/e2e/cash-forecast-writes.spec.ts` (new).
- Backend lane: none. No backend change; no contract edit.
- Integration owner: lane D coordinator. Shared files: `src/features/workspace/*` and `src/features/work-item/*` belong to lane C and are not edited here; `adapter.ts`'s `Actions` slot, `useWorkCommand`, `EvidencePicker` and `fileToEvidence` are used as they are; a needed frame change is a named dependency on lane C. Any change to `frontend/mock/finance*` or the payments fixtures is named in build.md for lane B.
- Protected paths in `delivery/config.json` (`delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`) stay unchanged.

## Acceptance criteria
1. On `/work/4302` (mock, Next 4990, mock 4991) with `review_roles:["Finance"]` the Approve, Return and Reject buttons are off until an evidence item and a note are given; with an item picked and a note typed, Approve sends one `POST /api/v1/work/4302/forecast` whose body has `action:"review"`, `role:"Finance"`, `verdict:"approve"`, the picked `evidence_id`, `reason`, `scenario_id`, `run_id`, and `expected_revision`/`case_revision` as read — verify: e2e asserts the request body and that exactly one request was made.
2. Nothing is preselected: the evidence list and any role select start empty, and with an empty evidence list the page says "No evidence is on file for this work yet." and every send button is off — verify: e2e on a fixture with no evidence rows; unit test on the form state.
3. With `review_roles: []` no review control and no "reviewer not set" text is drawn at 1440 or 390 — verify: e2e text and role search on both widths.
4. A null `expected_revision` or `case_revision` blocks every send with the disabled reason and makes no request; `null` is never sent as 0 — verify: unit test on `forecastCommands.ts` for all five action areas; e2e asserts zero POSTs.
5. Return and Reject need a non-empty note; so does Approve (contract) — verify: unit test that an empty or whitespace note keeps all three off; body carries the note verbatim.
6. On `/work/4308` (`audience:"group"`) the verdict sends `action:"group_review"` with `version_id` and no `evidence_id` — verify: e2e body assertion.
7. A 409 on a verdict re-reads the forecast, shows "This changed while you were working. Showing the latest version." and does not resend; a 403 shows "You can't do this." plus the server message and leaves the page as read; a 422 shows the server message and first field message; a wrong-tenant 404 shows "This record is unavailable." — verify: mock scenarios, e2e and the `useWorkCommand` error unit tests.
8. A double click on Approve makes one request and every button in the action area is disabled while it runs — verify: e2e counts requests.
9. A network failure on a verdict re-reads the page, says "We couldn't confirm that this happened. Check the page before trying again.", and keeps the buttons off until the revision changes or the page is reloaded — verify: e2e with the mock dropping the connection; unit test.
10. The month form for `2026-11` offers match only for rows not already matched; Match needs an evidence item, an `actual_id` chosen from the month read's `actuals[]`, and a typed decimal amount; the body carries `item_key`, `actual_id`, the amount exactly as typed, `operation_key` and `evidence_id` — verify: e2e body assertion; unit test that `"abc"`, `"1,000"`, an empty amount and `"-5"` keep the button off.
11. The page never fills or computes an amount: with a row `expected: "1500000.00"` and an actual of `"1000000.00"` the amount field starts empty and no sum, difference or "remaining" figure appears; an actual with a null amount reads "Unknown" and cannot be picked for a match — verify: e2e and unit test.
12. Retrying the same match press after an uncertain failure sends the same `operation_key`; after a re-read or success a new one is generated — verify: unit test on the form state.
13. Leave unmatched sends `POST /api/v1/work/{id}/forecast/actuals/2026-11` with `item_key`, `actual_id`, `reason`; an empty reason keeps it off — verify: e2e and unit test.
14. After a successful match or unmatch the month read and the forecast read are both re-requested and the row shows the state from the re-read; the page never shows "Matched" before the re-read — verify: e2e network order on a mock that changes state only after the POST.
15. The disclosure form offers rows only from `row_keys`, recipients only from `recipient_ids`, one `oracle` from `oracle_choices`, one `decision` from `decision_choices`, `fields` and `metadata` only from the contract lists; the poisoned fixture (staff name and pay in a row object) draws neither the name nor the pay figure, and no payroll key is selectable unless it is in `row_keys` — verify: e2e on `4309` asserts DOM text and the checkbox set; unit test on the choice mapper.
16. "Send for group review" stays off until at least one row, one field, one recipient, an oracle, a decision, at least one reviewer role, at least one publisher role and an `effective_from` are chosen; `allow_preparer_review` starts unticked; the body matches the contract with `base_configuration` equal to `disclosure.configuration_id` — verify: e2e body assertion; unit test on each missing input.
17. A 422 on disclosure puts the first `fields[].message` beside the matching control and the rest above the form; a 409 re-reads and keeps the ticked choices — verify: mock scenarios, e2e.
18. Nothing is sent to the group by the disclosure form: the page text says "Sending this for review does not send anything to the group." and no request goes to any route other than `POST .../forecast/disclosure` and the re-reads — verify: e2e request log.
19. On `/work/4305` with `observation: null` Retry and Cancel delivery are off with "Record what happened first." and "Record what happened" shows delivered, not delivered and "I can't tell yet" with nothing preselected — verify: e2e.
20. Recording `delivered` or `not_delivered` without a file keeps Record off; `unknown` can be sent without one; the request is `multipart/form-data` with `job_id`, `outcome`, `expected_revision`, `case_revision` and `proof` as the field name; the file is not previewed — verify: e2e inspects the multipart body.
21. After an `unknown` observation, with `can_retry:true`, Retry opens a confirm step that shows the recorded state and "Nothing has been resent from this page."; only the confirm sends `{action:"operate", operation:"retry", job_id, reason, ...}` and it needs a reason; Cancel delivery does the same with `operation:"cancel"` — verify: e2e on both; unit test on the body builder.
22. Retry is off for a job with `can_retry:false`, Cancel delivery is off for `can_operate:false`, and retry is off after a `delivered` observation; no attempt count or "retry once" wording appears — verify: e2e on four job variants; text search.
23. No restart control is drawn when `can_restart` is true: the F-103 line "Restart allowed under rule {id}" stays text — verify: e2e on 4305.
24. Group view shows no staff name or individual pay anywhere, including inside any form, and the page makes no request to a `payroll` URL — verify: e2e on the poisoned fixture asserts DOM text and the request log.
25. A page load, a month change and a navigation make no POST, PUT, PATCH or DELETE; every write comes from a press — verify: e2e records methods across all fixtures; `grep -rn "liveApi.POST" frontend/src/features/forecast` shows hits only in `forecastCommands.ts` or the shared `useWorkCommand` path.
26. `ForecastActions` is the adapter's `Actions` slot, rendered under the forecast panel's sections inside its error boundary; a thrown error in a form leaves the F-103 sections on screen; nothing under `frontend/src/features/workspace` or `work-item` changed — verify: unit test; `git diff --stat origin/main -- frontend/src/features/workspace frontend/src/features/work-item` shows no lines.
27. At 1440 and 390 the forms match the SCR-56 boards for the parts kept (Decide panel and note, group rows, group review decide panel, actuals Match action, uncertain Record what happened and Cancel/Retry), hidden parts leave no empty heading or gap, controls are at least 44 px high at 390 and axe WCAG 2.2 AA has no violations on 4302, 4305, 4308 and 4309 — verify: screenshots at both widths against the artboards; axe.
28. New tests exist and run: unit tests for each body builder, the form states, the evidence list mapper, the disclosure choice mapper and the observation multipart builder; one e2e file for the scenarios above — verify: files exist and run in `npm test` and `npm run e2e`; `delivery/checks.sh` passes.
29. The v7 forecast pages `W-4001..W-4013`, `e2e/cash-forecast.spec.ts` and F-103's `e2e/cash-forecast-live.spec.ts` still pass; F-103's "no write" criterion is replaced by criterion 25 here — verify: run the three specs.

## Out of scope
- Everything F-103 reads and shows; any change to `src/features/workspace` or `work-item`, the frame, or the generic step engine.
- Withdraw and post (no action in the 1.25.0 contract, Question 2), the restart form (needs a selection the page cannot read, Question 2), `lookup`, whole-work `cancel`, and the actions `priority`, `support`, `verify` and `unmatch`.
- Building payroll detail, staff names or pay from any other read; offering any payroll row, field or amount the API did not list; any call to a payroll route.
- Inventing approvers, reviewer or publisher defaults, attempt counts, retry limits or amounts; computing, rounding or carrying forward any amount.
- Previewing or polling the proof file; resending a delivery from the page; an automatic retry after any failure.
- A "reviewer not set" warning; short phone money (D-182).
- Backend, migrations and contract edits. Changes to `frontend/mock/finance*` or the payments fixtures (named in build.md for lane B).
- The split into F-103C is only taken if the builder finds the recovery forms (sections 4 and 5) too large for one reviewable PR; the builder says so before building.

## Assumptions
- Evidence comes from `GET /work/{id}/history?kind=evidence` rows with an `evidence_id`, because the forecast read lists none and the review, actual and match routes have no upload field. Reason: PSL answer 1 allows picking from the evidence the work holds; no better list exists (Question 1).
- The role on a review is limited to the read's `review_roles[]`. Reason: the contract enum lists 23 roles, and offering all of them would let the page imply authority.
- `lot_id` is sent as `null` on record-actual. Reason: the read supplies no lot list and the field is nullable.
- `operation_key` for a match is generated in the form (one per open form, reused on a repeat of the same press). Reason: the contract requires it in the body and no source supplies it.
- Retry maps to the job's `can_retry` and Cancel delivery to its `can_operate`. Reason: the read names these two permissions per job and the board shows the two buttons; the server stays the judge.
- Retry and cancel are held off until an observation is recorded, and retry is off after a `delivered` observation. Reason: the readiness uncertain-effect order (record, then retry or cancel); a second send after "delivered" would be a duplicate. If the server allows more, the page is stricter, never looser.
- A proof file is required in the page for `delivered` and `not_delivered` and optional for `unknown`. Reason: the contract leaves `proof` optional; an outcome claim without proof is the weaker record and "unknown" has nothing to prove.
- Reviewer and publisher roles and `effective_from` on the disclosure are chosen by the person with nothing preselected, and `allow_preparer_review` starts off. Reason: the read does not list them; the safest default asks for no independence waiver and invents no approver (Question 3).
- Review controls show when `review_roles` is non-empty, `result` and `run_id` are not null; `group_review` is used when `audience` is `group` and `version_id` is not null. Reason: the read has no "can_review" flag; the server rejects what the person may not do.
- The disclosure send is one press (draft and send for review) with the board's "Save rows" label changed to "Send for group review". Reason: the route drafts against a reviewed run and there is no separate save route.
- Words for "Done", the confirm sheets and the empty evidence note are written in plain business language by the builder from the shared F-87 phrases. Reason: no board text exists for them.

## Questions
1. **Where does the evidence for a verdict, a record-actual and a match come from?** The forecast read lists none and those routes have no upload field. Options: (1, recommended) pick from `GET /work/{id}/history?kind=evidence` rows, with the F-85 `fileToEvidence` upload only as a flagged fallback; (2) hold these three forms until the backend adds an evidence list to the forecast read; (3) use `GET /work/{id}/proofs` (it lists `evidence_id`, but its kinds are PMO-oriented `pdf_copy` and `pmo_lead_note`). Recommendation 1: it needs no new route and invents no id. Backend question to log: "which read lists the evidence ids a forecast review may cite?"
2. **Withdraw, post and restart.** Readiness lists withdraw and post, but the 1.25.0 `POST /forecast` union has no such action; `lifecycle` `restart` needs a `configuration_id` and a full `selection` the page cannot read. Options: (1, recommended) hold all three and list them as backend questions (which action withdraws or posts; where the restart selection is read); (2) build restart with `configuration_id = restart_policy_id` and a selection copied from `result`; (3) drop them from the feature. Recommendation 1: option 2 would invent a rule.
3. **Who reviews and publishes a group forecast?** `POST disclosure` requires `reviewer_roles`, `publisher_roles` and `allow_preparer_review`, and the board says the group reviewer "isn't set yet". Options: (1, recommended) the person picks roles with nothing preselected and the preparer waiver starts off; (2) hold the disclosure form until PSL names the roles (policy configuration); (3) take the roles from `review_roles[]`. Recommendation 1 keeps the form usable and asserts no approver; the server still enforces. PSL may want option 2 since this is a payroll-adjacent group audience.
4. **Confirm steps.** Retry and cancel of a delivery are hard to undo. Options: (1, recommended) a confirm sheet with the typed reason; (2) the reason box alone; (3) a second approver. Recommendation 1 matches F-87's Cancel.

## Conflicts with the boards
1. Group rows board draws a fixed list (Closing cash by month, Receipts by month, Payments by month, Receipts by client, Payroll) and a single "Save rows". The spec adds fields, metadata, recipients, an oracle and a decision choice, reviewer and publisher roles, a preparer-review box and an effective date (all required by the 1.25.0 body), and offers only keys in `row_keys`; "Payroll" is shown only if the API lists it. Recommendation: accept; the design engineer should draw the extra controls.
2. Group review board shows "Rows 3 of 5", recipient and template and the "Group reviewer · not set" warning. Spec draws none of the warning, no template (no API field) and the row count only if both numbers come from the read. Recommendation: hide, per D-182.
3. Boards say a note is "needed to return, reject or withdraw". The contract requires `reason` on approve too, so the spec makes the note always required, and Withdraw is not drawn (Question 2). Recommendation: accept; update the board label to "Note (needed)".
4. Decide panel boards show the role as a heading ("Forecast reviewer", "Group reviewer") and no evidence control. Spec adds an evidence picker above the buttons (not for group review) and shows the role as read; the heading title uses the read's role name. Recommendation: accept the picker (PSL answer 1).
5. Actuals board draws only a "Match actual" button and a note. Spec adds "Record actual" and "Leave unmatched" forms with an evidence picker, amount and actual choice, and no remaining-balance figure. Recommendation: accept; the "Next" hint text is drawn only when the month read carries a row needing a match.
6. Uncertain board draws "Record what happened" and "Cancel delivery", and the text "retry it once checked". Spec adds a "Retry" button, a recorded-state block, a proof field, a confirm sheet and drops "once" (no attempt limit is known). Recommendation: accept.
7. Group disclosure and review boards show the station track, six facts and agent card: hidden under D-182 (as in F-103).
