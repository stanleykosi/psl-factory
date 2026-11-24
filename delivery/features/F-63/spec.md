# My work on the live work list: eight tabs, counts, kind, station, reference and rows per page

> Tasks: FE-CONNECT-1 (part 2). Architecture: package v9, manifest sha256 `2c65b0325a160981658092dd9e4f0a189ece1eec2053e5bf24c8f5547fdc0a76`; live API 1.24.0+ (`contracts/psl-factory.openapi.json`, 1.26.0 on main; backend answers A-6 to A-10). Design: approved canvas version 1794454032-781f; screens: SCR-01 (`SCR-01-desktop`, `-mobile`, `-desktop-empty`, `-mobile-empty`, `-desktop-my-work`, `-mobile-my-work`, `-desktop-filter`, `-mobile-filter`, `-mobile-lead`), with D-182 and D-185 applied.

Start of build (from readiness): the builder runs `design.py check`, confirms FE-CONNECT-1 is approved in `architecture/model.json`, and confirms `src/features/work-list` is in its checkout. If any fails, stop and report.

## Summary
- `/my-work` reads the live `GET /api/v1/work` through the F-62 adapter (`src/features/work-list`), not the v7 `api` client. F-125's `isV7Row` guard and the v7 types in `src/features/my-work/model.ts` go away.
- Eight tabs on `queue=needs_me|waiting|mine|active|decisions|exceptions|unassigned|verified`, default `needs_me`. Tab counts and the "records you can see" total come from `GET /work/counts`; an unknown count is never shown as 0.
- Rows show kind tag (Decide/Do/Fix/Started), title, line title (from `lines[]`), reference, station with index, state tag with `status_label`, owner ("Unassigned" when null), start age and last update, and the sample flag.
- State filter (`state`), line, project and search; rows per page 10/20/50 sent as `limit`; "Show more" keeps asking past empty pages; coverage and "Updated hh:mm" shown honestly.
- Hidden and recorded as deviations: waiting-on filter, agent avatar, "While you're free", `payroll_questions`, `/role-dashboard` parts. The Unassigned tab body belongs to F-88.

## Context
- Screen: `src/app/my-work/page.tsx` renders `src/features/my-work/MyWorkPage.tsx` then `MyWork.tsx` (476 lines), `WorkRows.tsx`, `FilterPanel.tsx`, `CaughtUp.tsx`, `model.ts`, `my-work.css`. All of it reads v7 `E-WORK-LIST` with `api.GET('/api/v1/work')` (cursor, `waiting_on`, `counts`, `filters.lines`, `age_seconds`, `line_key`). F-125 added `isV7Row` so a live row shows the error card instead of crashing; D-182 left an interim `Verified outputs` link under the heading (`my-work__verified` in `MyWork.tsx`).
- Shared adapter (F-62, merged 15699653): `src/features/work-list/{types,useWorkList,coverage,labels,WorkListParts,index}`. `useWorkList({queue,line,q,project})` returns `{state,loadMore,retry,setFilters,filters}`; today it sends no `limit` and no `state`, ignores `total` and `total_coverage`, has no refresh. Helpers: `lineTitle`, `ownerText`, `stateTag`, `workHref`, `coverageNotes`, `shownText`, `LineFilter`, `WorkListError`, `WorkListFooter`, `WorkListLoading`. Types derive from `src/api/live-schema.d.ts` (`operations['work_queue']`, `operations['work_counts']`).
- Live contract: `GET /work` query `queue, line (26 keys), q (max 120), page (1..10000), project (uuid), limit (8|10|15|20|50), state (11 values), verified_month`. Row: `id` (int), `case_id`, `title`, `line` (key), `state`, `status_label`, `owner|null`, `sample`, `updated_at`, `started_at`, `reference|null`, `action_kind` (decide|do|fix|started|null), `station {key,index,count,name}|null`, `agent|null`, plus `verified_at`, `queue_output_url`, `exception_*` (not used here), `django_url`/`api_url` (never used). Page: `page, next_page|null, page_size, total|null, total_coverage (complete|incomplete), limited, evaluated, deferred[], lines[{key,title}], payroll_questions[]`.
- `GET /work/counts` (query `project, line, q, verified_month`): `{as_of, evaluated, limited, verified_month, queues[{key, observed, total|null}], lines[{key, needs_person, held, open, stopped, verified, verified_this_month, stations[]}]}`. `total` null means the server could not count everything; `observed` is what it did count.
- Other users of `GET /work`: `src/features/decide/DecideStates.tsx:420` reads v7 `queue=needs_me&limit=50`; `src/features/floor/stationWork.ts` imports `formatAge` from `my-work/model`; `tests/shell-live.test.tsx` renders `MyWorkPage`. Mock: `frontend/mock/live-work.mjs` serves live shape for `verified` and `exceptions` only; `frontend/mock/work-list.mjs` serves v7 for the rest.
- F-88 (lane C, INTEGRATED_QA, branch `fe-connect-1-received-rfp-assign-pm`) edits `MyWork.tsx`, `model.ts`, `tests/my-work.test.tsx`: the Unassigned tab body becomes `src/features/rfp/UnassignedBids` (received RFPs from `GET /received-bids/assignments`, not the work list), `assign` is a UUID in the URL, the search toolbar is hidden on Unassigned, and the F-36 assign panel, toast and notice are removed.

## Contract

### Reads (no writes on this screen)
Permission and tenant rule: the server decides. The page never reads roles; it shows what the API returns and maps 401 to the signed-out state, 403 to "This list isn't open to your role." (no retry; link "Go to Needs me" when not already there), 400/422/5xx/network to the error card with Try again. A failed read changes nothing and the card says so. Idempotent GETs, no versioning tokens.

**1. Rows: `GET /api/v1/work?queue=<q>&page=<n>&limit=<8|10|15|20|50>[&line=][&q=][&project=][&state=]`**
- Adapter change (additive, small, in `src/features/work-list`): `useWorkList` accepts `state` and `limit`; its ready state also exposes `total` (`number|null`), `totalComplete` (`total_coverage==='complete'`, true only then is `total` an exact count), `pageSize`, and `refresh()` (re-reads page 1 and merges, keeping rows loaded later, minus ids now on page 1, as `mergeRefresh` in `my-work/model.ts` does today). `WorkListFilters` gains `state?: WorkState`. A change of queue, line, q, project, state or limit restarts from page 1 (page numbers depend on the page size) and drops answers to earlier requests. Existing callers (Verified, Exceptions) are unchanged: no `limit` sent means the server default. If F-123 lands first with the same additions, reuse them and do not duplicate.
- "Show more" skips empty pages as the adapter already does (up to 10 requests, then `keep-looking`, button "Keep looking"). Empty state only when `next_page` is null and there are no rows.
- Never re-sort rows; de-duplicate by `id`.
- `refresh()` runs every 15 s while the tab is visible and at once on return when data is older than 15 s (D-UPDATES, `POLL_MS` today); a failed refresh keeps rows and shows "Couldn't refresh · updated hh:mm".

**2. Counts: `GET /api/v1/work/counts`** (new `useWorkCounts` in `src/features/work-list/useWorkCounts.ts`, exported from `index.ts`; F-123 may reuse it)
- Sent with no filter parameters, so tab counts are the person's whole queues, not narrowed by search. Re-read with each refresh.
- Tab count: `total` when not null; when `total` is null and `observed` > 0, show `observed+` with the accessible name "at least N" and the tab's coverage note; when `total` is null and `observed` is 0, show no number. A real `total` of 0 shows 0. A failed or pending counts read shows no numbers and the existing quiet "Count unavailable" note; the list still works.
- "Records you can see" (board: "46 records you can see · updated 10:42"): the sum of `lines[].open`. Read as exact only when `limited` is false; when `limited` is true write "at least N open records you can see". Fewer than all lines is never summed silently. See Question 2.
- Updated time: `as_of` of the list response, formatted with `formatClock` ("Updated 10:42", Africa/Lagos as today).

**3. Line filter options**: `lines[]` of the first page of the current queue (adapter `lineOptions`, kept while a filter is applied), through `LineFilter`'s data. A `line` in the URL that is not one of the 26 keys is dropped.

**4. Project filter options**: the live `GET /api/v1/projects` through `liveApi`, as `src/features/projects/ProjectsList.tsx` reads it (limit 50, first page). If it fails, only "Any project" is offered. The value sent is the project's `case_id` (uuid); a non-uuid `project` in the URL is dropped. The chip shows the project title, not the id, once the options have loaded.

**5. Unassigned (F-88)**: the tab body is `UnassignedBids` as F-88 builds it. F-63 does not request `GET /work?queue=unassigned` for the body. Its tab count comes from `/work/counts`. Visibility rule: the tab is drawn when the counts read lists `unassigned` with `total` > 0 or `observed` > 0, or when the URL already says `queue=unassigned` (then the server's answer for the body decides, including 403). See Question 1.

### URL
`/my-work?queue=&q=&line=&project=&state=&limit=&assign=`. Defaults are left out (`queue=needs_me`, `limit=10`). Invalid `queue` falls back to `needs_me`; invalid `state` or `limit` is dropped; `q` is trimmed and cut to 120 characters (the search input has `maxLength=120`). `waiting_on` and `cursor` are no longer read or written. `assign` keeps F-88's rule (UUID, only with `queue=unassigned`).

### Tabs
Order and words (Question 3): Needs me, Waiting on others, Started by me, Active, Decisions, Exceptions, Unassigned (when drawn), Verified. Phone: the same tabs in the scrolling strip (`Tabs strip`). `Verified` replaces the interim "Verified outputs" link (Question 5); `/verified` itself is unchanged.

### Row (desktop table SCR-01-desktop: WORK, WHERE ON ITS LINE, STATE, STARTED)
- WORK: kind tag from `action_kind` (Decide, Do, Fix, Started; `null` draws no tag), the title linking to `workHref(id)` (`/work/{id}`, never `django_url`/`api_url`), then `{line title} · {reference}` in mono (reference omitted when null; line title from `lines[]` via `lineTitle`, key as received if missing), and `SampleLabel` when `sample`.
- WHERE ON ITS LINE: `MiniStationBar` with `station.count` segments, current at `station.index`, text "Station {index} of {count} · {name}"; verified rows "All {count} stations done". Reuse `miniSegments`/`stationText` from `my-work/model.ts` (the `kind`-less station-only inputs). `station` null: the cell shows the `status_label` only, no bar.
- STATE: state tag (`stateTag`, 11 states, words from `STATE_TAGS`) with `status_label` as the secondary line when it differs from the tag words; under it the owner (`ownerText`). No agent avatar.
- STARTED: age from `started_at` ("2h", `formatAge` from seconds since `started_at`, computed from `as_of` not the browser clock), the full time in `title`, and "Updated {formatDayTime(updated_at)}" as a secondary line.
- Phone card (SCR-01-mobile): kind tag, title, start age top right, `CardBar`, state tag, owner as the note, sample label; the card is one link. Waiting-on-others phone cards (`SCR-01-mobile-my-work`) show title, state tag and owner.

### Screen states (every tab except Unassigned)
- Loading: skeleton and "Loading your queue…" (`WorkListLoading`); tab strip stays.
- Empty, Needs me, no search or filter applied: the caught-up view (`CaughtUp`). Heading "You're all caught up". Second line "{N} things you started are moving." only when the `mine` count is known (`total` not null); with an unknown count the line reads "Things you started keep moving." and never shows 0. Buttons: "Start work" (existing) and "See what you started" (goes to `queue=mine`). Groups "Where your work is" and "While you're free" are not drawn (no live source). Search bar hidden as today.
- Empty with search or filters: "No work matches" with "Clear filters".
- Empty on any other tab with no filters: "{tab-specific one line}" (e.g. "Nothing is waiting on others") and "New work will appear here."
- Error: card with "We couldn't load your queue. Your work is safe; nothing was changed." and "Last loaded hh:mm" when known; Try again.
- Success: rows, then `ShowMore` (rows per page 10/20/50, "Show more"), then the quiet coverage lines (`coverageNotes`: As of; "may be incomplete" when `limited`; "N more items are still being checked" from `deferred`).
- Result count above the list (`ListToolbar`): `total` complete: "{loaded} OF {total} ITEMS", or "{total} ITEMS" when all are loaded; `total` unknown: "{loaded}+ ITEMS" while more pages exist, else "{loaded} ITEMS". `ShowMore total` gets the number only when `totalComplete`.
- Filter panel (`MyWorkFilter`, CMP-22): Line, Project, State (11 live states), no Waiting on. The apply button reads "Show {N} items" when a one-page preview request (`limit=8`) with the draft returns a complete `total`, else "Show results". Chips for line, project and state.

### Fixture examples (mock must serve these; `frontend/mock/live-work.mjs`, `work-counts` handler, fixtures)
```json
// GET /api/v1/work?queue=needs_me&limit=10
{"items":[{"id":412,"case_id":"7d7c0c9e-2f0a-4c3e-9c61-0f6a8f1a2b11","title":"Harmattan Bank · M2 invoice","line":"finance-ledger/v1","state":"action_needed","status_label":"Review the draft","owner":"Ada Okafor","sample":false,"updated_at":"2026-11-24T09:40:00Z","started_at":"2026-11-24T07:00:00Z","reference":"INV-0412","action_kind":"decide","station":{"key":"decision","index":3,"count":5,"name":"Approval"},"agent":null,"verified_at":null,"queue_output_url":null,"exception_code":null,"exception_next_step":null,"exception_started_at":null}],
 "page":1,"next_page":null,"as_of":"2026-11-24T09:42:00Z","page_size":10,"total":1,"total_coverage":"complete","limited":false,"lines":[{"key":"finance-ledger/v1","title":"Finance ledger"}],"evaluated":12,"deferred":[],"payroll_questions":[]}
// GET /api/v1/work/counts
{"as_of":"2026-11-24T09:42:00Z","evaluated":46,"limited":false,"verified_month":"2026-11","queues":[{"key":"needs_me","observed":3,"total":3},{"key":"waiting","observed":2,"total":2},{"key":"mine","observed":9,"total":9},{"key":"active","observed":14,"total":14},{"key":"decisions","observed":1,"total":1},{"key":"exceptions","observed":2,"total":null},{"key":"unassigned","observed":0,"total":0},{"key":"verified","observed":28,"total":null}],"lines":[...]}
```
The mock also serves: an empty page with `next_page` set (then rows on the next page), `action_kind:null`/`station:null`/`reference:null`/`owner:null` rows, `limited:true` with `deferred`, counts with `total:null`, a counts 500, and 401/403 on `/work`. The persona with no work gets all-empty pages.

## Lanes
- **Frontend lane (A) owns:** `src/features/my-work/*` after F-88 has landed (`MyWork.tsx`, `WorkRows.tsx`, `FilterPanel.tsx`, `CaughtUp.tsx`, `model.ts`, `my-work.css`, `MyWorkPage.tsx`); the additive changes in `src/features/work-list/*` (`useWorkList.ts`, `types.ts`, `index.ts`) and the new `useWorkCounts.ts`; `frontend/mock/live-work.mjs`, its fixtures and the `GET /work/counts` handler in `frontend/mock/server.mjs`; tests `tests/my-work.test.tsx`, `tests/my-work-model.test.ts`, `tests/work-list.test.ts`, `tests/mock-work-list.test.ts`, `tests/shell-live.test.tsx` (only if it breaks), `e2e/my-work.spec.ts`, and any e2e that opens `/my-work` and breaks (list: `alerts-bell`, `ceo`, `decide-board`, `conformance`, `frame`, `demo`, `finance-month-end`, `hr`, `rfp-assign`).
- **Overlap with F-88 (lane C):** F-88 also edits `MyWork.tsx`, `model.ts` and `tests/my-work.test.tsx`; it is in INTEGRATED_QA so it should merge first. F-63 rebases on it, keeps `UnassignedBids` as the Unassigned body, the UUID `assign` rule, and the hidden toolbar on that tab, and does not touch `src/features/rfp/*` or `src/features/start-work/*` (F-88's). If F-63 reaches build first, it waits, or merges F-88's branch into its own and resolves in F-88's favour for those three behaviours. Never build both at once in the same files.
- **Backend lane:** none.
- **Integration owner:** the lane A coordinator runs the screen once against live Django (`PSL_DJANGO_UI=0`) with the test accounts live-none and live-lead (Unassigned tab and 403), and records what differed from the mock. Also decides how `src/features/decide/DecideStates.tsx:420` (v7 `queue=needs_me&limit=50`) is carried: F-63 does not edit `src/features/decide/*`; the mock keeps answering it in the v7 shape until its owner moves it (the mock tells the two apart by the v7-only `cursor`/`waiting_on` parameters being absent from live callers: the coordinator confirms the rule before the build). Exported helper `formatAge` stays exported from `my-work/model.ts` for `src/features/floor/stationWork.ts`.
- **Shared files:** `src/api/*` is not edited (types come from `live-schema.d.ts`; `src/api/schema.ts` belongs to the lane C coordinator). `src/shell/*` is not edited. `delivery/config.json` `protected_paths` unchanged.

## Acceptance criteria
1. Opening `/my-work` (signed in, mock or live) requests `GET /api/v1/work?queue=needs_me` and `GET /api/v1/work/counts`, and no request carries `cursor`, `waiting_on` or `counts` — verify: a network-mock test in `tests/my-work.test.tsx` asserts the requested URLs; `grep -rn "waiting_on\|E-WORK-LIST\|isV7Row" frontend/src/features/my-work` returns nothing.
2. The eight tabs appear in the order Needs me, Waiting on others, Started by me, Active, Decisions, Exceptions, (Unassigned), Verified, and each sends its live `queue` value (`needs_me`, `waiting`, `mine`, `active`, `decisions`, `exceptions`, `unassigned`, `verified`); `/my-work?queue=done` or `waiting_on_others` falls back to Needs me — verify: test clicks each tab and asserts the `queue` query; a URL test for the two old values.
3. A row shows kind tag, title linking to `/work/{id}`, line title from `lines[]`, reference, "Station 3 of 5 · Approval" with a mini bar, state tag, owner, a start age and "Updated" time — verify: page at 1440 and 390 with the fixture above; test asserts the link `href` is `/work/412` and no `django_url`/`api_url` appears in any `href`.
4. A row with `owner: null` shows "Unassigned"; `action_kind: null` shows no kind tag; `reference: null` shows no reference; `station: null` shows no bar and no "Station" text — verify: component test with those fields null; no "null", "undefined" or "0" text in the row.
5. Tab counts come only from `/work/counts`: `total` 3 shows 3; `total: null, observed: 2` shows "2+" with accessible name "at least 2"; `total: null, observed: 0` shows no number; a real `total: 0` shows 0; a failed counts read shows no numbers and "Count unavailable" while rows still load — verify: tests for the five cases; the page never renders a tab count from the list response.
6. "N records you can see" equals the sum of `lines[].open`; when `limited` is true it reads "at least N"; when counts are missing it is absent, never "0 records" — verify: tests with `limited` false/true and a counts 500.
7. Rows per page 10/20/50 sends `limit=10|20|50` on the next list request, restarts from `page=1`, and is kept in the URL (`limit=20`); 10 is omitted from the URL; `?limit=8` or `?limit=15` in the URL is dropped (not offered by the control) — verify: test selecting 20 asserts `limit=20&page=1` and the URL; test `?limit=15` requests with no `limit` or with 10.
8. State filter: choosing "Waiting" in the panel sends `state=waiting` (the 11 live values are offered, no Waiting on group), adds a "State" chip, restarts from page 1, and the chip removes it — verify: filter test; the panel contains no "Waiting on" text.
9. Search sends `q` (trimmed, max 120; the input stops at 120 characters), line sends `line=<key>`, project sends `project=<uuid>`; any change restarts at page 1 and drops late answers from the earlier request — verify: tests with a slow first response resolving after the second request; the older result never replaces the newer.
10. "Show more" on an empty page with `next_page` set keeps asking, up to 10 requests, then the button reads "Keep looking"; rows appear as soon as a page has any; no empty state shows while `next_page` is non-null — verify: tests with `[]`,`[]`,rows and with ten empties.
11. Result count: `total` complete shows "{loaded} OF {total} ITEMS"; `total: null` shows "{loaded}+ ITEMS" while more pages exist and never "OF"; `total_coverage: "incomplete"` is treated as unknown even if `total` is a number — verify: three test cases.
12. Coverage: `limited: true` shows "This list may be incomplete. Some work could not be checked yet."; `deferred` of 3 shows "3 more items are still being checked." and 8 shows "8 or more…"; "As of hh:mm" is always shown — verify: test using `coverageNotes`.
13. Needs me empty with no filters shows "You're all caught up", "Start work" and "See what you started" (goes to `?queue=mine`); the number of started things comes from the `mine` count and is replaced by "Things you started keep moving." when that count is unknown; there are no "Where your work is" groups, no suggestions and no `waiting_on` requests — verify: test with `mine` total 9 and with `total:null`.
14. Empty with a search or filter shows "No work matches" and "Clear filters", which clears q, line, project and state — verify: component test.
15. Wrong user: a 403 on the list shows "This queue isn't open to your role." with a "Go to Needs me" link (not on Needs me) and no Try again; 401 shows the signed-out state with `next=/my-work`; 500 and a network failure show the error card "We couldn't load your queue. Your work is safe; nothing was changed." with Try again and the support reference — verify: four tests; with live-none, `?queue=exceptions` or `unassigned` shows the closed state (live-none run, coordinator).
16. A failed counts read does not blank the list, and a failed list read does not blank the tabs — verify: two tests.
17. Wrong tenant and invalid input: `?project=not-a-uuid`, `?line=nope`, `?state=nope`, `?queue=nope` send no such parameter and the page loads Needs me; a `q` of 130 characters is cut to 120 — verify: URL-parse tests in `tests/my-work-model.test.ts`.
18. The Unassigned tab renders F-88's `UnassignedBids` and makes no `GET /work?queue=unassigned` request; it is drawn only when the `unassigned` count is above zero or the URL names it; `?queue=unassigned&assign=<uuid>` still opens F-88's drawer and the toolbar is hidden there — verify: tests from F-88 still pass unchanged; a new test asserts the request list.
19. The 15-second refresh re-reads page 1 and `/work/counts`, keeps rows loaded with Show more, and a failed refresh shows "Couldn't refresh · updated hh:mm" without removing rows — verify: fake-timer test.
20. The interim "Verified outputs" link under the heading is gone and the Verified tab opens the same list shape with `queue=verified`; `/verified` still works — verify: `grep -n "my-work__verified" frontend/src` returns nothing; `tests/verified.test.tsx` passes unchanged.
21. Existing `useWorkList` callers behave as before: Verified and Exceptions send no `limit` or `state` — verify: `tests/work-list.test.ts` and `tests/verified.test.tsx` pass; new adapter tests cover `limit`, `state`, `total`, `totalComplete` and `refresh`.
22. Keyboard and sample label: tab order is tabs, search, Filter, rows; after "Show more" focus moves to the first added row (as today); `SampleLabel` shows on sample rows — verify: tests kept from `tests/my-work.test.tsx`.
23. The mock serves the live shape for all eight queues, `limit`, `state`, `total` and `/work/counts`, and its tests pass — verify: `tests/mock-work-list.test.ts`; `npm run dev` mock at `/my-work` shows rows for each persona.

## Out of scope
- The waiting-on filter and chips, the agent avatar and agent names on rows, "While you're free" suggestions (BQ-21), the "Where your work is" groups on the caught-up board (they need `waiting_on`), `payroll_questions`, and a `/role-dashboard` heading, team decisions and approval desks. Deferred to a later feature.
- Assigning from the Unassigned tab, `AssignPmDrawer`, received bids (F-88).
- `/role-work` actions, `POST /work/{id}/...` writes, the work item page (lane C), `verified_month` and the Verified page changes, `exception_*` fields (F-123).
- Any change under `src/api/*`, `src/shell/*`, `src/features/decide/*`, `src/features/rfp/*`, `src/features/start-work/*`, or the protected paths. No backend change.
- `limit` 8 and 15 (valid for the API, not drawn by the board's control).
- Per-queue counts that follow the search or filters, a month filter, and any "N of M" claim beyond what the response marks complete.

## Conflicts with the boards
1. Tabs: the boards draw four (Needs me, Waiting on others, Done, Unassigned). The spec draws eight; `Done` becomes `Verified`; Started by me has a board (`SCR-01-desktop-my-work`) but Active, Decisions and Exceptions have none. Recommendation: build all eight as readiness says (Question 3).
2. "Age" column becomes "Started" with an "Updated" line under it (the board draws one age). Recommendation: keep both; the API gives the two times (A-10).
3. State cell: the board draws a "waiting on" phrase and an agent avatar; the spec draws the owner and no avatar. Recommendation: as specced.
4. "46 records you can see" is a sum of per-line open counts and may read "at least N"; the board draws a plain number. Recommendation: Question 2.
5. Waiting-on filter group and chips removed from `SCR-01-*-filter`. Recommendation: hide until the backend adds the parameter.
6. Caught-up boards (`SCR-01-desktop-empty`, `-mobile-empty`): "Where your work is" groups and "While you're free" panel removed; "9 things you started" becomes unknown-safe wording. Recommendation: as specced.
7. Rows per page and "Show more" follow the existing control; the board's "N of M items" can read "N+" or be absent. Recommendation: as specced.
8. A quiet coverage line ("As of…", "may be incomplete", "still being checked") appears under the list; no board draws it. Recommendation: as specced.
9. Station bar: drawn from `station.index/count`; absent when the row has none; the bar's "who holds it" colour comes from the state, not from an agent. Recommendation: as specced.
10. The interim "Verified outputs" link is removed because a Verified tab replaces it (Question 5). Recommendation: as specced.
11. The Unassigned tab list is F-88's (received RFPs) and not the board's work-row list; that conflict is F-88's to record.

## Questions for the design engineer
1. When does the Unassigned tab appear? (a) Recommended: when the person's `unassigned` count is above zero, or when the URL names it; the server's 403 decides the rest. A lead with nothing unassigned sees no tab until something arrives. (b) Always show it to everyone; people without access see "This queue isn't open to your role." (c) Hide it unless the first read succeeds (extra request).
2. "Records you can see" total. (a) Recommended: "{N} open records you can see" from the sum of per-line open counts, "at least N" when the server says the count is limited. (b) Drop the line and show only "Updated 10:42". (c) Add the queue totals (wrong: queues overlap).
3. Names for the three tabs the boards do not draw, and `Done`. (a) Recommended: "Started by me", "Active", "Decisions", "Exceptions", "Verified". (b) Use the backend's own words (`mine`, `active`...) in plain case. (c) Draw only the four board tabs plus Started by me and Verified; reach Active, Decisions and Exceptions from other screens.
4. The STARTED column. (a) Recommended: start age ("2h") with "Updated 10:20" in small text underneath. (b) Start age only. (c) Last update only, as the Verified list does.
5. Where Verified outputs lives now. (a) Recommended: the Verified tab replaces the interim link; `/verified` stays as its own page, not linked from here. (b) Keep both the tab and the link. (c) Make the Verified tab link out to `/verified`.
6. Tab count when the server cannot count everything. (a) Recommended: "12+" with the accessible name "at least 12". (b) Show no number. (c) "12" with a footnote.
7. The caught-up view without its "Where your work is" groups. (a) Recommended: heading, one sentence, Start work and See what you started, nothing else. (b) Fill the gap with the first rows of Started by me. (c) Show the board's groups with an "unavailable" note.

## Assumptions
- Tab counts are read without search, line or project, so a tab keeps showing the person's whole queue while the list is narrowed. Reason: the boards draw whole-queue numbers; the list's own `total` serves the narrowed count.
- "Records you can see" is the sum of `lines[].open`. Reason: A-233 defines the visible open total as the sum of line counts; no all-records total exists. The builder checks against the live API that `open` excludes `stopped` and `verified`, and if it does not, the coordinator asks the backend before the wording ships.
- Changing rows per page restarts from page 1. Reason: live paging is by page number and depends on `limit`.
- Start age is computed from `as_of`, not the browser clock. Reason: avoids a skewed clock changing the age.
- 8 and 15 are valid limits but not offered. Reason: the shared control offers 10, 20 and 50 and the boards draw those.
- The mock stays v7 for callers that send `cursor` or `waiting_on` until their owners move. Reason: `decide/DecideStates.tsx` is not in this feature's scope.
- The adapter additions (`state`, `limit`, `total`, `refresh`, `useWorkCounts`) are made in this feature unless F-123 lands them first. Reason: the screen needs them now; the surface stays small and documented in `index.ts`.
- The project and line filters are not shown on the Unassigned tab. Reason: F-88 hides the toolbar there.

## Coordinator note (engineering, 24 Nov)
- The decision desk reads the v7 `queue=needs_me&limit=50` shape (src/features/decide/DecideStates.tsx). F-63 does not edit it, and the mock keeps answering v7 callers on that path until F-64 or F-124 moves the decision desk. Confirmed by the lane A coordinator.
