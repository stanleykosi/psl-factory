# Hypercare shows the live stability result, each criterion's outcome, and lets the PM pause Tola's evaluation

> Tasks: FE-CONNECT-1. Architecture: v9 package; contract `contracts/psl-factory.openapi.json` API 1.24.0 (origin/main b8542c79). Design: approved 13 Nov canvas with the D-173/D-181 exceptions in `design/review.json`; screens: SCR-46 (boards `SCR-46-desktop`, `-evaluating`, `-qualified`, `-not-met`, `-setup-needed`, plus phone versions). Part 1 of 2; the `-record` board belongs to F-115B.

## Summary
- WAIT: the build starts only after F-85 (lane C, PR #101) is on main. This spec is written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md` and does not change the shared frame.
- `delivery-hypercare/v1` work items stop being drawn from the generic v7 `workspace` object. The page reads `GET /work/{id}/stability` and `GET /work/{id}/stability/events`, and open issues from `GET /projects/{case_id}/issues`.
- Four states are drawn from the live read: Setup needed, Evaluating, Qualified, Not met. Each criterion shows Met, Not met or Not known, from `criterion_results[]`.
- Metric readings (by Engineering or Infrastructure) and open issues are two separate lists. Release and acceptance state come from `checks[]` and `stability/events`, display only.
- One write: pause or continue Tola's evaluation, `POST /work/{id}/background` (202). Everything else (observations, release record, criteria setup) is F-115B.

## Context
- Shared frame (lane C, not edited here): `frontend/src/features/workspace/` (`Workspace.tsx`, `Sections.tsx`, `labels.ts`), and from F-85 `workspace/adapter.ts` (`LineAdapter`, `PanelRef`, `LineContext`, `CommandDescriptor`, `registerLineAdapter`). Page: `frontend/src/features/work-item/` (`WorkItemView.tsx`, `useWorkItem.ts`), which F-85 moves to the live `GET /work/{work_id}`.
- v7 build being replaced for this line: F-34, `frontend/mock/fixtures/work/W-3101..W-3112.json` (`workspace.line_key: "delivery_hypercare"`, `view: "hypercare"`), steps `log_observation` and `record_release`, `frontend/e2e/delivery-hypercare.spec.ts`. The v7 fixtures and spec stay for any page not yet moved; do not delete them.
- Backend (read only, `/Users/Hunchoo/psl-factory-worktrees/lane-d`): `apps/core/factory_api/hypercare.py` (`detail`), `apps/pmo/delivery_closure.py` (`hypercare_inputs`, which produces the `criterion_results` keys), `apps/core/factory_api/work.py:391` (line `delivery-hypercare/v1` has panels `stability` and `stability/events`; each `panels[]` entry is `{key, url}`).
- Live reads (viewer: `python3 delivery/connect/oa.py live GET /api/v1/work/{work_id}/stability 6`; method and path are separate arguments):
  - `GET /work/{work_id}/stability` required: `expected_revision, case_revision, dossier_id, checks[{name: release|acceptance|stability, status: ready|held, finding|null}], proofs[], configuration_id|null, criteria|null, can_draft_criteria, observation_owners[], assessment_id|null, qualified (true|false|null), observations[{owner, source_id, verification_id}], criterion_results[{owner|null, key, status: met|not_met|unknown}], findings[], due_at|null, verified`.
  - `criteria` when set: `clock, minimum_hours, confirmation_owners[], metrics[{key, unit, owner, operator lte|gte|eq, threshold}], financial_controls`, and optionally `issue_clearance {scope, reader_id, blocking_statuses[], blocking_severities[]}`.
  - `criterion_results[].key` is one of `confirmation` and `elapsed_hours` (one each per confirmation owner), `metric:<metric key>` (per owner), and `issue_clearance` (owner null). The list is empty until a release and acceptance exist and the criteria are set.
  - `GET /work/{work_id}/stability/events` required: `expected_revision, case_revision, can_record_release, readiness_ids[], release_evidence[{id,version,kind}], signatures[{id,version,kind}], private_logs[{id,filename}], acceptance_packet|null, receipts[{id,version_id,at}]`.
  - `GET /projects/{case_id}/issues` (`?before=` pages) returns `case_revision, issues[{id, state_id, reference, title, kind, status Open|In Progress|Resolved|Closed, severity, owner_id, next_action, opened_at, age_days, acknowledged_at, resolved_at}], next_before, owners[{id,name}], proofs[]`.
  - `POST /work/{work_id}/background` body `{expected_revision, enabled}`; 202 `{work_id, state, revision}`; 400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503 documented.
- Work item `GET /work/{id}` gives `case_id`, `revision`, `case_revision`, `state`, `current_activity {label, watching}`, `available_control[] (resume|cancel|adopt_profile)`, `panels[]`.

## Contract

### Page and adapter
- Route stays `/work/[id]` (F-85). For `line === 'delivery-hypercare/v1'` the page registers the adapter below. Put the files in `frontend/src/features/hypercare/` (`hypercareAdapter.ts`, `hypercareLabels.ts`, `useHypercareIssues.ts`, `BackgroundControl.tsx`, tests). No change to `frontend/src/features/workspace/**`. If the frame cannot take a section kind this needs, stop and name a dependency on lane C; do not patch it.
- Two adapters are registered with F-85's `registerLineAdapter`: key `stability` (reads `ref.url`) and key `stability/events`. `sections()` returns existing `Section` objects only (`text`, `checklist`, `table`, `facts`, whatever `workspace/labels.ts` already defines); if a needed kind is missing, use the nearest existing one and record it under Questions to lane C, not a frame edit.
- `commands()` on the `stability` adapter returns one descriptor `hypercare.background` : `POST /api/v1/work/{id}/background`, tokens `{expected_revision}` from the work item `revision`, `idempotency.field === null`, `successStatuses [202]`, `body({enabled})` giving `{expected_revision, enabled}`. A `null` revision keeps the control disabled with "Not available right now." and the token stays `null`, never 0. `case_revision` is not in this endpoint's contract and is not sent (readiness note says both; the live contract wants one; see Assumptions).
- Open issues: `useHypercareIssues(caseId)` reads `GET /projects/{case_id}/issues` through `liveApi`, follows `next_before` until exhausted or 100 rows, and keeps only `status` Open or In Progress. A failure here shows an inline "Open issues couldn't be loaded. Try again" row and never blocks the rest of the page.

### What is drawn, per state
State is derived only from the `stability` read, in this order:
1. `criteria === null`: **Setup needed**.
2. else `qualified === null`: **Evaluating**.
3. else `qualified === true`: **Qualified** (`verified` true adds "Verified"; `verified` false shows "Qualified, not yet verified").
4. else `qualified === false`: **Not met**.

Header tag words: "Setup needed", "Evaluating", "Qualified", "Not met". No "Day 10 of 30": the live read has `criteria.minimum_hours` and `due_at` only. Show "Window ends {due_at}" when `due_at` is set, "{minimum_hours} hours from the release" when not, and nothing about a day count.

Sections, in this order, each omitted when it has no content (no empty heading):
- **Result note** (text): Qualified "Hypercare qualified." Not met: the `findings[]` as a list, in the order returned. Evaluating: "Tola is evaluating hypercare." plus the control in the next block. Setup needed: "Hypercare criteria are not set." and, when `can_draft_criteria` is true, "An admin can draft them in Setup" with no link or button (drafting is F-115B); when false, "An admin sets the criteria in Setup." The words come from this spec; the API supplies no sentence.
- **Criteria** (checklist), one row per `criterion_results[]` item, only when the list is not empty, else the configured criteria without a result tag (when `criteria` is set). Row label by key: `confirmation` "{owner} confirms stability"; `elapsed_hours` "{owner} observed after {minimum_hours} hours"; `metric:<k>` "{owner} · {k}" followed by the rule "{operator word} {threshold} {unit}" from the matching `criteria.metrics` entry (lte "at most", gte "at least", eq "exactly"); `issue_clearance` "No blocking issues" with "Blocking: {blocking_severities} severity, {blocking_statuses}" from `criteria.issue_clearance`. An unrecognised key shows its raw text. Result tag: `met` "Met", `not_met` "Not met", `unknown` "Not known" (never read as Met or Not met).
- **Checks** (checklist): `checks[]` as Release, Acceptance, Stability, each "Ready" or "Held", with `finding` text under a held one. Not drawn when `checks` is empty.
- **Metric readings** (table): one row per `observations[]` item: owner, "Recorded", and the owner's metric results taken from `criterion_results` (count "n of m met", never an invented value). The reading's number is not in the read, so no actual value is drawn. A confirmation owner in `criteria.confirmation_owners` with no observation row shows "No reading yet". Nothing here is a free-text note, an issue or an incident.
- **Open issues** (table, separate from the readings, D-18): from `useHypercareIssues`: reference, title, severity, status, owner name (`owners[]` lookup by `owner_id`; none found shows "No owner"), `age_days` as "{n} days open" when not null. A blocking issue (matches `criteria.issue_clearance.blocking_statuses` and `blocking_severities`) is tagged "Blocks hypercare". With no open issues: "No open issues."
- **Release and acceptance** (facts, from `stability/events`, display only): "Release evidence: {n} recorded" (`release_evidence.length`, 0 shows "None recorded", never hides the line); "Go-live signatures: {n} recorded"; "Acceptance packet: {acceptance_packet}" or "Not recorded"; receipts as "{n} receipts, latest {at}". `can_record_release` true with zero release evidence adds "The release has not been recorded." and no button (F-115B). If this read fails the section shows its own retry row and the rest still draws.
- **Next** (text): Not met: "Fix the findings above. Tola evaluates again when they are resolved." and "Closure stays blocked until then." only if `checks` has a held `stability` or `acceptance` entry; otherwise leave that second line off. Evaluating, Qualified and Setup needed use only the lines above. The text is this spec's wording, no link.

### Pause and continue Tola's evaluation
- Shown only when the work item allows it, so the frame never guesses: a **Pause** button when `current_activity.watching === true` (sends `enabled:false`), a **Continue** button when `available_control` includes `"resume"` (sends `enabled:true`). If neither holds, no control is drawn. The control is hidden in Setup needed.
- On press: one `POST /work/{id}/background` with `{expected_revision, enabled}` and the `X-CSRFToken` header from the shared client; the button is disabled while it runs (one request in flight). On 202 re-read the work item and the `stability` read (do not trust the returned `state` alone) and show "Paused" or "Continued" in the status line.
- Errors: 409 "This changed while you were looking. Reloaded, try again." with an automatic re-read, no automatic resend; 403 `csrf_failed` refreshes the session and says "Press again"; 403 otherwise "You can't change this."; 404 "This record is unavailable."; 422 first `fields[].message` or `message`; 429 and 503 "Try again shortly."; network "We couldn't reach the server. Nothing was changed." A failed press is never retried by itself and never reported as success.

### Page states
- Loading: existing `WorkItemStates` loading; the three reads load in parallel and the header draws as soon as `stability` is back.
- Error: `stability` read failure uses F-85's error mapping (401 signed-out link with `?next=`, 403 no access, 404 "This record is unavailable." with no difference between missing and not yours, 429/503 "Try again shortly" with Try again, network). Issues and events failures are section-local as above.
- Empty: `stability` returned with nothing to draw cannot occur (header and state always exist); a project with no issues shows "No open issues."
- Success: the four states above.
- Permission: the viewer sees only what the backend returns (`observation_owners`, `can_draft_criteria`, `can_record_release`, `available_control`); the front end checks no role itself.
- Polling: reuse F-85's `useWorkItem` rule (every 5 s while `current_activity.watching` or `state === 'processing'` and the tab is visible; keep the last good data on a failed poll, stop on lost access). The `stability` and `events` reads re-run on the same tick.

### Hidden because the API does not supply it (D-182)
Tola's step cards and "Ask Tola" (DC-3), "Day 10 of 30", the agent start time, observation rows shaped as issue or note (ISS-/OBS- lines), "Log an observation", "Log an issue", "Record release", "Open Setup > Rules" as a link, and any actual reading value.

### Fixtures (mock, builder creates; ids free but shape fixed)
Live-shaped, served by `frontend/mock/server.mjs` for numeric work ids; v7 ids keep their v7 answers.
- `4201` Setup needed: `criteria:null`, `can_draft_criteria:true`, `qualified:null`, `criterion_results:[]`, `checks:[{name:"stability",status:"held",finding:"Hypercare criteria are not set."}]`.
- `4202` Evaluating: criteria with `minimum_hours:720`, `confirmation_owners:["Engineering","Infrastructure"]`, one metric each, `qualified:null`, `criterion_results` with `unknown` entries, one observation (Engineering), work item `current_activity.watching:true` (shows Pause).
- `4203` Qualified: all results `met`, `verified:true`, two observations, `issue_clearance` present with no open issues.
- `4204` Not met: one `not_met` metric, one `unknown` confirmation, `findings:["Engineering/error_rate fails the configured criterion"]`, one open High issue that matches the clearance (tag "Blocks hypercare").
- `4205` paused: `available_control:["resume"]`, `watching:false` (shows Continue).
- `4206`: 404 for any caller. `4207`: events read returns 503; `4208`: issues read returns 503.

## Lanes
- Frontend lane (owner): `frontend/src/features/hypercare/**`, registration in the F-85 registry (one import line in the module that F-85 designates for adapter registration, otherwise `frontend/src/features/hypercare/index.ts` imported by `WorkItemView.tsx`), `frontend/mock/**` (stability, events, issues and background routes and the fixtures above), `frontend/src/api/types.ts` live types for these reads, tests `frontend/src/features/hypercare/*.test.ts(x)` and `frontend/e2e/hypercare-live.spec.ts`.
- Backend lane: none. No backend or contract change.
- Integration owner: lane D coordinator. Shared files: `frontend/src/features/workspace/**` and `frontend/src/features/work-item/**` belong to lane C (not edited, only imported); `frontend/src/api/*` shared, edits limited to live types and error kinds F-85 has not added; `frontend/src/api/live-schema.d.ts` regenerated only if API 1.24.0 changed it.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. A work item with `criteria:null` (mock `4201`) shows the tag "Setup needed", "Hypercare criteria are not set.", the held stability check with its finding, and no Pause or Continue control — verify: open `http://localhost:4990/work/4201` (mock 4991).
2. `4202` shows "Evaluating", each criterion with its result tag (unknown ones read "Not known", never Met), a Pause button, and one Engineering reading with the other owner "No reading yet" — verify: page text and `hypercare-live.spec.ts`.
3. `4203` shows "Qualified" with "Verified", every criterion "Met", and "No open issues." — verify: page.
4. `4204` shows "Not met", the findings text, the unmet criterion tagged "Not met", the unknown one "Not known", and the open High issue tagged "Blocks hypercare" in a list separate from the readings table — verify: page and DOM (two distinct sections).
5. Each criterion key maps to the specified wording: `confirmation`, `elapsed_hours`, `metric:<k>` with rule words, `issue_clearance`, and an unknown key shows raw text — verify: unit test on `hypercareLabels.ts`.
6. State derivation follows the stated order, including `qualified:true` with `criteria` set, `qualified:null` with `criteria` set, and `criteria:null` with any `qualified` — verify: unit test on the state function with all four fixtures plus the edge combinations.
7. No text "Day N of 30", no Tola step cards, no "Log an observation", "Log an issue", "Record release" or "Ask Tola" appear in any state; no empty heading is drawn when a section has nothing — verify: e2e asserts absence at 1440 and 390; grep for those strings in `frontend/src/features/hypercare` returns only tests.
8. No actual reading value is drawn and no missing value renders as 0: a missing `due_at` shows the "{minimum_hours} hours from the release" wording; a null `finding` shows no finding line — verify: unit tests.
9. Release and acceptance section shows counts from `stability/events`, "None recorded" for zero release evidence, and "Not recorded" for a null `acceptance_packet`; it draws no button — verify: page on `4202`; unit test.
10. Open issues come from `GET /projects/{case_id}/issues`; Resolved and Closed rows are not listed; an owner id missing from `owners[]` shows "No owner"; paging follows `next_before` and stops at 100 — verify: unit test with a two-page mock; network panel.
11. Events read failing (`4207`) or issues read failing (`4208`) shows that section's retry row while the header, criteria and checks still draw; Try again repeats only that read — verify: open both ids; network panel.
12. `stability` 404 for `4206` and for a live id the account cannot see show exactly "This record is unavailable." with no difference — verify: open both; compare text.
13. 401 shows the signed-out state linking to `/sign-in?next=<path>`; 403 `csrf_failed` is not shown as no-access — verify: mock scenarios plus unit test.
14. Pause on `4202` sends exactly one `POST /api/v1/work/{id}/background` with `{"expected_revision": <work revision>, "enabled": false}` and an `X-CSRFToken` header, and no `case_revision`; the button is disabled during the request — verify: Playwright request capture; double click makes one request.
15. Continue on `4205` sends `enabled:true`; after 202 the page re-reads and shows the refreshed state, not the 202 body alone — verify: e2e counts the two GETs after the POST.
16. Background errors map as specified: 409 (re-read once, no resend), 403 `csrf_failed` (session refresh, "Press again", one POST), 403, 404, 422 with `fields`, 429, 503, network; no automatic resend after any failure — verify: unit tests count fetch calls per scenario.
17. A work item with `revision:null` leaves the control disabled with "Not available right now." and sends nothing — verify: unit test.
18. Neither control is drawn when `watching` is false and `available_control` lacks `resume`; Pause is not drawn in Setup needed — verify: unit test on `BackgroundControl`.
19. The hypercare feature imports no v7 `WorkItem` type and no file under `frontend/src/features/workspace` is changed — verify: `git diff --stat origin/main -- frontend/src/features/workspace frontend/src/features/work-item` is empty; `grep -rn "api/schema'" frontend/src/features/hypercare` returns nothing.
20. Adapters: a test registers `stability` and `stability/events`, reads a mock panel through F-85's `adapterFor`, gets `Section[]` that the existing `Sections` renderer draws, and gets the `hypercare.background` descriptor with a `null` revision token kept `null` — verify: `hypercareAdapter.test.ts`.
21. The only `POST` this feature sends is the background call — verify: `grep -rn "liveApi.POST\|\.POST(" frontend/src/features/hypercare` shows one call site; e2e asserts no other POST during each state.
22. Against live Django (8030, the Postgres fixture in the runbook, account that can see a hypercare item) the page for a real `delivery-hypercare/v1` work id shows the same state, criteria results, findings and issue list as `curl` of `/api/v1/work/{id}/stability` and `/projects/{case_id}/issues` — verify: compare page and JSON.
23. Viewport check at 1440 and 390 for the four states: one column on the phone, no horizontal scroll, controls 44 px tall, no axe violations, and the parts that remain match the SCR-46 boards (header tag, criteria list with tags, next block) — verify: screenshots against `design/screens.md` SCR-46 artboards; `hypercare-live.spec.ts` axe run.
24. `npm run typecheck`, `npm run lint`, `npm test` pass and `api-live-schema-drift.test.ts` still passes — verify: `delivery/checks.sh`.

## Out of scope
- All other writes: log an observation (`POST /work/{id}/stability`), record the release (`POST .../stability/events`), draft or review criteria, `release-register`. These are F-115B, as is the `SCR-46-desktop-record` board.
- Go-live acceptance actions (SCR-45, F-114) and the archive (SCR-47, F-116).
- Any change to `frontend/src/features/workspace` or the work item page (lane C).
- Showing actual reading values, a day counter, Tola's narrative, free-text notes, or logging an issue from this screen.
- Cancel and adopt-profile controls from `available_control`; only resume/pause is built here.
- Deleting the v7 W-31xx fixtures and the old e2e file.
- Backend, contract, migrations.

## Assumptions
- Background control logic: Pause when `current_activity.watching` is true, Continue when `available_control` includes `resume`. Reason: no read says whether the background request is on; these are the only signals the work item carries.
- Send only `expected_revision` and `enabled` to `/background`. Reason: the 1.24.0 request schema has just those two fields; readiness mentioned `case_revision` as well. If the live backend rejects this, the builder reports it rather than adding fields.
- Issues come from the project issues register, not from an issue field on `stability`. Reason: D-18 says use the separate issue record; `issue_clearance` supplies only the blocking rules.
- Criterion wording and the Next/result lines are written here. Reason: the API gives only keys, results and `findings[]` text.
- Metric readings show counts of met rules per owner, not values. Reason: `observations[]` carries only source and verification ids.
- Panel keys `stability` and `stability/events` are taken from `work.py:391`. Reason: that is how this line's `panels[]` are built.
- "Qualified, not yet verified" wording for `qualified:true` with `verified:false`. Reason: both fields exist and are independent.
- Issue polling is not repeated on the 5 s tick unless the `stability` read changed `assessment_id`. Reason: avoids hammering a paged register; the builder may refetch on tick if simpler, and the cost is low.

## Questions
1. Open issues link. The board links "Open ISS-0315". The issues register gives an issue id and `state_id`, not a work id for SCR-30, so a link target is unknown. Options: (a) show the reference as plain text, no link (recommended, nothing to guess); (b) link to the project's issues page if one exists; (c) wait for a backend field. Context: the F-111 issue page reads by `work_id` through `issue-followup`.
2. Day count. The boards draw "HYPERCARE · DAY 10 OF 30" and "30 days · from Setup". Options: (a) show "Window ends {due_at}" or "{minimum_hours} hours from the release" (recommended, uses only supplied data); (b) compute a day from `due_at` and `minimum_hours` on the client; (c) ask the backend for an elapsed field. A client-computed day would be an invented figure, so (b) is not advised.
3. Observation rows. Boards draw issue and note rows ("ISS-0301 Login slow", "OBS-0012 Noted"). Live has metric readings by owner and issues separately. Options: (a) two lists, readings by owner with counts, issues separately (recommended, follows D-18); (b) merge both into one list as drawn, which mixes meanings; (c) hide readings until F-115B. Needs a design engineer board for the metric rows.
4. Tola's card and "Ask Tola". Boards show "step 3 of 4 · Working" and an Ask Tola button. Options: (a) hide (recommended, DC-3, D-182); (b) show only the one-line `current_activity.label` as a status line; (c) wait for a backend narrative. Option (b) is cheap if you want the board's rhythm kept.
5. Pause control. No board draws Pause or Continue. Options: (a) one text button in the Evaluating status line, named Pause/Continue (recommended); (b) a menu item; (c) hold until a board exists. Needs a board by the design engineer, and the chosen signal (watching/resume) confirmed by the backend: is it right to read "paused" from `available_control` containing `resume`?
6. Frame section kinds. If the existing `Section` kinds cannot draw the two-list layout (readings table beside issues table), a small kind is needed in `frontend/src/features/workspace/labels.ts`. Options: (a) reuse `table` twice (recommended, no frame change); (b) ask lane C for a new kind; (c) render these two sections in `frontend/src/features/hypercare` outside the frame. Dependency on lane C only under (b).

## Conflicts with the boards
The spec removes or changes these drawn parts; the design engineer decides once before the build (all also listed under Questions).
1. "DAY 10 OF 30" and "30 DAYS · FROM SETUP": replaced by "Window ends {due_at}" or "{minimum_hours} hours from the release". Recommendation: accept (Question 2).
2. Tola's step card, "step 3 of 4", "Started 01 May 09:00" and "Ask Tola": removed. Recommendation: hide (Question 4).
3. Observations list drawn as issue/note rows (ISS-0301, OBS-0012, "Incidents NONE"): replaced by a readings-by-owner table plus a separate open-issues list; no incidents row, no actual values. Recommendation: accept (Question 3).
4. "Log an observation", "Log an issue" and the Record release board: not drawn here; observation and release are F-115B, "Log an issue" has no source on this screen. Recommendation: leave out.
5. "Open ISS-0315" and "Open Setup > Rules" links: text only. Recommendation: plain text (Question 1).
6. Added though no board draws it: Pause/Continue control, a Checks list (Release, Acceptance, Stability with findings), a Release and acceptance facts block, and "Not known" as a third criterion result. Recommendation: keep; they are live data the boards lack and need a design engineer board.
