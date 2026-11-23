# Start work reads the live lines, picks a project, and starts the weekly report

> Tasks: FE-CONNECT-1. Architecture: v9 package, contract `contracts/psl-factory.openapi.json` 1.22.0 (manifest digest not re-verified by the spec writer; readiness did not check it and `approval_evidence_refs` is empty, so the coordinator confirms before accepting). Design: approved 13 Nov canvas under the recorded exception in `design/review.json`; screens: SCR-04 (artboards SCR-04-desktop, -mobile, -lines, -validation, -weekly).

## Summary
- The Start work drawer lists lines from live `GET /lines` (no groups, no "Next" summary), picks a project from `GET /lines/projects`, and a source record from `GET /projects/{case_id}/intake-sources` where a line needs one.
- Lines with `can_submit_via_api:false` are listed as unavailable with a link to their `django_url` (LC-Q3 option 1). No form is built for them. `invoice` is not shown at all.
- One line works end to end: the weekly report, started with `POST /work` `line:"pmo-weekly-report/v1"`; a 200 answer opens `/work/{work_id}`.
- Uploads use F-85's `EvidencePicker` and `uploadCaseFile` (no second picker). The weekly body has no file field, so the weekly form shows none (LC-Q11).
- Frontend only. The start-work files get a small per-line registry so F-88 (received bid) and later lanes add a line without editing the chooser.

## Context
Worktree `/Users/Hunchoo/psl-factory-worktrees/lane-c/frontend`; paths below are relative to `frontend/`. Builds only after F-85 has merged (its `src/features/workspace/EvidencePicker.tsx`, `evidence.ts`, and the live client).
- Drawer: `src/features/start-work/` (`StartWorkDrawer.tsx`, `LineChooser.tsx`, `LineForm.tsx`, `IntakeField.tsx`, `RecordPicker.tsx`, `useStartWork.ts`, `intake.ts`, `labels.ts`, `types.ts`). Today all of it is typed from the v7 `E-LINES` (`group`, `subtitle`, `default_line`, `intake[]`, `start_via`), calls `api.GET('/api/v1/lines')`, `/lines/{line_key}/fields/{field}/options`, and expects `POST /work` to answer 201 with a string `work_id`.
- Callers: `StartWorkButton.tsx`, `src/shell/TopNav.tsx`, `src/shell/PhoneBar.tsx`, `src/features/assistant/DraftStart.tsx` (passes `prefill` and `onStarted(workId: string)`), `src/features/workspace/Workspace.tsx`, `StepForm.tsx`, `useWorkspaceStep.ts`. Keep their props working: `onStarted` still receives a string (`String(work_id)`); `prefill` for a line with no live form shows the existing "You can't start this here" callout.
- API client: `src/api/client.ts` exposes `api` (v7) and `liveApi` (live, `src/api/live-schema.d.ts`), `call()`, shared CSRF. Errors: `src/api/errors.ts`.
- Mock: `mock/start-work.mjs`, `mock/fixtures/start-work/lines.*.json` (v7 shapes), `mock/server.mjs`, `mock/session.mjs` (model for live-shaped reads).
- Live shapes (viewer: `python3 delivery/connect/oa.py live GET /api/v1/lines 3`):
  - `GET /lines` -> `{items[{key, title, description, can_submit_via_api, django_url, project_options_url|null, submit_url}], as_of}` (25 lines).
  - `GET /lines/projects?line=&q=&page=` (`line` required, `q` max 120, `page` 1..10000) -> `{items[{case_id, title, case_revision, sample, django_url, source_options_url, workflow_intake_url|null}] (max 25), page, next_page|null}`.
  - `GET /projects/{case_id}/intake-sources?line=&field=&parent_id=&before=` -> `{case_revision, fields[] (max 30), field|null, items[{id:int,label}] (max 25), next_before|null}`.
  - `POST /work` weekly branch: `{line, case_id, case_revision, idempotency_key (1..100, printable ASCII), background?, intake:{inputs:{template_id|null, content_id|null, start_at (<=64), end_at (<=64)}}, reference (1..160)}`, no extra keys. 200 `{work_id:int, state, revision, background: queued|existing|held|not_requested}`. Errors 400/401/403/404/409/413/415/422/429/500/503.

## Contract

### Chooser (SCR-04-desktop-lines, SCR-04-mobile-lines)
- Read `GET /lines` on every opening of the drawer (grants stay current). Each row: `title` as the name, `description` as the detail line (desktop only, as the board's detail line). No group headings, no "Next: ..." line, no count of stations. Keep the search on title and description and the phone's count in the head.
- The list has two kinds of row, in the order returned:
  - Startable: `can_submit_via_api` true and the line has a registered form (`lines/index.ts`, below). Selectable; Next opens its form.
  - Unavailable: every other returned line except `invoice`. Not selectable. One plain line under the title: "Not available here yet. Open it in the full form." with the link "Open in the full form" to `django_url` (same tab). It is never dimmed to unreadable and the link is keyboard reachable. The words are one constant in `labels.ts`.
- `GET /lines` has no default line: every entry (main button, chevron, "+ Start work") opens the chooser. Remove the `default_line` branch from `StartWorkDrawer.tsx`. `prefill` opens a form only for a startable line in the returned list.
- States: loading (existing skeleton), error (401 `SignedOutState` with `/sign-in?next=`; 403 and 404 show the server's message; anything else "We couldn't load your lines. Nothing was started." with Try again), empty ("There are no lines you can start right now."), success as above.

### Project picker (the form's first field)
- For a line with `project_options_url` not null: `GET /lines/projects?line=<key>&q=<search>&page=<n>`. Search is sent only when non-empty (trimmed, at most 120). "Show more" requests `next_page` while it is not null. Rows show `title`, a "Sample" tag when `sample`. The chosen row's `case_id` and `case_revision` are held for the start. `django_url`, `workflow_intake_url` and `source_options_url` are not used here.
- A line whose `project_options_url` is null has no project step in this feature (no form is registered for it).
- Changing the project clears the chosen source record and any uploads for the old case.
- Empty result: "No projects to start this on." Error: the same retry pattern as the chooser.
- Reuse `RecordPicker.tsx` for the list UI; replace only its data source with a function `fetchProjects(line, q, page)` in `useStartWork.ts`.

### Source record picker
- `fetchSources(caseId, line, {field, parentId, before})` calls `GET /projects/{case_id}/intake-sources` and returns `{caseRevision, fields, items, nextBefore}`. `items[].id` is an integer sent as the line's integer id; `before` pages with `next_before`.
- The weekly form does not use it (its inputs are a period and optional ids). The function and a `SourcePicker` built on `RecordPicker` are built and unit-tested here because F-88 and later lines need them; no weekly control renders it. The weekly start sends `template_id` and `content_id` as null (backend question LC-6; board conflict LC-Q10).
- Whenever the response carries a `case_revision`, the form uses it as the freshest revision for the start.

### Weekly report form (SCR-04-desktop-weekly, -mobile-weekly)
Drawer title "Weekly client report" and primary button "Start report" stay (`labels.ts`). Fields in order:
| Field | Control | Sends |
|---|---|---|
| Project (required) | project picker above | `case_id`, `case_revision` |
| Week (required) | existing date range control (`IntakeField` `date_range`) | `intake.inputs.start_at`, `intake.inputs.end_at` as the control's ISO dates (`YYYY-MM-DD`), each at most 64 chars |
| Reference (required, 1..160) | text | `reference` |
- `intake.inputs.template_id` and `content_id` are always sent, as `null`.
- `background` is not sent (it is optional; the server's default applies).
- `idempotency_key`: one `newIdempotencyKey()` (existing helper, `intake.ts`) made when the form opens and reused on every resend of the same body. It is replaced after a definitive 409 or 422 (nothing recorded) or after the person changes a field following such a failure.
- Required fields empty on press: the existing `ValidationSummary` ("Project is required.", "Week is required.", "Reference is required."); no request is made.
- The start button is disabled while the request runs; a double press sends one request (keep the existing synchronous guard).
- No "up to 8 days" or "must have ended" check is made by the client; the server's 422 message is shown.

### Start (POST /work)
- Request: `POST /api/v1/work` through `liveApi` with `X-CSRFToken`, body exactly as in Context, no keys beyond the schema.
- 200 (the expected first-start answer, A-24): take `work_id`, close the drawer, `router.push('/work/' + work_id)`; call `onStarted(String(work_id))` where a caller supplied one. Any 2xx other than 200 is also treated as success only if the body has an integer `work_id`; otherwise it is uncertain.
- 401: signed-out state with `/sign-in?next=`.
- 403 with `code:'csrf_failed'`: refresh the session once (`refreshSession()`), keep the form, say "Refresh your session and try again" (nothing was sent as a start). Other 403: "Your role doesn't let you start this line." with the server's `message` if present.
- 404: "This record is unavailable." (the project or line is missing or not theirs; no difference shown). Form stays; picking another project is allowed.
- 409: nothing is resent. Say "This project changed since you opened it." Keep every value, re-read `GET /lines/projects` for the same title search to refresh `case_revision`, and generate a new key for the next press. The server's `message` is shown beneath.
- 413, 415, 429, 500, 503 and network failure or the 20 s timeout (`START_TIMEOUT_MS`): 429 "Try again shortly." (known not started: new key next press); 413 and 415 show the server `message`; 500, 503, network and timeout are uncertain: lock the form, "Not confirmed. Check before trying again." with "Check again" that resends the same body and the same key. A replayed key's answer is unconfirmed (A-24): the app shows whatever status and `work_id` the server returns and builds no replay logic beyond that.
- 422: map `fields[].name` to controls by this table, flagging a mismatch rather than renaming: `case_id` or `case_revision` -> Project; `line` -> general message; `idempotency_key` -> general message; `reference` -> Reference; `intake.inputs.start_at`, `intake.inputs.end_at`, `intake.inputs`, `start_at`, `end_at` -> Week; `template_id`, `content_id` -> general message. Any other name is drawn as its own box ("unmatched", existing `Notice` `invalid.unmatched`). A 422 with no `fields` shows `message` as the general text.
- Writes happen one at a time; the form never resends by itself.

### Upload (shared, F-85)
- `StartUpload` (new, `src/features/start-work/StartUpload.tsx`) wraps F-85's `EvidencePicker` with props `{caseId, value, onChange, disabledReason?}` and returns the `upload_id` through `onChange`. It is used by a line form only when that line's registry entry sets `takesUpload: true`; the weekly form does not (LC-Q11 option 1). It never calls `fileToEvidence` and never sends an `upload_id` as an evidence id.
- It is disabled until a project is chosen ("Choose a project first.") and cleared when the project changes. The files go to the chosen `case_id` only.
- The old v7 `StartProof.tsx` (base64 `POST /cases/{id}/evidence`) is no longer used by any registered live line; leave the file for lines not yet moved and do not import it in the weekly form.

### Per-line registry (extension point for F-88 and later)
`src/features/start-work/lines/index.ts` exports:
```ts
export type LineForm = {
  key: string;                 // the live line key, e.g. 'pmo-weekly-report/v1'
  startLabel: string;          // primary button
  drawerTitle: string;
  takesUpload?: boolean;
  Form: React.ComponentType<LineFormProps>;   // owns its fields and its start call
};
export function lineFormFor(key: string): LineForm | undefined;
```
`lines/weeklyReport.tsx` is the one registered entry. `LineForm.tsx` becomes the drawer shell (frame, back/close, project picker, start state machine); per-line files supply fields and a `buildBody(values, ctx)` that returns the typed body. F-88 registers its form separately; the received bid is not a `/lines` line and does not appear in the chooser from here. The chooser decides startable vs unavailable from `can_submit_via_api` and `lineFormFor`.

### Types
`src/features/start-work/types.ts` derives `Lines`, `Line`, `ProjectOptions`, `IntakeSources` and the weekly start body/answer from `@/api/live-schema`, not `@/api/schema`. The weekly body type is the schema's weekly branch (no hand-written duplicate). The old v7 `Field` and `LineOption` types stay only where `StartProof.tsx` and code for unmoved lines still need them.

### Mock (`mock/`, Next 4980, mock 4981)
Live-shaped answers the mock serves; v7 routes for unmoved callers keep working:
- `GET /api/v1/lines`: `{items:[{key:"pmo-weekly-report/v1", title:"Weekly client report", description:"Friday report for a client", can_submit_via_api:true, django_url:"/lines/pmo-weekly-report/", project_options_url:"/api/v1/lines/projects?line=pmo-weekly-report/v1", submit_url:"/api/v1/work"}, {key:"pmo-minutes/v1", ..., can_submit_via_api:false, django_url:"/lines/pmo-minutes/"}, {key:"finance-payroll/v1", ..., can_submit_via_api:true}], as_of}`. A line that is `can_submit_via_api:true` but has no registered form shows as unavailable too. No invoice line.
- `GET /api/v1/lines/projects`: two pages (25 + 3) for `?line=pmo-weekly-report/v1`; `q` filters by title; one item with `sample:true`; `case_id` uuids and `case_revision` 4, 7.
- `POST /api/v1/work` weekly: validates the body against the schema (extra key or missing field -> 422 with `fields[{name,message}]` using the typed names); 200 `{work_id:4102, state:"processing", revision:1, background:"not_requested"}`. Cookie scenarios: `start_stale` (409), `start_uncertain` (503 then 200 on the same key), `start_denied` (403), `csrf_failed` (403 `code:'csrf_failed'`), `start_missing` (404). Opens `/work/4102` (F-85 fixture).
- `POST /api/v1/cases/{case_id}/files`: F-85's route.

## Lanes
- Frontend lane (owner of all of this feature): `src/features/start-work/**` (including new `lines/`, `StartUpload.tsx`), `mock/start-work.mjs` and `mock/fixtures/start-work/**`, `mock/server.mjs` route registration for the three live reads and `POST /work`, tests under `src/**` and `e2e/start-work*.spec.ts`.
- Backend lane: none. Questions: LC-6 (`backend-questions.md`), A-23 to A-26 already filed.
- Integration owner: lane C coordinator. Shared files: `src/features/workspace/EvidencePicker.tsx`, `evidence.ts` (F-85 owns; read only here), `src/api/client.ts`, `errors.ts`, `live-schema.d.ts` (shared; no edits expected beyond live error kinds for 409/413/415/429/503 if F-85 has not added them), `src/shell/TopNav.tsx`, `PhoneBar.tsx`, `StartWorkButton.tsx`, `src/features/assistant/DraftStart.tsx` (callers: change only what the removal of `default_line` and the string `work_id` require). F-88 edits `src/features/start-work/` later: it adds `lines/<line>.tsx` and one registry line, and must not need to change `LineChooser.tsx`.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. With the mock running, opening Start work from the top bar shows live lines by title with a description, no group headings and no "Next:" line — verify: open `/` on port 4980, press "+ Start work", read the list; `e2e/start-work.spec.ts` asserts no group heading text and no "Next:".
2. A line with `can_submit_via_api:false` and a line with no registered form appear as unavailable, each with "Open in the full form" linking to its `django_url`, are not selectable, and Next stays disabled when one is focused — verify: chooser unit test and the e2e; `invoice` appears nowhere in the list.
3. Choosing the weekly report, the project picker lists projects for `?line=pmo-weekly-report/v1`; typing in the search sends `q` (only when non-empty and at most 120 characters); "Show more" loads `page=2` and disappears when `next_page` is null — verify: unit test on `fetchProjects` with a mocked client and the e2e network log.
4. Pressing "Start report" with Project, Week or Reference empty makes no `POST /work` and lists each missing field — verify: e2e counts requests to `/api/v1/work` (zero).
5. A valid start sends exactly `{line:"pmo-weekly-report/v1", case_id, case_revision, idempotency_key, intake:{inputs:{template_id:null, content_id:null, start_at, end_at}}, reference}` with no other keys and the `X-CSRFToken` header, then lands on `/work/4102` — verify: unit test on `buildBody`, mock request log, and URL after the e2e.
6. A double press on Start report sends one request, and "Check again" after a 503 resends the same body with the same `idempotency_key` — verify: e2e (`start_uncertain`) comparing the two request bodies.
7. A 409 keeps every typed value, shows the "changed since you opened it" message, re-reads the project's revision, and the next press carries a new key and the new `case_revision`; nothing is resent on its own — verify: unit test on the state machine with a mocked client.
8. A 422 from the server maps `fields[].name` as in the table; an unknown name appears as its own box and none are dropped — verify: unit test per row of the table.
9. 401 shows the signed-out state with `/sign-in?next=`; a 403 `csrf_failed` does not show "can't start" and refreshes the session once; a 404 says exactly "This record is unavailable." — verify: unit tests and the mock scenarios `csrf_failed`, `start_missing`.
10. Wrong user and wrong tenant: a project from another team is never listed, and a hand-edited `case_id` (mock `start_missing`) shows the 404 wording with no hint it exists — verify: mock scenario and unit test.
11. Provider and network failure: with the mock stopped mid-start the form locks with "Not confirmed. Check before trying again." and does not start a second work item — verify: e2e with the mock paused; mock log shows one started work.
12. `StartUpload` uploads through `uploadCaseFile` to the chosen `case_id` only, returns an `upload_id` (not an evidence id), is disabled before a project is chosen, and is cleared when the project changes — verify: component test; `grep -n "uploadCaseFile" src/features/start-work/StartUpload.tsx`, and no second multipart upload helper exists under `src/features/start-work`.
13. `fetchSources` sends `line`, `field`, `parent_id`, `before` only when set, returns `next_before`, and uses the response `case_revision` — verify: unit test with a mocked client.
14. A caller that passes `onStarted` (the assistant draft) receives the work id as a string, and `prefill` for a line not in the startable list shows "You can't start this here." — verify: update `tests/` for `DraftStart` and run it.
15. `StartWorkDrawer.tsx` has no `default_line` path and `LineChooser.tsx` does not import a per-line form — verify: `grep -rn "default_line" src/features/start-work` returns nothing; F-88 can add a line by adding a file and a registry entry (reviewer reads `lines/index.ts`).
16. No client-side rule is invented: `grep -n "8 days\|up to 8" src/features/start-work` returns nothing — verify: grep.
17. Layout matches the weekly and lines boards at desktop and phone widths except for the changes under "Conflicts with the boards" — verify: the fidelity tool run for SCR-04-desktop-weekly, SCR-04-mobile-weekly, SCR-04-desktop-lines, SCR-04-mobile-lines.
18. Live: against Django on 8020 with a PM account, the chooser lists the 25 lines from the live `GET /lines` and one weekly start for a real project returns 200 and opens its `/work/{id}` — verify: manual run recorded in the PR with the `work_id` and `oa.py live GET /api/v1/work/{work_id} 3`.

## Out of scope
- Every other line's form (minutes, issues, change, emergency, escalation, leadership, delivery, finance lines): they show as unavailable with the link.
- The Finance invoice start and the "Find a process" list (`GET /processes`).
- The received bid form and `POST /received-bids` (F-88); minutes intake (`POST /projects/{case_id}/minutes/intake`).
- Weekly report content, drafts, cites, corrections (SCR-25, `weekly-report-intake`, F-87).
- Template or content choices for the weekly line (always null), the `background` choice, and any rule on the length of the week.
- A "Next: ..." station summary, group headings, and per-line field lists from the server (none exist).
- Replay handling beyond showing the server's answer; the access-request control; changes to protected paths; backend changes.

## Conflicts with the boards
Recorded as LC-Q10 and LC-Q11 in `delivery/connect/questions-batch.md`.
1. Weekly board draws Project, Week and a Template line. The spec adds a required "Reference" text field (live requires it) and omits the Template line (live has an id only, no name). Recommendation: accept both (LC-Q10 option 1).
2. Weekly Week help "Must have ended; up to 8 days" is a rule the contract does not state. Spec removes the help line. Recommendation: remove until the backend confirms.
3. Lines board draws group headings (or accessible groups) and a "Next:" summary; live has neither. Spec removes both, and the detail line under a title becomes `description`. Recommendation: accept.
4. Lines board draws only startable lines. Spec adds an "Unavailable" row with "Open in the full form". Recommendation: accept (LC-Q3 option 1); the design engineer should draw it.
5. The main button used to open the default line directly; live has no default line, so it opens the chooser. Recommendation: accept.
6. The upload box appears on no weekly board; the spec shows none on the weekly form (LC-Q11 option 1).

## Assumptions
- `start_at` and `end_at` are sent as `YYYY-MM-DD` from the date range control; the schema only gives a 64-character string and no format. Reason: the control already yields ISO dates; verify against live in the build and record any 422.
- `template_id` and `content_id` are null in every weekly start. Reason: no name or list is served (LC-6), and null is allowed by the schema.
- A 2xx other than 200 with an integer `work_id` is success. Reason: A-24 unconfirmed; the schema lists 200 only.
- The 409 message wording and the "Not available here yet" wording are mine; both are one constant each in `labels.ts` for the design engineer to edit.
- The Reference field has no default text. Reason: a default would invent a business value.
- Lines flagged `can_submit_via_api:true` that this feature has no form for are shown as unavailable, not hidden. Reason: LC-Q3 option 1 applies to anything the screen cannot submit.
