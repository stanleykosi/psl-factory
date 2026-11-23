# A payroll reviewer decides each review, an operator publishes, withdraws or replaces the totals, and a recipient acknowledges their own receipt, live

> Tasks: FE-FIN-PAYROLL-RUN (part 2). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0 (read directly from `/Users/Hunchoo/psl-factory-worktrees/lane-d/contracts/`). Design: approved 13 Nov canvas under the exceptions in `design/review.json`; screens: SCR-59 part 2, artboards SCR-59-desktop-totals-review, SCR-59-mobile-totals-review, SCR-59-desktop-publish, SCR-59-mobile-publish, plus the decision cards on the part 1 boards (input-review, combine-review, match-review, followup).

## Summary
- Extends F-110's panel (`frontend/src/features/payroll-run/`) with one form component, `PayrollRunActions.tsx`, registered through F-87's `Actions` slot. It carries every write of this part: review decisions, Publish, Withdraw, Successor, Restart, Ask HR to correct, and the recipient's "Confirm I received it" on the report.
- Seven writes, all in the 1.25.0 contract, no backend change: `POST /work/{id}/reviews` (`kind: "payroll"`), `POST /work/{id}/payroll-operations` (`publish`, `withdraw`, `successor`, `restart`), `POST /work/{id}/corrections` (`line: "finance-payroll/v1"`) and `POST /work/{id}/aggregate-receipt`.
- Every control comes from a live read (`working[]`, `stage`, `publication_id`, `payroll-recovery.restart`, report `can_acknowledge`); the server decides every rule and a refusal is shown, not predicted. Every write is shown from a re-read, never from its answer alone. Uncertain effects lock the form until the re-read settles.
- Restricted payroll: only aggregate figures drawn (E-26, E-30). Unknown money stays unknown; no total is ever 0 by default. Wherever the API supplies nothing a board draws, that part is hidden (D-182).
- Waits (build start only, not readiness): F-110 merged (the panel, `payrollRunApi.ts`, mock folder), F-108, F-85 and F-87 (`Actions` slot, `useWorkCommand`). Two writes need an evidence id that no 1.25.0 read supplies (see Questions 1 and 2); they are built to the contract and held off until a list exists. High risk: merge goes to the design engineer's merge batch.

## Context
Lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`. Paths marked (F-110), (F-85), (F-87) arrive when those merge.
- F-110 (`delivery/features/F-110/spec.md`) is binding for reads, display rules, the no-leak rule for `working-rows`, the no-access wording ("This record is unavailable." for 403 and 404, no ids, names or values), the uncertain-effect lock and the "tokens never null or 0" rule. Its files: `payrollRunAdapter.ts`, `PayrollRunPanel.tsx`, `StationButtons.tsx`, `HrReceiptForm.tsx`, `payrollRunApi.ts`, `labels.ts`, `frontend/mock/payroll-run.mjs`, `frontend/mock/fixtures/payroll-run/**` (F-110).
- F-87: optional `Actions?: ComponentType<LineActionsProps>` on `LineAdapter`, `LineActionsProps = { readback, ctx: LineContext, commands: CommandDescriptor[], reload }`, and `useWorkCommand` (press lock, uncertain lock, csrf, 409 re-read). Example form: F-89's `WeeklyReportActions.tsx`. This feature registers `PayrollRunActions` once; it never edits `src/features/workspace`.
- Shared UI by name: `Button`, `Callout`, `Tag`, `Select` in `src/components`; `Money`, `Unknown` in `src/components/Values.tsx`; `liveApi`, `call`, `refreshSession` in `src/api/client.ts`; `ApiError` in `src/api/errors.ts`.
- Reads this part uses (F-110 owns them, no new reads): `GET /work/{id}/payroll-operations` (tokens, `selected`, `stage`, `publication_id`, `working[]`, `hr_receipt`), `GET /work/{id}/payroll-recovery` (`restart`, `previous_receipt`), `GET /projects/{case_id}/payroll/reports/{publication_id}` (`eligible_total`, `by_business_unit`, `version`, `receipt_id`, `can_acknowledge`, `revision`). New reads for the successor and restart pickers only: `GET /projects/{case_id}/payroll/requests` (list, `page`) and `GET /projects/{case_id}/payroll/requests/{request_id}/start-choices` (`inputs[{id, provider, version}]`, `hr_snapshots[{id, captured_at, period}]`).
- Backend answers: E-30 (`eligible_total` is a confirmed decimal string; incomplete totals are held on the server), E-31 (operations are working, receive_hr, publish, withdraw, successor, restart), E-26 (no names or pay rows beyond what a reader is admitted to). Per the connection map: "the original recipient confirms through `aggregate-receipt` without reading pay rows; a successor match needs fresh independent review."

## Contract

Tokens for every write come from the latest `payroll-operations` read (`expected_revision`, `case_revision`), never defaulted, never 0 or null. With the read not loaded every control is off and nothing is sent. After every write, 409 or uncertain outcome: re-read `payroll-operations`, the work item, and the report or recovery read the panel shows. No write is sent twice by itself.

Shared error handling (all writes): 401 signed-out state linking to `/sign-in?next=<path>`; 403 `csrf_failed` refresh the session once and say "Press the button again" (no automatic second send); other 403 "You can't do this." plus the server message, then re-read (an admitted reviewer who is not the independent reviewer sees the server's refusal); 404 the no-access state "This record is unavailable."; 409 re-read and "This changed while you were working. Showing the latest version."; 422 the server message and the first `fields[].message`; 429 and 503 "Try again shortly."; network error or 5xx is uncertain (below). Error `code` values are not mapped to prose beyond the server's `message`.

Uncertain effect: a dropped connection, 5xx, or a work `state` of `effect_uncertain` or `awaiting_reconciliation` after the re-read locks every control in `PayrollRunActions` with "We couldn't confirm that this ran. Check the page before trying again." and sends nothing by itself. Controls unlock only when the re-read shows a different `expected_revision` and a settled state. No retry, no reconcile action here (F-87).

### Write 1: review a stage (`reviews`, kind `payroll`)
Decision card on the input-review, combine-review and match-review boards. One card per subject: `subject: "input"` for each id in `selected.input_ids`, `subject: "run"` for the `working[]` entry of the board's stage (`combine` on combine-review, `match` on match-review).
- Buttons: "Approve", "Return" (always); "Revoke approval" and "Approve draft match" only when the server's last refusal or the read names them (see Assumptions: shown on the match card for `approve_draft_match` only while the `match` run is `held` with counts present; "Revoke approval" only on the totals-review board). A required note field (0 to 4000 chars; empty allowed by the contract, but the form asks for one on Return).
- `POST /api/v1/work/{work_id}/reviews`, body `{kind:"payroll", expected_revision, case_revision, subject:"input"|"run", subject_id, verdict:"approve"|"return"|"revoke"|"approve_draft_match", operation_key, evidence_id, note}`; exactly these fields, no others. 200 `{work_id, state, revision, review_id|null}`.
- `operation_key`: a fresh key per decision (`review-` plus a new uuid), made when the card is opened and kept until the re-read shows a new `expected_revision`; a new key after that. It is never sent twice by itself.
- `evidence_id`: required. No 1.25.0 payroll read supplies a review evidence list (`review_evidence[]` exists on other lines, not on `payroll-operations`). The card draws "Approve" and "Return" off with "No review evidence is available yet." and sends nothing, until Question 1 is answered. Never invent an id; never use `hr_receipt.proofs[]` for a review (it is the HR snapshot receipt proof).
- Successor match: after a `successor` or `restart` the new run's reviews are fresh, independent decisions; the card shows only what the read supplies, and the server's independence refusal (403 or 422) is shown as given. No client-side "different person" check.
- Permission and tenant rule: the signed-in person only; a 403 or 404 draws no-access; no staff names or pay values appear on the card (subject is shown as "Input: {provider}" or the run's label and counts from F-110's mapper).
- Idempotency: `operation_key` plus the two tokens. Versioning: `expected_revision`.

### Write 2: publish totals (`payroll-operations`, `publish`)
Board SCR-59-publish. Button "Publish totals", on only when `publication_id` is null, `working[]` has an `aggregate` entry with status `complete`, and the read is loaded; a confirm step names who receives them only as far as the read supplies it (it supplies no recipients, so the text is "Publish these totals to the people named in the run." with nothing invented).
- `POST .../payroll-operations` body `{action:"publish", expected_revision, case_revision}`. 200 `{work_id, state, revision, record_id}`; `record_id` is the new publication id but the page takes `publication_id` from the re-read, not from the answer.
- After 200: re-read; the report block (F-110 Read 4) and the "Receipts" state appear from the re-read.
- Errors: shared. An incomplete or too-small-group total is held on the server (E-30) and the server's refusal is shown as given.

### Write 3: withdraw approval or withdraw published totals (`withdraw`)
Board SCR-59-totals-review ("Withdraw approval") and the follow-up path.
- Shown only when `publication_id` is not null. A reason (required, 1 to 2000 characters) and a proof choice.
- `POST .../payroll-operations` body `{action:"withdraw", expected_revision, case_revision, publication_id, evidence_id, reason}`. `publication_id` comes from the read. 200 as above.
- `evidence_id`: required; no read supplies a list and no proof route exists on the action (Question 2). The button is off with "No evidence is available yet to withdraw these totals." until a list exists. Never invented.
- After 200: re-read; the work `state` and the `payroll-recovery` read (`previous_receipt`) come from the re-read.
- Confirmation text: "Withdrawing removes these totals from the people who received them. Their receipt stays on record." (the second sentence only when the re-read's `previous_receipt.receipt_id` is set; otherwise only the first).

### Write 4: replace with a successor (`successor`)
Shown on totals-review only when `publication_id` is not null and the person opens "Replace these totals".
- Form: choose a request (from `GET .../payroll/requests`, up to 25 per page, follow `next_page` at most 4 pages), then the two inputs and optional HR snapshot from `GET .../payroll/requests/{request_id}/start-choices` (`inputs[]` max 2; `hr_snapshots[]` max 40; nothing preselected; the snapshot may be left as "No snapshot" which sends `null`), and a reason (1 to 2000).
- `POST .../payroll-operations` body `{action:"successor", expected_revision, case_revision, publication_id, request_id, inputs:{input_ids:[a,b], hr_snapshot_id:<int|null>}, reason}`. `input_ids` are exactly two distinct ids. 200 as above.
- After 200: re-read. The new run's stages and reviews restart; the page does not claim anything is approved.
- Reads that fail (403, 404, empty list): "No replacement inputs are available to you." and the button stays off.

### Write 5: restart a cancelled run (`restart`)
Shown on the follow-up board only when work `state` is `cancelled` or `followup_needed` and `payroll-recovery.restart` is non-null. Button "Start a corrected run".
- Values come from `restart`: `request_id`, `selected.input_ids`, `selected.hr_snapshot_id`, `configuration_id`, and the tokens `expected_revision`, `case_revision` from the recovery read (not from `payroll-operations`: use the pair on `restart`). The person may change nothing but the reason.
- `POST .../payroll-operations` body `{action:"restart", expected_revision, case_revision, request_id, inputs:{input_ids, hr_snapshot_id}, configuration_id, instruction_key, reason}`; `instruction_key` is `restart-` plus a new uuid (matches `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$`), made when the form opens and kept until the re-read changes `expected_revision`. 200 as above.
- After 200: re-read `payroll-operations`, `payroll-recovery` and the work item. Nothing is called "corrected" from the answer.

### Write 6: ask HR to correct (`corrections`)
Match-review board. Button "Ask HR to correct", shown when the `match` run is complete and `counts.unmatched` or `counts.conflict` is greater than 0 (never from a null count).
- `POST /api/v1/work/{work_id}/corrections` body `{expected_revision, case_revision, line:"finance-payroll/v1", reason, source:{request_id, inputs:{input_ids:[a,b], hr_snapshot_id:<int|null>}}}`. The contract's body is a corrected set of inputs plus a reason; it carries no HR question text. 200 `{work_id, state, revision}`.
- Built on the best reading (Question 3): the form takes the reason and the replacement set from the same pickers as Write 4 (preselected with the run's current `selected` values, which the person may change); the reason text is the ask. The name-check route (`payroll/name-checks/{id}`) is F-109 and is not called here.
- After 200: re-read; the state shown is from the re-read. A refusal is shown as given.

### Write 7: recipient receipt (`aggregate-receipt`)
Receipts board and the report block. Button "Confirm I received it" on the report, on only when the report read has `can_acknowledge` true and `receipt_id` null.
- `POST /api/v1/work/{work_id}/aggregate-receipt` body `{publication_id}`; no tokens in this body. 200 `{receipt_id, publication_id}`.
- The recipient reads no pay rows to do this: the button is on the report block only, which shows `eligible_total`, `by_business_unit` and `version` exactly as F-110 Read 4. After 200: re-read the report; "Your receipt: Recorded" comes from `receipt_id` now set, not from the answer.
- Errors: shared (no 409 body tokens, so a 409 re-reads).

### Screen states (every write form)
- Loading: skeleton; the form is not drawn until the read is loaded.
- Empty: a control whose source list is empty is off with its reason line (never an empty heading).
- Error: shared handling above; the panel keeps its last good read on a failed re-read and drops it on 401, 403 or 404.
- Success: from the re-read only.
- Uncertain: lock text above.
- Totals-review board is drawn only once `publication_id` is set. Before it, the board does not render (Question 2 of readiness, recommendation (a) assumed).

### Fixture examples (mock, port 4991; extends F-110's ids 4601 to 4612, new ids 4621 to 4634)
All names fictional; no row values.
- `4621` input review with a review card: `working:[]`, evidence list empty -> Approve and Return off with "No review evidence is available yet."
- `4622` combine review ready: same with `evidence` available (mock-only; shape provided by the Question 1 answer), Approve sends `{kind:"payroll", subject:"run", subject_id:401, verdict:"approve", operation_key, evidence_id, note}`.
- `4623` match review with `counts:{total:139,held:2,conflict:1,matched:136,unmatched:2}`: "Ask HR to correct" on; `4624` match `counts:{matched:null, unmatched:null}`: not shown.
- `4625` aggregate complete, no publication: "Publish totals" on. `4626` published (eligible_total "99200000.00", units Delivery, Design, Finance, Other): totals-review board with Withdraw and Replace.
- `4627` publish refused 422 (small group held): server message shown. `4628` 409 on first write then success.
- `4629` withdrawn with receipt (`previous_receipt` set, `restart` set): "Start a corrected run" on; `4630` same with `restart:null`: absent.
- `4631` recipient: report `can_acknowledge:true, receipt_id:null`; `4632` already acknowledged. `4633` `effect_uncertain`. `4634` 403 for non-independent reviewer on review.
- Mock checks field names, exact bodies (no extra fields), tokens, key patterns, and 405s a second send of the same key. v7 ids keep their answers. Any change to `frontend/mock/finance*` or payments fixtures is named in build.md for lane B.

## Lanes
- Frontend lane (owner): `frontend/src/features/payroll-run/` additions: `PayrollRunActions.tsx`, `ReviewCard.tsx`, `PublishForm.tsx`, `WithdrawForm.tsx`, `SuccessorForm.tsx`, `RestartForm.tsx`, `CorrectionForm.tsx`, `ReceiptButton.tsx`, `payrollRunWrites.ts` (bodies and key helpers), additions to `payrollRunApi.ts` and `labels.ts`; registration in `payrollRunAdapter.ts` (`Actions`); `frontend/mock/payroll-run.mjs` and `frontend/mock/fixtures/payroll-run/**` extended; `frontend/e2e/payroll-run-actions.spec.ts`; unit tests beside each file; live types from `live-schema.d.ts` into `src/api/types.ts`.
- Backend lane: none. No backend, migration or contract change.
- Integration owner: lane D coordinator (merge into the design engineer's merge batch).
- Shared files and owners: `src/features/workspace/*` (lane C owns; read only; the `Actions` slot and `useWorkCommand` are F-87). `src/api/*` (shared; live types only). `mock/server.mjs` (shared; no new import, F-110 mounts the file). `src/components/*` used as is. F-110's files are extended, not restructured.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
Ports: Next 4990, mock 4991, Django 8030.
1. Every write sends exactly the bodies in Contract (no extra fields, no null or 0 token, `successor` and `restart` inputs are exactly two distinct ids) — verify: unit tests on `payrollRunWrites.ts` for all seven bodies; mock rejects extras.
2. With the read not loaded, every control is off and nothing is sent — verify: unit test.
3. `/work/4621` shows Approve and Return off with "No review evidence is available yet." and sends nothing; no id is invented and `hr_receipt.proofs[]` is not offered for a review — verify: e2e request count 0; unit test.
4. `/work/4622` Approve sends one `POST /work/4622/reviews` with `kind:"payroll"`, `subject:"run"`, `verdict:"approve"`, an `operation_key` starting `review-`, then re-reads; the card shows the decision only after the re-read — verify: mock request log.
5. A repeated press after a 409 does not reuse an `operation_key` that the server already saw; a repeated press while uncertain sends nothing — verify: mock scenarios 4628 and 4633; request count.
6. A reviewer the server refuses as not independent (`4634`, 403) sees the server message and "You can't do this."; no client-side role check hides or shows the card — verify: e2e; grep for role checks in `payroll-run`.
7. `/work/4625` shows "Publish totals"; pressing it sends one `{action:"publish", expected_revision, case_revision}` and nothing else; the report block appears only from the re-read — verify: mock log; e2e.
8. Publish is off when `publication_id` is set or no `aggregate` entry is complete; a 422 on `4627` shows the server message and no total is drawn from the answer — verify: unit test of the gate; e2e.
9. `/work/4626` draws the totals-review board with "NGN 99,200,000.00" from `eligible_total` through `Money`, the four unit rows, "Version 1", and no "Unknown" split, no "Not matched" row, no staff counts, no per-recipient rows; a unit absent from `by_business_unit` has no row and no 0 — verify: page; unit test.
10. The totals-review board is not drawn when `publication_id` is null (`4625`) — verify: e2e asserts absence.
11. Withdraw sends `{action:"withdraw", expected_revision, case_revision, publication_id, evidence_id, reason}`; reason is required (empty is refused in the form and sends nothing); with no evidence list the button is off with its reason line — verify: unit tests; e2e.
12. After a withdraw 200 the page shows the state and `previous_receipt` only from re-reads; the confirm text mentions the receipt only when `receipt_id` is set — verify: mock; page text.
13. Successor sends `{action:"successor", ..., publication_id, request_id, inputs:{input_ids, hr_snapshot_id}, reason}` with `hr_snapshot_id: null` kept as `null` when "No snapshot" is chosen; two identical input ids cannot be submitted — verify: unit test; mock.
14. "Start a corrected run" appears on `4629` and not on `4630` (`restart: null`) and not on a run that is not `cancelled` or `followup_needed`; its body uses `restart` values and the recovery tokens, with `configuration_id` and an `instruction_key` matching the pattern — verify: e2e; unit test on the pattern.
15. "Ask HR to correct" appears on `4623` and not on `4624` (null counts) and sends the `finance-payroll/v1` corrections body — verify: e2e; unit test.
16. `/work/4631` shows "Confirm I received it" on the report; it sends `POST /work/4631/aggregate-receipt` `{publication_id}`; "Your receipt: Recorded" appears from the re-read; `4632` shows no button — verify: mock log; page.
17. A person who can acknowledge sees only the aggregate report (total, unit rows, version): no staff name, pay row or count appears in the DOM, storage, URL, cache keys or console — verify: unit test greps mapper output; e2e dumps storage and DOM and searches fixture names.
18. 403 `csrf_failed` on any write does not show no-access; it refreshes the session once and says "Press the button again"; no automatic second send — verify: unit test counts fetch calls.
19. A write that gets 409 re-reads, shows "This changed while you were working. Showing the latest version.", and sends nothing again by itself — verify: scenario `4628`; count requests.
20. A dropped connection after any of the seven writes, or `/work/4633` (`effect_uncertain`), locks every control in `PayrollRunActions` with "We couldn't confirm that this ran. Check the page before trying again." and sends no request until the re-read shows a new `expected_revision` and a settled state — verify: scenarios; request count.
21. 403 and 404 on the work read still draw only "This record is unavailable." (no ids, values, or which of the two); a different user without the payroll grant and a different tenant each get no-access and no write control — verify: mock scenarios; live check with two accounts against Django 8030.
22. Against live Django 8030 with a real payroll work: the buttons that appear match `payroll-operations`, `payroll-recovery` and the report (`publication_id`, `restart`, `can_acknowledge`), and a server refusal (for example a non-independent reviewer) shows its message — verify: compare with `curl` JSON using the session; run with two accounts.
23. The page makes no write on load, polling or navigation — verify: e2e asserts zero POSTs on load; `grep liveApi.POST frontend/src/features/payroll-run` shows only `working`, `receive_hr`, `startPayrollRun` (F-110) and the seven writes here.
24. No change in `src/features/workspace` and none in `delivery/config.json` protected paths — verify: `git diff --stat` against main.
25. Viewport check at 1440 and 390 against SCR-59 totals-review, publish and the part 1 boards with decision cards: hidden parts leave no empty gap or heading — verify: screenshots at both widths reviewed against the boards.
26. Tests exist for each write body, the key rules, the gates (publish, restart, ask HR, withdraw), the uncertain lock, the 409 path, the csrf path and the no-leak rule; `delivery/checks.sh` passes — verify: `npm test`; checks result.

## Out of scope
- Everything F-110 owns (stations, HR receipt, report and recovery reads, `startPayrollRun`) and F-108/F-109 (`working-rows`, problem rows, name checks, HR questions, attestations).
- Reconcile, resume and "Check what happened" (F-87). Cancelling a run.
- Any recipient list, per-recipient receipt rows, "Gross pay + Unknown", "Merge rule F16", "Written to HR records / Posted to the ledger"; staff names and individual pay anywhere (E-26).
- Choosing or uploading evidence by uploading a new file for these actions: no proof route exists on them (see Questions); no `fileToEvidence`.
- Changes to `src/features/workspace`, the F-85 frame, the SCR-57 BU totals run (E-32), the SCR-13 visibility editor, backend, migrations, contract edits.

## Assumptions
- `operation_key` and `instruction_key` are client-made (`review-<uuid>`, `restart-<uuid>`), one per opened form, kept until the re-read changes the revision. Reason: the contract requires them and no read supplies one.
- "Revoke approval" appears only on the totals-review board and "Approve draft match" only on the match card while the `match` run is `held` with counts. Reason: the contract lists four verdicts and no read says which apply; the drawn proposals are "Withdraw approval (revoke)" and the draft match; the server refuses the rest.
- Review decision card gating (Approve, Return) otherwise follows the stage: input cards per input, run cards per `working[]` entry of the board's stage. Reason: `subject` and `subject_id` come from `selected.input_ids` and `working[].id`.
- The replacement request list and choices use the two read paths named above; the person picks, nothing preselected, except "Ask HR to correct", which preselects the current set. Reason: the successor and corrections bodies need a request and two inputs and no read offers a ready choice.
- Withdraw and review confirmations use only text the read supports. Reason: no recipient list exists in 1.25.0.
- Mock ids 4621 to 4634. Reason: free after F-110's 4601 to 4612.
- Totals-review draws only once `publication_id` is set. Reason: its table has no source before.

## Conflicts with the boards
Boards were checked through `design/screens.md` and F-110's board split, not pixel by pixel; the design engineer decides once before the build.
1. Totals-review board: "Gross pay + Unknown" and the "Not matched · Unknown" row removed (no source; E-30). Recommendation: show the confirmed total and unit rows only.
2. Totals-review and publish boards: any recipient or group list ("Finance Lead RECEIVED / CEO WAITING", "2 of 2") removed (nothing lists recipients). Recommendation: hide; the report block shows only the caller's own receipt.
3. Added, not drawn: a required reason field and a proof/evidence choice on Withdraw and Replace; a reason field on Ask HR to correct and on Start a corrected run; a request and input picker for Replace (the boards draw an entry point only). Recommendation: keep; the contract requires them.
4. Added: the "No review evidence is available yet." and "No evidence is available yet to withdraw these totals." states on the decision and withdraw controls (no source of evidence ids in 1.25.0). Recommendation: keep until the backend supplies a list.
5. Added: the successor and "Start a corrected run" entry points on the totals-review and follow-up boards. Recommendation: Question 4 option (a).
6. Added: confirm step before Publish and Withdraw (the boards draw a single button). Recommendation: keep; both are hard to undo and publish reaches named recipients.
7. Added: "Ask HR to correct" as a form with a replacement-input picker (the board draws a button). Recommendation: see Question 3.

## Questions
1. Where does the evidence id for a payroll review come from? The 1.25.0 `payroll-operations` read has no `review_evidence[]` (other lines have). Options: (a) backend adds a `review_evidence[]` (id, version, kind) to `payroll-operations` or the work read, as on the other review lines (recommended; until then the review buttons stay off); (b) accept F-85's `fileToEvidence` for reviews, flagged, which the lane D rule forbids where a route is expected; (c) allow the person to type an evidence id (not recommended, invents ids). Context: Write 1 needs an `evidence_id` on every `approve` and `return`.
2. The same gap for Withdraw (`evidence_id` required, no list, no proof route). Options: (a) backend supplies a list or a proof field on `withdraw` (recommended; button off until then); (b) reuse the report's own proof if the backend confirms it is the right record; (c) drop Withdraw from this release. Context: the totals-review board draws "Withdraw approval".
3. What does "Ask HR to correct" mean to the API? `POST /work/{id}/corrections` for `finance-payroll/v1` takes a reason plus a replacement request and inputs; there is no HR question text. Options: (a) build it as drawn in Write 6 and ask the backend to confirm it routes to HR (recommended; flagged); (b) route to the name-check route owned by F-109 instead; (c) hide the button until the backend answers. Context: backend answers in the connection map say "corrections or name-checks route".
4. Does a board draw the successor entry (Replace these totals) and the "Start a corrected run" entry? Options: (a) draw both, only when the read supplies `publication_id` or `restart` (recommended, matches readiness Q1); (b) leave them off until a board draws them.
5. Review verdicts "Revoke approval" and "Approve draft match": do they appear on the boards only where assumed? Options: (a) as in Assumptions (recommended); (b) hide both and offer only Approve and Return.
