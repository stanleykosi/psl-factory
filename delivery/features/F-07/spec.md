# Projects shows the projects a person can see, and each opens its whole journey, against the contract mock

> Tasks: FE-M3-PROJECTS, first part (R-PROJECT; JR-08 frontend half; A-ACCESSIBILITY; D-PAGING r2; INV-ACCESS; INV-SAMPLE). Architecture: package `architecture/packages/v5`, manifest.sha256 `a91bc3ce41f97d59afd80bf918b8462d2a5d3eaf3ff7bace23cde79b751e8606`, openapi.json info.version `5ebad6a4a904`, base commit `267a426`. E-PROJECTS and E-PROJECT are byte-identical in v4 and v5, and the generated client and mock still load v4. Design: canvas version 1794581312-b166 (design/review.json); screens: SCR-22 (artboards SCR-22-desktop, SCR-22-mobile) and SCR-07 (SCR-07-desktop, SCR-07-mobile, plus the "EMPTY · PROJECT JOURNEY" card), with the shared STATES-desktop and STATES-mobile boards (design/canvas/project/).

## Summary
- `/projects` replaces the "not built yet" placeholder with SCR-22. It is a list of the projects the person's grants cover, with Project, PM and "Where it is". The list has a search box, 10/20/50 rows per page and "Show more". It reads only E-PROJECTS (`GET /api/v1/projects`).
- `/projects/<case_id>` is new and shows SCR-07: a breadcrumb, the title, a project tab bar with only Journey, a "What is next" callout and every line's work in the order returned. Each line has its state tag and a link to `/work/<work_id>`. It reads only E-PROJECT (`GET /api/v1/projects/{case_id}`).
- 404 and 403 show a no-access state that names nothing about the project (JR-08 failure). 401 shows the shell's signed-out callout.
- The contract mock gets `frontend/mock/projects.mjs` and its fixtures. In `server.mjs` the change is two ids appended to `M1_OPERATIONS`, one import and one dispatch line.
- The page shows only what the contract carries. Every board element without a contract field is left out (Out of scope) and listed in build.md for product acceptance.

## Context
- **Route today:**
  - `frontend/src/app/projects/page.tsx` renders `DestinationPage destination="projects"` (`frontend/src/shell/DestinationPage.tsx`). That component checks `useMe().destinations` and shows `NotOpenState` when `projects` is missing.
  - There is no `frontend/src/app/projects/[caseId]/` route.
- **Pattern to follow:** `frontend/src/app/my-work/page.tsx` → `frontend/src/features/my-work/MyWorkPage.tsx` and `MyWork.tsx`. The parts to copy as patterns are:
  - debounced search into the URL (`SEARCH_DEBOUNCE_MS = 300`);
  - the `psl-seg` "Rows per page" radiogroup with arrow keys;
  - the `psl-showmore` footer;
  - the phone query `(max-width: 719.98px)`;
  - ignoring late responses.
- **Detail page pattern:** `frontend/src/app/work/[id]/page.tsx` → `frontend/src/features/work-item/WorkItemView.tsx`. It has:
  - `useWorkItem` for loading, error and ready;
  - `SignedOutState` for 401;
  - `NoAccessState` (`WorkItemStates.tsx`) for 403 and 404;
  - `WorkErrorCard` for anything else;
  - a static `metadata.title` that never names the record.
- **API client:**
  - `frontend/src/api/client.ts`: `api.GET(...)` wrapped in `call()` returns the data or throws `ApiError`.
  - `frontend/src/api/errors.ts` maps 401 to `unauthenticated`, 403 to `forbidden`, 404 to `not_found`, anything else to `server`, and a network failure to `network`.
  - `frontend/src/api/schema.d.ts` already has `/api/v1/projects` (line 243) and `/api/v1/projects/{case_id}` (line 264), so no regeneration is needed.
- **Shared UI to import (read-only):**
  - from `frontend/src/shell/FrameStates.tsx`: `LoadingState`, `SignedOutState` and `NotOpenState`;
  - from `frontend/src/shell/`: `useMe` (`AppShell.tsx`), `DESTINATIONS` and `visibleDestinations` (`destinations.ts`), and `SampleLabel` (`SampleLabel.tsx`, hidden unless `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1`, architecture/sources/decisions-2026-11-14.md);
  - from `frontend/src/features/work-item/labels.ts`: `STATE_TAGS`, the CMP-05 words and tone for all 11 states, rendered as `psl-tag psl-tag--<tone>`;
  - from `frontend/src/features/my-work/icons.tsx`: `SearchIcon` and `CloseIcon`;
  - bundle classes in `frontend/src/styles/psl-bundle.css`: `psl-toolbar`, `psl-search`, `psl-input`, `psl-tablewrap`, `psl-table`, `psl-list`, `psl-crumb`, `psl-tabs`, `psl-tab`, `psl-empty`, `psl-callout`, `psl-seg` and `psl-showmore`;
  - from the shell: `shell-title`, `shell-errorcard` and `shell-reference`.
- **Mock:**
  - `frontend/mock/server.mjs`:
    - `M1_OPERATIONS` (line 24) gates the 501;
    - `createMockServer` loads `fixtures/<id>.json` for every M1 id except E-ME, so a new M1 id needs that file or the mock crashes at start;
    - the scenario cookie or header is applied before dispatch;
    - dispatch is at about lines 226-234.
  - The handler pattern to copy is `frontend/mock/work-list.mjs` (an `o<offset>` cursor, and 404 `invalid_query` for a bad limit or cursor).
  - Work-item fixtures `frontend/mock/fixtures/work/W-1002..W-1006.json` and `E-WORK-ITEM.json` (W-1001) hold these states: W-1001 waiting, W-1002 action_needed, W-1003 processing, W-1004 ready, W-1005 effect_uncertain and W-1006 verified, all on the "Prepare an invoice", "Record a receipt" and "Weekly client update" lines.
- **Generic mock test:** `frontend/tests/mock-contract.test.ts` loops over `M1_OPERATIONS`. For every persona (finance_lead, pm, none) it expects 200 with a schema-valid body, and for every declared error status it expects the scenario response. Path params it does not know become `X-1`, so `GET /api/v1/projects/X-1` must answer 200 for all three personas.
- **Existing assertions on /projects:**
  - `frontend/e2e/frame.spec.ts:238-241` expects an h1 "Projects" after menu navigation.
  - `frontend/tests/shell.test.tsx:217` renders `/projects` with a stubbed fetch that answers every request with the E-ME fixture. The new page must not break that test, so a non-list body must land in the error or loading state without throwing.
- **Records:** REC-CASE (`id: uuid`, kind project, title; "Visible only with a case.read grant"). Both endpoints need `case.read`, and "404 hides records the person may not see" (openapi description).

## Contract
The frontend and the mock both build against this. Field shapes come from `architecture/packages/v5/openapi.json`, are generated into `frontend/src/api/schema.d.ts`, and use `operations['E-PROJECTS']` and `operations['E-PROJECT']` types only, with no hand-written duplicates.

### E-PROJECTS · `GET /api/v1/projects` (list)
- **Request query:**
  - `q`: string, minLength 1, never sent empty;
  - `cursor`: string, minLength 1, from the last `next_cursor`;
  - `limit`: one of 10, 20 or 50; the frontend always sends it, default 20.
- **200:**
  - `{ items: [{ case_id, title, pm, stage, sample }], next_cursor?, as_of }`, with all five item fields required and `additionalProperties: false`;
  - no counts and no total;
  - `next_cursor` absent means this is the last page.
- **Errors** (`{code, message}`):
  - 401 → `SignedOutState pathname="/projects"`;
  - 403 → `NotOpenState` (no case.read anywhere);
  - 404, 5xx and network → the list error card (below).
- **Permission and tenant rule:**
  - The backend filters by grants (INV-ACCESS). The frontend shows exactly the rows returned and never filters, sorts or adds rows.
  - The page makes no request when `useMe().destinations` lacks `projects`, and shows `NotOpenState` with the first visible destination.
- **Idempotency and versioning:** a read only, with no writes and no CSRF. Rows keep server order. There is no polling (D-UPDATES names no project list cadence), and Try again and a new search re-read.
- **URL state:**
  - `/projects?q=<text>&limit=<10|20|50>`, with `q` omitted when empty and `limit` omitted when 20;
  - an invalid `limit` falls back to 20;
  - nothing is stored in localStorage, sessionStorage or cookies.

Fixture example (first page, finance_lead, `limit=10`):
```json
{ "items": [
    { "case_id": "P-0101", "title": "Lagoon Health · patient app", "pm": "Tunde Bello", "stage": "Release · UAT with client", "sample": true },
    { "case_id": "P-0102", "title": "Harbour Bank · mobile onboarding", "pm": "Kunle Ade", "stage": "Go-live · report sent", "sample": true }
  ],
  "next_cursor": "o10", "as_of": "2026-11-14T09:00:00Z" }
```

### E-PROJECT · `GET /api/v1/projects/{case_id}` (journey)
- **Request:** the path `case_id` is taken from the route segment and sent through openapi-fetch path params (encoded). It is opaque to the frontend.
- **200:**
  - `{ case_id, title, lines: [{ line, state, work_id }], next }`, all required;
  - `state` is one of the 11 enum values;
  - `lines` may be empty;
  - `next` is a non-empty string.
- **Errors:**
  - 401 → `SignedOutState pathname="/projects/<case_id>"`;
  - 403 and 404 → the project no-access state, with nothing from any response shown;
  - 5xx and network → the journey error card.
- **Permission and tenant rule:**
  - case.read is checked by the backend per record.
  - The page makes no request when `useMe().destinations` lacks `projects` (it shows `NotOpenState`).
  - The browser tab title is static `Project · PSL Factory`. It never contains the project title.
- **Idempotency and versioning:** a read only, with no polling and no writes.

Fixture example (P-0101, shortened):
```json
{ "case_id": "P-0101", "title": "Lagoon Health · patient app",
  "lines": [
    { "line": "Prepare an invoice", "state": "waiting", "work_id": "W-1001" },
    { "line": "Prepare an invoice", "state": "ready", "work_id": "W-1004" },
    { "line": "Prepare for release", "state": "owner_needed", "work_id": "W-1703" }
  ],
  "next": "Client UAT response, then Finance review of the milestone 2 invoice." }
```

### Screen states
**SCR-22 list** (`h1` "Projects", always present once the person is signed in and has the projects destination):

| State | What shows |
|---|---|
| Loading | `LoadingState` (role=status, skeleton). No rows from a previous view. |
| Default (1440) | Toolbar: search field (label "Search projects") and the text "N shown". `psl-tablewrap` table with columns PROJECT (title as a link to `/projects/<case_id>`), PM and WHERE IT IS (`stage` verbatim). Footer: the "Rows per page" 10/20/50 radiogroup, "Show more" while `next_cursor` is present, and "All N showing" when it is absent. Closing note: "You see projects your roles cover." |
| Default (390) | SCR-22-mobile: search, then a `psl-list` of cards. Each card is a link with the title, then "`stage` · PM `pm`". The same footer, with no horizontal page scroll. |
| Empty (no `q`, zero items) | `psl-empty`: "No projects you can see yet." / "You see projects your roles cover." |
| No results (`q` set, zero items) | `psl-empty`: "No projects match" with a "Clear search" button that removes `q`. |
| Show more fails | Loaded rows stay, plus `psl-callout psl-callout--problem`: "We couldn't load more. Nothing was changed." and Try again. |
| Error | `shell-errorcard` role=alert: "ERROR · COULDN'T LOAD", "We couldn't load your projects. Your work is safe; nothing was changed.", "Reference {code} for support." and Try again (re-reads the same view). |
| Signed out (401) | `SignedOutState` with `next=%2Fprojects`. |
| Not open (403, or no destination) | `NotOpenState`. |

**SCR-07 journey:**

| State | What shows |
|---|---|
| Loading | `LoadingState`. |
| Default (1440) | Breadcrumb `nav aria-label="Breadcrumb"`: "Projects" (link to `/projects`) / title (`aria-current="page"`). `h1` is the title. Project tab bar `nav aria-label="Project"` with one link, Journey, at `/projects/<case_id>` with `aria-current="page"`. "What is next" `psl-callout` holding `next`. A section heading "The whole journey", then an `ol` of lines in response order. Each `li` holds one link to `/work/<work_id>` containing the `line` text and the CMP-05 tag (`STATE_TAGS[state]`, `psl-tag psl-tag--<tone>`, one line, never wraps). |
| Default (390) | SCR-07-mobile: "← Projects" back link, title, the same tab bar (scrolls sideways if needed), "What is next", then stacked line rows with the tag under or after the line name. No horizontal page scroll. |
| Empty (`lines: []`) | Title, tab bar and "What is next" stay. In place of the list, `psl-empty`: "No work on this project yet." (STATES board wording). |
| No access (403/404) | `section` with `h1` "You can't open this project", a neutral "NO ACCESS" tag and the text "It belongs to work you don't have access to. Nothing about it is shown here, not even its name." It has a link "Back to projects" (`/projects`). No breadcrumb title, no tab bar, and none of the error body's `message` or `code`, so nothing echoes the server. |
| Error | `shell-errorcard`: "We couldn't load this project. Your work is safe; nothing was changed.", Reference {code} and Try again. |
| Signed out | `SignedOutState` with `next=%2Fprojects%2F<case_id>`. |

Sample: list rows render `<SampleLabel show={item.sample} />` next to the title, which renders nothing by default. The journey renders no record-level sample tag, because E-PROJECT carries no `sample` field. The frame's own `SampleLabel` is unchanged.

### Mock (`frontend/mock/projects.mjs`)
- **Export:** `projects({ operationId, url, persona })` returns `{ status, body }`.
- **`server.mjs` changes** (the whole edit):
  1. append `'E-PROJECTS', 'E-PROJECT'` to `M1_OPERATIONS`;
  2. add `import { projects } from './projects.mjs';`;
  3. add one dispatch line beside the E-WORK-LIST one:
     `if (route.operationId === 'E-PROJECTS' || route.operationId === 'E-PROJECT') { const r = projects({ operationId: route.operationId, url, persona }); return send(res, r.status, r.body); }`
  4. extend the header comment by one line.
- **Fixtures:**
  - `fixtures/E-PROJECTS.json` and `fixtures/E-PROJECT.json` are default bodies, required because `createMockServer` reads `fixtures/<id>.json` for each M1 id. `E-PROJECT.json` is the fallback journey for ids not in the list. `E-PROJECTS.json` is a valid one-page body.
  - `fixtures/projects/list.json` is `{ as_of, rows: [{ personas: [...], item: {case_id,title,pm,stage,sample:true} }] }`:
    - finance_lead sees at least 23 rows, so 10/20/50 give 3/2/1 pages;
    - pm sees 4 rows (PM Tunde Bello), all on one page;
    - none sees an empty list.
  - `fixtures/projects/<case_id>.json` holds the journey bodies.
- **Required cases:**
  - `P-0101` Lagoon Health · patient app (finance_lead and pm) covers all 11 states at least once. Every line whose `work_id` has a work fixture (`E-WORK-ITEM.json` = W-1001, or `fixtures/work/<id>.json`) has the same `line` and `state` as that fixture. The other lines use ids W-1701 and up, which have no fixture.
  - `P-0105` (finance_lead and pm) has `lines: []`.
  - `P-0102` is visible to finance_lead only, so pm gets 404.
  - `P-0099` is reserved no-access: 404 for every persona and never in any list.
- **Rules:**
  - E-PROJECTS filters the rows by persona, then `q` (case-insensitive substring of `title`), then pages with cursor `o<offset>` and `limit` (default 20).
  - An invalid `limit` or `cursor`, or an empty `q`, answers 404 `{code:"invalid_query", message:"We could not read that list request."}`.
  - E-PROJECT answers as follows:
    - `P-0099` returns 404 with `SCENARIO_BODIES[404]`'s body (`not_found` / "We could not find that record.");
    - an id in `list.json` that the persona cannot see returns the same 404;
    - an id in `list.json` that the persona can see returns its journey file;
    - any other id returns `fixtures/E-PROJECT.json`, matching the work-item fallback convention, so the generic contract test's `X-1` passes.
  - Every body is `sample: true` where the schema has `sample`, and validates against v4 (= v5) with the existing Ajv setup.

## Lanes
- **Frontend lane (builder)** owns:
  - `frontend/src/app/projects/page.tsx`, which replaces `DestinationPage` with the list. It keeps `metadata.title` "Projects · PSL Factory".
  - `frontend/src/app/projects/[caseId]/page.tsx`, with static `metadata.title` "Project · PSL Factory".
  - `frontend/src/features/projects/**`: the list, journey, tab bar (`ProjectTabs`, rendering only Journey and built so later features add entries), no-access state, hooks, view/URL helpers (for example `parseProjectsView` and `buildProjectsQuery`) and `projects.css`.
  - `frontend/mock/projects.mjs`, `frontend/mock/fixtures/E-PROJECTS.json`, `frontend/mock/fixtures/E-PROJECT.json` and `frontend/mock/fixtures/projects/**`.
  - The four-part `frontend/mock/server.mjs` edit described under Mock, and nothing else in that file.
  - New tests:
    - `frontend/tests/projects*.test.ts(x)`, which includes `projects-model.test.ts`, `projects.test.tsx` and `projects-journey.test.tsx`;
    - `frontend/tests/mock-projects.test.ts`;
    - `frontend/e2e/projects.spec.ts`.
- **Backend lane:** no work. `apps/`, `config/` and `templates/` stay untouched, and T-PROJECTS (real endpoints and grants) is separate.
- **Integration owner:**
  - Rebases the `server.mjs` edit over F-05, F-06 and F-08. Each lane only appends ids and adds its own dispatch line, so the merge is additive.
  - Confirms `tests/mock-contract.test.ts` still passes after all four lanes merge.
- **Shared files, owned elsewhere and not to be changed:**
  - `frontend/src/shell/**`, `frontend/src/api/**` and `frontend/src/styles/**` (F-01);
  - `frontend/src/features/work-item/**` (F-03) and `frontend/src/features/my-work/**` (F-02), which may be imported but not edited;
  - `frontend/mock/fixtures/work/**`, `E-WORK-*.json`, `E-TASK-*.json` and `me.*.json`;
  - `frontend/tests/mock-contract.test.ts`, `tests/shell.test.tsx` and `e2e/frame.spec.ts`. These should pass unchanged. If one truly must change, the edit is limited to its /projects assertion and listed in build.md.
  - `frontend/package.json`, the lockfile, `playwright.config.ts` and `vitest.config.ts`;
  - `architecture/**` and `design/**`;
  - the protected `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json`.
- **Ports:** app 3701, mock 3702.
  - E2E: `cd frontend && E2E_PORT=3701 MOCK_PORT=3702 npx playwright test e2e/projects.spec.ts`.
  - Dev: `cd frontend && MOCK_PORT=3702 npm run dev -- -p 3701`.

## Acceptance criteria
1. **List reads E-PROJECTS (JR-08 "open project").**
   - Behaviour: as finance_lead, `/projects` sends exactly one `GET /api/v1/projects?limit=20`. It shows h1 "Projects" and a table with the headers PROJECT, PM and WHERE IT IS, in that order. The rows appear in response order, each title links to `/projects/<case_id>`, and `stage` and `pm` are verbatim.
   - Verify: a component test with stubbed `fetch` checks the request URL, the header text, the row order and `href="/projects/P-0101"`. Also open http://localhost:3701/projects with the mock on 3702 and look.
2. **Only contract fields render.**
   - Behaviour: the list has no Active, Closed or "All I can see" tabs, no Filter button, and no Next milestone, Needs a person or Stopped columns. The journey has no PM or route sub-line, no facts strip, no per-line reference or detail line, no tab counts and no agent summary aside. A list response with only the five fields renders without any "undefined", "0" or "—" placeholders.
   - Verify: a component test asserting that the absence texts and roles are missing (`queryByRole('tab')` is null in the list, there is no button named Filter, and `textContent` does not contain "undefined"). The e2e screenshots go into build.md.
3. **Search.**
   - Behaviour: typing "lagoon" sends one request with `q=lagoon&limit=20` 300 ms after the last keystroke, and the URL becomes `/projects?q=lagoon`. Clearing the box sends a request without `q`. No request ever has an empty `q=`.
   - Verify: a fake-timer component test inspecting the request URLs.
   - Behaviour: with the mock, "lagoon" returns only P-0101, and "zzz" shows "No projects match" with Clear search, which restores the full list.
   - Verify: e2e at 1440.
4. **Paging (D-PAGING r2).**
   - Behaviour: as finance_lead at the default, 20 rows show, the text says "20 shown" and "Show more" appears. Clicking it sends `cursor=o20&limit=20` and appends the rest, then "All N showing" shows with no button. Choosing 10 in Rows per page sends `limit=10` with no cursor, shows 10 rows and sets `?limit=10`. A reload keeps 10. `/projects?limit=7` falls back to 20. Arrow keys move the radiogroup selection.
   - Verify: component tests with request inspection, and e2e on http://localhost:3701/projects?limit=10.
5. **Journey reads E-PROJECT and keeps order (JR-08 "see every line and what is next").**
   - Behaviour: `/projects/P-0101` sends `GET /api/v1/projects/P-0101`. It shows a breadcrumb with Projects / Lagoon Health · patient app, h1 "Lagoon Health · patient app", the tab bar with one link "Journey" (`aria-current="page"`), the "What is next" callout with `next` verbatim, and one `li` per `lines[]` entry in response order. Each line links to `/work/<work_id>`, and clicking the W-1004 line opens that work item.
   - Verify: a component test comparing the rendered order and hrefs with the stubbed body, and e2e clicking through to `/work/W-1004`, which shows its h1.
6. **State tags come from the enum.**
   - Behaviour: each of the 11 states renders `STATE_TAGS[state].text` in `psl-tag psl-tag--<tone>` (for example `owner_needed` → "Owner needed", person, and `followup_needed` → "Stopped: invoice follow-up needed"). The tag does not wrap (`white-space: nowrap`).
   - Verify: a table-driven component test over all 11 values. The mock test checks that P-0101 contains all 11.
7. **Journey empty.**
   - Behaviour: `/projects/P-0105` shows the title, tab bar and "What is next", plus "No work on this project yet.", with no `ol`.
   - Verify: a component test and e2e at 390 and 1440.
8. **No grant: 404 reveals nothing (JR-08 failure, INV-ACCESS).**
   - Behaviour: `/projects/P-0099` (any persona) and `/projects/P-0102` as pm show "You can't open this project" with "Back to projects". The page contains neither the requested case_id nor the error body's message, and there is no tab bar. `document.title` is "Project · PSL Factory". A stubbed 403 renders the same state.
   - Verify: a component test with 404 and 403 bodies whose `message` is "Lagoon Health secret" asserts that the text is absent. In e2e, check that `page.title()` and `body.innerText` do not contain "P-0099" and that P-0102's title is missing as pm.
9. **Wrong user, no section.**
   - Behaviour: with persona `none` (no `projects` destination), `/projects` and `/projects/P-0101` show "This section isn't open to your role." and send no E-PROJECTS or E-PROJECT request.
   - Verify: a component test counting fetch calls to `/api/v1/projects`, plus e2e with cookie `psl_mock_persona=none`.
   - Behaviour: as pm, the list shows exactly pm's 4 projects and never P-0102.
   - Verify: e2e.
10. **Signed out and refusals.**
    - Behaviour: a 401 on E-PROJECTS shows the signed-out callout with `next=%2Fprojects`, and a 401 on E-PROJECT shows it with `next=%2Fprojects%2FP-0101`. A 403 on E-PROJECTS shows `NotOpenState`.
    - Verify: component tests, plus e2e with cookie `psl_mock_scenario=401` set only after the frame has loaded, or `page.route('**/api/v1/projects*')`.
11. **Load failures (provider failure).**
    - Behaviour: a 500 or a network failure on either endpoint shows the matching error card with "Reference {code} for support." and Try again. Try again repeats the request and recovers. If Show more fails, the loaded rows stay and the inline problem callout shows. A malformed 200 (for example the E-ME body that `tests/shell.test.tsx` returns) does not throw an uncaught error.
    - Verify: component tests; e2e with `page.route('**/api/v1/projects*', r => r.fulfill({ status: 500, … }))`. `tests/shell.test.tsx` passes unchanged.
12. **Loading and stale responses.**
    - Behaviour: while a request is pending, `role="status"` loading shows with no old rows. A late response for an earlier `q` does not replace the current one, and a late journey response for a previous `caseId` is ignored.
    - Verify: a component test resolving two stubbed responses out of order.
13. **Sample label rule (INV-SAMPLE, 14 Nov decision).**
    - Behaviour: by default no `.psl-sample` renders on either page. With `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1` stubbed, each list row with `sample: true` shows exactly one SAMPLE DATA and a row with `sample: false` shows none.
    - Verify: a component test using `vi.stubEnv`.
14. **Mock honours the query and stays on contract.**
    - Behaviour:
      - For finance_lead and pm at limits 10, 20 and 50, following `next_cursor` to the end returns every visible row exactly once, with at most `limit` items per page. `none` gets `items: []`.
      - `q` narrows the results case-insensitively by title.
      - A bad `limit`, a bad `cursor` or an empty `q` gets 404 `invalid_query`.
      - P-0099 gets 404 for every persona, and P-0102 gets 404 for pm.
      - Every 200 and error body validates against the loaded openapi's E-PROJECTS or E-PROJECT schemas.
      - Every line whose `work_id` has a work fixture matches that fixture's `line` and `state`.
      - P-0101 covers all 11 states.
      - `tests/mock-contract.test.ts` passes unchanged with the two new M1 ids, and E-PROJECT-TAB and E-DOCUMENT still answer 501.
    - Verify: new `frontend/tests/mock-projects.test.ts`, and `npm test`.
15. **Accessibility (A-ACCESSIBILITY).**
    - Behaviour:
      - Axe (the WCAG 2.2 AA tags from `e2e/my-work.spec.ts`) reports no violations at 390×844 and 1440×900 for: the list default, no results, loading, error, journey default, journey empty, no access and not open.
      - There is no horizontal page scroll at 390.
      - Focus-visible outlines show on the search field, the rows-per-page options, Show more, row and card links, breadcrumb, Journey tab, line links and Back to projects.
      - Touch targets are at least 44px at 390.
      - With `reducedMotion: 'reduce'` nothing animates.
    - Verify: `cd frontend && E2E_PORT=3701 MOCK_PORT=3702 npx playwright test e2e/projects.spec.ts` with `timezoneId: 'Africa/Lagos'`. If this cannot run inside checks.sh, record the command and its output in build.md.
16. **Frame tests stay green.**
    - Behaviour: the menu navigation in `e2e/frame.spec.ts` still reaches an h1 "Projects", and `tests/shell.test.tsx` passes.
    - Verify: `npm test`, plus the e2e command above extended with `e2e/frame.spec.ts`.
17. **Product acceptance items are visible.**
    - Behaviour: build.md lists every omitted board element from criterion 2 (PMO-0-2), the Journey-only tab bar, and the server.mjs lines changed. It includes screenshots at 390 and 1440 of the list, the journey, the empty journey and no access.
    - Verify: build.md content.

## Out of scope
- The Milestones, Documents, Money, Registers and Actions tabs and their routes (E-PROJECT-TAB has no typed rows, PMO-0-1). Do not render them as disabled or "coming soon" tabs, and do not call E-PROJECT-TAB or E-DOCUMENT.
- **SCR-22 elements with no contract field:**
  - the Active / Closed / All I can see tabs and their counts;
  - the Filter button;
  - the Next milestone, Needs a person and Stopped columns, and the phone "2 need a person · 1 stopped" line;
  - a total such as "5 PROJECTS" (no total is returned; show only the loaded count).
- **SCR-07 elements with no contract field:**
  - the PM / route / "8 pieces of work across 6 lines" sub-line;
  - the six-cell facts strip;
  - per-line references (RFP-0031) and detail lines ("Station 2 of 5 · client UAT");
  - the CMP-02 and CMP-03 station bars (E-PROJECT has no station data);
  - "Awaiting Finance decision" wording (not in the enum);
  - Tola's summary aside and "Ask me about this project".
- Deriving any of the above on the client, for example counting lines by state to fill "waiting on people". Counts and status are the backend's (UI lead rule: derive from authorised records, with coverage stated).
- Polling or live refresh; sorting; filters; client-side grant checks beyond `useMe().destinations`.
- SCR-43 delivery overview, line screens, SCR-08 document review, and the SCR-12 drill-down (F-08).
- Backend T-PROJECTS and `apps/api`; the real API (FE-CONNECT-1); any openapi.json edit; repointing the mock or `gen:api` from v4 to v5; new npm dependencies.
- Editing shared components (`src/shell/**`, `src/api/**`, `src/features/work-item/**`, `src/features/my-work/**`) or other lanes' fixtures. If a shared component almost fits, wrap it inside `src/features/projects/`.
- A "SAMPLE DATA" tag other than `SampleLabel`, or any always-on sample banner.

## Assumptions
- Mock case ids are readable strings (`P-0101`), not uuids. The frontend treats `case_id` as opaque, so REC-CASE's uuid makes no difference to the UI.
- Ids that are not in `fixtures/projects/list.json` fall back to `fixtures/E-PROJECT.json`, mirroring the work-item fallback. The generic `mock-contract.test.ts` requests `X-1` and expects 200, and that file must stay unchanged.
- Appending to `M1_OPERATIONS` and adding the two top-level default fixtures is required by `createMockServer`'s fixture loader. Readiness PMO-0-3 allows the list append, so this stays within "an import plus one small branch".
- Lines that point at ids with no work fixture (W-1701 and up) open the default work item (W-1001) on the mock. This is a mock-only artefact that keeps `fixtures/work/**` untouched.
- 403 on E-PROJECT looks the same as 404 (no access). This copies `WorkItemView`, so a 403 never confirms that the project exists (INV-ACCESS). 403 on E-PROJECTS means no case.read at all, so `NotOpenState` is used.
- The heading is "The whole journey" without "oldest first". The contract fixes the order but carries no dates, so the page claims only what it shows.
- No polling. D-UPDATES r2 sets cadences for My work and the open work item only, and this page is a read the person refreshes.
- The empty list and no-results wording ("No projects you can see yet.", "No projects match") are not on a board. They follow the STATES rule "Empty says what will appear and why".
- The no-access wording adapts `NoAccessState` from the work item to a project. It drops "or amount" because the journey shows no amounts.
- On phones the state tag is shown on each line, although SCR-07-mobile shows a detail line there. The detail line has no contract field, and the tag is the only status available.
- Search matches only on title in the mock (readiness). How the real backend matches `q` belongs to T-PROJECTS.
- `limit` is always sent, even at the default 20. This makes requests explicit and testable, and the contract allows it.
