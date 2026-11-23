# The weekly client report can be corrected after a return, and approved, returned or refused by its reviewer, live

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.22.0. Design: approved 13 Nov canvas under the recorded exception in `design/review.json` (delivery may continue on the current design version); screens: SCR-25 (states review, returned, received).

## Summary
- On the weekly report panel of a live work item, "Edit your update" appears only when the readback says `can_correct`. It opens four text boxes (Status, Risks, Timeline, Next steps) and a required "Reason for the change", and sends `POST /work/{id}/weekly-report` `action:"correct"`.
- Review buttons ("Approve and send", "Return with a note", "Refuse") appear only for the verdicts listed in the readback's `review_verdicts[]`, and only when `document_version_id` is set. They send `POST /work/{id}/reviews` `kind:"document"`. The client decides nothing about who may review; a 403 or 409 is shown as the server gave it.
- Approving reaches the client, so success is told only from a re-read of the report and the item. Neither body has an idempotency key, so after a timeout or 5xx every write on this report stays locked until a re-read shows the report moved (F-87's uncertain lock, reused).
- Everything goes through F-85's `LineAdapter`/`CommandDescriptor` (the `weeklyReportAdapter` gains review descriptors next to its `correct`) and F-87's shared locking and `useWorkCommand`. No new lock, key or error mapping is defined here.
- The returned note text, cite labels and the assembled report text are not served by the API (C-16, C-15, C-17); none is drawn or invented.

## Context
Lane C worktree `/Users/Hunchoo/psl-factory-worktrees/lane-c/frontend`. This feature builds after F-85 and F-87 have merged.
- Adapter (F-85): `src/features/workspace/adapter.ts` (`LineAdapter`, `CommandDescriptor`, `makeCommand`, `readPanel`, `registerLineAdapter`) and `src/features/workspace/weeklyReportAdapter.ts`. Its `sections()` already draws Period, parts with "N records cited", "Returned to you" (when `return_review_id` is set, no note text), Recipients and Next. Its `commands()` returns only `weekly-report.correct` (tokens `expected_revision`, `case_revision`; `disabledReason` when `can_correct` is false) and is tested for shape only.
- Locking (F-87): `src/features/workspace/useWorkCommand.ts` (press lock, one write at a time, uncertain lock, reload on 409, error words from `ApiError`) and the shared piece extracted from `useWorkspaceStep.ts`. It takes `{ item, reload }` and today sends the five work-item controls built by `workItemCommands`.
- Page: `src/features/work-item/live/LiveWorkItemView.tsx` (`PanelView` draws a registered adapter's sections), `live/useLiveWorkItem.ts`, `live/model.ts`. `GET /work/{id}` gives `panels[{key:'weekly-report', url}]`, `revision`, `case_revision`, `actions[]`.
- Errors: `src/api/errors.ts` (`ApiError.kind`: `unauthenticated`, `forbidden`, `csrf`, `not_found`, `stale`, `invalid`, `rate_limited`, `read_limited`, `network`, `server`; `fields`), `call()`, `liveApi`, `refreshSession()` in `src/api/client.ts`. Types: `LiveWeeklyReport` in `src/api/types.ts` and `src/api/live-schema.d.ts`.
- Mock: `mock/work-live.mjs` (live-shaped work items 4101 to 4107, weekly report at `/api/v1/work/{id}/weekly-report` read-only) and `mock/server.mjs`.
- Components to reuse: `Button`, `Callout`, `Dialog`, `FormField`/textarea already used by `StepForm.tsx`; no new component library.
- Not usable here: `src/app/projects/[caseId]/documents/[documentId]/page.tsx` is the v7 document page; live `document-reviews/{version_id}` is not wired (backend question B-7), so no "open the report as the client will see it" link is drawn.
- Contract 1.22.0:
  - `GET /work/{id}/weekly-report` (required keys): `expected_revision`, `case_revision` (ints, 1..2147483647), `selection{start_at,end_at,template_id|null,content_id|null}`, `editable_parts|null`, `draft|null {id, values{selection, parts, ...}}`, `return_review_id|null`, `can_correct`, `document_version_id|null`, `review_verdicts[]` (each `approve|return|reject`), `recipients[{name,status,receipt_id|null,recorded_at|null}]`, `next_action`, `evidence[]`.
  - `POST /work/{id}/weekly-report` body (all required, `additionalProperties:false`): `{action:'save_draft'|'correct', expected_revision, case_revision, draft_id|null, selection{template_id|null, content_id|null, start_at, end_at}, parts{status,risks,timeline,next_steps: {text (<=10000), evidence_ids[] (<=18, unique)}}, reason (1..2000)}`. 201 is either `{draft_id, case_revision}` (save_draft) or `{work_id, state, revision}` (correct). No key field.
  - `POST /work/{id}/reviews` document variant (all required, `additionalProperties:false`): `{kind:'document', expected_revision, case_revision, version_id, verdict:'approve'|'return'|'reject', note (string, <=4000)}`. 200 `{work_id, state, revision, review_id|null}`. No key field. Errors on both: 400, 401, 403 (incl. `csrf_failed`), 404, 409, 413, 415, 422, 429, 500, 503 as `{code, message, fields?}`.
  - The field is `verdict` (not `decision`), and `case_revision` is required on reviews.

## Contract

### Commands (descriptors)
`weeklyReportAdapter.commands(readback, ctx)` returns four descriptors, built with `makeCommand` and tokens from the weekly-report readback (not from the work item), a `null` or missing token stays null:

| id | label | offered when | url | body | success |
|---|---|---|---|---|---|
| `weekly-report.correct` | Send for review | `can_correct === true` and `editable_parts !== null` | `/api/v1/work/{id}/weekly-report` | `{action:'correct', expected_revision, case_revision, draft_id, selection, parts, reason}` | 201 |
| `weekly-report.approve` | Approve and send | `document_version_id !== null` and `review_verdicts` includes `approve` | `/api/v1/work/{id}/reviews` | `{kind:'document', expected_revision, case_revision, version_id, verdict:'approve', note}` | 200 |
| `weekly-report.return` | Return with a note | same, `return` | same | same with `verdict:'return'` | 200 |
| `weekly-report.reject` | Refuse | same, `reject` | same | same with `verdict:'reject'` | 200 |

- `makeCommand` gains one more optional spec field (additive, next to F-87's `action: null`): `fixed?: Record<string, unknown>`, merged into the body, used for `kind:'document'`. Review descriptors use `action: null` so no `action` key is sent. Existing callers and `adapter.test.ts` stay unchanged. None of the four bodies has a key field, so `idempotency.field === null` and no key is sent.
- `correct` body inputs come from the form and the readback: `draft_id` is `draft.id` or `null`; `selection` is the readback `selection` as given (all four members, nulls kept); `parts` is the four parts from the form text with each part's `evidence_ids` returned exactly as read from `editable_parts`; `reason` is the typed reason. The client never adds, removes or reorders cites.
- Review inputs: `version_id = document_version_id` from the readback, `note` from the box (empty string for approve when left empty).
- `disabledReason` (shown beside the control, never only as a tooltip): when a needed token is null or undefined, "We don't have this report's current version yet. Reload and try again."; for `correct` when `can_correct` is false, the existing "This report can’t be corrected now."; when `can_correct` is true but `editable_parts` is null, "The report parts aren't available to edit here." No reason is invented for a verdict the API does not list: that button is simply not drawn.
- `commands()` for review is empty when `document_version_id` is null, whatever `review_verdicts` says.

### Send, lock and result
`useWorkCommand` (F-87) is the only sender. Additive change, only if F-87 did not already provide it: `run(descriptor, inputs)` so a caller outside `workItemCommands` can send a descriptor, and an optional `reload` that re-reads both the work item and the weekly-report panel; F-87's behaviour for its five controls does not change.
- One lock for the whole report: while any of Send for review, Approve and send, Return with a note or Refuse runs, all of them (and the F-87 control row) are disabled, and a second press sends nothing.
- A new descriptor is made for each attempt (new `makeCommand` call). A descriptor that ended with an unknown result is never resent without a re-read in between.
- Success (status in `successStatuses`): re-read the panel and the item, and tell the result from the re-read, never from the 200/201 alone:
  - Review: "Recorded. This item is now: {state tag words}." using the re-read `state`/`status_label`. When the re-read recipients show `receipt_id` null, say nothing about delivery; the Recipients section keeps showing "No receipt yet". The words "Sent" or "Delivered" are not used for a review result, only for what the recipients rows say.
  - Correct: "Your update was sent for review. This item is now: {state tag words}." from the re-read.
  - If the re-read fails: "Sent. We couldn't reload the item; reload the page to see its state." and every control on the report stays locked until a read succeeds.
- Errors (words from `ApiError`; the server `message` is shown as given for 403 non-csrf, 409 and 422):
  - `unauthenticated` / `not_found`: replace the page with the existing signed-out / "This record is unavailable." state.
  - `forbidden` (403, not csrf): "You can't do this. {server message}"; re-read; no retry. This is how a self-review or any other independence rule appears; the client has no rule of its own.
  - `csrf` (403 `csrf_failed`): `refreshSession()` once, say "Press the button again". No automatic second send.
  - `stale` (409): re-read the panel and item, say "This changed while you were working. Showing the latest version.", show the server message under it; the press is not repeated. The form keeps what was typed.
  - `invalid` (422): show the server `message` and each `fields[].message` as given; the first field whose `name` equals `status`, `risks`, `timeline`, `next_steps`, `reason` or `note` is shown under that input, others in the callout; no retry; the panel is re-read; typed text is kept.
  - `rate_limited` and 503 `read_limited`: "Try again shortly." No automatic retry.
  - `network` or `server` (timeout, 5xx, dropped connection): uncertain. Re-read the panel and item, say "We couldn't confirm that this happened. Check the page before trying again.", and lock all four report commands. They unlock only when the re-read readback shows an `expected_revision` different from the one sent, or when the person reloads the page. If the item lists `reconcile` (F-87), "Check what happened" is the person's route; this feature draws nothing for it. Typed text and note are kept while locked.
- A null token: no request is made; the control shows its `disabledReason`.
- No timer, effect or poll sends a write; a write happens only from a press.

### Screen: SCR-25 on the live work item
Drawn inside the existing weekly report panel, after the sections `weeklyReportAdapter` already draws.
- Review block ("Your review"), drawn only when the review descriptors exist: a Note textarea ("Note", help "Needed to return or refuse", max 4000, character count shown near the limit), then the buttons for the verdicts offered, in the order Approve and send, Return with a note, Refuse. The static line "Approving sends this exact version to the client." sits above the buttons (the board names the client; the name is not served, so it says "the client"). On phone the buttons stack full width.
- Return and Refuse require a non-empty note (after trim) before any request; the empty case shows "Write a note first." under the Note and sends nothing. Approve sends the note as typed (possibly empty). This matches the board's "needed to return or refuse"; the server's 422 is still shown if it disagrees.
- Edit block, drawn only when `weekly-report.correct` is offered: the "Edit your update" button opens the form inline (no modal): four labelled textareas (Status, Risks, Timeline, Next steps) prefilled from `editable_parts`, a line under each "N records cited" (not editable), a required text input "Reason for the change" (1..2000), buttons "Send for review" and "Cancel" (discards typed text and closes). The board's line "Edit your part, then Tola reassembles v2 and it goes back for review." stays as the help text. Send for review is disabled until all four parts and the reason are non-blank and within their limits, the reason for the disabled state being shown as field messages, not a tooltip.
- States:
  - Loading: the panel's existing loading state; no review or edit block until the readback has loaded.
  - Empty: no verdicts offered and `can_correct` false (for example `received`, or someone else's turn): no block, no heading, no gap.
  - Pressing: the pressed button reads "Working..."; all report controls disabled.
  - Success: one `Callout` (status) under the blocks with the result words above; blocks redraw from the re-read (a review that is no longer offered disappears).
  - Error: one `Callout` (alert) with the mapped words; controls enabled again unless the uncertain lock applies, in which case each locked button is disabled with the sentence "Check the page before trying again." beside it.
- Not drawn, because the API does not serve them: the returned note text (the page keeps "Returned to you" with no quote), cite labels, the assembled report text and byline ("written by ... assembled by Tola"), "Open the report as the client will see it", the "What happened" timeline, "Approved by ... at ..." words. Recipients and receipts show as the adapter already draws them.

### Fixtures (mock; ids free numbers, builder adds to `mock/work-live.mjs`; 4112 to 4119 are left for other lanes)
- `4120` in review, all verdicts: `document_version_id:9101`, `review_verdicts:['approve','return','reject']`, `expected_revision:6`, `case_revision:12`, `can_correct:false`.
- `4121` review offered `['approve','return']` only.
- `4122` returned: `return_review_id:7001`, `can_correct:true`, `editable_parts` with cites `[301]`,`[302,303]`,`[]`,`[304]`, `review_verdicts:[]`, `document_version_id:9101`.
- `4123` neither: `can_correct:false`, `review_verdicts:[]`.
- `4124` verdicts listed but `document_version_id:null`: no review controls.
- `4125` `editable_parts:null`, `can_correct:true`.
- Writes: review answers 200 `{work_id, state:'waiting', revision:7, review_id:8001}` and the next readback has `review_verdicts:[]`, `expected_revision:7`, `recipients` with `receipt_id:null`; correct answers 201 `{work_id, state:'processing', revision:7}`, next readback `can_correct:false`, `review_verdicts:[]`.
- Scenarios (existing F-85/F-87 mechanism) for both routes: 403 `forbidden` (message "You wrote this report, so you can't review it."), 403 `csrf_failed`, 409 `stale_version` (then the GET returns a higher revision), 422 with `fields:[{name:'note', message:'A note is needed to return a report.'}]` and one for `reason`, 429, 503, 500 and a dropped connection (the dropped and 500 cases apply the write in the mock, so the re-read shows the report moved or not, selectable per scenario).

### Idempotency and versioning
- `expected_revision` and `case_revision` are the weekly-report readback's values, sent as given, never defaulted or 0; the readback is re-read after every write so the next press carries fresh ones.
- Neither body has a key. Duplicate presses are prevented by the press lock, the uncertain lock and the revision check, not by a key.

### Permission and tenant rules
- Whether the person may review or correct is the server's answer: the controls are drawn from `review_verdicts[]` and `can_correct` and a 403 or 409 is shown as given. No role, identity or "not the author" check exists in the client.
- Calls use only the loaded item's `work_id` and the readback's `document_version_id`; there is no input for either. A 404 shows "This record is unavailable." (same as a missing record).

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/workspace/weeklyReportAdapter.ts`, a new `frontend/src/features/workspace/WeeklyReportActions.tsx` (review block and edit form) with its CSS beside `workspace.css` additions, `frontend/src/features/workspace/adapter.ts` (additive `makeCommand` field only), `frontend/src/features/workspace/useWorkCommand.ts` (additive `run(descriptor, inputs)` and panel reload only), `frontend/src/features/work-item/live/LiveWorkItemView.tsx` (mount the block under the weekly report panel), `frontend/src/api/types.ts` (types for the two bodies and responses), `frontend/mock/work-live.mjs` and `mock/server.mjs` routes, tests under `frontend/src/**` and `frontend/e2e/work-item-weekly-report.spec.ts`.
- Backend lane: none. No backend, contract or migration change. Questions LC-9 and LC-10 are in `delivery/connect/backend-questions.md`.
- Integration owner: lane C coordinator. Shared files: `src/features/workspace/*` (lane C owns frame, adapter and locking; the changes here are additive and land after F-85 and F-87 merge; other lanes rebase via `git merge origin/main`), `src/api/*` (shared; types only), `src/components/*` (used as is), `src/features/response/*` and `useWorkspaceStep.ts` (v7; not touched).
- Build order: F-85, then F-87, then this.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4120` (mock) shows "Approve and send", "Return with a note" and "Refuse" and a Note box; `/work/4121` shows the first two only; `/work/4123` shows no review block, no heading and no gap — verify: open the pages; `frontend/e2e/work-item-weekly-report.spec.ts` asserts buttons by name and absence.
2. `/work/4124` (`document_version_id:null`) shows no review buttons even though verdicts are listed — verify: e2e plus unit test on `weeklyReportAdapter.commands`.
3. Approve on `/work/4120` sends exactly one `POST /api/v1/work/4120/reviews` with body `{"kind":"document","expected_revision":6,"case_revision":12,"version_id":9101,"verdict":"approve","note":""}`: no `action`, no key, no `decision` field — verify: e2e captures the body; unit test on the descriptor `body()`.
4. Return and Refuse send the same shape with `verdict` `return` / `reject` and the typed note; with an empty or blank note they send nothing and show "Write a note first." — verify: e2e counts requests; unit test.
5. After a 200 the page re-reads the report and the item, and shows "Recorded. This item is now: {state tag}." from the re-read; the review buttons disappear when the re-read no longer offers them; the page never says "Sent" or "Delivered" for a review result and the recipients still read "No receipt yet" when `receipt_id` is null — verify: e2e on the mock; DOM text assertion.
6. If the re-read after a success fails, the page says "Sent. We couldn't reload the item; reload the page to see its state." and all report controls stay disabled — verify: unit test of the run path with a failing reload.
7. `/work/4122` shows "Edit your update" (and "Returned to you" without any note text); `/work/4123` and `/work/4125` show no working edit button (4125 shows its `disabledReason`); a `can_correct:false` report shows no edit block — verify: e2e on all three; unit test on descriptors.
8. The edit form is prefilled from `editable_parts`, shows "N records cited" per part and has no cite control; "Send for review" is disabled while a part or the reason is blank, or over 10000 / 2000 characters — verify: component test.
9. Send for review sends one `POST /api/v1/work/4122/weekly-report` with `{"action":"correct","expected_revision":…,"case_revision":…,"draft_id":null,"selection":{…as read, nulls kept…},"parts":{…four parts, each with its original evidence_ids…},"reason":"…"}`; no key field, no other keys — verify: e2e captures the body and compares `evidence_ids` and `selection` with the readback; unit test.
10. After the 201 the page re-reads and says "Your update was sent for review. This item is now: {state tag}." with the re-read state; the edit block is gone when `can_correct` is now false — verify: e2e.
11. A double click on any of the four buttons sends one request; while one runs every control on the report and the F-87 control row is disabled; a poll result arriving mid-write does not clear the lock or the notice — verify: unit test with fake timers and a deferred POST; e2e counts requests.
12. A null or missing token sends nothing and shows "We don't have this report's current version yet. Reload and try again."; no body contains 0 or null for `expected_revision` or `case_revision` — verify: unit test with a readback missing the tokens.
13. A 409 `stale_version` re-reads the report, shows "This changed while you were working. Showing the latest version.", keeps the typed note or form text, does not repeat the press, and the next press carries the new revisions — verify: e2e with the 409 scenario capturing both requests.
14. A 403 `forbidden` shows "You can't do this." with the server message (for example the self-review message), re-reads, makes no retry, and the page offers no other route around it; a 403 `csrf_failed` refreshes the session once, says "Press the button again" and sends nothing more — verify: unit test counts POST and session calls; e2e on the forbidden scenario.
15. A 422 shows the server message and puts a `note` or `reason` field message under that input, keeps the typed text and re-reads — verify: e2e with both 422 scenarios.
16. A 429 and a 503 each say "Try again shortly." and send nothing further over 30 s of fake time — verify: unit test.
17. After a dropped connection or a 500 on Approve, Return, Refuse or Send for review: the report is re-read, "We couldn't confirm that this happened. Check the page before trying again." appears, all four buttons are disabled with "Check the page before trying again." beside them, typed text is kept, and no second request is sent by the page over 60 s of fake time; the buttons unlock only when a re-read shows a different `expected_revision` (mock scenario where the write was applied) or after a page reload — verify: unit test with fake timers; e2e drops the connection in both mock variants (applied and not applied); in the not-applied variant the controls stay locked until reload.
18. A 404 on a write replaces the page with "This record is unavailable."; a 401 shows the signed-out state with a link to `/sign-in?next=` the current path — verify: unit tests with a mocked client.
19. No write is made by load, polling or navigation, and the review and correct POSTs appear only in `useWorkCommand`'s send path: `grep -rn "liveApi.POST" frontend/src/features/work-item frontend/src/features/workspace` shows no new call site other than inside `useWorkCommand` and F-85's upload calls; e2e asserts zero POSTs on load — verify: grep and e2e.
20. The returned note, cite labels, assembled text, "Open the report as the client will see it", "What happened" and "Approved by" are not drawn, and no "not available" placeholder text appears — verify: e2e DOM assertions on 4120 and 4122.
21. The v7 paths are unchanged: `useWorkspaceStep` tests, F-87's control-row tests and `/work/W-xxxx` pages pass without edits — verify: `npm test`, `frontend/e2e/workspace.spec.ts`, `work-item.spec.ts`, `work-item-controls.spec.ts`.
22. Unit tests exist for the four descriptors (ids, urls, bodies, null-token hold, `fixed` and `action:null` handling) and for `WeeklyReportActions` states (loading, empty, pressing, success, each error kind) — verify: `npm test` lists them; `adapter.test.ts` still passes.
23. Against live Django (8020, Postgres 55433, account live-lead and a second reviewer account): on a weekly report work item where `GET /api/v1/work/{id}/weekly-report` lists `review_verdicts`, a review by the account the API lists returns 200 and the page then shows the readback's state; the author account sees no review block (or gets the server's 403 message if the API listed one); record the JSON of each response and compare the page with `oa.py live GET /api/v1/work/{id}/weekly-report 3` before and after. On a returned report, "Send for review" returns 201 and `document_version_id`/`review_verdicts` on the re-read are shown as served — verify: the recorded JSON and the page.
24. Viewport check at 1440 and 390: the review block and edit form have no overlap, buttons stack full width on the phone, the review block leaves no empty gap when absent, and the parts that remain match the SCR-25 review, returned and received artboards — verify: screenshots against `design/screens.md` SCR-25 artboards (see Conflicts with the boards).
25. `npm run lint`, `npm run typecheck` and `npm test` pass; `api-live-schema-drift.test.ts` still passes — verify: `delivery/checks.sh`.

## Out of scope
- Release invoice (`POST /work/{id}/actions` `release_invoice`, F-90); weekly report intake, save draft and start (F-86); reconcile, resume, cancel and background (F-87); corrections and coordination retry features (DC-1..DC-5); any other line's review (`kind` bid, closure, asset, schedule, payroll, business_unit).
- Showing the returned note, the assembled report text, cite labels, a "What happened" timeline, "Approved by" words, or a link to the client-facing preview; choosing or adding cites in the edit form; `save_draft` on a started report.
- Any client-side rule about who may review, whether the author may review their own report, which state allows which verdict, or how many reviews are needed.
- A delivered / not delivered choice, proof, or retry of an uncertain send (the F-87 "Check what happened" button is the only route).
- A confirmation dialog on Approve, an Undo, and any new endpoint, state, page or copy beyond what is written above; backend, migrations, contract edits.

## Assumptions
- Return and Refuse need a non-empty note in the form. Reason: the board says the note is "needed to return or refuse"; the contract only requires the field to exist. The server's own 422 still shows if it differs.
- The third verdict is labelled "Refuse". Reason: the board's note uses "refuse" and the prior v7 step was `refuse`; no board draws the button (LC-Q14).
- The uncertain lock covers all four report commands together, and unlocks when the readback `expected_revision` changes. Reason: a second verdict or edit after an unknown result could contradict the first or repeat the client message; a changed revision is the only readable proof the report moved (same rule as F-87).
- No Approve confirmation dialog. Reason: the board has none and shows the line "Approving sends this exact version"; the uncertain lock and the revision token cover duplicates. Flagged in LC-Q14 option 2.
- Cites are returned exactly as read and are not editable. Reason: there is no cite picker data (labels, C-15) and an edit that changed cites would be a guess; the server rejects an invalid set.
- "Reason for the change" is a new required input. Reason: the live body requires `reason` (1..2000) and the board draws none (LC-Q15).
- The reviewer sees the parts only if the readback serves them (`editable_parts` or `draft`); the readback is not documented to serve parts to a reviewer (LC-10). Reason: nothing else carries the text.
- `draft_id` is sent as `draft.id` or null. Reason: the contract requires the key; null is allowed.
- Success wording quotes the re-read state tag words, as in F-87. Reason: no outcome text is served.
- Fixture ids 4120 to 4125 are the builder's to create; the shapes are the contract. Reason: no live fixtures exist.

## Conflicts with the boards
Entered in `delivery/connect/questions-batch.md` under "## Lane C" as LC-Q14 to LC-Q16; recommendations first. The design approval rests on the recorded exception, so the design engineer decides these once before build.
1. SCR-25 review board draws two buttons ("Approve and send", "Return with a note"); live also allows reject. This spec adds "Refuse", shown only when listed. Recommendation: LC-Q14 option 1.
2. SCR-25 review board shows the report text (four parts with cites), the byline, an "Open the report as the client will see it" link and "Decide · PMO Lead". The API serves none of the byline or link, and the readback may not serve the parts to a reviewer. This spec draws what the readback serves, the "Your review" heading instead of "Decide · PMO Lead" (role not served) and no link. Recommendation: LC-Q16 option 1.
3. SCR-25 returned board quotes the reviewer's note and names the reviewer and date, and "Edit your update" opens an edit state no board draws. This spec shows "Returned to you" with no quote, and adds an inline edit form with four text boxes, "N records cited" and a required "Reason for the change". Recommendation: LC-Q15 option 1.
4. SCR-25 received board's "What happened" timeline and "Approved by ... at ..." are not drawn; the Recipients rows are. Already covered by LC-Q1 (hide what the backend does not supply).
5. The boards name the client ("Lagoon Health") in "Approving sends this exact version to ..."; this spec says "the client" because no client name is served.

## Coordinator note (lane C, 23 Nov)
LC-Q16: the lane C coordinator changed the recommendation to "do not draw Approve until the report parts are shown on the page; Return and Refuse stay", because approving sends the report to the client and the reviewer must see what goes out. Build that, not option 1 above. The design engineer's batch-2 answer overrides this.

D-183 (batch 2): the design engineer confirmed LC-Q16 "Hold Approve" and LC-Q14 "Add Refuse" (one button per verdict the API lists). LC-Q10 to LC-Q15 accepted as recommended.
