# Verified outputs and All exceptions read from live GET /work, through one shared work-list adapter

> Tasks: FE-CONNECT-1 (part 1). Architecture: package v9, live API 1.22.0 (`contracts/psl-factory.openapi.json`). Design: approved canvas as recorded in `design/screens.md`; screens: SCR-14 (`SCR-14-desktop`, `SCR-14-mobile`, empty) and SCR-10 (`SCR-10-desktop`, `SCR-10-mobile`, empty). Out: SCR-01 (F-63), recovery and correction writes.

Start of build (from readiness): the builder runs `design.py check` and confirms FE-CONNECT-1 is approved in `architecture/model.json`. If either fails, stop and report; do not build.

## Summary
- One adapter, `src/features/work-list/`, reads live `GET /api/v1/work` for any queue: page, next page, "show more" that skips empty pages, line titles from `lines[]`, coverage (`limited`, `evaluated`, `deferred`) and `as_of`. F-63 reuses it for My work.
- SCR-14 Verified outputs (new route `/verified`) lists `queue=verified`: title, line, owner, "Last updated", a link to the work item, and "Open output" through `output_url`.
- SCR-10 All exceptions (`/exceptions`, rebuilt on the adapter) lists `queue=exceptions`: state tag, "what is being done" (`status_label`), owner ("Unassigned" when null), "Last updated", link to the work item.
- Every board part the live list cannot fill is hidden, not invented and not shown as 0 (Facts earned, Proof, reference, kind chip, open count, "6 of 28", month filter). Each is listed under "Conflicts with the boards".
- Frontend only. No backend or contract change. The mock gains the live list shape for the two new queues so the screens run without Django.

## Context
- Live list: `GET /api/v1/work`, operation `work_queue` (`src/api/live-schema.d.ts`). Query `queue` (`needs_me|waiting|mine|active|decisions|exceptions|unassigned|verified`), `line` (the 26 line keys), `q` (max 120), `page` (1 to 10000), `project` (uuid). No `limit`. Response: `items[]` (max 8; `id` integer, `case_id`, `title`, `line` key, `state`, `status_label`, `owner` string or null, `sample`, `updated_at`, `django_url`, `api_url`), `page`, `next_page` (integer or null), `as_of`, `limited`, `lines[{key,title}]`, `evaluated`, `deferred[{id,url}]` (max 8), `payroll_questions[]`. Rows carry no `blocker`, `output_url`, reference, kind or total.
- `GET /api/v1/work/{work_id}` carries `output_url` (string or null), `blocker`, `next_step`.
- Today `src/features/exceptions/*` (`ExceptionsPage.tsx`, `ExceptionsList.tsx`, `useExceptions.ts`, `ExceptionsFilter.tsx`, `labels.ts`, `types.ts`, `exceptions.css`) reads the v7 `GET /api/v1/exceptions` with `api` and a cursor. `src/app/exceptions/page.tsx` is the route. There is no Verified page; the closest is the Done tab of `src/features/my-work/MyWork.tsx`, which stays on v7 until F-63.
- Reuse, by name: `liveApi` and `call` (`src/api/client.ts`), `ApiError` and `networkError` (`src/api/errors.ts`), `STATE_TAGS`/`StateTag`, `Tag`, `Table`, `ShowMore`, `usePagedRows`, `ListToolbar`, `FilterPanel`, `RadioGroup`, `EmptyState`, `PageTitle`, `SampleLabel`, `formatDayTime`, `useIsPhone` (`src/components`), `LoadingState`, `SignedOutState` (`src/shell/FrameStates`), `WorkErrorCard` (`src/features/work-item/WorkItemStates`).
- Work item link: `/work/{id}` with the integer `id` (as `rowHref` in `MyWork.tsx`); the route exists at `src/app/work/[id]/(item)/`. Lane C owns the work-item frame and expects exactly this form. Do not link to `django_url` or `api_url`.
- Mock: `frontend/mock/` (`server.mjs`, `fixtures/E-WORK-LIST.rows.json`, `exceptions.mjs`). v7 `GET /api/v1/work` uses `queue=done` and other v7 values; the two live-only queue values `verified` and `exceptions` are the switch for the live shape on the same path.

## Contract

### Adapter (`src/features/work-list/`)
Files: `types.ts` (types derived from `live-schema.d.ts`, no hand copies), `useWorkList.ts`, `coverage.ts`, `labels.ts`, `index.ts`.

`useWorkList({ queue, line?, q?, project? })` returns `{ state, loadMore, retry, setFilters, filters }`.
- `state`: `{status:'loading'}`, `{status:'error', error: ApiError}`, or `{status:'ready', items, lines, asOf, coverage, more}`.
- First load asks `page=1`. Any change of queue, `line`, `q` or `project` restarts from page 1 and drops answers to earlier requests (request counter, as `useExceptions.ts` does).
- Rows are shown in the order returned, never re-sorted, de-duplicated by `id`.
- `loadMore()` asks `next_page`. If the answer has no rows and `next_page` is not null, it asks again, up to 10 requests per click. If it stops at that cap with `next_page` still set, `more` is `'keep-looking'` and the button reads "Keep looking" (one more click asks 10 more). If `next_page` is null the list is complete and no button shows. `more` values: `idle | loading | failed | keep-looking | done`. A failed page keeps the rows already shown and offers "Try again".
- The first load applies the same skip: if page 1 has no rows and `next_page` is set, it keeps asking (same cap) before showing an empty state. Empty state shows only when `next_page` is null and there are no rows, with no coverage warning.
- Page size is the server's 8 and is not a setting: no rows-per-page control (A-8 reading).
- `lines`: titles come from the latest response's `lines[]` (key to title). A row whose `line` key is not in `lines[]` shows the key as received. The line filter lists `lines[]` of the first page of the current queue, kept while a filter is applied so a narrowed list can still be widened (A-9 reading).
- `coverage` is `{ limited, evaluated, deferredCount }`, taken from the latest page. `evaluated` is the count of work items the server looked at, not a total of rows and never shown as one.
- Errors: 401 gives the signed-out state (`SignedOutState`); 403 gives "This list isn't open to your role." (`EmptyState`, no retry); 400/422 and network show `WorkErrorCard` with Try again; nothing is changed by a failed read, and the card says so.
- Read only: no POST from either screen. The only extra read is `GET /api/v1/work/{id}` when a person chooses "Open output" (below).

Coverage text (one secondary line under the list, plus `as_of`):
- Always: "As of {formatDayTime(as_of)}".
- `limited` true: "This list may be incomplete. Some work could not be checked yet."
- `deferred` not empty: "{n} more items are still being checked." (n is `deferred.length`, at most 8; when 8, write "8 or more").
- Never "0 of N", never a total, never "0" for unknown. Result count in the toolbar reads "{rows loaded} shown" (and "so far" while `next_page` is set); it is hidden while loading.

### SCR-14 Verified outputs: route `/verified`
- Request: `GET /api/v1/work?queue=verified[&line=][&q=][&page=]`. Response as above.
- Heading "Verified outputs". Toolbar (CMP-22): search (`q`), Filter (line only), result count, removable line chip with Clear all; phone: search plus filter icon with bottom sheet.
- Desktop table columns: Output (title; `SampleLabel` under it when `sample`), Line (title from `lines[]`), Owner (`owner`, null shows "Unassigned"), Last updated (`updated_at` via `formatDayTime`, `<time dateTime>`), and an action cell. Never labelled "Verified at".
- Row actions: the title links to `/work/{id}`. "Open output" is a button: on press it reads `GET /api/v1/work/{id}`; if `output_url` is a string it opens it in a new tab (`rel="noopener noreferrer"`) and the read result is not cached for other rows; if `output_url` is null it shows an inline note on that row, "No output file is attached to this item yet. Open the item to see its records."; on read failure it shows "We couldn't open the output. Try again." on that row only. While reading, the button is busy and disabled (one read at a time per row).
- Phone: separate outlined cards (title, line, owner, "Last updated", Open output), title link over the card, as the SCR-10 cards do.
- Empty (`SCR-14-…-empty`): no rows and no `next_page`: `EmptyState` "Nothing has been verified yet." with the narrowed variant "No verified outputs match your search." and a "Clear search" button when `q` or `line` is set.
- Loading: `LoadingState` "Loading verified outputs…". Error: as the adapter.
- Fixture:
```json
{"items":[{"id":412,"case_id":"7d7c0c9e-2f0a-4c3e-9c61-0f6a8f1a2b11","title":"Invoice INV-0398 · Lagoon Health","line":"finance-ledger/v1","state":"verified","status_label":"Verified","owner":"Chidi Okafor","sample":true,"updated_at":"2026-11-23T10:20:00Z","django_url":"/work/412/","api_url":"/api/v1/work/412"}],"page":1,"next_page":null,"as_of":"2026-11-23T11:00:00Z","limited":false,"lines":[{"key":"finance-ledger/v1","title":"Finance ledger"}],"evaluated":1,"deferred":[],"payroll_questions":[]}
```

### SCR-10 All exceptions: route `/exceptions` (kept)
- Request: `GET /api/v1/work?queue=exceptions[&line=][&q=][&page=]`. Replaces the v7 `GET /exceptions` call. The server filters by the person's access; the page shows what it receives and never reads roles (INV-ACCESS).
- Heading "All exceptions", no open count.
- Desktop columns: What happened (state tag from `StateTag`, with "Last updated {time}" beneath instead of "since"), Work (title linked to `/work/{id}`), What's being done (`status_label`), Who acts (`owner`, null "Unassigned"). `action_needed` shows its existing tag word "Action needed" (the board's word; the old `blocked` kind mapped to it). `awaiting_reconciliation` and `effect_uncertain` use their own tags. The queue can also return other states (ready, waiting, verified, owner/setup needed, follow-up): each shows its own `STATE_TAGS` tag and is not hidden. The `StateTag` lookup must be exhaustive for every `state` value in the schema (typecheck fails on a new one).
- `blocker`: not on the row; not read. No per-row read for it.
- Phone: outlined cards (tag, title, `status_label`, owner and last updated on one secondary line), card title links to the item.
- Toolbar: search (`q`), Filter (line only), result count "{n} shown", chips. The kind filter and its `ExceptionsFilter.tsx` are removed.
- Empty (`SCR-10-…-empty`): "No exceptions right now." with the board's mascot/empty pattern via `EmptyState`; narrowed variant as SCR-14. Loading "Loading exceptions…". Error as the adapter.
- Fixture:
```json
{"items":[{"id":377,"case_id":"7d7c0c9e-2f0a-4c3e-9c61-0f6a8f1a2b11","title":"Invoice INV-0412 · Marina Bank","line":"finance-ledger/v1","state":"awaiting_reconciliation","status_label":"Checking whether the email was sent","owner":null,"sample":false,"updated_at":"2026-11-23T09:02:00Z","django_url":"/work/377/","api_url":"/api/v1/work/377"}],"page":1,"next_page":8,"as_of":"2026-11-23T11:00:00Z","limited":true,"lines":[{"key":"finance-ledger/v1","title":"Finance ledger"}],"evaluated":24,"deferred":[{"id":390,"url":"/work/390/"}],"payroll_questions":[]}
```

### Permission, tenant, idempotency
- Both pages need a signed-in session (`/me` as the shell already does). Access is by record, enforced by the server; a wrong user simply gets fewer rows or 403. No client role checks, no tenant argument sent. The `case_id` is never shown.
- All reads are GETs: no idempotency or revision concerns.
- `payroll_questions` are ignored on these screens (restricted payroll work is not listed here).

### Mock (`frontend/mock/`)
- `GET /api/v1/work` returns the live shape when `queue` is `verified` or `exceptions`, for every persona; other queues keep the v7 behaviour untouched (F-63 migrates them).
- Fixtures cover: more than 8 rows across 3 pages; a page 2 with no rows and `next_page` 3; `limited: true`; `deferred` not empty; `owner: null`; `sample: true`; a persona with an empty list; a persona answering 403 `queue_not_open` for exceptions; line and `q` filtering that can leave an empty middle page.
- `GET /api/v1/work/{id}` for fixture ids: one with `output_url` set, one with null, one 404.
- Remove the v7 `GET /exceptions` fixture only if nothing else imports it (`tests/exceptions-mock.test.ts` is rewritten for the new shape).

## Lanes
- Frontend lane (A) owns all of: `src/features/work-list/*` (new), `src/features/verified/*` (new: `VerifiedPage.tsx`, `VerifiedList.tsx`, `verified.css`), `src/features/exceptions/*` (rewritten onto the adapter), `src/app/verified/page.tsx` (new), `src/app/exceptions/page.tsx`, `frontend/mock/*` and the tests below.
- Backend lane: none. Integration owner: runs the screens once against live Django (`PSL_DJANGO_UI=0`, port 8000) and records what differed from the mock.
- Shared files: `src/api/*` is not edited (types are derived in `work-list/types.ts`). Navigation entry to `/verified` touches `src/shell/*` (lane A owns it): see Question 1; until answered, add no menu entry and reach the page by URL only. `src/features/work-item/*` belongs to lane C: not edited. F-63 imports `useWorkList` and the types from `src/features/work-list`; keep its export surface small and documented in a header comment.

## Acceptance criteria
1. `/verified` calls `GET /api/v1/work?queue=verified` (no other list call) and shows one row per returned item with title, line title, owner and "Last updated" — verify: run the mock, open `/verified` at 1440 px; the network log shows that one request; the column header reads "Last updated", and the words "Verified at" appear nowhere on the page.
2. `/exceptions` calls `GET /api/v1/work?queue=exceptions` and no longer calls `GET /api/v1/exceptions` — verify: network log on `/exceptions`; `grep -rn "api/v1/exceptions" frontend/src` returns nothing.
3. Line titles come from `lines[]`; a row whose key is missing from `lines[]` shows the key — verify: unit test of the adapter with both cases; page shows "Finance ledger", not `finance-ledger/v1`.
4. Rows keep the server order and 8 per page; no rows-per-page control exists on either page — verify: page with 3 mock pages shows 8 rows then "Show more"; no page-size control in the DOM.
5. "Show more" skips empty pages: with page 2 empty and `next_page` 3, one click adds page 3's rows — verify: adapter test (`tests/work-list.test.ts`) counts the requests (`page=2`, `page=3`); after more than 10 consecutive empty pages the button reads "Keep looking" and rows already shown stay.
6. A first page that is empty with `next_page` set does not show the empty state; it keeps asking until rows or `next_page: null` — verify: adapter test.
7. The empty state shows only when there are no rows and `next_page` is null — verify: persona with an empty list shows "Nothing has been verified yet." on `/verified` and "No exceptions right now." on `/exceptions`, desktop and 390 px; with a search that matches nothing the "No … match your search." text and "Clear search" show instead.
8. Coverage: `as_of` always shows; `limited: true` shows "This list may be incomplete…"; non-empty `deferred` shows the deferred count line; no total, no "of N" and no "0" appears anywhere for an unknown count — verify: component test over the two fixtures above plus `limited:false,deferred:[]` (only the as-of line); text search of the rendered DOM for " of " counts and "0 " finds none.
9. A null `owner` shows "Unassigned" on both pages; a present owner shows the name — verify: component test, both layouts.
10. Exceptions state tags: `action_needed` shows "Action needed", `awaiting_reconciliation` shows "Awaiting reconciliation", `effect_uncertain` shows "Effect uncertain"; a row of any other state in the queue is shown with its own tag, not dropped — verify: component test per state; `tsc --noEmit` fails if a state is removed from the lookup.
11. Each title links to `/work/{id}` with the integer id and never to `django_url` or `api_url` — verify: component test reads the `href` of every row and card; navigating from a row opens the work item route.
12. "Open output" on a verified row reads `GET /work/{id}` and opens `output_url` in a new tab with `noopener noreferrer`; when `output_url` is null the row shows the "No output file is attached…" note; when the read fails the row shows the retry message and the rest of the list is unchanged — verify: component tests with the three mock ids; only the pressed row changes.
13. Rows with `sample: true` show the sample label on `/verified` — verify: component test and page at 1440 px.
14. The line filter narrows with `line=<key>`, search sends `q`, and either restarts from page 1; a late answer from an earlier request does not replace newer rows — verify: adapter test with a delayed first response.
15. Errors: 401 shows the signed-out state, 403 shows "This list isn't open to your role." with no retry, a network or 5xx failure shows the error card with Try again and the text that nothing was changed; Try again reloads — verify: component tests per status (wrong user: mock persona with 403).
16. A failed "Show more" keeps the rows shown and offers "Try again" — verify: adapter test.
17. Phone (390 px): both pages show outlined cards with the title link over the card, search plus a filter icon opening a bottom sheet; no horizontal scroll — verify: Playwright or component test at 390 px; screenshot compared with `SCR-10-mobile` and `SCR-14-mobile`.
18. Desktop (1440 px) layouts match `SCR-10-desktop` and `SCR-14-desktop` for the parts kept; each hidden part (see conflicts) is absent, with no blank column, empty chip or "—" placeholder in its place — verify: screenshots at 1440 px; the design fidelity tool run once because the layout changes.
19. Nothing writes: neither page issues a POST/PUT/PATCH/DELETE — verify: network log on both pages while using search, filter, show more and open output.
20. The adapter's public surface (`useWorkList`, row and page types, `coverageNotes`) is exported from `src/features/work-list/index.ts` with no import from `features/exceptions` or `features/verified`, so F-63 can use it unchanged — verify: `grep -rn "features/exceptions\|features/verified" frontend/src/features/work-list` returns nothing; the adapter test passes `queue: 'needs_me'` and gets the same behaviour.
21. New tests exist and pass: `tests/work-list.test.ts` (adapter), `tests/verified.test.tsx`, `tests/exceptions.test.tsx` rewritten, `tests/exceptions-mock.test.ts` rewritten against the live shape, a mock test that the live shape is returned only for `verified` and `exceptions`, and that `queue=done` still returns the v7 shape — verify: `npm test` in `frontend/`.

## Out of scope
- SCR-01 My work and every non-`verified`/`exceptions` queue (F-63); the v7 Done tab stays as is.
- Corrections, reconcile, control and any other write; the work-item page and its history (lane C).
- Facts earned, Proof, reference, exception-kind chip and filter, open-exceptions count, "6 of 28" or any total, month filter, "since when" (the exception's start time), "Leads only" wording: hidden until A-37 to A-41 are answered. No extra per-row reads to fill them (no N+1 `GET /work/{id}`).
- Reading `blocker` or `next_step` for list rows.
- `project` filter control (the adapter accepts `project`; no screen draws a picker for it here).
- Backend, contract or `src/api/*` edits; changing `delivery/config.json` protected paths.
- Notifications, alerts, sign-in, any other screen.

## Conflicts with the boards
1. SCR-14 "Facts earned" and "Proof" columns: removed. Recommendation: hide until A-40 (rows carrying a one-line proof); the Open output button is the only proof path now.
2. SCR-14 reference ("INV-0398") under the title: removed (not in the live row).
3. SCR-14 "Verified at" column: relabelled "Last updated" (`updated_at` may not be the verification time).
4. SCR-14 "Verified · This month" filter and "6 of 28" count: removed; the toolbar shows "{n} shown".
5. SCR-14 gains an "Open output" button and a coverage/as-of line the board does not draw.
6. SCR-10 reference column and open-exceptions count in the heading: removed.
7. SCR-10 kind-of-exception filter chip and panel group: removed; the filter has the line only.
8. SCR-10 "since 11:02" becomes "Last updated"; "What's being done" shows backend wording (`status_label`), not the board's sentences; "Who acts" can read "Unassigned".
9. SCR-10 gains a coverage/as-of line, and shows non-exception states that the queue can return.
10. SCR-10 "Leads only" is not worded anywhere: access decides what is listed.
11. Both: rows-per-page choice removed (fixed 8); "Show more" can read "Keep looking".

## Questions for the design engineer
1. How do people reach Verified outputs? (a) Recommended: a "Verified" link under the My work heading area for now (a tab-style link to `/verified`; F-63 decides the final place), no top-bar change. (b) Add "Verified" to the top bar for everyone (shell change, the boards' top bar has no such item). (c) Leave `/verified` URL-only until F-63.
2. SCR-14 Facts earned and Proof columns, no data in the list. (a) Recommended: hide both and rely on Open output. (b) Show the column headers with "Open the item to see" text (clutter, a lie by omission). (c) Read each row's work item to fill them (up to 8 extra reads per page, slow, partial).
3. Heading counts "6 of 28" (SCR-14) and the open-exceptions count (SCR-10). (a) Recommended: show "{n} shown" only, plus "so far" while more pages exist. (b) Hide any count. (c) Count only the loaded rows and call it the total (wrong when more exist).
4. "Since 11:02" on exceptions becomes "Last updated". (a) Recommended: keep the board's position under the tag, wording "Last updated 11:02". (b) Drop the time from the tag cell and keep one "Last updated" column. (c) Keep the word "since" (misleading).
5. Exception kind filter chip. (a) Recommended: remove; line filter only. (b) Keep a state filter applied to loaded rows only (hides rows that exist on later pages). (c) Wait for A-38 before building the filter at all.
6. Coverage line ("may be incomplete", "n more items are still being checked") appears on both pages, not drawn. (a) Recommended: a quiet secondary line under the list. (b) A callout above the list. (c) Hide it (the list then looks complete when it is not).
7. Exception rows that are not exceptions (ready, waiting, verified) can come back on this queue. (a) Recommended: show them with their own tag. (b) Hide them on the client (the list then differs from what the server reports and the "shown" count undercounts). (c) Show a "Not an exception" tag.
8. `action_needed` tag word. (a) Recommended: "Action needed", the existing state-tag word and the board's. (b) "Blocked", the old v7 wording (no board draws it).

## Assumptions
- Route for Verified outputs is `/verified`: no route is named in the sources.
- Mock switches to the live shape on the two live-only queue values because v7 and live share the path `GET /api/v1/work`; v7 uses `done`.
- Empty-page skip cap is 10 requests per click; the sources give no number.
- Coverage and button wording ("may be incomplete", "Keep looking", "No output file is attached…") is proposed; no board draws it.
- "Open output" reads the item on press, not ahead of time, to keep to one list read per page and avoid N+1 reads.
- Result count text is "{n} shown" because no total exists (A-41, A-38).
- Line filter options come from the first page's `lines[]` for the current queue, because that is the only line list the live list returns.
- The `project` query is supported by the adapter but has no control on these screens; the boards list a project filter but no project list is part of this scope.
- "Unassigned" for a null owner is the readiness wording.
