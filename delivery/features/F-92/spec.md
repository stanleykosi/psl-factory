# Start work builds each line's form from its request_schema, proven on five PMO lines

> Tasks: FE-CONNECT-1. Architecture: contract `contracts/psl-factory.openapi.json` 1.24.0 (manifest digest not re-verified; `approval_evidence_refs` is empty, coordinator confirms). Design: approved 13 Nov canvas under the recorded exception in `design/review.json`; screens: SCR-04 (artboards SCR-04-desktop-minutes, -issue, -change, -incident, -escalation and their -mobile twins; -validation, -lines).

## Summary
- One form engine turns the `request_schema` that `GET /lines` serves for a line into the drawer's fields, body and 422 mapping. It plugs into F-86's registry, so the chooser, project picker and start state machine are reused, not rebuilt.
- Five lines are proven: `pmo-issues/v1`, `pmo-escalation/v1`, `pmo-minutes/v1`, `pmo-emergency/v1`, `pmo-change/v1`. `pmo-leadership-report/v1` drops to batch 2 (its body is not the weekly shape; LC-Q29).
- Record choices come from the served sources only: `GET /projects/{case_id}/intake-sources` (with `parent_id`, `before`) and, for the escalation request, the project's `workflow_intake_url`. Nothing is typed in as an id.
- Minutes starts from a notes file sent as multipart to `POST /projects/{case_id}/minutes/intake` (LC-Q30); the other four send JSON to `POST /work`.
- `pmo-weekly-report/v1` stays hand-built (F-86). A guard test checks its body against the served schema.
- Frontend only. A line the engine cannot fully build shows as "Not available here yet" (F-86's row), never a partial form.

## Context
Paths are relative to `frontend/` in the F-86 worktree (`/Users/Hunchoo/psl-factory-worktrees/lane-c2/frontend`, branch `fe-connect-1-start-work-weekly`). F-92 builds after F-86 and F-85 merge; if names below differ after merge, use the merged names.
- Registry: `src/features/start-work/lines/index.ts` (`LineForm` entry: `key`, `startLabel`, `drawerTitle`, `takesUpload`, `projectBound`, `Form`, `missing`, `buildBody`, `target`; `lineFormFor(key)`; `FORMS`). Hand-built entry: `lines/weeklyReport.tsx`.
- Shell: `LineForm.tsx` (`LineDrawer`: project picker, `ValidationSummary`, notices, unmatched 422 box), `useStart.ts` (`useStart`: one write at a time, key reuse, 409/422/uncertain handling, always `liveApi.POST('/api/v1/work', body)`), `LineChooser.tsx` (startable = `can_submit_via_api` and `lineFormFor`).
- Pickers: `ProjectPicker.tsx`, `SourcePicker.tsx` (props `caseId, lineKey, field, label, parentId, value, onChange, onRevision, disabled, error`), `RecordPicker.tsx`; reads `fetchProjects`, `fetchSources` in `useStartWork.ts`; `newIdempotencyKey()` in `intake.ts` (a UUID; it satisfies the minutes key rule `[A-Za-z0-9_.:-]{1,100}`).
- Upload: `src/features/start-work/StartUpload.tsx` over F-85's `src/features/workspace/EvidencePicker.tsx` and `evidence.ts` (`uploadCaseFile`). `src/components/FileUpload.tsx` takes `accept` and `maxBytes` (an empty `accept` and `maxBytes: null` leave the rule to the server).
- Served shapes (read from the backend source, `apps/core/factory_api/intake.py` and `intake_sources.py`; live Django was not running for the spec writer, so the build re-checks against 8020):
  - `GET /lines` item: `{key, title, description, can_submit_via_api, django_url, project_options_url|null, submit_url, request_schema, content_type}`. For a `POST /work` line, `request_schema` is that line's branch of the `POST /work` body: properties `line` (const), `case_id`, `case_revision`, `idempotency_key`, `background?`, `intake`, and `reference` (absent for `pmo-issues/v1` and `finance-ledger/v1`, whose reference the server derives). In the OpenAPI file `request_schema` is only `type: object`, so the engine reads it at run time and types it by hand as a small `JsonSchema` shape.
  - All five lines have `can_submit_via_api: true`, a non-null `project_options_url`, `submit_url: /api/v1/work` and `content_type: application/json` for the viewer who may start them (per the source above). `pmo-minutes/v1` advertises JSON even though its upload route is multipart (LC-Q30).
  - `intake-sources` with no `field` returns `fields[]`: the dotted names of the source fields a line has. With `field` it returns `items[{id, label}]` (25 per page, `next_before`).
- Intake bodies for the five lines (`apps/core/factory_api/intake.py` `STARTS`, `apps/workflows/factory_*.py`). Every key listed is required in the body; "null ok" means the schema allows `null`:
  - issues: `intake {issue_id: int}`.
  - escalation: `intake {request_id: int, template_id: int|null}`, `reference`.
  - emergency: `intake {profile_id: int, inputs {template_id, authorization_id, outcome_id: int|null each, audience: "internal"|"client"|null}}`, `reference`.
  - change: `intake {version_id: int, inputs {template_id, authorization_id: int|null each}}`, `reference`.
  - minutes (multipart route): `case_revision, idempotency_key, reference (1..160), template_id (int), audience (internal|client), notes_file`, optional `meeting_version_id`, optional `background` ("true"|"false").
- Mock: `mock/start-work.mjs`, `mock/fixtures/start-work/**`, `mock/server.mjs` (F-86 added the live `GET /lines`, `/lines/projects`, `POST /work`).

## Contract

### The engine (`src/features/start-work/engine/`)
One module, no second chooser, picker, upload or start machine.
- `schema.ts`: `fieldsOf(requestSchema): EngineField[]`, walking `properties.intake` (and `properties.reference`). Supported leaf shapes: integer, `anyOf [integer, null]`, string with `maxLength`, `enum` (with or without `null`), `const`. Anything else (array, object leaf, a required integer with no source) makes `fieldsOf` return `unsupported`, and the chooser then lists the line as unavailable. The engine never offers a free number box for an id.
- A leaf's path is its dotted name under `intake` (for example `inputs.authorization_id`). That path is the `field` sent to `intake-sources`. A leaf is a record picker when its path is in the `fields[]` that `GET /projects/{case_id}/intake-sources?line=` returns for the chosen project, or when the line's config names another served source (escalation only, below).
- `engineForm(config): LineForm` builds a registry entry. `config` per line is small and static: `key`, `drawerTitle`, `startLabel`, `labels` (path to label and optional help), `parents` (path to the path it depends on), `order`, optional `optionsFrom`, optional `send`. Everything else (required, nullable, enum values, max length, the const values) comes from the served schema. If config and schema disagree on a path, the schema wins and the control for the extra config path is not drawn.
- Required rule: a leaf whose schema is not nullable and has no default is required (the control is marked and checked before sending). A nullable leaf is optional and sends `null` when empty. `reference` is a required text of 1..160 when the schema has it, and the field is not drawn when the schema lacks it. `background` is never sent. No client rule beyond the schema.
- `buildBody(values, ctx, line)` returns exactly the schema's keys: `line`, `case_id`, `case_revision`, `idempotency_key`, `intake` (nested by dotted path), `reference` when present. No other keys.
- `target(serverName, line)` maps a 422 `fields[].name`: `case_id`/`case_revision` to Project; `line`, `idempotency_key` to general; `reference` to Reference; `intake.<path>`, `<path>`, and `<path>` with the `intake.` prefix removed to that leaf's control; a name that is a prefix of a leaf path (for example `intake.inputs`) to its first control; any other name stays unmatched (existing "own box"). For minutes the names are the form's own (`template_id`, `audience`, `notes_file`, `reference`, `meeting_version_id`, `case_revision`).
- Additive changes to F-86's shared types (the weekly entry ignores them): `LineFormProps` gains `line: Line` and `onRevision(n)`; `LineForm.missing`, `buildBody` and `target` take the served `Line` as a last argument; `LineForm.send?(prepared)` is an optional replacement for the default `POST /work` call (used only by minutes); `useStart` calls `form.send` when present, else today's call, and keeps one state machine for 409, 422, uncertain and resend-same-body.
- Dependent pickers: a picker named in `parents` is disabled with "Choose <parent label> first." until its parent is chosen, sends `parent_id` as the parent's id, and clears when the parent changes or the project changes (`projectBound` is every picker path). Whenever an `intake-sources` answer carries `case_revision`, it replaces the revision the body will send.
- Idempotency, replay, CSRF, 401/403/404/409/413/415/429/5xx handling: exactly F-86's `useStart` (A-24: show whatever the server returns on a replayed key; the app adds no replay logic). A reused key with changed data is the server's 409; the form shows "This project changed since you opened it." and takes a new key, as in F-86.

### Lines and their fields (labels are the spec writer's, from field names; see Assumptions and LC-Q28)
Project is always first (F-86's picker). `Source` = `intake-sources` field.
| Line | Control (label) | Body key | Source / values | Required |
|---|---|---|---|---|
| `pmo-issues/v1` | Issue | `intake.issue_id` | source `issue_id` | yes |
| `pmo-escalation/v1` | Escalation request | `intake.request_id` | `GET <project.workflow_intake_url>` (`/projects/{case_id}/escalation-register`) `requests[{id, profile_id, direction, target}]`, label `<direction> to <target> · #<id>` from the served words; page with `?page=` while `next_page` is not null | yes |
| | Template | `intake.template_id` | source `template_id` | no, null |
| | Reference | `reference` | text 1..160 | yes |
| `pmo-emergency/v1` | Emergency record | `intake.profile_id` | source `profile_id` | yes |
| | Authorisation | `intake.inputs.authorization_id` | source `inputs.authorization_id`, `parent_id` = profile | no, null |
| | Outcome | `intake.inputs.outcome_id` | source `inputs.outcome_id`, `parent_id` = profile | no, null |
| | Template | `intake.inputs.template_id` | source `inputs.template_id` | no, null |
| | Audience | `intake.inputs.audience` | enum from the schema (internal, client); empty sends null | no, null |
| | Reference | `reference` | text 1..160 | yes |
| `pmo-change/v1` | Change version | `intake.version_id` | source `version_id` | yes |
| | Authorisation | `intake.inputs.authorization_id` | source `inputs.authorization_id`, `parent_id` = version | no, null |
| | Template | `intake.inputs.template_id` | source `inputs.template_id` | no, null |
| | Reference | `reference` | text 1..160 | yes |
| `pmo-minutes/v1` | Template | `template_id` | source `data.template_id` | yes |
| | Meeting | `meeting_version_id` | source `data.meeting_version_id` | no, omitted when empty |
| | Audience | `audience` | internal, client (the multipart schema's enum) | yes |
| | Notes file | `notes_file` | one file; no client type or size rule (server decides, 413/415 shown) | yes |
| | Reference | `reference` | text 1..160 | yes |
- Emergency and change send `null` for an empty optional. The server may refuse (for example an authorisation it needs); its 422 `fields[]` and message are shown as given.
- Choice labels for enums are the served values, first letter capitalised ("Internal", "Client"). Source picker rows show the served `label` unchanged.
- Escalation request rows: empty list says "No escalation requests to start from." Read error: the F-86 retry pattern.

### Minutes (multipart)
- `send`: `POST /api/v1/projects/{case_id}/minutes/intake`, `multipart/form-data`, fields `case_revision`, `idempotency_key`, `reference`, `template_id`, `audience`, `notes_file`, plus `meeting_version_id` only when chosen. `background` is not sent. Built with a `FormData` and `bodySerializer` exactly as `uploadCaseFile` does (no hand-set `Content-Type`). Answer: 200 `{work_id, state, revision, background}`, same handling as `POST /work`.
- The notes file is held in the form as a `File` and sent with the start; it is not uploaded to `POST /cases/{id}/files` (that route returns an upload id the minutes body cannot cite). The control is `FileUpload` from `@/components` with `accept={[]}` and `maxBytes={null}`; there is no second upload helper and no `uploadCaseFile` call here. A file chosen is cleared when the project changes. "Check again" after an uncertain answer resends the same file and key.

### Per-action uploads and the organisation picker
- None of the five bodies has a field that takes an `upload_id` or names an organisation options endpoint. The engine therefore ships the control slots (`engine/controls.ts`: `record`, `choice`, `text`, `file`) and F-86's `StartUpload`/`takesUpload`, and builds no `upload_id` field and no organisation picker in this feature (LC-Q31). F-88 owns the organisation picker for `received-bid`; F-94 and later lines add controls to `controls.ts` rather than a second renderer.
- `ownsSubmit` (F-88) is not used: all five lines are listed by `GET /lines` with `can_submit_via_api: true`. If F-88 has merged, the chooser's `ownsSubmit` path is left untouched.

### Registry and the weekly report
- `lines/index.ts` `FORMS` gains five entries made by `engineForm`. A line is startable when `can_submit_via_api` is true, `lineFormFor(key)` exists and `fieldsOf` is not `unsupported`; the chooser reads `Line` for that check. A new engine line is one config object in `lines/` and one registry line.
- The weekly report stays `lines/weeklyReport.tsx`. Why: it is built and reviewed in F-86; its week uses the date-range control and sends null template and content ids by design (the schema gives `start_at`/`end_at` only as strings, so a schema-driven form would draw two text boxes and lose the board's control); moving it adds risk and no new behaviour. A guard test (below) keeps it from drifting from the served schema.

### Screen states (every engine form)
- Loading: project picker and source pickers show the existing skeleton; a picker in flight is disabled.
- Empty: a picker with no rows says its own empty text (Project: "No projects to start this on."; sources: "Nothing to choose from." only if the served list is empty; escalation text above).
- Error: a failed read shows the retry pattern; the start's errors are F-86's notices (signed out, role refused, "This record is unavailable.", changed since opened, "Try again shortly.", server message for 413/415, "Not confirmed. Check before trying again.").
- Validation: required controls empty on press produce F-86's `ValidationSummary` ("<Label> is required.") and no request.
- Success: the drawer closes and opens `/work/{work_id}`; `onStarted(String(work_id))` for callers that pass it.

### Fixture examples (mock, Next 4980, mock 4981)
- `GET /lines` serves the five lines with `can_submit_via_api: true` and a `request_schema` copied from the shapes above (including `pmo-issues/v1` without `reference`), plus `pmo-leadership-report/v1` with `can_submit_via_api: true` and a schema the engine marks `unsupported`, plus F-86's weekly line.
- `GET /lines/projects?line=<key>` for each key (same two pages as F-86); `workflow_intake_url` set for escalation.
- `GET /projects/{case_id}/intake-sources`: without `field` returns the `fields[]` names for the line; with `field` returns rows; `parent_id` filters `inputs.authorization_id` and `inputs.outcome_id`; `before` pages (a 25 then 3 list for one field).
- `GET /projects/{case_id}/escalation-register`: `{revision, can_request, issues, profiles, requests[3], next_page: null}`.
- `POST /work` validates the body against the line's own `request_schema` (extra key, missing key, wrong type give 422 `fields[{name,message}]` with the typed names); 200 `{work_id: 4102, state: "processing", revision: 1, background: "not_requested"}`. F-86's cookie scenarios apply to every line.
- `POST /projects/{case_id}/minutes/intake`: reads the multipart parts, 422 for a missing part (`notes_file`, `template_id`, ...), 413 over a mock limit, 200 as above; the log records the part names and the file name.

## Lanes
- Frontend lane (all of this feature): `src/features/start-work/engine/**`, `src/features/start-work/lines/*.ts(x)` for the five entries, the additive edits to `lines/index.ts`, `LineForm.tsx`, `useStart.ts`, `LineChooser.tsx` named above, `mock/start-work.mjs`, `mock/fixtures/start-work/**`, `mock/server.mjs` route registration, tests under `src/**` and `e2e/start-work-lines.spec.ts`.
- Backend lane: none. Backend asks (not blockers): serve a `submit_url` and `content_type` for `pmo-minutes/v1` that match its upload route (LC-Q30); name the options source for each `request_schema` leaf.
- Integration owner: lane C coordinator. Shared files: `lines/index.ts`, `LineForm.tsx`, `useStart.ts`, `LineChooser.tsx` (F-86 owns; F-92 changes only what is named here; F-88 adds `ownsSubmit` in the same files, so build after both merge and rebase), `EvidencePicker.tsx`, `evidence.ts` (F-85, read only), `src/api/client.ts`, `errors.ts`, `live-schema.d.ts` (read only).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `fieldsOf` turns each of the five lines' served `request_schema` into the controls in the table, and returns `unsupported` for the leadership schema (array and object leaves) — verify: unit tests `engine/schema.test.ts` with the five fixtures and the leadership fixture; chooser test shows leadership as "Not available here yet".
2. `buildBody` for each line produces exactly the schema's keys and validates against that line's `request_schema` with `ajv` (already in `package.json`); no key beyond the schema, `background` absent, empty optionals are `null` — verify: unit test per line with ajv, and a test that adds one extra key and fails.
3. Guard: F-86's weekly `buildBody` output validates against the weekly `request_schema` fixture — verify: unit test `lines/weeklyReport.schema.test.ts`.
4. Issues: choosing a project and an issue (rows from `intake-sources?field=issue_id`) and pressing Start sends `{line, case_id, case_revision, idempotency_key, intake:{issue_id}}` with no `reference`, and opens `/work/4102` — verify: e2e with the mock request log.
5. Escalation: request rows come from the project's `workflow_intake_url` `requests`, labelled from the served direction and target; the body has `intake.request_id`, `intake.template_id` (null when empty) and `reference` — verify: e2e and unit test; an empty `requests` list shows "No escalation requests to start from."
6. Emergency and change: Authorisation and Outcome are disabled with "Choose <parent> first." until the record is chosen, send `parent_id` of that record, and clear when it changes or the project changes — verify: component test with a mocked `fetchSources` asserting the `parent_id` query and the clearing.
7. Minutes sends one multipart `POST /projects/{case_id}/minutes/intake` with parts `case_revision, idempotency_key, reference, template_id, audience, notes_file` (and `meeting_version_id` only when chosen) and no `background`, no `Content-Type` set by hand; no `/cases/{id}/files` call is made — verify: e2e mock log lists the part names and zero requests to `/files`; `grep -rn "uploadCaseFile" src/features/start-work/engine src/features/start-work/lines` returns nothing.
8. A required control left empty makes no request and the summary names each ("Template is required.", "Notes file is required.", "Reference is required.", ...) — verify: e2e counts requests to `/api/v1/work` and `/minutes/intake` (zero).
9. A 422 maps `fields[].name` to the right control for each line (engine table, including `intake.inputs.authorization_id`, a prefix name `intake.inputs`, and minutes' own names); an unknown name is drawn as its own box; none are dropped — verify: unit test per row of the table.
10. Replay and uncertain: a double press sends one request; a 503 locks the form with "Not confirmed. Check before trying again."; "Check again" resends the same body (and for minutes the same file) with the same key; a 409 or 422 gives a new key next press — verify: e2e with `start_uncertain` for one JSON line and for minutes comparing both request bodies and keys.
11. The `case_revision` sent is the latest one any `intake-sources` or `lines/projects` answer returned — verify: unit test with two answers carrying different revisions.
12. Permission and tenant: a project not in the viewer's `lines/projects` is never offered; a hand-edited `case_id` (`start_missing`) shows exactly "This record is unavailable."; a 403 shows "Your role doesn’t let you start this line."; `csrf_failed` refreshes the session once and does not show that text; 401 shows the signed-out state — verify: mock scenarios and unit tests, for one JSON line and minutes.
13. Provider failure: a source picker whose read fails shows the retry and does not block other fields; the mock stopped mid-start leaves one started work item at most — verify: e2e.
14. A line whose schema has a required leaf with no source, or any array or object leaf, appears as unavailable with "Open in the full form" and is never drawn as a partial form — verify: chooser unit test.
15. No second implementation: `grep -rn "FormData" src/features/start-work` matches only the minutes `send`; `LineChooser.tsx` imports no per-line form; the weekly entry is unchanged except the added optional arguments — verify: grep and the diff.
16. No invented rule: `grep -rn "8 days\|up to 8" src/features/start-work` returns nothing, and no field, enum value or length appears in the engine that is not read from the served schema or listed in this spec — verify: grep and review.
17. Layout follows the SCR-04 desktop and mobile minutes, issue, change, incident and escalation boards except as listed under "Conflicts with the boards" — verify: the fidelity tool run for those ten artboards.
18. Live: against Django on 8020 with a PM account, `GET /lines` returns the five lines with `request_schema`, one real start per line succeeds or returns a typed 422 shown on its control, and each opens `/work/{id}` — verify: manual run recorded in the PR with the `work_id`s and `oa.py live GET /api/v1/work/{work_id} 3`.

## Out of scope
- `pmo-weekly-report/v1` (F-86), `pmo-leadership-report/v1` (batch 2, LC-Q29), `pmo-finance/v1` (F-94), the received bid (F-88), every `finance-*`, `delivery-*`, `planning`, `commercial`, `engagement`, `rfp-response` line.
- An `upload_id` field, an organisation picker, `fileToEvidence` and converting an upload into evidence.
- Choosing a template or meeting by name beyond what the source rows say; creating a template, a meeting or an issue from the form.
- Client-side business rules (who may escalate, when an emergency is allowed, whether an authorisation is needed); the server decides.
- The `background` choice, per-line station summaries, group headings, any screen after the start.
- Changes to protected paths and any backend change.

## Conflicts with the boards
Entered as LC-Q28 to LC-Q31 in `delivery/connect/questions-batch.md` under "## Lane C".
1. Minutes board: Project, Meeting (required), Audience, Proof (optional). Spec: Meeting optional, adds required Template and Reference, and the file is required and is the notes file. Recommendation: accept (LC-Q28).
2. Issue board: Project, Issue. Spec matches; no Reference is shown because the server derives it.
3. Change board: Project, "What the client asked for" (long text), Proof. Spec: Change version, Authorisation, Template, Reference (live takes records, not free text). Recommendation: accept (LC-Q28).
4. Incident (emergency) board: Project, Incident, Plan (long text). Spec: Emergency record, Authorisation, Outcome, Template, Audience, Reference. Recommendation: accept (LC-Q28).
5. Escalation board: Project, From issue, Escalate to. Spec: Escalation request (direction and target already recorded), Template, Reference. Recommendation: accept (LC-Q28).
6. Leadership board is not built here (LC-Q29). No board draws the "Not available here yet" row beyond F-86's (LC-Q3).
7. No board draws a file control for minutes beyond "Proof"; the spec reuses the same upload box with the label "Notes file".

## Assumptions
- Field labels in the table are mine, taken from the schema names ("Authorisation" for `authorization_id`, "Emergency record" for `profile_id`, "Change version" for `version_id`, "Escalation request" for `request_id`). Reason: no served label exists (A-23: labels come from the screen). One `labels` object per line for the design engineer to edit.
- An optional nullable leaf sends `null` when empty. Reason: the schema lists it as required but nullable ("explicit unprovided value").
- The escalation request list uses the project's `workflow_intake_url`. Reason: `intake-sources` has no `request_id` field for this line; the register read is the only served source (`apps/core/factory_api/escalations.py` `register`).
- The five lines' `GET /lines` flags were read from the backend source, not from a live call. Reason: Django was not running; the build confirms on 8020 first and swaps a line for `engagement/v1` or `rfp-response/v1` if a flag differs.
- `pmo-leadership-report/v1` is deferred although readiness named it. Reason: its body needs `kind`, `audience`, a `selections` object with six id lists and a `scope` object, whose options come from `leadership-report-intake`, not `intake-sources`.
- Minutes uses the upload route, not the advertised JSON route. Reason: the JSON body needs an existing evidence id (`data.evidence_id`) and an upload id is not one (F-85); the upload route takes the file directly.
- The minutes file has no client file-type or size rule. Reason: A-27 says domain uploads set their own rules and none is published; the server's 413/415 text is shown.
- Weekly stays hand-built, with a schema guard test. Reason: see Registry and the weekly report.
