# The project list and project journey read from the live API

> Tasks: FE-CONNECT-1 (screen connection part, SCR-22 and SCR-07). Architecture: live contract `contracts/psl-factory.openapi.json` 1.22.0 (D-API-STYLE r3 as built; connection map `delivery/connect/screens-b-projects-setup-clients.md`, SCR-22 and SCR-07). Design: the approved canvas boards for SCR-22 and SCR-07 (F-07 DONE); screens: SCR-22, SCR-07 (Journey tab; Delivery tab only as a "not available yet" state).

## Summary
- `/projects` (SCR-22) and `/projects/[caseId]` (SCR-07 Journey tab) read from `GET /api/v1/projects` and `GET /api/v1/projects/{case_id}` through the live-typed client (`liveApi` in `src/api/client.ts`, types in `src/api/live-schema.d.ts`) that F-56/F-57 added.
- Every part of a board that the live data cannot fill is left out or shown as "Not available", never invented, never shown as 0. Each such part is listed under "Conflicts with the boards" below, with the build default.
- Row and work-item links use the live ids (UUID `case_id`, integer work id) and go to `/work/{id}`.
- The mock `GET /projects` and `GET /projects/{case_id}` move to the live shape and are validated against the live contract in a test (as F-57 did for `/me`). The v7 mock keeps serving every other screen and the tab screens that still call the v7 project-tab endpoints.
- No write, no backend change, no tab content change.

## Context
- List: `frontend/src/features/projects/ProjectsList.tsx` (table, phone cards, search, status tabs, paging with `usePagedRows`), `ProjectsPage.tsx`, `model.ts` (`buildProjectsQuery`, `parseProjectsView`, `isProjectList`, `LIMITS`, `LIST_TABS`, v7 type aliases from `operations['E-PROJECTS']`). Route `src/app/projects/page.tsx`.
- Journey: `ProjectJourney.tsx` (`ProjectFrame`, `ProjectView`, `JourneyTab`, `JourneyLines`, `ProjectFacts`, `AgentSummary`), `useProject.ts` (one read per opened project, ignores late responses), `ProjectTabs.tsx` + `PROJECT_TABS` in `model.ts`, `ProjectStates.tsx` (`ProjectNoAccess`), `DeliveryTab.tsx`, `ProjectTabContent.tsx` (`PmRoute` reads `journey.pm` and `journey.route`). Routes under `src/app/projects/[caseId]/`.
- The project read is shared: the frame reads it once for every tab. `ProjectTabContent`, `DeliveryTab` and `ProjectTabs` take the v7 `JourneyView`; they must be moved to the new view model in this feature (the tab contents themselves still call the v7 `/projects/{case_id}/{tab}`, `/money` hooks (`useProjectTab.ts`, `useMoney.ts`) on the mock and do not change).
- Mock: `frontend/mock/projects.mjs` (v7 `E-PROJECTS`, `E-PROJECT` from `mock/fixtures/projects/list.json`, `P-0101.json` ..., `mock/fixtures/E-PROJECT.json`, `mock/demo-projects.mjs`), routed in `mock/server.mjs`; validated today by `tests/mock-projects.test.ts` against the v7 contract. F-57's pattern is `tests/mock-live-me.test.ts` (Ajv2020 + ajv-formats over `../../contracts/psl-factory.openapi.json`).
- Existing tests that use the v7 project shape and move with it: `tests/projects.test.tsx`, `projects-journey.test.tsx`, `projects-model.test.ts`, `mock-projects.test.ts`, `demo-mock.test.ts` (lines ~352, ~372), `tab-frames.test.tsx`, `money.test.tsx`, `project-tabs.test.tsx`, `engagement-planning.test.tsx`, and e2e `e2e/projects.spec.ts`, `e2e/project-tabs.spec.ts`.

## Contract

### GET /api/v1/projects (live, read-only)
- Request query: `status` = `active` | `closed` | `all`, always sent explicitly (the page default stays Active; the live default is `all`); `q` only when non-empty, trimmed, at most 120 characters (longer input is cut at 120 in the box and never sent longer); `cursor` from the previous `next_cursor`. No `limit` is sent (live has none; page size is fixed by the backend).
- Response 200: `{ items[], next_cursor: string|null, as_of }`. Item: `case_id` (uuid), `title`, `revision`, `sample`, `manager` (string|null), `lifecycle` (string|null), `phase` (string|null), `reviews` (int|null), `exceptions` (int|null), `django_url` (never used).
- Errors: 401 -> the existing signed-out state. 403 -> `NotOpenState` as today. 400 / 422 (`invalid_filter`) / 5xx / network -> `WorkErrorCard` with Retry, text "We couldn’t load your projects. Your work is safe; nothing was changed." A 200 body that is not `{items[]}` of rows with a text `case_id` and `title` is treated as a load failure (`isProjectList` keeps this check).
- Permission and tenant rule: the backend returns only projects the person may see; the page never filters by role itself.
- Idempotency/versioning: a read; `revision` is carried but not shown.

### SCR-22 states and fields
- Columns (desktop): PROJECT (title link to `/projects/{case_id}`, sample label), PM (`manager`; null -> the plain words "No manager", not Unknown and not a name), WHERE IT IS (`phase`; if `phase` is null, `lifecycle`; if both null, `Unknown`), NEEDS A PERSON (`reviews`), STOPPED (`exceptions`). Null `reviews` / `exceptions` show `Unknown`, never 0. NEXT MILESTONE column is removed.
- Phone card: title, "<where it is> · PM <manager>" (omit the PM part when the manager is null), then the red line "N need a person · N stopped" for counts above 0 only.
- Status tabs: Active, Closed, All I can see, no count badges. Changing a tab or the search reloads from page 1; cursors are never written to the URL; `status` stays out of the URL for Active.
- Result text beside the search: "N shown" for the loaded rows; "N shown, more available" while `next_cursor` is set. The "N PROJECTS" total is not shown (a total from one page is not a total).
- Paging: "Show more" appends the next page with `next_cursor`. The rows-per-page choice and the `limit` URL value are removed; an old `?limit=` in a link is ignored.
- Loading: `LoadingState`. Empty: no search -> "No projects you can see yet." with "You see projects your roles cover."; with a search -> "No projects match" with "Show all projects" clearing the search. Error: as above. Success: rows plus the existing footnote.
- Fixture example (live shape):
```json
{ "items": [
  { "case_id": "00000000-0000-4000-8000-000000000101", "title": "Lagoon Health · patient app", "revision": 4, "sample": true,
    "manager": "Tunde Bello", "lifecycle": "active", "phase": "Release · UAT with client", "reviews": 2, "exceptions": 1,
    "django_url": "/projects/00000000-0000-4000-8000-000000000101/" },
  { "case_id": "00000000-0000-4000-8000-000000000104", "title": "Atlas Retail · POS refresh", "revision": 1, "sample": true,
    "manager": null, "lifecycle": null, "phase": null, "reviews": null, "exceptions": null,
    "django_url": "/projects/00000000-0000-4000-8000-000000000104/" } ],
  "next_cursor": null, "as_of": "2026-11-23T09:00:00Z" }
```
The second row must render "No manager", `Unknown` for where it is, and `Unknown` in both count columns.

### GET /api/v1/projects/{case_id}?page=n (live, read-only)
- Request: `case_id` from the route (percent-decoded once, `routeCaseId`); `page` omitted for page 1, then `next_page`.
- Response 200: `case_id, title, revision, sample, tabs[{key,title,django_url,api_url}], items[{id,line,reference|null,state,started,updated,django_url,api_url}] (20 a page), page, next_page|null, as_of, facts{total,waiting,stopped,finance|null{stages|null,delivered|null,next|null,limited},engagement|null{route,reference,manager|null}}, assistant[]`.
- Errors: 401 -> `SignedOutState` for the current tab path. 403 and 404 look the same: `ProjectNoAccess`, nothing about the project shown, not even the server message. Other errors -> `WorkErrorCard` "We couldn’t load this project. Your work is safe; nothing was changed." with Retry. A 200 without a text `title` or an array `items` is a load failure (`isJourney` is rewritten for the live shape).
- Permission and tenant rule: `facts.finance` is null without `finance.read`, `facts.engagement` null without `engagement.read`; `tabs[]` is permission-filtered. The page shows exactly what is returned and decides nothing from the person's role.
- Read once per opened project by the frame (`useProject`); a late response for an earlier project is ignored; "Show more" on the journey reads the next `page` and appends rows; a failed "Show more" keeps the loaded rows and offers Retry.

### SCR-07 Journey states and fields
- Crumb and title: `Projects` / client / title. The client crumb is the part of `title` before the first " · " (best reading of B-1). If `title` has no " · ", the crumb ends at "Projects" with no client element and the title shows whole.
- Route line: "PM <facts.engagement.manager> · <facts.engagement.route> · <total> pieces of work". Each part is left out when absent (manager null, engagement null). `facts.engagement.reference` and `revision` are not drawn on the board and are not shown; `sample` shows the existing `SampleLabel`. No line count is shown.
- Phone line: "<total> pieces of work · <waiting> waiting on people · <stopped> stopped".
- Facts strip (aria-label "Facts earned"): four cells in this order: CONTRACT STAGES (`finance.stages`), WAITING ON PEOPLE (`waiting`), STOPPED (`stopped`), NEXT MILESTONE (`finance.next`). A null or absent value reads "Not available" (finance not readable by this person, or not given), never 0 and never blank. INVOICES VERIFIED and PAID are not drawn. When `finance.limited` is true a plain line under the strip reads "Figures may be partial."
- Work rows ("The whole journey, oldest first" panel, in the order returned): line title (`line`) linking to `/work/{id}`; the reference when not null; a detail line "Started 12 Nov · Updated 14 Nov" (`formatDayMonth` of `started` and `updated`); one neutral `Tag` with the `state` words exactly as given, and a neutral dot. No matching on the words, no tone, no station line. Two rows with the same title keep the visually hidden reference/state suffix in the link name.
- When `next_page` is set, a "Show more" control reads the next page; the footer reads "N of <facts.total> shown" (here `total` is the whole project's, so it is valid). With no rows: `EmptyState` "No work yet" / "No work on this project yet."
- "What is next" and Tola's summary are not drawn. The Tola panel is replaced by a small panel with the "Ask me about this project" link to `/assistant` shown only when `assistant[]` is non-empty and the person has the `assistant` destination (`hasDestination(me,'assistant')`); no summary text, no paragraphs.
- Tab bar: built from live `tabs[]`, keeping only keys the frontend routes (`journey`, `milestones`, `documents`, `money`, `registers`, `actions`), in the order live returns them, with the board labels from `PROJECT_TABS`, no counts. `delivery` is not in the bar (no live tab). A tab the live list does not contain is not shown even if its route exists.
- Delivery route `/projects/[caseId]/delivery`: stays reachable; shows the frame plus one panel: title "Delivery is not available yet", body "This project’s delivery view is not connected yet." No mock rows, no `department-handoffs` substitute.
- Other tabs (Milestones, Documents, Money, Registers, Actions): unchanged content; they receive `caseId` (and, for the PM/route line in `ProjectTabContent.PmRoute`, the manager and route from `facts.engagement` when present) from the new view model.
- Fixture example (live shape) is a body valid against the live contract with: 3 `items` (one `reference: null`, one with the same title as another), `facts: {total: 7, waiting: 2, stopped: 1, finance: {stages: 4, delivered: 1, next: "UAT sign-off", limited: true}, engagement: {route: "Route A", reference: "ENG-0101", manager: "Tunde Bello"}}`, `tabs` with the seven live keys of a finance-reading PM, `next_page: 2` on a second fixture, and a variant with `finance: null`, `engagement: null`, and a title with no " · ".

### Mock (contract mock only)
- `mock/projects.mjs` serves `GET /api/v1/projects` and `GET /api/v1/projects/{case_id}` in the live shape above, from fixtures that validate against `paths['/api/v1/projects'].get.responses['200']` and `paths['/api/v1/projects/{case_id}'].get.responses['200']` of the live contract. `case_id` values are UUIDs (the live schema's `format: uuid`): each existing `P-nnnn` id gets a fixed UUID, and the mock accepts both forms in every `/projects/{case_id}/...` route (tabs, money, report) so tab fixtures keyed by `P-nnnn` keep working. The reserved no-access id answers 404 in both forms. The persona-visibility rules and `demo-projects.mjs` (D-164 won-RFP projects) keep working in the live shape.
- The mock honours `status` (default `all`, as live), `q` and `cursor`, returns 20 work items a page with `page` / `next_page`, and returns no `counts`, `total` or `limit` handling. A scenario or fixture for each state: loaded, empty list, no manager / null counts, list error, journey with finance null, journey with next page, journey 403 and 404.
- A new test `tests/mock-live-projects.test.ts` validates every list and journey fixture and served body (each persona, each state above) with Ajv2020 against the live contract, and fails if a fixture carries a field the live schema forbids.

## Lanes
- Frontend lane (the builder): `frontend/src/features/projects/*` (model, hooks, list, journey, tabs bar, delivery state, `ProjectTabContent`), `frontend/mock/projects.mjs`, `mock/demo-projects.mjs`, `mock/fixtures/projects/*`, `mock/fixtures/E-PROJECT*.json` as needed, `mock/server.mjs` (id normalising only), and the tests listed under Context plus the new `tests/mock-live-projects.test.ts`.
- Backend lane: none. No backend change, no contract change (`contracts/psl-factory.openapi.json` read-only).
- Integration owner: the builder, for the mock-to-contract test and the UUID mapping.
- Shared files owned by other lanes: `src/api/*` (lane A), `src/shell/*` (lane A), `src/features/workspace/*` (lane C). This feature needs no change there. If one proves necessary (for example a missing helper in `src/components`), it is a separate small commit after `git merge origin/main`, named in `build.md`.
- v7 `schema.d.ts` stays; other screens keep using it.

## Acceptance criteria
Run all commands from `/Users/Hunchoo/psl-factory-worktrees/lane-b/frontend`, Next.js on 4970 (live) / 4971 (mock), Django 8010.
1. `/projects` on the live backend lists the projects the signed-in person may see, as returned by `GET /api/v1/projects?status=active` — verify: sign in as live-lead, open `http://127.0.0.1:4970/projects`; the Network panel shows `status=active` and no `limit` on the request; rows match `curl` of the same URL.
2. All I can see sends `status=all`, Closed sends `status=closed`; Active is the page default — verify: click each tab, read the request; the address shows no `status` for Active, `?status=closed` for Closed.
3. Search sends `q` trimmed, never empty, never longer than 120 characters — verify: type a name, one request has `q=<name>`; clear it, the next has no `q`; paste 200 characters, request `q` length is 120 or less (unit test of `buildProjectsQuery`).
4. A row with null `manager` shows "No manager"; null `reviews` / `exceptions` show Unknown, not 0; a row with `reviews: 0` shows 0 — verify: mock fixture rows from the example above; `tests/projects.test.tsx` asserts all three.
5. The list has no NEXT MILESTONE column, no count badges on the status tabs, no "N PROJECTS" total and no rows-per-page choice; with `next_cursor` set it shows "N shown, more available" and "Show more" appends the next page — verify: `tests/projects.test.tsx` and page at 1440 and 390 wide on the mock.
6. List error states: 401 shows the signed-out state, 403 the not-open state, 500 / 422 / network the error card with Retry that reloads, empty list and empty search show the texts under SCR-22 — verify: mock scenarios in `tests/projects.test.tsx`.
7. `/projects/{case_id}` for a project the person can see shows the title, client crumb, route line, facts strip and work rows from live `GET /api/v1/projects/{case_id}` — verify: live-lead opens a project from the list; values equal the `curl` body (`oa.py live GET /api/v1/projects/{case_id} 3` for the shape).
8. A title without " · " shows the whole title and no client crumb — verify: `tests/projects-model.test.ts` on `clientOf`, and the mock variant.
9. The facts strip has exactly four cells (CONTRACT STAGES, WAITING ON PEOPLE, STOPPED, NEXT MILESTONE); with `finance: null` the finance cells read "Not available" and no cell reads 0 for an absent value; with `finance.limited: true` "Figures may be partial." appears; INVOICES VERIFIED and PAID never appear — verify: `tests/projects-journey.test.tsx` for the four fixtures.
10. Work rows show line title, reference (only when not null), "Started ·  Updated" dates, and one neutral tag with the `state` words as given; changing a state's words changes no colour; the link goes to `/work/{id}` with the integer id — verify: `tests/projects-journey.test.tsx` (tag class is neutral for "Waiting", "Version 2" and an unknown word; `href="/work/12"`).
11. With `next_page` set, "Show more" reads `?page=2`, appends rows, keeps focus on the first new row, and a failed second read keeps the first rows and offers Retry — verify: `tests/projects-journey.test.tsx`.
12. "What is next", Tola's summary text, the "Station n of m" line, and line count do not appear; the "Ask me about this project" link appears only when `assistant[]` is non-empty and the person has the Assistant destination, and goes to `/assistant` without any POST — verify: test asserts no request to `/api/v1/assistant/conversations`.
13. Wrong person / other tenant: 403 and 404 both show "You can’t open this project" with no title, id or server message; a project id that does not exist shows the same — verify: live-none opens a UUID from live-lead's list in the browser; the mock no-access id in both `P-0099` and its UUID form (`tests/projects-journey.test.tsx`).
14. 401 on the journey shows the signed-out state with the current tab's path as the return path; 500 shows the error card and Retry reloads — verify: `tests/projects-journey.test.tsx`.
15. The tab bar shows only keys in live `tabs[]` that the frontend routes, in the returned order, without counts; the Delivery tab is absent from the bar; a person whose `tabs[]` lacks `money` sees no Money tab — verify: `tests/project-tabs.test.tsx` with a reduced `tabs[]` fixture.
16. `/projects/{case_id}/delivery` shows "Delivery is not available yet" and no rows or mock text — verify: `tests/project-tabs.test.tsx` or `e2e/project-tabs.spec.ts` on the mock.
17. The Milestones, Documents, Money, Registers and Actions tabs still load their v7 mock content for a project opened by UUID, and by `P-0101` — verify: `e2e/project-tabs.spec.ts` and `tests/tab-frames.test.tsx` pass on the mock.
18. The mock list and journey bodies validate against the live contract for every persona and state, and `case_id` values are UUIDs; a deliberately invalid fixture (a non-UUID id, or an extra required field missing) makes the test fail — verify: `npx vitest run tests/mock-live-projects.test.ts`.
19. No file under `frontend/src` still reads `operations['E-PROJECTS']` or `operations['E-PROJECT']` for these two screens, and no code in `ProjectsList.tsx` or `ProjectJourney.tsx` reads `pm`, `stage`, `needs_person`, `stopped`, `next_milestone`, `counts`, `total`, `lines`, `tab_counts`, `agent_summary` or `next` — verify: `grep -rn "E-PROJECTS\|E-PROJECT'" src/features/projects` returns nothing for the list and journey modules; typecheck and lint pass.
20. The state words, counts or dates are never inferred: a unit test shows `factText`-style helpers return "Not available" for null and never "0" for null, and `reviews: null` renders Unknown — verify: `tests/projects-model.test.ts`.
21. On the design engineer's mock (ports 3000/3001 are not touched): the lane's mock server on 4971 shows the list, the journey, the empty list, the no-manager row and the Delivery "not available" state for design review — verify: open `http://127.0.0.1:4971/projects` and `/projects/00000000-0000-4000-8000-000000000101` (Playwright `e2e/projects.spec.ts` covers both).

## Out of scope
- All tab contents (SCR-11, 12, 29, 38, 08), the Delivery tab content and any substitute from `GET /projects/{case_id}/department-handoffs`.
- `POST /assistant/conversations` from "Ask me about this project" (stays a link to `/assistant`); any write; any backend or contract change.
- Work page `/work/{id}`: only the link is built here.
- Derived values: no "what is next", no station, no line count, no tab counts, no status counts, no total from one page, no "invoices verified" or "paid" from `finance.delivered`, no tag colour from the words of `state`.
- Reference, next milestone and due date on list rows; Active/Closed/All counts; rows-per-page; filters beyond search and status (the Filter panel keeps its "Filters come next" text).
- Templates, Month-end and HR live tab keys (not routed).
- Changes to `src/api`, `src/shell`, `src/features/workspace`.

## Assumptions
- `reviews` -> "needs a person" and `exceptions` -> "stopped" (best reading of B-32; flag in the PR). `facts.waiting` -> "waiting on people" and `facts.stopped` -> "stopped" on the journey (same reading).
- The WHERE IT IS column shows `phase`, falling back to `lifecycle`, then Unknown: B-32 does not say what each holds; showing one value avoids stacking two unexplained strings.
- Null `manager` reads "No manager": the sources say "show no manager"; an em dash would look like a missing value.
- `finance` null is "Not available" rather than "Unknown": the live reason is a permission or missing read, not an unknown business value.
- Mock UUID ids are fixed values (`00000000-0000-4000-8000-000000000nnn`, nnn from the `P-0nnn` number) so test URLs stay stable; both forms are accepted by the mock for every project route.
- The mock status default becomes `all` to match live; the frontend always sends `status`, so screens are unaffected.
- The tab bar keeps the frontend labels (board text) rather than live `title`, because labels for the six routed keys match the boards and live titles are not documented.
- `started` / `updated` are shown as day and month (`formatDayMonth`), the format of other time-light rows; no board draws them.
- `facts.engagement.reference` is not shown: no board slot; the project `revision` is not shown for the same reason.
- Page footers use "N of <total> shown" on the journey only because `facts.total` is the whole project's count, not a page's.

## Conflicts with the boards
Each item adds, moves or removes something a board draws. The build default is option 1 in every case, and the coordinator may batch these for the design engineer. These mirror readiness questions 1 to 6.

1. **Next milestone and reference on each SCR-22 row (B-33).** Live gives neither.
   1. (Recommended, build default) Remove the NEXT MILESTONE column and the reference; the table has five columns.
   2. Keep the column and show "Not available" on every row.
   3. Hold this feature until the backend adds the field.
2. **Count badges on Active / Closed / All and the "N PROJECTS" line (B-33).**
   1. (Recommended, build default) No badges; "N shown" plus "more available" while `next_cursor` is set.
   2. Show the loaded-page count as "20 or more" on the selected tab only.
   3. Keep the badges as "—".
3. **Rows-per-page choice on SCR-22 (B-34).** Live has no `limit`.
   1. (Recommended, build default) Remove the control; the page size is whatever the backend sends.
   2. Keep it as a display-only trim of the shown rows.
4. **"What is next", Tola's project summary, and the "Station n of m" line on SCR-07 (B-3, B-4).**
   1. (Recommended, build default) Remove them; the right-hand panel becomes a small panel with only the "Ask me about this project" link.
   2. Keep the panel and lines as empty slots reading "Not available yet".
   3. Hold the feature until the backend answers.
5. **Facts strip (B-6).** The board draws six cells including INVOICES VERIFIED and PAID.
   1. (Recommended, build default) Four cells from live (contract stages, waiting on people, stopped, next milestone) plus a "Figures may be partial." line; INVOICES VERIFIED and PAID removed.
   2. Keep six cells and show "Not available" in the two without a source.
   3. Feed INVOICES VERIFIED from `finance.delivered` (not recommended: it counts invoices with a delivery record, not verified ones).
6. **Delivery tab (B-5).** No live tab exists.
   1. (Recommended, build default) Not in the tab bar; the route shows "Delivery is not available yet".
   2. Keep the tab in the bar showing "not available yet".
   3. Replace it with `department-handoffs` rows (needs a new design).
7. **Status tag on work rows (B-2).** The board colours the tag by state.
   1. (Recommended, build default) One neutral tag with the live words until the backend gives a code.
   2. Match common words ("Waiting", "Blocked") to tones (rejected by readiness: matches on words).
8. **Tab counts and line count on the journey (B-5, B-3).** The board shows counts such as "Registers 2" and "N lines".
   1. (Recommended, build default) No counts; "N pieces of work" only.
   2. Show the counts as "—".
9. **Added by live: started and updated times on each work row, and a "Figures may be partial." line.** Not drawn on the boards.
   1. (Recommended, build default) Show them in the existing detail slot and under the strip, in the board's text style.
   2. Leave them out until the board draws them.
