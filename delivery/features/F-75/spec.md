# Registers and Actions tabs read the live sectioned project tab

**Re-specified against 1.24.0 (D-185).** What changed from the 1.22.0 spec: sections are matched by `key` (B-12), state tones by `state_code` (B-2), and the board parts D-182 hid for lack of data are now built as drawn: register count badges, the Actions header counts, the AGE column and the "From <meeting> · <date>" line. Parts live still cannot supply stay hidden (see Conflicts).

> Tasks: FE-CONNECT-1 (D-180 connect exception). Architecture: live contract 1.24.0 (`contracts/psl-factory.openapi.json`, operation `workspaces_project_tab`, main b8542c79); v7 package is the retiring mock contract. Design: approved boards for SCR-11 (Registers) and SCR-29 (Actions) in `design/screens.md`; D-182 applies only to what 1.24.0 still does not supply; screens: SCR-11, SCR-29.

## Summary
- The Registers (SCR-11) and Actions (SCR-29) tabs stop reading the v7 typed arrays through `api` (`E-PROJECT-TAB`) and read `GET /api/v1/projects/{case_id}/registers|actions` through `liveApi`, using the generated live types (`src/api/live-schema.d.ts` already carries the 1.24.0 section fields).
- The live body is sections, not rows: `{case_id, tab, sections[], as_of}`. The page picks registers by the stable section `key` (`issues`, `changes`, `emergencies`, `rfp`) and Actions by key `meetings`; section `title` text is never matched.
- Built as the boards draw them, now that live supplies the data: count badges per register (`section.total`), the Actions header "N ACTIONS · N OVERDUE · N WITHOUT OWNER" (`section.counts`), the issue AGE column (`age_days`), and "From <meeting> · <date>" on action rows (`origin_meeting`). A null value reads "—" or Unknown, never 0.
- Still hidden because live has no data: owner role and "recorded by PM"/outside-party marks, Overdue as a row state, page-size choice, row links (no frontend detail route).
- Paging follows the live rule: one `page` shared by all sections, 25 rows a section, "Show more" uses the selected register's own `has_more`. Read-only. The per-action proof upload (priority 1) is a write, not drawn on these tabs, and is a follow-up.

## Context
Paths are under `frontend/` of the lane-b worktree (read on `origin/main` b8542c79, which includes F-70, PR #102).

- `src/features/projects/RegistersTab.tsx`, `ActionsTab.tsx`: built in F-25 on v7. Register switch via `Tabs` (`REGISTERS`), `ListToolbar` search, `Table`/cards, `ShowMore` with page-size choice, `summary` counts.
- `src/features/projects/tabsModel.ts`: v7 types from `operations['E-PROJECT-TAB']`, `REGISTERS`, `parseTabView`/`tabSearch`/`buildTabQuery` (limit, register, cursor), `isTabResponse`, `ageText`, `dueText`, `fromText`, `ownerText`, `actionsSummaryText`, `registerCount*`; it imports `STATE_TAGS` and `FactoryState` from `@/components` (`src/components/Tag.tsx`).
- `src/features/projects/useProjectTab.ts`: one `api.GET` per view, cursor "Show more".
- `src/features/projects/TabParts.tsx`: `tabStateView` (loading, signed out, 403/404 as `TabNoAccess`, error with Try again), `TabEmpty`, `AsOf`, `OwnerValue`, `RowLink`, `useTabPaging`.
- `src/features/projects/ProjectTabContent.tsx` renders `<RegistersTab caseId base />` and `<ActionsTab caseId base />`; props stay as they are. `ProjectJourney.tsx` is F-70's and unchanged.
- `src/features/projects/MoreFooter.tsx` and `model.ts` (`textOf`, `shownText`) are F-70's live pattern; `useProject.ts` is the live-client pattern (`call(liveApi.GET(...))`, `isJourney` check, sequence guard).
- `src/api/client.ts` exports `liveApi`; `src/api/live-schema.d.ts` has `operations['workspaces_project_tab']` with the 1.24.0 section (`key`, `total`, `counts`) and item fields (`state_code`, `reference`, `age_days`, `origin_meeting`).
- Routes: there is no frontend route for an issue, action, change or bid detail (`src/app/work/[id]` is a work item, not a register record). Rows therefore stay plain text.
- Mock: `mock/project-tabs.mjs` (v7 shape), `mock/server.mjs` (path normalised by `normaliseProjectPath`, route chosen by operation `E-PROJECT-TAB`), `mock/fixtures/projects/tabs/P-0101|0102|0106.{registers,actions}.json`.
- Backend (reference only, do not change): `apps/core/factory_api/workspaces.py` `project_tab`, `SECTION`, `SECTION_ITEM`; `apps/core/project_journey.py` `sections`.
- Tests today: `tests/project-tabs-model.test.ts`, `tests/mock-project-tabs.test.ts` (v7 Ajv), `tests/project-tabs.test.tsx`, `e2e/project-tabs.spec.ts`, `e2e/tab-frames.spec.ts`.

## Contract

### Operation: read one tab
`GET /api/v1/projects/{case_id}/{tab}` with `tab` = `registers` or `actions`. Path `case_id` is the UUID from the project (`journey.case_id`); the mock also accepts `P-nnnn`.

Query the page sends: `q` (only when the settled search has text, at most 120 chars), `page` (only on "Show more", integer from 2). It never sends `state`, `owner`, `severity` (the boards draw no filters, G-SCR11-1; B-14 says the tab has no option catalogue for them) and never `limit` (B-34: projects page at a fixed 25).

200 body (generated type, nothing hand-written):
```
{ case_id: uuid, tab: string, as_of: date-time,
  sections: [ { key, title, page, has_more, total: int>=0, django_url, api_url|null,
                counts: { overdue, unassigned, total } | null,
                items: [ { title, state, state_code, detail|null, at|null, due|null, severity|null, owner|null,
                           reference|null, age_days: int>=0|null,
                           origin_meeting: { id, reference, at } | null,
                           django_url, record_id: number, api_url|null } ] (max 25) } ] }
```
What the live backend does (read from `project_tab` and `project_journey.sections`), which the build relies on:
- Section `key` is the route name without "-page": registers return `issues`, `escalations`, `changes`, `emergencies`, `rfp`; Actions returns one section with key `meetings` (title "Project actions"). Sections come back only for what the person may read (`issue.read`: Issues and Escalations; `change.read`; `emergency.read`; `rfp.read`). A permitted section with no rows returns `items: []`.
- `total` is the authorised row count of that section for the current `q` (not for the current page). `counts` is non-null only on the Actions section: `total`, `overdue` and `unassigned` for the authorised actions matching the current `q`, using the backend's due-date and pause rules. The page never counts rows itself.
- `page` is one number applied to every section. A section with fewer pages than requested answers with its last page again and its own `page` value, so a section is new data only when its returned `page` equals the requested page.
- `q` applies to every section at once. `as_of` is the server time of that read.
- Item text. Issues: `title` = reference, `reference` = same, `detail` = the issue's own title, `state` = status word as display text, `state_code` = raw status, `severity` = "Critical/High/Medium/Low", `owner` = name, team label or "Owner needed", `age_days` = whole days open, null for closed issues. Changes: `title` = reference, `state` = "Version N", `detail` = module, `state_code` = `recorded`. Emergency changes and Bid requests: `title` = reference, a fixed `state` phrase, `state_code` `recorded`, no detail/owner/severity. Escalations: `title` = issue reference, `state` = "Awaiting decision" or "Decision recorded · <verdict>". Actions: `title` = action text, `state` = display word, `state_code` one of `open`, `in_progress`, `paused`, `completed`, `cancelled`, `detail` = owner name or "Owner needed", `due` date-time or null, `reference` = action reference, `origin_meeting` = `{id, reference, at}` only when the person can see the source meeting, else null.

Errors (all through `call()` and `ApiError`): 401 signed out (sign-in prompt keeping the current path), 403 and 404 (same "No access to this tab" state, no row text left behind), 422 `invalid_filter`, 5xx and network (error card with Try again, "Your work is safe; nothing was changed"). A 200 that is not a sections body for the requested tab is a load failure (`unexpected_response`).

Permission and tenant: decided by the server per record and action. The page renders only the sections it receives and never infers a permission. Idempotency and versioning: none (read-only GET); no polling, no automatic retry.

### Pure model (new file `src/features/projects/sectionsModel.ts`)
- Types from `operations['workspaces_project_tab']`: `TabBody`, `Section`, `SectionItem`.
- `isSectionsBody(body, tab)`: object, `case_id` text, `tab` equal to the requested tab, `sections` an array of objects each with text `key` and `title`, integer `total` of at least 0, integer `page` of at least 1, boolean `has_more`, `counts` null or `{overdue,unassigned,total}` integers, and `items` an array of objects with text `title`, `state` and `state_code`, `age_days` null or an integer of at least 0.
- One swap-easy table: `REGISTER_SECTIONS = [{ id:'issues', label:'Issues', word:'issues', key:'issues' }, { id:'changes', label:'Changes', word:'changes', key:'changes' }, { id:'emergencies', label:'Emergencies', word:'emergencies', key:'emergencies' }, { id:'rfps', label:'RFPs', word:'RFPs', key:'rfp' }]` and `ACTIONS_SECTION_KEY = 'meetings'`. A section whose `key` is in no table (`escalations`) is not drawn. `title` is never read for matching.
- `availableRegisters(sections)`: the table entries whose section was returned, in the table's order.
- `parseSectionView(params, tab)`: `{register?, q?}`. `register` is read from the URL only for Registers (`?register=issues|changes|emergencies|rfps`, as before); one not returned reads as the first available register. `q` is trimmed and cut at 120; empty is none. `sectionSearch(view)` writes `?register=<id>` for any register that is not Issues and `?q=` when set; `page` never goes in the URL.
- `buildSectionQuery(q, page?)` returns `{q?, page?}` only.
- `mergePage(prev, next, requestedPage)`: for each section in `next`, if its `page` equals `requestedPage` append its items to the held section with the same `key` (a key not yet held is added), skipping an item whose `api_url ?? ''` plus `record_id` is already held, and take that section's `page`, `has_more`, `total` and `counts`; otherwise leave the held items and set `has_more` to false. Keys absent from `next` stay as held.
- `stateTone(code)`: the one small table for Actions state tags, on `state_code`: `open`, `in_progress`, `paused` = `waiting`; `completed` = `done`; `cancelled` = `neutral`; any other code = `neutral`. The tag shows `state` text as given, in capitals. Registers show `state` as plain text, as the board does.
- `severityTag(text|null)`: "high", "medium", "low" (any case) use the existing `PriorityTag`; any other word (including "Critical") is a neutral `Tag` with the word as given; null is "—".
- `ageText(days|null)`: `${n}d` for a known integer (0 reads "0d"), "—" for null. Never 0 for null.
- `dueText(due)`: `formatDayMonth(due)` for a readable date-time, otherwise undefined (the caller draws `Unknown`).
- `fromText(origin|null)`: `From <reference> · <day month>` using `formatDayMonth(at)`; undefined for null (no line drawn).

### Hook `src/features/projects/useProjectSections.ts`
`useProjectSections(caseId, tab, q)` returns `{ state, more, showMore, retry }`.
- `state`: `loading` | `error` (an `ApiError`) | `ready` with `sections`, `requestedPage` (the last page asked, starting at 1), `asOf`.
- One read per `(caseId, tab, q)`; a new search reloads from page 1 and drops earlier rows. Switching the register does not read again. A late answer for an earlier view is ignored (sequence guard, as `useProject`). A failed read drops rows and shows the error state.
- `showMore()` reads `requestedPage + 1` (same `q`), merges with `mergePage`, sets `asOf` from that answer. A failure keeps all rows and sets `more` to `error` (footer line "We couldn’t load more. Your rows are safe; try again." with Retry, `MoreFooter`); 401, 403 and 404 on it replace the tab with that state.
- `useProjectTab.ts` is deleted only when `grep -rn useProjectTab src tests` finds no user after F-71 has merged; do not leave two hooks reading the same endpoint.

### Screen SCR-11 Registers (`RegistersTab.tsx`)
- Register switch (`Tabs` label "Register", panel id `PANEL_ID`): the drawn registers whose section came back, in the order Issues, Changes, Emergencies, RFPs. Each tab carries a count badge from that section's `total`, as the board draws; a `total` of 0 reads "0" because it is a known zero count from the server. `?register=` as before. If the four drawn registers are all absent, show the no-access state (`TabNoAccess`).
- Search box unchanged (placeholder "Search <word> by title or reference" desktop, "Search <word>" phone). Beside it the selected section's count line from `total` (existing wording of the F-25 `registerCount*` helpers, fed by `total`); with a search set, the badges and the line are the counts of matching rows, as the server returns them.
- Table caption = the register label. Columns and cells per row of the selected section, as returned and in the returned order (no sorting):
  - ISSUE: `title` (mono), not a link.
  - WHAT: `detail`, else "—".
  - SEVERITY: `severityTag`, "—" for a row without one.
  - OWNER: `owner` as given; for the Issues register a null owner reads "Owner needed" (signal ink, `ptabs__noowner`); for other registers a null owner reads "—". No role text and no "recorded by PM" or outside-party mark (live does not send them).
  - AGE: `ageText(age_days)`, as the board draws; "—" when null.
  - STATE: `state` as given.
- Phone: cards as today: reference and severity; the WHAT text (else the reference); "state · owner · age" (a part that reads "—" is left out).
- Footer: `MoreFooter` with `hasMore` from the selected section's `has_more`; no page-size choice. Under the rows `AsOf` from `as_of`, and the existing note "Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval."
- States: loading (`LoadingState`), signed out, no access (403/404), error with Try again, empty ("No <word> on this project yet."), empty search ("No <word> match “q”." with Clear search), success.

### Screen SCR-29 Actions (`ActionsTab.tsx`)
- The section with key `meetings` only. If it is not returned the page shows the no-access state.
- Header line from `section.counts`: "<total> ACTIONS · <overdue> OVERDUE · <unassigned> WITHOUT OWNER" when `counts` is non-null and no search is set. With a search set the line reads "<total> actions match “q”" from `section.total`. A null `counts` draws no line. Numbers come from the server only; never from rows loaded.
- Columns ACTION (`title`, not a link, and under it the `fromText(origin_meeting)` line when present), OWNER (`detail`, "Owner needed" in signal ink when null or that text), DUE (`dueText`, else the amber `Unknown` tag), STATE (`Tag` with `stateTone(state_code)` showing `state`). Rows in returned order. Phone cards: title with state tag, the From line, then "owner · due <date or Unknown>".
- No Overdue row tag: live gives overdue only as a section total, not per row.
- Search box (placeholder "Search actions"), `MoreFooter` from the section's `has_more`, `AsOf`, the existing note "Actions come from confirmed minutes."
- States as for Registers; empty copy "No actions on this project yet." / "No actions match “q”.".

### Fixture examples (mock, live shape)
`GET /api/v1/projects/00000000-0000-4000-8000-000000000101/registers`:
```json
{ "case_id": "00000000-0000-4000-8000-000000000101", "tab": "registers", "as_of": "2026-11-12T15:40:00Z",
  "sections": [
    { "key": "issues", "title": "Issues", "page": 1, "has_more": false, "total": 3, "counts": null,
      "django_url": "/projects/00000000-0000-4000-8000-000000000101/issues/", "api_url": "/api/v1/projects/00000000-0000-4000-8000-000000000101/issues",
      "items": [ { "title": "ISS-0233", "reference": "ISS-0233", "detail": "Login fails on older Android phones", "state": "Fix in testing", "state_code": "fix_in_testing",
                   "severity": "High", "owner": "Tunde Bello", "age_days": 2, "origin_meeting": null,
                   "at": null, "due": null, "django_url": "/projects/…/issues/#issue-233", "record_id": 233, "api_url": "/api/v1/projects/…/issues/233" } ] },
    { "key": "changes", "title": "Changes", "page": 1, "has_more": false, "total": 1, "counts": null,
      "items": [ { "title": "CHG-0014", "reference": null, "detail": "Reminders", "state": "Version 2", "state_code": "recorded", "severity": null, "owner": null, "age_days": null, "origin_meeting": null, "at": null, "due": null, "record_id": 14, "api_url": "…/change-versions/31", "django_url": "…" } ], "django_url": "…", "api_url": "…" } ] }
```
Actions section: `{ "key": "meetings", "title": "Project actions", "total": 9, "counts": { "total": 9, "overdue": 2, "unassigned": 1 }, ... }` with item `{ "title": "Send test accounts for UAT", "reference": "ACT-0001", "state": "Open", "state_code": "open", "detail": "Lagoon Health", "due": "2026-11-13T00:00:00Z", "origin_meeting": { "id": 4, "reference": "Weekly sync", "at": "2026-11-10T09:00:00Z" }, "at": null, "severity": null, "owner": null, "age_days": null, "record_id": 1, "api_url": "…/actions/1", "django_url": "…" }` and one with `"detail": "Owner needed", "due": null, "origin_meeting": null`.

Fixture set (replace the v7 files, same names; builder fills required fields):
- `P-0101.registers`: Issues 3 (severities Critical, High, Low; one closed with `age_days: null`), Escalations 1, Changes 2, Emergency changes 0 rows (section present, `total: 0`), Bid requests 1 (key `rfp`).
- `P-0102.registers`: Issues 30 rows (two pages, `total: 30`), Changes 1, Emergency changes 1, Escalations 1, Bid requests 1 (so page 2 returns the last Issues page and the clamped other sections).
- `P-0106.registers`: all four drawn sections present with `items: []`, `total: 0` (empty case).
- `P-0101.actions` (9 rows, one "Owner needed", one null due, one with `origin_meeting: null`, states open/in_progress/completed), `P-0102.actions` (4), `P-0106.actions` (section present, empty, `counts` all 0).
- A variant where Issues and Escalations are absent (a person without `issue.read`) so the switch shows only Changes, Emergencies, RFPs; wired to the existing persona with least access, named in build.md.

### Mock handler (`mock/project-tabs.mjs`, registers and actions only)
- Output the live envelope: `case_id` = `uuidOf(P-nnnn)`, `tab`, `sections` sliced 25 per section by `page` (fixtures hold every row), `as_of` from the fixture. Page beyond a section's last page answers that section's last page with its own `page` (the clamp). `has_more` = another page exists after the answered one. `total` = rows matching `q`. For Actions `counts` = `{total, overdue, unassigned}` over the matching rows, overdue meaning a non-null `due` before `as_of` with `state_code` not `completed`, `cancelled` or `paused`, unassigned meaning `detail` "Owner needed" with an active state; other sections `counts: null`.
- `q` filters every section's rows case-insensitively on `title`, `reference` and `detail`; `page` not an integer of at least 1, `q` over 120 or empty `q=` answers 422 `{code:'invalid_filter', message:'We could not read that list request.'}`; `state`, `owner`, `severity` are ignored.
- Visibility unchanged: `P-0099` and a case outside the persona's list answer 404, `P-0103` answers 403, an unlisted `P-nnnn` answers like `P-0106`.

## Lanes
- **Frontend lane (lane-b)** owns: `src/features/projects/RegistersTab.tsx`, `ActionsTab.tsx`, `sectionsModel.ts` (new), `useProjectSections.ts` (new), `project-tabs.css` rules used only by these two tabs (`ptabs__registers`, `ptabs__actions-table`, `ptabs__cards` pieces), the mock handler's registers/actions branch and fixtures, and the tests below.
- **Backend lane**: none. The live API is read as-is; contract questions go to `delivery/connect/backend-questions.md` under "New from lanes" with the prefix `LB-`.
- **Integration owner**: the coordinator, for merge order with F-71.
- **Not ours**: `src/api/*` (including `live-schema.d.ts`) and `src/shell/*` are lane A's; `liveApi` exists and the schema already holds 1.24.0, so no change is needed. `src/features/workspace/*` is lane C's.

**Files F-71 and F-75 both touch** (F-71 builds first; F-75 starts with `git fetch && git merge origin/main`, then keeps F-71's version of anything about Milestones, Documents or Money). F-71 now puts its milestone code in `milestonesModel.ts` and `useMilestones.ts` and leaves the register and action parts alone.
1. `src/features/projects/tabsModel.ts`: F-71 removes only milestone remnants. F-75 deletes only the register and action remnants (`RegisterRow`, `ActionRow`, `Register`, `REGISTERS`, `registerOf`, `registerCount*` (move the wording into `sectionsModel.ts` first), `ageText`, `fromText`, `actionsSummaryText`, `dueText`, `ownerText` if unused, and the registers/actions entries in `ROW_CHECKS`, `parseTabView`, `tabSearch`, `buildTabQuery`). New code goes in `sectionsModel.ts`.
2. `src/features/projects/useProjectTab.ts`: F-75 does not edit it; deletes it only if no user is left (see Hook).
3. `src/features/projects/TabParts.tsx`: F-75 widens the `tabStateView` parameter type to `{status:'loading'|'ready'|'error'; error?: ApiError}` (structural, so every hook fits) and deletes `OwnerValue`, `RowLink`, `useTabPaging` only if grep shows no other user. F-71 owns `AmountValue`.
4. `src/features/projects/ProjectTabContent.tsx`: F-75 makes no change. F-71 may.
5. `mock/project-tabs.mjs`, `mock/server.mjs`: both edit the handler; keep one handler that answers each tab's live body. F-75 adds only the registers and actions branch; F-71 owns milestones and documents. Use F-71's fixture file format for sections if it chose one.
6. `tests/mock-project-tabs.test.ts`, `tests/project-tabs-model.test.ts`, `tests/project-tabs.test.tsx`, `e2e/project-tabs.spec.ts`, `e2e/tab-frames.spec.ts`: F-75 deletes or rewrites only the registers/actions cases and adds its own new test files.
7. `mock/fixtures/projects/tabs/*`: F-75 owns the `*.registers.json` and `*.actions.json` files only.

Builder runtime: worktree lane-b, ports 4970 (Next) and 4971 (mock), Django 8010 on PG 127.0.0.1:55433; run commands from `frontend/`.

## Acceptance criteria
1. Registers on the mock read the live endpoint: opening `/projects/00000000-0000-4000-8000-000000000101/registers` (and `/projects/P-0101/registers`) makes `GET /api/v1/projects/<uuid>/registers` with no `limit`, `register`, `cursor`, `state`, `owner` or `severity`; the page shows a "Register" tab list `Issues, Changes, Emergencies, RFPs` — verify: Playwright request log in `e2e/project-tabs.spec.ts` and the tab names at 1440 and 390.
2. Sections are matched by `key`, not `title`: a fixture where the title text is changed (for example "Bid requests" renamed) but the key is `rfp` still shows RFPs; a section with an unknown key is not drawn — verify: unit test of `availableRegisters` and a render test.
3. Each register tab shows a count badge equal to its section's `total` (P-0101: Issues 3, Emergencies 0), and a total of 0 is shown as 0 only because the server sent 0; the count is never computed from loaded rows (P-0102 Issues reads 30 with 25 rows loaded) — verify: P-0102 page and `tests/project-tabs.test.tsx`; grep shows no `.length` used for a count in the two tab files.
4. An Issues row shows reference (mono), the issue title, severity, owner, age and state exactly as returned; a "Critical" row shows a neutral tag reading "Critical" (not High); `age_days: null` shows "—" not "0d"; `age_days: 0` shows "0d"; no row is a link — verify: P-0101 registers page and `tests/project-tabs.test.tsx`.
5. Changes shows reference, module and "Version N"; Emergencies and RFPs show "—" for severity, owner and age; a null owner on an Issues row reads "Owner needed"; no owner role or "recorded by PM" text appears — verify: switch registers on P-0101; `?register=changes` in the URL; unit test on the row text.
6. A person whose response has no `issues` section sees only the registers returned and `?register=issues` falls back to the first available; with none of the four returned the page shows "No access to this tab" — verify: the variant fixture and a unit test with `sections: []`.
7. The Escalations section is never drawn — verify: P-0101 fixture has an Escalations row whose reference text is not on the page.
8. Paging on P-0102 (Issues 30 rows): the first read shows 25 Issues and a "Show more" button; pressing it requests `?page=2`, appends 5 rows (30 shown), updates the badge from the newest answer, and the button goes; switching to Changes afterwards shows its 1 row once, not twice (the clamped answer is not appended again) — verify: `tests/project-tabs.test.tsx` with the mock and the request log.
9. With a search, changing register does not request again, but changing the search does, from page 1, and drops the rows held; badges then show the server's match counts — verify: request log; URL `?q=android` and `?register=changes&q=android`.
10. A failed "Show more" keeps every row, shows "We couldn’t load more. Your rows are safe; try again." with Retry, and Retry succeeds — verify: test forcing a 503 on `page=2`.
11. Actions (section key `meetings`) shows ACTION, OWNER, DUE, STATE; the header reads "9 ACTIONS · 2 OVERDUE · 1 WITHOUT OWNER" from `counts` on P-0101 and is absent when `counts` is null; with a search set the header reads "N actions match “q”"; the numbers are never counted from rows — verify: P-0101 actions page at 1440 and 390; test with `counts: null`.
12. An action with `origin_meeting` shows "From <reference> · <day month>" under the title; one with null shows no From line; a null `due` shows the amber `Unknown` tag, not a date and not 0; `detail` "Owner needed" or null shows "Owner needed"; the state tag shows the `state` text with the tone from `state_code`, an unknown code is neutral; no OVERDUE row tag appears — verify: P-0101 actions page at 1440 and 390; unit tests of `stateTone` and `fromText`.
13. A due date-time shows as "13 Nov" in the Africa/Lagos test timezone — verify: unit test of `dueText` and the e2e run (`timezoneId: 'Africa/Lagos'`).
14. Negative: `P-0099` and a case outside the persona show the same "No access to this tab" state with no row text; `P-0103` (403) the same; a 401 shows the signed-out state with the tab's path kept; a 422 or 503 shows the error card with Try again and nothing was changed — verify: mock cases in `tests/project-tabs.test.tsx`.
15. A 200 whose `tab` is not the requested one, or whose sections are malformed (missing `key`, `total` or `state_code`), is shown as the error card, not as an empty list — verify: unit test of `isSectionsBody` and a hook test.
16. Search with no match shows "No <word> match “q”." with Clear search; a section with zero rows and no search shows "No <word> on this project yet." — verify: `?q=zzz` on P-0101; `P-0106`.
17. Mock contract: every served body for registers and actions (all personas, `P-0101`, `P-0102`, `P-0106`, UUID and `P-nnnn` ids, `page=1..3`, `q`) validates against the live 1.24.0 200 schema with Ajv (`strict: true`, `ajv-formats`), `case_id` is a UUID, page 3 of P-0102 answers each section's last page with its own `page`, `counts` is non-null only for Actions, `page=0` / `page=x` / `q=` answer 422 — verify: new `tests/mock-live-project-sections.test.ts` (pattern of `tests/mock-live-projects.test.ts`), run `npx vitest run tests/mock-live-project-sections.test.ts`.
18. `mergePage`, `isSectionsBody`, `parseSectionView`, `sectionSearch`, `stateTone`, `severityTag`, `ageText`, `fromText`, `dueText` have unit tests, including the clamp case and the duplicate case — verify: `tests/project-sections-model.test.ts`.
19. A grep of the two tab files and the new hook finds no `api.GET`, no `title ===` section matching, and no import of the v7 `E-PROJECT-TAB` types — verify: `grep -rn "E-PROJECT-TAB\|useProjectTab" src/features/projects/RegistersTab.tsx src/features/projects/ActionsTab.tsx` returns nothing; same for `Project actions\|'Issues'` used as a match key in `sectionsModel.ts`.
20. Against the real backend (Django 8010): signed in as `live-lead`, `/projects/<case_id>/registers` and `/actions` render without console errors, the as-of time shows, and the badges and Actions header match the server's `total` and `counts`; a case the account cannot read shows "No access to this tab" — verify: manual run with the lane ports, recorded in build.md.
21. Accessibility and layout: axe WCAG 2.2 AA clean and no horizontal scroll at 390 and 1440 on both tabs; the register switch keeps arrow, Home and End keys; after "Show more" removes the button, focus moves to the first new row — verify: `e2e/project-tabs.spec.ts`.

## Out of scope
- Every write: record, update or close an issue, change, emergency or escalation, assign a bid, assign, complete or create an action, and the per-action proof upload (priority 1: a project action update accepts an eligible evidence ID or a checked private PDF). The boards do not draw an upload on SCR-11 or SCR-29. Follow-up feature, with B-37.
- Money, Milestones (F-71), the Documents tab, the Journey, Delivery, the issue and action detail pages and meetings.
- Setup answers B-23 to B-25 (rule `can_change`, review authority, `decision-proofs` upload) belong to the Setup screens; nothing in them changes this feature.
- Filters on `state`, `owner` or `severity`; a page-size choice; any `limit`.
- Counting anything from loaded rows; computing Overdue, age or any state from dates; sorting or regrouping rows.
- Linking rows to `api_url`, `django_url` or `/work/...` (B-15 says follow each item's own `api_url`, but no frontend detail route exists for these records, and `role-work` and `received-bids` urls are different kinds); a new route.
- An owner role label or "recorded by PM"/outside-party mark (the payload does not carry them).
- Any backend, `src/api`, `src/shell` or `src/features/workspace` change.

## Conflicts with the boards
D-182 hides that 1.24.0 now fills are removed from this list and built as drawn (acceptance 3, 4, 11, 12). What is left:

1. Owner role and the "recorded by PM" and outside-party marks — not in the payload (B-13: only where the native source records a role). Recommendation: show the name only (hide the role and marks).
2. OVERDUE as an action row tag — live sends `counts.overdue` for the section but no per-row overdue or timing. Recommendation: hide the row tag; the header still counts overdue. Revisit if the backend adds a per-row flag.
3. Page-size choice 10/20/50 — project tabs have a fixed 25 per section and no `limit` (B-34). Recommendation: hide; "Show more" only.
4. Rows that open a work page — the boards' rows are links; no frontend detail route exists for issue, change, emergency, bid or action records. Recommendation: plain text rows until a detail screen is built.
5. Severity "Critical" — the boards draw High/Medium/Low only. Option 1 (recommended): show "Critical" as its own neutral tag with the live word. Option 2: show it as High (loses what the PM recorded). Option 3: hide Critical rows (not advised).
6. Escalations — live returns a section (key `escalations`) the boards do not draw. Option 1 (recommended): leave it out of the switch; listed for D-184. Option 2: add a fifth register (needs a board). Option 3: fold into Issues (mixes record kinds).
7. Changes, Emergencies and RFPs under the Issues columns — one set of columns for every register. Option 1 (recommended): keep the columns and show "—" where live has no value. Option 2: per-register columns (needs a board).
8. Count badges and the count line while a search is set show the server's matching-row counts, not whole-register totals, because `total` follows `q`. Option 1 (recommended): show them as returned. Option 2: hide badges while searching.

Board static text kept as drawn: the registers note ("Severity is set by the PM. …") and the actions note ("Actions come from confirmed minutes.").

## New product questions (1.24.0)
None. Escalations (conflict 6) is unchanged from the earlier spec and needs no new answer to build.

## Assumptions
- Register default: Issues when returned, else the first returned drawn register; the board is silent for a person without Issues.
- Sections are matched on `key` through the mapping table only; no fallback to "the only section", so a renamed key shows no-access rather than a guess.
- A section's rows are matched across pages by `api_url` plus `record_id`, so shifting data never shows a row twice.
- Null owner on a non-Issues register is "—" (not applicable), because those records have no owner in live.
- Tones for Actions come from `state_code` (open, in_progress, paused = waiting; completed = done; cancelled and unknown codes = neutral); a display choice, not a business status model. Registers state stays plain text as the board draws it.
- `age_days` of 0 is a real "0d"; only null reads "—".
- The "From" line shows the meeting `reference` as the board's meeting label, because the payload has no meeting title.
- Header counts are drawn only without a search; with a search the line uses `total` (matching rows) because `counts` also follows `q`.
- The phone cards and footer note text are unchanged from F-25.
- Shown time uses the existing `formatDayMonth`; `due` is a date-time, so a due near midnight may show the local day.
- The retiring `E-PROJECT-TAB` v7 operation stays in the mock route table for Documents (and Milestones until F-71 merges).
