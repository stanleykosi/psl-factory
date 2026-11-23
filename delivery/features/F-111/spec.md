# The issue workspace shows a live project issue, read only (SCR-30 part 1)

> Tasks: FE-CONNECT-1. Architecture: v9 package; contract `contracts/psl-factory.openapi.json` 1.24.0 (main b8542c79). Design: approved 13 Nov canvas under the D-173/D-181 exceptions in `design/review.json`; screens: SCR-30 (default, overdue, no-owner, verified; desktop and mobile; 8 boards in `design/canvas/project/SCR-30-*.dc.html`).

## Summary
- `/work/{id}` for an issue follow-up item (line `pmo-issues/v1`, panel key `issue-followup`) reads live data: the work item, the issue follow-up read, the issue detail, the owner messages and the work history.
- The page shows reference, title, severity, status (Open, In Progress, Resolved, Closed), owner, raised date, age, the blocked-milestone link, "What has happened", "Chasing", and the no-owner and overdue banners.
- It is an issue adapter on F-85's shared line adapter (`LineAdapter`, key `issue-followup`). It adds one adapter file and its mock and tests. It does not touch `frontend/src/features/workspace` frame code.
- Read only. Owner update, reply, set owner, message owner, refresh and restart, and raise escalation are F-111B or other features. Their buttons render hidden or disabled and send nothing.
- Wait: the builder starts after F-85 (PR #101) is on main. This feature depends on F-85's `adapter.ts`, the live work item read and the live history read.

## Context
- Page and frame (lane C owns, read only here): `frontend/src/features/work-item/` (`WorkItemView.tsx`, `WorkItemOverview.tsx`, `useWorkItem.ts`), `frontend/src/features/workspace/` (`Workspace.tsx`, `Sections.tsx`, `AssignForm.tsx`, `labels.ts`). After F-85 they carry `workspace/adapter.ts` (`registerLineAdapter`, `adapterFor`, `LineAdapter`, `CommandDescriptor`) and a live work item with `panels[{key,url}]`.
- The v7 build of this screen is F-30 (`delivery/features/F-30/spec.md`, fixtures `frontend/mock/fixtures/work/W-2411..2414`, `W-3609`). It drew `workspace.sections` from the v7 item. Live has no `workspace` object, so the sections are now built by the adapter.
- Live panel: `apps/core/factory_api/work.py` `STATION_PANELS['pmo-issues/v1'] = ('issue-followup',)`, so `GET /work/{id}` returns `panels:[{key:'issue-followup', url:'/api/v1/work/{id}/issue-followup'}]`.
- Live operations (look up with `python3 delivery/connect/oa.py live GET <path> 4`):
  - `GET /api/v1/work/{work_id}/issue-followup` (`issues_work_detail`) returns `{expected_revision, case_revision, issue, team, source_id, can_request_update, blocked_milestone|null, blocked_planned_milestone|null, response_task{id,revision}|null, next_action, finding}`.
  - `GET /api/v1/projects/{case_id}/issues/{issue_id}` (`issues_detail`) returns `{case_revision, issue, team, blocked_milestone, blocked_planned_milestone, history[{id,status,at}], messages_url, timeline[{id|null, kind: state|acknowledgement|request|reminder, status, at}], acknowledgement{status, at|null, basis|null, reply_id|null}}`.
  - `GET /api/v1/projects/{case_id}/issues/{issue_id}/messages` (`issue_communications_index`) returns `{case_revision, state_id, items[{draft_id, version, kind: request|reminder, body, status, review_id, verdict, dispatch_id, receipt, finding}], evidence[{id,version,kind}], timing{last_receipt_id, reminder_due_at, escalation_due_at, reminder_overdue, escalation_overdue, escalation_target, finding}|null}`.
  - `GET /api/v1/work/{work_id}/history?kind=` (shared with F-85).
  - `issue` is `{id, state_id, reference, title, kind, status, severity: Critical|High|Medium|Low|null, owner_id, next_action, opened_at|null, age_days|null, acknowledged_at|null, resolved_at|null}`; `team` is `{mode: team|internal, status, assignment_id|null, label, can_record, can_resolve, finding}`.
- Backend answers: D-2 (raised date and age come from `issue.opened_at` and `issue.age_days`; the blocked milestone from `blocked_milestone` or `blocked_planned_milestone`), D-3 (`timeline` is the bounded "what has happened" list; the Messages read keeps its own permissions and carries the reminder timing), D-4 (writes only, F-111B).
- Connection map: `delivery/connect/screens-d-delivery-issues-escalation.md` section SCR-30 and DC-1 to DC-5.

## Contract

### Reads (all as the signed-in person; no client role check decides access)
1. `GET /api/v1/work/{id}` (F-85's read). `panels` must contain `issue-followup`; otherwise the page falls back to F-85's generic page (header, state, next step, blocker).
2. Adapter `read(ref)` for `issue-followup`: `GET ref.url` (the follow-up read). It gives `issue.id` and `case_revision`. The case id comes from the work item's `case_id`, never from the follow-up body.
3. Then, in parallel: `GET /projects/{case_id}/issues/{issue.id}` (detail, timeline) and `GET /projects/{case_id}/issues/{issue.id}/messages` (chasing, timing). The panel counts as loaded when the follow-up and the detail have answered. The messages read is a separate section state (below).
4. `GET /work/{id}/history` is read only through the existing history page route (`/work/{id}/history`), as F-85 builds it. This feature adds a "See full history" link to it and uses no history rows to build the timeline (D-3).
5. Polling: F-85's rule (every 5 s while `current_activity.watching` or `state === 'processing'`, page visible). On each tick the adapter re-reads the three issue reads together. A failed poll keeps the last good data and shows "couldn't refresh". Reads only.

### Mapping to the page (presentation only)
| Page part | Source |
|---|---|
| Reference, title | `issue.reference`, `issue.title` |
| Severity tag | `issue.severity`, words as sent (Critical, High, Medium, Low). Null: no severity tag, no placeholder |
| Status tag | `issue.status` as sent: Open, In Progress, Resolved, Closed. Tone: Open = waiting (amber), In Progress = agent (blue), Resolved = done (green), Closed = neutral. The v7 words "FIX IN TESTING", "FOLLOW-UP VERIFIED", "NO RESPONSE · n DAYS" and "OWNER NEEDED" are not shown as status text (see Questions 1) |
| Owner | `team.label`. `issue.owner_id` is an id only and is never drawn. A recorded-by wording is drawn only if the response carries it (it does not), so none is drawn |
| Raised | `issue.opened_at` as a date and time; null reads "Not recorded" |
| Age | `issue.age_days` as "N days" (1 reads "1 day", 0 reads "Today"); null reads "Not recorded", never 0 |
| Blocks | `blocked_milestone.name` as a link to its page route (the milestone id into the project's milestones route; the API `url` is not followed). If null and `blocked_planned_milestone` is set: its `name` with the word "planned" and the stage (UAT or completion), not a link. Both null: the Blocks fact is not drawn |
| What has happened | `timeline[]` of the issue detail, in the order sent, newest last. Each row: time `at`, and words from `kind` and `status` ("Logged"/"Status changed" for `state`, "Owner acknowledged" for `acknowledgement`, "Update requested" for `request`, "Reminder" for `reminder`) followed by `status` as sent. Unknown `kind` or empty `status` shows the raw text. Rows are shown with the backend's attribution only; no actor name is composed. Empty timeline: "Nothing has happened yet." |
| Acknowledgement line | `acknowledgement.status`, and `at` when not null; `basis` as a plain line when not null. Null `at` reads "Not acknowledged yet" |
| Chasing | `messages.items[]`: one row per item with kind ("Asked" for `request`, "Reminder" for `reminder`), `status`, and its `receipt` word when not null (null shows "No receipt yet", never a tick); `finding` under the row when not empty. Then the timing rows: "Reminder due" `timing.reminder_due_at`, "Escalate by" `timing.escalation_due_at`, and `timing.escalation_target` when not null. A null date reads "Not set". `timing` null: only the items; no timing rows. No items and no timing: "No message has been sent to the owner." |
| Overdue banner | shown when `timing.reminder_overdue` or `timing.escalation_overdue` is true; wording is `timing.finding` when not empty, else "The owner has not responded in time." Never worked out from dates |
| No-owner banner | shown when `team.assignment_id === null` and the issue is not Resolved or Closed (Questions 3); `team.status` is not parsed. Text: `team.finding`, then `next_action` |
| Next | `next_action` from the follow-up read, and `finding` when not empty |
| Verified | the work item's `state === 'verified'` (F-85 state tag) with the follow-up's `finding` as the lead sentence. The page never says the issue is closed unless `issue.status` is `Closed`; it never claims verified from agent text |
| Allowed actions | from the follow-up read only: `can_request_update`, `team.can_record`, `team.can_resolve`, `response_task` (null = no owner response task). A write control is hidden when its flag is false and drawn disabled, with no invented reason text, when it is true; none does anything until F-111B (Questions 2) |
| Links | "Open the issue register" to `/projects/{case_id}/registers`; "See full history" to `/work/{id}/history`; "Back to project" as the existing frame |

Not drawn, with no placeholder: Tola's note and its steps (DC-3, D-182/D-185), the v7 "FIX IN TESTING" wording, "recorded by PM", chasing rows not in `messages.items`, the owner choices list (`GET .../issues` `owners[]` is a write input, F-111B), `issue.owner_id`, `source_id`, `state_id`, `response_task` ids, evidence ids, `blocked_planned_milestone.policy_id`.

### Adapter
File `frontend/src/features/issue-followup/issueFollowupAdapter.ts` (new), registered under key `issue-followup` through `registerLineAdapter` from F-85's `workspace/adapter.ts`:
- `read(ref)` as above, returning `{followup, detail, messages: Messages | {error: ApiError}}`.
- `sections(readback, ctx)` returns existing `Section[]` kinds (`facts`, `timeline`, `text`) so the existing `Sections` renderer draws them: `facts` (Owner, Raised, Age, Blocks), `text` lead (banner or finding), `timeline` "What has happened", `timeline` "Chasing", `text` "Next".
- `commands()` returns no descriptor in this feature (writes are F-111B). Tokens `expected_revision` and `case_revision` are held in the readback for F-111B, never defaulted to 0.
- Types for the three reads come from `frontend/src/api/live-schema.d.ts` (regenerated from 1.24.0); no hand-written copy.

### Section states
Each of the page, "What has happened" and "Chasing" has its own state:
- Loading: F-85's loading state; sections show a skeleton; no zero values.
- Empty: as in the table (timeline and chasing empty wordings); a section never shows an empty heading with nothing under it.
- Error: 401 signed-out state linking to `/sign-in?next=<current path>`; 403 `forbidden` no-access state; 403 `csrf_failed` is not no-access (refresh session, "Refresh your session and try again"); 404 shows "This record is unavailable." for missing and not-yours alike; 429 and 503 "Try again shortly" with Try again; network "We couldn't reach the server." with Try again. If only the messages read fails (for example 403 or 503 for the Messages panel's own permission), the page and the timeline still show and "Chasing" shows "Chasing is not available to you" (403) or the mapped message with Try again; the other sections are unaffected. If the detail read fails and the follow-up read succeeded, the facts and Next still show, and "What has happened" shows the error with Try again.
- Success: as the table.

### Idempotency and versioning
Reads only; no key, no token sent. `expected_revision` and `case_revision` from the follow-up read are held for F-111B and are `number` (live types them required), shown nowhere.

### Permission and tenant rules
Read as the signed-in person. 404 reads the same for missing and not-yours. The case id and issue id come only from the loaded work item and follow-up read; there is no input for either. Messages carry the Messages panel's own permissions: a person who may read the issue but not the messages sees the rest of the page.

### Fixtures (mock, `frontend/mock/**`; numeric ids are free, shapes are the contract; Next 4990, mock 4991)
`GET /work/{id}` for a `pmo-issues/v1` item returns `panels:[{key:'issue-followup', url:'/api/v1/work/{id}/issue-followup'}]`, with the other three reads served by case and issue id.
- `5101` default (In Progress): `issue{reference:'ISS-0233', title:'Login fails on older Android phones', severity:'High', status:'In Progress', opened_at, age_days:3, acknowledged_at set}`, `team{label:'Engineering', assignment_id:7, status:'acknowledged', can_record:true, can_resolve:false}`, `blocked_milestone{id, name:'Go-live', url}`, timeline of four rows, messages with one request, `timing{reminder_overdue:false, escalation_overdue:false}`.
- `5102` overdue (Open): `acknowledged_at:null`, `acknowledgement.at:null`, messages with a request and a reminder (`receipt` null on the reminder), `timing{reminder_overdue:true, escalation_overdue:true, escalation_target:'PMO lead', finding:'No response since 09 Nov'}`.
- `5103` no owner (Open): `team{label:'', assignment_id:null, status:'unassigned', can_record:false, finding:'This issue has no owner.'}`, `can_request_update:false`, `response_task:null`, empty messages `items:[]`, `timing:null`, `opened_at:null`, `age_days:null`, `severity:null`.
- `5104` verified: work `state:'verified'`, `issue.status:'Resolved'`, `resolved_at` set, `blocked_milestone:null`, `blocked_planned_milestone{stage:'uat', name:'UAT', policy_id:3}`.
- `5105`: issue detail 200 but messages 403 (Chasing unavailable). `5106`: 404 for any caller. `5107`: follow-up 200, detail 503.

## Lanes
- Frontend lane (owner of all the work): new `frontend/src/features/issue-followup/**` (adapter, mappers, tests); `frontend/mock/**` additions for the four reads and fixtures 5101 to 5107 (new files, e.g. `frontend/mock/issues.mjs`, plus one registration line in `frontend/mock/server.mjs`); `frontend/e2e/issue-followup.spec.ts`; one import line registering the adapter at the place F-85 registers adapters; live types only in `frontend/src/api/live-schema.d.ts` if 1.24.0 is not already generated there.
- Backend lane: none. No backend or contract change.
- Integration owner: lane D coordinator. Shared files and owners: `frontend/src/features/workspace/**` and `frontend/src/features/work-item/**` belong to lane C (not edited; a needed change is a named dependency on lane C); `frontend/src/api/*` shared (live types and error kinds only, reuse F-85's); `frontend/mock/server.mjs` shared (one registration line).
- Paths in `delivery/config.json` `protected_paths` stay unchanged.

## Acceptance criteria
1. Open `/work/5101` on Next 4990 with mock 4991: the page shows ISS-0233, "Login fails on older Android phones", a High tag, an "In Progress" status, Owner "Engineering", Raised with the date, Age "3 days", and Blocks "Go-live" as a link — verify: open the page; `frontend/e2e/issue-followup.spec.ts` asserts each.
2. "What has happened" lists exactly the rows of the detail's `timeline` in the order sent, with the time and words for each kind; no row is built from history or messages — verify: unit test on the mapper with a timeline of the four kinds; page text compared with the mock JSON.
3. `/work/5102` (overdue) shows the overdue banner using `timing.finding`, the Chasing rows (Asked, Reminder with "No receipt yet"), "Reminder due" and "Escalate by" dates and the escalation target; the banner shows only because the flags are true, not from comparing dates — verify: e2e; flip `reminder_overdue` and `escalation_overdue` to false in the fixture and the banner disappears even with past dates (unit test).
4. `/work/5103` (no owner) shows the no-owner banner with `team.finding` and `next_action`, an Owner fact that is not drawn as a name or "Unassigned" placeholder, no Raised or Age value of 0 (null reads "Not recorded"), no severity tag, and no timing rows — verify: e2e and mapper unit test asserting no "0 days".
5. `/work/5104` (verified) shows the verified state tag from the work item, the follow-up `finding` as the lead, and a "planned UAT" Blocks line that is not a link; the page does not say "Closed" while `issue.status` is `Resolved` — verify: e2e.
6. A null `blocked_milestone` and null `blocked_planned_milestone` leave out the Blocks fact with no empty gap — verify: unit test and screenshot.
7. Tola's note, "FIX IN TESTING", "FOLLOW-UP VERIFIED", "recorded by PM" and any "not available" placeholder do not appear on any of the four states — verify: e2e asserts those strings are absent; `grep -rn "FIX IN TESTING" frontend/src/features/issue-followup` returns nothing.
8. No write is sent: no `POST` is made by loading, or by pressing any control, on any state, and no control labelled Post update, Record reply, Set owner, Message owner, Refresh, Restart or Raise an escalation is enabled — verify: e2e records requests and asserts only `GET`; grep `liveApi.POST` in `frontend/src/features/issue-followup` returns nothing.
9. A control whose allowed flag (`can_request_update`, `team.can_record`) is false is not drawn; one whose flag is true is drawn disabled — verify: unit test on both flags with `5101` and `5103`.
10. Messages 403 (`/work/5105`): the header, facts, timeline and Next show; Chasing reads "Chasing is not available to you"; no page-level error — verify: e2e.
11. Detail 503 (`/work/5107`): facts and Next show; "What has happened" shows the mapped message with Try again, and Try again re-reads only the failed read — verify: e2e counting requests.
12. `/work/5106` (404) and a live id the account cannot see show exactly "This record is unavailable." — verify: open both and compare the text; unit test on the 404 body.
13. 401 shows the signed-out state linking to `/sign-in?next=` the current path; 403 `csrf_failed` shows the refresh message and not the no-access state — verify: mock scenarios plus unit tests.
14. A wrong case: with the work item's `case_id` changed in the mock, the adapter requests `/projects/{that case_id}/issues/{issue.id}` and never one taken from another body; a person cannot type a case or issue id anywhere — verify: unit test on the request URLs.
15. Polling: while `current_activity.watching` is true the three issue reads repeat every 5 s together; a failed poll keeps the last good data with the "couldn't refresh" note; a 404 on a poll replaces the page and stops polling; a hidden tab pauses — verify: unit test with fake timers on the adapter reader.
16. The adapter is registered through `registerLineAdapter` under `issue-followup` and `commands()` returns `[]`; a work item with no `issue-followup` panel shows F-85's generic page — verify: unit test.
17. Against live Django (8030, account that can see an issue) the page matches `oa.py`-described fields of the three live reads for the same issue: reference, severity, status, age, owner label, timeline row count, and message row count — verify: `curl` the three URLs with the session and compare with the page.
18. Viewport check at 1440 and 390: each of the four states matches its SCR-30 desktop and mobile board for the parts that remain, and removed parts leave no empty heading or gap — verify: screenshots at both widths reviewed against `design/screens.md` SCR-30 artboards.
19. New unit tests cover the mapper for all four states, null `age_days`, null `opened_at`, null `severity`, unknown timeline `kind`, null `receipt`, null `timing`; `npm run lint`, `typecheck` and `npm test` pass and the live-schema drift test passes — verify: `delivery/checks.sh` result.

## Out of scope
- All writes (F-111B): owner update, owner reply and `team-replies` (D-4), set owner, message owner (prepare, edit, review, release, check, reconcile, recover), refresh, restart.
- Evidence upload, `EvidencePicker` and `fileToEvidence`; no proof fields.
- Raise an escalation (SCR-50) and change request (SCR-31): no link is drawn that starts them.
- Owner choices (`GET /projects/{case}/issues` `owners[]`) and the issues register list.
- Any change to `frontend/src/features/workspace` or `work-item` (lane C); the project tab bar stays as lane C has it.
- Tola's note and any agent step card (DC-3); building a timeline from history, messages or acknowledgement; worked-out overdue or ages.
- Backend, migrations, contract edits.

## Questions
1. Status wording. Boards draw "FIX IN TESTING", "NO RESPONSE · 3 DAYS", "OWNER NEEDED", "FOLLOW-UP VERIFIED" as the status tag; live gives Open, In Progress, Resolved, Closed plus a banner for the rest.
   - Option A (recommended): show the four live words in the tag, and carry "no response", "owner needed" and "verified" as the banner and the work-state tag. Follows D-182 and the readiness scope.
   - Option B: keep the board words by mapping each to a state we derive. Rejected here because it derives status the API does not send.
2. Disabled write controls. Readiness says write controls render "disabled or hidden, according to F-85".
   - Option A (recommended): hide a control whose allowed flag is false; draw it disabled, with no extra explanatory text, when the flag is true, until F-111B enables it.
   - Option B: hide every write control until F-111B (the page is plainly read only; the boards' owner-update form and "Post update"/"Record reply"/"Set an owner"/"Raise an escalation" buttons are absent).
   - Option C: draw all as disabled with "Available soon".
3. No-owner detection. The follow-up read has no explicit "no owner" flag; `issue.owner_id` is a required integer and `team.status` is free text.
   - Option A (recommended): treat `team.assignment_id === null` on an Open or In Progress issue as no owner and show `team.finding` and `next_action`; ask the backend to confirm. Asked in `delivery/connect/backend-questions.md` by the coordinator.
   - Option B: show the banner only when `team.finding` is non-empty, whatever the assignment.
4. Board parts the spec removes or changes (design engineer decides once):
   - Tola's note card and the v7 chasing text are removed (no live source). Recommendation: hide.
   - The default desktop board's "owner update" form, "Record a reply" and "Set an owner" forms and "Raise an escalation" button are not drawn (writes, F-111B or SCR-50). Recommendation: hide until F-111B.
   - "OWNER … (recorded by PM)" becomes the owner's name only. Recommendation: name only.
   - The crumb and project tab bar come from lane C's frame; the boards differ between states (default has no tab bar, the others do). Recommendation: no change here, lane C's frame decides.
   - Added to the page and not on the boards: acknowledgement line, "Not recorded" for missing raised date and age, the planned-milestone Blocks line, receipt words per chasing row, "See full history" link. Recommendation: keep; each exists only to show live data without inventing it.

## Assumptions
- Panel key and URL: `issue-followup` from `STATION_PANELS`; the case id is the work item's `case_id`. Reason: the follow-up body carries no case id.
- "Raised" and "Age" show Not recorded when null, since D-2 says they come from the issue but the types allow null.
- Timeline wording per `kind` is a presentation label; `status` is shown as sent because the contract gives no enumeration.
- Mock fixture ids 5101 to 5107 are free. Reason: no live fixtures exist.
- The milestone link goes to the project's milestones route by id, not the API `url`. Reason: `url` names a backend path.
- Overdue and verified are read from flags and the work state only; no date arithmetic. Reason: AGENTS.md says status comes from the backend.
- The history read is reached through the existing history page link only. Reason: D-3 puts the timeline in the issue detail.
