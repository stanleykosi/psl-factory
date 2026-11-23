# A change request can be logged, assessed, decided and authorised from its work page (part 1 of SCR-31)

> Tasks: FE-CHANGE (part 1). Architecture: v9 package; contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas with the D-173/D-181 exceptions in `design/review.json`; screens: SCR-31 (boards below).

## Summary
- A `pmo-change/v1` work item at `/work/{id}` draws the change request: reference, category, module, the stage track, the four impact assessments, the deciders and the authorisation. It reads live `GET /work/{id}/change`.
- A PM can log a new change (`capture`) on the project's change list and open it. Standard changes use `preapprove` and `bind_standard`.
- A PM can record a team's impact assessment (`assess`), a decider's verdict (`decide`) and the authorisation (`authorize`). Every write sends both revision tokens and handles 201 and 409.
- Only the deciders that live says are required are shown (D-5). The screen never assumes all five.
- Notice, execution, go-live note, signatures, close, retry, cancel and restart are F-112B. The track draws them, but no control acts on them here.
- The build starts only after F-85 (lane C, PR #101) is on main. Written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.

## Context
Worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d` (origin/main b8542c79, API 1.24.0), frontend in `frontend/`.
- No SCR-31 code exists. Nothing in `frontend/src` or `frontend/mock` mentions the change line or `ordinary-changes`.
- Shared frame (lane C owns, unchanged here): `frontend/src/features/workspace/` (`Workspace.tsx`, `Sections.tsx`, `labels.ts`, `useWorkspaceStep.ts`). F-85 adds `workspace/adapter.ts` (`LineAdapter`, `CommandDescriptor`, `registerLineAdapter`), `EvidencePicker.tsx` and `evidence.ts`. This feature uses them as specified there.
- Live client: `frontend/src/api/client.ts` (`liveApi`, `call()`), `frontend/src/api/live-schema.d.ts`, `frontend/src/api/errors.ts`.
- The change list entry point: `frontend/src/features/projects/RegistersTab.tsx` (SCR-11 Changes register, today v7).
- Mock: `frontend/mock/server.mjs` and `mock/session.mjs` (live-shaped reads).
- Live operations (`python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live <METHOD> <path> 3`; note: `oa.py` returned "NOT IN live" for these four paths in the spec writer's run, so the shapes below were read from the contract file directly):
  - `GET /api/v1/work/{work_id}/change`
  - `POST /api/v1/work/{work_id}/change` (201)
  - `GET /api/v1/projects/{case_id}/ordinary-changes`
  - `POST /api/v1/projects/{case_id}/ordinary-changes` (201)
- Line key is `pmo-change/v1` (the board's "change_request" is the adapter's name).

## Contract

### Change read: `GET /api/v1/work/{work_id}/change`
200 body (all fields always present): `expected_revision`, `case_revision`, `change_id`, `change_version_id`, `category` ("Standard"|"Normal"), `stage` (string), `finding`, `next_action`, `authorization_id` (int|null), `authorization_choices[]` (int ids, max 20), `impact[]` (max 4) `{team: Engineering|QA|Infra|Security, status, assessment_id|null, summary|null, effort|null (string)}`, `assessors[]` (teams the caller may assess), `decisions[]` `{role: Product|Engineering|Client|Engineering Lead|Security Manager, status, verdicts[] (approve|return|reject)}`, `documents[]`, `evidence[]` `{id, version, kind}`, `can_close`, `closure_id`, `can_restart`, `can_authorize`, `deployment_authorized` (always false), `jobs[]`.
Errors: 401, 403 (`csrf_failed` is not no-access), 404 (one wording "This record is unavailable." for missing and not yours), 422, 503, network. Mapping as in F-85.

Mapping to the page (presentation only; nothing here decides access):
| Page part | Source |
|---|---|
| Reference, category tag, module | `GET /projects/{case_id}/ordinary-changes` `records[]` row whose `version_id === change_version_id`; if no row matches, show category only and omit reference and module. Never invent |
| Title | `work.title` from `GET /work/{id}` |
| Status tag | derived from `stage` and counts (table below) |
| Stage track | `stage` (codes source, impact, authorization, notice, execution, go_live, signatures, complete) grouped into five steps |
| Impact table | `impact[]`, four teams in the order Engineering, QA, Infra, Security |
| Record an assessment | shown for a team only when it is in `assessors[]` |
| Deciders | `decisions[]` as served; one row per element |
| Record a decision | per row, only the verdict buttons listed in that row's `verdicts[]`; an empty `verdicts` means no control |
| Record the authorisation | only when `can_authorize === true` and `authorization_id === null` |
| Next / finding | `next_action`, `finding` (shown when non-empty) |

Stage track grouping (D-6): `source`, `impact`, `authorization` -> step 1 "Authorization"; `notice` -> 2; `execution` -> 3; `go_live` -> 4; `signatures`, `complete` -> 5 "Signatures". A stage value outside the eight codes marks no step and shows the raw `stage` text. Part 1: steps 2 to 5 are drawn (done, current, upcoming) but have no control and no sub-page.

Status tag (derived; no live field): `stage` source or impact with fewer than all four impact rows recorded -> "BEING ASSESSED · {recorded} OF 4"; `stage` impact/authorization with all four recorded and any decider not `approve`d -> "DECIDING · {approved} OF {decisions.length}"; any decider verdict `reject` -> "REJECTED"; `authorization_id` null, `can_authorize` and all required deciders approved -> "APPROVED · TO AUTHORISE"; `authorization_id` set -> "AUTHORISED"; otherwise the raw `status` text of the first row not recorded, else no tag. How a recorded status is recognised comes from `impact[].assessment_id !== null` and a decider's approval from its `status` text (assumption 3).

Required deciders (D-5): the screen draws exactly the `decisions[]` the read returns. Standard and emergency changes show whatever live returns. No role is added or hidden client-side, and the screen never asks for all five.

### Change list and log a change: `GET/POST /api/v1/projects/{case_id}/ordinary-changes`
- Read: `{case_revision, records[] {id, version_id, reference, category, module, description} (max 50), evidence[] {id, version, kind}, catalogue[] {key, module, roles[] Product|Engineering}, catalogue_finding}`. List rows show reference, category tag, module, description. Open row -> the change's work page (by `pmo-change/v1` work item for that change; the row carries no work id, so a row opens only when the project work list (`GET /work` filtered by `case_id` and `line`) contains one whose change read has the same `change_version_id`; otherwise the row is read only. Assumption 5).
- `capture`: `POST` `{action:"capture", case_revision, reference, category, module, description, reason, evidence_id}` -> 201 `{id, case_revision}`. All fields required; `evidence_id` is an integer chosen from `evidence[]` (assumption 1).
- `preapprove`: `{action, case_revision, key, role, verdict, evidence_id, note}`. `bind_standard`: `{action, case_revision, version_id, key, evidence_id, note}` (body shape per contract). Both drawn only for a change in `Standard` category and only when `catalogue[]` has an entry; the `key` is chosen from `catalogue[]`, never typed. If `catalogue_finding` is non-empty it is shown and the Standard path is disabled.
- Errors: 409 case revision changed (reload and keep typed text), 422 with `fields[]` shown beside the named field, 413/415/429 as F-85.

### Writes: `POST /api/v1/work/{work_id}/change` (201)
Response `{work_id, state, revision, record_id}`. After 201 re-read the change (the read is the truth); keep the page's work revision from the response only for the next call.
Every body carries `action`, `expected_revision` and `case_revision` from the last read, and `change_version_id` from the read.
- `assess`: `{action:"assess", expected_revision, case_revision, change_version_id, contributor, cost_impact, timeline_impact, client_facing, production_impact, scope_items, outputs, effort_person_days, evidence, note, proof_upload}`. All keys required by the contract. Form: team (one of `assessors[]`), assessment note (`note`, 1 to 4000), effort in person-days (string up to 32, sent as typed, blank -> `null`), four yes/no/unknown choices (`cost_impact`, `timeline_impact`, `client_facing`, `production_impact`; "Not known" -> `null`), scope items (list, each 1 to 240, blank -> `null`), the five output notes (discipline, timeline, cost_resource, risk, dependency; blank -> `null`; the whole `outputs` is `null` when all blank), proof (`evidence` id chosen from `evidence[]`; `proof_upload` is the F-85 `upload_id` or `null`). Unknown is `null`, never `false` or 0.
- `decide`: `{action:"decide", ..., role, verdict, evidence, note}`. `role` is the row's role, `verdict` from the row's `verdicts[]`, `note` 1 to 4000 required, `evidence` an id from `evidence[]`. "Return" and "Reject" show a confirm step with the note required.
- `authorize`: `{action:"authorize", ..., commercial}`. `commercial` is one of `authorization_choices[]` chosen by the person, or `null` when the list is empty. Confirm step before sending ("This commits the change. It cannot be undone here.").
- Idempotency: live has no key on these. The submit button locks while pending; a second press is ignored. After a network failure or 5xx the form shows "We could not confirm this was saved" and offers only "Check again", which re-reads the change and does not resend. A 201 whose re-read shows the action already applied is treated as saved.
- Errors: 409 -> "This change was updated by someone else. Reload to see it." keeping typed text; 403 -> "You can't record this."; 404 as above; 422 `fields[]` beside the field; 413/415/429/503 as F-85.

### Permission and tenant rule
Access is whatever the backend allows for the signed-in person; 404 for missing and not yours. Controls come from the read (`assessors[]`, `decisions[].verdicts`, `can_authorize`), never from the person's role in the client (DC-5). A person who cannot act sees the record read only with no "you can't" banner. The case id for uploads and writes is the loaded item's, never typed.

### Adapter and files
Own folder `frontend/src/features/change-request/` (see Lanes). Registered through F-85's `registerLineAdapter` under panel key `change` (assumption 2). `commands()` returns descriptors for `assess`, `decide`, `authorize` with `tokens {expected_revision, case_revision}` and `idempotency.field === null`; `disabledReason` set when the read blocks the action. Sections use existing kinds in `workspace/labels.ts`; the stage track, impact table and decider list may need a small bespoke component in this folder (not in the frame).

### Screen states (each of Overview, Impact form, Decision, Rejected, Authorise)
- Loading: the work item loading state, then the change loading skeleton.
- Error: mapped messages above with Try again; a failed re-read after a write keeps the last good read and shows "Couldn't refresh".
- Empty: change with no impact rows recorded -> four "Not given yet / MISSING" rows; a project with no changes -> "No changes logged yet" with the Log a change control (when the caller may capture).
- Success: as drawn.
- Unknown: `effort` null shows "Not recorded"; never 0 or "0 days".

### Fixtures (mock serves, ids free)
- `4201` Normal, stage impact, 3 of 4 recorded, `assessors:["Security"]` (SCR-31 default and impact).
- `4202` stage authorization, `decisions` of Product (approve), Engineering (approve), Client (status waiting, `verdicts:["approve","return","reject"]`), Engineering Lead and Security Manager rows (timeline affected), deciding (decision).
- `4203` a Client `reject` recorded (rejected).
- `4204` all required approved, `can_authorize:true`, `authorization_choices:[11,12]`, `authorization_id:null` (authorise).
- `4205` read only for the caller (`assessors:[]`, empty `verdicts`, `can_authorize:false`); `4206` 404.
- `4207` a Standard change with a non-empty `catalogue`; `4208` with `catalogue_finding` set.
- Mock `POST` answers 201, and scenarios for 409, 422 with `fields`, 403 `csrf_failed`, 413, 429, 503 and dropped network.
Live: `GET /projects/{case_id}/ordinary-changes` for an existing change case and `GET /work/{id}/change` shown via curl with the session.

## Boards: part 1 and F-112B
Source: `design/canvas/project/SCR-31-<desktop|mobile>[-state].dc.html`. Each state has a desktop and a mobile board.
| State | Boards | Part |
|---|---|---|
| default (change detail with impact table and deciders) | SCR-31-desktop, SCR-31-mobile | part 1 |
| impact (record an assessment) | SCR-31-desktop-impact, SCR-31-mobile-impact | part 1 |
| decision (several deciders) | SCR-31-desktop-decision, SCR-31-mobile-decision | part 1 |
| rejected | SCR-31-desktop-rejected, SCR-31-mobile-rejected | part 1 |
| authorise | SCR-31-desktop-authorise, SCR-31-mobile-authorise | part 1 |
| notice | SCR-31-desktop-notice, SCR-31-mobile-notice | F-112B |
| execution | SCR-31-desktop-execution, SCR-31-mobile-execution | F-112B |
| go-live-note | SCR-31-desktop-go-live-note, SCR-31-mobile-go-live-note | F-112B |
| closed | SCR-31-desktop-closed, SCR-31-mobile-closed | F-112B |

Part 1: 10 boards. F-112B: 8 boards. The "log a change" form and the Changes list have no board; see Questions 1.

## Lanes
- Frontend lane (all of this feature): `frontend/src/features/change-request/**` (adapter, stage track, impact table and form, deciders and decision form, authorise form, log-a-change form, hooks, css), `frontend/src/api/types.ts` (live change types only, additive), `frontend/mock/**` (new `change.mjs` plus its registration in `server.mjs`), tests `frontend/src/features/change-request/*.test.ts(x)` and `frontend/e2e/change-request.spec.ts`.
- Backend lane: none. No backend, migration or contract change.
- Integration owner: lane D coordinator. Shared files and owners: `frontend/src/features/workspace/**` is lane C's (unchanged; use F-85's adapter, picker, `Sections`; if the frame must change, stop and raise it as a lane C dependency); `frontend/src/features/projects/RegistersTab.tsx` is shared (limited to the link into the change list in Question 2); `frontend/src/api/*` shared (additive types only).
- `delivery/config.json` protected paths stay unchanged.

## Acceptance criteria
1. `/work/4201` (mock, Next 4990, mock 4991) shows the title, category tag, the five-step track with step 1 current, four impact rows (three recorded, Security "Not given yet" and MISSING) and "Record an assessment" only on the Security row — verify: open page; `e2e/change-request.spec.ts`.
2. Stage grouping: stages source, impact, authorization all light step 1; notice, execution, go_live, signatures/complete light 2 to 5; an unknown stage lights no step and shows the raw text — verify: unit test on the stage mapper.
3. Steps 2 to 5 have no button or link that sends a request in any state — verify: e2e asserts no control with those labels; `grep -rn "document_review\|operate_delivery\|\"close\"\|execution\|restart" frontend/src/features/change-request` finds no request code.
4. The decider list shows exactly the roles in `decisions[]` (fixture `4202` five rows, a Normal client-internal fixture with two rows shows two); the page never shows "all five" text and no row not in the read — verify: unit test per fixture and page.
5. A decider row shows only the verdict buttons in its `verdicts[]`; an empty list shows none; fixture `4205` shows no write control and no banner — verify: e2e.
6. Recording an impact assessment sends `POST /work/4201/change` with `action:"assess"`, `expected_revision`, `case_revision`, `change_version_id`, every contract key present, unknown choices as `null`, `effort_person_days` as the typed string, and the page then shows the team as recorded after re-read — verify: unit test on the body builder; e2e checks the request body in the mock log.
7. An empty effort is `null` and renders "Not recorded"; the page never shows "0" for an unrecorded effort — verify: unit and e2e.
8. Recording a decision sends `action:"decide"` with `role`, `verdict`, a non-empty `note` and `evidence` id from `evidence[]`; with an empty note the Record button stays disabled and no request is made — verify: unit and e2e.
9. A return or reject asks for confirmation and a note; cancelling sends nothing — verify: e2e.
10. After a `reject` (fixture `4203`) the page shows REJECTED, the reject note and who recorded it only if the read carries it, and "You can log a new change later"; no authorise control — verify: e2e on `4203` against the rejected board.
11. `/work/4204` shows "Record the authorisation" with a choice from `authorization_choices[]` (or none when empty), a confirm step, and sends `{action:"authorize", ..., commercial}` once; the Authorised by, Authorised on and proof fields from the board are not drawn — verify: e2e and body assertion; DOM has no "Authorised by" input.
12. `can_authorize:false` or a non-null `authorization_id` shows no authorise control; the authorised state shows "Authorised" and whatever `authorization_id` allows, no person or time — verify: e2e on fixtures.
13. `deployment_authorized` is false in every state and the page never says deployment is authorised — verify: unit test on the mapper; grep copy.
14. A 409 on any write keeps the typed text, shows "This change was updated by someone else. Reload to see it.", and sends nothing automatically; Reload re-reads and keeps the typed note where the field still exists — verify: mock scenario `conflict`; unit.
15. A 422 with `fields[]` shows each message by its field; a 403 `csrf_failed` refreshes the session and says "Press save again" without resending; 413, 415 and 429 show their wording — verify: mock scenarios; fetch counts in unit tests.
16. A dropped network or 5xx on a write shows "We could not confirm this was saved" with "Check again" only; Check again re-reads and never resends; double click on submit sends one request — verify: unit with fake fetch counting calls.
17. A re-read after 201 failing leaves the form locked with "Couldn't refresh" and Try again, not a repeat of the write — verify: unit.
18. `/work/4206` and a live work id the caller cannot see both show exactly "This record is unavailable." — verify: open both; unit on the 404 body.
19. The change list for a project shows each record's reference, category tag (Standard or Normal), module and description from `ordinary-changes`; an empty list shows "No changes logged yet" — verify: e2e and live curl comparison of the same project.
20. Log a change sends `capture` with reference, category, module, description, reason, `evidence_id` and `case_revision`; every field is required before the button enables; the `evidence_id` can only be chosen from the read's `evidence[]`; a 201 refreshes the list with the new row and a 409 keeps the typed text — verify: unit and e2e.
21. For a Standard change with catalogue entries, `preapprove` and `bind_standard` send the contract bodies with `key` chosen from `catalogue[]`; with `catalogue_finding` non-empty the Standard path is disabled and the finding is shown (fixtures `4207`, `4208`) — verify: e2e; there is no free-text key input.
22. A control that needs an `evidence` id and has an empty `evidence[]` is disabled with "No proof file is recorded for this case yet"; no write is sent without an evidence id — verify: e2e with a fixture whose `evidence` is empty.
23. Against live Django 8030 (Postgres, `live-lead`), `GET /work/{id}/change` for a `pmo-change/v1` item renders reference, impact and deciders matching the JSON from curl; one `assess` or `decide` on a test change returns 201 and the page re-read shows it — verify: compare page and curl; record the response.
24. Revision handling: the work `expected_revision` and `case_revision` in every body equal the last read; after a 201 the next write uses a freshly read pair, never the old one — verify: unit test sequence.
25. A `null` or absent optional field renders "Not recorded"/omitted, never 0; a `summary` null impact row shows "Not given yet" — verify: unit on the mapper.
26. The agent card, "Recorded by PM · date", person names on deciders, "Authorised by" and any "milestone scope now includes" line are not drawn and leave no empty gap — verify: e2e DOM absent; screenshots.
27. Layout at 1440 and 390 matches the part 1 boards (default, impact, decision, rejected, authorise) for the parts that remain, with the keyboard and focus order working on the forms and confirm steps — verify: screenshots at both widths against the 10 boards; Tab through each form.
28. The shared frame is unchanged: `git diff origin/main -- frontend/src/features/workspace` is empty — verify: that command.
29. New unit tests cover the stage mapper, status tag, assess/decide/authorize/capture body builders, null handling and the write error mapper; `npm run lint`, `npm run typecheck`, `npm test` pass — verify: `delivery/checks.sh`.

## Out of scope
- F-112B: notice and go-live note documents (`document_review`, `documents[]`, receipts), execution evidence, close with PM and client signatures (including `owner_applicability`), `operate_delivery` (retry, cancel), `restart`, `change-milestone-link`, `GET /projects/{case_id}/change-versions/{version_id}`, `jobs[]`, and the four boards notice, execution, go-live-note and closed (8 boards).
- Showing "Authorised by {name} · {time}"; Tola's step card, `agent_note` and cited records; "milestone scope now includes" lines (D-182, DC-3).
- Names beside deciders, or "Recorded by PM · date" (not in the read).
- Uploading a file and turning it into an evidence id, beyond choosing from `evidence[]` and passing F-85's `upload_id` as `proof_upload` (D-1).
- Sending the change notice to the client, any message, or any deployment.
- Changes to the shared frame, `src/features/workspace`, the OpenAPI contract or the backend.
- Choosing who may capture or decide on the client side; no role check outside the read.

## Assumptions
1. `evidence` and `evidence_id` are chosen from the read's `evidence[]` (already recorded proofs). Reason: D-1 gives no upload-to-evidence call. Where a person needs a new proof, the write is held with "No proof file is recorded for this case yet"; flagged for the design engineer.
2. The adapter is registered under panel key `change`; if `GET /work/{id}` does not list that key for `pmo-change/v1`, the work page opens the change view when `line === "pmo-change/v1"`, reading `/work/{id}/change` directly. Reason: the contract does not state the key.
3. The status tag is derived, not served: recorded rows from `assessment_id !== null`, an approval from the decider `status` text (matched case-insensitively on "approve", unknown text shows as given). Reason: `status` is an unconstrained string.
4. Reference, module and description come from `ordinary-changes` by `change_version_id`; the change read carries none. Reason: the only source.
5. A change list row opens a work page only if a matching `pmo-change/v1` work item can be found; the list row carries no work id. Reason: no such link in the contract. If none, the row is read only.
6. `assess` sends `contributor` from the selected team and the PM records on behalf of the team (the board says teams do not log in). Reason: board and contract agree.
7. `proof_upload` is the F-85 `upload_id` and `evidence` is a separate required integer. Reason: the contract needs both and they are different ids.
8. Start-the-change from the drawer (`POST /work` with line `pmo-change/v1`) is not part of this feature; the log-a-change form creates the change record only. Reason: not in the readiness scope.

## Questions
1. The "Log a new change" form and the Changes list have no board, and the readiness scope requires them. Options: (a) build a plain form and list using existing form and list components, flagged for a board later (recommended; the API requires it); (b) hold both until a board is drawn; (c) hide the list and log form and open changes only through the work page. Context: nothing else in part 1 lets a PM log a change.
2. Where the change list lives. Options: (a) the existing SCR-11 Changes register tab (`RegistersTab.tsx`) lists `ordinary-changes` with a "Log a change" button, the board crumb path "Projects / Lagoon Health / Registers / Changes / CR-0031" (recommended; it matches the board crumb); (b) a new page; (c) only inside the work page. Context: the boards show the change under Registers > Changes.
3. The default board draws only Product, Client and Engineering Lead and the decision board draws all five with the line "Open question for the backend team: must all five approve". D-5 settled it. Options: (a) draw only `decisions[]` as served and remove the open-question text (recommended); (b) always draw five. Context: Standard and emergency changes use their own rules.
4. Impact board versus contract: the board has a note, effort and proof; the contract also requires cost, timeline, client-facing and production impact, scope items and five output notes. Options: (a) add the four yes/no/unknown choices and an optional collapsed "More detail" with scope items and output notes (recommended); (b) show all fields open; (c) send nulls for fields the board does not draw. Context: sending nulls drops information the backend uses for D-5's required deciders (timeline, client-facing).
5. Authorise board draws "Authorised by", "Authorised on" and a proof upload. `authorize` accepts only `commercial`. Options: (a) hide those three fields; show an optional "Linked commercial item" choice only when `authorization_choices[]` is non-empty (recommended); (b) show them disabled and unsaved (misleading); (c) hold the authorise form. Context: D-182 says hide what the API cannot fill.
6. Rejected board says "The change is closed as rejected" and quotes the client's note and who recorded it. The read has no stage code for rejected and no note. Options: (a) show REJECTED from a `reject` verdict in `decisions[]` and the `finding` text, with no quote or recorder (recommended); (b) hide the whole rejected state until live returns a stage; (c) draw the board as is with placeholders. Context: stage codes are only the eight in D-6.
7. Page frame: the boards draw a project page with crumbs, tabs and the title; the work frame `/work/{id}` has none of the project tabs. Options: (a) draw the title, crumb link back to the project's Registers tab and no tab bar (recommended; consistent with F-85's crumb decision); (b) rebuild the project tab bar on the work page; (c) open the change inside the project route. Context: F-85 conflict 6 chose the crumb approach.
8. Mobile boards for the four wide parts (impact table, five-step track): confirm the track becomes a vertical list and the impact table stacks as in the mobile boards. Options: (a) follow the mobile boards exactly (recommended); (b) scroll horizontally. Context: boards exist, checked only by screenshot.

## Conflicts with the boards
Places where the spec adds, moves or removes something a board draws (the design engineer decides once; each is also a numbered Question):
1. Added: the four yes/no/unknown impact choices, scope items and output notes on the impact form (Question 4). Recommendation: add a compact set with the rest collapsed.
2. Removed: "Authorised by", "Authorised on" and the proof upload on the authorise board; added an optional commercial item choice (Question 5). Recommendation: as the spec.
3. Removed: the open-question note and the fixed five-decider list (Question 3). Recommendation: as the spec.
4. Removed: Tola's card, "Recorded by PM · 11 Nov", decider person names ("Femi Ade") and the "next: record the Engineering Lead's and Security Manager's decisions" wording is replaced by `next_action` from the read. Recommendation: as the spec (D-182, DC-3).
5. Changed: the rejected board's quote and "closed as rejected" are replaced by `finding` text (Question 6). Recommendation: as the spec.
6. Added: confirm step on authorise, return and reject; the "Check again" recovery state; the log-a-change form and list (no board; Questions 1 and 2). Recommendation: build and flag.
7. Moved: the board crumb "Projects / Lagoon Health / Registers / Changes / CR-0031" and project tabs sit on `/work/{id}`, which has no project tabs (Question 7). Recommendation: crumb back link only.
