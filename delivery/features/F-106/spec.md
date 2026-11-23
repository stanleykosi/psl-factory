# Management accounts reviews, drafting, publication, uncertain delivery and the verified result run on the live API

> Tasks: FE-FIN-ACCOUNTS-PUBLISH. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the recorded exceptions in `design/review.json`; screen SCR-53, states reviews, drafting, publishing, uncertain, verified (`design/screens.md` line 71; artboards `design/canvas/finance/project/SCR-53-{desktop,mobile}-{reviews,drafting,publishing,uncertain,verified}`).

## Summary
- A person opens a management-accounts work item and sees the board that matches `accounting.state`: reviews, drafting, publishing, uncertain or verified. All five are fed by one live read, `GET /work/{work_id}/accounting`.
- Reviews board: each station and its subjects with status, claim and decision through `POST /tasks/{id}/claim` and `/decision` (verdicts only from `tasks[].verdicts`), plus "Check reviewers again" (`recheck_reviewers`) and "Reassess" (`reassess`) when the API allows them.
- Publishing, uncertain and verified boards come from `publication` and `delivery_jobs[]`. The one recovery is `POST /work/{id}/actions {action: reconcile}` when `can_reconcile`; there is no resend control. The verified board appears only when `publication` is present with `verified_at`. `ledger_posted` is always shown as returned.
- Parts of the boards that the API does not supply are hidden under the D-182 rule (list under Contract and Conflicts). Unknown values read "Not recorded", never 0.
- Build waits on F-105 (intake boards and the state router) and F-85 (shared line adapter, PR #101) being on main. This delays the build start only.

## Context
Where this lives today (lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d`, code at API 1.24.0):
- Backend, read only for this feature: `apps/core/factory_api/accounting_work.py` (the `GET/POST /work/{id}/accounting` read and write; `ledger_posted` is the constant `false`; `state` is the work state, the same 11 values as `GET /work/{id}`), `apps/workflows/factory_accounting.py` (job statuses used for recovery: `pending`, `leased`, `held`, `unknown`; a job in `unknown` or an expired `leased` demands reconcile before anything else).
- Frontend: `frontend/src/api/client.ts` (`liveApi`, `call()`, shared CSRF), `frontend/src/api/live-schema.d.ts` (regenerated from 1.24.0; types for all operations below), `frontend/src/features/work-item/` (page; `GET /work/{id}` returns `panels[]`, and the accounting panel is `{key:'accounting', url:'/api/v1/work/{id}/accounting'}`), `frontend/src/features/workspace/` (shared frame, owned by lane C; F-85 adds `adapter.ts` with `LineAdapter`, `CommandDescriptor`, `registerLineAdapter`), `frontend/src/features/finance/` (month-end, payments; F-105 adds the accounts folder), `frontend/mock/server.mjs`.
- No SCR-53 route or code exists on main. F-105 lands the intake boards and the board router for its states; this feature adds the five states below to it.
- Live operations (looked up in the 1.24.0 contract):
  - `GET /api/v1/work/{work_id}/accounting` 200 required: `expected_revision`, `case_revision`, `state`, `next_action`, `finding`, `source_id|null`, `mapping_id|null`, `allocation_id|null`, `formula_id|null`, `report_version_id|null`, `publication|null {id, run_id, version_id, receipt_ids[], ledger_posted (false), published_at, verified_at}`, `tasks[] {id, revision, label, can_claim, can_decide, verdicts[approve|return|reject]}`, `calculated_at|null`, `review_stations[] {label, subjects[] {id, status, review_id|null, evidence_id|null, reviewed_at|null}}`, `delivery_jobs[] {id, status}` (max 30), `can_reassess`, `can_recheck_reviewers`, `can_reconcile`, `sources[]`, `setup_missing[]`, `correction|null`, `predecessor_id|null`, `successor_id|null`, `review_evidence[] {id, version, kind}`.
  - `POST /api/v1/work/{work_id}/accounting` 200 `{work_id, state, revision}`; body is one of `{action:'recheck_reviewers', expected_revision}` or `{action:'reassess', expected_revision, case_revision, source_id, adjustment_ids[], reason}`.
  - `POST /api/v1/tasks/{task_id}/claim` `{expected_revision}` 200 `{task_id, revision, claimed_by}`.
  - `POST /api/v1/tasks/{task_id}/decision` `{expected_revision, verdict: approve|return|reject, evidence_id, note}` 200 `{task_id, review_id, verdict, work_state}`. Evidence id and note are both required by the contract (note max 2000).
  - `POST /api/v1/work/{work_id}/actions` `{expected_revision, action: reconcile|release_invoice}` 202 `{work_id, state, revision}`. This feature sends only `reconcile`.
  - Errors on all of them: 400, 401, 403, 404, 409, 422, 429, 503 with `{code, message, fields[{name, message}]}`.
- Field shapes the readiness note asked about are settled by the contract: `publication` is fully typed above; `delivery_jobs[]` carries only `id` and `status` (no recipient name, no time, no receipt); `POST /actions` takes `{expected_revision, action}` only. No write is held for lack of a shape.

## Contract

### Board choice (presentation only; nothing here decides access)
A pure function `accountingBoard(accounting)` in this feature's folder returns one of `reviews | drafting | publishing | uncertain | verified | other`. `other` hands over to F-105's boards (quarantined, units, investigating, owner-needed, setup-needed, returned). First match wins:
1. `verified`: `state === 'verified'` and `publication` not null.
2. `uncertain`: `state` is `effect_uncertain` or `awaiting_reconciliation`, or any `delivery_jobs[].status === 'unknown'`.
3. `other`: `state` is `setup_needed`, `owner_needed`, `followup_needed` or `cancelled`.
4. `publishing`: `delivery_jobs` not empty.
5. `reviews`: `tasks` not empty, or any station subject whose status is not `approved`, while `report_version_id` is null.
6. `drafting`: `report_version_id` not null or `calculated_at` not null, with all review subjects approved and no delivery jobs.
7. otherwise `other`.
Unknown `state` or job-status words are shown as the raw text and never crash the page. The page re-reads every 5 s while `state === 'processing'` or the board is `publishing` or `drafting` and the tab is visible (reuse `POLL_MS` and the keep-last-good-on-failed-poll behaviour of `useWorkItem.ts`); no polling on `reviews`, `uncertain` or `verified`.

### Adapter
`frontend/src/features/finance/accounts/publish/` holds `accountingAdapter` registered with `registerLineAdapter({key:'accounting', ...})` per F-85, plus `accountingBoard.ts`, `ReviewsBoard.tsx`, `DraftingBoard.tsx`, `PublishingBoard.tsx`, `UncertainBoard.tsx`, `VerifiedBoard.tsx`, `FindingsList.tsx` and `VersionsNote.tsx`. Commands are described through `CommandDescriptor`: `claim`, `decide`, `recheck_reviewers`, `reassess`, `reconcile`. Tokens: `claim`/`decide` carry the task's own `revision` as `expected_revision`; the other three carry `accounting.expected_revision` (`reassess` also `case_revision`). None of the five has an idempotency key field (`idempotency.field === null`; no key is invented). A write is sent once per press; a 409 reloads the read and shows "This changed while you were looking. Check and try again."; there is no automatic retry of any write.

### Reviews board (SCR-53 reviews)
- Header: title and state tag from the work item; `next_action` as the next-step line; `finding` as the reason line when non-empty (empty means none).
- Table "Reviews · one per part": one group per `review_stations[]` (`label`), one row per subject with the status word as returned (`approved` and others as given, lightly capitalised) and `reviewed_at` when not null. A subject with `review_id` shows "Decided" with the evidence link only when `evidence_id` is not null.
- Decide panel: one per `tasks[]` row, titled by `label`.
  - `can_claim` true: button "Take this review". Sends `POST /tasks/{id}/claim {expected_revision: task.revision}`; on 200 reload the read.
  - `can_decide` true: verdict buttons built only from `verdicts[]` (approve "Approve", return "Return with a note", reject "Reject"). A verdict not in `verdicts[]` is never drawn. Required: evidence (a select from `review_evidence[]`, "Reviewed against"; preselected when exactly one) and a note (required for return and reject; for approve the note field is optional in the UI but the request sends the text or an empty string). If `review_evidence` is empty the decide control is disabled with "No review evidence is available yet." and nothing is sent. Sends `POST /tasks/{id}/decision {expected_revision: task.revision, verdict, evidence_id, note}`; on 200 reload the read.
  - Both false: the row is read only; text "Waiting for another reviewer" is not invented; show only the label and status.
  - The line "Approving doesn't publish anything; the report is drafted after all six reviews" is shown with the count taken from the number of subjects returned ("after all N reviews"), or omitted if none.
- "Check reviewers again" shown only when `can_recheck_reviewers`: `POST /work/{id}/accounting {action:'recheck_reviewers', expected_revision}`; on 200 reload.
- "Reassess" shown only when `can_reassess`: opens a small form for `reason` (required) and sends `{action:'reassess', expected_revision, case_revision, source_id, adjustment_ids, reason}`. `source_id` is `accounting.source_id`; if null the control is disabled "No source to reassess". `adjustment_ids` is sent as `[]` unless the read supplies adjustment ids (it does not in 1.24.0; see Assumptions).
- Hidden (not supplied): reviewer names column, the "Mapping rule D06 v3 maps 412 accounts to 14 report lines, 3 accounts are new" detail, the "Prepared output / after calculation" row's reviewer, and "A reviewer can't review a part they prepared" as a rule statement (shown only if the API returns a 403/422 with that message).
- Findings: `finding` text only. This read has no `finding_details`; F-105 owns the code/line rendering for intake and mapping findings and this feature reuses its `FindingsList` if present on main, else shows the plain text.

### Drafting board (SCR-53 drafting)
- Shows `state` tag, `next_action`, `finding`, "Calculated {calculated_at}" when not null (else "Not calculated yet"), and `setup_missing[]` as a list titled "Needed before it can be published" when not empty.
- Shows what is done as read-only lines from ids that exist: "Mapped accounts" (when `mapping_id` not null), "Allocated to business units" (`allocation_id`), "Applied the formula rule" (`formula_id`), "Report drafted" (`report_version_id`). Each line shows no count, no version word and no approval wording, because the API returns ids only.
- Hidden (not supplied): Revenue, Cost of sales, BU allocation count, Unallocated amount (the "Results so far" strip), the agent step list with "step 4 of 5", "Started 14:10", the "TEST TEMPLATE" tag, the "Send for output review" button and "Ask Chidi". No money figure is drawn anywhere on this feature.

### Publishing board (SCR-53 publishing)
- Shows "Published {publication.published_at}" when `publication` is not null; otherwise "Not published yet".
- "Who has it": one row per `delivery_jobs[]` entry: "Delivery {n}" and the status word as returned (`pending`, `leased`, `held`, `unknown` and any other shown raw, lightly capitalised). When `publication.receipt_ids` is present show "Receipts recorded: {receipt_ids.length}". Never show a tick or "Received" for a job; the API does not say which job a receipt belongs to.
- Copy: "Verified once every recipient has a receipt." (the page does not decide this; the API moves `state` to `verified`).
- No control other than a link back to the work item. A `held` job shows "Needs controlled recovery" only when `can_reconcile` is false and the status is `held`; no action is offered.
- Hidden (not supplied): recipient names and roles, per-recipient delivered time, per-recipient receipt state, "Chidi reminds the recipient tomorrow".

### Uncertain board (SCR-53 uncertain)
- Headline "We don't know if the report reached everyone." Not per-recipient; copy: "No new delivery is allowed until this is checked, so nobody gets it twice."
- "What we know": one row per `delivery_jobs[]` with status `unknown` (or `leased`), status word as returned, plus "Published {published_at}" when `publication` is not null.
- Control: "Check what happened" only when `can_reconcile`; it sends `POST /work/{id}/actions {expected_revision: accounting.expected_revision, action:'reconcile'}` once and shows "Checking" on 202, then reads again (poll every 5 s for up to the usual visibility rules; the 202 is not a result and the page never says "delivered"). A 409 or 422 shows the API `message`. When `can_reconcile` is false the board shows "Someone else is checking this" only if the API says so in `next_action`; otherwise it shows `next_action` alone and no button.
- There is no resend, retry or cancel control, and no "record the outcome" input (the live action takes none). Nothing on this page retries a delivery.
- Hidden (not supplied): "Sent to the email service 14 Nov 10:02", "Service confirmation UNKNOWN" as a drawn fact, "Checked twice 10:15 · 10:45", the recipient's name ("PMO Lead"), "Check with the PMO Lead".

### Verified board (SCR-53 verified)
- Shown only for board `verified` (see the router). Facts, each only when the field is not null: "Calculated {calculated_at}", "Published {publication.published_at}", "Verified {publication.verified_at}", "Receipts {publication.receipt_ids.length}". Review counts are shown as "Reviews: {n} subjects" taken from `review_stations`, with "approved" only for subjects whose status is exactly `approved`; no "6 of 6" is claimed unless every returned subject is approved.
- "Not done by this line": "Posting to the ledger" with the value "Not posted" read from `publication.ledger_posted === false`. If it were ever not false the row shows "Not recorded". `ledger_posted` is shown on every board that has a `publication`.
- Link "Open month-end" to `/finance/month-end` only if that route exists on main at build time; otherwise omit.
- Hidden (not supplied): "Changing the source file: NEVER" (no field).

### Earlier versions
When `predecessor_id` or `successor_id` is not null show a read-only line "Replaces report {predecessor_id}" or "Replaced by report {successor_id}" linking to `/work/{id}`. `correction` is not rendered here (F-105, returned board). No version history is invented.

### States
- Loading: `WorkItemStates` loading while the read is in flight.
- Empty: not applicable; an item with no accounting facts falls to `other` and F-105's investigating board.
- Error: 401 signed-out state with link `/sign-in?next=<path>`; 403 `forbidden` no-access; 403 `csrf_failed` refreshes the session and says "Refresh your session and try again" (not shown as no-access); 404 shows "This record is unavailable." for missing and not-yours alike; 429 and 503 "Try again shortly" with a retry button for reads; network "We couldn't reach the server."
- Write errors: 422 shows the first `fields[].message`; 409 as above; 403 the API message; every write button is disabled while any write is in flight, so one press sends one request.
- Success: as each board above.

### Fixture examples (the builder creates these in `frontend/mock/`; the shape is the contract, the numbers are free)
- `4201` reviews: `state:'action_needed'`, two stations (Source: one subject `approved`, review_id 11, evidence_id 301, reviewed_at set; Mapping rule: one subject `waiting`), `tasks:[{id:901, revision:3, label:'Mapping rule', can_claim:true, can_decide:false, verdicts:['approve','return','reject']}]`, `review_evidence:[{id:301, version:1, kind:'finance_review'}]`, `can_recheck_reviewers:true`.
- `4202` drafting: `state:'processing'`, `calculated_at` set, `mapping_id`, `allocation_id`, `formula_id` set, `report_version_id:null`, `delivery_jobs:[]`, `setup_missing:['Report template']`.
- `4203` publishing: `state:'waiting'`, `publication:null` or published, `delivery_jobs:[{id:1,status:'pending'},{id:2,status:'leased'}]`.
- `4204` uncertain: `state:'effect_uncertain'`, `delivery_jobs:[{id:1,status:'unknown'}]`, `can_reconcile:true`.
- `4205` verified: `state:'verified'`, `publication:{id:7, run_id:3, version_id:5, receipt_ids:[21,22,23], ledger_posted:false, published_at, verified_at}`.
- `4206`: 404 for any caller. `4207`: `can_decide:true` task with empty `review_evidence`. `4208`: `successor_id:4205`.

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/finance/accounts/publish/**`, `frontend/mock/**` routes and fixtures for the five operations, `frontend/src/api/types.ts` additions for the live accounting read, tests under `frontend/src/features/finance/accounts/publish/**` and `frontend/e2e/accounts-publish*.spec.ts`.
- Backend lane: none. No contract or backend change.
- Integration owner: lane D coordinator. Shared files and owners: `frontend/src/features/workspace/*` (lane C; not touched; a frame change would be named as a dependency on lane C), `frontend/src/features/finance/accounts/*` outside `publish/` and the board router (F-105 owns it; this feature adds `publish/` and one import and five router cases in a separate small commit after `git merge origin/main`), `frontend/src/api/*` (shared; live types and error kinds only), `frontend/src/components/*` (used as is).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. The router picks each board from the read: the five fixtures `4201`..`4205` show reviews, drafting, publishing, uncertain and verified, and `state:'owner_needed'` or `setup_needed` returns `other` — verify: unit test on `accountingBoard.ts`; open `/work/4201` to `/work/4205` against mock 4991 on Next 4990.
2. The reviews board draws one row per station subject with the API status word and no reviewer name column — verify: open `/work/4201` at 1440 and 390; DOM has no reviewer column.
3. "Take this review" appears only when `can_claim`; pressing it sends exactly one `POST /tasks/901/claim` with `{expected_revision: 3}` — verify: e2e plus network panel.
4. Decide verdict buttons are exactly the entries of `verdicts[]`; a verdict outside the list is never drawn or sent — verify: unit test with `verdicts:['approve']` shows one button.
5. A decision sends `{expected_revision (task revision), verdict, evidence_id, note}` with `evidence_id` from `review_evidence[]`; return and reject cannot be sent with an empty note; on 200 the board reloads — verify: unit test on the body; e2e on `4201`.
6. With empty `review_evidence` (`4207`) the decide control is disabled with "No review evidence is available yet." and no request is sent — verify: e2e, network panel shows no decision call.
7. Wrong user: a task with `can_claim:false` and `can_decide:false` has no button; a mock 403 on claim shows the API message and leaves the board unchanged — verify: e2e on both.
8. A 409 on claim, decision or any accounting write reloads the read and says "This changed while you were looking. Check and try again."; the write is not repeated — verify: unit test counts POSTs (one).
9. "Check reviewers again" is shown only when `can_recheck_reviewers` and sends `{action:'recheck_reviewers', expected_revision}` once — verify: unit and e2e.
10. "Reassess" is shown only when `can_reassess`, needs a reason, is disabled when `source_id` is null, and sends the full body with `case_revision` — verify: unit test on the descriptor body and the form.
11. Invalid input: an empty reassess reason and a note over 2000 characters are refused in the form before any request; a mock 422 shows its first `fields[].message` — verify: unit test, no fetch call on refusal.
12. The drafting board shows `calculated_at`, the id-backed done lines and `setup_missing[]`; it draws no revenue, cost, allocation count, unallocated amount, step list, "Send for output review" or "Ask Chidi" — verify: e2e on `4202` asserts those texts are absent.
13. The publishing board lists one row per `delivery_jobs[]` entry with the raw status and "Receipts recorded: N" from `receipt_ids`; no recipient name, no "Received" tick — verify: e2e on `4203` and `4205` fixtures; unit test on the row mapper with an unknown status word.
14. The uncertain board shows "Check what happened" only when `can_reconcile`; one press sends exactly one `POST /work/{id}/actions {expected_revision, action:'reconcile'}`; a 202 shows "Checking" and never "delivered" — verify: e2e plus network panel.
15. The page has no resend, retry, cancel or release control anywhere, and the code contains no `release_invoice` call — verify: e2e asserts those buttons are absent; `grep -rn "release_invoice" frontend/src/features/finance/accounts` returns nothing.
16. While a write is in flight every write button is disabled, so a double press sends one request — verify: unit test with a pending promise.
17. The verified board appears only with `publication` not null and `state:'verified'`; a job that reports success without a `publication` (state `waiting`, job `sent`) shows the publishing board, never verified — verify: unit test on the router with that input.
18. `ledger_posted` is shown as "Not posted" on every board with a `publication`; the page contains no text claiming a posting — verify: e2e on `4205`; grep of the board files for "posted to the ledger" shows only the "Not posted" label.
19. Unknown values read "Not recorded", never 0: `calculated_at:null`, `reviewed_at:null` and a missing date render that way and no money amount is drawn — verify: unit test; e2e on `4202`.
20. `predecessor_id` and `successor_id` show a read-only link line, and no write is attached to it — verify: e2e on `4208`.
21. Error states: 401 shows the signed-out link, 403 `forbidden` no-access, 403 `csrf_failed` is not no-access, 404 reads "This record is unavailable." and is the same for missing and not-yours (`4206`), 429 and 503 offer a retry — verify: unit tests with mocked client; open `/work/4206`.
22. A failed poll keeps the last good board with a "couldn't refresh" note; a 401, 403 or 404 on a poll replaces the page and stops polling; polling runs only on `processing`, `drafting` and `publishing` boards and pauses in a hidden tab — verify: unit test with fake timers.
23. Live check against Django 8030 (account with a Finance review role) on a real management-accounts work id: the page's state, `next_action`, stations and delivery jobs match `GET /api/v1/work/{id}/accounting` — verify: compare the page with the `curl` JSON for the same id; record the id.
24. Viewport check at 1440 and 390 for all five boards against the SCR-53 artboards: parts left out leave no empty gap or empty heading, and the stepper (Chidi investigates through Verified) matches the board — verify: screenshots reviewed against `design/screens.md` SCR-53 artboards.
25. The feature changes nothing under `frontend/src/features/workspace/` — verify: `git diff --stat origin/main -- frontend/src/features/workspace` is empty.
26. New tests exist for the router, each write body (claim, decision, recheck, reassess, reconcile), the one-press rule and the hidden-part absences; `delivery/checks.sh` passes — verify: test files named above run green.

## Out of scope
- Intake, quarantine, unit confirmation, mapping rows, corrected-extract upload, the returned board and the investigating, owner-needed and setup-needed boards (F-105).
- Any resend, retry, cancel or release control; any "record the outcome" input; `release_invoice`.
- Posting to the ledger or any money figure; reviewer names and why nobody can review; per-recipient names, times and receipts; the agent step list; "Ask Chidi"; "Send for output review"; withdraw approval (not in the decision verdicts).
- Changes to `frontend/src/features/workspace`; backend, migrations or contract edits.
- Any other line; the month-end overview; claim and decide for tasks of other lines.

## Assumptions
- The board router lives in F-105's accounts folder and F-106 adds its five cases to it. Reason: both features share one route and `state`, and F-105 merges first.
- Router order and thresholds (section "Board choice") are the best reading of the read. Reason: the API gives the work state, not the board name, and `state` alone cannot separate drafting from investigating.
- `adjustment_ids` for reassess is sent as `[]` when the read gives none. Reason: 1.24.0 returns `sources[]` but no adjustment ids; if the backend rejects an empty list the reassess write is held and listed for the batch.
- The decision evidence is chosen from `review_evidence[]`. Reason: it is the only evidence list on the read, and `evidence_id` is required (Question 1).
- Approve may be sent with an empty note. Reason: the board asks for a note only to return, reject or withdraw; the contract needs the field present, not non-empty. If the backend returns 422 the note is made required for approve too.
- "Receipts recorded: N" uses `receipt_ids.length` only. Reason: no link from a receipt to a delivery job exists.
- Job status words other than `pending`, `leased`, `held`, `unknown` are shown raw. Reason: the full set is not in the contract.
- The five commands send no idempotency key and rely on revision tokens. Reason: none of the five request bodies has a key field.
- The mock serves the live accounting shape for numeric ids 4201 to 4208 and keeps v7 answers for `W-xxxx` ids. Reason: same as F-85.

## Conflicts with the boards
These are the places the spec adds, moves or removes something a board draws. All recommendations are to follow the spec.
1. Reviews: reviewer-name column, the mapping detail line ("maps 412 accounts... 3 accounts are new") and the "Withdraw approval" option are removed. Added: "Check reviewers again" and "Reassess" controls, "Reviewed against" evidence select and the "Take this review" claim button, none of which a board draws. Recommendation: hide the three removed parts; the design engineer draws the four additions.
2. Drafting: the "Results so far" money strip, agent step list, "Started" time, TEST TEMPLATE tag, "Send for output review" and "Ask Chidi" are removed. Added: "Needed before it can be published" list. Recommendation: hide; add the list to the board.
3. Publishing: the recipient table (name, delivered time, receipt state) becomes a list of numbered deliveries with a raw status and a receipt count. Recommendation: accept until the API names recipients.
4. Uncertain: "What we know" timeline (sent time, service confirmation, checked twice) and the recipient's name are removed, and "Record what happened" becomes "Check what happened" with no outcome field. Recommendation: accept; the live action takes no outcome.
5. Verified: the tiles "SOURCE approved", "REVIEWS 6 of 6", "RECEIPTS 3 of 3" and "Changing the source file: NEVER" are replaced by facts the API gives (calculated, published, verified, receipt count, ledger posted "Not posted"). Recommendation: accept.

## Questions
1. The live decision requires an evidence id, and the reviews board has no evidence field. Options: (a) a "Reviewed against" select over `review_evidence[]`, disabled when empty (recommended); (b) a file upload next to the note (not possible: an upload id is not an evidence id, F-85); (c) hold the decide write until the board is redrawn. Context: `POST /tasks/{id}/decision` fails without `evidence_id`.
2. How should the router tell drafting from investigating, since both can be `processing`? Options: (a) use `report_version_id` or `calculated_at` as in the spec (recommended); (b) ask the backend for an explicit stage field; (c) always show drafting for processing. Context: the read has no stage name.
3. Uncertain board action. Options: (a) "Check what happened" with no outcome input (recommended; matches the live action); (b) hold the board until the backend supports recording an outcome; (c) keep the board label "Record what happened" over the same action. Context: the board draws a record step; the API only re-checks the original effect.
4. Recipients on publishing and verified. Options: (a) numbered deliveries and a receipt count (recommended); (b) hide the section entirely until the API names recipients; (c) fill names from setup recipients (not supplied here). Context: `delivery_jobs[]` has only id and status.
5. Verified review tile. Options: (a) show "Reviews: N subjects" and the word approved only where true (recommended); (b) hide the tile; (c) show "6 of 6" as drawn. Context: the number of subjects is not fixed by the contract.
6. Reassess has no board. Options: (a) a small reason form shown only when allowed (recommended); (b) leave it out of this feature and list it for a later board; (c) route to the Django page. Context: the action is live and readiness put it in scope.
