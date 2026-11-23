# A change request's notice, execution, go-live note and closure can be worked from its work page (part 2 of SCR-31)

> Tasks: FE-CHANGE (part 2). Architecture: v9 package; contract `contracts/psl-factory.openapi.json` 1.25.0 (read in the lane-d worktree; builders use the contract on main, 1.26.0 or later). Design: approved 13 Nov canvas with the D-173/D-181 exceptions in `design/review.json`; screens: SCR-31 boards `SCR-31-<desktop|mobile>-{notice,execution,go-live-note,closed}`.

## Summary
- Extends F-112's `pmo-change/v1` adapter. Steps 2 to 5 of the stage track become actionable: review the notice and the go-live note (`document_review`), record the four execution evidence steps (`execution`), close with PM and client signatures (`close`), retry or cancel a delivery job (`operate_delivery`) and restart (`restart`).
- Every control comes from the read: `documents[].verdicts`, `jobs[].can_retry`, `can_close`, `can_restart`. A person who cannot act sees the stage read only.
- The page never says a notice or note was sent unless `jobs[]` or `documents[].receipt_ids` says so, and never says a deployment is authorised.
- Writes are built as one `ChangeActions.tsx` form on F-87's `Actions` slot. Every write sends both revision tokens and `change_version_id`, handles 201 and 409, and `close` sends a fresh `operation_key`.
- Build start waits on F-112 (adapter, stage track, read), F-85 (PR #101) and F-87 (the `Actions` slot). This is not a readiness blocker.

## Context
Worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d`, frontend in `frontend/`. F-112 (its spec: `/Users/Hunchoo/psl-factory-main/delivery/features/F-112/spec.md`) creates `frontend/src/features/change-request/` with the adapter registered through F-85's `registerLineAdapter`, the stage mapper, the read hook, the write error mapper and the mock `frontend/mock/change.mjs`. This feature adds to that folder and does not rewrite F-112's files beyond additive exports. Nothing for these actions exists today (`grep` of `frontend/src` finds no `document_review`, `operate_delivery` or `restart`).
- Shared frame (lane C, unchanged): `frontend/src/features/workspace/**`. F-87 adds the optional `Actions?: ComponentType<LineActionsProps>` on `LineAdapter` with `LineActionsProps = { readback, ctx, commands, reload }`, and `useWorkCommand`. F-89's `WeeklyReportActions.tsx` is the form example. F-85 supplies `EvidencePicker`, `makeCommand`, `CommandDescriptor`.
- Live operations (read from the contract file; `oa.py live` does not run from the records checkout):
  - `GET /api/v1/work/{work_id}/change`, `POST /api/v1/work/{work_id}/change` (201; errors 400, 401, 403, 404, 405, 409, 413, 415, 422, 429, 500, 503).
  - `GET /api/v1/projects/{case_id}/change-versions/{version_id}` (200): `{id, change_id, reference, number, category Standard|Normal|Emergency, module, description, current, evidence_id}`.
  - `GET/POST /api/v1/projects/{case_id}/change-milestone-link`: see Out of scope.

## Contract

### Read fields used here (from `GET /work/{id}/change`, same read as F-112)
`stage`, `documents[]` (max 2) `{id, purpose "notice"|"go_live", verdicts[] (approve|return|reject), receipt_ids[] (int)}`, `jobs[]` (max 30) `{id, status, can_retry}`, `evidence[]` `{id, version, kind}`, `can_close`, `closure_id` (int|null), `can_restart`, `deployment_authorized` (always false), plus the tokens `expected_revision`, `case_revision`, `change_version_id`.
Stage mapping is F-112's (D-6): `notice` -> step 2, `execution` -> 3, `go_live` -> 4, `signatures` and `complete` -> 5. An unknown stage lights no step and shows the raw text.

### What each step shows (presentation only; nothing here decides access)
| Step | Shows | Control (only when the read allows it) |
|---|---|---|
| 2 Notice | the `documents[]` row with `purpose === "notice"`: "Change notice", its review state, receipts count; the `jobs[]` rows with status text as served | Approve / Return / Reject, one per verdict in that row's `verdicts[]` |
| 3 Execution | four rows: Plan updated, Implemented, Testing validated, Documentation updated, each "Recorded" or "Not recorded" only as far as the read tells (the read has no per-kind state, see Assumption 3) | "Record execution evidence" form (below) |
| 4 Go-live note | the `documents[]` row with `purpose === "go_live"`, jobs and receipts as step 2 | Approve / Return / Reject from that row's `verdicts[]` |
| 5 Signatures / closed | `can_close` true: the close form; `closure_id` non-null: "Closed" and the closure id; `stage === "complete"` | "Record signatures"; "Restart" when `can_restart` |
- "Delivered" or "Published" wording is drawn only when the document row has at least one `receipt_ids` entry. Otherwise the page says "Not delivered yet" for a `documents[]` row with an empty `receipt_ids`, and shows each job's `status` text unchanged. No date or time is drawn for a delivery (the read carries none).
- A document row absent from `documents[]` shows "Not drafted yet" and no control.

### `document_review`
Body: `{action:"document_review", expected_revision, case_revision, change_version_id, version_id, verdict, note}`. `version_id` is the chosen `documents[].id` (the contract names it `version_id`; Assumption 1). `verdict` is one of that row's `verdicts[]`. `note` 1 to 4000, required for all three verdicts. Return and Reject show a confirm step. Response 201 `{work_id, state, revision, record_id}`, then re-read.

### `execution`
Body: `{action:"execution", ..., kind, evidence, note, scope_items, dossier_id, candidate_id}`. Form: one `kind` (the four enum values, labelled Plan updated, Implemented, Testing validated, Documentation updated; nothing preselected), `note` 1 to 4000 ("What was done"), `evidence` an id picked from `evidence[]` (nothing preselected; the button is off with "No proof file is recorded for this case yet" when the list is empty), `scope_items` optional list (each 1 to 240, max 100; blank -> `null`). `dossier_id` and `candidate_id` are sent `null`: no board draws them and no read supplies them (Assumption 2). The form is shown only when `stage === "execution"` (Assumption 8).

### `close`
Body: `{action:"close", ..., receipt_id, pm_signature_id, client_signature_id, note, operation_key, mode, pm_signature, client_signature}`.
- Shown only when `can_close === true` and `closure_id === null`. `operation_key` is a new uuid made once per attempt and reused on a retry of that same attempt (`newIdempotencyKey` from F-85); it is not put in `inputs` to `makeCommand` (lane context rule), the descriptor adds it.
- `mode` is "Signed by both" (`signed`) or "Owner applicability, no client signature" (`owner_applicability`); nothing preselected. For `owner_applicability`, `client_signature_id` and `client_signature` are `null`, and a confirm step says "This closes the change without a client signature." For `signed`, both signatures are required.
- `receipt_id`: chosen from the union of `documents[].receipt_ids` (go-live note row first), shown as "Receipt {id}"; nothing preselected; off when empty.
- `pm_signature_id` and `client_signature_id`: chosen from `evidence[]`, nothing preselected, one list per signer; never typed (lane rule: no proof route on this action; D-1). F-85's `fileToEvidence` is not used.
- `pm_signature` and `client_signature` objects (D-7): `source_system`, `source_reference`, `decision_id`, `decision_version`, `signer_reference`, all typed text 1 or more characters, and `signed_at` a date and time sent as an ISO 8601 string with offset. Helper text: "Copy these from the signed proof. Use the real source system, reference, decision id and version, signer and signed time." The page does not default, guess or derive any of them. The client signature section is headed "Client's signature (recorded by you; the client does not log in)".
- `note` 1 to 4000.
- 201 then re-read: `closure_id` set shows "Closed". The board's "closed on 22 Nov with your and Dr Amaka Obi's signatures, verified" is drawn as "Closed" with the signing mode ("Signed by both" or "Owner applicability") and the evidence ids chosen; no names, no date and no "verified" claim, because the read carries none.

### `operate_delivery`
`{action:"operate_delivery", ..., job_id, operation, reason}`. Per `jobs[]` row: "Retry" only when `can_retry === true`; "Cancel" on every job row the read serves whose status text is not one the page recognises as finished (Assumption 4). `reason` 1 to 4000 required. Each shows a confirm step with the reason. Retry never re-sends anything without a press.

### `restart`
`{action:"restart", ..., reason}`, `reason` 1 to 2000, shown only when `can_restart === true`. Confirm step: "This restarts the change from the beginning of its approvals. It cannot be undone here." (Assumption 5, wording only, no rule claimed beyond what the button does.)

### Common write rules (same as F-112)
- Response 201 `{work_id, state, revision, record_id}`; the re-read is the truth. Every body carries `action`, `expected_revision`, `case_revision`, `change_version_id` from the last read; after a 201 the next write uses a freshly read set.
- Idempotency: live has a key only on `close`. For the other actions the submit locks while pending; a second press is ignored; after a network failure or 5xx the form says "We could not confirm this was saved" and offers only "Check again" (re-read, no resend). A 201 whose re-read shows the action applied is treated as saved. For `close`, "Check again" is the same, and the retry path reuses the attempt's `operation_key`.
- Errors: 409 "This change was updated by someone else. Reload to see it." keeping typed text; 403 "You can't record this." (`csrf_failed` refreshes the session and says "Press save again" without resending); 404 "This record is unavailable."; 422 shows `fields[]` messages beside the named field; 413, 415, 429 and 503 as F-85.
- A failed re-read leaves the form locked with "Couldn't refresh" and Try again.

### Permission and tenant rule
Access is whatever the backend allows for the signed-in person; 404 covers missing and not yours. Controls come from the read, never from the person's role in the client. A person who cannot act sees no control and no "you can't" banner. The case id and change version id come from the loaded item, never typed.

### Adapter and files
`ChangeActions.tsx` in `frontend/src/features/change-request/`, registered once as `adapter.Actions` after F-87 is on main. `commands()` (F-112) gains descriptors `document_review`, `execution`, `close`, `operate_delivery`, `restart` with tokens `{expected_revision, case_revision}`; `idempotency.field` is `operation_key` for `close` and `null` for the others; `disabledReason` is set from the read (no `can_close`, no `can_restart`, empty `can_retry`, empty `verdicts`, empty `evidence[]`). Pure body builders live in `frontend/src/features/change-request/changeBodies.ts` and are unit tested.

### Screen states (each of notice, execution, go-live note, closed)
- Loading: work item loading, then the change skeleton (F-112).
- Empty: `documents[]` empty -> "Not drafted yet" on steps 2 and 4; `jobs[]` empty -> no jobs list; `evidence[]` empty -> evidence-needing controls off with the message above.
- Error: mapped messages above with Try again; failed re-read keeps the last good read and shows "Couldn't refresh".
- Success: as drawn, with the board parts that the read supplies.
- Unknown: an absent value renders "Not recorded"; never 0 or a made-up date.

### Fixtures (mock; ids free; add to F-112's `change.mjs`)
- `4301` stage notice: notice document with `verdicts:["approve","return","reject"]`, empty `receipt_ids`, one job `{status:"queued", can_retry:false}`.
- `4302` stage notice, notice delivered: `receipt_ids:[501]`, no verdicts, job `{status:"delivered"}`.
- `4303` stage notice, job `{status:"failed", can_retry:true}`.
- `4304` stage execution with `evidence` of three items; `4305` stage execution with empty `evidence`.
- `4306` stage go_live, go-live note `verdicts` present; `4307` go-live note delivered (`receipt_ids:[502]`).
- `4308` stage signatures, `can_close:true`, `documents` receipts `[501,502]`, `evidence` of three; `4309` `can_close:false` (read only).
- `4310` closed: `stage:"complete"`, `closure_id:77`, `can_restart:true`; `4311` `can_restart:false`.
- `4312` 404. Mock scenarios for 201, 409, 422 with `fields`, 403 `csrf_failed`, 413, 429, 503 and dropped network on each action.
Live check: `GET /work/{id}/change` for a `pmo-change/v1` item with curl and the session on Django 8030.

## Boards
Source: `design/canvas/project/SCR-31-<desktop|mobile>-{notice,execution,go-live-note,closed}.dc.html` (8 boards). What each draws, and what this feature draws from it:
| Board | Draws | This feature |
|---|---|---|
| notice | stage track with 3 done/now, "Change notice" agent card (Tola) with three rows, "Published 13 Nov 11:20", Ask Tola | track, the notice document row with its review controls, receipts, jobs; card, template tag and time hidden (see Conflicts) |
| execution | "Record execution evidence": What was done, Recorded with (Engineering and QA), Proof (uploaded file), "What happens next: Tola drafts the go-live note", Record evidence | form with kind, note, evidence choice, optional scope items; "Recorded with" and the upload hidden/replaced |
| go-live-note | "The go-live note is with the client. The change closes when you and the client sign.", agent card, "Published 21 Nov 09:40", Next: Record the PM and client signatures, Record signatures button | document row, jobs, receipts, "Record signatures" opens the close form when `can_close` |
| closed | "CR-0031 closed on 22 Nov with your and Dr Amaka Obi's signatures, verified. Milestone 3's scope now includes SMS reminders." Next: Open milestones | "Closed", signing mode, `closure_id`; the rest hidden |

## Lanes
- Frontend lane (all of this feature): `frontend/src/features/change-request/**` (add `ChangeActions.tsx`, `changeBodies.ts`, step panels for notice, execution, go-live note and closure, css, tests `*.test.ts(x)`), `frontend/src/api/types.ts` (live change types, additive), `frontend/mock/change.mjs` (fixtures and scenarios, additive to F-112), `frontend/e2e/change-request-closure.spec.ts`.
- Backend lane: none. No backend, migration or contract change.
- Integration owner: lane D coordinator. Shared files: `frontend/src/features/workspace/**` is lane C's and stays unchanged (this feature does not add the `Actions` slot; it registers once F-87 is on main); `frontend/src/api/*` shared (additive types only); `frontend/mock/server.mjs` shared (registration only, if F-112 has not already done it). Any change to `frontend/mock/finance*` or payments fixtures is named in build.md for lane B (none expected).
- `delivery/config.json` protected paths stay unchanged.

## Acceptance criteria
1. `/work/4301` (Next 4990, mock 4991) shows step 2 current, "Change notice" with "Not delivered yet", the job status as served, and Approve, Return and Reject buttons, one per `verdicts[]` entry — verify: open page; `e2e/change-request-closure.spec.ts`.
2. `/work/4302` shows "Delivered" only because `receipt_ids` is non-empty and no review controls (empty `verdicts`); `/work/4301` shows no "Delivered" or "Published" text — verify: e2e; unit test on the status mapper.
3. No delivery date or time is drawn on any step, and the Tola card, "TEST TEMPLATE" tag and "Ask Tola" are absent — verify: e2e DOM assertions; grep copy.
4. Approve sends `POST /work/4301/change` with `{action:"document_review", expected_revision, case_revision, change_version_id, version_id: <documents[].id>, verdict:"approve", note}`; with an empty note the button stays off and no request is sent; Return and Reject open a confirm step and cancelling sends nothing — verify: unit on `changeBodies.ts`; e2e checks the request body in the mock log.
5. A verdict not in the row's `verdicts[]` has no button; `4309`, `4311` and any read with empty `verdicts` show no write control and no banner — verify: e2e.
6. `/work/4304` execution form: nothing preselected for `kind` or `evidence`; the evidence list holds exactly the read's `evidence[]`; submitting sends `{action:"execution", ..., kind, evidence, note, scope_items, dossier_id:null, candidate_id:null}` with blank `scope_items` as `null` — verify: unit; e2e body assertion.
7. `/work/4305` (empty `evidence[]`) disables "Record evidence" with "No proof file is recorded for this case yet" and sends nothing — verify: e2e.
8. The execution form is absent when `stage !== "execution"` — verify: e2e on `4301` and `4306`.
9. `/work/4308` close form: nothing preselected for mode, receipt or either signature; `receipt_id` options equal the union of `documents[].receipt_ids`; both signature lists equal `evidence[]`; no evidence id can be typed — verify: e2e; unit.
10. Mode `signed` requires both signature objects with all six fields filled and `signed_at` as an ISO 8601 string with offset; any empty field keeps "Close the change" disabled; the body has `client_signature_id` and `client_signature` non-null — verify: unit table over each missing field; e2e body assertion.
11. Mode `owner_applicability` hides the client signature section, sends `client_signature_id:null` and `client_signature:null`, and requires the confirm step "This closes the change without a client signature." — verify: e2e; unit.
12. `close` sends `operation_key` as a uuid; after a network drop the "Check again" path re-reads and does not resend; an explicit retry of the same attempt reuses the key and a new attempt makes a new one; a double click sends one request — verify: unit with fake fetch counting calls and keys.
13. `/work/4309` (`can_close:false`) and `/work/4310` (`closure_id` set) show no close form; `4310` shows "Closed", the mode text only if the page itself just sent it (a reload shows "Closed" and `closure_id` only), and no person name, date or "verified" text — verify: e2e.
14. A failed job `4303` shows "Retry" (`can_retry:true`) and "Cancel"; `4301` shows no Retry; each sends `{action:"operate_delivery", ..., job_id, operation, reason}` with a required reason and a confirm step — verify: e2e; unit.
15. `restart` is drawn only when `can_restart` is true (`4310`), asks for a reason (1 to 2000), confirms, and sends `{action:"restart", ..., reason}` once — verify: e2e on `4310` and `4311`.
16. Every write body has `expected_revision`, `case_revision` and `change_version_id` equal to the last read; after a 201 the next write uses freshly read values — verify: unit sequence.
17. A 409 on any action keeps typed text, shows "This change was updated by someone else. Reload to see it.", and sends nothing automatically; a 422 with `fields[]` shows each message by its field; a 403 `csrf_failed` says "Press save again" without resending; 413, 415, 429 and 503 show F-85's wording; a network drop or 5xx shows "We could not confirm this was saved" with "Check again" only — verify: mock scenarios; fetch counts in unit tests.
18. A failed re-read after a 201 leaves the form locked with "Couldn't refresh" and Try again, never a repeat of the write — verify: unit.
19. `/work/4312` and a live work id the caller cannot see both show exactly "This record is unavailable." — verify: open both.
20. `deployment_authorized` is false in every state and no copy says deployment is authorised or the change notice/note "was sent" unless a receipt supports it — verify: unit on the mapper; grep copy.
21. Nothing in the page names a signer or approver the read does not carry, and the "Milestone 3's scope now includes" line and "Open milestones" link are absent — verify: e2e DOM absent; no empty gap in screenshots.
22. No write is made by page load, polling or navigation; POSTs to `/work/{id}/change` come only from a press — verify: e2e asserts zero POSTs on load; `grep -rn "liveApi.POST" frontend/src/features/change-request` shows them only in the command send path.
23. The shared frame is unchanged: `git diff origin/main -- frontend/src/features/workspace` is empty, and `grep -rn "Actions" frontend/src/features/workspace` shows no addition from this feature — verify: those commands.
24. Layout at 1440 and 390 matches the 8 boards for the parts kept (stage track, document rows, forms, closed state), with a vertical track on mobile as in the mobile boards, keyboard order and focus working on forms and confirm steps — verify: screenshots at both widths against the 8 boards; Tab through each form.
25. Against live Django 8030 (Postgres), for a `pmo-change/v1` item at a notice or go_live stage, the page's document rows, receipts and jobs match `curl` of `GET /work/{id}/change`; one `document_review` on a test change returns 201 and the re-read shows it; any action that cannot be exercised live is stated in build.md rather than claimed — verify: compare page and curl; record the response.
26. New unit tests cover the five body builders, the stage and document status mappers, the close validation table, null handling and the error mapper; `npm run lint`, `npm run typecheck` and `npm test` pass — verify: `delivery/checks.sh`.

## Out of scope
- All of part 1: log, assess, decide, authorise, the change list and `capture`, `preapprove`, `bind_standard` (F-112).
- `change-milestone-link` (read and `POST`) and the board's "Milestone 3's scope now includes SMS reminders" and "Open milestones" link: no board draws the link form, and the closed board's line depends on it (D-182; Question 3).
- `GET /projects/{case_id}/change-versions/{version_id}`: its fields (reference, category, module, description) already reach the page through F-112's `ordinary-changes` lookup; this feature does not call it.
- Agent cards, "Ask Tola", "TEST TEMPLATE" tags, cited records, decider and signer names, delivery times, any "verified" claim (DC-3, D-182).
- Drafting, publishing or sending the notice or go-live note, or any message to a client; deployment of any kind.
- Uploading a file and turning it into an evidence id (D-1 gives no route on these actions); `fileToEvidence`.
- A Retry or Cancel on a document or job the read does not list; client-side role checks; backend, migration or contract changes; changes to `frontend/src/features/workspace`.

## Assumptions
1. `document_review.version_id` is the `documents[].id`. Reason: the read names the row `id` and no other id exists for a notice or note version.
2. `dossier_id` and `candidate_id` on `execution` are sent `null`. Reason: they are required keys but no board draws them and no read supplies a value; nothing is invented.
3. Per-kind execution state is not shown ("Recorded" ticks) because the read has no field for it; after a 201 the page states "Evidence recorded" for that kind in the session only and the re-read stage is the truth. Reason: the contract carries only `stage`.
4. "Cancel" is offered on any listed job whose status text is not "delivered", "cancelled" or "complete" (case-insensitive); unknown status text keeps Cancel on and the server rejects an invalid cancel with its own error. Reason: `status` is an unconstrained string and there is no `can_cancel` field.
5. Restart and close confirmation wording describes only what the button does; no policy is stated. Reason: sources are silent on the rule.
6. `signed_at` is entered with a date-time control and sent as an ISO string with the browser's offset. Reason: the contract requires `date-time` and does not fix a timezone.
7. The receipt for `close` is chosen from `documents[].receipt_ids`. Reason: it is the only receipt id the read supplies; if the backend expects another receipt, the 422 text shows it.
8. The execution form shows only at `stage === "execution"`. Reason: the board draws it as the step-3 action.

## Conflicts with the boards
1. Removed: Tola's agent cards with their rows, "TEST TEMPLATE" tags, "Published 13 Nov 11:20" and "Published 21 Nov" times, "Ask Tola" (notice and go-live-note boards). Reason: no read supplies them; the read serves only receipts and job status. Recommendation: hide, draw "Delivered" from receipts only.
2. Added: Approve, Return and Reject on the notice and go-live note with a required note and confirm step. No board draws the review, but `document_review` is the only action on those stages. Recommendation: build and flag.
3. Changed: the execution board draws one "What was done" note, "Recorded with Engineering and QA" and an uploaded proof. The contract takes one of four typed kinds, an evidence id from the case's recorded evidence, optional scope items. Recommendation: replace "Recorded with" with the kind choice, replace the upload with the evidence choice.
4. Removed: "What happens next: Tola drafts the go-live note" (the read gives `next_action`; show that when non-empty).
5. Added: the whole close form (mode, receipt, two signature evidence choices, two source-field blocks, note) behind "Record signatures". The go-live-note board draws only the button. Recommendation: build and flag; D-7 requires every source field.
6. Removed: "closed on 22 Nov with your and Dr Amaka Obi's signatures, verified", "Milestone 3's scope now includes SMS reminders", "Open milestones". Replaced by "Closed" and the closure id. Recommendation: as the spec.
7. Added: jobs list with Retry and Cancel, owner applicability mode, Restart, confirm steps and the "Check again" recovery state. No board. Recommendation: build and flag.
8. Moved: crumb and project tabs sit on the board; the work frame has none (F-112 Question 7 recommendation: crumb back link only).

## Questions
1. The close form and the document review controls have no board. Options: (a) build plain forms from existing form components and flag them for a board later (recommended; the actions are the only way to progress the change); (b) hold the close form until a board is drawn; (c) hide both and leave the steps read only. Context: Conflicts 2 and 5.
2. Execution evidence: the board's single "What was done" note versus four typed steps. Options: (a) one form with a required kind choice, repeated for each step (recommended; matches the contract); (b) four separate forms on the page; (c) default the kind to "Implemented" (not recommended, invents a value). Context: the contract requires `kind`.
3. The closed board's "Milestone 3's scope now includes" line and "Open milestones" link depend on `change-milestone-link`, which has no board. Options: (a) leave them out now and build the link as its own part later (recommended, D-182); (b) add a "Link to a milestone" form from `plans[]` and `stages[]` on the closed page; (c) show the link only as a text "Open milestones" with no claim about scope. Context: the read-only milestone list at SCR-43/44 is separate.
4. `close` source fields (D-7) are typed by the PM from the retained proof. Options: (a) six plain text fields per signer with helper text (recommended); (b) prefill from the evidence item's kind or version (the read carries none, would invent values); (c) hold until the backend serves the proof's source record. Context: D-7 says the identifiers must come from the retained proof.
5. "Cancel" appears on every job not clearly finished (Assumption 4). Options: (a) as written, with the server rejecting an invalid cancel (recommended); (b) show Cancel only when `can_retry` is true; (c) hide Cancel until the read carries a `can_cancel`. Context: the read has `can_retry` only.
