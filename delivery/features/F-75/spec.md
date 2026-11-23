# Registers and Actions tabs read the live sectioned project tab

> Tasks: FE-CONNECT-1 (D-180 connect exception). Architecture: live contract 1.22.0 (`contracts/psl-factory.openapi.json`, operation `workspaces_project_tab`); v7 package is the retiring mock contract. Design: approved boards for SCR-11 (Registers) and SCR-29 (Actions) in `design/screens.md`; D-182 "hide, accept all recs" applies; screens: SCR-11, SCR-29.

## Summary
- The Registers (SCR-11) and Actions (SCR-29) tabs stop reading the v7 typed arrays through `api` (`E-PROJECT-TAB`) and read `GET /api/v1/projects/{case_id}/registers|actions` through `liveApi`, using the generated live types.
- The live body is sections, not rows: `{case_id, tab, sections[], as_of}`. The page picks the drawn registers out of the returned sections by `title` through one small mapping table, and shows the "Project actions" section for Actions.
- Everything the boards draw that live cannot supply is hidden, never counted from a page and never shown as 0: count badges, header counts, age, owner role and marks, the "From meeting" line, Overdue as a state, the page-size choice.
- Paging follows the live rule: one `page` number shared by all sections, 25 rows a section. "Show more" uses the selected register's own `has_more` and keeps every section consistent.
- The contract mock moves to the live shape for these two tabs (UUID ids, `P-nnnn` still accepted) and a new Ajv test validates every served body against the live contract. Read-only; no writes.

## Context
Read on `origin/main` (F-70, PR #102, be9d34d9). Paths are under `frontend/` of the lane-b worktree.

- `src/features/projects/RegistersTab.tsx`, `ActionsTab.tsx`: built in F-25 on v7. Register switch via `Tabs` (`REGISTERS`), `ListToolbar` search, `Table`/cards, `ShowMore` with page-size choice, `summary` counts.
- `src/features/projects/tabsModel.ts`: v7 types from `operations['E-PROJECT-TAB']`, `REGISTERS`, `parseTabView`/`tabSearch`/`buildTabQuery` (limit, register, cursor), `isTabResponse`, `ageText`, `dueText`, `fromText`, `ownerText`, `actionsSummaryText`, `registerCount*`.
- `src/features/projects/useProjectTab.ts`: one `api.GET` per view, cursor "Show more".
- `src/features/projects/TabParts.tsx`: `tabStateView` (loading, signed out, 403/404 as `TabNoAccess`, error with Try again), `TabEmpty`, `AsOf`, `OwnerValue`, `RowLink`, `useTabPaging`.
- `src/features/projects/ProjectTabContent.tsx` renders `<RegistersTab caseId base />` and `<ActionsTab caseId base />`; props stay as they are. `ProjectJourney.tsx` (frame, `useProject`, tab bar from live `tabs[]`) is F-70's and unchanged.
- `src/features/projects/MoreFooter.tsx` and `model.ts` (`textOf`, `shownText`) are F-70's live pattern; `useProject.ts` is the live-client pattern (`call(liveApi.GET(...))`, `isJourney` check, sequence guard).
- `src/api/client.ts` already exports `liveApi`; `src/api/live-schema.d.ts` has `operations['workspaces_project_tab']`.
- Mock: `mock/project-tabs.mjs` (v7 shape, `items[]` and typed arrays, `cursor`/`limit`), `mock/server.mjs` (path normalised by `normaliseProjectPath`, route chosen by operation `E-PROJECT-TAB`), `mock/fixtures/projects/tabs/P-0101|0102|0106.{registers,actions}.json`.
- Backend (reference only, do not change): `apps/core/factory_api/workspaces.py` `project_tab` and `apps/core/project_journey.py` `sections`.
- Tests today: `tests/project-tabs-model.test.ts`, `tests/mock-project-tabs.test.ts` (v7 Ajv), `tests/project-tabs.test.tsx`, `e2e/project-tabs.spec.ts`, `e2e/tab-frames.spec.ts`.

## Contract

### Operation: read one tab
`GET /api/v1/projects/{case_id}/{tab}` with `tab` = `registers` or `actions`. Path `case_id` is the UUID from the project (`journey.case_id`); the mock also accepts `P-nnnn`.

Query the page sends: `q` (only when the settled search has text, at most 120 chars), `page` (only on "Show more", integer from 2). It never sends `state`, `owner`, `severity` (the boards draw no filters, G-SCR11-1; valid values are open question B-14) and never `limit`.

200 body (generated type, nothing hand-written):
```
{ case_id: uuid, tab: string, as_of: date-time,
  sections: [ { title, page, has_more, django_url, api_url|null,
                items: [ { title, state, detail|null, at|null, due|null, severity|null, owner|null,
                           django_url, record_id: number, api_url|null } ] (max 25) } ] }
```
What the live backend does (read from `project_tab`), which the build relies on:
- Sections are returned only for what the person may read: Issues and Escalations (`issue.read`), Changes (`change.read`), Emergency changes (`emergency.read`), Bid requests (`rfp.read`); Actions returns one "Project actions" section. A permitted section with no rows is returned with `items: []`.
- `page` is one number applied to every section. A section that has fewer pages than the requested page answers with its last page again and its own `page` value (Django `get_page` clamps). So a section is new data only when its returned `page` equals the requested page.
- `q` applies to every section at once. `as_of` is the server time of that read.
- Item text: Issues: `title` = the issue reference, `detail` = the issue's own title, `state` = status word, `severity` = "Critical/High/Medium/Low", `owner` = name or team label. Changes: `title` = reference, `state` = "Version N", `detail` = module. Emergency changes and Bid requests: `title` = reference, `state` = a fixed phrase, no detail/owner/severity. Escalations: `title` = issue reference, `state` = "Awaiting decision" or "Decision recorded · <verdict>". Actions: `title` = action text, `state` = status word ("Open", "In progress", "Paused", "Completed", "Cancelled"), `detail` = owner name or "Owner needed", `due` date-time or null.

Errors (all through `call()` and `ApiError`): 401 signed out (sign-in prompt keeping the current path), 403 and 404 (same "No access to this tab" state, no row text left behind), 422 `invalid_filter`, 5xx and network (error card with Try again, "Your work is safe; nothing was changed"). A 200 that is not a sections body for the requested tab is a load failure (`unexpected_response`).

Permission and tenant: decided by the server per record and action. The page renders only the sections it receives and never infers a permission. Idempotency and versioning: none (read-only GET); no polling, no automatic retry.

### Pure model (in a new file `src/features/projects/sectionsModel.ts`)
- Types from `operations['workspaces_project_tab']`: `TabBody`, `Section`, `SectionItem`.
- `isSectionsBody(body, tab)`: object, `case_id` text, `tab` equal to the requested tab, `sections` an array of objects each with text `title`, array `items` of objects with text `title` and text `state`, integer `page` of at least 1, boolean `has_more`.
- One swap-easy table (B-12 is open): `REGISTER_SECTIONS = [{ key:'issues', label:'Issues', word:'issues', title:'Issues' }, { key:'changes', label:'Changes', word:'changes', title:'Changes' }, { key:'emergencies', label:'Emergencies', word:'emergencies', title:'Emergency changes' }, { key:'rfps', label:'RFPs', word:'RFPs', title:'Bid requests' }]` and `ACTIONS_SECTION_TITLE = 'Project actions'`. A section whose `title` is in no table (Escalations) is not drawn.
- `availableRegisters(sections)`: the table entries whose section was returned, in the table's order.
- `parseSectionView(params, tab)`: `{register?, q?}`. `register` is read from the URL only for Registers; one not returned reads as the first available register (normally Issues). `q` is trimmed and cut at 120; empty is none. `sectionSearch(view)` writes `?register=<key>` for any register that is not Issues and `?q=` when set; `page` never goes in the URL.
- `buildSectionQuery(q, page?)` returns `{q?, page?}` only.
- `mergePage(prev, next, requestedPage)`: for each section in `next`, if its `page` equals `requestedPage` append its items to the section with the same `title` (a title not yet held is added) skipping an item whose `api_url ?? ''` plus `record_id` is already held, and take that section's `page` and `has_more`; otherwise leave the held items and set `has_more` to false. Titles absent from `next` stay as held.
- `stateTone(text)`: the one small table for Actions state tags, on display text (case-insensitive): open and in progress and paused = `waiting`, completed = `done`, cancelled = `neutral`, any other word = `neutral`; the tag shows the word as given in capitals. Registers show the state as plain text, as the board does. (B-2 and B-35 are open.)
- `severityTag(text|null)`: "high", "medium", "low" (any case) use the existing `PriorityTag`; any other word (including "Critical") is a neutral `Tag` with the word as given; null is "—".
- `dueText(due)`: `formatDayMonth(due)` for a readable date-time, otherwise undefined (the caller draws `Unknown`).

### Hook: `src/features/projects/useProjectSections.ts`
`useProjectSections(caseId, tab, q)` returns `{ state, more, showMore, retry }`.
- `state`: `loading` | `error` (an `ApiError`) | `ready` with `sections`, `requestedPage` (the last page asked, starting at 1), `asOf`.
- One read per `(caseId, tab, q)`; a new search reloads from page 1 and drops earlier rows. Switching the register does not read again (all sections are already held). A late answer for an earlier view is ignored (sequence guard, as `useProject`). A failed read drops rows and shows the error state.
- `showMore()` reads `requestedPage + 1` (with the same `q`), merges with `mergePage`, sets `asOf` from that answer. A failure keeps all rows and sets `more` to `error` (footer line "We couldn’t load more. Your rows are safe; try again." with Retry, `MoreFooter`); 401, 403 and 404 on it replace the tab with that state.
- The old `useProjectTab.ts` is deleted when nothing else imports it once F-71 has merged (see Lanes); do not leave two hooks reading the same endpoint.

### Screen SCR-11 Registers (`RegistersTab.tsx`)
- Register switch (`Tabs` label "Register", panel id `PANEL_ID`): only the drawn registers whose section came back, in the order Issues, Changes, Emergencies, RFPs, **no count badges**. `?register=` as before. If the four drawn registers are all absent, show the no-access state (`TabNoAccess`).
- Search box unchanged (placeholder "Search <word> by title or reference" desktop, "Search <word>" phone). **No result-count text** beside it.
- Table caption = the register label. Columns and cells per row of the selected section, as returned and in the returned order (no sorting):
  - ISSUE: `title` (mono), not a link.
  - WHAT: `detail`, else "—".
  - SEVERITY: `severityTag`, "—" for a row without one.
  - OWNER: `owner` as given; for the Issues register a null owner reads "Owner needed" (signal ink, `ptabs__noowner`); for other registers a null owner reads "—".
  - STATE: `state` as given.
  - No AGE column.
- Phone: cards as today: reference and severity; the WHAT text (else the reference); "state · owner" (owner part left out when "—").
- Footer: `MoreFooter` with `hasMore` from the selected section's `has_more`, no count text; no page-size choice. Under the rows `AsOf` from `as_of`, and the existing note "Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval."
- States: loading (`LoadingState`), signed out, no access (403/404), error with Try again, empty ("No <word> on this project yet."), empty search ("No <word> match “q”." with Clear search), success.

### Screen SCR-29 Actions (`ActionsTab.tsx`)
- The "Project actions" section only. If it is not returned the page shows the no-access state.
- Columns ACTION (`title`, not a link, no "From" line), OWNER (`detail`, "Owner needed" in signal ink when null or that text), DUE (`dueText`, else `Unknown`), STATE (`Tag` with `stateTone`). Rows in returned order. Phone cards: title with state tag, then "owner · due <date or Unknown>".
- Search box (placeholder "Search actions"), **no header counts**, `MoreFooter` from the section's `has_more`, `AsOf`, the existing note "Actions come from confirmed minutes."
- States as for Registers; empty copy "No actions on this project yet." / "No actions match “q”.".

### Fixture examples (mock, live shape)
`GET /api/v1/projects/00000000-0000-4000-8000-000000000101/registers`:
```json
{ "case_id": "00000000-0000-4000-8000-000000000101", "tab": "registers", "as_of": "2026-11-12T15:40:00Z",
  "sections": [
    { "title": "Issues", "page": 1, "has_more": false, "django_url": "/projects/00000000-0000-4000-8000-000000000101/issues/", "api_url": "/api/v1/projects/00000000-0000-4000-8000-000000000101/issues",
      "items": [ { "title": "ISS-0233", "detail": "Login fails on older Android phones", "state": "Fix in testing", "severity": "High", "owner": "Tunde Bello",
                   "at": null, "due": null, "django_url": "/projects/…/issues/#issue-233", "record_id": 233, "api_url": "/api/v1/projects/…/issues/233" } ] },
    { "title": "Changes", "page": 1, "has_more": false, "items": [ { "title": "CHG-0014", "detail": "Reminders", "state": "Version 2", "severity": null, "owner": null, "at": null, "due": null, "record_id": 14, "api_url": "…/change-versions/31", "django_url": "…" } ], "django_url": "…", "api_url": "…" } ] }
```
Actions item: `{ "title": "Send test accounts for UAT", "state": "Open", "detail": "Lagoon Health", "due": "2026-11-13T00:00:00Z", "at": null, "severity": null, "owner": null, "record_id": 1, "api_url": "…/actions/1", "django_url": "…" }` and one with `"detail": "Owner needed", "due": null`.

Fixture set (replace the v7 files, same names; builder fills required fields):
- `P-0101.registers`: Issues 3 (one "Critical", one with null severity-free? no: severities Critical, High, Low), Escalations 1, Changes 2, Emergency changes 0 rows (section present, empty), Bid requests 1.
- `P-0102.registers`: Issues 30 rows (two pages), Changes 1, Emergency changes 1, Escalations 1, Bid requests 1 (so page 2 returns the last Issues page and the clamped other sections).
- `P-0106.registers`: all four drawn sections present with `items: []` (empty case).
- `P-0101.actions` (9 rows, one "Owner needed", one null due, states Open/In progress/Completed), `P-0102.actions` (4), `P-0106.actions` (section present, empty).
- Cookie or persona case: one fixture variant where Issues and Escalations are absent (a person without `issue.read`) so the switch shows only Changes, Emergencies, RFPs; the builder wires it to an existing persona (for example the persona with the least access) and names it in build.md.

### Mock handler (`mock/project-tabs.mjs`, registers and actions only)
- Output the live envelope: `case_id` = `uuidOf(P-nnnn)`, `tab`, `sections` sliced 25 per section by `page` (fixtures hold every row of a section), `as_of` from the fixture. Page beyond a section's last page answers that section's last page with its own `page` (the clamp). `has_more` = another page exists after the answered one.
- `q` filters every section's rows case-insensitively on `title` and `detail`; `page` not an integer of at least 1, `q` over 120 or empty `q=` answers 422 `{code:'invalid_filter', message:'We could not read that list request.'}`; `state`, `owner`, `severity` are ignored.
- Visibility unchanged: `P-0099` and a case outside the persona's list answer 404, `P-0103` answers 403, an unlisted `P-nnnn` answers like `P-0106`.

## Lanes
- **Frontend lane (this builder, lane-b)** owns: `src/features/projects/RegistersTab.tsx`, `ActionsTab.tsx`, `sectionsModel.ts` (new), `useProjectSections.ts` (new), `project-tabs.css` rules used only by these two tabs (`ptabs__registers`, `ptabs__actions-table`, `ptabs__cards` pieces), the mock handler's registers/actions branch and fixtures, and the tests below.
- **Backend lane**: none. The live API is read as-is; contract questions go to `delivery/connect/backend-questions.md` under "New from lanes" with the prefix `LB-`.
- **Integration owner**: the coordinator, for merge order with F-71.
- **Not ours**: `src/api/*` and `src/shell/*` are lane A's (no change needed; `liveApi` exists). `src/features/workspace/*` is lane C's.

**Files F-71 and F-75 both touch** (F-71 builds first; F-75 starts with `git fetch && git merge origin/main`, then rebases its edits onto F-71's, keeping F-71's version of anything about Milestones, Documents or Money):
1. `src/features/projects/tabsModel.ts`: F-71 rebuilds it for Milestones. F-75 deletes only the register and action remnants (`RegisterRow`, `ActionRow`, `Register`, `REGISTERS`, `registerOf`, `registerCount*`, `ageText`, `fromText`, `actionsSummaryText`, `dueText`, `ownerText` if unused, and the registers/actions entries in `ROW_CHECKS`, `parseTabView`, `tabSearch`, `buildTabQuery`) and leaves everything else alone. New code goes in the new `sectionsModel.ts` to avoid a conflict.
2. `src/features/projects/useProjectTab.ts`: F-71 may change it for Milestones/Documents. F-75 does not edit it; it adds `useProjectSections.ts` and deletes `useProjectTab.ts` only if `grep -rn useProjectTab src tests` finds no user left.
3. `src/features/projects/TabParts.tsx`: F-75 widens the `tabStateView` parameter type to `{status:'loading'|'ready'|'error'; error?: ApiError}` (structural, so both hooks fit) and deletes `OwnerValue`, `RowLink`, `useTabPaging` only if grep shows no other user. F-71 owns `AmountValue`.
4. `src/features/projects/ProjectTabContent.tsx`: F-75 makes no change (props are the same). F-71 may.
5. `mock/project-tabs.mjs`, `mock/server.mjs`: both edit the handler; keep one handler that answers each tab's live body. F-75 adds only the registers and actions branch; F-71 owns milestones and documents. If F-71 already chose a fixture file format for sections, F-75 uses the same format.
6. `tests/mock-project-tabs.test.ts`, `tests/project-tabs-model.test.ts`, `tests/project-tabs.test.tsx`, `e2e/project-tabs.spec.ts`, `e2e/tab-frames.spec.ts`: F-75 deletes or rewrites only the registers/actions cases and adds its own new test files (below).
7. `mock/fixtures/projects/tabs/*`: F-75 owns the `*.registers.json` and `*.actions.json` files only.

Builder runtime: worktree lane-b, ports 4970 (Next) and 4971 (mock), Django 8010 on PG 127.0.0.1:55433; run commands from `frontend/`.

## Acceptance criteria
1. Registers on the mock read the live endpoint: opening `/projects/00000000-0000-4000-8000-000000000101/registers` (and `/projects/P-0101/registers`) makes `GET /api/v1/projects/<uuid>/registers` with no `limit`, `register`, `cursor`, `state`, `owner` or `severity`; the page shows a "Register" tab list `Issues, Changes, Emergencies, RFPs` — verify: Playwright request log in `e2e/project-tabs.spec.ts` and the tab names at 1440 and 390.
2. The register switch has no count badges and there is no count text beside the search; Actions has no "N ACTIONS · N OVERDUE · N WITHOUT OWNER" line — verify: page at P-0101, text absent; a test asserts no digit-only badge on the register tabs.
3. An Issues row shows reference (mono), the issue title, severity, owner and state exactly as returned; a "Critical" row shows a neutral tag reading "Critical" (not High); there is no AGE column and no row link — verify: P-0101 registers page and `tests/project-tabs.test.tsx`.
4. Changes shows reference, module and "Version N"; Emergencies and RFPs show "—" for severity and owner; a null owner on an Issues row reads "Owner needed" — verify: switch registers on P-0101; `?register=changes` in the URL; unit test on the row text.
5. A person whose response has no Issues section sees only the registers returned and `?register=issues` falls back to the first available; with none of the four returned the page shows "No access to this tab" — verify: the variant fixture and a unit test with `sections: []`.
6. The Escalations section is never drawn, and no section title outside the mapping table appears anywhere — verify: P-0101 fixture has an Escalations row whose reference text is not on the page.
7. Paging on P-0102 (Issues 30 rows): the first read shows 25 Issues and a "Show more" button; pressing it requests `?page=2`, appends 5 rows (30 shown), and the button goes; switching to Changes afterwards shows its 1 row once, not twice (the clamped answer is not appended again) — verify: `tests/project-tabs.test.tsx` with the mock and the request log.
8. With a search, changing register does not request again, but changing the search does, from page 1, and drops the rows held — verify: request log; URL `?q=android` and `?register=changes&q=android`.
9. A failed "Show more" keeps every row, shows "We couldn’t load more. Your rows are safe; try again." with Retry, and Retry succeeds — verify: test forcing a 503 on `page=2`.
10. Actions: the section "Project actions" is shown with ACTION, OWNER, DUE, STATE; a null `due` shows the amber `Unknown` tag, not a date and not 0; `detail` "Owner needed" or null shows "Owner needed"; state tags show the live word in capitals with the tone table; no "From" line and no OVERDUE tag unless the live word is itself "Overdue" (it is then neutral) — verify: P-0101 actions page at 1440 and 390.
11. A due date-time shows as "13 Nov" in the Africa/Lagos test timezone — verify: unit test of `dueText` and the e2e run (`timezoneId: 'Africa/Lagos'`).
12. Negative: `P-0099` and a case outside the persona show the same "No access to this tab" state with no row text; `P-0103` (403) the same; a 401 shows the signed-out state with the tab's path kept; a 422 or 503 shows the error card with Try again and nothing was changed — verify: mock cases in `tests/project-tabs.test.tsx`.
13. A 200 whose `tab` is not the requested one, or whose sections are malformed, is shown as the error card, not as an empty list — verify: unit test of `isSectionsBody` and a hook test.
14. Search with no match shows "No <word> match “q”." with Clear search; a section with zero rows and no search shows "No <word> on this project yet." — verify: `?q=zzz` on P-0101; `P-0106`.
15. Mock contract: every served body for registers and actions (all personas, `P-0101`, `P-0102`, `P-0106`, UUID and `P-nnnn` ids, `page=1..3`, `q`) validates against the live 200 schema with Ajv (`strict: true`, `ajv-formats`), `case_id` is a UUID, page 3 of P-0102 answers each section's last page with its own `page`, `page=0` / `page=x` / `q=` answer 422 — verify: new `tests/mock-live-project-sections.test.ts` (pattern of `tests/mock-live-projects.test.ts`), run `npx vitest run tests/mock-live-project-sections.test.ts`.
16. `mergePage` and `isSectionsBody`, `parseSectionView`, `sectionSearch`, `stateTone`, `severityTag`, `dueText` have unit tests, including the clamp case and the duplicate case — verify: `tests/project-sections-model.test.ts`.
17. A grep of the two tab files and the new hook finds no `api.GET` and no import of the v7 `E-PROJECT-TAB` types — verify: `grep -rn "E-PROJECT-TAB\|useProjectTab" src/features/projects/RegistersTab.tsx src/features/projects/ActionsTab.tsx` returns nothing.
18. Against the real backend (Django 8010): signed in as `live-lead`, `/projects/<case_id>/registers` and `/actions` render without console errors and the as-of time shows; a case the account cannot read shows "No access to this tab" — verify: manual run with the lane ports, recorded in build.md.
19. Accessibility and layout: axe WCAG 2.2 AA clean and no horizontal scroll at 390 and 1440 on both tabs; the register switch keeps arrow, Home and End keys; after "Show more" removes the button, focus moves to the first new row — verify: `e2e/project-tabs.spec.ts` (registers and actions cases updated).

## Out of scope
- Every write: record, update or close an issue, change, emergency or escalation, assign a bid, assign, complete or create an action. They need an `evidence_id` (B-37) and are not drawn.
- Money and Milestones tabs (F-71), the Documents tab, the Journey, Delivery, the issue and action detail pages and meetings.
- Filters on `state`, `owner` or `severity`; a page-size choice; any `limit`.
- Counting anything from loaded rows (register counts, overdue, without-owner, "N shown").
- Computing Overdue, age or any state from dates; sorting or regrouping rows.
- Linking rows to `api_url`, `django_url` or `/work/...` (no frontend detail route exists, B-15); a new route.
- Any backend, `src/api`, `src/shell` or `src/features/workspace` change.

## Conflicts with the boards
Under D-182 each hide is the build default (option 1). Items 1 to 8 are plain hides. Items 9 to 11 are not plain hides and carry options, recommendation first.

1. Count badges on the register switch ("ISSUES 3") and the count text beside the search — live has none. Option 1: hide (build default). Option 2 (later, when B-12 adds totals): show them.
2. Actions header "12 ACTIONS · 3 OVERDUE · 2 WITHOUT OWNER" — live has none (B-36). Option 1: hide.
3. Registers AGE column and the "2d" value — live does not send age (B-13). Option 1: hide the column.
4. Owner role and the "recorded by PM" and outside-party marks — live owner is a plain text (B-13, B-35). Option 1: show the name only.
5. Action "From <meeting> · <date>" line — not in the list read. Option 1: hide.
6. OVERDUE as an action state tag — the list `state` is the status word only. Option 1: show the live word; no overdue tag.
7. Page-size choice 10/20/50 — live pages 25 a section and has no `limit`. Option 1: hide; "Show more" only.
8. Rows that open a work page — the boards' rows are links; live gives only API paths of records with no frontend page. Option 1: rows are plain text (build default). Option 2: link rows once a detail page exists (a later feature).
9. Severity "Critical" — the boards draw High/Medium/Low only. Option 1 (recommended): show "Critical" as its own neutral tag with the live word. Option 2: show it as High (loses what the PM recorded). Option 3: hide Critical rows (hides real issues; not advised).
10. Escalations — live returns a section the boards do not draw. Option 1 (recommended): leave it out of the switch and show nothing of it; listed here for D-184. Option 2: add a fifth register "Escalations" with the same columns (needs a board). Option 3: fold its rows into Issues (mixes different record kinds).
11. Changes, Emergencies and RFPs under the Issues columns — the boards use one set of columns for every register; live has no severity or owner for these. Option 1 (recommended): keep the same columns and show "—" where live has no value. Option 2: per-register columns (needs a board).

Board static text kept as drawn: the registers note ("Severity is set by the PM. …") and the actions note ("Actions come from confirmed minutes.").

## Assumptions
- Register default: Issues when returned, else the first returned drawn register; the board is silent for a person without Issues.
- Section matching is on `title` through the mapping table only; no fallback to "the only section", so a renamed title shows no-access rather than a guess (B-12 open).
- A section's rows are matched across pages by `api_url` plus `record_id`; two reads of the same rows never show a row twice if data shifts between pages.
- Null owner on a non-Issues register is "—" (not applicable), not "Owner needed", because those records have no owner in live.
- Actions state tones (open, in progress, paused = waiting; completed = done; cancelled and unknown words = neutral) are a display choice on text, not a business status model; B-2 and B-35 are open.
- Registers state stays plain text as the board draws it; only Actions uses state tags.
- The phone cards and footer note text are unchanged from F-25.
- Shown time uses the existing `formatDayMonth`; the live `due` is a date-time, so a due near midnight may show the local day.
- The retiring `E-PROJECT-TAB` v7 operation stays in the mock route table for Milestones and Documents until F-71 moves them.
