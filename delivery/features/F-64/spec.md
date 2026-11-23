# SCR-03 Decision desk on the live API: read the invoice or accounting review, claim it, record approve, return or reject

> Tasks: FE-CONNECT-1. Architecture: live API 1.22.0 (`contracts/psl-factory.openapi.json`; connection map `delivery/connect/screens-a-frame-core.md` "SCR-03 · Decision"). Design: approved canvas as built under F-04 and F-16; screens: SCR-03 (default, done, not-yours, stale on the main canvas; own on the Finance canvas). Out: payment-exception, ceo-costing, cto-emergency.

## Summary
- The built Decision page (`/work/[id]/decide?task=`) reads and writes the live task API instead of the v7 work item.
- The person must pick one piece of review evidence and write a note before approve, return or reject can be sent. Nothing is pre-selected.
- Who may act comes only from the server (`can_decide`, `can_claim`, `claimed_by_you`). The page invents no approvers, no reason sentence and no approval chain.
- Board parts the live API cannot fill (chain strip, basis, change list, preparer name, pager) are hidden; each is listed under "Questions for the design engineer".
- A revision conflict (409) reloads and shows the stale board; an uncertain write reloads and never resends.

## Context
All paths are in `frontend/` of the lane-a worktree (`/Users/Hunchoo/psl-factory-worktrees/lane-a/frontend`).
- `src/features/decide/useDecision.ts`: loads `GET /api/v1/work/{work_id}` through the v7 client `api`, finds the task with `findDecisionTask` (`format.ts`), auto-claims once per task revision, posts `/tasks/{id}/decision` with `{expected_revision, verdict, note?}`, reconciles by reloading after an uncertain write.
- `DecideView.tsx`, `DecidePanel.tsx`, `DecisionContent.tsx`, `DecideStates.tsx` (cannot-act, stale, done views), `presentation.ts` (queue text, "decision 2 of 5"), `decide.css`.
- `src/features/workspace/InlineDecide.tsx`: the same decision made in place on the work page.
- `src/api/client.ts` already exports `liveApi` (typed by `src/api/live-schema.d.ts`) next to the v7 `api`. Use `liveApi` for every call in this feature.
- v7 read shape the UI expects today: `WorkItem.tasks[].decision{version, amount, basis, recipient, changes, prepared_by, chain}`, `you_can_act`, `cannot_act_reason`. None of that exists live (see map).
- Tests today: `tests/decide.test.tsx`, `tests/decide-board.test.tsx`, `tests/mock-decide.test.ts` (v7 mock). The mock server must serve the live shapes below for the decide routes.

## Contract
All calls use `liveApi`, same-origin session cookie and CSRF as in `src/api/client.ts`. Work and task ids are integers (the route param stays a string and is converted for the call; a non-numeric id shows the existing no-access/not-open state, no request sent).

### Reads
1. `GET /api/v1/work/{work_id}`: used for the title, state, reference and `tasks[]{id, kind, role, status, revision, claimed_by_you, can_claim, can_decide, verdicts[], url}`. The page opens the task named by `?task=`. When no `?task=`, or it is not in `tasks[]`, show the existing "not open" state. The destination for a task from lists comes from `tasks[].url`; the page never builds a route by kind (A-22).
2. `GET /api/v1/tasks/{task_id}` returns `{task{...same fields}, work_id, label, invoice_packet | null, review_evidence[{id, version, source, sha256}], recipient_change{earlier, current}}`. Render:
   - version `invoice_packet.version`, amount `invoice_packet.amount` (decimal string, formatted with `formatAmount`, never a float; `null` packet or empty amount shows "Unknown", never 0), currency, recipient (`recipient_change.current`; when `earlier` differs and is non-null show the earlier recipient as a visible "recipient changed" line), `label` as the task title, `invoice_packet.sources[]` if it renders as a plain list.
   - `sha256` is shown short and secondary (technical details), not in the lead.
3. `GET /api/v1/work/{work_id}/history?kind=decision` returns `{items[{at, station, status, task_id, actor, reason, evidence_id}], as_of}`. Used for the done board after a decision (the item for this `task_id`: actor, `at`, reason). If no matching item, the done board omits the "decided by" line rather than guessing.
4. `GET /api/v1/work?queue=decisions` feeds any "next decision" link and the queue count on the page (live list only). No count or position is shown when the list read fails or the current task is not in it.

### Who can act (derived only from the task read)
- `can_decide` and `claimed_by_you` true: the deciding board (default).
- `can_claim` true and not yet claimed: claim once (below), then the deciding board.
- `can_decide` false and `can_claim` false: the read-only (not-yours) board. When the sources do not say why, show the generic sentence the page already uses for "no reason", never a specific reason ("prepared by you", "not your turn"). The own board (`prepared_by_you`) cannot be derived and is not reachable (Question 2).
- `verdicts[]` decides which of approve, return, reject appear; absent verdicts are not drawn.
- A 403 on any write turns the page read-only after a reload; a 401 shows the existing signed-out state; a 404 shows no-access.

### Writes
1. Claim: `POST /api/v1/tasks/{task_id}/claim` body `{expected_revision}` (the task's revision from the read) returns 200 `{task_id, revision, claimed_by}`. Sent once per `taskId:revision` (as today). A failed claim shows the existing claim-failed retry; 409 triggers the stale reload.
2. Decision: `POST /api/v1/tasks/{task_id}/decision` body `{expected_revision, verdict: "approve"|"return"|"reject", evidence_id: int, note: string}` returns 200 `{task_id, review_id, verdict, work_state}`.
   - `expected_revision` is the revision returned by the claim.
   - `evidence_id` is the id the person picked from `review_evidence[]` (radio list, labelled by source and version). No default selection; the three buttons stay disabled until one is picked (A-18). If `review_evidence` is empty the buttons stay disabled and a plain sentence says there is no evidence to cite yet.
   - `note` key is always sent. Return and reject require a non-empty note on the page (existing rule); approve may send `""`. Max length `NOTE_MAX` (2000).
   - No `revoke` anywhere on the page (A-20); remove the revoke path from `InlineDecide.tsx` and `useDecision.ts`.
   - No retry of the write. 409: reload the task and show the stale board with the replaced version (kept from before the write) against the current one. Network or 5xx: reload once, never resend; if the reload fails too, the controls stay off with the existing "couldn't confirm" notice. 422 shows the server message and `fields[]` messages next to the note or picker. 400 is treated as 422. 403, 401, 404 as above.
   - Success shows the done board from the response: the verdict word, the label, the note the person wrote, and the new work state mapped from `work_state` (including `effect_uncertain` as the existing uncertain notice). Then it reloads the work and history; a failed reload shows the existing "refresh failed" note and still shows what was recorded.
3. Comment (not-yours board): `POST /api/v1/tasks/{task_id}/comments` body `{revision, body}` returns 200 `{comment_id}`. Offered only on the read-only board when the board draws a comment box (Question 4). Body required, max 2000; 409 reloads; 403 or 422 shows the server message. Idempotency: one tap sends once; the button is busy until the answer, and an uncertain failure reloads and tells the person to check before sending again.

### Screen states
- Loading: existing `LoadingState`.
- Error (not 401/403/404): existing `WorkErrorCard` with Try again, "nothing was changed".
- Empty: task not in `tasks[]`: existing `NotOpenState`.
- Default (deciding), done, not-yours, stale: as built, with the parts listed under Questions hidden.
- Success: done board.

### Fixtures (mock server and tests)
- Deciding: `GET /tasks/41` -> `{task{id:41, kind:"invoice_review", role:"finance_reviewer", status:"open", revision:3, claimed_by_you:false, can_claim:true, can_decide:false, verdicts:["approve","return","reject"], url:"/work/17/decide?task=41"}, work_id:17, label:"Invoice 3 for the Lekki handover", invoice_packet{invoice_id:9, version:2, sha256:"…", amount:"4250000.00", currency:"NGN", recipient:"Lekki Estates Ltd", preparation_id:5, sources:[]}, review_evidence:[{id:88, version:2, source:"signed milestone certificate", sha256:"…"}, {id:91, version:2, source:"client email", sha256:"…"}], recipient_change{earlier:null, current:"Lekki Estates Ltd"}}`. After claim: `claimed_by_you:true, can_decide:true`.
- Decision 200: `{task_id:41, review_id:12, verdict:"approve", work_state:"waiting"}`.
- Stale: decision answered 409 `{code:"conflict", message:"…"}`; the next read has `revision:4` and `invoice_packet.version:3, amount:"4300000.00"`.
- Not yours: `can_claim:false, can_decide:false`.
- Unknown amount: `invoice_packet:null`.

## Lanes
- Frontend lane (owner of everything): `src/features/decide/*`, `src/features/workspace/InlineDecide.tsx`, the decide handlers of the mock server and `tests/decide*.test.tsx`, `tests/mock-decide.test.ts`.
- Backend lane: none. The backend is not changed; the page builds on the best reading of A-18 to A-22 and flags each.
- Integration owner: `src/api/types.ts` and `live-schema.d.ts` are shared; add only the aliases this page needs (task read, history item) to `types.ts` after `git merge origin/main`. Lane C owns `workspace/*` generally; `InlineDecide.tsx` is changed here as a separate small commit named in build.md.

## Acceptance criteria
1. Open `/work/17/decide?task=41` against the mock or live server as a person who can claim. The page makes `GET /tasks/41`, one `POST /tasks/41/claim` with `{expected_revision:3}`, and shows the label, version, formatted amount and recipient — verify: network log in `tests/decide.test.tsx` (one claim call, even under StrictMode) and the page text.
2. No evidence is pre-selected and approve, return and reject are disabled until one item of `review_evidence` is chosen — verify: test asserts disabled buttons on open, enabled after choosing, and the decision body carries that item's `id`.
3. Approve sends exactly `{expected_revision, verdict:"approve", evidence_id, note}` with `note` present even when empty; return and reject with an empty note show a validation message and send nothing — verify: request-body assertions in the test.
4. A decision 200 shows the done board with the verdict, note and label, and does not show "decided by" unless the history read has a matching item (then actor and time from it) — verify: test with and without a history item.
5. A 409 on claim or decision reloads and shows the stale board with the replaced version beside the current one, controls on the current only after "Review version n"; the write is not resent — verify: test counts decision calls (1).
6. A network or 5xx failure on the decision reloads once, never resends, and shows the uncertain notice; when the reload also fails, the buttons stay disabled and Try again only issues GETs — verify: test.
7. Wrong user: `can_decide:false, can_claim:false` shows the read-only board with no decision controls and no specific reason sentence; no claim is sent — verify: test; wrong tenant or unknown task: GET 404 shows the no-access state; 401 shows signed-out; 403 on a write turns the page read-only — verify: tests per status.
8. Invalid input: a 422 on the decision shows the server message (and `fields[]` text) without leaving the board and without clearing the picked evidence or note — verify: test.
9. Unknown amount (`invoice_packet:null` or empty) shows "Unknown", never 0 or "₦0.00" — verify: test on `formatAmount` and the page.
10. A task whose `verdicts[]` omits a verdict does not draw that button; no revoke control exists on SCR-03 or `InlineDecide` — verify: `grep -rn "revoke" src/features/decide src/features/workspace/InlineDecide.tsx` returns nothing, plus a test.
11. No pager "decision n of m" is drawn unless `GET /work?queue=decisions` succeeds and contains this task; with the list failing the rest of the page still works — verify: test both cases.
12. Comment on the not-yours board (if kept, Question 4) sends `{revision, body}`, requires a body, shows the server message on 403/409/422 and does not send twice — verify: test.
13. Every call on this feature goes through `liveApi` and the typed live schema; `tests/api-live-schema-drift.test.ts` still passes — verify: `grep -rn "api\.\(GET\|POST\)" src/features/decide` returns nothing.
14. The page matches the approved boards at 1440 and 390 for default, done, not-yours and stale, apart from the parts listed under Questions — verify: UI review of the changed area; the own board is checked only for the unreachable-state note below.

## Out of scope
- Payment-exception, CEO costing and CTO emergency variants, `/work/{id}/reviews`, `/role-work/*`, payment-controls, costing proposals, emergency routes.
- Any backend, contract or migration change; asking the server for the approval chain, reasons, basis or change list (those are questions, A-19 and A-21).
- Revoke on tasks (A-20), pre-selecting evidence (A-18), inferring the "own" case from names or ids.
- Uploading new proof from this page (evidence must already be recorded; B-files path is A-18/question 1 in `backend-questions.md`).
- Changing the work page layout, task lists, or the shell.

## Assumptions
- Pre-select nothing, because the contract does not rank evidence; the person always chooses.
- Approve may send an empty note (the key is required, not the content); return and reject keep today's required-note rule because a returned or rejected decision needs its reason.
- Recipient change is shown when `earlier` is non-null and differs, because the packet exposes it and a hidden recipient change is a risk; no board draws it, flagged in Question 5.
- Stale comparison uses the packet kept in memory from before the 409 against the reloaded one (version, amount, recipient only), because the live read has no change list.
- The decided-by line comes from `GET /work/{id}/history?kind=decision` (`actor`, `at`) because the decision reply has no `decided_by`; absent means hidden.
- A task id in the route that is not an integer is treated as not open, because the live API takes integers.
- Queue count and "next" link come from `GET /work?queue=decisions` only, no cached counts.

## Questions for the design engineer
1. Evidence picker (not on any board). The live decision needs one evidence item. Options: (a) a short radio list under the verdict buttons, labelled by source and version, nothing pre-selected, buttons off until one is picked (recommended: smallest, honest); (b) a drop-down in the note area; (c) pre-select the newest item (rejected: A-18 unanswered, would cite evidence the person did not choose).
2. Own board (prepared by you) and the "why you cannot decide" sentence. The live read has no reason and no preparer. Options: (a) show the not-yours board with the generic sentence for every case and leave the own board unreachable until the backend answers A-19 (recommended); (b) show a softer "You can't decide this one" without any reason; (c) hold the read-only boards and show only the facts.
3. Approval chain strip ("your step 2 of 3"), basis line, "what changed since last version" list, prepared-by name. No live source (A-19, A-21). Options: (a) hide each part and show nothing in its place (recommended); (b) show the row with "Not available yet" in the value; (c) keep the part but fill it only from what exists (on the stale board, version, amount and recipient comparison only).
4. Comment box on the not-yours board. The live comment write exists but `can_comment` is not exposed, so we cannot tell who may comment. Options: (a) show the box only on the read-only board and let the server's 403 turn it off (recommended); (b) hide the box until the backend says who may comment; (c) show comments as read-only text only.
5. Recipient change warning. Live data has `recipient_change{earlier,current}`, no board draws it. Options: (a) a single line in the amount/recipient rows when it changed (recommended); (b) a warning callout above the rows; (c) leave it out.
6. Decided-by on the done board. The reply has no decider or time. Options: (a) take actor and time from the decision history and hide the line if missing (recommended); (b) drop "decided by" always and keep only verdict and note; (c) show the signed-in person's name and the page's own clock time (rejected: not a record).
7. Pager "decision 2 of 5" and the phone bar's queue note. Options: (a) drop it unless the live decision list loads and contains this task, then fill from that list (recommended); (b) drop it always; (c) show the list count only ("5 waiting").
8. Parts of the done board with no live source: "Next step. Chidi will issue it and email it to…", "Paid is tracked separately…" sentence, the SENT/RECEIPT strip detail, and the "Still waiting on you" list. Options: (a) keep the "Paid is tracked separately" sentence (fixed policy copy), hide the Chidi next-step sentence and fill the "Still waiting on you" list and "Next decision" link from `GET /work?queue=decisions` only, hiding them if the list fails (recommended); (b) hide the whole "what happens next" block; (c) replace the next step with the work state label from `work_state`.
9. Stale board sentence "Version 3 was drafted at 10:46 after the billing contact changed" and the agent note "Chidi redrafted it…". The live read has no draft time, cause or agent note. Options: (a) say "A newer version arrived while you were reading. Version 2 can no longer be approved." and drop the time, cause and agent note; the comparison table (amount, recipient) stays (recommended); (b) add the time of the reload as "seen at hh:mm"; (c) keep the agent block empty.
10. Not-yours board: the "Ada Okafor was alerted at 10:42 by WhatsApp and email" line, the "You hold Finance on this project…" reason, and the BASIS value. No live source. Options: (a) keep the heading "Not your decision", the amount, "Waiting for {task.role}" and the comment box; hide the alert line, reason and basis (recommended); (b) show the line "Not available yet" in each; (c) hide the comment box as well (Question 4).
11. Default board sentence "Only a Finance Lead can decide. You are Finance Lead." Options: (a) draw "Only a {task.role} can decide." from the task and drop "You are …" because the page may not infer the person's role from /me (recommended); (b) drop the sentence; (c) fill "You are …" from /me (rejected: INV-ACCESS says /me does not decide what is offered).
12. Own board (Finance canvas) shows "Prepared by Bisi Ade (you) · with Chidi", "Asked: Ada Okafor · Finance Lead 12 Nov 10:20" and "Waiting · Finance reviewer". Preparer, asked person and time have no live source (A-19, A-21). Options: (a) leave the board built but unreachable, as in Question 2 (recommended); (b) reach it only when a later backend answer provides a `prepared_by_you` flag; (c) show it with the three lines hidden.

## Conflicts with the boards
Checked against SCR-03 desktop, done, not-yours, stale (main canvas) and own (Finance canvas) and their mobile twins. The boards draw no evidence picker, so:
- Default (desktop and mobile): adds one control, the evidence picker (Question 1). Removes: basis row, "Changed since v1" row, approval-chain strip, "1 of 3" in the trail unless the live list holds the task (Questions 3, 7), the Chidi sources note, "You are Finance Lead" (Question 11). The "Preview: a newer version arrives" control is a design toggle, not built. Recommendation: as in each question.
- Done: removes the Chidi next-step sentence, uses history for "decided by" (Questions 6, 8). Recommendation: as asked.
- Stale: removes drafted-time, cause and agent note (Question 9). The comparison rows stay (amount, recipient only); a "changed" mark on any other row is dropped. Recommendation: hide.
- Not-yours: removes the alert line, reason and basis (Question 10); the optional comment box stays only if the server accepts it (Question 4).
- Own: unreachable; three lines have no source (Question 12).
- Revoke: no board draws it; nothing to remove on the boards. The default board never drew a revoke control, so the removal only affects code paths.
