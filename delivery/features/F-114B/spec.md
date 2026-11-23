# The PMO Lead confirms and completes the go-live milestone, and staff correct or withdraw a recorded client reply

> Tasks: FE-DELIVERY-RELEASE (part 2; part 1 is F-114). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0 (builders use 1.25.0 or later). Design: approved 13 Nov canvas under the recorded exceptions in `design/review.json`; screens: SCR-45 (boards SCR-45-desktop-accepted and -mobile-accepted for the milestone; no board draws correct or withdraw).

## Summary
- On F-114's page `/work/{id}/go-live` the PMO Lead sees "Confirm and complete milestone" only when the replies read says `milestone.can_confirm` is true, picks the completion evidence from `milestone.proof_ids`, and sends `POST /work/{id}/go-live-milestone` with `action: confirm_and_complete`. It replaces F-114's read-only "Milestone" row where the read allows it.
- Staff can correct or withdraw the current recorded client reply, only where `corrections[]` supplies an entry for it, through `POST /work/{id}/go-live-replies` (`action: record_reply`, `previous_id` from the entry; outcome `changes_requested`, `declined` or `withdrawn`). Nothing is sent to the client.
- A confirmed milestone shows who confirmed it and when from `milestone.confirmation`; `withdrawn` rows stay read-only history.
- Document review (`POST /work/{id}/reviews`) is not here; it is F-114C.
- Build start waits for F-114 (page, adapters, mock), F-85 (shared frame) and F-87 (`Actions` slot, `useWorkCommand`) to be on main. This delays the start only. High risk: the merge goes to the design engineer's batch.

## Context
- Page, adapters and mock come from F-114 (`/Users/Hunchoo/psl-factory-main/delivery/features/F-114/spec.md`): `frontend/src/features/go-live/**`, `frontend/src/app/work/[id]/go-live/page.tsx`, `goLiveRepliesAdapter.ts`, `frontend/mock/go-live.mjs`. F-114 reads `corrections[]` and `milestone` but does not act on them, and draws "Milestone" as a read-only row.
- Backend (read only): `apps/core/factory_api/go_live_replies.py` (`detail` builds `corrections[]` and `milestone`; `COMMANDS`; `milestone` view takes the three actions), `apps/workflows/factory_go_live_milestone.py` (`confirm_and_complete`, `_complete`). `milestone.can_confirm` is true only when the server's PMO Lead direct-confirmation check passes; `proof_ids` are the eligible completion evidence ids (`direct_confirmation.sources`); `acceptance_id` is the verified acceptance; `name` is null until a mapping or recorded milestone exists.
- Shared frame (lane C, not changed here): `frontend/src/features/workspace/adapter.ts` (`LineAdapter.Actions?`, `LineActionsProps = {readback, ctx, commands, reload}`), `useWorkCommand` (F-87), example `WeeklyReportActions.tsx` (F-89).
- API client `frontend/src/api/client.ts`, errors `src/api/errors.ts`, live types `src/api/live-schema.d.ts`.
- D-17 (`delivery/connect/backend-answers.md`): the PMO Lead reviews the project and go-live evidence, confirms which milestone is complete and records that decision before the milestone is marked complete. In 1.25.0 one call does both.

## Contract
Conventions are F-114's: writes as the signed-in person with `X-CSRFToken` via `liveApi`; revision pair taken from the most recent replies read (`expected_revision`, `case_revision`); a null revision disables the write. Errors: 404 "This record is unavailable."; 400/422 first `fields[].message` or `message`; 409 "This changed while you were working. We reloaded it. Check it and try again." (re-read the replies read, plus the sign-off read if F-114 loaded it); 429 "Try again shortly."; 403 `csrf_failed` refreshes the session once and says "Press the button again" (nothing sent); 403 otherwise shows the API message; 503 and network "We couldn't reach the server. Nothing was recorded."; response lost after send: re-read and say "Check the record before trying again", no automatic retry. No idempotency key exists: the button is disabled while in flight and after a 2xx until the read is refetched. After a 2xx the screen shows what the read says, not what was typed.

### 1. Confirm and complete the milestone
Read: `GET /work/{id}/go-live-replies` `milestone{recorded_id, configuration_id, name|null, acceptance_id|null, proof_ids[], owner_decision_ids[], can_confirm, confirmation{id, actor_id, at, role:"PMO Lead", name, note|null}|null}`.

Write: `POST /work/{id}/go-live-milestone` 201 `{work_id, state, revision, record_id}`:
`{action:"confirm_and_complete", expected_revision, case_revision, name, acceptance_id, evidence_id, note?}`
- `acceptance_id` is `milestone.acceptance_id` from the read, never typed (the server rejects a changed one). If it is null the control is not drawn.
- `evidence_id` is chosen from `milestone.proof_ids[]`, nothing preselected; the button is off when the list is empty (PSL answer 1, D-1). Labelled "Completion evidence #{id}" (the read supplies ids only). No upload route exists for it.
- `name` is the exact milestone name the PMO Lead confirms, 1 to 200 printable characters. If the read's `milestone.name` is not null it is shown and sent unchanged and not editable. If it is null, the PMO Lead types it in a required field with no prefill (Assumption 1, Question 1).
- `note` optional, 1 to 4000; omit the key when blank (the contract has no empty string).
- `draft_mapping` and `record_completion` are not used (Assumption 2).
- Visibility: the control is drawn only when `can_confirm` is true, `recorded_id` is null and `confirmation` is null. `can_confirm` false and nothing recorded: show no control and no invented reason (the read gives none). Never decide from the person's role in the client (DC-5).
- After 2xx: refetch; show "Milestone completed" with `milestone.name`, "Confirmed by the PMO Lead {at}" and the note from `confirmation`, "Recorded #{recorded_id}". The "Milestone" row reads "Recorded". Nothing is said about hypercare or handover starting (not supplied by a read).

### 2. Correct or withdraw a recorded reply
Read: `corrections[{receipt_id, previous_id|null, roles[]}]` and `replies[]`, `channels[]` from the same read. The entry whose `previous_id` equals a reply's `id` is the correction target for that reply; draw the controls on that reply's row only. No entry means no control. `withdrawn` rows never get controls.

Write: `POST /work/{id}/go-live-replies` 201 `{work_id, state, revision, record_id}`:
`{action:"record_reply", expected_revision, case_revision, receipt_id, previous_id, outcome, party, responded_at, channel, evidence_id, note, role, attested:true}`
- `receipt_id` and `previous_id` come from the `corrections[]` entry; `role` is one of its `roles[]`; `channel` one of `channels[]`; `party` 1 to 160; `responded_at` a date-time; `note` 1 to 4000; `attested` is a required tick ("I attest this is what the client told us"); the form does not send without it.
- Correct: `outcome` is `changes_requested` or `declined`, chosen by the person; fields start empty. The form offers a visible "Reply being replaced" quote of the current reply (party, date, note) where those are not null.
- Withdraw: `outcome:"withdrawn"`; the same fields are required by the contract, so the form asks for party, date, channel, proof, role, a note (the reason) and the tick. Copy: "Withdraw this reply".
- `evidence_id` follows F-114 exactly (its Assumption 1 and Question 1): the recorded-evidence source F-114 settles. If F-114 holds the reply write because no evidence id is available, this form is held the same way with "Add a proof first" and listed in build.md. No `evidence_id` is invented or copied from another reply.
- A reply whose details are hidden (null party, channel, date, note) can still be corrected only if `corrections[]` supplies an entry; its row still reads "Details not available to you".
- After 2xx: refetch both F-114 reads; the history shows the new reply and the earlier one as the read says; "Recorded." with `record_id`. If the new latest outcome changes which F-114 panel is drawn (changes, declined), F-114's rules apply.

### Page states
- Loading, per-read error, 404: F-114's. If the replies read fails, neither control is drawn and the section shows its mapped message with Try again.
- Milestone block: not drawn when `acceptance_id` is null and nothing is recorded; confirm form (can_confirm); completed (confirmation or recorded_id not null); read-only row otherwise.
- Success inline: "Recorded." then refreshed sections.
- Empty evidence list: the form shows "No completion evidence is available yet." and the button is off.

### Fixtures (mock, port 4991; extend `frontend/mock/go-live.mjs` minimally, ids 4411 to 4419; F-114's 4401 to 4410 keep their meaning with `can_confirm:false, confirmation:null` and `corrections:[]` added where missing)
- `4411` can confirm: `milestone{acceptance_id:7001, name:null, proof_ids:[8101,8102], can_confirm:true, confirmation:null, recorded_id:null}`.
- `4412` can confirm with name supplied: `name:"Go-live"`, same ids.
- `4413` cannot confirm: `can_confirm:false`, accepted.
- `4414` empty evidence: `can_confirm:true, proof_ids:[]`.
- `4415` conflict: the milestone POST answers 409 once, then 201.
- `4416` completed: `recorded_id:9001`, `confirmation{id:9002, at, role:"PMO Lead", name:"Go-live", note:"Reviewed the sign-off pack."}`.
- `4417` correctable reply: one `changes_requested` reply (id 301), `corrections:[{receipt_id:201, previous_id:301, roles:["PM"]}]`, `channels` incl. `email`.
- `4418` withdrawn reply: `[changes_requested (301), withdrawn (302)]`, `corrections:[]`.
- `4419` write refused: milestone POST answers 403 (not PMO Lead).

## Lanes
- Frontend lane (owner of all): in `frontend/src/features/go-live/**` add `MilestoneConfirmActions.tsx` and `ReplyCorrectionActions.tsx` (each a `ComponentType<LineActionsProps>` using `useWorkCommand`), their labels and mappers, tests beside them, and `frontend/e2e/go-live-completion.spec.ts`. Register them once, through the `Actions` field of F-114's `goLiveRepliesAdapter.ts` (a small edit to an F-114 file, allowed because F-114 is on main before the build), and render them in F-114's page where it draws the milestone row and the reply history. Mock: fixtures in `frontend/mock/go-live.mjs` (F-114's file), named in build.md.
- Backend lane: none. No contract edit.
- Integration owner: lane D coordinator. `src/features/workspace/*`, `work-item/*`, `shell/*` are lane C's and are not changed. `src/api/*` shared: add types or error kinds only if missing. `frontend/mock/finance*` and payments fixtures untouched.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. On `4411` the replies read shows a "Confirm and complete milestone" form with a required name field, an evidence list of `8101` and `8102` with nothing selected, an optional note and a button that is off until a name and one evidence are chosen — verify: open `/work/4411/go-live`; `frontend/e2e/go-live-completion.spec.ts`.
2. Sending posts one `POST /work/4411/go-live-milestone` with `action:"confirm_and_complete"`, both revisions from the read, the typed `name`, `acceptance_id:7001`, the chosen `evidence_id`, and `note` only when filled; no `draft_mapping` or `record_completion` call is made — verify: unit test on the body; network panel.
3. On `4412` the name shows "Go-live", is not editable and is sent unchanged — verify: unit test on the body; e2e.
4. On `4413` (`can_confirm:false`) and for any fixture with `acceptance_id` null no confirm control is drawn and no reason text is invented — verify: e2e DOM.
5. On `4414` (empty list) the words "No completion evidence is available yet." show and the button stays off; no evidence id is sent or preselected — verify: e2e; unit test.
6. A double click on the confirm button sends exactly one POST — verify: unit test with a slow mock counts calls.
7. On `4415` a 409 shows the changed-record message, re-reads, and a second press sends a body with the new revisions — verify: e2e compares revision values.
8. On `4419` a 403 shows the API's message and the page stays unchanged after the refetch; a 403 `csrf_failed` refreshes the session once and sends no second POST — verify: unit test counts calls.
9. On `4416` the page shows "Milestone completed", the milestone name, "Confirmed by the PMO Lead" with the time and note, and no confirm form; the "Milestone" row reads "Recorded" — verify: e2e DOM.
10. The blank note is omitted and a name over 200 characters or empty is refused before any request — verify: unit test.
11. On `4417` the current reply row has "Correct" and "Withdraw" controls; the form offers only `changes_requested` and `declined` for a correction, only the read's `channels[]` and only the entry's `roles[]`, and refuses to send without the attestation tick — verify: unit test; network panel.
12. A correction sends `record_reply` with `receipt_id` and `previous_id` (301) from the `corrections[]` entry, the chosen outcome, `attested:true` and both revisions; a withdrawal sends the same with `outcome:"withdrawn"` and a non-empty `note` — verify: unit tests on both bodies.
13. On `4418` the withdrawn row has no control and no form offers "withdrawn" for a row that is already withdrawn; on any fixture with `corrections:[]` no correct or withdraw control is drawn — verify: e2e DOM.
14. A reply with hidden details still shows "Details not available to you", never blank, 0 or "null", and has controls only when `corrections[]` supplies an entry — verify: unit test.
15. The reply form's `evidence_id` comes only from the source F-114 settles and is never typed or copied from another reply; with no source the form is held with "Add a proof first" and build.md lists it — verify: unit test; build.md.
16. Both writes disable on a `null` revision and after a 2xx until the refetch; after success the shown history and milestone come from the read — verify: unit test.
17. Only the routes in the Contract are called by the new files; nothing is sent to the client — verify: grep `liveApi.POST` and `liveApi.GET` in the two new files and `frontend/src/features/go-live`.
18. A work id not on this line or returning 404 shows exactly "This record is unavailable." — verify: e2e (F-114 fixtures).
19. Against live Django (8030), signed in as the PMO Lead on a go-live item with `can_confirm:true`, the page's milestone block, evidence list and corrections match `GET /api/v1/work/{id}/go-live-replies`; as another user (not the PMO Lead) no confirm control shows — verify: compare the page with the `curl` JSON using the session. Do not complete a real milestone on shared data without the design engineer's say; use a seeded test project.
20. Viewport check at 1440 and 390: the milestone block matches SCR-45-desktop-accepted and -mobile-accepted for the parts kept; hidden parts leave no empty heading or gap — verify: screenshots against `design/screens.md` SCR-45.
21. `npm run lint`, `npm run typecheck`, `npm test` pass and `api-live-schema-drift.test.ts` still passes — verify: `delivery/checks.sh`.
22. build.md names the board parts hidden and any change to `frontend/mock/go-live.mjs` shape — verify: file content.

## Out of scope
- `POST /work/{id}/reviews` and any "Open the document review" link (F-114C).
- Everything F-114 owns: sign-off, record_reply for a first reply, successor, decline panel.
- `draft_mapping`, `record_completion`, `owner_decision_ids` (a legacy two-step path; not offered).
- `POST /setup/{case}/policy-configurations/{id}/review`.
- Sending anything to the client; "Hypercare RUNNING" or "Archive STARTED" rows; agent steps and Tola (D-182); amounts and attempt counts.
- Inventing the milestone choice, the evidence, an approver or a reason `can_confirm` is false.
- Any change to `frontend/src/features/workspace`, `work-item` or `shell`; backend, migrations, contract edits.

## Assumptions
1. When `milestone.name` is null the PMO Lead types the exact milestone name. Reason: the contract requires `name` and the D-17 answer says the PMO Lead confirms which milestone is complete; the read gives no list of choices.
2. Only `confirm_and_complete` is used. Reason: D-17 and readiness; it replaces the two-step path and needs no `owner_decision_id`.
3. Controls appear only when `can_confirm` and `corrections[]` say so, never from the viewer's role. Reason: DC-5.
4. Withdraw uses `record_reply` with `outcome:"withdrawn"` and `previous_id` from `corrections[]`. Reason: the contract's `outcome` enum includes it and there is no separate withdraw route.
5. Because `record_reply` requires all fields even for a withdrawal, the withdraw form asks for them. Reason: required in the contract.
6. Evidence labels read "Completion evidence #id". Reason: `proof_ids` carries ids only.
7. Fixture ids 4411 to 4419 are free to renumber. Reason: no live fixtures.
8. The new forms are components registered on F-114's replies adapter and rendered by F-114's page. Reason: F-114 owns a separate route, and the `Actions` slot shape (F-87) is the lane D write form.
9. No wording is drawn on any board for correct, withdraw, attest or "No completion evidence"; the plain words above are the builder's.

## Questions
1. **Who supplies the milestone name when `milestone.name` is null?** (a) The PMO Lead types it, no prefill (recommended; matches D-17 and the required `name`). (b) Hold the confirm control until the read supplies a name. (c) Prefill from the SOW milestone list if a read exists (none does in 1.25.0). Context: readiness said to show the name from the read only; `confirm_and_complete` requires one.
2. **Where does a corrected or withdrawn reply's proof come from?** (a) Same as F-114's question 1: file-to-evidence, held with "Add a proof first" if nothing is available (recommended). (b) Hold correction and withdrawal until the backend names an evidence route. (c) Allow reusing the previous reply's evidence id (not recommended; unconfirmed meaning). Context: the contract needs an integer `evidence_id` even for a withdrawal.
3. **Should withdrawal ask for all reply fields?** (a) Yes, as the contract requires (recommended). (b) Ask the backend to relax the withdrawn shape (a backend question). Context: the person must retype party, date and channel to withdraw.
4. **Hypercare pointer after completion.** (a) Say nothing (recommended, nothing supplied). (b) Link to the hypercare page when the work item read supplies one. Context: the board's "Hypercare ... STARTED" row is not drawn.

## Conflicts with the boards
1. SCR-45-desktop-accepted draws "Mark milestone 3 complete" with a milestone number and a single button. The spec draws "Confirm and complete milestone" with a name, evidence choice and note, and shows the name from the read or typed. Recommendation: accept; the API needs the exact name, the acceptance and separate evidence.
2. The boards draw "Hypercare ... STARTED" and "Archive and handover STARTED" after completion. Not drawn (not supplied). Recommendation: hide, as F-114.
3. No board draws correct, withdraw, the attestation, the evidence picker or "Reply being replaced". Added because the API requires them. Recommendation: keep, and the design engineer draws boards later.
4. "Open the document review" on the accepted board is not drawn (F-114C). Recommendation: leave out until F-114C.
5. The board shows no completed-milestone state with who confirmed. Added from `milestone.confirmation`. Recommendation: keep.
