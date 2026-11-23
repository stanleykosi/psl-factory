# The issue page records owner updates and replies, sets the owner and messages the owner (SCR-30 part 2)

> Tasks: FE-CONNECT-1. Architecture: v9 package; contract `contracts/psl-factory.openapi.json` 1.25.0 (lane-d worktree, main d906028a / 8484668a lineage; use 1.26.0 if main has moved, per D-188). Design: approved 13 Nov canvas under the D-173/D-181 exceptions in `design/review.json`; screens: SCR-30 (default, overdue, no-owner, verified; 8 boards `design/canvas/project/SCR-30-*.dc.html`).

## Summary
- On `/work/{id}` for a `pmo-issues/v1` item, a permitted person (1) posts an owner update, (2) records the owner's reply, (3) sets an owner, and (4) prepares, reviews, releases and reconciles a message to the owner. The page then shows the server's re-read, not the response alone.
- All four forms live in one new file, `IssueFollowupActions.tsx`, registered as the issue adapter's `Actions` slot (F-87). They send through `useWorkCommand`. Nothing under `frontend/src/features/workspace` changes.
- Every control is drawn only when the server's flags allow it. Revision tokens come from the reads and are never defaulted to 0. Proof is always chosen from a served evidence list; no evidence id is invented.
- Message release goes out only through the server's review and release steps, by a press. After an uncertain send the page locks, re-reads, and offers only "Check what happened" before any retry.
- Waits (build start, not blockers): F-111 (part 1 merges), F-85 (PR #101, shared adapter), F-87 (`Actions` slot, `useWorkCommand`). High risk (external message, assignment): UI review, security review, design engineer's merge batch.

## Context
- Part 1 (F-111, `delivery/features/F-111/spec.md`) adds `frontend/src/features/issue-followup/issueFollowupAdapter.ts` (key `issue-followup`, readback `{followup, detail, messages | {error}}`, `commands()` returns `[]`, the `expected_revision` and `case_revision` held unused). This part adds `IssueFollowupActions.tsx` beside it and fills `commands()`.
- Seam (F-87): `LineAdapter.Actions?: ComponentType<LineActionsProps>`, `LineActionsProps = { readback, ctx: LineContext, commands: CommandDescriptor[], reload }`. Example form: F-89's `WeeklyReportActions.tsx`. `makeCommand` and `CommandDescriptor` are in `workspace/adapter.ts` (F-85).
- Live operations (all in the lane-d worktree `contracts/psl-factory.openapi.json`; code in `apps/core/factory_api/issues.py`, `apps/pmo/issue_teams.py`):
  - `POST /api/v1/work/{work_id}/issue-followup` (`issues_work_command`), 200 `{work_id, state, revision}`. Action `respond` takes `{expected_revision, case_revision, task_id, task_revision, operation: acknowledge|start|progress, evidence_id, note, next_action, team_reply: {assignment_id, operation_key, party, channel: email|whatsapp|ticket|meeting|phone|document, responded_at|null, source_ref} | null}`.
  - `POST /api/v1/projects/{case_id}/issues/{issue_id}/team-replies` (`issues_team_reply`), 201 `{issue_id, state_id, case_revision}`. Body `{case_revision, state_id, assignment_id, operation_key, party, channel, responded_at|null, source_ref, operation: acknowledge|start|progress|resolve, evidence_id, note, next_action, fix_id, root_cause_id, resolution_role}`.
  - `POST /api/v1/projects/{case_id}/issues/{issue_id}/assignment` (`issues_assign`), 201 `{id, case_revision}`. Body `{case_revision, state_id, mode: team|internal, team_key, recorder_id, recorder_role, evidence_id, reason}` (`work_id`, `source_id` optional).
  - `POST /api/v1/projects/{case_id}/issues/{issue_id}/messages` (`issue_communications_command`), 201 `{id, case_revision}`. Actions: `prepare {case_revision, state_id, kind: request|reminder, operation_key}`; `edit {…prepare fields, draft_id, body, evidence_id, reason}`; `review {case_revision, draft_id, role, verdict: approve|return|reject, evidence_id, reason}`; `release {case_revision, review_id, role, channel: email|whatsapp|ticket, not_before|null}`; `begin_manual {case_revision, dispatch_id}`; `attest {case_revision, dispatch_id, role, source_evidence_id, reference, delivered, delivered_at|null, checked}`; `lookup {case_revision, dispatch_id, role}`; `cancel {case_revision, dispatch_id, role, reason}`.
  - Reads that feed the forms: the F-111 reads, plus `GET /api/v1/projects/{case_id}/issues` (`issues_register`), which gives `owners[{id,name}]`, `proofs[{id,version,kind}]` and `case_revision` (this feature adds that one read).
- Backend answer D-4: respond with `team_reply` only for the exact work task; `team-replies` for an independently captured reply; never both for one reply. D-185 and PSL decisions apply (build what the boards draw where the API supplies data).
- Today's v7 forms (F-30): `frontend/src/features/workspace/StepForm.tsx`, `AssignForm.tsx`, `useWorkspaceStep.ts`, `useWorkspaceAssign.ts`. They are not reused (they send to the v7 `/work/{id}/steps`).

## Contract

### Which control is drawn (flags from the F-111 follow-up read; the page does no role check)
| Control | Drawn when | Sends |
|---|---|---|
| Post update (owner update) | `team.can_record` is true and `response_task` is not null, and `issue.status` is Open or In Progress | `respond` on `ref.url` |
| Record reply (independent) | `team.can_record` is true, `response_task` is null and `team.assignment_id` is not null | `team-replies` |
| Set an owner | `can_request_update` is true or `team.assignment_id` is null (see Assumptions 3) and the issue is not Closed | `assignment` |
| Message owner | `can_request_update` is true and the messages read answered | `messages` steps below |
Hidden, not disabled, when the condition is false. While a write runs every control on the panel is disabled. A command with no usable token (`null`) is drawn disabled with "We don't have this issue's current version yet. Reload and try again." and never sent.

### 1. Owner update (`respond`)
- Form fields: Update type (Acknowledge, Started, Progress update, mapping to `operation` acknowledge, start, progress; none preselected), Update (`note`, required, 1 to 2000 characters), Next action (`next_action`, required, prefilled with the read's `next_action` as editable text), Proof (the picker below, required).
- Body: `{action:'respond', operation, note, next_action, evidence_id, task_id: response_task.id, task_revision: response_task.revision, expected_revision, case_revision, team_reply}`. `expected_revision` and `case_revision` come from the follow-up read as `tokens`; `task_revision` as the descriptor's `task_revision` token. None of them goes inside `inputs`.
- `team_reply`: `null` when `team.mode === 'internal'`. When `team.mode === 'team'` the form adds Who replied (`party`), How (`channel`, six words, none preselected), When (`responded_at`, optional, blank sends `null`) and Source reference (`source_ref`, required), and sends `team_reply: {assignment_id: team.assignment_id, operation_key: <uuid>, party, channel, responded_at, source_ref}`. The uuid is made once per attempt through the descriptor's idempotency slot (`operation_key`), never reused after a failure with an unknown result.
- 200: re-read the issue reads and the work item; the page shows "Update recorded." plus the new `issue.status` and `next_action` from the re-read. Not from the 200 body.

### 2. Owner reply (`team-replies`)
- Same fields as the team-mode form above plus Update type (acknowledge, start, progress only; `resolve` is not offered, see Out of scope). Body `{case_revision, state_id: issue.state_id, assignment_id: team.assignment_id, operation_key (uuid, descriptor), party, channel, responded_at, source_ref, operation, evidence_id, note, next_action, fix_id: null, root_cause_id: null, resolution_role: null}`.
- Never sent when `response_task` is not null (the update form with `team_reply` is the only path then, D-4). One reply, one request: the form is locked after a press until the re-read.
- 201: same re-read and confirmation as above.

### 3. Set an owner (`assignment`)
- Data: one `GET /projects/{case_id}/issues` when the form is first opened (not on page load). `owners[]` fills the "Follow-up coordinator" choice (name shown, `id` sent as `recorder_id`; none preselected); `proofs[]` fills the proof picker; `case_revision` of that read is the token.
- Fields: Follow-up coordinator, Reason (required, 1 to 2000), Proof (required picker). Mode is "A person in the factory" (`mode:'internal'`). External team is not offered because no read lists the configured team keys (Question B1). Internal sends `team_key: ''` and `recorder_role: ''` on the best reading of `issue_teams.assign`; the contract's role enum has no empty value (Question B2), so the live result is recorded in build.md and the server's answer is shown as given.
- Body: `{case_revision, state_id: issue.state_id, mode:'internal', team_key:'', recorder_id, recorder_role:'', evidence_id, reason, work_id, source_id: followup.source_id}` (`work_id` is the page's work id, so the server attaches the follow-up task).
- 201: re-read all issue reads and the work item; the Owner fact and the no-owner banner change only from the re-read.

### 4. Message the owner (`messages`)
Steps are offered from the structure of `messages.items[]` only; the free-text `status` is never parsed. Newest item is the current one.
| Step button | Drawn when | Body notes |
|---|---|---|
| "Prepare a message" (Ask / Remind) | no item, or the newest item has a `receipt` and no open draft | `prepare`, `kind` request or reminder (the person chooses; none preselected), `state_id` from the messages read, fresh `operation_key` |
| "Edit draft" | newest item has `review_id === null` or `verdict` is `return` | `edit`, `draft_id`, `body` (prefilled with the draft text, 1 to 4000), `evidence_id`, `reason`, `operation_key`, `kind` of the item |
| "Review" Approve / Return / Reject | newest item has `review_id === null` | `review`, `draft_id`, `role`, `verdict`, `evidence_id`, `reason` |
| "Send to the owner" | newest item has `verdict === 'approve'`, `review_id` set, `dispatch_id === null` | `release`, `review_id`, `role`, `channel` (email, whatsapp, ticket; none preselected), `not_before` blank = null |
| "Check what happened" | `dispatch_id` set and `receipt === null` | `lookup`, `dispatch_id`, `role` |
| "Record it by hand" | same | `begin_manual` then `attest` (`source_evidence_id` from the messages `evidence[]` picker, `reference`, `delivered` yes/no, `delivered_at`, `checked`) |
| "Cancel the send" | same | `cancel`, `dispatch_id`, `role`, `reason` |
- `role` ("Acting as") is a choice from the schema's role list, none preselected, because no read serves the person's role for these steps (`/me` positions use a different list). The server decides; a 403 is shown as given (Question B3).
- Evidence for `edit`, `review` and `attest` comes from `messages.evidence[]` only. Empty list: the button is off and says "No proof is available to attach."
- The reviewer's own draft is not blocked in the client (independence is the server's rule); the server's 403/422 message is shown.
- Tokens: every message body carries `case_revision` from the messages read (descriptor token). Release is a single press with one request; the page never releases because of agent or model text, a timer or a poll.
- Uncertain send (`network`/`server` error, timeout, dropped connection) on `release`, `begin_manual`, `attest`, `lookup` or `cancel`: lock the message controls, re-read the messages, and say "We couldn't confirm that this happened. Check what happened before trying again." Unlock only when the re-read shows a changed `dispatch_id`, `receipt` or `case_revision`, or after a reload. While locked, only "Check what happened" (a `lookup`, which sends nothing to the client) is offered, never a second "Send to the owner". After an uncertain `prepare` or `edit`, re-read first; if a draft now exists the form shows it, and no second prepare is made.
- After any 201: re-read messages, detail and follow-up together and show the confirmation from the re-read ("Draft saved", "Review recorded: approved", "Sent. Waiting for the receipt", "Receipt recorded"), never "Delivered" unless `receipt.delivered` is true. A null receipt shows "No receipt yet".

### Proof picker (shared by all forms)
Select from the served list (`proofs[]` or `evidence[]`; shown as kind and version, id kept internal), nothing preselected, button off while empty or unchosen. No upload field is drawn: none of these actions has its own upload or proof route. F-85's `fileToEvidence` is not used.

### Errors (via `useWorkCommand`, words from `ApiError`)
401/404 replace the page with the existing states; 403 non-csrf: "You can't do this." plus the server's message, then re-read; 403 `csrf_failed`: refresh session once, "Press the button again", nothing sent by itself; 409: re-read, "This changed while you were working. Showing the latest version.", the press is not repeated (covers `stale_version`, `idempotency_conflict`); 422: server `message` and first `fields[].message` as given; 429/503: "Try again shortly."; network/5xx: uncertain, as above. A failed write never clears what the person typed (except after a 409 re-read, where the form is kept and the proof choice is cleared if the id left the list).

### Form states
Loading (owner list or proofs being read: field shows "Loading"), empty (no owners: Set owner button off with "No one can be chosen."; no proofs: submit off), error (Callout under the row, alert role), success (Callout status role, form cleared), working (all controls disabled, "Working...").

### Fixtures (mock `frontend/mock/**`; Next 4990, mock 4991; shapes are the contract)
Reuse part 1's 5101 to 5107 and add: `5111` internal owner with `response_task{id,revision}` (update form); `5112` team owner (`team.mode:'team'`, `assignment_id:7`, `response_task:null`, `can_record:true`): reply form; `5113` no owner (Set owner; register read with two owners and three proofs); `5114` messages: no items; `5115` draft unreviewed; `5116` draft approved, not sent; `5117` dispatched, `receipt:null`; `5118` delivered; `5119` forbidden: all flags false (no controls). Write mocks bump `case_revision`/`expected_revision` and return the changed readback, and support the failure switch F-87 uses for 409, 422, 403, csrf, 503 and a dropped connection.
Examples: update body `{"action":"respond","operation":"progress","note":"Fix verified on 2 of 3 models","next_action":"Test the third model","evidence_id":41,"task_id":88,"task_revision":3,"expected_revision":12,"case_revision":57,"team_reply":null}`; release body `{"action":"release","case_revision":57,"review_id":19,"role":"PMO Lead","channel":"email","not_before":null}`.

## Lanes
- Frontend lane (all of the work): `frontend/src/features/issue-followup/IssueFollowupActions.tsx`, `issueFollowupCommands.ts` (descriptors via `makeCommand`), `messageSteps.ts` (pure derivation of offered steps), their tests; edits to part 1's `issueFollowupAdapter.ts` (`commands()` and `Actions` registration, one added register read); mock files `frontend/mock/issues.mjs` (extended) and write routes; `frontend/e2e/issue-followup-actions.spec.ts`.
- Backend lane: none. No backend, migration or contract edit.
- Integration owner: lane D coordinator. Lane C owns `frontend/src/features/workspace/**` and `work-item/**` (not edited; a needed change is a named dependency). `frontend/mock/server.mjs` is shared (route registration lines only). Any change to `frontend/mock/finance*` is named in build.md.
- Paths in `delivery/config.json` `protected_paths` stay unchanged.

## Acceptance criteria
1. `/work/5111` shows the update form only; posting Progress with a note, next action and a chosen proof sends exactly one POST to `/api/v1/work/5111/issue-followup` with the body shape above, `team_reply:null`, `task_id`/`task_revision` from `response_task`, and the page then shows the re-read status — verify: e2e records the request and compares it to the fixture JSON.
2. `/work/5112` (team owner, no task) shows the reply form and sends one POST to `/projects/{case}/issues/{issue}/team-replies` with a uuid `operation_key`, `assignment_id` 7, channel and source reference; it sends nothing to `issue-followup` — verify: e2e. `/work/5111` never calls `team-replies` — verify: e2e request log.
3. The update form with `team.mode:'team'` sends `team_reply` with `assignment_id`, a uuid `operation_key`, party, channel, `responded_at` null when blank — verify: unit test on the descriptor body.
4. Every write body carries `expected_revision`/`case_revision` (or `case_revision` alone for project routes) from the correct read, never 0, never inside `inputs`; with a `null` token the control is disabled with the reload text and no request is made — verify: unit tests on each descriptor and `grep` that no `inputs` object holds a revision or key.
5. Flags: with 5119 no control is drawn; with `can_record` false the update and reply forms are absent; with `can_request_update` false "Message owner" is absent — verify: unit test on the visibility table and e2e on 5119.
6. Proof: no proof is preselected; submit is off with an empty list; the evidence id sent is one from the served list; no file input is on the page — verify: unit test and e2e; `grep -rn "fileToEvidence" frontend/src/features/issue-followup` returns nothing.
7. `/work/5113` Set an owner reads `GET /projects/{case}/issues` only when the form opens, lists the owner names from `owners[]` with none preselected, and sends one `assignment` POST with `mode:'internal'`, `recorder_id`, `state_id`, `evidence_id`, `reason`, `work_id`; the Owner fact changes only after the re-read — verify: e2e; no external-team option appears.
8. Message steps follow the structure table: 5114 offers only Prepare; 5115 Edit and Review; 5116 only Send to the owner; 5117 Check what happened, Record it by hand and Cancel; 5118 offers Prepare only and shows the receipt — verify: unit test on `messageSteps.ts` for all five fixtures; the `status` text is never read (grep).
9. Release sends one request on one press (double click sends one), needs a chosen channel and "Acting as", and no step releases anything automatically on load, poll, timer or tool text — verify: e2e counting POSTs; `grep liveApi.POST` shows sends only through `useWorkCommand`.
10. Uncertain send: a dropped connection on release locks the message controls, re-reads, shows the uncertainty message, offers only Check what happened, and does not send a second release until the re-read changes `dispatch_id`/`receipt`/`case_revision` or the page is reloaded — verify: e2e with the failure switch and a request count.
11. A message with `receipt:null` shows "No receipt yet" and never "Delivered"; "Delivered" shows only when `receipt.delivered` is true — verify: unit test and e2e on 5117 and 5118.
12. Wrong person / wrong tenant / invalid input: 403 shows "You can't do this." with the server message and re-reads; 404 shows "This record is unavailable."; 409 re-reads and shows the stale text without repeating the press; 422 shows the server message and `fields[]`; `csrf_failed` refreshes the session once and sends nothing by itself; 503 shows "Try again shortly." — verify: mock scenarios and unit tests on each.
13. Empty note, missing update type, missing proof, missing channel or source reference (team form) keep submit off with the field named; limits (2000/4000 characters) are enforced before sending — verify: unit tests.
14. A provider/delivery failure is not success: after `release` with a 201 the page says "Sent. Waiting for the receipt" and only a served `receipt` changes it — verify: e2e on 5116 then 5117 fixture sequence.
15. The case id and issue id sent come only from the loaded work item and reads; no input accepts either — verify: unit test on request URLs with a changed `case_id`.
16. `IssueFollowupActions` is registered through the adapter's `Actions` slot and the issue page works without it for a line with no `Actions`; no file under `frontend/src/features/workspace` or `work-item` is changed — verify: `git diff --stat` and a unit test.
17. Against live Django (8030, an account that can see an issue) the update and the message prepare are exercised once each against a test project; the status of each answer and the page after re-read are recorded in build.md. The live result of Set an owner (Question B2) is recorded as found — verify: curl the three reads before and after and compare with the page.
18. Viewport check at 1440 and 390 on the four SCR-30 states plus the forms: boards' parts remain; added forms use CMP-04 fields, CMP-09 buttons and CMP-18 callouts and leave no empty heading — verify: screenshots reviewed against SCR-30 artboards.
19. New tests cover descriptors, step derivation, the visibility table, the uncertain-send lock and error mapping; `npm run lint`, `typecheck` and `npm test` pass — verify: `delivery/checks.sh`.

## Out of scope
- The F-111 reads, Tola's note and story (DC-3), SCR-50 escalation raise (the overdue board's "Raise an escalation" stays hidden) and SCR-31 change request.
- `resolve` on a reply, and `fix_id`, `root_cause_id`, `resolution_role` (resolve/close stay in the issue register; no read serves them).
- External-team assignment (no served team keys), `action: request_update`, and `refresh`/`restart` of the follow-up (the read has no flag naming when they are allowed; hidden until the backend names one, Question B4).
- File upload and any evidence creation; message editing of channel lists; scheduling beyond `not_before` null.
- Any change to `frontend/src/features/workspace`, backend, migrations or contract; a needed frame change is a named dependency on lane C.

## Assumptions
1. Message steps are derived from `review_id`, `verdict`, `dispatch_id` and `receipt` because the read names no allowed steps and `status` is free text.
2. "Reconcile" maps to `lookup` (check), `begin_manual` plus `attest` (record by hand) and `cancel` (recover); the contract names no step "reconcile" or "recover".
3. Set an owner is drawn when `can_request_update` is true or the issue has no owner; no dedicated flag exists. The server is the check.
4. `case_revision` for each write is the one on the read named under that form; all reads are re-fetched after any write.
5. `/me` positions are not used for "Acting as" because their six role names do not match the message role list.
6. Update type words: Acknowledge, Started, Progress update, from the default board.
7. Mock ids 5111 to 5119 are free.

## Conflicts with the boards
1. Default board draws one Owner follow-up form (Update type, Update, Post update). The spec adds Next action and Proof fields (required by the API) and, for team owners, party, channel, date and source reference. Recommendation: accept; each is a required field of the contract.
2. Overdue board draws "Record a reply" and "Raise an escalation" as buttons. Spec: Record a reply opens the reply form (add party, channel, source reference, proof); "Raise an escalation" stays hidden (SCR-50). Recommendation: accept; hide until SCR-50.
3. No-owner board draws "Set an owner in the issue register" as a button. Spec: an inline form (coordinator, reason, proof) on the page. Recommendation: accept; D-185 says build what the API supplies. Alternative: link to the register.
4. No board draws Message owner (prepare, edit, review, send, check, hand-record, cancel), the "Acting as" choice or the proof picker. Recommendation: a new panel "Message the owner" under Chasing, using CMP-04/09/18; the design engineer confirms or asks lane C for artboards. If rejected, hold message steps and ship the other three forms.
5. Verified board has no forms. Spec follows: no write control drawn when `issue.status` is Resolved or Closed except none; the message panel still shows the history read-only. Recommendation: accept.

## Questions
1. Message panel without a board (design engineer). A: add "Message the owner" under Chasing as above (recommended); B: draw four more artboards first and hold the messages part; C: link to a separate screen.
2. Set an owner on the no-owner board. A: inline form on the page (recommended); B: keep the board's link to the issue register and build no form here.
3. Verified/closed issues. A: hide every write including messages (recommended); B: allow a late reminder message on Resolved issues.

Backend questions (coordinator to route; builder proceeds on the stated reading):
- B1. Which call lists the configured external team keys for `assignment` `mode:'team'`? Recommendation: add `teams[{key,label}]` to `GET .../issues`. Until then external-team assignment is not offered.
- B2. For `mode:'internal'` the code expects an empty `team_key` and `recorder_role`, but the schema's role enum has no empty value. Which body is right? Recommendation: allow `recorder_role: null` or '' when internal.
- B3. Which role does each message step expect, and can the read serve the person's allowed roles per step? Recommendation: add `roles[]` per step to the messages read.
- B4. Which flag allows `refresh`, `restart` and `request_update` on the follow-up read? Recommendation: add `can_refresh`, `can_restart`.
