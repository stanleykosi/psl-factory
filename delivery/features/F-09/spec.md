# Record a client response or SOW signature with proof, and confirm what happened to an uncertain send

> Tasks: FE-M2B-RESPONSE (R-RESPONSE, R-EXCEPTION). Architecture: package v7 (proposal, commit 61a7ade), manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624` (`architecture/packages/v7/manifest.sha256`). D-RESPONSE-VIEW r2 and D-WORK-ACTIONS-VIEW r2 are `proposed` and are used only under the design engineer's recorded exception (`architecture/sources/decisions-2026-11-14-v2.md` (f)(g), `decisions-2026-11-15.md` (h)(i)): contract mock only, the backend developer may change or refuse any field, nothing is released. Design: approved canvas version 1794581312-b166 (`design/review.json`, `design_sha256` 9fad8d2d…); screens: SCR-16 (default, validation, success, sow-signed) and SCR-02 (awaiting-reconciliation panel; waiting entry button only). Artboards (`design/canvas/project/`): SCR-16-desktop, SCR-16-mobile, SCR-16-desktop-validation, SCR-16-mobile-validation, SCR-16-desktop-success, SCR-16-mobile-success, SCR-16-desktop-sow-signed, SCR-16-mobile-sow-signed, SCR-02-desktop-awaiting-reconciliation, SCR-02-mobile-awaiting-reconciliation, SCR-02-desktop-waiting and SCR-02-mobile-waiting (button only).

## Summary
- On `/work/<id>/respond?task=<task id>` a PM records what an outside party did: who responded, when, what they did, which version, and the proof file. They tick that it is genuine and press Record. Every option on the form comes from `tasks[].response`. The page offers nothing the API did not return and works nothing out from `/me` roles.
- The proof is uploaded first, through E-EVIDENCE-UPLOAD. The case revision returned by the last upload goes on E-RESPONSE. When `claim_required` is true, E-TASK-CLAIM runs first. E-RESPONSE is sent once per press. An uncertain result is never resent: the page re-reads the item and, if the task is already recorded, shows the recorded state.
- The success view is filled from the E-RESPONSE 200 (`recorded`, `next`) and shows only the fields that came back. The SOW signature variant uses the same flow with its own board layout.
- On a work item awaiting reconciliation, a person whose `allowed_actions` includes `reconcile` sees "Confirm what happened" with the API's outcomes. "It arrived" needs a proof upload. The answer goes through E-WORK-ACTION. The frontend never resends anything.
- A new `frontend/mock/response.mjs` validates against v7, and the v7-shaped fixtures W-1601 to W-1610 live under `fixtures/response/work/`. The base's v4 checks run unchanged.

## Context
- **Base:** branch `dlv-00-delivery-setup` at 1827260. F-01 (frame), F-02 (My work), F-03 (work item) and F-04 (decide) are merged. F-06, F-07, F-08, F-12 and F-13 are not merged.
- **App frame:**
  - `frontend/src/shell/FrameStates.tsx` exports `LoadingState` and `SignedOutState({pathname})`.
  - `frontend/src/shell/icons.tsx` exports `WarningIcon`.
  - The shell sets CSRF through `setCsrfToken`.
- **API client:**
  - `frontend/src/api/client.ts:29` exports `api`, typed on the v4 `paths` (`src/api/schema.d.ts`), and `call()` at :39. Its middleware adds `X-CSRFToken` to every POST.
  - `frontend/src/api/errors.ts` maps 401/403/404/409/422 to `ApiError.kind` unauthenticated, forbidden, not_found, stale and invalid. 5xx is server and a failed fetch is network.
  - The paths `/api/v1/cases/{case_id}/evidence`, `/api/v1/tasks/{task_id}/response`, `/api/v1/work/{work_id}/actions` and `/api/v1/tasks/{task_id}/claim` all exist in v4, so `api.POST` can reach them. Only the v7 body and response shapes are missing from the v4 types.
- **Work item (F-03):**
  - `frontend/src/features/work-item/WorkItemView.tsx` loads the item with `useWorkItem` (`useWorkItem.ts`) and renders `WorkItemOverview`.
  - `WorkItemOverview.tsx:147-162` `TaskPanels` shows "Only a {role} can decide." and links "Open the decision" for every task with `you_can_act`.
  - `WorkItemOverview.tsx:179-189` has the `.work-columns` row: the left column (AgentCard, NextStep at :182) and the tasks column, which renders only when `tasks.length > 0`.
  - `WorkItemStates.tsx` exports `NoAccessState` and `WorkErrorCard`. `labels.ts` exports `WorkItem` (v4), `currentStationIndex` and `formatWat`.
- **Decide (F-04), as a pattern to copy, not to edit:**
  - `frontend/src/app/work/[id]/decide/page.tsx` sets a page title that never names the item.
  - `frontend/src/features/decide/format.ts` has `NOTE_MAX`, `formatClock` and `AGENT_NAMES`.
  - Its uncertain-effect notices are in `DecideView.tsx:21-45`.
- **Mock (`frontend/mock/server.mjs`):**
  - `OPENAPI_PATH` is v4 (:22), and `M1_OPERATIONS` is at :24.
  - `readWorkFixtures` (:49) reads only `fixtures/work/`.
  - The `overrides` Map is at :199, and `POST /__mock/reset` (:208) clears it.
  - Any operation not in `M1_OPERATIONS` gets 501 at :215. This happens before the scenario check (:219) and the CSRF check (:223).
  - `findTask` (:107) looks through the default item, the `work` map and the overrides. F-04's claim handler is `taskResponse` (:118).
  - Personas (`me.*.json`): `pm` is Tunde Bello, roles PM, csrf `mock-csrf-pm`. `finance_lead` is Ada Okafor, csrf `mock-csrf-finance_lead`. `none` has no destinations.
- **v4 checks that must keep passing untouched:**
  - `tests/mock-contract.test.ts:69-86` calls every `M1_OPERATIONS` entry with `{}`.
  - `tests/mock-contract.test.ts:219-235` validates every `fixtures/work/W-<digits>.json` against v4.
  - Also `tests/api-schema-drift.test.ts` and `tests/mock-decide.test.ts`.
- **Assets and styles:**
  - The avatars are `frontend/public/agents/tola.png`, `chidi.png` and `zainab.png` (PR #12).
  - `frontend/src/styles/psl-bundle.css` has `psl-field`, `psl-label`, `psl-hint`, `psl-select`, `psl-input`, `psl-input--area`, `psl-radio`, `psl-choice`, `psl-seg`/`psl-seg__opt`, `psl-check`, `psl-drop`, `psl-file`/`psl-file__name`, `psl-btn` and its variants, `psl-actionbar`, `psl-callout--info|warning|problem|success`, `psl-crumb`, `psl-panel` and `psl-panel__head`, `psl-mono` and `psl-empty`. Do not edit `tokens.css` or `psl-bundle.css` (`tests/styles-drift.test.ts`).
- **What does not exist yet:**
  - `frontend/src/app/work/[id]/respond/`, `frontend/src/features/response/`, `frontend/mock/response.mjs` and `frontend/mock/fixtures/response/`.
  - No `/projects/[id]` route.

## Contract

### Local v7 types and the one adapter (PMO-0-2)
- `frontend/src/features/response/contract.ts` declares the v7 shapes once, mirroring `architecture/packages/v7/openapi.json`:
  - `TaskResponse` (`tasks[].response`, openapi.json:1300-1593);
  - `Reconcile` (openapi.json:1780-1830);
  - `ResponseWorkItem` (v4 `WorkItem` plus optional `case_id`, `case_revision`, `allowed_actions`, `reconcile`, and `tasks[].response`);
  - `EvidenceUploadBody/Result`;
  - `ResponseBody/Result` (E-RESPONSE, openapi.json:4623-4984);
  - `WorkActionBody/Result` (E-WORK-ACTION).

  Every r2 field is optional.
- `frontend/src/features/response/api.ts` is the only module that calls the API for this feature. It exports `getWorkItem`, `uploadEvidence`, `claimTask`, `recordResponse`, `workAction`, and `asResponseItem(item: WorkItem): ResponseWorkItem`. Each call goes through `api.POST/GET` and `call()`, so CSRF and `ApiError` come from the existing client. Exactly one commented widening cast sits at this boundary. No cast appears anywhere else in the feature (verified by grep).
- `frontend/src/features/response/index.ts` exports `ProofField`, `useEvidenceUpload`, `ReconcilePanel`, `responseOf(task)` and `RESPONSE_LABELS` (for FE-M2A-PROOF and the two F-03 edits).
- build.md lists the cast and the v7 constant in `mock/response.mjs`. Whichever of F-09 and F-13 rebases second removes both.

### GET /api/v1/work/{work_id} (E-WORK-ITEM, read)
- **Used:**
  - `line`, `reference`, `revision`, `stations`, `case_id?` and `case_revision?`;
  - `allowed_actions?` and `reconcile?`;
  - the task whose `id` equals `?task=`, with `title`, `you_can_act`, `revision` and `response?`.
- **`response`:**
  - `variant`;
  - `responders[{id,name,role?,organisation?}]` and `actions[{value,label?}]`, both required;
  - `versions?[{id,label,note?,sent_at?}]`;
  - `evidence_kind?` and `claim_required?`;
  - r2: `intro?`, `proof_hint?`, `agent_note?{agent,lines[]}`, `channels?[{value,label}]`, `context?{project?{case_id,title}, document?{reference,label?,document_id?}}`, `next?[]` and `recorded?{by{name,role?,is_you?}, at, responded_at?, received_via?, proof_count?, summary?}`.
- **Errors (page load):**
  - 401 → `SignedOutState` with pathname `/work/<id>/respond?task=<task>`.
  - 403 or 404 → `NoAccessState`.
  - Network or 5xx → `WorkErrorCard` with "We couldn't load this response form. Your work is safe; nothing was changed." and Try again.
- **Permission:** the only switches are `you_can_act`, the presence of `response`, and `allowed_actions`. Feature code never reads `useMe().roles` or `destinations`.

### POST /api/v1/cases/{case_id}/evidence (E-EVIDENCE-UPLOAD)
- **When:** the moment a file is chosen. Each file is one upload. An upload never runs on its own retry.
- **Request:**

  ```json
  {"kind": "<response.evidence_kind | reconcile.evidence_kind>", "filename": "<file name>", "content_base64": "<FileReader result without the data: prefix>", "case_revision": <current>}
  ```

  - `case_revision` is the item's `case_revision` for the first upload. After that it is the `case_revision` returned by the previous upload, or the item's when none was returned.
  - CSRF comes from the client.
- **200:** `{evidence_id, sha256, case_revision?}`. The file chip shows the file name and size (for example "Lagoon_UAT_signoff_11Nov.pdf · 184 KB") and a remove button labelled "Remove <file name>". Removing a file only drops it from what is sent. The proof stays on the case, because evidence is append-only.
- **Errors:**
  - 401 → `SignedOutState`.
  - 403 → a problem line on that chip: "You can't add proof to this item."
  - 404 → `NoAccessState`.
  - 409 → reload the item to get the current `case_revision`, and mark the chip "This item changed. Add the file again." The file is not re-sent automatically.
  - 422 → the server `message` on the chip.
  - Network or 5xx → "Couldn't upload. Try again." with a Try again button. The button first reloads the item and then uploads with the current `case_revision`. It is never pressed for the user.
- **No upload possible:** when `case_id`, `case_revision` or the `evidence_kind` is absent, the proof control is disabled with the hint "Proof can't be uploaded for this item." Record or Record and continue stays disabled for any choice that needs proof.

### POST /api/v1/tasks/{task_id}/claim (E-TASK-CLAIM)
- **When:** only when `response.claim_required` is true. It runs at the Record press, immediately before E-RESPONSE, with `{expected_revision: task.revision}`.
- **200:** `{revision}` becomes the E-RESPONSE `expected_revision`.
- **Errors:**
  - 409 → the stale flow.
  - 403 → the 403 flow below.
  - Network or 5xx → an inline warning "We couldn't get this ready. Try again." with E-RESPONSE not sent. A claim records nothing, so Try again may claim again.
- When `claim_required` is false or absent, no claim is sent.

### POST /api/v1/tasks/{task_id}/response (E-RESPONSE)
- **Request** (keys absent when there is no value; never `team`, `estimate_person_days` or `what`):

  ```json
  {"expected_revision": <task.revision, or the claim's revision>, "who": "<responders[].id>", "action": "<actions[].value>",
   "responded_at": "<ISO with +01:00, from the WAT time entered>", "evidence_id": "<first proof>", "evidence_ids": ["<2nd>", "..."],
   "attested": true, "case_revision": <last upload's case_revision>, "version_id": "<versions[].id>",
   "received_via": "<channels[].value>", "note": "<trimmed, 1-2000 chars>"}
  ```

  - `evidence_ids` is sent only with two or more files.
  - `version_id` is sent when `versions` is non-empty.
  - `received_via` is sent when `channels` is non-empty.
  - `note` is sent only when it is non-blank.
- **Client rules.** Record stays disabled, and no request goes out, until all of these hold:
  - a responder is chosen;
  - an action is chosen;
  - a response time is entered;
  - a version is chosen, when `versions` is non-empty;
  - a channel is chosen, when `channels` has more than one entry;
  - at least one proof has uploaded;
  - the attestation is ticked;
  - the note is 2000 characters or fewer.
- **The `role="alert"` line beside the disabled button:**
  - When only proof or attestation is missing: the board line "Add the proof and confirm it's genuine to record this."
  - When other fields are missing: "Choose who responded, when, what they did and which version to record this." Leave out any part whose field is already filled or not offered.
- **One write at a time:**
  - While claim or E-RESPONSE is in flight, Record is disabled and reads "Recording…", and the form has `aria-busy="true"`.
  - A second press sends nothing.
  - Nothing retries automatically.
- **200:** `{task_id, work_state, revision?, recorded?, next?}` → the success view. Then reload E-WORK-ITEM once. When the 200 has no `recorded`, the reloaded `task.response.recorded` is used.
- **Errors (all through `ApiError.kind`):**
  - 401 → `SignedOutState`.
  - 404 → `NoAccessState`.
  - 403 → reload the item. If the task is no longer actionable, show the not-open state. Otherwise show a problem callout with the server message and keep the controls.
  - 409 (stale):
    - Everything entered is kept, including uploaded proof.
    - The item is reloaded, and a warning shows: "This changed while you were recording. We've reloaded it. Check the details and record again."
    - Choices that the reloaded task no longer offers are cleared.
    - Nothing is resent.
    - If the reloaded task already has `recorded`, the success view is shown.
  - 422 → a problem callout above Record with the server `message`. Entries are kept and nothing is resent.
  - Network or 5xx is an **uncertain effect**:
    - Show "We couldn't confirm your response was recorded. We've reloaded this item so you can see whether it was."
    - Reload once, without resending.
    - If the reloaded task has `response.recorded`, or is gone from `tasks`, show the success view from `recorded`, or the not-open state when there is none.
    - Otherwise Record comes back for a deliberate new press.
    - If the reload also fails, the warning reads "We couldn't confirm whether your response was recorded, and couldn't reload to check. Record stays off. Try again reloads the item; it doesn't send your response again." Try again only reads.
- **Idempotency/versioning:** E-RESPONSE has no idempotency key (INV-REVISION, INV-AUDIT). The guards are the in-flight lock, `expected_revision` and re-read-before-resend.

### POST /api/v1/work/{work_id}/actions (E-WORK-ACTION, reconcile only)
- **Request:** `{"expected_revision": item.revision, "action": "reconcile", "outcome": "<reconcile.outcomes[]>", "evidence_id"?: "<proof>", "case_revision"?: <upload's>}`.
  - `evidence_id` and `case_revision` are sent only for `delivered`.
  - `resume` and `cancel` are never sent.
- **200:** `{work_id, state, revision}` → reload the page (the panel calls `reloadPage()` from `features/response`, which wraps `window.location.reload()` so tests can stub it). The panel shows "Recorded. Reloading the work item…" while the page reloads.
- **Errors:**
  - 401 → `SignedOutState` (pathname `/work/<id>`) in place of the panel.
  - 403, 422 → a problem callout in the panel with the server message.
  - 404 → `NoAccessState`.
  - 409 → a warning "This item changed. Reload it to see the latest." with a "Reload the work item" button.
  - Network or 5xx → a warning "We couldn't confirm your answer. Reload the work item to see whether it was recorded." with the same button. Nothing is resent.
- The panel's button follows the same one-write-at-a-time rule ("Recording…").

### Screen states — SCR-16 (`/work/[id]/respond`)
- The page is `frontend/src/app/work/[id]/respond/page.tsx`, a server page that reads `params` and `?task=` the same way `decide/page.tsx` does. Its metadata title is "Record a response · PSL Factory".
- No SAMPLE DATA tag is shown.
- All times are in Africa/Lagos (WAT) inside `<time dateTime>`.

1. **Loading:** `LoadingState`.
2. **Not open:** `psl-empty` with h2 "This response isn't open here", the text "It may have been recorded already or moved. The work item shows where things stand." and the link "Open the work item" (`/work/<id>`). It is shown when any of these is true:
   - `?task=` is missing or unknown;
   - the task has no `response`;
   - `you_can_act` is false and there is no `recorded`;
   - `variant` is not `client_response` or `sow_signature`.

   A task that carries `recorded` shows the success view instead.
3. **Default, `client_response`** (SCR-16-desktop, in board order):
   - **Crumb** (mono, `psl-crumb`): "QUEUE" (link `/my-work`) / `line` upper-cased / `reference` · "STATION n OF m". n is `currentStationIndex(stations)+1` and m is `stations.length`. When there is no current station, the station part is left out.
   - **When `context.project` is present**, the crumb is instead "PROJECTS" (link `/projects`) / `context.project.title` upper-cased (text, since no project route exists) / "DOCUMENTS" / `context.document.reference`. The last two parts appear only when `context.document` is present.
   - **h1:** `task.title`. **Intro:** `intro` under the h1.
   - **Form** (white panel, 2px ink border):
     - A two-column row:
       - "Who responded": a select of `responders`, with option text "<role> · <name>, <organisation>" (parts left out when absent).
       - "When they responded": `datetime-local`, read as WAT.
     - When `channels` has two or more entries, a third select "How they responded" sits in that row, with options in API order. A single channel is sent without a control.
     - With exactly one responder, version or channel, that option is selected. With more than one, the select starts on "Choose…".
     - "What they did": radio pills (native radios) with the `actions` labels, in API order. None is preselected. `label` is required for display. An action without a `label` is not offered.
     - "For which version": a select of `versions` with "<label> (<note>)". It is left out when `versions` is empty or absent.
     - "Note (optional)": a textarea with `maxLength` 2000 and the counter "n / 2000".
     - "Proof": the dashed `psl-drop` area holding the file chips, "Add another file" (a file input styled as the board's button) and `proof_hint` as the hint. With no file yet, the area shows "No proof added yet" plus the same button (SCR-16-desktop-validation).
     - Checkbox: "I confirm this response is genuine and came from the client contact named above."
     - "Record response" (primary blue) and the line "Recorded with your name and the time. It can't be edited later, only corrected by a new record."
   - **Aside** (blue info panel, right, max 380px), only when `agent_note` is present:
     - the avatar `<img src="/agents/<agent>.png" alt="">` (36px circle);
     - "<Tola|Chidi|Zainab> · <PMO agent|Finance agent|HR agent>";
     - each of `lines` as a paragraph.
4. **Validation** (SCR-16-desktop-validation): the same layout. Record is `disabled`, with the alert line before it as in the client rules.
5. **Default, `sow_signature`** (SCR-16-desktop-sow-signed):
   - The project crumb.
   - **h1** `task.title`.
   - **Panel** headed "Signature":
     - "Document": `versions[0].label` · "sent <d MMM HH:mm>" from `sent_at`, with `note` under it. When there are two or more versions, a select is used instead.
     - "Who signed": "<name> · <role>, <organisation>". When there are two or more responders, a select is used instead.
     - "When": `datetime-local`.
     - "What they did": a segmented radio group (`psl-seg`, native radios) with the `actions` labels.
     - "Proof": an uploaded-file card showing the name and "Uploaded · <size>". With no file, a "Choose the signed copy" file button.
     - The note field and the attestation checkbox, the same as in the client_response form.
     - "**What happens next:** " followed by `next` joined with a space. It is left out when `next` is absent.
     - "Record signature".
   - **Aside:** an info callout holding `intro`. It is left out when `intro` is absent.
6. **Phone (below 720px; SCR-16-mobile, -mobile-validation, -mobile-sow-signed):**
   - A back link under the shell bar (D-08):
     - client_response: "← Queue" to `/my-work`;
     - sow_signature: "← <context.document.label>" to `/work/<id>`, with `context.document.reference` on the right.
   - **h1:**
     - client_response: `task.title`;
     - sow_signature: the current station's name (for example "SOW signature").
   - **client_response:**
     - one summary line "<organisation> · <version label> · <responder name>" replaces the Who and Version selects when each has exactly one option (otherwise the selects show);
     - "When they responded" stays;
     - then the action pills;
     - Proof: "Take a photo or choose a file" (a file input with no `capture`) before any file, then the chips;
     - the note;
     - the short attestation "I confirm this response is genuine.";
     - the alert line.
   - `intro`, `proof_hint` and the aside are not shown on the phone.
   - **sow_signature:** the same rows as on desktop, without the aside.
   - Record sits in a `psl-actionbar` pinned to the bottom, at least 44px tall, and `scrollWidth` is at most 390.
7. **Success** (SCR-16-desktop-success and -mobile-success; `recorded` from the 200, else from the reloaded task):
   - **Eyebrow:** `reference` · the chosen responder's `organisation`, upper-cased. The second part is left out when absent.
   - **h1:** the name of the station that was current before recording (for example "Client UAT response").
   - **Success callout (`role="status"`):**
     - "**Response recorded.**" followed by `summary`;
     - ", received by <channel label, lower-cased> on <d MMM of responded_at>" when present;
     - ", recorded by <by.name> at <HH:mm of at>";
     - " with <n> proof file(s)" when `proof_count` is present, then ".".
     - Without `summary`, the sentence after the bold part starts "Recorded by …".
   - **"What happens next"**, then each `next` line on its own line. The block is left out when `next` is absent or empty.
   - The fixed line "Recorded responses can't be edited. If something is wrong, record a correction; both stay in the history."
   - **Desktop:** "Back to the work item" (`/work/<id>`).
   - **Phone:** "← Work item" with `reference` at the top, and "Back to my queue" (`/my-work`) at the bottom.
   - There are no form controls.

### Screen states — SCR-02 entry and reconcile (F-03 edits)
- **Entry (SCR-02-desktop-waiting, -mobile-waiting).** In `TaskPanels`, a task where `responseOf(task)` is present and `you_can_act` is true gets the link (`psl-btn`, primary) to `/work/<id>/respond?task=<task id>` in place of "Open the decision". Its text is `RESPONSE_LABELS.entry[variant]`:
  - `client_response` → "Record the client's response";
  - `sow_signature` → "Record the client's signature".

  The rest of the panel is unchanged. `NextStep` is untouched.
- **Reconcile panel (SCR-02-desktop/-mobile-awaiting-reconciliation).** It is shown only when `reconcile` is present **and** `allowed_actions` includes `"reconcile"`. Otherwise nothing renders, and no request is ever sent. It is mounted once, inside `.work-columns` after the left column (beside :182), in its own `work-column`. This makes it the right-hand aside at 1440px and places it below at 390px.
  - **Desktop head:** "Confirm what happened".
  - **Desktop body:** "<Agent> checked <count> times over <duration> and found no delivery receipt. The factory won't resend until a person confirms what happened, so the client is never invoiced twice."
    - `<duration>` comes from `first_at` to `last_at`: "N minutes" under an hour, otherwise "N hour(s)", rounded down.
    - When `checks.agent` is absent, the sentence starts "The factory checked". When the times are absent, " over …" is left out.
    - When `checks` itself is absent, only the second sentence shows.
  - **Phone:** a warning callout instead: "No receipt found after <count> checks. Confirm what happened before anything is resent." Without `checks` it reads "Confirm what happened before anything is resent."
  - **Options:** one native radio per entry of `outcomes`, in API order:
    - `delivered` → "**It arrived.** I have proof the client received it (upload it next)."
    - `not_delivered` → "**It didn't arrive.**" + " Allow <resend>." when `resend` is present.
    - `unknown` → "**I can't tell yet.**" + " <unknown_note>." when present.
    - A final "." is added only if the field has no closing punctuation.
  - **Proof for "It arrived":** choosing it shows a `ProofField` with `kind` = `reconcile.evidence_kind`. "Record and continue" stays disabled until it has uploaded.
  - **Button and footer:** "Record and continue" (primary). Then "Your choice is recorded with your name." + " " + `resend_note` (when present, with a "." added if needed).

### Mock behaviour (PMO-0-1)
- **`frontend/mock/response.mjs`** exports:
  - `RESPONSE_OPENAPI_PATH` (the single v7 constant, `architecture/packages/v7/openapi.json`);
  - `RESPONSE_OPERATIONS = ['E-EVIDENCE-UPLOAD', 'E-RESPONSE', 'E-WORK-ACTION']`;
  - `responseRoute(...)`;
  - `resetResponses()`.

  It compiles its request and response validators once from the v7 file with `ajv/dist/2020` + `ajv-formats` (no new package), and validates every reply before sending it.
- **Checks for each of the three operations, in this order:**
  1. **Scenario:** `X-Mock-Scenario` or `psl_mock_scenario` with a declared status gets `SCENARIO_BODIES[status]` (imported from server.mjs). The F-09-only value `record-then-fail` makes E-RESPONSE and E-WORK-ACTION apply their success effect and then answer 502 `{code:"mock_lost", message:"The mock dropped this reply."}`. It exists to exercise uncertain effects.
  2. **CSRF:** the persona's `csrf_token`, else 403 `csrf_failed`.
  3. **Persona `none`:** 403 `forbidden`.
  4. **Find the record:**
     - E-EVIDENCE-UPLOAD: the served item whose `case_id` matches.
     - E-RESPONSE: the task, via `findTask`-equivalent lookup over default, `work` and overrides.
     - E-WORK-ACTION: the served item.
     - Not found → 404.
  5. **Body:** JSON parse, then the v7 request schema → 422 "Check these fields: <names>." (the same format as F-04).
  6. **Rules:**
     - **Upload:**
       - `kind` must equal that item's response `evidence_kind` or `reconcile.evidence_kind`;
       - `content_base64` must decode to at least one byte.
     - **E-RESPONSE:**
       - `attested` must be `true`;
       - `evidence_id` and every `evidence_ids` entry must be ones this mock issued for that case;
       - `who` must be in `responders`, `action` in `actions`, `version_id` in `versions` (when versions exist) and `received_via` in `channels` (when channels exist);
       - `note` must be 2000 characters or fewer;
       - any failure → 422 naming the field.
     - **E-WORK-ACTION:**
       - `action` `resume` or `cancel` → 501 `not_mocked`;
       - `outcome` must be present and in `reconcile.outcomes`;
       - `delivered` needs a known `evidence_id`;
       - any failure → 422 naming the field.
  7. **Revision:**
     - `expected_revision` must equal the task's revision (E-RESPONSE) or the item's revision (E-WORK-ACTION);
     - `case_revision`, when sent, must equal the mock's current case revision.
     - Otherwise → 409 `stale_revision`.
  8. **Grant:**
     - E-RESPONSE needs a task with `you_can_act: true`.
     - E-WORK-ACTION needs `allowed_actions` to include the action.
     - E-EVIDENCE-UPLOAD needs a response task with `you_can_act` or a `reconcile` grant on that item.
     - Otherwise → 403.
  9. **Success:**
     - **Upload:** 200 `{evidence_id:"EV-<case>-<n>", sha256:<hex of the decoded bytes>, case_revision:<current+1>}`. It stores the evidence and the new case revision in memory.
     - **E-RESPONSE:**
       - The served item becomes `fixtures/response/<work_id>.recorded.json` with `tasks[i].response.recorded` set to `{by:{name:me.name, role:me.roles[0], is_you:true}, at:<now>, responded_at, received_via?, proof_count:<1+evidence_ids.length>, summary:<sidecar's summary>}`. This goes through the existing `overrides` Map.
       - It answers 200 `{task_id, work_state:<sidecar state>, revision:<sidecar task revision>, recorded:<same>, next:<sidecar response.next>}`.
       - Without a sidecar it answers 501 `not_mocked`.
     - **E-WORK-ACTION:** the item becomes `fixtures/response/<work_id>.<outcome>.json` through `overrides`, and it answers 200 `{work_id, state, revision}`. Nothing is sent to anyone.
- **E-TASK-CLAIM** stays F-04's handler. It finds W-16xx tasks because their bodies are in the `work` map.
- **Additive `server.mjs` edits only** (listed in build.md):
  - (a) `readWorkFixtures` also reads `fixtures/response/work/*.json` into the same `work` map;
  - (b) one line before the 501 check at :215 routes `RESPONSE_OPERATIONS` to `responseRoute`, passing the request, url, raw body, cookies, personas, `work` and `overrides`;
  - (c) `/__mock/reset` also calls `resetResponses()`.

  No `M1_OPERATIONS` entry. `OPENAPI_PATH` is unchanged.
- **Fixtures** (`frontend/mock/fixtures/response/work/W-16xx.json`, served as items; post-action sidecars in `frontend/mock/fixtures/response/`). All have `sample: true`, all are valid against v7 E-WORK-ITEM, and all are board data. Unless stated, the persona is `pm` and the line is "Prepare for release".

| id | task (rev) | purpose |
|---|---|---|
| W-1601 | T-1601 (2) | **SCR-16 default/validation/success, SCR-02 waiting.** REL-0077, title "Lagoon Health · release to UAT", state `waiting`. Stations: Prepare UAT pack done, Send to client done, Client UAT response `current_person`, Go-live readiness and Go-live `not_started`. `case_id` C-1601, `case_revision` 4. `you_can_act: true`, task title "Record the client's UAT response". `response`: variant `client_response`; responders `[{id:"P-AO", name:"Dr Amaka Obi", role:"Client contact", organisation:"Lagoon Health"}]`; actions approved "Approved", changes_requested "Asked for changes", rejected "Rejected"; versions `[{id:"V-240", label:"Patient app · build 2.4.0", note:"the version sent for UAT"}]`; channels `[{value:"email", label:"Email"}]`; evidence_kind `client_response_proof`; claim_required false; intro, proof_hint and agent_note (tola, the two board lines) as on SCR-16-desktop. Sidecar `W-1601.recorded.json`: state `ready`, station 3 done and 4 `current_person`, task with `you_can_act:false`, `cannot_act_reason:"already_decided"`, `response.next` = the two success-board lines, summary "Client UAT sign-off for Lagoon Health" |
| W-1602 | T-1602 (2) | **SOW signature.** Reference SOW-0207, title "Tamarind Loans · SOW", line "Prepare a SOW", current station "SOW signature". variant `sow_signature`; responder Ngozi Bello, "Head of Lending Operations", "Tamarind Loans"; actions signed "Signed", changes_requested "Asked for changes", rejected "Declined"; versions `[{id:"SOW-0207-v1", label:"SOW-0207 v1 · Tamarind Loans", note:"The version the client received", sent_at:"2026-12-18T09:30:00Z"}]`; channels one (email); context `{project:{case_id:"C-0207", title:"Tamarind Loans"}, document:{reference:"SOW-0207", label:"SOW"}}`; next ["the SOW's 4 stages become the project's milestones, each billable once it's complete.", "Delivery starts with release gates."]; the board aside sentence as `intro`; no agent_note. Sidecar `W-1602.recorded.json` |
| W-1603 | — | **Reconcile, granted.** INV-0412, "Lagoon Health · Milestone 2 invoice", line "Prepare an invoice", state `awaiting_reconciliation`, the seven board stations with Deliver `current_person`, `tasks: []`, `case_id` C-1603. `allowed_actions:["reconcile"]`. reconcile: what "Invoice INV-0412 v2 to the billing contact"; checks `{count:6, first_at, last_at:+2h, agent:"chidi"}`; outcomes [delivered, not_delivered, unknown]; evidence_kind `delivery_receipt`; resend "one resend of the same version"; unknown_note "Keep it held and remind me tomorrow"; resend_note "A resend reuses the same invoice number". Persona `finance_lead`. Sidecars `W-1603.delivered.json` (state `ready`, Deliver done, Verify `current_person`, no reconcile, no allowed_actions), `W-1603.not_delivered.json` (state `processing`, no reconcile), `W-1603.unknown.json` (state `awaiting_reconciliation`, revision+1, reconcile and grant kept) |
| W-1604 | — | W-1603 **without** `allowed_actions`: the panel is hidden and E-WORK-ACTION answers 403 |
| W-1605 | T-1605 (3) | **claim_required: true**, two responders, two versions, three channels (email, letter, in person): the selects show "Choose…" and the channel select appears. Sidecar `.recorded` |
| W-1606 | T-1606 (2) | **Every r2 field absent:** response has only variant, responders, actions, versions, evidence_kind and claim_required false. Sidecar `.recorded` with no `recorded`/`next` blocks in the 200 |
| W-1607 | — | Reconcile with only `outcomes:["not_delivered","unknown"]` and `checks:{count:3}`: no resend, no notes, no delivered option |
| W-1608 | T-1608 (2) | Response task with `you_can_act: false`: no entry button, not-open page, E-RESPONSE 403 |
| W-1609 | T-1609 (2) | No `case_id`/`case_revision`: proof disabled, Record never enabled |

**Fixture example** (W-1601 `tasks[0].response`, abridged):
```json
{"variant":"client_response","responders":[{"id":"P-AO","name":"Dr Amaka Obi","role":"Client contact","organisation":"Lagoon Health"}],
 "actions":[{"value":"approved","label":"Approved"},{"value":"changes_requested","label":"Asked for changes"},{"value":"rejected","label":"Rejected"}],
 "versions":[{"id":"V-240","label":"Patient app · build 2.4.0","note":"the version sent for UAT"}],
 "channels":[{"value":"email","label":"Email"}],"evidence_kind":"client_response_proof","claim_required":false,
 "agent_note":{"agent":"tola","lines":["After you record it, I'll check the PDF names build 2.4.0 and is signed by Dr Obi, and tell you if anything doesn't match.","I can't record responses for you; a person has to vouch for them."]}}
```

## Lanes
- **Frontend lane (F-09 builder) owns:**
  - `frontend/src/app/work/[id]/respond/**`;
  - `frontend/src/features/response/**` (`contract.ts`, `api.ts`, `labels.ts`, `index.ts`, components, hooks, an optional `response.css` using only existing tokens);
  - `frontend/mock/response.mjs`;
  - `frontend/mock/fixtures/response/**`;
  - `frontend/mock/fixtures/work/W-16[0-4]x*.json` (reserved; only v4-valid bodies, none needed now);
  - `frontend/tests/response*.test.ts(x)`;
  - `frontend/e2e/response.spec.ts`.
- **Shared, additive, listed in build.md** (the integration owner, the coordinator, merges them):
  - the three `server.mjs` edits (a)–(c);
  - the two `WorkItemOverview.tsx` edits (the `TaskPanels` branch and the `ReconcilePanel` mount).
- **Backend lane:** none (T-RESPONSE and T-EXCEPTIONS are not part of this feature).
- **Integration owner:** the coordinator. Rebase onto whichever lane first touches `WorkItemOverview.tsx` or `server.mjs` (F-06, F-13).
  - If F-13 lands first, drop the cast and `RESPONSE_OPENAPI_PATH` and use `OPENAPI_PATH` and the generated types.
  - If F-09 lands first, F-13's rebase removes them.
- **Not touched:**
  - `architecture/**`, `src/api/**` and `src/shell/**`;
  - `NextStep`;
  - F-05, F-06, F-07, F-08, F-12 and F-13 files;
  - `decide/**` and `my-work/**`;
  - the W-10xx, W-12xx, W-14xx and W-15xx fixtures;
  - `public/agents/**`;
  - `tokens.css` and `psl-bundle.css`;
  - `tests/mock-contract.test.ts`, `api-schema-drift.test.ts` and `mock-decide.test.ts`;
  - `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json` (protected).
- **Ports:** app 4401, mock 4402.
  - Dev: `cd frontend && MOCK_PORT=4402 npm run dev -- -p 4401`.
  - e2e: `cd frontend && E2E_PORT=4401 MOCK_PORT=4402 npx playwright test e2e/response.spec.ts`.

## Acceptance criteria
1. **Entry button.** /work/W-1601 shows the link "Record the client's response" to `/work/W-1601/respond?task=T-1601`, and no "Open the decision" in that panel. W-1608 shows neither link. W-1201 still shows "Open the decision". — verify: component test on `WorkItemOverview` with the three fixtures.
2. **Default form shows only returned options (A-RESPONSE).** /work/W-1601/respond?task=T-1601 (persona pm) shows, in board order:
   - the crumb "QUEUE / PREPARE FOR RELEASE / REL-0077 · STATION 3 OF 5";
   - the h1 "Record the client's UAT response" and the intro;
   - "Client contact · Dr Amaka Obi, Lagoon Health" (preselected);
   - exactly three action radios "Approved", "Asked for changes" and "Rejected", none checked;
   - "Patient app · build 2.4.0 (the version sent for UAT)";
   - no "How they responded" control;
   - the proof hint and the attestation sentence;
   - "Record response" (disabled);
   - the Tola aside with `img[src="/agents/tola.png"]`, "Tola · PMO agent" and both lines.

   W-1605 shows "Choose…" in the Who and Version selects and a "How they responded" select with exactly Email, Letter and In person. A test that adds an extra action to the fixture in memory sees it, and one that removes an action does not. — verify: component tests.
3. **Validation (SCR-16-desktop-validation).** With everything filled but no proof and no tick, Record is disabled and `role="alert"` reads "Add the proof and confirm it's genuine to record this." Clicking Record sends no request. With proof but no tick, the alert is the same. With proof and the tick, Record is enabled and the alert is gone. — verify: component test counting fetch calls.
4. **Proof uploads first, and its case revision is carried.** Choosing a file sends one `POST /api/v1/cases/C-1601/evidence` with `{"kind":"client_response_proof","filename":…,"content_base64":…,"case_revision":4}` and `X-CSRFToken: mock-csrf-pm`. A second file is sent with the first upload's returned `case_revision` (5). Recording then sends `evidence_id` = the first id, `evidence_ids` = [the second id] and `case_revision` 6. — verify: component test inspecting the stubbed fetch bodies, in order.
5. **Record body.** After filling W-1601 with Approved, 11 Nov 2026 16:20, one file and the tick, Record sends exactly one `POST /api/v1/tasks/T-1601/response` with the CSRF header and this body: `{"expected_revision":2,"who":"P-AO","action":"approved","responded_at":"2026-11-11T16:20:00+01:00","evidence_id":"EV-…","attested":true,"case_revision":5,"version_id":"V-240","received_via":"email"}`. There is no `note`, `team`, `what` or `estimate_person_days` key. Typing a note "Signed on paper" adds `"note":"Signed on paper"`. — verify: component test.
6. **Claim first when required.** On W-1605, Record sends `POST /api/v1/tasks/T-1605/claim` `{"expected_revision":3}` and only after its 200 sends E-RESPONSE, with `expected_revision` = the claim's `revision`. On W-1601 no claim request is sent. A claim answering 409 sends no E-RESPONSE. — verify: component test asserting the call order.
7. **One record on a double press.** A double click on an enabled Record, with a deferred fetch, sends one E-RESPONSE. While it is pending the button reads "Recording…", is disabled, and the form has `aria-busy="true"`. — verify: component test.
8. **Success (SCR-16-desktop-success).** After a 200 on W-1601 the page shows:
   - "REL-0077 · LAGOON HEALTH" and the h1 "Client UAT response";
   - "Response recorded. Client UAT sign-off for Lagoon Health, received by email on 11 Nov, recorded by Tunde Bello at <HH:mm> with 1 proof file.";
   - "What happens next" with both `next` lines;
   - the correction line;
   - "Back to the work item";
   - and no form controls.

   At 390px it shows "← Work item", "REL-0077" and "Back to my queue". — verify: component test; e2e against the mock.
9. **Absent fields are left out, with no fallback copy (W-1606).**
   - The form has no intro, no aside and no proof hint; the crumb, pickers, proof field and attestation still render.
   - The success view has no "received by", no "with n proof file", no "What happens next" and no summary. It reads "Response recorded. Recorded by Tunde Bello at <HH:mm>." when the 200 has only `task_id` and `work_state` and the reload's `recorded` gives `by` and `at`.
   - None of the W-1601 board sentences ("Lagoon Health's client contact…", "Signed PDF…", "After you record it…") appears anywhere.

   — verify: component test asserting absence.
10. **SOW signature (SCR-16-desktop/-mobile-sow-signed).** /work/W-1602/respond?task=T-1602 shows:
    - "PROJECTS / TAMARIND LOANS / DOCUMENTS / SOW-0207", with only PROJECTS a link (`/projects`);
    - "Record the client's SOW signature" and the "Signature" panel;
    - "SOW-0207 v1 · Tamarind Loans · sent 18 Dec 10:30" and "The version the client received";
    - "Ngozi Bello · Head of Lending Operations, Tamarind Loans";
    - the radios "Signed", "Asked for changes" and "Declined";
    - "What happens next: the SOW's 4 stages become the project's milestones, each billable once it's complete. Delivery starts with release gates.";
    - "Record signature";
    - the intro in the aside.

    At 390px the h1 is "SOW signature" and the back link reads "← SOW". Recording sends `action:"rejected"` when "Declined" is chosen. — verify: component tests.
11. **Errors on record (wrong user, invalid input, provider failure).**
    - 422 `{code:"invalid",message:"Check these fields: evidence_id."}` → that message in a problem callout, entries kept, no second POST.
    - 409 → "This changed while you were recording…", one GET reload, entries and uploaded proof kept, no second POST.
    - 403 → one GET reload. W-1608 after reload shows "This response isn't open here".
    - 401 → a sign-in link with `next` = `/work/W-1601/respond?task=T-1601`.
    - Item 404 → `NoAccessState` with no id or title.
    - Item 500 → the error card with Try again.

    — verify: component tests.
12. **Uncertain effect is re-read, never resent.** E-RESPONSE network error, with a reload returning `W-1601.recorded.json` → the warning plus the success view, and exactly one POST in total. With a reload still showing the open task → the warning, and Record is enabled again with no automatic POST. With the reload also failing → "…couldn't reload to check. Record stays off…", and Try again sends only a GET. In e2e, `X-Mock-Scenario: record-then-fail` set on the E-RESPONSE request shows the success view after the reload. — verify: component tests; e2e.
13. **Reconcile panel (A-RECONCILE, frontend half).** /work/W-1603 (persona finance_lead) at 1440 shows, as the right-hand aside:
    - "Confirm what happened";
    - "Chidi checked 6 times over 2 hours and found no delivery receipt. The factory won't resend until a person confirms what happened, so the client is never invoiced twice.";
    - the three options with the board wording, including "Allow one resend of the same version." and "Keep it held and remind me tomorrow.";
    - "Record and continue";
    - "Your choice is recorded with your name. A resend reuses the same invoice number."

    At 390 it shows "No receipt found after 6 checks. Confirm what happened before anything is resent." W-1607 shows only two options, with no "Allow …" text, no delivered option and no resend_note. — verify: component tests.
14. **Reconcile only with the grant.** W-1604 (no `allowed_actions`) and W-1601 render no "Confirm what happened" and send no POST. `grep -rn "roles\|destinations" frontend/src/features/response` finds no branch that controls what is offered. — verify: component test and grep.
15. **Reconcile write.**
    - Choosing "It arrived" shows the proof field and keeps "Record and continue" disabled until the upload (`kind:"delivery_receipt"`) succeeds. Pressing it then sends one `POST /api/v1/work/W-1603/actions` with `{"expected_revision":<rev>,"action":"reconcile","outcome":"delivered","evidence_id":"EV-…","case_revision":<returned>}` and CSRF, then calls `reloadPage` once.
    - "It didn't arrive" sends `outcome:"not_delivered"` with no `evidence_id`.
    - No request other than the upload and this one is sent: no resend or delivery call exists in the feature (`grep -rn "resend\|deliver" frontend/src/features/response/api.ts` shows none).
    - 409 shows the warning with "Reload the work item" and no second POST. A network error shows "We couldn't confirm your answer…" and no second POST.

    — verify: component tests.
16. **Mock against v7.** `frontend/tests/response-mock.test.ts` runs a fresh `startMockServer({port:0})` and checks:
    - every file in `fixtures/response/**` validates against v7 E-WORK-ITEM with strict Ajv and has `sample: true`;
    - every reply from the three operations validates against its v7 declared schema;
    - upload: wrong `kind` → 422 `kind`; stale `case_revision` → 409; success → a 64-hex `sha256`, and `case_revision` +1;
    - E-RESPONSE:
      - without `attested` → 422; with `attested:false` → 422 `attested`; with an unknown `evidence_id` → 422 `evidence_id`;
      - a `who` not in responders → 422 `who`; an `action` not offered → 422 `action`; a 2001-character note → 422 `note`; an extra key → 422 naming it;
      - a stale `expected_revision` → 409; T-1608 → 403; persona `none` → 403;
      - no CSRF → 403 `csrf_failed`; `X-Mock-Scenario: 422` → the scenario body;
      - success → 200 with `recorded.by.name` "Tunde Bello", after which GET W-1601 returns the recorded sidecar; a repeat with revision 2 → 409;
    - E-WORK-ACTION:
      - W-1604 → 403; `outcome` missing → 422; `delivered` without evidence → 422 `evidence_id`; `resume` on a granted item → 501;
      - success → 200, after which GET W-1603 returns the outcome sidecar;
    - `POST /__mock/reset` restores W-1601 and W-1603 and clears the evidence;
    - claim on T-1605 → 200 through F-04's handler.

    — verify: `cd frontend && npx vitest run tests/response-mock.test.ts`.
17. **The base's v4 checks are unchanged.** `M1_OPERATIONS` and `OPENAPI_PATH` are unchanged. No `fixtures/work/W-16*` file has v7 fields. `tests/mock-contract.test.ts`, `api-schema-drift.test.ts` and `mock-decide.test.ts` pass with no edits. `git diff <base> -- architecture frontend/src/api frontend/src/shell` is empty. `grep -rn " as unknown as\| as Response" frontend/src/features/response` matches only `api.ts`. — verify: `cd frontend && npx vitest run tests/mock-contract.test.ts tests/api-schema-drift.test.ts tests/mock-decide.test.ts`, the diff and the grep.
18. **Accessibility and layout (A-ACCESSIBILITY).** axe reports no WCAG 2.2 AA violations at 390x844 and 1440x900 for these states, with `/__mock/reset` in `beforeEach`:
    - W-1601 default;
    - validation;
    - success;
    - W-1602;
    - W-1603 (finance_lead).

    Also:
    - At 390, Record and "Record and continue" are within the viewport, each at least 44px tall, and `scrollWidth` is at most 390.
    - Tab order on SCR-16 is Who, When, the actions, Version, Note, the proof button, the attestation and Record, each with a visible focus ring.
    - With `reducedMotion: 'reduce'` nothing animates.
    - Every radio group has an accessible name ("What they did", "Confirm what happened").

    — verify: `cd frontend && E2E_PORT=4401 MOCK_PORT=4402 npx playwright test e2e/response.spec.ts`.
19. **Design fidelity.** The coordinator's fidelity driver passes at 1440 (desktop boards) and 390 (mobile boards): 100% element coverage after approved exceptions and visual score at least 90. The pages are:

    | boards | page and persona |
    |---|---|
    | SCR-16-*, -validation | `/work/W-1601/respond?task=T-1601`, persona pm, filled with the board values (validation: no file, unticked) |
    | SCR-16-*-success | after recording that |
    | SCR-16-*-sow-signed | `/work/W-1602/respond?task=T-1602` with the board file `SOW-0207-v1-signed.pdf` |
    | SCR-02-*-awaiting-reconciliation | `/work/W-1603`, persona finance_lead (panel only, PMO-0-6) |
    | SCR-02-*-waiting | `/work/W-1601` (button only) |

    The builder supplies the act script and lists every proposed exception in build.md (see Assumptions). — verify: the gate's fidelity run.
20. **Gate:** `delivery/checks.sh` passes, including new component tests in `frontend/tests/response.test.tsx`. — verify: the gate run.

## Out of scope
- **Readiness excluded:**
  - F-09B / FE-M2B-RFP: team input (`team_input`, `teams`, `blocking`, `team`, `estimate_person_days`, `what`), RFP outcome and follow-up;
  - the `go_live_acceptance` and `support_handover` variants (they get the not-open state here);
  - "Change the reminder";
  - the resume and cancel actions;
  - the backend (T-RESPONSE, T-EXCEPTIONS) and real-API wiring;
  - the v7 repoint (F-13);
  - edits to `architecture/**`, `src/api/**` and `src/shell/**`;
  - new npm dependencies;
  - any SAMPLE DATA tag.
- **Tempting, not built:**
  - preselecting an action, or defaulting `responded_at` to now;
  - deriving responders, actions or channels from roles or the task kind;
  - a resend button, or any outbound message;
  - automatic retry of E-RESPONSE, E-WORK-ACTION or an upload;
  - editing or deleting a recorded response, or deleting uploaded evidence;
  - a client-side file size or type limit;
  - a confirm dialog before Record;
  - polling the respond page;
  - adding W-16xx rows to My work (`work-list.mjs` belongs to F-02);
  - highlighting Projects in the top bar on the SOW page (PMO-0-4);
  - restyling F-03's facts or stations to match the SCR-02 boards (PMO-0-6: raised against F-03).
- **Board elements with no contract or owner:**
  - the rest of the waiting panel's copy ("Waiting on the client", the due and reminder sentences), which stays F-03's;
  - the SCR-02 eyebrow "INV-0412 · LAGOON HEALTH" (F-03's header);
  - "Tunde Bello · PMO" in the top bar (frame).

## Assumptions
- **The note field, the channel select (shown only with two or more channels) and the attestation checkbox on the SOW boards are drawn on no board.** They are extra elements, kept because readiness requires `note` and `received_via` and because the sworn attestation is a security control. The builder proposes them as fidelity exceptions for the design engineer.
- **"When they responded" stays on the phone even though SCR-16-mobile omits it.** `responded_at` is a sworn fact and must not be defaulted. This is a proposed exception.
- **No action is preselected**, although the default board draws Approved as checked. A wrong default on a record that cannot be edited would go unnoticed. The board scenario's act script makes the choice. This is a proposed exception.
- **The crumb station number is computed from `stations`.** For W-1601 it reads "STATION 3 OF 5". The board's "2 OF 5" contradicts SCR-02-waiting, where the response is station 3, so it is treated as a board slip (as D-09 did).
- **The phone summary line reads "Lagoon Health · Patient app · build 2.4.0 · Dr Amaka Obi"** where the board has "build 2.4.0", because the version label is used as returned. This is a proposed exception.
- **The phone Who and Version selects collapse into that summary line only when each has exactly one option.** With more options, the choices must stay visible.
- **A single responder, version or channel is preselected**, because the API offers no alternative. With more than one, the select starts on "Choose…". No such rule applies to actions.
- **Option text order differs by variant to match the boards.** client_response uses "<role> · <name>, <organisation>" and sow_signature uses "<name> · <role>, <organisation>".
- **`intro` sits under the h1 for client_response and in the aside for sow_signature.** The phone hides it, the aside and `proof_hint`, as the boards do.
- **The success h1 is the name of the station that was current before recording, and the phone SOW h1 is the current station's name.** This matches "Client UAT response" (SCR-02-waiting station 3) and "SOW signature". The eyebrow uses the chosen responder's `organisation`.
- **The channel label is lower-cased inside the success sentence** ("received by email"). This is presentation only.
- **Several sentences are drafted with no board, and are listed for product acceptance:**
  - the combined missing-fields alert;
  - the stale and uncertain warnings;
  - the not-open state;
  - the upload chip errors;
  - "Proof can't be uploaded for this item.";
  - the entry label "Record the client's signature";
  - "Choose the signed copy";
  - "Recorded. Reloading the work item…";
  - the reconcile 409 and uncertain lines.
- **These fixed sentences are frontend statements of existing invariants, not backend data:**
  - "The factory won't resend until a person confirms what happened, so the client is never invoiced twice." (INV-RESEND);
  - "Your choice is recorded with your name.";
  - "Recorded with your name and the time…" and "Recorded responses can't be edited…" (INV-AUDIT).
- **The claim runs at the Record press, not on page open.** Readiness says only "before E-RESPONSE". Opening the form should not lock the task for others.
- **After a reconcile 200 the page does a full reload (`reloadPage`)** so that `WorkItemView` re-reads the item. Readiness allows only two F-03 edits, and passing a refetch callback would be a third.
- **The reconcile panel is mounted in its own `work-column` after the left column**, so it is the right-hand aside as on the board, even when `tasks` is empty. It is still one conditional mount.
- **An upload's Try again reloads the item first and then uploads.** No evidence list endpoint exists to check for a duplicate, and a stray proof on the case is harmless, unlike a duplicate response.
- **The mock does not enforce "claimed before recording".** That rule belongs to the backend (D-RESPONSE-VIEW rationale). The component test checks the order.
- **The mock answers 403 for persona `none` and decides other grants from fixture flags,** because the mock personas do not map to record grants (as F-04 did).
- **`record-then-fail` is a mock-only scenario value** used to exercise uncertain effects in e2e. It never affects numeric scenarios or the v4 checks.
- **No future-date check is applied to `responded_at`.** The board data is dated December 2026, and the backend owns that validation.
- **The "Tola · PMO agent", "Chidi · Finance agent" and "Zainab · HR agent" labels** come from the boards (`labels.ts`). Avatars are read from `/agents/<agent>.png` (PR #12).
