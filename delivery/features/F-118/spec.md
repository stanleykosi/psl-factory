# Closure reads the live checklist, Finance confirms milestone notifications, and the Head of PMO closes or returns the project

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0 (main b8542c79). Design: approved 13 Nov canvas under the recorded exception in `design/review.json` (D-173/D-181); screens: SCR-49 (10 artboards in `design/canvas/project/`: `SCR-49-{desktop,mobile}` and the same with `-blocked`, `-decision`, `-returned`, `-closed`). Written against F-85's spec (`delivery/features/F-85/spec.md`). **Build starts only after F-85 (PR #101) is on main.**

## Summary
- The Closure step of a project's Delivery tab reads `GET /projects/{case}/delivery/{dossier}/closure-checklist` and draws all eight live checks (the six the boards draw plus "Current project scope" and "PM closure report"), with the blocked, report-ready, decision, returned and closed states.
- A person with current Finance authority sees a "Confirm milestone notifications" form (`GET`/`POST .../finance-confirmation`). It is worded as milestone notifications confirmed, never "debts confirmed".
- The Head of PMO closes or returns with `POST /work/{id}/reviews` (`kind:"closure"`), carrying both revision tokens, the closure document `version_id` and the decision `evidence_id` (D-26). The PM replaces the report after a return with `POST /work/{id}/closure-report`.
- "Still open after closure" is drawn from the protected `debt` block of the checklist, with its as-of date and the unknown coverage. Unknown stays "Not recorded", never 0. It is hidden when the viewer has no Finance read.
- Tola's step card, "Ask Tola" and the read-only-project claim are hidden (DC-3, D-182). The line is started with `GET /intake-sources` and `POST /work` (`delivery-closure/v1`).

## Context
Where this lives today (lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`):
- Project page: `src/app/projects/[caseId]/(tabs)/[tab]` and `src/features/projects/DeliveryTab.tsx` (imports `Panel` from `@/components`; `ProjectJourney.tsx` draws the DELIVERY-flow step map). No Closure view exists. `mock/fixtures/work/W-2003.json` is the only closure fixture (v7 generic, line key `delivery_closure`); it is not live-shaped.
- Shared frame (lane C owns, do not change): `src/features/workspace/` with F-85's `adapter.ts` (`LineAdapter`, `CommandDescriptor`, `registerLineAdapter`), `EvidencePicker.tsx`, `evidence.ts`, `Sections.tsx`. Work item page: `src/features/work-item/`.
- API: `src/api/client.ts` (`liveApi`, `call()`, `refreshSession()`), `src/api/live-schema.d.ts` (already contains `closure_checklist` at line 29692 and the `finance-confirmation` operations), `src/api/errors.ts`.
- Live reads (inspect with `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/projects/{case_id}/delivery/{dossier_id}/closure-checklist 4`):
  - Checklist `GET /projects/{case_id}/delivery/{dossier_id}/closure-checklist?retrospective_id=&report_evidence_id=` returns `{revision, as_of, ready_to_prepare, recorded_closure_id|null, checks[{key,title,status,summary,references[int],finding|null}], debt|null {items[{reference,currency,basis,owed|null,api_url}] (max 25), limited, as_of (date)}, retrospective_url|null}`. `status` is one of `current, held, unknown, closed, recorded, unavailable`. Keys: `context, go_live, hypercare, archive, handover, retrospective, finance, report`.
  - Finance read `GET .../finance-confirmation` returns `{revision, confirmation_id|null, finding|null, milestones[{milestone_id, receipt_id}]}`.
  - `GET /projects/{case_id}/delivery-overview` returns `lines[{key, title, work_id|null, state|null, reference|null, updated_at|null, work_url|null, gate_state, gate_url|null}]`; the `delivery-closure/v1` row gives this line's `work_id` and `reference` (the "CLS-0021" of the boards).
  - `GET /work/{id}` (F-85 shape) gives `revision`, `case_revision`, `state`, `tasks[{can_decide, can_claim, verdicts[]}]`, `blocker`, `next_step`. `GET /work/{id}/history` gives the rows used for the "returned" note.
  - `GET /projects/{case_id}/intake-sources?line=delivery-closure/v1[&field=&parent_id=&before=]` returns `{case_revision, fields[], field, items[{id,label}], next_before}`.

## Contract

### Route and data loading
- View `ClosureView` at `src/features/delivery-closure/`, mounted as the "Closure" step of `DeliveryTab`. Inputs: `caseId` (uuid) and `dossierId` (integer) from the route; the Closure work item is found from the delivery-overview row with `key:"delivery-closure/v1"` (`work_id` may be null: line not started).
- Calls, all through `call(liveApi...)`: `closure-checklist` (re-read after every write and every 409), `delivery-overview` (once), `GET /work/{id}` when `work_id` is set, `finance-confirmation` only when the viewer may confirm (see below), `history` only in the returned state.
- Report and retrospective ids: when the viewer picked a different report or retrospective, the checklist is re-read with `report_evidence_id` / `retrospective_id`; the default is the call without them. The selection is held in view state and shown ("Checked against report <ref>").

### Check mapping (presentation only; nothing here decides access)
| Live `status` | Word | Tone |
|---|---|---|
| `current`, `recorded` | Done | success |
| `held` | Not yet (with `finding`) | warning |
| `unknown` | Unknown | neutral (never rendered as done) |
| `closed` | Closed | success |
| `unavailable` | Not available | neutral |
Rows: `title`, status word, `summary`, `finding` when not null, references as a count ("2 records") with no invented labels. Board names: `go_live` "Go-live accepted", `hypercare` "Hypercare qualified", `archive` "Archive verified", `handover` "Handover acknowledged", `retrospective` "Retrospective saved", `finance` "Finance confirmation" (sub-line "Milestone notifications confirmed by Finance"), plus `context` "Current project scope" and `report` "PM closure report". Where the API `title` differs, the API `title` is shown and the board name is a tooltip-free sub-line; presentation question Q2.
- `retrospective` held: "Write the retrospective" links to `retrospective_url` when not null (SCR-33, built by F-119); when null the link is omitted.

### Screen states (desktop and mobile, same data)
- **Loading**: skeleton rows (existing `ProjectStates` loading). **Error**: 401 signed-out state with `/sign-in?next=`; 403 `csrf_failed` refreshes the session and says "Refresh your session and try again" (not shown as no-access); 404 "This record is unavailable." (same words for missing and not yours); 429/503 "Try again shortly" with Try again; network "We couldn't reach the server." Reads are retried by Try again only.
- **Blocked** (`SCR-49-*-blocked`): `recorded_closure_id` null, no closure work (`work_id` null) and `ready_to_prepare:false`. Header tag "Closure · Not yet". Checks listed; "Next" line is the first held check's `finding`. **Mapping flag**: the API has no "blocked before the line starts" state; this spec maps `ready_to_prepare:false` with no closure work to blocked (Q3).
- **Ready to start**: `ready_to_prepare:true` and `work_id` null. Not drawn on a board (Q3): shows the checks and one "Start closure" button (below).
- **Report ready / awaiting Head of PMO** (`SCR-49-*`): closure work exists, `recorded_closure_id` null, a decision task exists and the viewer is not the decider. Tag "Closure · Awaiting Head of PMO"; "Next: The PMO Lead decides on closure." (board words; the role word is "Head of PMO" per memory 13 Nov, "PMO Lead" on the board, Q4). Finance confirmation row "Confirmed" / "Unknown" from the `finance` check.
- **Decision** (`SCR-49-*-decision`): same, and `tasks[].can_decide` is true with `verdicts` containing `approve` (and `return`). Shows checks, "Close the project" and "Return with a note" (note required to return, max length per contract). Buttons shown only for verdicts the task lists; `reject` is not drawn.
- **Returned** (`SCR-49-*-returned`): work `state` is `action_needed` or `ready` after a closure review row in history with status of a return; shows "<actor> returned closure on <date>: "<reason>"" from the latest matching history row, and the "Replace the report" form. If no such history row is found, the note is omitted, not invented (Q5).
- **Closed** (`SCR-49-*-closed`): `recorded_closure_id` not null (check `context` status `closed`). Tag "Closed <date>" using the history/closure time when present, else "Closed". Shows who closed and "verified" only when the work `state` is `verified`. "Still open after closure" from `debt` (below). "The project is now read-only", "moves to Closed in Projects" and the "Support contract: With Support" row are not drawn (no source).
- **Empty debt**: `debt` null means "not visible to you" and the section is omitted; `debt.items` empty shows "No open invoices recorded as of <as_of>."; `limited:true` adds "List is limited; more may exist."

### Still open after closure (D-27)
Rows from `debt.items[]`: `reference`, `basis`, and `owed` formatted with `currency`; `owed:null` shows "Amount not recorded" (never 0). Link each row to its `api_url` page route only if one exists; otherwise plain text. Caption "As of <debt.as_of>". The copy "Closing the project doesn't erase debt" stays, without a milestone number (not served).

### Start the line
- Button "Start closure" (only when `work_id` null and `ready_to_prepare`): opens the existing Start work drawer for `delivery-closure/v1`. Options come from `GET /projects/{case_id}/intake-sources?line=delivery-closure/v1` (field list from `fields[]`, dependent fields via `parent_id`, paging via `next_before`). Request `POST /work` `{line:"delivery-closure/v1", case_id, intake:{dossier_id, inputs:{...}}}`; 201 reloads the overview and checklist. Evidence is not uploaded generically: any field that needs evidence offers only the ids the owning operation lists (D-1). The generic picker from F-85 is not used to mint evidence ids.
- Errors: 409 shows "This changed while you were editing. Reload and try again." with a reload that keeps typed text; 422 shows `fields[].message` under the named field; 403/404 as above.

### Finance confirmation (D-25)
- Shown only when the viewer may confirm: the `GET .../finance-confirmation` read answers 200. A 403 or 404 on that read hides the block entirely (no "no access" message, no existence leak). The read is made only when the `finance` check is not `current`/`recorded`.
- Content: heading "Finance confirmation: milestone notifications"; the list of `milestones[]` (`milestone_id`, receipt link by `receipt_id`) as "Milestone <id>" with "Receipt <id>" (no names are served); `finding` as the reason it cannot be confirmed (when not null the Confirm button is disabled with that text); `confirmation_id` not null shows "Confirmed" and no form.
- Form (when `confirmation_id` null and `finding` null): checkbox "These are all the milestone notifications" (required), an evidence field, a note (required, plain textarea). The evidence field offers the evidence ids the readback allows; if the read lists none, the button is disabled with "No Finance evidence available to attach" (Q6). Request `POST .../finance-confirmation` `{revision, milestone_ids:[all listed ids], inventory_complete:true, evidence_id, note}`; `revision` is the one from the read. 201 `{confirmation_id, revision}`; re-read both reads. 409 re-reads and says "Finance confirmation changed. Review it again."; 422 shows `fields[]`; 429 "Try again shortly".
- The wording never says debts are confirmed.

### Close or return (D-26)
- `POST /work/{work_id}/reviews` body `{kind:"closure", expected_revision, case_revision, version_id, evidence_id, verdict:"approve"|"return", note}`. `expected_revision` and `case_revision` come from the `GET /work/{id}` just read (a null token disables the buttons with "Reload to continue"; never sent as 0). `version_id` is the closure document version and `evidence_id` the eligible decision evidence, both taken from the `report` check `references[]` / the work read; if the checklist does not supply both integers the buttons are disabled with "The closure report isn't ready to decide yet" and a flagged backend question is recorded (Q1, new D-36). No separate claim call.
- 200: re-read work and checklist; the board switches to closed or returned from the new data, not from the button pressed. A double press is prevented by disabling while in flight; a repeat after a lost response is safe because a stale `expected_revision` answers 409 and the screen re-reads and shows the recorded outcome.
- 403 `csrf_failed`: refresh session, "Press again". 403 otherwise: "You can't decide this closure." (do not reveal why). 409: "This changed. Review the latest report." + re-read. 422: first `fields[].message`.
- Note: required when returning (client check plus backend); the note is sent as typed, never edited.

### Replace the report after a return
- Form "Replace the report" shown in the returned state to a person whose work read allows it (`actions[]` lists it or `can_correct`; if neither is present the form is read only, Q5): fields report text (max 16 000 chars, counter), source reference, reason. Request `POST /work/{id}/closure-report` `{expected_revision, case_revision, previous_evidence_id, report_text, source_reference, reason}`; `previous_evidence_id` is the report evidence id from the `report` check (null stays null). 201 `{work_id, state, revision, report_evidence_id}`: re-read, show the new report id in "Checked against report". Errors 413 "The report is too long.", 409, 422 as above.
- Correct sources (`POST /work/{id}/corrections`): not drawn as a form here. The held-check row offers a link to the owning line (F-114, F-115, F-116, F-117, F-119 screens) where the correction is made; corrections for the closure line itself are Q7.

### Idempotency and versioning
Reads send nothing. Writes carry the tokens above (`expected_revision` + `case_revision` on work writes; `revision` on Finance confirmation). Live closure writes have no key field, so the adapter descriptor sets `idempotency.field: null` and builds no uuid. A write is never retried automatically; after any failure the screen re-reads before offering the action again.

### Permission and tenant rules
Every call is made as the signed-in person. The backend answers 404 for missing and not yours alike; the UI shows one wording. No client-side role check decides access: decision buttons follow `tasks[].can_decide/verdicts`, the Finance block follows the Finance read answering 200, the debt block follows `debt` not null. The `case_id` and `dossier_id` come from the route and the overview; no field lets the person type them.

### Adapter mapping (F-85 frame)
New files only under `frontend/src/features/delivery-closure/`: `closureAdapter.ts` registers a `LineAdapter` with key `delivery-closure` (read = closure checklist + overview; `sections()` builds Section objects for the checks, debt and finance rows; `commands()` returns descriptors `closure.decide`, `closure.replace-report`, `closure.finance-confirm`, each with the tokens above, `disabledReason` from the readback only, `successStatuses` `[200]`, `[201]`, `[201]`). The view uses the descriptors to build bodies. The frame (`workspace/*`) is not changed; if the build needs a frame change (for example a panel key for closure), it is named as a dependency on lane C and held.

### Fixture examples (the builder creates these in `frontend/mock/`, live-shaped; mock on 4991)
- Dossier `5001` blocked: `ready_to_prepare:false`, `recorded_closure_id:null`, retrospective `held` with finding "No retrospective saved", finance `unknown`, `debt:null`; overview row `work_id:null`.
- `5002` ready: all checks `current`, `ready_to_prepare:true`, `work_id:null`.
- `5003` awaiting (work `4301`, viewer not decider) and `5004` decision (work `4302`, `can_decide:true, verdicts:["approve","return"]`, `debt:{items:[{reference:"INV-0533",currency:"NGN",basis:"Milestone invoice",owed:"1250000.00",api_url:"/api/v1/..."}],limited:false,as_of:"2026-11-20"}`).
- `5005` returned (work `4303`, history row with reason "Add the client's sign-off on the hypercare summary to the report.").
- `5006` closed (`recorded_closure_id:7`, context `closed`, debt with one item `owed:null`).
- Finance read: one variant with two milestones and `confirmation_id:null`; one with `finding:"Receipt missing for milestone 3"`; one 403.
- Error scenarios: 401, 403 `csrf_failed`, 404, 409 on each write, 422 with `fields`, 429, 503, dropped network.

## Lanes
- **Frontend lane (owner of this feature)**: `frontend/src/features/delivery-closure/**` (new: view, `closureAdapter.ts`, hooks, model, tests), `frontend/src/features/projects/DeliveryTab.tsx` (mount point only), `frontend/src/api/types.ts` (live closure types), `frontend/mock/**` (closure routes and fixtures above), `frontend/e2e/delivery-closure.spec.ts`.
- **Backend lane**: none. Backend question D-36 (where `version_id`/`evidence_id` for `kind:"closure"` come from on a read) goes to `delivery/connect/backend-questions.md`.
- **Integration owner**: lane D coordinator. Shared files and owners: `src/features/workspace/*` (lane C; read only, no change), `src/api/*` (shared; live types and error kinds only), `src/features/start-work/*` (the existing drawer; add the `delivery-closure/v1` line options only if not already there, as a small separate commit), `src/features/work-item/*` (lane C, not touched).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. Open `/projects/<case>/delivery` Closure step for dossier 5001 on Next 4990 with mock 4991: tag "Closure · Not yet"; eight rows (go-live, hypercare, archive, handover, retrospective, finance, scope, report) with the live titles; retrospective shows "Not yet" and the finding; finance shows "Unknown"; no Tola card, no "Ask Tola", no "read-only" text — verify: page and DOM; `frontend/e2e/delivery-closure.spec.ts`.
2. The same step against Django 8030 for a real dossier shows the same titles, statuses and findings as `GET /api/v1/projects/{case}/delivery/{dossier}/closure-checklist` — verify: compare with `oa.py`/`curl` JSON using the session.
3. A status of `unknown` or `unavailable` is never drawn as Done; `held` shows its `finding` — verify: unit test on the check mapper (all six statuses).
4. Dossier 5002 (ready, no work) shows "Start closure"; dossier 5001 (not ready, no work) shows none — verify: e2e; the button posts `POST /work` with `line:"delivery-closure/v1"` and `intake.dossier_id` and a 201 reloads the page — verify: network panel.
5. Start work options come from `intake-sources?line=delivery-closure/v1`; paging uses `next_before`; no field offers a generic file upload for evidence — verify: unit test and network panel.
6. Dossier 5004 as the Head of PMO shows "Close the project" and "Return with a note"; the Return button stays disabled until a note is typed — verify: e2e.
7. Pressing "Close the project" sends exactly one `POST /work/4302/reviews` with `kind:"closure"`, `verdict:"approve"`, `expected_revision`, `case_revision`, `version_id`, `evidence_id`, `note`, and no claim call; the page then shows the closed state from the re-read — verify: network panel and e2e asserting the body.
8. "Return with a note" sends `verdict:"return"` with the typed note; the page then shows the returned state with the note from history — verify: e2e.
9. A viewer with `can_decide:false` (dossier 5003) sees no decision buttons and "The PMO Lead decides on closure." — verify: e2e.
10. A null `revision` or `case_revision` disables the decision buttons with "Reload to continue" and sends nothing; a missing `version_id`/`evidence_id` disables them with the "isn't ready to decide yet" text — verify: unit test on the descriptor and e2e.
11. A 409 on the decision re-reads work and checklist, shows "This changed. Review the latest report.", and does not repeat the write; a double click sends one request — verify: mock scenario `409` plus fetch-count unit test.
12. A 403 `csrf_failed` refreshes the session once and says "Press again"; no automatic second write — verify: unit test counts fetches.
13. A 403 (not csrf) on the decision shows "You can't decide this closure." and no reason; a 404 shows "This record is unavailable." identical to a missing record — verify: mock scenarios; compare the text.
14. Returned state (5005) shows who returned, the date and the note from the latest closure history row; with no such row the sentence is absent, not invented — verify: e2e on 5005 and on a variant without history.
15. "Replace the report" sends `POST /work/{id}/closure-report` with `previous_evidence_id` from the `report` check, text up to 16 000 characters (counter, 16 001 refused before sending); 201 shows the new report id and re-reads — verify: unit and e2e; 413 shows "The report is too long."
16. The Finance block appears for a Finance user on dossier 5003 with milestones listed; for a non-Finance viewer (mock 403 on the read) it is absent with no message, and the rest of the page loads — verify: e2e as both users; wrong tenant or unknown dossier gives the 404 wording.
17. Confirm is disabled until the completeness checkbox, an evidence id and a note are set, and always when `finding` is not null (shown as the reason) — verify: e2e.
18. Confirm sends `POST .../finance-confirmation` `{revision, milestone_ids (all listed), inventory_complete:true, evidence_id, note}`; 201 re-reads both reads and the finance row becomes "Confirmed"; 409 says "Finance confirmation changed. Review it again." and re-reads — verify: network panel and e2e.
19. No text on the page says debts are confirmed; the finance row and form say "milestone notifications" — verify: grep of the feature folder and DOM text for 5003/5004.
20. Dossier 5006 (closed) shows "Still open after closure" from `debt.items`, "As of 2026-11-20", an `owed:null` item as "Amount not recorded" (never 0 or blank), and "List is limited" when `limited:true` — verify: e2e and unit test on the debt mapper.
21. A viewer whose `debt` is null sees no "Still open" section and no placeholder; `items:[]` shows "No open invoices recorded as of <date>." — verify: unit and e2e.
22. The closed state does not say the project is read-only or moved to Closed in Projects, and has no "Support contract" row — verify: grep and DOM.
23. Each of 401, 429, 503 and a dropped network shows its mapped wording with Try again (reads) and keeps typed form text on a write failure — verify: mock scenarios.
24. `closureAdapter.ts` registers key `delivery-closure`, returns `Section[]` the existing renderer draws, and its three descriptors carry the tokens, `idempotency.field === null`, and a `null` token stays `null` in `body()` — verify: `closureAdapter.test.ts`.
25. No file under `frontend/src/features/workspace/` or `frontend/src/features/work-item/` is changed — verify: `git diff --stat origin/main -- frontend/src/features/workspace frontend/src/features/work-item` is empty.
26. Viewport check at 1440 and 390 against the ten SCR-49 artboards for the parts drawn; hidden parts leave no empty heading or gap — verify: screenshots reviewed against `design/screens.md` SCR-49.
27. Focus and keyboard: the decision and finance forms are reachable by Tab, errors are announced (role alert), the note field has a label, and the page has no `prefers-reduced-motion` animation — verify: e2e keyboard run and axe check.
28. `npm run lint`, `npm run typecheck`, `npm test` pass and `api-live-schema-drift.test.ts` still passes — verify: `delivery/checks.sh`.

## Out of scope
- Tola step cards, notes and "Ask Tola" (DC-3); "Drafted <time>" and "Open the full closure report" (no report read exists).
- Any claim that the project is read-only or moves to Closed in Projects; milestone number on a debt row; "Support contract" row.
- SCR-33 retrospective authoring (F-119); SCR-45, SCR-46, SCR-47 (F-114, F-115, F-116); the handover SCR-48 (F-117). They are only read through the checklist.
- The `corrections` form for other lines, `reject` verdict, evidence minting from an upload (D-1), changing `frontend/src/features/workspace` or `work-item`.
- Backend, migrations, contract edits; any new business rule, approver, count or amount.

## Assumptions
- Status words (current/recorded = Done, held = Not yet, unknown = Unknown). Reason: the contract gives enum values, no wording.
- The Closure view takes `dossierId` from the route and the work item from `delivery-overview`. Reason: no closure panel or dossier id on `GET /work/{id}`.
- `version_id` and `evidence_id` for the closure review are read from the `report` check `references[]` and the work read. Reason: D-26 names them but no read field is documented; held with disabled buttons if absent (Q1).
- The returned state is detected from the latest closure return row in `GET /work/{id}/history` plus work `state`. Reason: no returned flag in the checklist.
- The Finance read answering 403/404 means "cannot confirm"; no separate role check. Reason: D-25 says it needs current Finance authority and the server decides.
- `milestone_ids` sent is the full list the read returned. Reason: the board is a single confirmation of the complete inventory; no partial selection is documented.
- Debt rows are linked only when `api_url` maps to a known page route. Reason: `api_url` names the API.
- Head of PMO and PMO Lead are one role (memory, 13 Nov); screen copy uses "Head of PMO" where it names the role.

## Conflicts with the boards
- Eight checks instead of six (adds "Current project scope", "PM closure report"). Recommendation: draw them (live holds closure on them).
- Finance confirmation form (checkbox, evidence, note, milestone list) is not drawn on any board; the boards only show UNKNOWN/CONFIRMED and an "open question" note. Recommendation: build the form and drop the open-question note; needs a board.
- Tola card ("Closure report · Tola · done", step list, "Drafted 06 May 16:00", "Ask Tola") hidden on desktop and mobile. Recommendation: hide (D-182).
- "Ask Tola to update the report" on the returned board becomes a "Replace the report" form (report text, source, reason), which the board does not draw. Recommendation: build the form; needs a board.
- Closed board: "read-only", "moves to Closed in Projects", "Support contract: With Support", and "INV-0533 · milestone 4" are removed or shortened. Recommendation: hide.
- Decision board: "Open the full closure report" link hidden (no read); the "PMO Lead and PMO Lead are one role" note hidden. Recommendation: hide.
- New "Ready to start" state with a "Start closure" button, not on a board. Recommendation: add a board.

## Questions
1. Where do `version_id` and `evidence_id` for the closure decision come from on a read? Options: (a) read both from the `report` check `references[]` and the work read, disable the buttons if missing (recommended; unblocks the build); (b) hold the Close/Return write until backend answers a new D-36; (c) add a field to the checklist (backend change). Context: D-26 names them but no documented read returns them.
2. Check titles: show the API `title` as is, or the board names? Options: (a) API title with the board name as a sub-line (recommended; the API titles may differ and are the source); (b) board names only; (c) API titles only.
3. The "blocked" state maps `ready_to_prepare:false` with no work; "ready, not started" has no board. Options: (a) map as written and add a board for "Ready to start" (recommended); (b) show the blocked board for both; (c) show nothing until work exists.
4. Role word on the decision board: "PMO Lead" (board) or "Head of PMO" (client's name)? Options: (a) "Head of PMO" everywhere (recommended; matches 13 Nov); (b) keep "PMO Lead"; (c) show the role name the task returns.
5. Returned state: where the return note and the allowed "Replace the report" actor come from. Options: (a) latest closure return row of `GET /work/{id}/history` and `actions[]` from the work read (recommended); (b) hold the returned board until a backend field exists; (c) show a generic "Returned" line with no note.
6. Finance evidence field: how does the person choose the evidence id? Options: (a) a select of the evidence ids the Finance read exposes, disabled with a message if none (recommended); (b) a typed id; (c) hold the form until the backend lists allowed evidence (backend question).
7. Source corrections for the closure line (`POST /work/{id}/corrections`): leave to the owning screens (recommended, no board), add a "Correct sources" form (needs a board), or hold until a correction path is drawn.
