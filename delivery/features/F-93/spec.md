# An authorised person can record what happened to an uncertain send from the work item, live

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0 (re-checked 23 Nov: tracking read `can_record_delivery_observation`, `delivery_observation_url`, `uncertain_effects[]`; `proofs_url`; `POST/GET /work/{work_id}/delivery-observations`; `POST/GET /work/{work_id}/proofs`). Design: approved 13 Nov canvas under the recorded exception in `design/review.json`; screens: SCR-02 (work item, state awaiting-reconciliation, desktop and phone).

## Summary
- On a live work item (`/work/{integer id}`) the "Confirm what happened" panel the SCR-02 awaiting-reconciliation board draws appears when the tracking read says the person may record an outcome. The person picks "It arrived", "It didn't arrive" or "I can't tell yet", writes a reason, attaches proof, and "Record and continue" sends the proof and then `POST /work/{id}/delivery-observations` (201).
- D-187 (LC-Q19, accepted as recommended): plain sublines that promise nothing the backend does not do, a required Reason box, the proof picker always shown, and the footer "Your choice is recorded with your name."
- The page never invents who may record. The panel is drawn only on the served flag, a same-origin URL for this work item and at least one uncertain effect; the server checks recovery authority and its 403 and 409 are shown as given.
- A recording never resends, reminds, verifies or approves anything, and the page says none of those. If the POST ends uncertain, the page reads the observations list to settle it and never retries by itself.
- Builds after F-87 is merged. This feature, with F-87, covers the old F-87 criteria 3 and 23 to 32 once; F-87 holds the rest.

## Context
Lane C worktree `/Users/Hunchoo/psl-factory-worktrees/lane-c/frontend`. All of this exists after F-85 and F-87 merge; the builder starts from F-87 merged.
- Live page: `src/features/work-item/live/LiveWorkItemView.tsx` (`Header`, `Overview`, `PanelView`), `live/useLiveWorkItem.ts`, `live/model.ts`. `item.revision` and `item.case_revision` are nullable; `item.tracking_url` and `item.proofs_url` come from `GET /work/{id}`.
- From F-87: `workspace/useWorkCommand.ts` (`useWorkCommand({ item, reload })`, press lock, uncertain lock, error mapping), the shared locking piece extracted from `workspace/useWorkspaceStep.ts`, `workspace/adapter.ts` with `makeCommand` (optional `action: null`, inputs cannot override descriptor fields), `workspace/workItemCommands.ts`, the controls row in `Overview` with its single result `Callout`, and `LineAdapter.Actions` (not used here; this panel is not line-specific).
- From F-85: the tracking read hook for `GET {item.tracking_url}` (if it is not exported, add only a read of `tracking_url`), `EvidencePicker` and `uploadCaseFile` (`POST /cases/{case_id}/files`, yields `upload_id`).
- Errors: `src/api/errors.ts` (`ApiError.kind`, `fields`), `liveApi` in `src/api/client.ts`.
- Old v7 reconcile UI `src/features/response/ReconcilePanel.tsx` stays for `W-xxxx` ids and is not touched.
- Mock: `mock/work-live.mjs` (F-87 added 4107 to 4111); this feature adds 4112 to 4115.
- Contract 1.24.0 bodies, re-checked:
  - Tracking read `GET /api/v1/work/{work_id}/tracking`: `can_record_delivery_observation` (boolean), `delivery_observation_url` (string or null), `uncertain_effects[]` of `{job_id, job_type}`, next to `facts` (`sent`, `receipt`, `verified`: boolean or null).
  - `POST {proofs_url}` body `{kind:'pdf_copy', upload_id (1..2^63-1), case_revision (1..2147483647)}`, `additionalProperties:false`; 201 `{evidence_id, kind, name, sha256, note, download_url}`. The `pmo_lead_note` kind exists and is not used.
  - `POST {delivery_observation_url}` body (all required, `additionalProperties:false`) `{expected_revision (1..2147483647), case_revision (1..2147483647), outcome:'delivered'|'not_delivered'|'unknown', effect:{job_id, job_type}, proof_id (1..2^63-1), reason (1..4000)}`; 201 `{id, effect, outcome, proof_id, reason, recorded_at}`. Errors 400, 401, 403 (incl. `csrf_failed`), 404, 409, 413, 415, 422, 429, 500, 503 with `{code, message, fields?}`. No key field exists. `GET` of the same path returns `{items[<=25]}` of the same record.

## Contract

### Command descriptor `work.observe`
Added to `workItemCommands(item)` (F-87) or a sibling export, using `makeCommand` with no key field.
| id | label | gate | url | body | success |
|---|---|---|---|---|---|
| `work.observe` | Record and continue | tracking `can_record_delivery_observation === true`, `delivery_observation_url` a non-empty same-origin path for this `work_id`, and at least one `uncertain_effects[]` | the URL as served | `{expected_revision, case_revision, outcome, effect:{job_id, job_type}, proof_id, reason}` | 201 |
- Tokens are copied from the item as loaded; a `null` stays `null`. `item.revision === null` or `item.case_revision === null` gives `disabledReason` "We don't have this item's current version yet. Reload and try again."; the button is drawn disabled with that text beside it and nothing is sent.
- `outcome` comes only from the radio the person chose; there is no default.
- The proof POST lives in a new `src/features/workspace/deliveryObservation.ts` (proof call, observation call, observations read). The observation send goes through `useWorkCommand`; neither the proof nor the observation sends from load, poll or navigation.

### The "Confirm what happened" panel
New `src/features/work-item/live/DeliveryObservationPanel.tsx`, rendered in `Overview` next to the controls row (desktop: the amber-bordered side panel headed CONFIRM WHAT HAPPENED; phone: the radios, then a "Record and continue" bar). It is not tied to a state name.
- Fields: three radios ("It arrived." / "It didn't arrive." / "I can't tell yet.") with plain sublines, a required "Reason" text box (1 to 4000 characters, counted, the box refuses more), the shared `EvidencePicker` for proof (always shown, for all three outcomes), and the button "Record and continue". Footer: "Your choice is recorded with your name."
- Sublines (D-187, accepted wording; the builder may adjust only the words, not the promises): "It arrived." - "The invoice reached the client."; "It didn't arrive." - "It did not reach the client."; "I can't tell yet." - "We could not find out." They name no resend, reminder or later step.
- Intro paragraph reads from tracking `facts` only: when `sent` is null or false and `receipt` is not true: "We could not confirm that this was delivered. Nothing is resent until a person confirms what happened." No count, checker name or time the API did not send.
- One effect: sent as served. More than one: one panel per effect in served order, headed by its `job_type` in plain words (the raw `job_id` is never shown); each records its own effect. The page never picks or composes an effect.
- Button disabled text beside it, in this order: "Choose what happened." (no outcome), "Write a reason." (empty reason), "Attach proof first." (no file chosen); then the version-missing reason when a revision is null.
- Calls on press: (1) if no proof is attached yet, `POST {proofs_url}` `{kind:'pdf_copy', upload_id, case_revision}` returns `evidence_id`; (2) `POST {delivery_observation_url}` with `proof_id = evidence_id`. The attached proof is kept for that panel: if step 2 fails, a retry sends only step 2, never a second proof.
- After 201: re-read the item and the tracking read. The panel shows "Recorded: {It arrived | It didn't arrive | We can't tell yet}, {recorded_at}." from the 201 body, with the state tag from the re-read; that effect's inputs are cleared and disabled. Recording does not change the state by itself. The person may then press "Check what happened" (F-87, when listed). If the re-read fails, say "Recorded. We couldn't reload the item; reload the page to see its state." and keep the button locked until a read succeeds.
- Errors: 403 non-csrf "You can't do this." plus the server message, re-read, no retry; 403 `csrf_failed` refreshes the session once and says "Press the button again", no second send; 409 re-reads item and tracking and shows the server message under "This changed while you were working. Showing the latest version."; 422 shows the server message and first `fields[].message` as given; 429 and 503 say "Try again shortly."; 404 and 401 as F-87 (page-level "This record is unavailable." and signed-out). Proof-step failures map the same way and leave no observation sent.
- Uncertain result (network, timeout, 5xx, dropped connection) on the observation POST: `GET {delivery_observation_url}`. If an item with this `effect`, `outcome`, `proof_id` and `reason` is listed, treat it as recorded. If it is not listed or the read fails, lock "Record and continue" for that panel, say "We couldn't confirm that this was recorded. Check the page before trying again.", and unlock only when the list or the item `revision` changes, or the page is reloaded. No automatic retry, no timer. An uncertain proof POST is read from `GET {proofs_url}` by `sha256`/`name` before any second proof is sent; if it cannot be settled the same lock applies.
- States: loading (tracking not read: no panel, no skeleton); empty (flag false, no effect or no URL: no panel, no heading, no gap); uploading ("Uploading proof..."); recording ("Working...", this panel and the controls row locked); error (Callout inside the panel); success (the Recorded line).

### Fixture examples (mock, `mock/work-live.mjs` and the mock server routes)
- `4112` uncertain delivery: `state:'awaiting_reconciliation'`, `actions:['reconcile']`, `revision:5`, `case_revision:9`, `tracking_url`, `proofs_url`. Tracking: `can_record_delivery_observation:true`, `delivery_observation_url:'/api/v1/work/4112/delivery-observations'`, `uncertain_effects:[{job_id:731, job_type:'invoice_delivery'}]`, `facts.sent:null`, `facts.receipt:null`. Proof POST 201 `{evidence_id:55, kind:'pdf_copy', name:'receipt.pdf', sha256:'...', note:null, download_url:'...'}`; observation POST 201 `{id:1, effect, outcome, proof_id:55, reason, recorded_at}`; observations GET `{items:[...]}`.
- `4113` two effects (jobs 731 and 732); `4114` flag false (no panel); `4115` as `4112` with `case_revision:null`.
- Scenarios for the proof POST, observation POST and observations GET, using F-85's scenario mechanism: 403 `forbidden`, 403 `csrf_failed`, 409 `stale_version` (then the item GET returns a higher revision), 422 `setup_required`, 429, 503, 500, a dropped connection, and "dropped connection but the list holds it" versus "dropped connection and the list is empty".

### Idempotency and versioning
`expected_revision` is the item's `revision` as loaded, and `case_revision` as loaded, each sent as given and never defaulted, bumped or 0. The observation body has no key; duplicates are prevented by the press lock, the uncertain lock and the revision check. After every success the item and tracking read are re-read.

### Permission and tenant rules
Whether a person may record is the server's answer: the panel is shown only on the served flag and a 403 or 409 is shown as given. The client has no role check and names no role or authority. Every call uses the loaded item's `work_id`; the proofs and observation URLs are used only if they are same-origin paths for that `work_id`, otherwise the panel is not drawn. A 404 gives "This record is unavailable."

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/work-item/live/DeliveryObservationPanel.tsx` and its mount in `LiveWorkItemView.tsx`, `frontend/src/features/workspace/deliveryObservation.ts`, the `work.observe` descriptor in `workspace/workItemCommands.ts`, `frontend/mock/work-live.mjs` and the mock routes, panel and descriptor tests under `frontend/src/**`, and the cases for 4112 to 4115 in `frontend/e2e/work-item-controls.spec.ts`.
- Backend lane: none. No backend, contract or migration change.
- Integration owner: lane C coordinator; runs the live check (criterion 12) against Django 8020. Shared files: `src/features/workspace/useWorkCommand.ts`, `adapter.ts` and the shared locking are owned by F-87 and used as is (only an additive change if the observation needs one, agreed with the coordinator); `EvidencePicker`, `uploadCaseFile` and the tracking hook belong to F-85 and are used as is; `src/api/*` and `src/components/*` are shared and unedited; `src/features/response/*` is not touched.
- Build order: F-85, then F-87, then F-93. Ports: Next 4980, mock 4981, Django 8020.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4112` (mock) shows the CONFIRM WHAT HAPPENED panel with three radios (none selected), a Reason box, the proof picker and "Record and continue" disabled; `/work/4114` (flag false) and `/work/4107` show no panel, no heading and no gap — verify: e2e in `frontend/e2e/work-item-controls.spec.ts` by role and name; on `/work/4107` the DOM has no radio or file input.
2. "Record and continue" stays disabled with "Choose what happened.", "Write a reason." or "Attach proof first." until each is done, and a 4001-character reason is refused in the box — verify: unit test of the panel and e2e.
3. With "It didn't arrive", a reason and a PDF, one press sends `POST /api/v1/work/4112/proofs` `{"kind":"pdf_copy","upload_id":<id>,"case_revision":9}` then one `POST /api/v1/work/4112/delivery-observations` `{"expected_revision":5,"case_revision":9,"outcome":"not_delivered","effect":{"job_id":731,"job_type":"invoice_delivery"},"proof_id":55,"reason":"..."}`; the page then shows "Recorded: It didn't arrive, ..." — verify: e2e captures both bodies in order; unit test on the descriptor body.
4. The page claims no resend, reminder, verification or approval anywhere in or beside the panel, and the sublines and footer match the contract above — verify: e2e text search of the page for "resend", "remind", "verif"; the footer reads "Your choice is recorded with your name."
5. If the observation POST fails after the proof was attached (422 or 409), a retry sends only the observation and no second proof — verify: unit test counts proof and observation POSTs.
6. A 403 shows "You can't do this." with the server message; a 409 re-reads item and tracking and shows the server message; a 422 shows the server message and first field message; a 403 `csrf_failed` refreshes the session once, says "Press the button again" and sends nothing more; 429 and 503 say "Try again shortly." and send nothing by themselves — verify: e2e scenarios; unit test counts POSTs and session calls over 30 s of fake time.
7. After a dropped connection or 500 on the observation POST, the page reads the observations list: when the list holds the same effect, outcome, proof and reason it shows Recorded; when not, or when the read fails, it shows "We couldn't confirm that this was recorded. Check the page before trying again.", disables the button, and sends nothing by itself for 60 s of fake time; it unlocks only when the list or the item `revision` changes or the page is reloaded — verify: unit test with both list answers and a failing list.
8. After a dropped connection on the proof POST, no second proof is sent until the proofs list is read and does not hold that file — verify: unit test counts proof POSTs.
9. `/work/4115` (null `case_revision`) draws the panel with "Record and continue" disabled and the version-missing reason beside it; no body holds null or 0 for a revision; the same for a null `revision` — verify: e2e and unit test.
10. `/work/4113` draws one panel per uncertain effect, each recording its own effect, and the raw job id is not shown — verify: e2e with request capture for each panel.
11. The page never sends an observation or proof on load, poll or navigation and never sends `outcome` from a default; the lookup button and the panel are independent (pressing one sends nothing for the other); a double press sends one request — verify: e2e asserts zero POSTs on load and after each single press; `grep -rn "liveApi.POST" frontend/src/features/work-item frontend/src/features/workspace` shows the new calls only in `useWorkCommand` and `deliveryObservation.ts`.
12. Against live Django (8020, Postgres 55433, account live-lead), on an item whose tracking read has `can_record_delivery_observation: true`, one observation recorded with proof returns 201 and `GET .../delivery-observations` lists it; a person without recovery authority sees no panel or gets the server's 403 shown as given; a wrong-tenant or unknown id shows "This record is unavailable." — verify: record the JSON of each with `oa.py live`. If no such item exists locally, say so in build.md as unproved rather than assumed.
13. Viewport check at 1440 and 390: the panel has no overlap, the radios, Reason and button fit on the phone, no empty gap when absent — verify: screenshots against the SCR-02 awaiting-reconciliation artboards.
14. F-87 behaviour is unchanged: its controls, locking and `useWorkspaceStep` tests pass without edits, and `/work/W-xxxx` pages behave as before — verify: `npm test`, `frontend/e2e/workspace.spec.ts`, `work-item.spec.ts`.
15. Unit tests exist for `work.observe` (gate, url, body, null-token hold) and the panel (criteria 2, 5, 7, 8) — verify: `npm test` lists them; `api-live-schema-drift.test.ts` still passes (`delivery/checks.sh`).

## Out of scope
- Everything in F-87 (lookup, resume, cancel, background controls) and F-90 (release invoice); changes to `useWorkCommand`'s behaviour.
- The `pmo_lead_note` proof kind, a history list of past observations, "checked N times", the checker's name, "Sent at" and "next check at" (no source).
- Any resend after "It didn't arrive" or reminder after "I can't tell yet" (the backend does neither).
- Any client rule about who may record or which state allows it; any role name on the page.
- Any backend, migration or contract change; the v7 `ReconcilePanel` and `W-xxxx` pages.

## Assumptions
- No key field exists on the proof or observation bodies (`additionalProperties:false`), so duplicates are prevented by locks, the revision check and reading the list, not a key. Reason: contract 1.24.0.
- Gate is the tracking flag, a same-origin URL and at least one effect, not the state name. Reason: A-13; the flag is the only served answer on recovery authority.
- Proof is a PDF through `EvidencePicker` only. Reason: the board draws only an upload and the contract needs `proof_id` for all three outcomes.
- One panel per uncertain effect. Reason: the schema allows an array; picking one would hide an effect (LC-Q23).
- The exact subline words are mine, within D-187's "plain sublines that promise nothing the backend does not do". Reason: the answer fixed the rule, not the words.
- Uncertain proof upload is settled from `GET {proofs_url}`. Reason: the proof POST also has no key; reading the list is the only served proof of a recording.
- "Different `revision` or changed list" is what unlocks after an uncertain observation. Reason: no reconcile token is served.
- The Recorded line and the disabled-reason texts are mine. Reason: no board draws them (LC-Q23).

## Conflicts with the boards
LC-Q19 (accepted under D-187) covers the sublines, the Reason box, always-shown proof and the footer. New item LC-Q23 is in `delivery/connect/questions-batch.md` under "## Lane C".
1. Sublines, Reason box, proof for every outcome, footer: recommended and accepted (LC-Q19, D-187). The board's first paragraph numbers ("checked 6 times over 2 hours", "No receipt found after 6 checks") and "Chidi" have no source and are replaced by the facts-only paragraph.
2. The board draws one panel; more than one uncertain effect gives one per effect, the "Recorded: ..." line replaces the inputs after success, and the disabled reasons sit beside the button (LC-Q23). Recommendation: keep.
3. The lookup button lives in F-87's controls row, not on the board (LC-Q12, unchanged).
