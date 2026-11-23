<!-- Part of the connection map: see README.md. Cluster A. Written 23 Nov 2026 from live OpenAPI 1.22.0 (main 9bac3109) and the frontend at f8b28059. -->

# Connection map · Cluster A (frame, My work, Work item, Decision, Start work, Assistant, Overview, Exceptions, Verified outputs, Alerts, Sign in, Staff accounts)

Sources read: live OpenAPI 1.22.0 (checked with `oa.py`), `handoffs/nextjs/README.md`, `docs/design/frontend-api.md`, `docs/design/frontend-handoff-review-2026-11-21.md`, `screen-state-crosswalk.csv`, backend code `apps/core/factory_api/{http,work,workspaces,accounts}.py` and `apps/workflows/factory_views.py` (to confirm behaviour the schema does not state), our code under `frontend/src`, and our gap files. Question IDs are `A-n`.

### App frame and session
**Built today:** yes — feature F-01, all routes (the shell wraps every page). Files `src/shell/{AppShell,TopNav,PhoneBar,destinations,FrameStates,DemoBar,HomeRedirect,DestinationPage}.tsx`, `src/api/{client,errors,types}.ts`.
**Live operations:** `GET /api/v1/me`, `GET /api/v1/session`, `POST /api/v1/session`, `POST /api/v1/session/logout`, `GET /api/v1/me/onboarding`, `GET /api/v1/role-dashboard` (for role names).

**Reads**
| What the frame shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Person's name in the top bar and phone menu | `GET /me` → `name` | `GET /me` → `name` (full name, else username) | same |
| Person's role words ("Ada Okafor · Finance Lead"; phone menu line; Setup frame text) | `/me` → `roles[]` (strings) | not in `/me`. Closest: `GET /role-dashboard` → `positions[]` `{role, mode, name, area, focus, workspace}`, one per workspace | missing in live (derive) |
| Which sections are in the menu | `/me` → `destinations[]` = list of 5 enum strings, already filtered for the person; pages test `me.destinations.includes('overview')` | `/me` → `destinations[]` = objects `{key, title, django_url}`, always the same 6 for everyone: `my_work, projects, overview, setup, clients, assistant` (hard-coded in `workspaces.py`, not filtered by role) | reshaped |
| Whether "+ Start work" shows | `/me` → `startable_lines[]` (v7 keys like `invoice`, `income_schedules`) | `/me` → `startable_lines[]` = live line keys (`pmo-weekly-report/v1` …), from the person's intake options | renamed (values differ) |
| Which assistants can be asked | `/me` → `assistant_agents[]` | same field, same three values, only agents with a project the person can use | same |
| Token for writes | `/me` → `csrf_token` | `/me` → `csrf_token`; also `GET /session` → `csrf_token` (works before sign-in) | same |
| Where "My work" lives | not in v7 | `/me` → `work_desk_url`, and `destinations[].django_url`: both name retired Django pages | new in live (ignore, see below) |
| Signed in or not, before sign-in | none (401 on `/me`) | `GET /session` → `{csrf_token, signed_in, next_url}`; `next_url` is the landing page after sign-in | new in live |
| "Is this person admitted yet" | none | `GET /me/onboarding` → `{admitted, can_create_workspace, next_url}` | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Sign in | not built (links to Django `/accounts/login/`, `SIGN_IN_URL` in `shell/sample.ts`) | `POST /session` `{username, password, remember?, next_url?}` + `X-CSRFToken`; 200 returns a **rotated** `csrf_token`; bad details give 422 `sign_in_failed` (no `fields`) | new in live |
| Sign out | none ("no account menu or sign-out in this release") | `POST /session/logout` body `{}`; 200 returns a fresh token and `signed_in:false` | new in live |

**Rules the client must follow (live)**
- *Token:* today it is read once from `/me` and kept in memory (`setCsrfToken`); a write before `/me` throws `csrf_unavailable`. Live tokens rotate on sign-in, sign-out and password change (`POST /me/account/password` returns a new `csrf_token`). After each, call `setCsrfToken` with the returned value and reload `/me`.
- *Cookies and origin:* Django session cookie, same-origin through the Next proxy. A separate frontend host must be listed exactly in the backend's `PSL_FRONTEND_ORIGINS` or every write gets 403.
- *401:* body `{code:'unauthenticated', message:'Sign in to continue.'}` on every route except the three session routes. Today this shows `SignedOutState` with a link to the retired Django login; it must route to the new sign-in screen (SCR-17) with `?next=`.
- *403:* two different bodies, both status 403: `forbidden` ("You do not have permission for this action.") and `csrf_failed` ("Refresh your session and try again."). `errors.ts` maps both to kind `forbidden`, so a stale token on `/me` would show "Your account can't use PSL Factory". Branch on `code`: for `csrf_failed` call `GET /session`, store the new token, and tell the person to press the action again (nothing ran).
- *404:* one body for "missing" and "not yours": `{code:'not_found', message:'This record is unavailable.'}` (good: it hides existence). Same wording for SCR-02 permission state.
- *Other statuses:* 409 (`stale_version`, `stale_evidence`, `conflict`, `idempotency_conflict`), 422 (`invalid_input` with `fields[{name,message}]`, `invalid_filter`, `setup_required` = a policy, owner or configuration value is missing and `message` says which, `action_unavailable`), 429 (rate limit), 413/415/400 (`request_too_large`, `unsupported_media_type`, `invalid_json`), 503 `read_limited` ("needs a closer review"). `errors.ts` maps only 401/403/404/409/422; 400/413/415/429/503 fall to kind `server`. 429 and 503 need their own wording ("try again shortly") and no auto-retry for writes.
- *Error body shape:* always `{code, message, fields?}`, header `Cache-Control: no-store` — same as v7 plus `fields` on every 422 that names inputs (this closes our BQ-17). `call()` still drops `fields`; keep the `postStep`-style reader and make it the default.
- *Idempotency code:* we test for `idempotency_key_reused` (409); live says `idempotency_conflict` (409). Update `useStartWork.ts` line ~430.
- *Types:* `src/api/schema.d.ts` is v7. Add `live-schema.d.ts` (generate from `contracts/psl-factory.openapi.json`) and switch `createClient<paths>` per screen as each is rewired; `types.ts` (`Me`, `Destination`, `WorkItem`) must move to live types.

**origin/main embed (FactoryDesk).** `git diff HEAD...origin/main` adds `src/shell/FactoryDesk.tsx` and changes `AppShell.tsx` and `next.config.ts`. In `AppShell` any `/me` that contains `work_desk_url` (the live reply always does) sets `native`, empties the menu and returns `<FactoryDesk>` instead of our shell. `FactoryDesk` mounts the retired Django web component `<psl-work-client>` (script `/factory-assets/work-client.js` → Django `/static/factory-work-client.js`) for `/`, `/my-work` and `/work/<id>[/history|/decide]`, and draws plain links to Django forms (`/factory-forms/...`) for everything else. It replaces all our screens with the retired UI.
- *Remove:* `FactoryDesk.tsx`; in `AppShell.tsx` the `import`, the `native` constant, the `!native` guard on `destinations`, and the early `if (native) return …`. In `next.config.ts`: `NEXT_PUBLIC_FACTORY_ORIGIN` env, the `/factory-assets/work-client.js`, `/accounts/:path*`, `/factory-forms/:path*`, `/static/:path*` rewrites, and the catch-all `fallback` (it forwards any unmatched path to Django, which now answers 404 `page_retired`). Do not point `SIGN_IN_URL` or links at `django_url` values.
- *Keep:* the `/api/v1/:path*` rewrite, `allowedDevOrigins`, and the mock-only `/__mock/reset` rewrite.
- *Add instead:* rewrites for the six authenticated file downloads the API still returns (`/cases/{case}/files/{upload}/`, `/projects/{case}/templates/{id}/file/`, `/cases/{case}/rfp/intake/{id}/attachment/`, `/work/{id}/invoice-proof/{proof}/`, `/cases/{case}/finance/invoices/{issue}/payments/{receipt}/proof/{kind}/`, `/cases/{case}/finance/reminders/{issue}/drafts/{draft}/{kind}/`; backend `config/urls.py`) and our own pages for `/staff/join/` and `/accounts/recovery/link/` (token is in the URL fragment; see SCR-17).

**Other frame files.** `AppShell` fetches `/me` once per page load and shows loading / signed-out / forbidden / error states from the error `kind`; keep it, change the destination test to look up `d.key`. `destinations.ts`: fixed display order and labels for 5 keys; add `clients` as a known key (we hang Clients under Projects) and read `title` from `/me` only as a fallback. `PhoneBar` and `TopNav` use `me.roles.join(', ')` and `me.startable_lines.length`; roles need a source (question A-1). `DemoBar` (role switch via `psl_mock_persona` cookie, speed, reset) only works against the mock (`NEXT_PUBLIC_MOCK_DEMO=1`, never in production); keep for design review, it has no live meaning. `FrameStates`: copy is fine; `LoadErrorState` prints the error `code` as the reference, which still works.

**Design parts the live API cannot fill:** the role words in the top bar and phone menu; a menu that already hides sections the person's role cannot open (live lists everything for everyone; unknown whether Overview and Setup answer 403 per role).
**Live data the design does not show yet (worth knowing):** `signed_in` / `next_url` for a first-run landing; `can_create_workspace` for new people; `positions[].mode` (lead, member, standalone, administrator) and team names.
**Effort to connect:** M — three small mismatches in one file set (destination objects, roles, 403 codes) plus the removal of the embed; the sign-in screen itself is SCR-17.
**Questions for the backend:**
1. A-1 `GET /me`: where do we read the person's role words (the v7 `roles[]`) — only from `GET /role-dashboard` `positions[]`, or will `/me` carry a `roles` list?
2. A-2 `GET /me` `destinations[]`: is it intentionally the same six entries for every account, and do `GET /overview`, `/setup/...` and `/clients` answer 403 per role so the frame can hide those sections?
3. A-3 `POST` writes: is a 403 `csrf_failed` always safe to retry once after `GET /session` (nothing executed)?
4. A-4 `GET /me`: will `work_desk_url` and `destinations[].django_url` be removed or left pointing at retired pages? We will not use them.
5. A-5 Status 429 and 503 `read_limited`: do they carry a retry-after or a `code` we can show?

---

### SCR-01 · My work (work queue)
**Built today:** yes — F-02 (and F-36 assign panel), route `/my-work`, files `src/features/my-work/{MyWork,WorkRows,FilterPanel,CaughtUp,model}.ts*`.
**Live operations:** `GET /work`, `GET /lines` (lines list for the filter), `GET /role-dashboard`, `GET /role-work/{assignment_id}`, `POST /role-work/{assignment_id}/actions`, `GET /work/source-queues`, `GET /received-bids/assignments` (for Unassigned).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The list tabs | `GET /work?queue=` `needs_me, waiting_on_others, done, unassigned` | `GET /work?queue=` `needs_me, waiting, mine, active, decisions, exceptions, unassigned, verified` (default `needs_me`) | renamed (`waiting_on_others`→`waiting`, `done`→`verified`); `mine` ("Started by me"), `active`, `decisions`, `exceptions` are new |
| Number on each tab and "34 records you can see" | `counts{needs_me, waiting_on_others, done, unassigned}` | none | missing in live |
| Row: title, line name | `items[].title`, `.line` (display title), `.line_key` | `items[].title`; `.line` is the **key** (`planning/v1`); titles come from top-level `lines[{key,title}]` (only lines the person has work on) | reshaped |
| Row reference ("INV-0412") | `items[].reference` | none (only integer `id`, and `case_id`) | missing in live |
| Row tag: Decide / Do / Fix / Started | `items[].kind` | none | missing in live |
| "Where on its line" station bar | `items[].station{index,count,name}` | none | missing in live |
| State tag | `items[].state` (11 values) | `items[].state` (same 11 values) plus `status_label` (the backend's own words) | same (+ new `status_label`) |
| "Waiting on" words and agent avatar | `items[].waiting_on`, `.agent` | `items[].owner` (string or null; "Unassigned" on that tab), no agent | reshaped / missing |
| Age ("2h") | `items[].age_seconds` | `items[].updated_at` (last change, not time open) | reshaped |
| Sample flag, link | `items[].sample`, route `/work/{id}` | `items[].sample`, `id` (int), `api_url`, `django_url` (ignore) | same |
| "Updated 10:42" | `as_of` | `as_of` | same |
| Search | `q` | `q` (matches reference, project title, key; max 120 chars) | same |
| Filters: line, project | `line` (key), `project` (case id) | `line` (enum of the 26 definitions), `project` (UUID) | same (values renamed) |
| Filters: state, waiting-on | `state`, `waiting_on` | none | missing in live |
| Paging and "rows per page" 10/20/50 | `cursor`, `limit`; `next_cursor` | `page`; `next_page` (int or null). Fixed 8 rows per page, no `limit` | reshaped |
| Honest coverage | none | `limited`, `evaluated`, `deferred[{id,url}]` (rows too heavy to read this time), `payroll_questions[]` (private staff-cost questions for the person) | new in live |
| Role heading, team invitations, my decisions, "lead sees team" | none (SCR-01-lead = Unassigned tab) | `GET /role-dashboard`: `positions[]`, `actions[]`, `decisions[]`, `team_decisions[]`, `workspace_decisions[]`, `approval_desks[]`, `has_teams`, `page`, `has_next` | new in live |
| Agent suggestions "While you're free" | `suggestions[]` (our proposal, BQ-21) | none | missing in live |

Note on paging (from `queue_context`): the backend takes 8 candidate records per page, then drops those that do not belong in the chosen tab. A page can come back with fewer than 8 rows, or none, while `next_page` is still set. "Show more" must keep asking until it has rows or `next_page` is null; "N of M items" cannot be shown.

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Assign the accountable PM from Unassigned (F-36) | `POST /work/{id}/assignment` `{expected_revision, person_id, note?}` 200 | not at that path. Received bids: `GET /received-bids/assignments`, `GET/POST /received-bids/{case_id}/assignment` (cluster owner of RFP). Issues: `POST /projects/{case_id}/issues/{issue_id}/assignment` | moved |
| Start or complete my assigned action | not built | `POST /role-work/{assignment_id}/actions` `{expected, case_expected, operation: start|complete, reason, action_revision}` 200 `{state, action_revision}` | new in live |

**Design parts the live API cannot fill:** per-tab counts and the "records you can see" total; the station mini-bar; the Decide/Do/Fix tag; the agent avatar; state and waiting-on filters; reference numbers; "rows per page"; the idle "While you're free" suggestions.
**Live data the design does not show yet (worth knowing):** `limited`/`deferred` coverage notice; `payroll_questions` (staff-cost questions); `exceptions` and `decisions` tabs; my team's decisions and approval desks from `/role-dashboard`.
**Effort to connect:** L — the row model (station, kind, counts, filters, paging) is rebuilt around fewer fields; role dashboard is a new section.
**Questions for the backend:**
1. A-6 `GET /work` item: can rows carry `reference`, `kind` (decide/do/fix/started), `station{index,count,name}` and `agent`, as in v7?
2. A-7 `GET /work`: can the response include per-queue counts, and a `state` filter?
3. A-8 `GET /work`: can the page size be settable (`limit`), and can empty pages be skipped so `next_page` never leads to an empty page?
4. A-9 `GET /work` `line`: do you want us to read titles from `lines[]` only, or can each item carry its `line_title`?
5. A-10 `GET /work` item: is `updated_at` the right stand-in for age, or can you add `started_at`?

---

### SCR-02 · Work item
**Built today:** yes — F-03, F-09, F-14, F-17 (+ workspace frame F-23, F-30…F-45 per line), routes `/work/[id]`, `/work/[id]/history`, `/work/[id]/respond`, files `src/features/work-item/*`, `src/features/workspace/*`, `src/features/response/*`.
**Live operations:** `GET /work/{work_id}`, `GET /work/{work_id}/history`, `POST /work/{work_id}/actions`, `POST /work/{work_id}/background`, `POST /work/{work_id}/control`, `POST /work/{work_id}/coordination/{check_id}/retry`, `POST /work/{work_id}/corrections`, `GET/POST /work/{work_id}/access-request`, `GET/POST /work/{work_id}/information/{task_id}`, `GET/POST /work/{work_id}/invoice-milestone-proof`, `POST …/invoice-milestone-proof/{task_id}/claim`, `GET/POST /work/{work_id}/invoice-draft-stop`, `POST /work/{work_id}/invoice-preparation`, `GET /work/{work_id}/department-handoff`, `GET /projects/{case_id}/billing-invoices/{invoice_id}`, `GET/POST /projects/{case_id}/delivery/{dossier_id}/client-testing/pack…`.

**Reads — the work item itself**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Title, reference, line, sample tag | `GET /work/{id}` → `title, reference, line, sample` | `title, sample`; `line` is the line key; no `reference` | reshaped / missing |
| State tag and next step | `state` (11), `next_step` | `state` (same 11), `status_label`, `next_step`, `blocker` (text, empty when none) | same (+ new) |
| Version to send back on writes | `revision`, `case_revision` | `revision`, `case_revision` (both can be null on a handoff-only or recipient-only view) | same |
| Stations track (done / person / agent / waiting) with who holds each | `stations[]` `{name,status,held_by,started_at,finished_at}` | none | missing in live |
| Six facts (drafted, reviewed, approved, sent, receipt, verified) | `facts[]` | none; nearest: the line's own readback (`panels[]`), `output_url`, invoice record `issued_at`/`delivered_at` | missing in live |
| Agent card and steps | `agent{status,steps[]}` | `progress{status, updated_at}` (background job), `current_activity{label, watching}` (only some lines) | reshaped |
| "Poll while agent works" | poll every 5 s while `agent.status==='working'` | poll while `current_activity.watching` is true or `state==='processing'` (docs say so) | reshaped |
| Who started it, when, amount | `started_by, started_at, amount` | `owner` (who holds it), `updated_at`; amount only inside line readbacks | missing in live |
| Decisions waiting here | `tasks[]` (full decision card: version, amount, basis, recipient, changes, prepared_by, approval chain, `cannot_act_reason`, `asked[]`, `response{…}`) | `tasks[]` `{id, kind, role, status, revision, claimed_by_you, can_claim, can_decide, verdicts[], url}` — only invoice and accounting reviews; card content comes from `GET /tasks/{id}` (see SCR-03) | reshaped |
| Buttons: resume, cancel, confirm what happened | `allowed_actions[]` `resume|cancel|reconcile` | split in two: `actions[]` `background|reconcile|release_invoice`; `available_control[]` `resume|cancel|adopt_profile` (+ `profile_adoption{configuration_id,version}`) | reshaped |
| "Confirm what happened" panel (what was sent, when, checks made, outcomes) | `reconcile{…}` | none; live reconcile is a lookup, see Writes | missing in live |
| Where the work is read in detail (the line's own content) | `workspace{sections[], steps[], status, byline, version, context, agent_note, next}` | `panels[]` `{key,url}` — each a link to that line's own readback, e.g. `weekly-report`, `forecast`, `bid-submission`, `release-register`, `stability`, `go-live-signoff`, `invoice` (keys per line are fixed in the backend `STATION_PANELS`) | reshaped (see frame note below) |
| Open the finished output | none (verified item) | `output_url` (set only when verified and not changed since) | new in live |
| Invoice information requests | tasks of kind information | `information[]` `{task_id,url}` → `GET /work/{id}/information/{task_id}` `{task_revision, case_revision, requested_kinds[], can_claim, can_provide, can_recheck, can_release, private_file_url}` | reshaped |
| Pages the backend still has as forms | none | `screens[]` `{key: decision|response|recovery, django_url}`: retired Django pages; ignore | new in live (ignore) |
| Payroll recipient view | none | `aggregate{report_id, values, currency, period, receipt_id}` | new in live |
| Permission state ("ask for access") | 404 hides | still 404 (`work_detail:404`); `POST /work/{id}/access-request` gives the same `{requested}` answer whether or not the record exists | new in live |
| History list | `GET /work/{id}/history` `items[{at, actor_kind, actor, event, version, detail, restricted}]`, `kind` all/decisions/agent_work/evidence, cursor, limit | `GET /work/{id}/history?kind=worker|decision|evidence` → `items[{at, station, status, task_id?, actor?, reason?, evidence_id?}]`; up to 30 events, no cursor, no limit | reshaped |
| History counts per filter | `presentation.history_counts` (our proposal) | none | missing in live |

**Frame note — shared line workspace (`src/features/workspace`).** Today the frame is generic: it reads only `item.workspace` (header: `title, subtitle, status{label,tone}, byline, version, context{project, crumbs}`; `agent_note{agent, lines, warn_lines}`; `sections[]` of nine kinds with `columns, items, total, filters, next_cursor, coverage, as_of, restricted`; `steps[]` with `fields, confirm, consequence, sends, claim_required, task_id, disabled_reason`; `next[]`; `revision`), plus `assign`, `rfp`, `reconcile`, `stations`, and our proposed `links[]`, `values`, `starts_line`, `items_default`, `submit_label`, `team_key`, `attachment`. All of that is composed by the backend in v7; live composes none of it. What exists instead:
- *Header:* title and tag can come from `title`, `state`, `status_label`; project name and crumbs need `GET /projects/{case_id}` (`case_id` is on the item); byline, version label and the status tone have no source (tone could be mapped from `state`).
- *Sections:* each line's own readback (`panels[].url`) has its own shape (for example `GET /work/{id}/weekly-report`, `/leadership-report`, `/forecast`, `/bid-submission`, `/stability`, `/engagement`, `/accounting`). No shared `kind` (facts/table/checklist/…); many carry `as_of` and `coverage` fields. Two ways to connect: (a) one small adapter per line that turns its readback into our section objects and keeps the generic renderer, or (b) per-line views. The generic pieces worth keeping are the section kinds, the unknown-is-not-zero rendering, restricted rows, "As of" lines and the show-more control; the generic step engine is not reusable as is.
- *Steps:* v7 has one write, `POST /work/{id}/steps` `{expected_revision, step, item_ids, inputs, case_revision, evidence_ids, note, idempotency_key}` → 200 `{work_id,state,revision,outcome: done|queued|effect_uncertain}`. Live has no such operation; each action is its own typed command on the line's resource, with its own revision tokens (`expected_revision`, `case_revision`, `action_revision`, `task_revision`, `revision`) and `operation`/`idempotency_key` UUIDs, and answers 200, 201 or 202. `useWorkspaceStep` locking (press lock, uncertain lock, fresh key per attempt, 409 → reload) can stay; the body building and result mapping move to a per-line adapter. The `fields[]` from a 422 now name the real inputs.
- *Assign accountable PM:* v7 `workspace.assign` + `POST /work/{id}/assignment`; live has it only for received bids and issues (see SCR-01).
- *Response drawer (`respond`):* v7 `tasks[].response` + `POST /tasks/{id}/claim` + `POST /tasks/{id}/response` + `POST /cases/{id}/evidence` (base64). Live equivalents are per line (client-testing pack, commercial response, go-live replies, support replies) and upload is multipart `POST /cases/{case_id}/files` → `{upload_id,name,size,sha256,download_url}` or the line's own `…/files` route. Covered by the delivery and bid clusters.
- *Reconcile:* see Writes.

**Reads — invoice states (the line this screen's boards use)**
| What the screen shows | Today | Live | Fit |
|---|---|---|---|
| Issued and delivered invoice, amounts, paid, owed (verified, issue, awaiting-reconciliation) | `facts`, `presentation.preview` | `GET /projects/{case_id}/billing-invoices/{invoice_id}` → `reference, version, issued_at, delivered_at, currency, amount, paid, owed, issue_id, delivery_id, payments_url, corrections_url`; id arrives as a panel `invoice` | new in live |
| Milestone proof asked / supplied | `tasks[].response`, evidence upload | `GET /work/{id}/invoice-milestone-proof` → `{revision, proof, request}` | reshaped |
| Draft that can be stopped, and any invoice already issued | `allowed_actions: cancel` | `GET /work/{id}/invoice-draft-stop` → `{revision, case_revision, can_stop, existing_issue, recorded_stop}` | reshaped |
| Returned invoice, corrected version | v7 tasks/steps | `POST /work/{id}/invoice-preparation`; then new review task | reshaped |
| Client testing pack (waiting state) | none | `GET/POST /projects/{case_id}/delivery/{dossier_id}/client-testing/pack` and `…/pack/{pack_id}/{side}` (download) | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Confirm what happened after an uncertain send | `POST /work/{id}/actions` `{expected_revision, action:'reconcile', outcome: delivered|not_delivered|unknown, evidence_id?, case_revision?}` 200 | `POST /work/{id}/actions` `{expected_revision, action:'reconcile'}` → **202** `{work_id,state,revision}`. The backend checks the original effect itself; the person cannot state an outcome or attach proof | reshaped (the person's choice of outcome is gone) |
| Release an invoice | not a v7 action | same op with `action:'release_invoice'` → 202; offered only when `actions[]` contains it | new in live |
| Resume / cancel | `POST /work/{id}/actions` `action: resume|cancel` | `POST /work/{id}/control` `{expected_revision, action: resume|cancel}` 200; adopt a reviewed setup profile: `{expected_revision, action:'adopt_profile', configuration_id, reason}` | moved |
| Pause or continue background work | none | `POST /work/{id}/background` `{expected_revision, enabled}` → 202 | new in live |
| Take a line step | `POST /work/{id}/steps` | per-line commands (other clusters) | missing in live (generic op) |
| Supply requested invoice information | `tasks[].response` + `POST /tasks/{id}/response` | `POST /work/{id}/information/{task_id}` one of `{action:'claim', task_revision}`, `{action, task_revision, reason}` (recheck/release), or `{action, task_revision, case_revision, kind, content, source}` → 200 `{task_id, task_revision, case_revision, evidence_id}` | reshaped |
| Attach milestone proof (original file) | `POST /cases/{id}/evidence` base64 | upload to the case first (`POST /cases/{case_id}/files`), then `POST /work/{id}/invoice-milestone-proof` `{task_id, task_revision, case_revision, upload_id, operation (uuid), previous_id?, note?}` → **201** `{proof{…download_url}, task_revision, case_revision}`; claim first: `POST …/{task_id}/claim` | reshaped |
| Stop an unsent draft | `action: cancel` | `POST /work/{id}/invoice-draft-stop` `{expected_revision, case_revision, reason, existing_invoice_id?}` 200 | reshaped |
| Retry a coordinator check | none | `POST /work/{id}/coordination/{check_id}/retry` `{revision, reason}` → 202 `{check_id}` | new in live |
| Correct the source the work was started from | none | `POST /work/{id}/corrections` `{expected_revision, case_revision, line, reason, source{…per line}}` 200 | new in live |
| Ask for access to a hidden record | none | `POST /work/{id}/access-request` `{}` 200 `{requested}` | new in live |

**Design parts the live API cannot fill:** the stations track with who holds each station; the six facts strip; the agent card with its numbered steps and "Tola is working"; started-by and started-at; the state panel text (`presentation.*`, our proposal BQ-22); history rows written as sentences with "restricted" marks and the per-filter counts; the generic "Take a step" form with confirm and consequence words; "choose what happened" with proof for an uncertain send.
**Live data the design does not show yet (worth knowing):** `blocker` (why it is stuck), `status_label`, `output_url` for verified work, the background pause/continue, coordinator retries, corrections, access requests, `current_activity.label`.
**Effort to connect:** L — the generic work item and workspace are rebuilt around `panels[]` and per-line commands; the frame (header, tags, history, invoice states) is M by itself.
**Questions for the backend:**
1. A-11 `GET /work/{id}`: is a stations list (name, status, who holds it) coming, or should the track be dropped / derived from `state` only?
2. A-12 `GET /work/{id}`: can it carry the six facts (drafted, reviewed, approved, sent, receipt, verified) as v7 did, or is each fact read from the line's panel?
3. A-13 `POST /work/{id}/actions` `reconcile`: can a person with recovery authority record "delivered / not delivered / unknown" with proof when the lookup cannot decide, as the design shows?
4. A-14 `GET /work/{id}` `reference`, `started_by`, `started_at`, `amount`: are these available anywhere in live, or are the id and `owner` the only identity?
5. A-15 `GET /work/{id}/history`: can it page (cursor) and filter beyond 30 events, and return an actor kind and a readable event sentence?
6. A-16 `panels[]`: is there a list of every panel `key` per line with its response schema, so we can write one adapter per line?
7. A-17 `current_activity`: which lines return it, and is `watching:true` the only signal to keep polling?

---

### SCR-03 · Decision
**Built today:** yes — F-04, F-16 (payment-exception, CEO costing, CTO emergency variants are not built), route `/work/[id]/decide?task=`, files `src/features/decide/*`, plus in-place decisions in `workspace/InlineDecide.tsx`.
**Live operations:** `GET /tasks/{task_id}`, `POST /tasks/{task_id}/claim`, `POST /tasks/{task_id}/decision`, `POST /tasks/{task_id}/comments`, `POST /work/{work_id}/reviews`, `GET /role-work/{assignment_id}` + `POST …/decision`, `GET/POST /work/{work_id}/emergency`, `GET/POST /projects/{case_id}/payment-controls` (+ `/assessments/{id}`, `/exceptions/{id}`), `GET/POST /projects/{case_id}/costing/proposals/{proposal_id}`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The decision card: version label, amount, basis, recipient, what changed, who prepared it | `GET /work/{id}` → `tasks[].decision{version, amount, basis, recipient, changes, prepared_by}` | `GET /tasks/{task_id}` → `invoice_packet{invoice_id, version, sha256, amount (string), currency, recipient, preparation_id, sources[]}`; `recipient_change{earlier, current}` | reshaped (no basis, no change list, no preparer name) |
| Approval chain ("your step 2 of 3") | `decision.chain{steps, your_step, step_count}` | none | missing in live |
| Can I act, and why not | `tasks[].you_can_act`, `cannot_act_reason` (not your role, prepared by you, already decided, not your turn) | `task{can_claim, can_decide, claimed_by_you, verdicts[]}`; no reason | reshaped (reason missing) |
| Role required | `required_role` | `task.role` | renamed |
| Evidence the reviewer saw | `evidence_id` optional | `review_evidence[{id, version, source, sha256}]` — **required** to decide | new in live |
| Which tasks I can decide | `GET /work?queue=needs_me` | `GET /work?queue=decisions`; `GET /role-dashboard` `decisions[]`, `team_decisions[]`, `workspace_decisions[{work_id,title,workspace,state,url,api_url}]`, `approval_desks[]` | reshaped |
| Decided, with reason and evidence | `GET /work/{id}/history` | `GET /work/{id}/history?kind=decision` → `{task_id, actor, reason, evidence_id, status}` | reshaped |
| Payment exception variant | not built | `GET /projects/{case_id}/payment-controls/exceptions/{request_id}` → `{id, revision, assessment_id, reason, requested_by_me, evidence_id, valid_from, valid_until, decisions[]}` | new in live |
| CEO costing variant | not built | `GET /projects/{case_id}/costing/proposals/{proposal_id}` → `{id, revision, base_rule_id, reason, parameters[], verdicts[confirm|return|withdraw], recorded_verdict, independent_examples[], proposed_examples[], comparison[], hold}` | new in live |
| CTO emergency variant | not built | `GET /work/{id}/emergency` → `{expected_revision, case_revision, profile_id, stage, finding, actions[], options[], decisions[], recorded_authorizations[] …}` | new in live |
| Other native decision packets | none | `GET /role-work/{assignment_id}` → `{revision, case_revision, action_revision, review{title, version, role, sections[], verdicts[], token}, operations[]}` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Claim the review | `POST /tasks/{id}/claim` `{expected_revision}` 200 `{task_id:string, revision, claimed_by}` (page claims automatically on open) | same path and body; id is an integer; 200 `{task_id, revision, claimed_by}` | same |
| Approve / return / reject | `POST /tasks/{id}/decision` `{expected_revision, verdict (+revoke), note?, evidence_id?}` 200 `{task_id, verdict, decided_by, decided_at, work_state}` | `{expected_revision, verdict: approve|return|reject, evidence_id (required, int), note (required key)}` 200 `{task_id, review_id, verdict, work_state}` | reshaped (evidence and note now required; no `revoke`; no `decided_by/at`) |
| Comment without a verdict (not-yours board) | none | `POST /tasks/{id}/comments` `{revision, body}` 200 `{comment_id}` | new in live |
| Other independent reviews (document, response, commercial, ledger…) | none | `POST /work/{id}/reviews` one of seven bodies by `kind` (verdict, `expected_revision`, `case_revision`, `version_id` or `target_id`, `evidence_id`, `note`, sometimes `operation_key`) 200 `{work_id, state, revision, review_id}` | new in live |
| Role-desk decision | none | `POST /role-work/{id}/decision` `{expected, case_expected, verdict, note, token}` 200 `{review_id, verdict}` | new in live |
| Payment exception decision | none | `POST /projects/{case_id}/payment-controls` `{action, revision, request_id, verdict: approve|reject|return|revoke|withdraw, reason, evidence_id}` | new in live |
| Costing verdict | none | `POST /projects/{case_id}/costing/proposals/{id}` `{revision, verdict: confirm|return|withdraw, reason, evidence_id}` 201 `{id, revision}` | new in live |
| Emergency decision | none | `POST /work/{id}/emergency` `{action, expected_revision, case_revision, profile_id, evidence_id, note, role, authority_role, verdict}` 201 | new in live |

**Design parts the live API cannot fill:** the approval chain strip; the "why you cannot decide" sentence; "what changed since last version" list; basis line; prepared-by name; "decided by X at time" on the done page; the pager "decision 2 of 5" (`decide_presentation`, BQ-23).
**Live data the design does not show yet (worth knowing):** the document fingerprints (`sha256`) and the exact evidence the reviewer must cite; recipient change warning; review comments; payment-exception, costing and emergency packets with their own holds (`hold`, `setup_required` messages say which policy value is held for PSL).
**Effort to connect:** M for the invoice and accounting review (same flow, evidence picker added); L for the three variants, which are separate packets per owner.
**Questions for the backend:**
1. A-18 `POST /tasks/{id}/decision`: which `review_evidence[]` item should we pre-select for the person, and may the person choose none (the key is required)?
2. A-19 `GET /tasks/{id}`: can it return the approval chain and a `cannot_act_reason` (prepared by you, already decided, not your turn)?
3. A-20 `POST /tasks/{id}/decision`: no `revoke` verdict here, but `payment-controls` and `reviews` have it; is revoke only on those?
4. A-21 `GET /tasks/{id}`: can it return `basis`, a change list against the previous version, and the preparer's name?
5. A-22 Task ids are integers on live; confirm `GET /work/{id}` `tasks[].url` is the page to open for the right packet (task vs role-work vs payment-controls).

---

### SCR-04 · Start work
**Built today:** yes — F-05, F-47, F-51, drawer from "+ Start work"; files `src/features/start-work/*`. (Line-specific forms: other clusters.)
**Live operations:** `GET /lines`, `GET /lines/projects`, `GET /processes`, `GET /projects/{case_id}/intake-sources`, `POST /work`, `POST /projects/{case_id}/minutes/intake`, `GET /received-bids/organisations`, `POST /received-bids`, per-line intake reads (`…/weekly-report-intake`, `…/validation-intake`, `…/payroll/requests/{id}/start-choices`, etc.), `POST /cases/{case_id}/files`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| List of work types the person can start | `GET /lines` → `items[{key,title,group,subtitle,case_scope,case_id,case_revision,start_via,next{…}}]` | `GET /lines` → `items[{key,title,description,can_submit_via_api,django_url,project_options_url,submit_url}]` + `as_of` (25 lines; received bids are separate) | reshaped (no `group`, no `next` station summary) |
| Form fields for the chosen type (labels, required, help, types) | `items[].intake[{name,label,type,required,help,options,depends_on,evidence_kind,multiple}]` — the drawer draws the form from this | none; field sets are fixed per line in the request schema of `POST /work` and in the line's own intake read | missing in live |
| Pick the project (and its current revision) | `case_scope` + options `value, case_id, case_revision` | `GET /lines/projects?line=&q=&page=` → `items[{case_id, title, case_revision, sample, source_options_url, workflow_intake_url}]`; `next_page` | moved |
| Pick a record (milestone, issue, meeting, template…) | `GET /lines/{line}/fields/{field}/options?parent&q&cursor&limit` → `{value,label,hint,disabled_reason,case_id,case_revision,sample}` | `GET /projects/{case_id}/intake-sources?line=&field=&parent_id=&before=` → `{case_revision, fields[], field, items[{id,label}], next_before}` (typed; `parent_id` for dependent choices, `before` for paging) | reshaped |
| "Find a process" list (108 PMO and Finance processes) | none | `GET /processes` → `items[{process, title, department, line, project_handoff, intake_available, intake_url, guide{action, screen, source_url, tracking_url}}]` | new in live |
| Who can be chosen as organisation for a received bid | `rfp_intake` line fields | `GET /received-bids/organisations` → `items[{id, organisation}]` | new in live |

Line keys differ: v7 `invoice, weekly_report, minutes, issue_followup, change_request, emergency_change, escalation, leadership_report, income_schedules, ledger_sources, fixed_assets, cash_forecast, rfp_intake, hr_staff_list` → live `pmo-weekly-report/v1, pmo-minutes/v1, pmo-issues/v1, pmo-change/v1, pmo-emergency/v1, pmo-escalation/v1, pmo-leadership-report/v1, finance-schedules/v1, finance-ledger/v1, finance-ppe/v1, finance-forecast/v1, finance-payroll/v1`, plus `engagement/v1, pmo-finance/v1, finance-bu/v1, finance-accounts/v1, planning/v1, commercial/v1, rfp-response/v1` and the delivery lines. There is no `invoice` line in the 25; invoice work is created by the Finance flow and the `…/invoice-preparation` command. `rfp_intake` is `POST /received-bids`, not a line.

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Start the work | `POST /work` `{line, case_id, case_revision, intake{name:value}, idempotency_key}` → **201** `{work_id:string, state}` (any other success counts as uncertain) | `POST /work` `{line, case_id (uuid), case_revision, idempotency_key, background?, reference?, intake{…}}` where `intake` has a different fixed shape per line (e.g. issues `{issue_id}`, planning `{packet_id}`, delivery `{dossier_id, inputs}`, weekly `{inputs{…}}`, minutes `{data{…}}`) → **200** `{work_id:int, state}` | reshaped (200 not 201; per-line body) |
| Start minutes from a notes file | v7: `proof` evidence field | `POST /projects/{case_id}/minutes/intake` multipart `{case_revision, idempotency_key, reference, template_id, audience, notes_file, meeting_version_id?, background?}` → 200 `{work_id, state, revision, background: queued|existing|held|not_requested}` | moved |
| Log a received bid | `rfp_intake` line | `POST /received-bids` multipart `{authority, start_key (uuid), reference, received_at, deadline_status, deadline_at?, prospect_name?, submission_method?, submission_target?, context_attested?, document}` → 200 `{receipt_id, case_id, django_url}` | moved |
| Upload proof | `POST /cases/{id}/evidence` JSON base64 `{kind, filename, content_base64, case_revision}` → `{evidence_id, sha256, case_revision}` | `POST /cases/{case_id}/files` multipart `{file}` → `{upload_id, name, size, sha256, download_url}`; then the line's start body cites `upload_id`/`evidence_id` | reshaped (no revision returned) |

**Design parts the live API cannot fill:** a form drawn from data (field labels, help text, required marks, "Next: 6 stations, Tola, decided by…" summary, group headings such as "Client delivery"); per-line default and "Who gets the minutes" choice labels; the 422 `fields[]` names match the typed body keys, not our field names.
**Live data the design does not show yet (worth knowing):** `can_submit_via_api` (some lines still say "use the form"), `workflow_intake_url` per project, `background` choice (start with the background worker on or off, and the `queued/held` answer), the Find-a-process list with its department hand-off links.
**Effort to connect:** L — the generic drawer becomes a per-line form set (25 lines) built on typed bodies; chooser, project picker and upload are M.
**Questions for the backend:**
1. A-23 `GET /lines`: can each item return the intake field list (name, label, type, required, help, options source) as v7 did, or do we hard-code 25 forms?
2. A-24 `POST /work`: is 200 (not 201) with `work_id` the intended success for a first start, and what status does a replay of the same `idempotency_key` return?
3. A-25 `GET /lines` `can_submit_via_api:false`: which lines are false today and what should the screen show for them?
4. A-26 Invoice: which operation starts the Finance invoice line, given `invoice` is not among the 25 `POST /work` lines?
5. A-27 `POST /cases/{case_id}/files`: is the size and type limit published, and does the upload give back a `case_revision` we must send on start?

---

### SCR-05 · Assistant
**Built today:** yes — F-24, F-48 (speech is on-device typing only), routes `/assistant`, `/assistant/[conversationId]`, files `src/features/assistant/*`.
**Live operations:** `GET/POST /assistant/conversations`, `GET /assistant/conversations/{id}`, `POST …/messages`, `POST /assistant/turns/{turn_id}/transfer`, `GET/POST /assistant/turns/{turn_id}/draft`, `GET …/draft-options`, `POST …/start`, `GET /projects/{case_id}/intake-sources`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Conversation list | `GET /assistant/conversations` → `items[{conversation_id, title, agent, status(working/answered/cannot_answer/drafted), status_line, updated_at}]`, cursor, limit | `items[{conversation_id, case_id, scope (project|department), agent, updated_at, django_url}]`; no title, status or paging | reshaped |
| Thread messages | `GET /assistant/conversations/{id}` → `messages[{role person|agent, text, steps[], sources[], at, draft_work_id, cannot_reason, handoff, draft{title,status_label,rows,start,next,started}}]` | `messages[{id, question, status, answer|null, sources[{label,django_url}], at, started_work_id, draft_url, transfer_url}]`; one object per question and answer | reshaped |
| Which sources the answer may use | `context{project, access[]}`, `@mentions` picker `GET /assistant/mentions?q&kind` | `available_sources[{key,label,django_url}]`, `question_options[]` (suggested questions) | reshaped |
| Agents the person can use | `/me` → `assistant_agents` | same | same |
| Draft for starting work | inline `draft{rows,start,started}` | `GET /assistant/turns/{turn_id}/draft` → by line: `{line, case_id, case_revision, draft_version, draft{…}, started_work_id}`; options `GET …/draft-options` → `{fields[], items[{id,label}], next_before, source_options_url, current_intake_id}` | new in live |
| "I can't answer" with reason; "staff-cost" suggestions | `cannot_reason`, `suggestions` (gap G-SCR05-5) | `status` text per message (likely carries "cannot"); no reason field | missing in live |
| Image upload (our D-161 proposal) | `/assistant/uploads` | none | missing in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Start a conversation | `POST /assistant/conversations` `{agent}` 200 `{conversation_id}` | `{agent, case_id (uuid), idempotency_key (uuid), scope?}` 200 `{conversation_id, case_id, scope, agent, updated_at, django_url}` — needs a project (or department scope) | reshaped (project first) |
| Ask a question | `POST …/messages` `{text, mentions[{kind,id}]}` 200 `{message_id, agent_run_id, status}` | `{text, idempotency_key (uuid), source_keys[]}` → **202** `{message_id, status}`; then read the conversation until `status` settles | reshaped (202; sources instead of mentions; closes G-SCR05-3) |
| Pass the answer to another agent | the hand-off note in the thread | `POST /assistant/turns/{turn_id}/transfer` `{agent}` 200 conversation | new in live |
| Save the draft | none | `POST …/draft` `{line, case_revision, draft_version, draft{per-line fields}, background?}` 200 (closes part of G-SCR05-2) | new in live |
| Start the work from the draft | open Start work drawer prefilled | `POST …/start` same body → 200 `{work_id, state, revision}`; only the exact saved `draft_version` | reshaped |

**Design parts the live API cannot fill:** thread titles and status badges in the list; step-by-step "what I did" lines under an answer; the @mention picker for project/work/document/person; the "can't, here is why" card with buttons; the "working" run card with start time; image attachments; replies as separate person/agent bubbles with edit.
**Live data the design does not show yet (worth knowing):** the project/department scope of each conversation; the list of exact sources the person may let the agent read; suggested questions; a saved, reviewed draft with version; hand-off between agents. Note: the backend review says the project picker for department chat returns only sample projects until a real provider path is approved.
**Effort to connect:** L — conversation is now per project, messages are per question and queued, the source picker replaces mentions, and drafts add a new save-then-start flow.
**Questions for the backend:**
1. A-28 `GET /assistant/conversations`: can items carry `title`, `status` and `status_line` (working / answered / cannot answer / drafted) so the list can show them?
2. A-29 `POST /assistant/conversations`: for the "new conversation" button, which `case_id` do we send when the person has not picked a project (department scope)?
3. A-30 `GET …/conversations/{id}` `messages[].status`: what are all the values, and where is the reason when the agent cannot answer?
4. A-31 Is there a working-progress field (steps or started time) to show while `status` is not final, and how often should we poll?
5. A-32 Is there a way to attach an image to a question (our design allows it), or should we remove that part?

---

### SCR-06 · Overview: factory floor
**Built today:** yes — F-08, route `/overview`, files `src/features/overview/*` (flat and 3D floor).
**Live operations:** `GET /overview`; drill-down `GET /work?line=`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| "Updated at" | `as_of` | `as_of` | same |
| Four totals (in progress, need a person, stopped, verified this month) | `totals{in_progress, need_a_person, stopped, verified_this_month}` | none | missing in live |
| Floor rows, one per line group ("Pre-sale", "Invoices", "Payroll"…) | `lines[{line, key, subtitle, agent, status{label,tone}, note}]` — 8 groups | `lines[{key, title, total}]` — one per authorised line definition (up to 26 keys like `planning/v1`) | reshaped (groups are gone) |
| Station counts on the floor (name, count, needs a person) | `lines[].stations[{name,count,needs_person}]` | none | missing in live |
| Line tag and colour | `lines[].status{label,tone}` | none | missing in live |
| Open the matching queue | link to `/my-work` or `/exceptions` | `GET /work?line=<key>` (crosswalk: "open the exact corresponding line queue") | new in live |

**Writes:** none.

**Design parts the live API cannot fill:** the four headline totals; per-station counts and "needs a person" marks; the line tag colour and label ("Stopped", "Waiting"); the grouping into eight floors with agent and subtitle (we hold the subtitle and avatar text keyed to the group name; live gives 26 line keys, so the mapping must be rewritten).
**Live data the design does not show yet (worth knowing):** one total per line the person is allowed to see (counts "recorded work", so the screen must say what total means).
**Effort to connect:** M — the data shrinks to a count per line; the floor must be redrawn from line keys and a mapping we keep (line key → floor group), or the design reduced.
**Questions for the backend:**
1. A-33 `GET /overview`: does `total` mean all recorded work or open work, and is it scoped to the person?
2. A-34 `GET /overview`: can it return totals (in progress, need a person, stopped, verified this month) and per-line station counts with `needs_person`?
3. A-35 `GET /overview`: is a group (floor) for each line key planned, or do we keep our own mapping of 26 keys to 8 floors?
4. A-36 Which roles may read `/overview`: do others get 403 (v7: leads, CEO, CTO only)?

---

### SCR-10 · All exceptions
**Built today:** yes — F-06, route `/exceptions`, files `src/features/exceptions/*`.
**Live operations:** `GET /work?queue=exceptions`, `GET /work/{work_id}`; recovery actions as in SCR-02; line detail `GET /work/{id}/{payroll-recovery|accounting|incumbent-reference|invoice-milestone-proof|invoice-draft-stop|information/{task_id}}`, `POST /work/{id}/forecast/lifecycle`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The list of exceptions | `GET /exceptions` → `items[{work_id, what, title, doing, who_acts, since, ref}]`, cursor, limit | `GET /work?queue=exceptions&line=&q=&page=&project=` → standard work rows | moved (different path and shape) |
| What happened (tag) | `what`: `effect_uncertain, owner_needed, setup_needed, blocked, followup_needed` | `items[].state`: `effect_uncertain, owner_needed, setup_needed, action_needed (= blocked), followup_needed`, `awaiting_reconciliation` | renamed |
| "What's being done" | `doing` | `status_label` (backend wording); fuller text: `next_step` and `blocker` on `GET /work/{id}` | reshaped (extra read per row) |
| "Who acts" | `who_acts` | `owner` (nullable) | renamed |
| "Since" | `since` | `updated_at` (last change, not start of the exception) | reshaped |
| Reference | `ref` | none | missing in live |
| Filter by kind of exception | `what` | none (use `state` on the returned rows) | missing in live |
| Count of open exceptions | `open_count` | none | missing in live |
| Page | `cursor`, `limit` | `page`, `next_page`, fixed 8 rows; empty pages possible (see SCR-01) | reshaped |

The `exceptions` queue also lists ready/waiting work and verified work whose source changed, and exception rows are filtered after paging, so `evaluated` and `deferred` matter.

**Writes** (read-only screen today; the row opens the work item): live recovery actions are on the work item — `POST /work/{id}/actions` reconcile (202), `POST /work/{id}/control`, `…/invoice-draft-stop`, `…/information/{task_id}`, `…/corrections`, `POST /work/{id}/forecast/lifecycle` — see SCR-02.

**Design parts the live API cannot fill:** the "kind of exception" filter chip; the open-exceptions count in the heading; a "since when" time; the reference column; Leads-only wording (live filters by the person's access).
**Live data the design does not show yet (worth knowing):** `blocker` text, `owner` is often "Unassigned", `limited/deferred` coverage, payroll questions held for the person.
**Effort to connect:** S–M — same list pattern as My work with a different queue; main work is the extra detail read for the "doing" line.
**Questions for the backend:**
1. A-37 `GET /work?queue=exceptions`: can each row carry the exception kind, the time the exception began, and a one-line "what is being done"?
2. A-38 `GET /work?queue=exceptions`: can we get the open total and a `state` filter?
3. A-39 Which role gets this queue (v7 said leads only): is it everyone with access to the record?

---

### SCR-14 · Verified outputs
**Built today:** partly — the "Done" tab of My work (F-02) is the closest; the design's separate Verified list with Output, Facts earned, Proof and Verified-at columns is not built. Route `/my-work?queue=done`.
**Live operations:** `GET /work?queue=verified`, `GET /work/{id}` (`output_url`), `GET /work/{id}/history`, `GET /work/{id}/department-handoff`, `GET /projects/{case_id}/billing-invoices/{invoice_id}`, line readbacks `…/engagement`, `…/weekly-report`, `…/leadership-report`, `…/stability`, `…/bid-submission`, `…/forecast`, `…/accounting`, `…/incumbent-reference`, `GET /projects/{case_id}/delivery/{dossier_id}/closure-checklist`, `POST /work/{id}/corrections`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The list of verified items | `GET /work?queue=done` | `GET /work?queue=verified` (only verified work; an item whose source changed after verification drops out) | renamed |
| Output title and reference ("INV-0398") | `title`, `reference` | `title`; reference only inside the invoice record (`billing-invoices/{id}.reference`) or line readback | partly missing |
| "Facts earned" ("Email delivery receipt · 03 Nov 11:20") | `facts[]` on the item | none in list; per line from the readback or `output_url` target | missing in live (extra read) |
| Proof | none | `output_url` → the line's verified readback (report, receipt, invoice, closure checklist) | new in live |
| Verified at | none in list | `updated_at` (last change; may not equal verification time) | reshaped |
| Filters "Verified · This month" | none in v7 | `line`, `q`, `project`; no date filter | missing in live |
| Count ("6 of 28") | `counts.done` | none | missing in live |
| Authenticated file | n/a | file downloads through the six proxied routes | new in live |

**Writes:** none. A correction of a verified output goes through `POST /work/{id}/corrections` (see SCR-02).

**Design parts the live API cannot fill:** the "Facts earned" and "Proof" columns in the list (they exist only after one read per item); month filter; total count.
**Live data the design does not show yet (worth knowing):** `output_url` to the real output; a verified item leaves the list when its source changes; handoff receipts via `department-handoff`.
**Effort to connect:** M — a new list view over `queue=verified`, plus one detail read per row or on open.
**Questions for the backend:**
1. A-40 `GET /work?queue=verified`: can rows carry `verified_at`, the output reference and a one-line proof ("Email delivery receipt · 03 Nov")?
2. A-41 `GET /work?queue=verified`: can we filter by month and get a total count?

---

### SCR-15 · Alerts and notification settings
**Built today:** yes — F-12, F-15 (bell and drawer), F-46 closed; routes `/notifications`, `/settings/alerts`; files `src/features/alerts/*`. The Account tab (password) is not built.
**Live operations:** `GET /notifications`, `POST /notifications/{notification_id}/read`, `GET/POST /me/alert-preferences`, `GET /me/account`, `POST /me/account/password`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| List of alerts | `GET /notifications?cursor&limit&q&agent&unread` → `items[{id, work_id, agent, text, at, read, reference, delivered_via, delivered_at, digest_at, in_app_reason}]`, `total`, `unread_count` | `GET /notifications` (no params) → `items[{id, title, subject, detail, group: action|update, read, django_url}]`, `as_of` | reshaped |
| Time, agent name and avatar, "via WhatsApp" | `at, agent, delivered_via, delivered_at` | none | missing in live |
| "Needs you" group | `needs_you` (our BQ-18) | `group: 'action'` = needs you; `'update'` = for information | renamed (closes BQ-18) |
| Open the work item | `work_id` | `django_url` (retired page; parse the work id out or ask) | missing in live |
| Search, agent filter, unread filter, paging, counts | query params, `total`, `unread_count` | none (full list, no paging) | missing in live |
| Settings: per-event WhatsApp/email switches, daily digest time, quiet hours, locked rows | `GET /me/alert-preferences` → `{channel, frequency, revision, events[{key,label,whatsapp,email,timing,locked_reason}], digest_at, quiet_hours, whatsapp{masked_number,verified}, note}` | `{revision, email_requested, whatsapp_requested, email_ready, whatsapp_ready, recent_deliveries[{channel, state: queued|uncertain|delivered|held, created_at, delivered_at, receipt}]}` | reshaped (two switches only) |
| Account: name, username, email | none | `GET /me/account` → `{name, username, email, alerts{…same as above}}` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Mark an alert read | `POST /notifications/{id}/read` no body → `{id, read, unread_count}` | same path, body `{}` + CSRF → `{id, read}` (no unread count) | reshaped |
| Save how I am alerted | `PUT /me/alert-preferences` `{channel, frequency, expected_revision, events[], digest_at, quiet_hours}` | `POST /me/alert-preferences` `{revision, email_requested, whatsapp_requested}` → 200 `{revision, …ready flags}` | moved (PUT→POST, body much smaller) |
| Change my password | none | `POST /me/account/password` `{old_password, new_password1, new_password2}` → 200 `{csrf_token, signed_in, next_url}`; store the new token | new in live |

**Design parts the live API cannot fill:** per-event switches, digest time, quiet hours, locked rows; the agent avatar and time in each alert; unread badge number from the server, search and agent filter; delivery wording per alert ("WhatsApp 10:40", "digest 17:00"). The frontend review says WhatsApp and email are deferred; only in-app alerts are live.
**Live data the design does not show yet (worth knowing):** whether email and WhatsApp channels are verified and ready; the last delivery receipts with states (queued, uncertain, delivered, held); a password change form.
**Effort to connect:** M — the list gets simpler (group, title, detail), settings shrink to two switches plus receipts, and the account tab is new.
**Questions for the backend:**
1. A-42 `GET /notifications`: can items carry `at`, `agent` and a work id (or a typed link) so we can show time, avatar and open the work item?
2. A-43 `GET /notifications`: will it page (`page`/`next_page`) and return an unread count?
3. A-44 `GET /me/alert-preferences`: will per-event switches, digest time and quiet hours come later, or should the design drop them for this release?
4. A-45 `POST /notifications/{id}/read`: is the body `{}` required, and does it need the unread count back?

---

### SCR-17 · Sign in
**Built today:** no — no route; signed-out state links out to Django `/accounts/login/`. Related: `SignedOutState` in `src/shell/FrameStates.tsx`.
**Live operations:** `GET /session`, `POST /session`, `POST /session/logout`, `GET /me`, `GET /role-dashboard`, `GET /me/onboarding`, `POST /accounts/recovery/request`, `POST /accounts/recovery/link`, `GET/POST /accounts/recovery/password`, `POST /accounts/invitations/preview`, `POST /accounts/invitations/accept`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Am I signed in; token for the form | not built | `GET /session` → `{csrf_token, signed_in, next_url}` | new in live |
| Where to go after sign-in | not built | `POST /session` → `next_url` (checked against our host; default is the person's landing page) | new in live |
| Is this session ready to set a new password | not built | `GET /accounts/recovery/password` → `{ready}` | new in live |
| Setup state: "Welcome Sola… you have PMO for Ojo Foods" | none (G-SCR17-3) | `POST /accounts/invitations/preview` `{token}` → `{name, email, expires_at, workspaces[{…, access}]}` | new in live |
| First-run entry | none | `GET /me/onboarding` → `{admitted, can_create_workspace, next_url}` | new in live |

**Writes**
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Sign in | none | `POST /session` `{username, password, remember?, next_url?}` → 200; bad details 422 `sign_in_failed` with no field names and no "tries left" | new in live |
| Ask for a reset link | none | `POST /accounts/recovery/request` `{email}` → **202** `{requested}` (same answer for every valid address; closes G-SCR17-7) | new in live |
| Open the link from the email | none | page `/accounts/recovery/link/` with the token in the URL fragment; `POST /accounts/recovery/link` `{token}` → 200 `{ready}` | new in live |
| Choose the new password | none | `POST /accounts/recovery/password` `{new_password1, new_password2}` → 200 `{complete}`; then sign in | new in live |
| Finish account setup (invitation) | none | page `/staff/join/` with token in the fragment; `POST /accounts/invitations/accept` `{token, password, confirm, review_alerts?}` → **201** `{complete, next_url}` | new in live |
| Sign out | none | `POST /session/logout` `{}` | new in live |

**Design parts the live API cannot fill:** "3 tries left before sign-in pauses for 15 minutes", "link works for 30 minutes", "At least 12 characters", "works for 72 hours" (policy values; not in any response); "You'll go straight to INV-0412" before sign-in (we flagged it as a leak, G-SCR17-2; nothing in live reveals it); WhatsApp number add and code check (G-SCR17-5, no operation).
**Live data the design does not show yet (worth knowing):** `expires_at` of an invitation; the workspaces and access words the invitation offers; the 429 rate-limit answer.
**Effort to connect:** M — five small forms against well-defined endpoints; two fragment-token routes and CSRF handling are the care points.
**Questions for the backend:**
1. A-46 `POST /session` 422 `sign_in_failed`: can it return how many tries are left or when sign-in resumes, or should the design drop those lines?
2. A-47 What are the password rules and the validity of reset links and invitations (30 minutes, 72 hours in the design) — can the preview and recovery status return `expires_at` and the minimum length?
3. A-48 `GET /me/onboarding`: if `admitted` is false what should the person see?
4. A-49 `POST /session` `remember`: what session length does each choice give?

---

### SCR-21 · Staff accounts
**Built today:** no — `/setup/staff` is a placeholder (`ReservedTab`, `src/features/setup/ReservedTab.tsx`). The Roles tab is also a placeholder.
**Live operations:** `GET /staff`, `GET /staff/{person_id}`, `GET/POST /staff/{person_id}/deactivation`, `GET/POST /staff/{person_id}/restoration`, `GET/POST /staff/delegations/{authority_id}`, `GET/POST /setup/{case_id}/invitations`, `GET/POST /setup/{case_id}/people/{person_id}/{primary-role|team-scope|profile|departure}`, `GET /me/workspaces/{case_id}/primary-role`, `GET/POST /setup/{case_id}/primary-roles`, `GET /setup/primary-roles`, `POST /accounts/invitations/accept`.

**Reads**
| What the screen shows | Today | Live (op → field) | Fit |
|---|---|---|---|
| The people list (name, email, roles and projects, account state) | not built | `GET /staff?q&status=all|active|inactive&page&invitations_page` → `people[{id, name, username, email, active, workspace_count, access, departure_available, reactivation_available}]`, `next_page` | new in live |
| Pending invitations ("INVITED · NOT SET UP", expires) | not built | same call → `invitations[{id, case_id, name, username, email, access, expires_at, status: pending|expired|accepted|superseded}]`, `next_invitations_page` | new in live |
| "8 people" count | not built | none | missing in live |
| "Last signed in" | not built | none | missing in live |
| One person's access by workspace | not built | `GET /staff/{person_id}?page` → `person{…}`, `workspaces[{case_id, name, access, primary_role, can_edit_profile, can_assign_primary_role}]` | new in live |
| Invite form choices (roles, team, authority) | not built | `GET /setup/{case_id}/invitations?team_id` → `{revision, authority_id, membership_id, lead_role, teams[{id,name}], invitations[]}`; roles: `GET /setup/{case_id}/primary-roles` | new in live |
| Deactivate review: open actions that need a new owner, proofs | not built | `GET /staff/{id}/deactivation` → `{person, fingerprint, blocked[], workspaces[{case_id, name, handover_pending, proofs[], actions[]}]}` | new in live |
| Restore review | not built | `GET /staff/{id}/restoration` → `{person, fingerprint, blocked[], guidance, workspaces[{case_id, name, role_source}]}` | new in live |

**Writes**
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Invite someone / resend | not built | `POST /setup/{case_id}/invitations` `{revision, name, username, email, authority_id, membership_id, role: pmo-lead|finance-lead|ceo|cto|hr|admin, mode: lead|member|standalone, team_id, preceding_id}` → **201** `{invitation, join_url, revision}`; resend = same call with `preceding_id` (renews, supersedes the old one) | new in live |
| Deactivate | not built | `POST /staff/{id}/deactivation` `{fingerprint, operation (uuid), reason, confirmed, actions[{action_id, successor_id}], evidence[{case_id, evidence_id}]}` 200 `{person_id, active}` | new in live |
| Restore sign-in | not built | `POST /staff/{id}/restoration` `{fingerprint, operation, reason, confirmed}` 200; prior grants stay revoked | new in live |
| Change role ("Edit roles") | not built | preview `GET /setup/{case}/people/{id}/primary-role?role=`; confirm `POST` same path (fingerprint, request id, reason); move to team scope: `…/team-scope` | new in live |

**Design parts the live API cannot fill:** "Last signed in"; the "8 people" count; the roles list written as "Finance Lead · Lagoon Health, Harmattan Bank" (live gives one `access` text per row and per-workspace roles from the person read); "Invite sent 2 days ago" (only `expires_at`; sent time unknown); the "Move to: Tunde Bello" picker with eligible people per action (the deactivation read lists `actions[]` but we have not confirmed it lists who may take each; likely, see question); "Deactivated 30 Oct" date; reasons for admins "can't approve anything" copy is design text only.
**Live data the design does not show yet (worth knowing):** a fingerprint-and-confirm flow for every change (review first, then confirm); `blocked[]` reasons that stop deactivation; handover proofs; technical delegation controls (`/staff/delegations/{authority_id}`); team-scope moves; the person's roles per workspace.
**Effort to connect:** L — the screen is built from scratch and every change is a two-step review then confirm, across several workspaces.
**Questions for the backend:**
1. A-50 `GET /staff`: can people carry `last_sign_in`, `deactivated_at`, `invited_at` and a total count?
2. A-51 `GET /staff/{id}/deactivation` `workspaces[].actions[]`: does each action list the people eligible to take it (for "Move to")?
3. A-52 `GET /staff`: `access` is a single string; can it come as a list of `{role, workspace}` so we can show "Finance Lead · Lagoon Health"?
4. A-53 Which role may open this screen: only delegated Admins ("workspaces you administer"), and what does a non-admin get (empty list or 403)?
5. A-54 `POST /setup/{case}/invitations`: how long is an invitation valid (design says 72 hours) and is the `join_url` host the Next.js origin?

---

## Cluster summary
- **Frame and session first.** Remove the origin/main embed (`FactoryDesk`, the `native` branch in `AppShell`, the Django rewrites and catch-all in `next.config.ts`), because the live `/me` always triggers it and replaces our shell with the retired UI. Then fix `/me` handling: destinations are objects (and the same six for everyone), `roles` is gone, and 403 has two meanings (`forbidden` vs `csrf_failed`). Build SCR-17 sign-in on `GET/POST /session`, with token rotation after sign-in, sign-out and password change.
- **Work reads lose the factory model.** Live `GET /work` and `GET /work/{id}` have no stations, facts, agent steps, kind, reference or counts, and `/work` pages 8 at a time by `page`. My work, Exceptions, Verified and the Work item header must be redrawn from `state`, `status_label`, `owner`, `next_step`, `blocker`, `panels[]`, `output_url` and `current_activity`, or the backend must add fields (questions A-6 to A-17, A-37 to A-41).
- **The generic workspace renderer has no live source.** There is no `workspace` block and no generic `POST /work/{id}/steps`; each line's content and commands are on its own panel endpoint with its own revision tokens and 200/201/202 results. Plan one adapter per line (other clusters) and keep only the frame pieces (locks, uncertain handling, stale reload, unknown-is-not-zero, restricted rows).
- **Decision and reconcile change meaning.** Decisions need an evidence id and note and cannot use `revoke` (SCR-03); "confirm what happened" is now a backend lookup (202), so the person cannot record delivered/not delivered with proof (A-13, A-18).
- **Start work becomes per-line typed forms.** `GET /lines` has no field list; `POST /work` has a different body for each of 25 lines and answers 200; uploads are multipart `POST /cases/{case_id}/files` (SCR-04). Assistant now needs a project per conversation and queues messages (202) (SCR-05).
- **Connect first:** frame + sign-in, then My work list and Work item header (needs answers to A-6, A-11, A-12), then Alerts and Account (simple), then Start work for the first few lines, Assistant, and Staff accounts (new build). Overview needs a product choice because live only gives a count per line.
