# The release gates page shows the live gates and lets the right person decide the planning exit and record the release

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0 or later. Design: approved 13 Nov canvas under the recorded exceptions (D-173/D-181) in `design/review.json`; screens: SCR-44 (states default, decision, returned, owner-needed, readiness, ready; desktop and mobile).

## Summary
- The release line's work item (`/work/{id}` for `delivery-release/v1`) draws the gates from `GET /work/{id}/release-register` and `GET /work/{id}/planning-exit`: phases and checks with the D-14 words, the planning-exit checklist and blockers, the client UAT outcome (read only), and the six board states derived from those reads.
- The PMO Lead approves or returns the planning exit with a note (`POST /work/{id}/planning-exit`). The server decides who may, from `verdicts[]` and `can_approve_directly`; the page adds no approver rule. An eligible current PMO Lead (`can_approve_directly`) approves their own named planning exit with no evidence (PSL answer 1); every other decision takes evidence chosen from `proofs[]`, nothing preselected.
- The PM can press "Prepare release readiness" (`prepare_readiness`, D-13) and record the actual release with a checked PDF (`observe_release`), each only when the read's `actions[]` lists it.
- Owner-needed shows when the work item's `state` is `owner_needed`, using `GET /setup/{case}/decision-appointments`.
- Built as the release adapter mapping (`GET` panels to sections) plus `ReleaseActions.tsx` on F-87's `Actions` slot. `src/features/workspace` is not changed. Waits (build start only): F-113 merged, F-85 and F-87 on main.

## Context
- Work page: `frontend/src/features/work-item/` (`WorkItemView.tsx`, `useWorkItem.ts`) renders `GET /work/{id}`; its `panels[]` entries `{key, url}` feed the line adapter registry in `frontend/src/features/workspace/adapter.ts` (F-85: `PanelRef`, `LineContext`, `LineAdapter`, `CommandDescriptor`, `makeCommand`, `registerLineAdapter`). F-87 adds `LineAdapter.Actions?: ComponentType<LineActionsProps>` with `LineActionsProps = { readback, ctx: LineContext, commands: CommandDescriptor[], reload: () => void }`, plus `useWorkCommand`. F-89's `WeeklyReportActions.tsx` is the form example. Specs: `delivery/features/F-85/spec.md`, `delivery/features/F-87/spec.md`.
- Reuse from F-113: `frontend/src/features/projects/deliveryModel.ts` (`stateWords` for the line's state tag; `LINE_KEYS`). Not reused: `deliveryRows`, `isOverview` (overview only). `DeliveryTab.tsx` already links "Open" to `/work/{work_id}`, which is how this page is reached.
- Mock: `frontend/mock/delivery-overview.mjs` already answers `GET /work/{id}/release-register` with only `dossier_id` (`REGISTER_PATTERN`) for F-113's closure reasons. This feature must extend it to the full shape without breaking F-113 (name the change in build.md for the coordinator).
- Upload: `src/components/FileUpload.tsx` and F-85's `EvidencePicker`/`uploadCaseFile` (`POST /cases/{case_id}/files` returns `upload_id`).
- Live reads used (viewer: read `/Users/Hunchoo/psl-factory-worktrees/lane-d/contracts/psl-factory.openapi.json` directly):
  - `GET /work/{work_id}/release-register` returns `{expected_revision, case_revision, dossier_id, candidate_id, as_of, current_scope, synthetic, actions[], phases[{name, checks[{key, title, authority, status, records[{id,type}]}]}], proofs[{id,version,kind}], readiness_ids[], release|null{reference, released_at, environment|null, evidence_id}}`. `actions[]` values: `capture_source`, `verify_source`, `capture_gate`, `verify_gate`, `record_progress`, `record_glpi_request`, `prepare_readiness`, `observe_release`.
  - `GET /work/{work_id}/planning-exit` returns `{expected_revision, case_revision, packet (64-char hex | null), verdicts[approve|return|reject], proofs[], blockers[{id, reference}], checklist[{name, status}], workaround|null{return_id, issue_state_id, response_id, review_id}, can_approve_directly, latest_decision|null{id, verdict, role, by, at, direct}}`. Note: this read has no `actions[]` (readiness assumed one); `verdicts[]` and `can_approve_directly` carry that meaning.
  - `GET /setup/{case_id}/decision-appointments?page=` returns `{case_revision, latest_id, active_id, people[{id,label}], proofs[], can_draft, appointments[{user_id, roles[], eligibility}], next_page}`.
  - `GET /projects/{case_id}/delivery/{dossier_id}/client-testing` returns `{outcome|null (approved, changes_requested, rejected, approved_with_workaround), proof_current, binding_current, gate_id|null, ...}`.

## Contract

### Reads on opening `/work/{id}` for the release line
1. `GET /work/{id}` (existing). Its `panels[]` supply the keys and URLs; the builder reads the real keys for a release line from live and registers the adapter on them (assumption below). `state` of `owner_needed` selects the owner-needed screen.
2. The release adapter's `read` fetches, in parallel: release-register and planning-exit (always); client-testing (after release-register, using its `dossier_id` and the item's `case_id`; a failure here only hides the UAT row); decision-appointments (only when `state === 'owner_needed'`). A failure of release-register or planning-exit is the page error; the others degrade to hidden parts.
3. No read is repeated by a timer. The page re-reads once after every write (`reload()`), and keeps F-85's polling rule for the work item.

### Screen states (derived only from the reads above; nothing counted or invented)
| Board state | When | What is drawn |
|---|---|---|
| default (waiting on PMO Lead) | `latest_decision` null, `state` not `owner_needed` | Gates list; for a viewer who cannot decide, the line "Waiting for the PMO Lead" |
| decision | `verdicts[]` is non-empty and `packet` is non-null | Gates list, checklist, blockers, the decision form |
| returned | `latest_decision.verdict` is `return` | The returned line "{by} returned the release on {at}" with the note only if the read carries it (it does not today, so omitted), blockers as links, `workaround` shown as "Client workaround on file" when non-null |
| owner-needed | work `state === 'owner_needed'` | Held line, the "PMO Lead assigned" row as OWNER NEEDED, the appointments from decision-appointments (people and eligibility words as given), and a link to Setup roles |
| readiness | `latest_decision.verdict` is `approve`, `readiness_ids[]` empty | "Preparing release readiness"; the PM button when `actions[]` has `prepare_readiness`; the activity line from `current_activity` when the work read has it |
| ready | `readiness_ids[]` non-empty | "Release ready" with the readiness record count; if `release` is non-null, "Release recorded {released_at} · {reference}"; the record-release form when `actions[]` has `observe_release` and `release` is null |

When a case matches two rows the later one wins (ready over readiness over returned over decision over default). A packet of null with verdicts non-empty is shown as "Waiting for the packet" and the form stays off.

### Gates list
- One group per `phases[]` entry in the given order (Initiation, Planning, Execution, Closure); under each, one row per check: `title`, `authority` as small text, status tag, and the count of `records[]` ("2 records") only when non-empty. No record ids shown.
- Status words (D-14): `current` CURRENT (done tone); `stale_scope` STALE SCOPE; `restricted_or_authority_changed` AUTHORITY CHANGED; `unknown_or_stale` UNKNOWN OR STALE; `unknown` UNKNOWN; any other value is shown as given in capitals. Unknown is never drawn as 0, as done, or hidden.
- Planning decision row: `checklist[]` rows `{name, status}` as given, then `latest_decision` as "Approved/Returned {date} by {by}" (and "approved directly" when `direct`).
- Client UAT row (read only): `outcome` words (Approved, Changes requested, Rejected, Approved with workaround; null is "No response recorded") and `proof_current === false` adds "Proof is out of date". `binding_current` false adds "Not tied to this release".
- Blockers: one link per `blockers[]` entry, text `reference`, to the issue page `/work/{id}` is not known, so the link is built only if the work read or issue route provides one; otherwise plain text (assumption).
- Not drawn (no live data, D-182): the "What you're deciding" figures (stages built, open issues by severity, changes since SOW), Tola's check card and step lists, the PM and PMO Lead names on the first row, "Send for decision again", "Open ISS-xxxx" as a button.
- Hide the whole gates list group when `current_scope` is false and show "This record is not for the current scope." in its place (assumption on the meaning; the server's words win if a message is present).

### Write 1: decide the planning exit
`POST /work/{id}/planning-exit` body `{expected_revision, case_revision, packet, verdict, evidence_id?, note?, issue_id?}`; 200 `{work_id, state, revision, record_id}`.
- Tokens: `expected_revision`, `case_revision` and `packet` are copied from the planning-exit read just loaded; never defaulted, never 0. A null token or null packet disables the form with the reason "This can't be decided yet."
- Form (inside `ReleaseActions.tsx`, shown only when `verdicts[]` is non-empty): Note (textarea, max 4000, optional for Approve); Evidence (a select of `proofs[]` as "{kind} · version {version}", nothing preselected, label "Evidence for this decision"); buttons "Approve for release" (when `verdicts` has `approve`) and "Return with a note" (when it has `return`). Return requires a non-empty note (client check for clarity; the server stays final).
- Direct approval (PSL answer 1, binding): when `can_approve_directly` is true, "Approve for release" needs no evidence. It is enabled without one, and the body omits `evidence_id` unless the person chose a proof (the select is optional for Approve in this case and its label reads "Evidence (optional)"). The signed-in approval is the record; the page asks for no signature or upload.
- Every other decision follows the proof rule: Approve when `can_approve_directly` is false, and Return always. When `blockers[]` is non-empty, "Return with a note" offers an optional "Related issue" select of the blockers (sends `issue_id`).
- `reject` is not drawn even when listed (the board has two buttons).
- Evidence rule (binding) for every decision that is not a direct approval: no proof route exists for this action, so the choice comes from `proofs[]`, nothing preselected; those buttons stay off while no proof is chosen, and while the list is empty the sentence "No evidence is on file for this decision yet." shows. Never invent an evidence id.
- When `can_approve_directly` is true the line "You can approve this yourself." shows under the buttons. Server errors win.
- Once `latest_decision.verdict` is `approve`, the planning decision row and the readiness/ready screens show "Approved by PMO Lead", `by` and `at` (and "approved directly" when `direct`), taken from the re-read, never from the 200. The words "PMO Lead" come from `role` when it says so, else are omitted rather than assumed.
- After 200: re-read both reads, show the new state; the result text comes from the re-read, not from the 200.

### Write 2: prepare readiness
`POST /work/{id}/release-register` `{action:"prepare_readiness", expected_revision, case_revision}`; 200. Button "Prepare release readiness" shown only when `actions[]` has `prepare_readiness`. Tokens from the release-register read. On success re-read; the result is the readiness state from the re-read.

### Write 3: record the release
`POST /work/{id}/release-register` `{action:"observe_release", expected_revision, case_revision, readiness_id|null, released_at, reference, upload_id, checked:true, note, environment|null, private_log_id|null}`; 200. Shown only when `actions[]` has `observe_release`.
- Form: Release date and time (required), Reference (required, max 240), Environment (optional, max 160), Note (required, max 4000), Release record file (a PDF through the F-85 picker for the item's own `case_id`; returns `upload_id`), and a checkbox "I have checked this file is the release record" that sets `checked:true`; the button stays off until the file is uploaded and the box is ticked. `readiness_id`: when `readiness_ids[]` has one entry send it; with several, the person picks (nothing preselected); with none send null. `private_log_id` is sent as null (no field drawn).
- This is the D-1 route (the release register's own proof route), so no evidence picker for it. `upload_id` is never sent as `evidence_id`.
- An uncertain result (timeout, 5xx, dropped connection) locks the form: re-read release-register; if `release` is non-null with that `reference`, treat it as recorded; otherwise say "We couldn't confirm that this was recorded. Check the page before trying again." and unlock only when the read's `expected_revision` changes or the page is reloaded.

### Errors (all three writes; words from `ApiError`, server `message` shown as given)
401 signed-out state; 404 "This record is unavailable."; 403 `forbidden` "You can't do this." plus the server message and a re-read; 403 `csrf_failed` refresh the session once and say "Press the button again" (nothing sent by itself); 409 re-read and say "This changed while you were working. Showing the latest version."; 422 the server `message` and the first `fields[].message`, no retry; 413/415 on the upload mapped as F-85; 429 and 503 "Try again shortly."; network/5xx on prepare_readiness and the decision: re-read, and lock that button until `expected_revision` changes or reload, with "We couldn't confirm that this happened. Check the page before trying again."

### Idempotency and versioning
None of the three bodies carries a key. Duplicates are prevented by `useWorkCommand`'s press lock, the uncertain lock and the revision tokens. Commands are `CommandDescriptor`s from the adapter's `commands()`: `release.decide`, `release.prepare_readiness`, `release.observe`, each with `disabledReason` taken from the read (empty `verdicts`, missing action, null token), never invented.

### Permission and tenant rules
Every button exists only because the read lists it for this person (`verdicts[]`, `actions[]`). The page has no role check. Calls use only the loaded item's `work_id`, `case_id` and the read's `dossier_id`. A 404 reads the same whether the record is missing or not theirs.

### Fixtures (mock on 4991; ids free, shapes binding; builder creates `frontend/mock/delivery-release.mjs`)
- `4201` decision: PMO Lead viewer; `verdicts:["approve","return","reject"]`, `packet:"<64 hex>"`, `proofs:[{id:61,version:1,kind:"signed_pdf"}]`, `can_approve_directly:true`, one blocker `{id:301,reference:"ISS-0301"}`, four phases with mixed statuses.
- `4202` decision with `proofs:[]` and `can_approve_directly:false` (buttons off). `4213` decision with `proofs:[]` and `can_approve_directly:true` (Approve works, Return off). `4203` packet null. `4204` viewer cannot decide (`verdicts:[]`, `latest_decision:null`).
- `4205` returned: `latest_decision:{verdict:"return", by:"Kemi Adebayo", ...}`, `workaround:null`; `4206` returned with a `workaround`.
- `4207` owner-needed: work `state:"owner_needed"`; decision-appointments with `people` and `appointments:[]`.
- `4208` readiness: approved, `readiness_ids:[]`, `actions:["prepare_readiness"]`. `4209` readiness, `actions:[]`.
- `4210` ready, `readiness_ids:[71]`, `release:null`, `actions:["observe_release"]`. `4211` released (`release` set). `4212` null `expected_revision` path (work item `revision:null`).
- Scenarios for each write: 403 `forbidden`, 403 `csrf_failed`, 409 `stale_version`, 422 with `fields`, 429, 503, 500, dropped connection (F-85 scenario mechanism).

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/delivery-release/**` (new: `releaseAdapter.ts`, `releaseModel.ts`, `ReleaseGates.tsx`, `ReleaseActions.tsx`, `release.css`, tests), `frontend/mock/delivery-release.mjs`, an additive extension of `frontend/mock/delivery-overview.mjs` and the mock server routes, and `frontend/e2e/delivery-release.spec.ts`. Reuses `deliveryModel.ts` by import only.
- Backend lane: none; no contract edit.
- Integration owner: lane D coordinator. Shared files: `src/features/workspace/*` (lane C, not changed; `ReleaseActions` is registered through `registerLineAdapter` once F-87 is on main), `src/features/projects/deliveryModel.ts` (F-113, import only), `frontend/mock/delivery-overview.mjs` (F-113's file; change named in build.md so the coordinator can tell lane B/F-113), `src/api/*` (shared).
- Protected paths in `delivery/config.json` stay unchanged.
- If the release writes prove too large, split them as F-113C and keep the planning exit here (readiness).

## Acceptance criteria
1. `/work/4201` (Next 4990, mock 4991) shows the four phases in order with each check's title and a status tag, the checklist rows and a "Planning decision" row — verify: open the page; compare with `GET /api/v1/work/4201/release-register` and `/planning-exit` JSON.
2. Every D-14 status maps to its words (CURRENT, STALE SCOPE, AUTHORITY CHANGED, UNKNOWN OR STALE, UNKNOWN) and a made-up status shows the raw text in capitals; none is drawn as 0 or as done unless `current` — verify: unit test on `releaseModel.ts` over all five plus one unknown.
3. A check with empty `records[]` shows no "0 records" text — verify: component test on a fixture.
4. Each board state selects from the reads as in the state table (default, decision, returned, owner-needed, readiness, ready), including the precedence rule and the null-packet case — verify: unit test on the state function over fixtures 4201 to 4211; open each page at 1440 and 390 widths.
5. On `/work/4201` (`can_approve_directly:true`) the decision form shows "Approve for release" and "Return with a note" (no Reject), a Note field and an optional "Evidence (optional)" select listing `proofs[]` with nothing preselected; Approve is enabled with no proof chosen, Return stays off until a proof is chosen and a note is typed — verify: e2e; DOM shows the select at "Choose evidence".
6. A fixture with `can_approve_directly:false` and `proofs:[]` (make `4202` this) shows both buttons off and "No evidence is on file for this decision yet."; no request is made on press attempts. A fixture with `can_approve_directly:true` and `proofs:[]` (make `4213`) lets Approve work and keeps Return off — verify: e2e asserts no POST on 4202 and one on 4213 approve.
7. Direct approve on `/work/4201` with no proof sends exactly one `POST /api/v1/work/4201/planning-exit` with `verdict:"approve"`, the loaded `expected_revision`, `case_revision`, `packet` and no `evidence_id`; with a proof chosen it includes that `evidence_id`. On a `can_approve_directly:false` fixture Approve sends only with a chosen proof. After success the page re-reads and shows "Approved by PMO Lead", the name and the time from `latest_decision` — verify: network panel body; mock logs one POST; page text.
8. Return needs a note and a chosen proof: either missing leaves "Return with a note" off; with both it sends `verdict:"return"`, `note`, and `issue_id` only when a blocker was picked — verify: e2e and the POST body.
9. The page sends `evidence_id` only when the person chose a proof, and never sends an id not in `proofs[]` — verify: unit test on the command body; grep shows no literal evidence id.
10. `/work/4203` (packet null) and `/work/4212` (null revision) show the form off with its reason and send nothing; a null token is never sent as 0 — verify: e2e plus unit test on `body()`.
11. `/work/4204` (`verdicts:[]`) shows no decision form and no buttons, and the line "Waiting for the PMO Lead" — verify: e2e.
12. A double click on Approve sends one request; while it runs both buttons are disabled — verify: e2e counting POSTs on the mock.
13. Each error scenario shows its words: 403 `forbidden` "You can't do this." plus server message; `csrf_failed` "Press the button again" with one session read and no second POST; 409 "This changed while you were working…" with the item re-read; 422 the server message and first field message; 429/503 "Try again shortly."; a dropped connection or 500 shows "We couldn't confirm…" and locks the button until the revision changes or reload — verify: mock scenarios, e2e, and unit test of the lock.
14. `/work/4205` shows "{by} returned the release on {date}" and blockers as reference text; it does not show "Send for decision again" or a note quote — verify: page text.
15. `/work/4206` shows "Client workaround on file" and `/work/4205` does not — verify: page text.
16. `/work/4207` (owner-needed) shows the held line, "PMO Lead assigned" as OWNER NEEDED, and the people and eligibility from decision-appointments, with no decision form; the decision-appointments call is made only on that item — verify: network panel on 4207 and on 4201.
17. `/work/4208` shows "Prepare release readiness" and pressing it sends one `POST /release-register` `{action:"prepare_readiness", expected_revision, case_revision}` and re-reads; `/work/4209` (no such action) shows no such button — verify: e2e on both.
18. `/work/4210` shows "Release ready", the record count, and the record-release form; the submit stays off until date, reference, note, a PDF and the "I have checked this file" box are all set — verify: e2e toggling each.
19. Submitting the release form uploads the PDF to the item's `case_id` (`POST /cases/{case_id}/files`), then sends `observe_release` with `upload_id`, `checked:true`, `readiness_id` (the single id), and null `environment`/`private_log_id` when blank; `upload_id` is never in `evidence_id` — verify: network panel; unit test on the body; `// @ts-expect-error` test that an `UploadId` cannot be passed as `evidence_id`.
20. An uncertain observe_release (dropped connection) re-reads the register; a non-null `release` with the same reference is shown as recorded, otherwise the form locks with "We couldn't confirm that this was recorded…" and no second POST is sent — verify: e2e with the scenario; count POSTs.
21. `/work/4211` shows "Release recorded {date} · {reference}" and no record form — verify: page text.
22. The client UAT row shows the `outcome` words, "No response recorded" for null, and "Proof is out of date" when `proof_current` is false; a failing client-testing read hides only this row and the rest loads — verify: unit test and mock 500 on that route.
23. Not drawn: stage and issue figures, Tola cards or step lists, "Send for decision again", PMO Lead and PM names on the first row, Reject — verify: page text search on 4201, 4205, 4208 finds none.
24. Wrong person: for a viewer the server gives no `verdicts` and no `actions`, no write control exists; a forced POST that the mock answers with 403 shows the mapped error — verify: e2e with the 403 scenario on 4201.
25. Wrong record: `/work/4290` (mock 404) and a work id the account cannot see against Django 8030 both show exactly "This record is unavailable." — verify: open both and compare text.
26. Against live Django 8030 (account with a delivery-release item), the phases, checklist and `proofs[]` shown match `GET /api/v1/work/{id}/release-register` and `/planning-exit` as returned — verify: compare page with `curl` JSON using the session.
27. No write is made by page load, polling or navigation; the three POSTs exist only in `ReleaseActions.tsx` through `useWorkCommand` — verify: `grep -rn "liveApi.POST" frontend/src/features/delivery-release` lists none outside it; e2e asserts zero POSTs on load.
28. `ReleaseActions` is registered as `adapter.Actions` and `frontend/src/features/workspace/**` has no changes — verify: `git diff --stat origin/main` lists no path there; the adapter test registers the release adapter and gets sections and three descriptors.
29. At 1440 and 390 widths each of the six states matches the SCR-44 boards for the parts that remain, with no horizontal scroll and no empty heading or gap where a part is hidden — verify: screenshots at both widths against `design/screens.md` SCR-44 artboards.
30. New tests exist for `releaseModel` (states, statuses, precedence), the adapter (`read`, `sections`, `commands`, tokens stay null) and the form (proof gating, double press, uncertain lock); `src/api/live-schema.d.ts` is unchanged apart from a regeneration to 1.25.0 or later — verify: test files present; `git diff --stat`.

## Out of scope
- The "Decide" panel figures and Tola's check (DC-3); "Send for decision again"; the Reject verdict.
- Client-testing writes, the `/pack` routes, the planning-exit workaround link write (`POST .../planning-exit/workaround`), and the source and gate capture actions (`capture_source`, `verify_source`, `capture_gate`, `verify_gate`, `record_progress`, `record_glpi_request`) even though `actions[]` may list them. A listed action with no form is not drawn.
- Appointing a PMO Lead (decision-appointments writes, policy review); the page only reads and links to Setup roles.
- SCR-43 (F-113), SCR-45 go-live, and SCR-46 hypercare criteria and observations (F-115B).
- Any change to `frontend/src/features/workspace`, the backend, or the contract.

## Assumptions
- Panel keys for the release line are read from live `GET /work/{id}` by the builder and the adapter registers on them; if the work read lists one panel only, the adapter's `read` fetches the other route itself. Reason: keys are not named in the contract.
- Revision tokens come from each read's own `expected_revision`/`case_revision`, not from the work item. Reason: both release routes return them, and the POST must match that read.
- With `verdicts[]` lacking `return`, only Approve is drawn, and the reverse. Reason: the server lists what the viewer may do.
- Evidence is optional only for a direct approval (`can_approve_directly`); every other decision requires a chosen proof. Reason: PSL answer 1 and the binding proof rule.
- Blocker references are plain text unless an issue route for the id is provided. Reason: the read gives `{id, reference}` only.
- `current_scope:false` hides the gates and shows a plain line. Reason: the field's meaning is not documented; the server message wins if present.
- A ready state is `readiness_ids[]` non-empty; preparing is approve with none. Reason: no explicit readiness status field exists.
- Mock fixture ids 4201 to 4212 are free numbers (the shapes are the contract). Reason: no live fixtures exist.
- The record-release `readiness_id` is sent automatically only when exactly one exists. Reason: it names which readiness the release observes; with several, guessing would record the wrong one.

## Conflicts with the boards
1. Readiness board draws a "Mark release ready" button and a Tola step card; live has a PM click "Prepare release readiness" (`prepare_readiness`, D-13) and no step data. Recommendation: draw the button with the live label, hide the Tola card.
2. Decision board's "Approve for release" needs a chosen evidence and the note field says "(needed to return)"; the board draws no evidence control. Recommendation: add an "Evidence" select (optional for a direct approval, required otherwise); design engineer to draw it. The "Approved by PMO Lead" line with name and time is also not drawn on the decision boards; recommendation: add it to the decision row.
3. Returned board's quoted note and "Send for decision again" and "Open ISS-0301" button: live gives no note text, no resend operation, and only a blocker reference. Recommendation: hide the quote and the resend, show blockers as text or links.
4. Decision board's "What you're deciding" figures and all Tola check cards are removed (DC-3). Recommendation: hide.
5. Gates list: the board draws four rows; live gives phases and checks (more rows, D-14 words) plus the UAT outcome. Recommendation: draw the live groups; keep the board's row look and order for Planning decision.
6. Added to the page, not on any board: the "Record the release" form (board says deployment is recorded in hypercare). Decided by the coordinator: build it here when `actions[]` lists it; F-115B will not build it.
7. Owner-needed board has no people list; the spec draws appointments from decision-appointments. Recommendation: keep, small and read only.

## Questions
1. Resolved by the coordinator: the release record (`observe_release` with the checked PDF) is built here, only when `actions[]` lists it. F-115B will not build it.
2. Resolved by PSL answer 1: an eligible current PMO Lead approves their own named planning exit directly, with their signed-in approval as the record and an optional note; no evidence needed. Every other decision follows the proof rule.
3. How should the blocker issue link read? Options: (a) plain reference text now, link once an issue route is supplied; (b) link to the project's issues page; (c) hide blockers. Recommendation: (a) (coordinator agreed).
4. Reject is in `verdicts[]` but not on the board. Options: (a) hide; (b) draw a third button. Recommendation: (a) (coordinator agreed).
