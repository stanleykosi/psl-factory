# Handover to Support: the PM sees the live handover, publishes the approved version, and records Support's reply with its gaps

> Tasks: FE-CONNECT-1. Architecture: v9 package (`architecture/packages/v9/tasks.csv`; revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the D-173/D-181 exceptions in `design/review.json`; screens: SCR-48 (8 artboards: `SCR-48-desktop`, `-mobile`, `-desktop-record`, `-mobile-record`, `-desktop-gaps`, `-mobile-gaps`, `-desktop-received`, `-mobile-received`). The builder runs `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project /Users/Hunchoo/psl-factory` before starting and records the result in `build.md`.

## Summary
- A handover work item (`delivery-handover/v1`) at `/work/[id]` reads its own live resources: `support-publication`, `support-replies`, `support-receipt` and `history`. It no longer reads the v7 `workspace` object.
- "Publish to Support" shows only when `can_publish` is true and sends the exact `version_id` the read returned. The result is "queued", never "received". Support's receipt is shown as a separate record.
- "Record Support's reply" posts `status` received or gaps with party, channel, time, role, proof, note and a structured `gaps[]` (D-23). It sends both revisions and can replace an earlier record through `previous_id`.
- "Ask Tola to draft v2" posts `corrections`; an uncertain delivery offers "Check what happened" (`actions` reconcile, 202). Start posts `delivery-handover/v1`.
- Build-start wait: F-85 (shared line adapter, lane C, PR #101) is not on main. The coordinator holds the builder until it is. This spec is written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`. It changes nothing in `frontend/src/features/workspace`.

## Context
Worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend` at origin/main (API 1.24.0).
- Built today on the v7 mock (F-40 part 1): `src/features/workspace/Workspace.tsx` (`line_key === 'delivery_handover'`, `screenHeading`), `src/features/response/SupportHandoverForm.tsx` with `ResponseForm.tsx`, `ProofField.tsx`, `ReconcilePanel.tsx`, `useResponse.ts`, `api.ts`; `src/features/work-item/WorkItemView.tsx:285` (project crumb for the handover line); mock fixtures `mock/fixtures/work/W-3701..W-3708`, `mock/fixtures/response/W-37xx.*`, `mock/response.mjs` (G-48-1 overlay). Those use `tasks[].response`, `workspace.steps` and `POST /tasks/{id}/response`, none of which exist live (DC-2).
- Live client: `src/api/client.ts` (`liveApi`, `call()`, shared CSRF), `src/api/live-schema.d.ts` (already carries the four support operations), `src/api/errors.ts`.
- Shared frame from F-85 (not yet on main): `src/features/workspace/adapter.ts` (`LineAdapter`, `PanelRef`, `LineContext`, `CommandDescriptor`, `registerLineAdapter`), `weeklyReportAdapter.ts` as the reference, and `useWorkItem` reading the live `GET /work/{id}` with `panels[]`.
- Live operations (look up with `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live <METHOD> <path> 3`):
  - `GET /work/{work_id}/support-publication` returns `{expected_revision, case_revision, can_publish, version_id|null}`.
  - `POST /work/{work_id}/support-publication` takes `{expected_revision, case_revision, version_id}` and returns 202 `{work_id, state, revision, record_id}`.
  - `GET /work/{work_id}/support-replies` returns `{expected_revision, case_revision, roles[], channels[email|whatsapp|client_portal|signed_document|meeting], can_record, proofs[{id,version,kind}] (max 50), receipts[{id, recipient, recorded_at, previous_id|null, status received|gaps|null, reply{party, channel, responded_at, note, gaps[] (max 10, each at most 400 chars)}|null, ...}]}`. The builder reads the full `receipts[]` item schema in the contract.
  - `POST /work/{work_id}/support-replies` takes `{expected_revision, case_revision, receipt_id, previous_id|null, status, evidence_id, note, party, channel, responded_at, role, gaps?[]}` and returns 201 `{work_id, state, revision, record_id}`.
  - `GET /work/{work_id}/support-receipt` returns `{expected_revision, case_revision, receipts[{id, can_acknowledge, status}], document{id,title,version,sections[{heading,text}],supporting_records[]}|null, proofs[]}`. `document` is non-null only for the real Support recipient (D-24).
  - `POST /work/{work_id}/support-receipt` takes `{expected_revision, case_revision, receipt_id, evidence_id, status, note}` and returns 200.
  - `POST /work/{work_id}/corrections` (the `delivery-handover/v1` variant) takes `{expected_revision, case_revision, line, reason, source{inputs{template_id, support_document, escalation_document}}}` and returns 200.
  - `POST /work/{work_id}/actions` takes `{expected_revision, action:"reconcile"}` and returns 202.
  - `GET /work/{work_id}` and `GET /work/{work_id}/history` as in the F-85 spec.

## Contract

### Adapter mapping (this feature's own file)
`src/features/delivery-handover/handoverAdapter.ts` (new, in the feature, not in `workspace`) implements F-85's `LineAdapter`:
- The handover has more than one read, so the adapter's `read()` fetches `support-publication`, `support-replies` and `support-receipt` for the work id in parallel and returns one `HandoverReadback`. Which panel keys `GET /work/{id}` lists for this line is read from `panels[]` at build time; the adapter registers for whichever key the live response carries for this line. The builder names the key in `build.md`. If `panels[]` carries no key for this line, the page routes by `line` instead and says so (see Questions 4).
- `support-receipt` is read only to learn `receipts[].can_acknowledge` and `document`. A 403 or 404 from it (the viewer is not a Support recipient) is not an error for the page: it means "no recipient view" and the other reads still draw.
- Tokens: `expected_revision` and `case_revision` are taken from the same response the command is built from (`support-replies` for replies and reconcile, `support-publication` for publish). A null token stays null, never 0. Every write is built from a read made on the same page load and re-read after a 409.
- `commands()` returns `handover.publish`, `handover.record_reply`, `handover.acknowledge`, `handover.draft_v2` and `handover.reconcile` descriptors. `idempotency.field` is null for all of them (the live bodies carry no key field). Double presses are prevented in the UI (below), because the server offers no replay key.
- `disabledReason` comes only from the readback (`can_publish:false`, `can_record:false`, `can_acknowledge:false`). The page never invents a reason.

### Screen states
The page header is the F-85 work item header (title, state tag, next step, blocker, activity). Below it the handover panel draws these parts, each only when its data exists:

1. **Handover status** (always): one sentence built from `state` and the receipts. "Waiting to be published" when `can_publish` is true. "Queued for Support" after a publish this session or `state` `processing`. "Support found N gaps" when the latest receipt has `status:"gaps"`. "Support received it" when the latest receipt has `status:"received"`. "Not recorded" otherwise. The words "received", "published" and "acknowledged" appear only from a read, never from a 202.
2. **Publish to Support** (success, `can_publish:true`): the SCR-48 default "Next" block with the button. The consequence line is the board's: "Publishing sends it to Support. Then you record whether they received it or found gaps." The button posts as below. When `can_publish` is false the block is absent with no disabled button and no explanation text (the backend sends no reason).
3. **Support's reply** (from `support-replies.receipts[]`): one row per receipt. It shows `recipient`, the status word (Received or Gaps), `reply.party`, `reply.channel` as words, `reply.responded_at`, `recorded_at`, and `reply.note` when present. A receipt with `status:null` reads "No reply recorded yet". A record that another record replaced (it is some other row's `previous_id`) reads "Replaced" and sits below the current one. The recorder's name is not served; the page does not draw one.
4. **Gaps** (from `reply.gaps[]` of the latest receipt with status gaps): numbered rows as the gaps board draws. The row tag "OPEN" is drawn only while the latest receipt still has status gaps. The backend serves no per-gap status, so no row says closed or resolved. A latest receipt with status received shows no gaps list.
5. **Record Support's reply** (form, only when `can_record:true`): see Record form.
6. **Support receipt** (separate record): from `support-receipt.receipts[]`. A row shows "Acknowledged by Support: received / gaps" only when `status` is non-null for that receipt. A row with `can_acknowledge:true` shows "Support's own acknowledgement" with a small form (proof, status, note) for the signed-in recipient (see Acknowledge). Nothing here is derived from the PM's record.
7. **Ask Tola to draft v2** (corrections): shown when the latest receipt has status gaps. The button posts `corrections`. If `GET /work/{id}` does not list corrections as an allowed action, see Questions 3.
8. **Uncertain delivery**: when `state` is `effect_uncertain` or `awaiting_reconciliation`, show the existing banner wording from `src/features/response/ReconcilePanel.tsx` and one button "Check what happened" posting `actions` reconcile. No resend, no new publish while uncertain.
9. **History**: the F-85 `/work/{id}/history` page, unchanged.

Not drawn, with no placeholder (D-182, DC-3): Tola's step card ("Support handover v1 · Tola · done", REL/GLV/ARC references, "TEST TEMPLATE", "2 ATTACHMENTS", "Drafted 08 Apr"), the "Review needed? NO" line, the handover document summary and attachments for the PM, the "Open question for PSL" note, the Delivery sub-nav, Journey/Planning tabs and their counts. The document title, version and sections are drawn only inside part 6 when `document` is non-null (the real recipient).

Page states for loading, error, permission and empty follow the F-85 work item: loading skeleton; 401 signed-out link; 403 `csrf_failed` is "Refresh your session and try again"; 404 and "not yours" both read "This record is unavailable."; 429 and 503 "Try again shortly" with a retry. An item with `can_publish:false`, `can_record:false`, no receipts and no document shows the header, the status sentence "Not recorded", and nothing else.

### Publish to Support
- `GET /work/{id}/support-publication` on load and after every write. Request: none.
- `POST /work/{id}/support-publication` body `{expected_revision, case_revision, version_id}` with `version_id` exactly as read (never typed or chosen). A null `version_id` hides the button.
- 202 `{state, revision, record_id}`: show "Queued for Support" and re-read all three reads. Poll like F-85 while `state` is `processing`. A 202 is never shown as delivered.
- Errors: 409 shows "This changed while you were looking. The page has been refreshed." and re-reads, with no automatic second post. 422 shows `message` and the first `fields[].message`. 403 `csrf_failed` refreshes the session and says "Press Publish again" (nothing was sent). 403 otherwise: "You can't publish this handover." 404: "This record is unavailable." 429/503: "Try again shortly. Check below before you press Publish again" and the page re-reads first. A dropped connection or timeout is treated as uncertain: re-read, and if `state` is `effect_uncertain` show the reconcile control; never offer Publish again until the re-read says `can_publish:true`.
- The button is disabled from the first press until the re-read returns. One press makes one POST.
- Permission: the backend decides (`can_publish`). The configured publisher identity is not shown or invented.

### Record Support's reply
- The form draws from the record boards, with the live fields:
  - **Who replied** (`party`): a text field (the board's "Femi Ojo · Support lead" row). Not prefilled.
  - **Role** (`role`): `roles[]` from the read. One role is shown as fixed text; several are a select. No default is chosen when there are several.
  - **How they replied** (`channel`): select over `channels[]` in words (Email, WhatsApp, Client portal, Signed document, Meeting). No default.
  - **When they replied** (`responded_at`): the shared date-time field; sent as ISO 8601 with offset; a future time is refused in the form.
  - **What Support said**: the Received / Gaps found segmented control (`status` received or gaps).
  - **Gaps** (`gaps[]`): shown only for Gaps found; one labelled box, one gap per non-blank line, trimmed, in order, as the board draws numbered lines. Needs 1 to 10 gaps and each at most 400 characters; Received sends no `gaps` key.
  - **Note** (`note`): a text area, required, at most 4000 characters (see Conflicts).
  - **Proof** (`evidence_id`): a select over `proofs[]` (each as "`kind` v`version`") (see Questions 1). With no proofs the field reads "No proof records available to attach yet" and Record stays off.
- Hidden fields: `receipt_id` is the id of the `receipts[]` row being recorded against; `previous_id` is that row's `id` when the row already has a status (this is a replacement) and null when `status` is null. If `receipts[]` has more than one row, the form asks "Which Support recipient?" with `recipient` words and sends the chosen row's id. See Assumptions.
- `POST /work/{id}/support-replies` with `expected_revision` and `case_revision` from the same read. 201 `{state, revision, record_id}`: re-read; the new record appears in part 3 and the form closes. One press, one POST, form disabled until the re-read.
- Errors: 422 puts each `fields[]` message beside its field and keeps what the person typed; 409 re-reads, keeps typed values, says "This changed while you were typing. Check it and press Record again."; 403 from a role not allowed reads "You can't record Support's reply here." and the form is not shown at all when `can_record` is false; 403 `csrf_failed` as above; 404, 429, 503 as above; 413/415 only come from files, which this form does not send.
- Idempotency: none on the wire. Double-press protection is the disabled button plus a re-read before any retry. A replacement is an explicit new record with `previous_id`; it never edits the old one.

### Acknowledge (Support's own)
When `support-receipt.receipts[]` has a row with `can_acknowledge:true`, a small form posts `POST /work/{id}/support-receipt` `{expected_revision, case_revision, receipt_id, evidence_id (from support-receipt.proofs[]), status, note}`; 200 re-reads. When no row has `can_acknowledge:true` there is no form. The PM's own record (part 5) is a different record and is labelled "Recorded by you for Support".

### Ask Tola to draft v2 and reconcile
- `POST /work/{id}/corrections` body `{expected_revision, case_revision, line:"delivery-handover/v1", reason, source:{inputs:{template_id, support_document, escalation_document}}}`. `reason` is a required text box (the board has none; see Conflicts). The three `inputs` ids come from the current work item's source as the live read supplies them; if the page cannot read them, the button is hidden and the gap is stated in `build.md` (it must not send nulls it made up). 200 re-reads.
- `POST /work/{id}/actions` `{expected_revision, action:"reconcile"}`: 202; re-read; the banner stays until `state` leaves `effect_uncertain`.

### Start
Start work chooser (`src/features/start-work/`) for the handover line posts `POST /work` `{line:"delivery-handover/v1", intake:{dossier_id, inputs:{template_id, support_document, escalation_document}}}` (shape verified with `oa.py live POST /api/v1/work 3`). `dossier_id` and the document ids are chosen from `GET /projects/{case}/intake-sources`; none is typed. A start that returns an existing work id opens it. Only changes needed to send the live body belong in `start-work/`; the chooser UI is otherwise unchanged. On failure the same error mapping applies.

### Mock fixtures (the mock serves these; shapes above are the contract, numbers are free)
Mock port 4991. For numeric work ids 4201 to 4208 (live shaped; the v7 `W-37xx` fixtures keep answering their own pages):
- 4201 ready to publish: `can_publish:true, version_id:9101`, no receipts.
- 4202 queued: `state:"processing"`, `can_publish:false`.
- 4203 record form: `can_record:true, roles:["Support lead"], channels:[all five], proofs:[{id:7301,version:1,kind:"signature"}]`, one receipt `status:null`.
- 4204 gaps: one receipt `status:"gaps"`, `reply.gaps:["No contact for the credit bureau outage","Runbook misses the nightly export restart"]`.
- 4205 received: latest receipt `status:"received"`, `previous_id` pointing at the gaps record.
- 4206 uncertain: `state:"effect_uncertain"`.
- 4207 recipient view: `support-receipt` has `document` and one row `can_acknowledge:true`.
- 4208 not yours: 404 for every route.
Fixtures carry a "sample" tag. They are mock results and the PR says no message was sent to Support.

## Lanes
- Frontend lane (owner of all of this feature): `frontend/src/features/delivery-handover/**` (new: adapter, panel, forms, hooks, tests), `frontend/src/features/start-work/{intake,useStartWork}.ts` (handover live body only), `frontend/src/features/response/{ReconcilePanel,labels}.ts*` (reuse; edit only to take live props), `frontend/src/api/types.ts` (live handover types), `frontend/mock/**` (live-shaped handover routes and fixtures 4201-4208), `frontend/e2e/delivery-handover.spec.ts`.
- Backend lane: none. No backend change. Open backend points are in Questions 1 and 3.
- Integration owner: lane D coordinator. Shared files this feature must not change: `frontend/src/features/workspace/**` (lane C owns; a needed frame change is named as a dependency on lane C), `src/api/*` beyond live handover types and error kinds if not already present, `src/shell/*`. Whichever of F-85 and this feature merges second merges current main first.
- The old v7 handover path (`SupportHandoverForm`, `W-37xx` fixtures, `POST /tasks/{id}/response`) is left in place for pages not yet moved and is not deleted here.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4201` on Next 4990 with mock 4991 shows the handover status "Waiting to be published" and a "Publish to Support" button with the board's consequence line; `/work/4204` shows no such button — verify: open both pages; `frontend/e2e/delivery-handover.spec.ts`.
2. Pressing Publish on 4201 sends one `POST /api/v1/work/4201/support-publication` whose body is exactly `{expected_revision, case_revision, version_id:9101}` with the values from the read, and the page then reads "Queued for Support", not "received" or "delivered" — verify: network panel and e2e assertion on the request body.
3. A double click on Publish makes one POST; during the re-read the button is disabled — verify: e2e counts requests.
4. A 409 on publish shows the refresh message, re-reads, and makes no second POST; a 422 shows the returned message; a 403 `csrf_failed` refreshes the session and says "Press Publish again"; a dropped connection triggers a re-read and no automatic resend — verify: mock scenarios and unit tests counting calls.
5. With `version_id:null` or `can_publish:false` there is no Publish button and no invented "why not" text — verify: unit test on the mapper.
6. `/work/4206` (`effect_uncertain`) shows the uncertain banner and "Check what happened", no Publish button; pressing it sends `POST /actions {expected_revision, action:"reconcile"}` once and accepts 202 — verify: e2e, network panel.
7. `/work/4203` shows the record form with Who replied, Role (fixed text for one role), How they replied (five channels in words), When, What Support said, Note and Proof (one option "signature v1"); Record is off until each required field is filled — verify: e2e.
8. Choosing Gaps found shows the Gaps box; two non-blank lines are sent as `gaps:["…","…"]` in order, trimmed; blank lines are dropped; zero gaps, more than 10 gaps or a line over 400 characters keeps Record off with a plain reason; choosing Received sends no `gaps` key — verify: unit test on the body builder; e2e.
9. The record POST body is `{expected_revision, case_revision, receipt_id, previous_id, status, evidence_id, note, party, channel, responded_at, role, gaps?}` with both revisions from the read, `previous_id:null` when the row had no status and the replaced row's id otherwise; a null revision is never sent as 0 — verify: unit tests on `handover.record_reply` body; e2e on 4203 and 4205.
10. With `can_record:false` (4202, 4208 as recorded) no form renders; a 403 on the POST says "You can't record Support's reply here." and keeps typed values; a 422 with `fields[]` shows each message by its field and keeps typed values; a 409 re-reads and keeps typed values — verify: mock scenarios; e2e.
11. After a successful 201 the page re-reads, the new record appears in "Support's reply", and the form closes; one press made one POST — verify: e2e counts requests.
12. `/work/4204` lists the two gaps as numbered rows tagged OPEN and shows "Ask Tola to draft v2"; `/work/4205` (latest received) shows no gaps list and no OPEN tag, and the earlier gaps record reads "Replaced" — verify: e2e.
13. "Ask Tola to draft v2" posts `corrections` with `line`, a required `reason`, both revisions and the `source.inputs` ids read from the work item; when those ids cannot be read the button is hidden — verify: unit test on the body; e2e.
14. `/work/4207` shows the recipient's "Support receipt" with the document title, version and sections and the acknowledge form; `/work/4201` (viewer is the PM, `document:null`) shows no document and no handover summary; a 403 from `support-receipt` does not break the page — verify: e2e on both; unit test on the 403.
15. The Support receipt ("Acknowledged by Support") renders only from `support-receipt` rows with a non-null `status`; the PM's own record never shows that wording — verify: unit test on the part-6 mapper.
16. Nothing on the page draws Tola's step card, "Review needed?", an attachments list for the PM, the sub-nav or "Open question for PSL", and the page leaves no empty heading or gap where they were — verify: e2e asserts absence; screenshots at 1440 and 390 against the SCR-48 default, record, gaps and received boards for the parts that remain.
17. Wrong user: `/work/4208` and a live id the account cannot see both show exactly "This record is unavailable." — verify: open both and compare; unit test on the 404 body.
18. Wrong tenant and a work item of another line: opening a work id whose `line` is not the handover line does not draw the handover panel — verify: unit test with another line's fixture.
19. Against live Django 8030 with an account that holds the PMO role and a delivery-handover work item, the page matches `GET /api/v1/work/{id}/support-publication`, `support-replies` and `support-receipt` field for field (can_publish, receipts, gaps, channels) — verify: compare the page with `curl` output using the session.
20. Against live Django 8030 the Publish and Record writes are not run against a real Support audience; the live check is read-only plus the reconcile-free record write on a sample item, and the result is labelled as a mock or live evaluation in `build.md` — verify: `build.md` text.
21. `liveApi.POST` appears only in the handover feature files for the six listed writes, none in `workspace/` — verify: grep.
22. `npm run lint`, `npm run typecheck`, `npm test` and `api-live-schema-drift.test.ts` pass; new unit tests cover the adapter mapper, each command body builder (nulls stay null, no key field on the wire), the status sentence, and the gaps parser — verify: `delivery/checks.sh`.

## Out of scope
- Tola's step cards and findings, the "Review needed? NO" line, the handover summary and attachments for the PM, the Delivery sub-nav and project tabs (DC-3, D-24, D-182).
- `POST /work/{id}/reviews` (document review): no SCR-48 board draws it.
- Any change under `frontend/src/features/workspace/` or to F-85's adapter types.
- Inventing a Support recipient, channel, publisher identity, attempt count, recorder name or per-gap status; editing the handover document; resending after an uncertain result.
- A file upload from this form (no live path from `upload_id` to a Support-reply `evidence_id` is documented).
- Closure, hypercare, archive and the other Delivery screens (F-113 to F-119).
- Backend, migrations, contract edits.

## Assumptions
- `receipt_id` is the `receipts[].id` of the recipient being recorded against; `previous_id` is that same row's id when it already has a status, else null. Reason: the contract names the field and the read gives a `previous_id` chain, but not who sets what. The builder verifies against live Django 8030 and the first mismatch goes back as a backend question.
- The note is required and at most 4000 characters. Reason: `note` is required in the body and the read caps `reply.note` at 4000.
- A role chosen from `roles[]` is sent as given, with no default. Reason: the backend checks the role.
- `Record` is hidden when `can_record` is false rather than shown disabled. Reason: no reason text is served.
- A dropped connection on a write is treated as uncertain and followed by a re-read. Reason: no idempotency key exists on these routes.
- The status sentence "Support found N gaps" counts `reply.gaps.length`. Reason: no separate count is served.
- Part 6 shows "No recipient view" silently when `support-receipt` answers 403 or 404. Reason: that is the normal case for the PM.
- The corrections `reason` is a required free-text box. Reason: the body requires `reason`; the board has none.
- Mock ids 4201-4208 are the builder's to create. Reason: no live-shaped fixtures exist.

## Questions
1. **Proof for Support's reply.** `evidence_id` must be an existing record, and no documented call turns an uploaded file into one for this route (D-1 says use the owning operation).
   1. Pick from `proofs[]` only, no upload. Recommended: it matches the contract and invents nothing.
   2. Pick from `proofs[]` and also show F-85's unconfirmed `EvidencePicker` upload proposal. Not recommended: it sends a file that may never become usable evidence.
   3. Hold Record until the backend names the path. Safe but blocks the flow.
   The record board draws an uploaded file chip ("support-reply-10apr.pdf · Uploaded · 40 KB"), so option 1 changes it to a select of existing records. Needs a design call.
2. **Fields the boards do not draw.** The live record needs Role, How they replied (channel), Who replied as text and a required Note; the record board draws one "Support replied" row, the status control, Gaps and the proof chip.
   1. Add the four fields, keep the board's order and layout. Recommended: the backend requires them.
   2. Fold role and channel into one row with the date. Fewer lines but cramped on 390.
   The "I confirm this response is genuine" tick that F-40 added is dropped because live has no `attested`.
3. **"Ask Tola to draft v2".** Live `corrections` needs a typed `reason` and the three source ids; the board has one button.
   1. Open a small reason box on press, ids read from the work item. Recommended.
   2. Prefill `reason` with the first gap text and send on one press. Faster but the PM never sees what is sent.
   3. Hide the button until the work item exposes the ids. Safe but removes a drawn control.
4. **Which panel key and route.** The F-85 page draws panels from `panels[]`; whether `GET /work/{id}` lists a handover panel key for this line in 1.24.0 is unconfirmed in this spec. If it does not, the feature selects the handover view by `line`, which is a small frame dependency on lane C.
   1. Route by `panels[]` key when present, else by `line` inside this feature's own page wrapper. Recommended: no frame change.
   2. Ask lane C to add a handover panel key. Cleaner but waits on another lane.
5. **Gap rows after v2.** Live gives no per-gap status, so "OPEN" is drawn while the latest record still has gaps and no row ever shows closed.
   1. Keep as specified. Recommended.
   2. Drop the OPEN tag entirely. Removes a drawn element.

## Conflicts with the boards
All for the design engineer to decide once before the build. They are also in Questions where marked.
1. Default board: the "Support handover v1 · Tola · done" card, "Review needed? NO", "Runbook and escalation contacts ATTACHED" and the "Open question for PSL" note are removed (no live source, D-24, DC-3). Recommendation: hide.
2. Default board "Publish to Support" button is kept but shown only when `can_publish` is true; the board's consequence line is kept. Recommendation: keep.
3. Record board: the uploaded file chip becomes a proof select (Questions 1); four fields are added (party text, role, channel, note) (Questions 2); the "genuine" tick is not drawn; "Support replied" is no longer a fixed "Femi Ojo · Support lead" row. Recommendation: as Questions 1.1 and 2.1.
4. Gaps board: numbered gap rows and the "Next" sentence are kept; "Support listed 2 gaps on 10 Apr" is built from `reply.responded_at` and the gap count; the line "isn't acknowledged until they're closed" is not drawn (no per-gap status). "Ask Tola to draft v2" gains a reason box (Questions 3). Recommendation: as written.
5. Received board: "Recorded by Tunde Bello with Support's reply as proof, verified" is not drawn (no recorder name or verified flag served); it reads "Support received it on {date}" plus the separate Support receipt row. "See what closure needs" and "Remaining: hypercare and the retrospective" are not drawn (no source). Recommendation: hide.
6. Sub-nav (Overview ... Closure), Journey/Planning tabs with counts and the project crumb byline are not drawn (F-85 header applies). Recommendation: as F-85 conflict 6.
7. Added with no board: the "Queued for Support" status, the uncertain banner with "Check what happened", the "Support receipt" block for the real recipient and the "Replaced" row. Recommendation: keep; they need a board from the design engineer.
