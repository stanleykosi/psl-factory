# Go-live acceptance records both signatures and the client's changes or decline

> Tasks: FE-DELIVERY-RELEASE (part 1; part 2 is F-114B). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the recorded exceptions in `design/review.json`; screens: SCR-45 (boards SCR-45-desktop, -signatures, -accepted, -changes, -declined and the five -mobile boards).

## Summary
- A new page `/work/{id}/go-live` for a work item on line `delivery-go-live/v1` lets the appointed PM record "Signed" with two distinct signature proofs and both signers' source details, through `GET/POST /work/{id}/go-live-signoff` and `POST .../go-live-signoff/proofs`.
- The same page records the client's reply (`changes_requested` or `declined`, by staff, nothing is sent to the client), shows `withdrawn` replies as read-only history, and prepares v2 after changes.
- For a declined reply it shows the fix options (log or link an issue, prepare a new release candidate, review the remediation).
- A read-only "what this unlocks" list shows only what the reads supply (accepted acceptance, linked issues, reviewed handoffs, the milestone name and whether one is recorded). Marking the milestone complete and the document review are F-114B.
- Waits for F-85 (lane C, PR #101) on main before the build starts. This delays the start only.

## Context
Where this lives today (lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`, API 1.24.0):
- No SCR-45 UI exists. `src/features/response/contract.ts` has an unused `go_live_acceptance` variant (v7 mock); do not extend it.
- Work item page: `src/app/work/[id]/(item)/page.tsx` and `src/features/work-item/` (F-85 turns this into the live read; panels come from `GET /work/{id}` `panels[]`). For line `delivery-go-live/v1` the backend lists panels `go-live-signoff`, `go-live-replies`, `go-live-milestone` (`apps/core/factory_api/work.py` `STATION_PANELS`; output panel is `go-live-milestone`).
- Shared adapter contract (F-85 spec, `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`): `src/features/workspace/adapter.ts` exports `PanelRef`, `LineContext`, `LineAdapter`, `CommandDescriptor`, `registerLineAdapter`, `adapterFor`; `workspace/EvidencePicker.tsx` and `workspace/evidence.ts` give `uploadCaseFile(caseId, file)` returning `upload_id`, with `UploadId` and `EvidenceId` as distinct branded types. Reuse them; do not change them.
- API client: `src/api/client.ts` (`liveApi`, `call()`, `refreshSession()`), `src/api/errors.ts`, live types `src/api/live-schema.d.ts` (go-live paths at about line 1415). Mock server: `frontend/mock/server.mjs`. File field: `src/components/FileUpload.tsx`.
- Backend (read only, for the rules below): `apps/core/factory_api/delivery.py` (`go_live`, `go_live_proof`, `record_go_live`, `current_signoff`), `apps/core/factory_api/go_live_replies.py` (`detail`, `decline_options`, `command`, `prepare_successor`).
- Live reads (viewer: `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/work/{work_id}/go-live-signoff 3`; the viewer truncates nested objects, so the shapes below are from the contract JSON).

## Contract

All writes are made as the signed-in person with `X-CSRFToken` through `liveApi`. The 404 body is the same for "missing" and "not yours"; show "This record is unavailable." for both (as F-85). Error words: 400/422 show the first `fields[].message` or `message`; 409 "This changed while you were working. We reloaded it. Check it and try again." (re-read both reads); 429 "Try again shortly."; 403 `csrf_failed` refreshes the session and says "Press the button again" (nothing was sent); 413/415 on the proof upload use F-85's wording; 503 and network "We couldn't reach the server. Nothing was recorded."; any write whose response is lost (network after send) reads both reads again and says "Check the record before trying again" with no automatic retry.

### Reads
1. `GET /work/{id}/go-live-signoff` (only the appointed PM; other callers get 403 or 404): `{expected_revision, case_revision, version_id, receipts[{id, recorded_at}], prior_acceptance_id|null, proofs[{id, version, kind}] (max 100, kind `signature`)}`.
2. `GET /work/{id}/go-live-replies`: `{expected_revision, case_revision, channels[email|customer_portal|meeting|phone|other], finding, capture[{receipt_id, previous_id|null, roles[]}], corrections[...], replies[{id, receipt_id, version_id, number, outcome changes_requested|declined|withdrawn, party|null, channel|null, responded_at|null, note|null, evidence_id|null}], linked_issues[{reply_id, issue_id}], reviewed_handoffs[{reply_id, review_id, dossier_id}], milestone{recorded_id, configuration_id, name, acceptance_id, proof_ids[], owner_decision_ids[]}}`. A reply whose source is not available to the caller has null party, channel, responded_at, note and evidence_id: show "Details not available to you", never blank or 0.
3. `GET /work/{id}/go-live-replies/decline`: `{expected_revision, case_revision, issues[{reply_id, existing_issues[{id,label}], owners[{id,label}]}], new_candidates[{reply_id, requirements_id}], review_options[{reply_id, previous_id|null, roles[], destinations[{id,label}]}], rules|null}`. Read only when at least one reply has outcome `declined`.
4. `GET /work/{id}` (F-85): `state`, `status_label`, `title`, `case_id`, `panels[]`, `revision`, `case_revision`, used for the header and to find the line.
Revision pair: every write sends `expected_revision` and `case_revision` from the most recent read of the same operation family (sign-off read for sign-off and proof; replies read for replies and successor; `case_revision` for the proof). A `null` revision is passed as unknown and disables the write.

### Writes
| Action | Request | Success | Notes |
|---|---|---|---|
| Upload a signed copy | `POST /work/{id}/go-live-signoff/proofs` `{case_revision, receipt_id, upload_id, role:"PM"\|"Client", checked:true}` | 201 `{evidence_id, case_revision}` | `upload_id` comes from F-85's `uploadCaseFile` (`POST /cases/{case_id}/files`). `checked` is sent only when the person ticks "I checked this is the signed copy of this go-live document for this signer" (const true). One call per signer. The new `case_revision` replaces the held one and the sign-off read is refetched so `proofs[]` lists the new id. |
| Record "Signed" | `POST /work/{id}/go-live-signoff` `{expected_revision, case_revision, version_id, receipt_id, pm_signature_id, client_signature_id, signers{PM,Client each {source_system, source_reference, decision_id, decision_version, signer_reference, signed_at}}, mode, prior_acceptance_id, note}` | 200 `{work_id, state, revision, record_id}` | `pm_signature_id` and `client_signature_id` are `proofs[].id` and must differ (D-15); the form refuses the same id twice and the API also does. Every signer field is 1 to 160 characters, `signed_at` is a date-time, `note` 1 to 4000. `version_id` and `receipt_id` come from the read, never typed. `mode`: `fresh_signatures` always offered; `metadata_binding` offered only when `prior_acceptance_id` is not null, and then sends that id; `fresh_signatures` sends `prior_acceptance_id: null`. |
| Record client reply | `POST /work/{id}/go-live-replies` `{action:"record_reply", expected_revision, case_revision, receipt_id, previous_id, outcome:"changes_requested"\|"declined", party, responded_at, channel, evidence_id, note, role, attested:true}` | 201 `{work_id, state, revision, record_id}` | `receipt_id` and `previous_id` come from the matching `capture[]` entry; `role` is one of that entry's `roles[]`; `channel` is one of the read's `channels[]`; `attested` is a required tick, "I attest this is what the client told us" (the box must be ticked to send). `party` 1 to 160, `note` 1 to 4000. `evidence_id` is an integer recorded evidence (see Assumption 1). `withdrawn` is never offered. |
| Prepare v2 | `POST /work/{id}/go-live-replies/successor` `{expected_revision, case_revision, inputs{template_id, checklist, incident_reporting, rollback}, reason}` | 200 `{work_id, state, revision}` | Shown only when the latest reply that is not `withdrawn` is `changes_requested`. `reason` 1 to 2000. The four inputs are sent as `null` (see Assumption 2). |
| Link a decline issue | `POST /work/{id}/go-live-replies` `{action:"link_decline_issue", expected_revision, case_revision, reply_id, existing_issue_id, title, owner_id, next_action, note}` | 201 | Either choose an `existing_issues[]` entry (title, owner_id, next_action null) or create new (existing_issue_id null; title up to 240, owner from `owners[]`, next_action up to 1000). `note` required. |
| Prepare a new candidate | `{action:"prepare_new_candidate", ..., reply_id, reference, requirements_id, note}` | 201 | `requirements_id` from `new_candidates[]` for that reply (not typed); `reference` up to 160. |
| Review the remediation | `{action:"review_remediation", ..., reply_id, previous_id, destination_id, role, evidence_id, note}` | 201 | `previous_id`, `roles[]` and `destinations[]` from `review_options[]` for that reply. |
Idempotency: none of these has a key. The submit button is disabled while a call is in flight and after a 2xx until the reads are refetched, so a double click sends one call. After 2xx both reads are refetched; the screen shows what the read says, not what was typed. Versioning: a 409 means someone else changed the record.

### Permission rules
- Sign-off read and write are for the appointed PM only. If the sign-off read returns 403 or 404 but the replies read works, the page shows the replies and the unlock list and, where the sign-off form would be, the words "Only the appointed PM records the signatures." (no form).
- Reply write controls appear only when `capture[]` has an entry (that entry's `roles[]` also decide the role list); with no entry show `finding` as the reason. Decline controls appear only for the actions the decline read supplies options for (`issues[]`, `new_candidates[]`, `review_options[]` entries for that `reply_id`). Never decide access from the person's role in the client.
- Project (tenant) scope is the backend's; the page only requests the `work_id` in the URL and uploads to the loaded item's `case_id`.

### Page states
Route `/work/[id]/go-live`, layout as the SCR-45 boards: header with state tag from `GET /work/{id}`, then the sections below. A line other than `delivery-go-live/v1` shows "This record is unavailable."
- Loading: skeleton for header and sections (existing `WorkItemStates` loading).
- Error: per-read. If `GET /work/{id}` fails the whole page shows the F-85 error state. If one of reads 1 to 3 fails the other sections still draw and the failed section shows its mapped message with Try again.
- Empty (nothing delivered yet: `receipts[]` empty): "The go-live document hasn't been sent to the client yet." and no forms. Matches board SCR-45-desktop (in review) apart from the hidden parts.
- Ready to sign (board -signatures): "Sent to the client" block from `receipts[]` (latest `recorded_at`, "delivery recorded"; the channel and "delivery confirmed" wording are not supplied, so only "Delivery recorded {time}"), then the sign-off form: for each of PM and Client, a signed-copy picker (upload or choose from `proofs[]` by "Signature record #{id}, version {version}"), the six signer fields, then `mode`, `note` and "Record signatures".
- Needs reconciliation: if either signer has any empty source field, or fewer than two distinct proofs are chosen, "Record signatures" is disabled and the signer block says "Needs reconciliation: add the source system, reference, decision id and version from the signed record." Do not invent or prefill values (D-16).
- Accepted (board -accepted): when `milestone.acceptance_id` is not null: "Go-live accepted" with the acceptance id, and the unlock list. With only `prior_acceptance_id` not null (and `milestone.acceptance_id` null) show "An earlier acceptance is on file (#id)" and the `metadata_binding` option, not the accepted banner.
- Changes (board -changes): latest non-withdrawn reply `changes_requested`: party, date, note quoted; "v1 not accepted" is not drawn (not supplied); the Prepare v2 form.
- Declined (board -declined): latest non-withdrawn reply `declined`: the quoted note, then the decline panel (issues, new candidates, review options) from read 3, `rules.current` summarised read only (recording roles, channels, handling words as the API gives them; null shows "No response rules set").
- History: all `replies[]` by `number`, `withdrawn` as read-only rows "Withdrawn".
- Success (after a write): inline "Recorded." with the returned `record_id`, then the refreshed sections.

### What this unlocks (read only, no write)
Rows drawn only when a read supplies them: "Acceptance" (`milestone.acceptance_id` set or not), "Issues linked to this decline" (count of `linked_issues[]`, each issue id linking to the project issue page when one exists, else plain text), "Reviewed handoffs" (count of `reviewed_handoffs[]`), "Milestone" (`milestone.name` when not null; "Recorded" when `recorded_id` is not null, else "Not recorded yet"). No "Hypercare ... RUNNING" and no "Archive and handover STARTED" rows. No button to mark the milestone complete.

### Fixtures (mock, ports 4991; builder creates in `frontend/mock/go-live.mjs`; the ids are free, the shapes are the contract)
- `4401` ready to sign: one receipt, two `signature` proofs, `prior_acceptance_id:null`, replies empty.
- `4402` accepted: `milestone.acceptance_id:7001`, `name:"Go-live"`, `recorded_id:null`.
- `4403` changes requested: one reply `changes_requested`, note "Add the bureau outage contact to the incident plan.", `capture[]` empty.
- `4404` declined: one `declined` reply with an `issues[]`, `new_candidates[]` and `review_options[]` entry.
- `4405` another PM: sign-off read 403; replies read works.
- `4406` earlier acceptance: `prior_acceptance_id:6990`, `milestone.acceptance_id:null`.
- `4407` conflict: the sign-off POST answers 409 once, then 200.
- `4408` source-hidden reply: all of a reply's party, channel, responded_at, note and evidence_id null.
- `4409` withdrawn history: `[changes_requested, withdrawn]`.
- `4410` empty: `receipts:[]`.

## Lanes
- Frontend lane (owner of all of this feature): `frontend/src/features/go-live/**` (page, the two adapters `goLiveSignoffAdapter.ts` and `goLiveRepliesAdapter.ts` registered through `registerLineAdapter`, hooks, form components, labels), `frontend/src/app/work/[id]/go-live/page.tsx`, `frontend/mock/go-live.mjs` and its registration in `frontend/mock/server.mjs`, live types for these routes in `frontend/src/api/types.ts` only if needed, and tests under `frontend/src/features/go-live/` and `frontend/e2e/go-live.spec.ts`.
- Backend lane: none. No contract edit. Backend gaps are in `delivery/connect/backend-questions.md`.
- Integration owner: lane D coordinator. Shared files and who owns them: `src/features/workspace/*` and `src/features/work-item/*` are lane C's (F-85) and are not changed here; the only link from the work item page to `/work/{id}/go-live` is a dependency on lane C (one link for panel keys `go-live-signoff` and `go-live-replies`; the builder adds it as a separate small commit after `git merge origin/main` and says so in build.md, per LANES.md). `src/api/*` shared: add types and error kinds only if missing.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4401/go-live` (mock) shows the "Sent to the client" block with the receipt time, a PM block and a Client block each with a signed-copy picker, six signer fields, and a disabled "Record signatures" — verify: open the page; `frontend/e2e/go-live.spec.ts`.
2. Choosing a file for the Client signer runs the picker upload then `POST /work/{id}/go-live-signoff/proofs` with `role:"Client"`, `receipt_id` from the read, the held `case_revision` and `checked:true` only after the box is ticked; the returned `evidence_id` is then listed from the refetched sign-off read — verify: network panel and unit test on the request body; no proof call is made with the box unticked.
3. The form cannot submit the same proof id for PM and Client; selecting the same one shows "Choose a different signature record for each signer" and sends nothing — verify: unit test, network panel shows no POST.
4. With both signers' six fields filled and two distinct proofs chosen, "Record signatures" sends one `POST /work/{id}/go-live-signoff` whose body contains `expected_revision`, `case_revision`, `version_id`, `receipt_id`, `pm_signature_id`, `client_signature_id`, both `signers` objects, `mode:"fresh_signatures"`, `prior_acceptance_id:null`, `note`; on 200 the sections refetch — verify: unit test on the request body; e2e on 4401.
5. With any signer field empty for either signer, the signer shows "Needs reconciliation" and the submit stays disabled; no value is prefilled — verify: e2e blanks one field; unit test.
6. On `4406` the `metadata_binding` option appears and, when chosen, sends `prior_acceptance_id:6990`; on `4401` the option is absent — verify: unit tests on both fixtures.
7. A 409 on the sign-off POST (`4407`) shows the changed-record message, re-reads both reads, keeps nothing as recorded, and a second press sends a fresh body with the new revisions — verify: e2e counts calls and compares revision values.
8. A double click on "Record signatures" sends exactly one POST — verify: unit test with a slow mock counts calls.
9. A caller who is not the appointed PM (`4405`) sees no sign-off form, the words "Only the appointed PM records the signatures.", and still sees replies and the unlock list — verify: e2e on 4405.
10. A work id not on this line, or one that returns 404 (wrong tenant or wrong user), shows exactly "This record is unavailable." with no difference between the two — verify: e2e with two fixtures; unit test on the mapper.
11. On `4410` (no receipts) no form is drawn and the page says the document has not been sent — verify: e2e.
12. On `4402` the "Go-live accepted" banner and unlock rows draw only from the reads (acceptance, linked issues count, reviewed handoffs count, milestone name and "Not recorded yet"); there is no "Mark milestone complete" control and no "Hypercare" or "Archive and handover" row — verify: e2e DOM assertions.
13. On `4406` the accepted banner is not drawn; "An earlier acceptance is on file (#6990)" is — verify: e2e.
14. Recording a reply (fixture with `capture[]`): the form offers only `changes_requested` and `declined`, only `channels[]` from the read and only the entry's `roles[]`; sending without the attestation tick is blocked; the POST body has `action:"record_reply"`, `receipt_id`, `previous_id`, both revisions, `attested:true` — verify: unit test; network panel.
15. With `capture[]` empty (`4403`) the reply form is absent and `finding` is shown as the reason — verify: e2e.
16. `4403` shows the client's quoted note and the Prepare v2 form; submitting sends `{expected_revision, case_revision, inputs:{template_id:null, checklist:null, incident_reporting:null, rollback:null}, reason}` — verify: unit test on the body.
17. `4404` shows the decline panel: choosing an existing issue sends `link_decline_issue` with `existing_issue_id` and null title, owner and next action; creating a new one sends title, `owner_id` from `owners[]`, `next_action` and null `existing_issue_id`; `prepare_new_candidate` sends the `requirements_id` from the read; `review_remediation` sends `previous_id`, `destination_id` and `role` from `review_options[]` — verify: one unit test per action on the request body.
18. A decline control for a `reply_id` with no entry in `issues[]`, `new_candidates[]` or `review_options[]` is not drawn — verify: unit test.
19. `4409` lists the `withdrawn` reply as a read-only history row with no control, and no "withdrawn" option exists in any form — verify: e2e.
20. `4408` shows "Details not available to you" for a reply whose party, channel, note and date are null and never shows 0, blank or "null" — verify: e2e DOM.
21. Nothing is sent to the client: no request other than those in the Contract is made by this page, no email or message call — verify: grep `liveApi.POST` and `liveApi.GET` in `frontend/src/features/go-live` lists only the routes in the Contract; network panel on a full run shows none other.
22. Unit test: the proof upload accepts a PDF and refuses a `.exe` or a file over the picker's limit before any request, and an `UploadId` cannot be passed where an `EvidenceId` is expected (`// @ts-expect-error`) — verify: `go-live` unit tests.
23. Against live Django (8030, account the appointed PM of a go-live work item) the page's receipts, proofs, replies, `prior_acceptance_id` and milestone match `GET /api/v1/work/{id}/go-live-signoff` and `.../go-live-replies` — verify: compare the page with the `curl` JSON using the session.
24. A write answered 403 `csrf_failed` refreshes the session once and says to press again; no automatic second POST — verify: unit test counts calls.
25. Viewport check at 1440 and 390: the page matches the SCR-45 boards (header, sent block, signatures, accepted, changes, declined) for the parts kept; hidden parts leave no empty heading or gap — verify: screenshots at both widths reviewed against `design/screens.md` SCR-45 artboards.
26. `npm run lint`, `npm run typecheck` and `npm test` pass and `api-live-schema-drift.test.ts` still passes — verify: `delivery/checks.sh`.

## Out of scope
- F-114B: `POST /work/{id}/go-live-milestone` (`draft_mapping`, `record_completion`), "Mark milestone complete", `POST /work/{id}/reviews` (document review), `POST /work/{id}/corrections`, correcting or withdrawing a recorded reply (`corrections[]` is read but not used), the Setup review response `POST /setup/{case}/policy-configurations/{id}/review`.
- Drafting the response rules (`POST .../go-live-replies/decline`): no board, and rules are validated and activated in Setup. Only `rules.current` is shown read only.
- Tola's agent card and steps, "Ask Tola", the single "Signed / Changes / Declined" form with one proof, and any attempt count or amount (D-182, DC-3).
- "Hypercare can be evaluated: RUNNING" and "Archive and handover STARTED" as unlock rows.
- Sending anything to the client; a client login; email or portal delivery.
- Generic `/cases/{id}/files` as the signature path other than through the sign-off proofs call that retains it as evidence (D-1).
- Changes to `frontend/src/features/workspace`, `work-item` or `shell`; backend, migrations, contract edits.

## Assumptions
1. The proof for a reply or remediation (`evidence_id`, an integer) is recorded evidence obtained through F-85's `fileToEvidence` proposal (unconfirmed, backend question 1). The reads supply no list of such ids and no go-live reply proof route exists. If that proposal yields no evidence id the reply write stays disabled with "Add a proof first" and is listed in build.md as held. Reason: the contract requires an integer and offers no other source.
2. Prepare v2 sends all four `inputs` as `null`. Reason: the fields are nullable and no read lists template, checklist, incident or rollback options; the API's 422 text is shown if it needs them.
3. The accepted banner depends on `milestone.acceptance_id`, not `prior_acceptance_id`. Reason: the sign-off read does not say whether the prior acceptance is verified.
4. `fresh_signatures` sends `prior_acceptance_id: null` and `metadata_binding` sends the read's id. Reason: the contract shows the field and the two modes; no other reading is supplied.
5. The page is a new route `/work/{id}/go-live` linked from the work item page, not a section inside the shared frame. Reason: forms with uploads need own state, and the frame is lane C's.
6. Signed-copy choices are labelled "Signature record #id, version n". Reason: `proofs[]` has only id, version and kind.
7. "Delivery confirmed" and the channel of the sent document are not shown. Reason: `receipts[]` carries only id and recorded time.
8. Mock ids 4401 to 4410 are free to renumber. Reason: no live fixtures exist.
9. The reply attestation wording and the "I checked" wording are the builder's plain words. Reason: no board text; the API only needs the booleans.

## Questions
1. **Where does the client reply's proof come from?** (a) Use F-85's file-to-evidence proposal and hold the write if it yields nothing (recommended; matches Assumption 1). (b) Hold the reply and remediation writes until the backend names an evidence route. (c) Let the PM pick from the signature proofs list (wrong kind, not recommended). Context: `record_reply` and `review_remediation` need an integer `evidence_id` and nothing in API 1.24.0 supplies one; goes to backend question 1.
2. **"Ask Tola to draft v2" (board -changes).** (a) Show "Prepare v2" with a reason box and no agent wording (recommended, D-182). (b) Keep the "Ask Tola" label. (c) Hide the control until the API lists template and checklist options. Context: the API only takes four optional ids and a reason; there is no agent step.
3. **One form versus two on the board.** The board draws one "What the client did: Signed / Asked for changes / Declined" with a single proof. (a) Keep a three-way choice at the top that switches between the sign-off form and the reply form, each with its own fields (recommended: looks like the board, matches the two APIs). (b) Show the sign-off form and the reply form as two separate sections. (c) Follow the board literally (impossible: needs two proofs and signer details).
4. **Signer source fields have no board.** The API needs source system, reference, decision id, decision version, signer reference and signed time for each signer. (a) Show them as six plain fields per signer under the signature picker with the "Needs reconciliation" message (recommended). (b) Collapse them under "Signer record details". (c) Hide until the design engineer draws them (blocks the write).
5. **Link from the work item page.** (a) A single "Open go-live acceptance" link on `/work/{id}` for panel keys `go-live-signoff` and `go-live-replies`, added as a small lane C commit (recommended). (b) Make the adapters draw the full forms inside the shared frame (needs a frame change). (c) Reach the page only from the Delivery tab.

## Conflicts with the boards
1. Tola's card, steps, "Ask Tola", "Tola drafts v2 NEXT" and the "Ask Tola to draft v2" button are not drawn (no agent steps in the API, DC-3). Recommendation: hide and use Question 2 (a).
2. The single Signed / Asked for changes / Declined form with one proof is replaced by a sign-off form (two proofs, signer details) and a reply form. Recommendation: Question 3 (a).
3. "Client signed: Ngozi Bello, Head of Lending Operations" and "PM signed: Tunde Bello" lines are not drawn; the API holds signer references and times, not names or titles. Recommendation: show signer reference and signed time only after the record exists, and only if a read supplies them (none does in part 1), so hide.
4. "Delivery confirmed", the send channel ("emailed 31 Mar 10:02") and attachment rows (checklist, incident plan, rollback plan) are not drawn (`receipts[]` has id and time only). Recommendation: hide; "Delivery recorded {time}".
5. "Hypercare can be evaluated: RUNNING" and "Archive and handover can start: STARTED" are not drawn; replaced by the rows the reads supply. Recommendation: accept.
6. "Mark milestone 3 complete" and "Open the document review" are not drawn (F-114B). Recommendation: leave out until F-114B, with a one-line "Milestone completion is recorded separately" only if the design engineer wants a pointer.
7. Added, not drawn on any board: signer source fields, `mode` choice, channel, recorder role and attestation, reply history with withdrawn rows, the decline panel option lists (existing issue, owner, candidate, destination). Recommendation: keep; each is required by the API and needs a board from the design engineer (Question 4).
8. "v1 NOT ACCEPTED", the "Review, then send again" steps and "Declined: Hypercare, archive and handover ON HOLD / Milestone 3 NOT COMPLETE" rows are not supplied by any read and are hidden. Recommendation: hide.
