# The work item page shows live work, and the shared workspace can read any line through an adapter

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.22.0. Design: approved 13 Nov canvas under the recorded exception in `design/review.json`; screens: SCR-02 (work item), SCR-25 (weekly report, read only as the adapter proof).

## Summary
- `/work/[id]` and `/work/[id]/history` read the live `GET /work/{work_id}` and `GET /work/{work_id}/history` instead of the v7 mock shape. The page shows title, state tag, next step, blocker, current activity, progress, decisions waiting (links only) and the link to the finished output.
- The station track, six facts strip and agent steps are hidden (LC-Q1 option 1). Nothing is derived from history and no "not available" placeholders are drawn.
- `src/features/workspace` gains a small per-line adapter interface: a panel URL becomes the existing section objects, and a step becomes a typed command descriptor carrying its revision tokens and idempotency key. Types, one reference adapter and tests only; no write is wired.
- A shared evidence picker uploads a file with `POST /cases/{case_id}/files` and returns the `upload_id`. It also exposes the file-draft review path to `reviewed_evidence_id` as a labelled proposal (backend question 1). Nothing writes through it in this feature.
- The weekly report panel (`panels[].key = weekly-report`, `GET /work/{id}/weekly-report`) is rendered read-only through the adapter as the proof. All writes are F-87.

## Context
Where this lives today (lane C worktree `/Users/Hunchoo/psl-factory-worktrees/lane-c/frontend`):
- Page: `src/features/work-item/` (`WorkItemView.tsx`, `WorkItemOverview.tsx`, `WorkItemHistory.tsx`, `WorkItemStates.tsx`, `labels.ts`, `presentation.ts`, `useWorkItem.ts`, `useWorkHistory.ts`). `labels.ts` types `WorkItem` from the v7 `E-WORK-ITEM` (it carries `stations`, `facts`, `agent`, `workspace`). `useWorkItem.ts` polls every 5 s while `agent.status === 'working'`.
- Shared frame: `src/features/workspace/` (`Workspace.tsx`, `Sections.tsx`, `Steps.tsx`, `StepForm.tsx`, `useWorkspaceStep.ts`, `labels.ts`). `labels.ts` types `Section`, `Item`, `Cell`, `Step` from `item.workspace` (v7). The generic renderer is kept; the generic step engine is not reused here.
- API: `src/api/client.ts` already exposes `api` (v7) and `liveApi` (live contract, `src/api/live-schema.d.ts`) sharing one CSRF token, plus `call()` and `refreshSession()`. F-56/F-57 added the live client; reuse it. `src/api/errors.ts` maps 401/403/404/409/422 only.
- Upload: `src/components/FileUpload.tsx` is the one file field (D-171); `PROOF_TYPES`, `PROOF_MAX_BYTES`.
- Mock: `frontend/mock/server.mjs` with `mock/session.mjs` as the model for live-shaped frame reads.
- Live reads used (viewer: `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/work/{work_id} 3`):
  - `GET /work/{work_id}` required: `id, case_id, title, line, state, status_label, owner|null, sample, updated_at, django_url, api_url, revision|null, case_revision|null, next_step, blocker, tasks[], screens[], actions[], progress{status,updated_at}|null, aggregate|null, panels[{key,url}], output_url|null, information[], available_control[]`; optional `current_activity{label,watching}`, `department_handoff_url`, `profile_adoption`.
  - `GET /work/{work_id}/history?kind=worker|decision|evidence` returns `{items[{at, station, status, task_id?, actor?, reason?, evidence_id?}] (max 30), as_of}`.
  - `GET /work/{work_id}/weekly-report` returns `{expected_revision, case_revision, selection{start_at,end_at,template_id,content_id}, editable_parts|null, draft|null, return_review_id|null, can_correct, document_version_id|null, review_verdicts[], recipients[], next_action, evidence[]}`.
  - `POST /cases/{case_id}/files` (multipart `file`) returns 200 `{upload_id, name, size, sha256, download_url}`; errors 400/403/404/413/415/422/429.

## Contract

### Work item read (live)
- Route `/work/[id]` where `id` is the integer live work id. Request `GET /api/v1/work/{id}` through `call(liveApi.GET(...))`. Types come from `live-schema.d.ts`; the page no longer imports the v7 `WorkItem`.
- Mapping to the page (presentation only; nothing here decides access):
  | Page part | Source |
  |---|---|
  | Title; sample tag when `sample` | `title`, `sample` |
  | State tag (11 states, same words as `STATE_TAGS`); `status_label` as its sub-line | `state`, `status_label` |
  | Next step | `next_step` (shown when non-empty) |
  | Why it is stuck | `blocker` (shown when non-empty; empty means none, not an error) |
  | Current activity line | `current_activity.label` when present; else `progress.status` with "Updated {updated_at}" |
  | "With" | `owner` when not null; null shows nothing, never "Unassigned" |
  | "Updated" | `updated_at` |
  | Decisions waiting | `tasks[]`: one row each (`kind`, `role`, `status`), a link to `tasks[].url`'s page route (`/work/{id}/decide?task={id}`), and "Open decision" only when `can_decide` or `can_claim`; otherwise the row is read only. No claim or decide call is made here |
  | Open the output | link to `output_url` when not null (present only when verified and unchanged) |
  | Line panels | `panels[]`: for a key with a registered adapter the section list is drawn; a key with no adapter shows its key as a link to the panel URL's page when one exists, else is omitted |
  | History | link to `/work/{id}/history` |
- Not drawn, with no placeholder: station track, six facts, agent card and steps, started by, started at, amount, reference, project crumbs beyond the project title, state-panel prose, approval chain, `screens[]`, `django_url`, `information[]` (F-87), `actions[]`/`available_control[]` buttons (F-87), `aggregate` (payroll recipient view, not in scope).
- Polling: re-read every 5 s while `current_activity.watching === true` or `state === 'processing'`, and the page is visible (keep `POLL_MS`, the visibility handling and the "keep last good item on a failed poll, stop on lost access" behaviour of `useWorkItem.ts`). No polling otherwise.
- Revision tokens: `revision` and `case_revision` are held in the loaded item for the adapter's command descriptors; they may be `null` and are then passed on as unknown, never 0.
- States:
  - Loading: existing `WorkItemStates` loading.
  - Error: 401 shows signed-out state linking to `/sign-in?next=<current path>`; 403 `forbidden` shows no-access; 403 `csrf_failed` is not shown as no-access (refresh session, say "Refresh your session and try again"); 404, 429, 503 and network each show their own plain wording with Try again (429 and 503: "Try again shortly"). Reads may be retried; there is no write here.
  - Permission state: 404 `{code:'not_found', message:'This record is unavailable.'}` shows one wording for "missing" and "not yours": "This record is unavailable." No existence leak, and no difference between the two cases. The optional access-request control (`POST /work/{id}/access-request`) is not built.
  - Empty: an item with no tasks, no panels and empty `blocker`/`next_step` shows only the header and state; the missing sections are simply absent.
  - Success: as the table above.
- Fixture examples (the mock serves these for numeric ids; v7 `W-xxxx` ids keep their v7 answers for the pages not yet moved, such as decide and respond):
  - `4101` verified: `state:"verified"`, `output_url:"/api/v1/..."`, `panels:[]`, `blocker:""`.
  - `4102` processing: `state:"processing"`, `current_activity:{label:"Drafting the weekly update", watching:true}`, `panels:[{key:"weekly-report", url:"/api/v1/work/4102/weekly-report"}]`.
  - `4103` decision waiting: one `tasks[]` row with `can_decide:true, verdicts:["approve","return"]`.
  - `4104` stuck: `state:"setup_needed"`, `blocker:"A policy value is missing."`, `revision:null`, `case_revision:null`.
  - `4105` handoff-only view: `revision:null`. `4106`: 404 for any caller.

### History read (live)
- `GET /api/v1/work/{id}/history?kind=` with `kind` one of `worker`, `decision`, `evidence`; no `kind` for all. Filter tabs map: All, Decisions (`decision`), Agent work (`worker`), Evidence (`evidence`). No counts, no paging, no limit control (live has none).
- Each row: time (`at`), then words from `station` and `status`, `actor` when present, `reason` when present, and an evidence link only when `evidence_id` is set. A row whose `actor` is absent shows no actor. Unknown station or status values are shown as the raw text, never dropped.
- Caption: "Showing the latest 30 changes. As of {as_of}." (the as-of time from the response; the 30 only when exactly 30 rows came back, else "Showing all changes.").
- States: loading, empty ("No changes recorded yet."), error (same mapping as above, keeping the filter), success.
- Pending the design engineer: LC-Q4. This spec follows option 1.

### Per-line adapter (shared, lanes A and B build on this)
File `src/features/workspace/adapter.ts` (new), exported types only plus a registry. Keep it this small:

```ts
// A panel is one entry of GET /work/{id} panels[]: { key, url }.
export type PanelRef = { key: string; url: string };

// What every adapter reads from: the loaded work item (live) and the panel's own readback body.
export type LineContext = { workId: number; caseId: string; revision: number | null; caseRevision: number | null };

export type LineAdapter<Readback = unknown> = {
  key: string;                                   // the panels[].key it handles, e.g. 'weekly-report'
  read(ref: PanelRef): Promise<Readback>;        // GET ref.url through liveApi / call(); throws ApiError
  sections(readback: Readback, ctx: LineContext): Section[];   // existing Section objects (workspace/labels.ts)
  // Commands are described, not sent. F-87 and later lanes add `send`.
  commands?(readback: Readback, ctx: LineContext): CommandDescriptor[];
};

// One typed command on a line's own resource.
export type CommandDescriptor = {
  id: string;                                    // stable, e.g. 'weekly-report.correct'
  label: string;                                 // button words
  method: 'POST';
  url: string;                                   // the line's own route
  tokens: { expected_revision?: number | null; case_revision?: number | null; action_revision?: number | null; task_revision?: number | null; revision?: number | null };
  idempotency: { field: 'operation' | 'operation_key' | 'key' | null; value: string | null }; // uuid made once per attempt (newIdempotencyKey); null for a line with no key field
  body(inputs: Record<string, unknown>): Record<string, unknown>; // adds action + tokens + the key field
  disabledReason?: string;                       // from the readback (e.g. can_correct false), never invented
  successStatuses: (200 | 201 | 202)[];          // live commands answer 200, 201 or 202
};

export function registerLineAdapter(a: LineAdapter): void;
export function adapterFor(key: string): LineAdapter | undefined;
```
Rules: a `null` token stays `null` (unknown, not 0); `commands` is never called to send in this feature; the existing `useWorkspaceStep` locking is left alone and reused by F-87. Sections must keep the "unknown is not zero" rendering, "As of" lines and `restricted` rows the renderer already has. An adapter never invents text a readback does not carry.

### Reference adapter: weekly report (read only)
`adapter` key `weekly-report`, reading `GET /work/{id}/weekly-report`. Sections drawn, using existing kinds:
- Period: `selection.start_at` to `selection.end_at`; template and content ids shown only if the readback carries a name (it carries ids only, so they are omitted).
- Draft parts: `editable_parts` (status, risks, timeline, next_steps, each `{text, evidence_ids[]}`) when not null; `draft` when `editable_parts` is null and the draft carries the same part shape; the number of cited evidence ids per part ("3 records cited"), no labels (backend question C-15).
- Review: `review_verdicts` as read-only words only when the readback also exposes a review in progress; `return_review_id` as "Returned to you" with no note text (not served, C-16).
- Recipients: `recipients[]` rows `{name, status, receipt_id, recorded_at}`; `receipt_id` null shows "No receipt yet", never a tick.
- Next action: `next_action` text.
- `commands()` returns descriptors for `correct` (tokens `expected_revision`, `case_revision`; `disabledReason` set when `can_correct` is false) and nothing else; they are tested for shape and not rendered as buttons.
- Unknown or null values render as "Not recorded", never 0.

### Evidence picker (shared)
Files `src/features/workspace/EvidencePicker.tsx` and `src/features/workspace/evidence.ts` (new). Built on `FileUpload`.
- `uploadCaseFile(caseId, file): Promise<{upload_id, name, size, sha256, download_url}>`: multipart `POST /api/v1/cases/{case_id}/files` with `file`; `X-CSRFToken` from the shared client. Do not set `Content-Type` by hand. Refuses before sending a file over `PROOF_MAX_BYTES` or with a type outside `PROOF_TYPES` (the service stays the final rule).
- Error mapping for the row: 413 "That file is too large."; 415 "That file type isn't accepted."; 422 shows the first `fields[].message`; 429 "Try again shortly."; 403 `csrf_failed` refreshes the session and says "Press upload again" (the file was not sent); 404 "This record is unavailable."; network "We couldn't reach the server. Nothing was uploaded."
- A failed upload is never retried by itself; the row offers Try again (user press). The same file chosen twice is two uploads (live has no upload key); the picker disables the zone while one upload runs.
- Component props: `{ caseId: string; value: UploadedFile | null; onChange(file | null): void; disabledReason?: string }`; it returns the `upload_id` through `onChange`. An `upload_id` is NOT an evidence id and the types must keep them distinct (`UploadId` vs `EvidenceId` branded numbers).
- Proposal (backend question 1, labelled in code and in the PR as unconfirmed): `fileToEvidence(caseId, uploadId, role)` runs `POST /cases/{case_id}/files/{upload_id}/drafts` `{role}` (202) then, after a human reviews the draft, `POST /cases/{case_id}/file-drafts/{job_id}/review` `{draft, summary, gaps, note}` (200) and returns `reviewed_evidence_id` (number or null). It is exported and unit-tested against the mock; it is not rendered in any page, no line command consumes it, and no `role` default is chosen. Null `reviewed_evidence_id` means "not evidence yet" and is passed on as null.

### Idempotency and versioning
This feature sends no writes except the file upload, which has no key or revision token. Reads send none. Command descriptors carry tokens as above.

### Permission and tenant rules
Every read is made as the signed-in person; the backend answers 404 for "missing" and "not yours" alike and the UI must not distinguish them. The picker uploads only into the `case_id` of the loaded work item (never one typed by the person). No client-side role check decides access; `can_decide`, `can_claim`, `can_correct` are shown as the backend sent them.

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/work-item/**`, `frontend/src/features/workspace/adapter.ts`, `workspace/EvidencePicker.tsx`, `workspace/evidence.ts`, `workspace/weeklyReportAdapter.ts`, `frontend/src/api/types.ts` (live work item and history types), `frontend/mock/**` (live-shaped work detail, history, weekly report and file routes), tests under `frontend/src/**` and `frontend/e2e/work-item*.spec.ts`.
- Backend lane: none. No backend change; backend questions LC-1 and LC-2 are in `delivery/connect/backend-questions.md`.
- Integration owner: lane C coordinator. Shared files this feature touches and who owns them: `src/features/workspace/*` (lane C owns the frame and adapter; lanes A and B add adapters only as separate small commits after `git merge origin/main`), `src/api/*` (shared; edits limited to live types and the error mapping for 400/413/415/429/503 if not already done), `src/shell/*` (lane A; not touched), `src/components/*` (FileUpload is used as is).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. Opening `/work/4102` against the mock (Next 4980, mock 4981) shows the title, a "Processing" state tag, the next step, and "Drafting the weekly update" as the activity line; no station track, six facts strip or agent steps are on the page, and no "not available" text appears — verify: open the page and view the DOM; `frontend/e2e/work-item.spec.ts` asserts those three parts are absent.
2. The same page against live Django (8020, Postgres 55433, account live-lead) for a real work id shows the live `title`, `status_label`, `next_step` and `blocker`, matching `GET /api/v1/work/{id}` — verify: compare the page with `oa.py live GET /api/v1/work/{work_id} 3` output and the JSON from `curl` with the session.
3. The page makes no request to the v7 mock-only fields: its code imports the `WorkItem` type from the live schema and not from `@/api/schema` — verify: `grep -rn "api/schema'" frontend/src/features/work-item` returns nothing for work item types.
4. While `current_activity.watching` is true the page re-reads every 5 s; with `watching:false` and a state other than `processing` it makes one read only; a hidden tab pauses reads — verify: unit test `useWorkItem` with fake timers; in the browser network panel count `GET /work/4102` calls.
5. A failed poll keeps the last good item on screen and shows the "couldn't refresh" note; a 401, 403 or 404 on a poll replaces the page with the matching state and stops polling — verify: unit test with a mocked client.
6. `/work/4106` (mock) and a live id the account cannot see both show exactly "This record is unavailable." with no difference between them — verify: open both and compare the text; unit test on the 404 body.
7. A 403 with `code:'csrf_failed'` does not show "Your account can't use PSL Factory" or the no-access state; it refreshes the session and says to try again — verify: mock scenario `csrf_failed` plus unit test.
8. A 401 shows the signed-out state with a link to `/sign-in?next=` the current path — verify: sign out in the mock, open `/work/4102`, click the link.
9. Decisions waiting (`/work/4103`) show one row with its role and status and an "Open decision" link to `/work/4103/decide?task=<id>` only when `can_decide` or `can_claim` is true; a row with both false has no link; the page makes no claim or decision call — verify: e2e plus network panel.
10. A verified item (`/work/4101`) shows an "Open the output" link equal to `output_url`; an item with `output_url:null` shows none — verify: e2e on both fixtures.
11. A null `revision` or `case_revision` (`/work/4104`, `/work/4105`) is not rendered as 0 and the page loads — verify: e2e plus unit test on the item mapper.
12. `/work/4101/history` lists rows from `GET /work/{id}/history`; the Decisions, Agent work and Evidence tabs call it with `kind=decision`, `worker` and `evidence`; no counts and no "show more" are drawn; the caption reads "Showing the latest 30 changes. As of …" only when 30 rows came back — verify: unit and e2e tests; network panel.
13. A history row with an unknown `station` or `status` shows the raw text; a row without `actor` shows no actor; an `evidence_id` of null shows no evidence link — verify: unit test on the row mapper.
14. History empty shows "No changes recorded yet."; a history error shows the mapped message with Try again and keeps the chosen tab — verify: mock scenarios and e2e.
15. No write button (Resume, Cancel, Check what happened, Release, Start, Correct) appears on the page, and no `POST` other than the file upload is made by anything in this feature — verify: e2e asserts no such buttons; grep `liveApi.POST` in the new files shows only the upload and the picker's proposal calls.
16. `src/features/workspace/adapter.ts` exports `PanelRef`, `LineContext`, `LineAdapter`, `CommandDescriptor`, `registerLineAdapter`, `adapterFor` as specified, and a test registers a fake adapter, reads its panel, gets `Section[]` that the existing `Sections` renderer draws, and gets a `CommandDescriptor` whose `body()` includes the action, the tokens and a uuid key — verify: `adapter.test.ts`; typecheck passes.
17. A `null` token in a descriptor stays `null` in `body()`; a line with no key field gives `idempotency.field === null` and no key in the body — verify: `adapter.test.ts`.
18. `/work/4102` renders the weekly report panel through the adapter: the period, the four parts with "N records cited", the recipients with their receipt state, and `next_action`; a recipient with `receipt_id:null` reads "No receipt yet"; a null `editable_parts` and `draft` show no parts section — verify: e2e on 4102 and unit test on `weeklyReportAdapter`.
19. Against live Django, a weekly report work item's panel shows the same period and recipients as `GET /api/v1/work/{id}/weekly-report` — verify: compare the page with the `curl` JSON.
20. A `panels[]` entry whose key has no registered adapter does not break the page: it is omitted or shown as a link, and the rest of the page loads — verify: unit test with an unknown key.
21. The weekly report descriptor for `correct` is returned with `disabledReason` set when `can_correct` is false, and is not rendered as a button — verify: unit test and e2e (no button).
22. The picker uploads a PDF to `POST /cases/{case_id}/files` as multipart and returns the `upload_id`; the same call against live Django returns 200 with `upload_id`, `name`, `size`, `sha256` — verify: unit test against the mock; a live check with `live-lead` on a case they may write to, shown by the returned JSON.
23. The picker refuses a `.exe` and a file over 10 MB before any request is sent, and shows the file row's error with Try again — verify: unit test asserts no fetch call.
24. Upload errors map as specified: mock scenarios 413, 415, 422 (with `fields`), 429, 404 and a dropped network each show their own wording, and a failed upload is not retried until Try again is pressed — verify: unit tests; count fetch calls.
25. A 403 `csrf_failed` during upload refreshes the session once and says "Press upload again"; no automatic second upload — verify: unit test counts fetch calls (one upload, one session read).
26. The picker's types keep `UploadId` and `EvidenceId` distinct: assigning an `UploadId` where an `EvidenceId` is expected fails typecheck — verify: a `// @ts-expect-error` test in `evidence.test.ts`.
27. `fileToEvidence` calls the drafts route, then the review route, and returns `reviewed_evidence_id`; a null result is returned as null and the code and the PR description label it "proposal, backend question 1" — verify: unit test against the mock; grep for the label.
28. The picker and the proposal are not rendered by any page and the PR lists them as unused-by-design until F-87 — verify: grep for `EvidencePicker` imports shows only tests.
29. The picker uploads only to the loaded item's `case_id`; there is no input for a case id — verify: component test and props type.
30. Viewport check at 1440 and 390: the page matches the SCR-02 work item boards for the parts that remain (header, tag, next step, decisions waiting, output link); the hidden parts leave no empty gap or empty heading — verify: screenshots at both widths reviewed against `design/screens.md` SCR-02 artboards.
31. `npm run lint`, `npm run typecheck` and `npm test` pass, and `api-live-schema-drift.test.ts` still passes with `live-schema.d.ts` regenerated from contract 1.22.0 — verify: `delivery/checks.sh` result.

## Out of scope
- All writes: reconcile and "Check what happened", resume/cancel/adopt profile, background pause, release invoice, invoice information, proof, draft stop, weekly report review and correct, corrections, coordination retry, access request (all F-87).
- Claiming or deciding a task (SCR-03, a separate feature); the decision card content from `GET /tasks/{id}`.
- Any other line's adapter, any other panel (forecast, bid, release register, invoice and so on).
- Building a station track, six facts or agent steps from history or panels; "not available yet" placeholders (LC-Q1 option 2 or 3 would be a later change).
- History counts, paging, sentence writing beyond the fields live returns; reference, started by, amount; the payroll `aggregate` view; `screens[]` and `django_url` links.
- Wiring the picker or `fileToEvidence` into any form; recording evidence from a note; choosing a file-agent `role`.
- Backend, migrations, contract edits.

## Assumptions
- The mock serves the live work-item shape for numeric ids and keeps the v7 shape for `W-xxxx` ids, so pages not yet moved (decide, respond) keep working. Reason: both shapes live at the same path and the live ids are integers.
- Fixture ids 4101 to 4106 are the builder's to create in `frontend/mock/`; the shapes above are the contract, the numbers are free. Reason: no live fixtures exist yet.
- The decision link target is the existing `/work/{id}/decide?task={id}` route; `tasks[].url` (an API or Django URL) is not followed. Reason: `url` names backend pages.
- "Updated {updated_at}" stands in for age. Reason: `started_at` is not in live (LC-Q6).
- State tag words come from the existing `STATE_TAGS`. Reason: the 11 live states equal the 11 v7 states.
- Station, status and actor words in history are shown as given by the API, lightly capitalised. Reason: no sentence field exists (LC-Q4).
- Weekly report cites are shown as counts, not labels. Reason: `evidence[]` has only `{id, version, kind}` (C-15).
- The file-draft review route is the proposal for evidence ids. Reason: the only path found in the contract (backend question 1, LC-2).
- 400/413/415/429/503 get their own error kinds in `src/api/errors.ts` if lane A has not already added them; if it has, reuse. Reason: the shared mapping folds them into `server`.

## Conflicts with the boards
All approved SCR-02 parts that this spec removes or changes; the design engineer decides once before build. Entered in `delivery/connect/questions-batch.md`.
1. Station track (CMP-02), six facts strip, and the agent card with numbered steps: removed from the page. Recommendation: hide (LC-Q1 option 1).
2. History: per-filter counts, sentence rows with actor kind and "restricted" marks, and "show more" are removed; filter tabs stay, with a 30-row caption. Recommendation: LC-Q4 option 1.
3. Resume, Cancel, "Confirm what happened" and the decision card are not drawn here (writes in F-87, decision on its own page). Recommendation: leave out until F-87 (LC-Q5 option 1).
4. Reference, started by, started at and amount are removed; "With" (owner) and "Updated" are added from live. Recommendation: LC-Q6 option 1.
5. Added to the page that the boards do not draw: `blocker` line and `current_activity` line. Recommendation: keep both; they are the live replacements for the hidden parts and need a board by the design engineer.
6. Project crumbs and tabs below the title use the project title only; the line subtitle and byline have no live source. Recommendation: draw the crumb from the project title (via `GET /projects/{case_id}`) and drop the byline.
