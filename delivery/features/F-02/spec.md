# My work shows a person's queues, with search, filter, 10/20/50 rows and live refresh, against the contract mock

> Tasks: FE-MYWORK (R-MYWORK, R-VOLUME, R-SAMPLE, D-PAGING r2, D-UPDATES r2; acceptance A-MYWORK frontend half, A-ACCESSIBILITY). Architecture: package `architecture/packages/v3`, manifest.sha256 `2f74232fcac4f8fdd2cf0b4e61bf917863172c871890fb8331b61602fc3e04e5`, openapi.json info.version `9194e3567eb6`, base commit `6930181`. Design: canvas version 1794581312-b166 (design/review.json); screens: SCR-01 (artboards SCR-01-desktop, SCR-01-mobile, SCR-01-desktop-my-work, SCR-01-mobile-my-work, SCR-01-desktop-empty, SCR-01-mobile-empty, SCR-01-desktop-filter, SCR-01-mobile-filter, SCR-01-mobile-lead) and the shared STATES-desktop / STATES-mobile boards.

## Summary
- `/my-work` replaces the "not built yet" placeholder with SCR-01: queue tabs with count badges, a work list (table on desktop, stacked cards on phones), the list toolbar (search, Line and State filters, chips) and a footer with "Show more" and a 10/20/50 rows-per-page choice.
- The page reads only E-WORK-LIST (`GET /api/v1/work`) through the existing `api`/`call()` client. Queue, search, filters and rows per page live in the URL. It polls every 15 s while the tab is visible, and a refresh keeps the rows the person already loaded.
- The contract mock gains a small E-WORK-LIST handler (`frontend/mock/work-list.mjs`, wired into `server.mjs` with one branch) that honours `queue`, `q`, `line`, `state`, `cursor` and `limit` over a new per-persona row fixture. Every response stays schema-valid.
- It ships only what the v3 contract supports: no Project or Waiting-on filter, no agent avatar, no "records you can see" total, no "Awaiting Finance decision" or "Cancellation requested" wording, and none of the empty board's agent suggestions. Each omission is listed under Out of scope for the v4 revision.
- Product acceptance by the design engineer covers the rows-per-page control and its place in the list footer, and the filter panel shipping with Line and State only.

## Context
- **Route today:** `frontend/src/app/my-work/page.tsx` renders `<DestinationPage destination="my_work" />` (`frontend/src/shell/DestinationPage.tsx`), which checks `useMe().destinations` and shows a `.psl-empty` "This page is not built yet." The metadata title is `My work · PSL Factory`.
- **Frame:** `frontend/src/shell/AppShell.tsx` loads `/me` once and provides `useMe()`. It already handles the /me loading, 401, 403 and error states. `frontend/src/shell/FrameStates.tsx` exports `LoadingState`, `SignedOutState({pathname})`, `ForbiddenState`, `LoadErrorState` and `NotOpenState({first})`. `frontend/src/shell/destinations.ts` exports `visibleDestinations`. `frontend/src/shell/sample.ts` exports `SHOW_SAMPLE_LABEL`. `frontend/src/styles/shell.css` holds `.shell-title`, `.shell-errorcard`, `.shell-eyebrow`, `.shell-reference`, `.shell-errorcard__action`, `.shell-loading` and `.shell-skel` (the STATES patterns).
- **API client:** `frontend/src/api/client.ts` (`api`, `call()`), `frontend/src/api/errors.ts` (`ApiError` with `kind` of unauthenticated, forbidden, not_found, stale, invalid, server or network) and `frontend/src/api/types.ts`. `frontend/src/api/schema.d.ts` is generated from `architecture/packages/v2-reviewed/openapi.json`. The `/api/v1/work` path is byte-identical in v2-reviewed and v3 (checked), so the generated types are current. Do not repoint the generator or the mock.
- **Mock:** `frontend/mock/server.mjs` answers every M-1 operation with `fixtures[route.operationId]` and ignores the query. Scenarios (`X-Mock-Scenario` header or `psl_mock_scenario` cookie) are checked first and apply to every operation, `/me` included. `frontend/mock/fixtures/E-WORK-LIST.json` has three rows (W-1001 waiting/decide, W-1002 action_needed/do, W-1003 processing/started) and `counts` with `unassigned: 0` for every persona. `frontend/tests/mock-contract.test.ts` validates every M-1 operation × persona with Ajv, and requests E-WORK-LIST as `?queue=needs_me`.
- **Tests:** vitest (`frontend/vitest.config.ts`, `tests/**/*.test.{ts,tsx}`; component tests start with `// @vitest-environment jsdom`, as in `tests/shell.test.tsx`). Playwright and axe in `frontend/e2e/frame.spec.ts`. `frontend/playwright.config.ts` takes ports from `E2E_PORT` and `MOCK_PORT`.
- **Contract, E-WORK-LIST (v3 openapi.json `/api/v1/work` GET):** query `queue` is required, enum `needs_me|waiting_on_others|done|unassigned`. Also `q`, `line`, `state` and `cursor` (all strings, minLength 1) and `limit` (enum 10|20|50). The 200 body is `{items[], next_cursor?, as_of (date-time), counts?{needs_me, waiting_on_others, done, unassigned?}}`. Each item is `{id, title, line, reference, kind: decide|do|fix|started, state: ready|processing|waiting|owner_needed|setup_needed|action_needed|effect_uncertain|awaiting_reconciliation|verified|cancelled|followup_needed, station{index≥1, count≥1, name}, waiting_on, age_seconds≥0, sample}`. The endpoint declares 401, 403 and 404 with `{code, message}`. Permission: "Signed in; rows filtered by grants." `additionalProperties: false` everywhere.
- **Design sources:** `design/canvas/project/SCR-01-*.dc.html` and `STATES-*.dc.html`. Design-system READMEs in `design/system/project/components/` for WorkList, StateTag, MiniStationBar, Tabs, CountBadge, ListToolbar, Segmented, ShowMore, BottomSheet and Loading. Every class below is already in `frontend/src/styles/psl-bundle.css`.

## Contract

### C1. Request (frontend → E-WORK-LIST)
- Every request goes through `call(api.GET('/api/v1/work', { params: { query } }))`, with `query` built by one pure function `buildWorkQuery(view, cursor?)` in `frontend/src/features/my-work/`:
  - `queue`: always present.
  - `limit`: always present, 10, 20 or 50.
  - `q`: the trimmed search text. Omitted when empty after trimming; never `q=`.
  - `line`: the applied line, exactly as rows carry it. Omitted when none.
  - `state`: one value from the state enum. Omitted when none.
  - `cursor`: only on "Show more", the last response's `next_cursor`, passed through untouched.
- **URL ↔ view state** (`useSearchParams` + `router.replace`, no history entry per change; wrap the client component in `<Suspense>` so `next build` passes):

| URL param | values | default (param omitted) | invalid value |
|---|---|---|---|
| `queue` | needs_me, waiting_on_others, done, unassigned | needs_me | treated as needs_me |
| `q` | any text | none | empty → none |
| `line` | any non-empty text | none | — |
| `state` | state enum | none | not in enum → ignored |
| `limit` | 10, 20, 50 | 20 | anything else → 20 |

  Nothing is stored in localStorage, sessionStorage or cookies. A reload or a shared link restores the view. Cursors are never written to the URL; a reload starts at page 1.
- **Reload from page 1** whenever the queue, `q`, `line`, `state` or `limit` changes. The previous rows are dropped and the loading skeleton shows. A late response from an earlier view must never overwrite a newer one: abort it, or ignore it with a request sequence number.
- **Search:** debounce 300 ms after the last keystroke. Enter applies at once. Typing does not move focus.

### C2. Response handling
- **Tabs (CMP-06)** in this order: Needs me, Waiting on others, Done, then Unassigned **only when `counts.unassigned` is present** in the latest response. Each label is followed by `<span class="psl-badge">{count}</span>`; zero shows `0`. When the response has no `counts`, every badge shows `–` and the visible text "Count unavailable". The badge is never hidden and never reads 0 (unknown is not zero).
- **Rows** render in response order. The frontend never filters, re-sorts or re-derives `kind` from `state`; the board prototype's `kind()` function must not be ported.
- **Kind tag:** decide → `DECIDE`, do → `DO`, fix → `FIX` in `psl-tag psl-tag--person`; started → `STARTED` in `psl-tag psl-tag--neutral`.
- **State tag (CMP-05):** `<span class="psl-tag psl-tag--{family}">` with these exact words:

| state | words | family |
|---|---|---|
| ready | Ready to continue | person |
| processing | Processing | agent |
| waiting | Waiting | waiting |
| owner_needed | Owner needed | person |
| setup_needed | Setup needed | person |
| action_needed | Action needed | person |
| effect_uncertain | Effect uncertain | person |
| awaiting_reconciliation | Awaiting reconciliation | waiting |
| verified | Verified | done |
| cancelled | Cancelled | neutral |
| followup_needed | Stopped: invoice follow-up needed | person |

  A state value outside this table (only possible if the contract changes) shows its raw value in `psl-tag--neutral`. It never crashes the page.
- **Mini station bar (CMP-03):** `<span class="psl-mini"><span class="psl-mini__bar" aria-hidden="true">` with `count` `<i>` segments.
  - Segments before `index` get class `d`.
  - Segment `index` gets the state's class: person → `p`, agent → `a`, waiting → `w`, followup_needed → `s`, cancelled → none.
  - Later segments have no class.
  - For `verified`, every segment is `d` and the last is `v`.
  - The text in `psl-mini__text` is `Station {index} of {count} · {name}`, or `All {count} stations done` when verified. On phones the segments flex to the card width, as on SCR-01-mobile.
- **Age** from `age_seconds`: under 3600 → `{max(1, floor(s/60))}m`; under 86400 → `{floor(s/3600)}h`; otherwise `{floor(s/86400)}d`.
- **Sample:** a row with `sample: true` shows `<span class="psl-sample">SAMPLE DATA</span>` in its Work cell, after the line and reference. A row with `sample: false` has none.
- **As of:** next to the `<h1>My work</h1>` (`.shell-title`), mono text `Updated HH:MM` from `as_of`, in 24-hour time in the browser's time zone. For example, `2026-11-10T09:42:00Z` is `Updated 10:42` in Africa/Lagos.

### C3. Layout
- **Desktop (≥720px), SCR-01-desktop:**
  - Header: h1 and the updated text.
  - Tabs: `role="tablist" aria-label="Queues"`, built from `.psl-tabs` and `.psl-tab`.
  - Toolbar: `.psl-toolbar` with `role="search"`. It holds `.psl-search` with a labelled `input type="search"` (visually hidden label "Search", placeholder "Search work, client or reference"), then the Filter button (`psl-btn psl-btn--secondary` with the filter icon, `aria-haspopup="dialog"`, `aria-expanded`), then `.psl-resultcount`.
  - Chips row.
  - The list in `.psl-tablewrap > table.psl-table` with header cells Work, Where on its line, State and Age:
    - Work: kind tag, then the title as a Next `Link` to `/work/{id}`, then `{line} · <mono>{reference}</mono>`, then the sample label.
    - Where on its line: the mini bar.
    - State: the state tag, with `waiting_on` beneath it.
    - Age: the age.
  - Footer.
- **Phone (<720px), SCR-01-mobile:**
  - Tabs scroll sideways and never wrap.
  - The search box sits beside a 44px icon-only Filter button (`psl-iconbtn`, `aria-label="Filter"`, showing the count badge when filters are on).
  - Rows are a `<ul>` of cards. Each card is one link to `/work/{id}` and contains:
    - kind tag and title on the left, age on the right;
    - the mini bar at full width;
    - the state tag and the station text;
    - `waiting_on`;
    - the sample label.
- **Tabs keyboard:** roving tabindex. Left and Right arrows move between tabs and select, and Home and End jump to the first and last tab. The selected tab has `aria-selected="true"` and `aria-controls` pointing to the list region (`role="tabpanel"`, `aria-labelledby` the selected tab).
- Feature CSS goes in `frontend/src/features/my-work/my-work.css`. It uses token variables only, has no literal colours, does not restyle any bundle or shell class, and switches layout at 720px.

### C4. Toolbar, filters and chips (CMP-22)
- **Filter panel.**
  - Desktop: a `.psl-pop` with `role="dialog"` and `aria-label="Filter"`, under the Filter button.
  - Phone: a `.psl-sheet` bottom sheet with grab, head "Filter" and a close button, over a `var(--scrim)` backdrop. The footer button is `psl-btn--xl psl-btn--block`.
  - Both hold:
    - **Line:** radio group (`.psl-radio`). The first option is "Any line", followed by the distinct `line` values in the rows loaded for the current view, plus the applied line if it is missing from them, sorted A–Z.
    - **State:** a native `<select class="psl-input">` labelled "State". It offers "Any state" and then the 11 states in table order, with the CMP-05 words as labels and the enum values as option values.
    - **Footer:** "Clear" (resets the draft to Any and Any) and "Show results" (applies the draft, closes the panel and reloads).
  - Esc, the close button or a click outside discards the draft. Focus moves into the panel when it opens and returns to the Filter button when it closes.
- **Filter count badge:** the number of applied filters (line and state; search not counted) in `psl-badge psl-badge--signal` inside the Filter button. Hidden at 0.
- **Chips:** `.psl-chip` with `<span>Line</span><strong>{line}</strong><button aria-label="Remove Line filter">×</button>`, and the same for State, which shows the CMP-05 words. Then a `Clear all` text button (`psl-btn psl-btn--text`) that removes both filters (and leaves the search). Each removal reloads from page 1.
- **Result count** (`.psl-resultcount`, uppercase mono):
  - With no `q`, `line` or `state`: `{counts[queue]} ITEMS`.
  - With any of them and no `next_cursor`: `{loaded} OF {counts[queue]} ITEMS`.
  - With any of them and a `next_cursor`: `{loaded}+ OF {counts[queue]} ITEMS`.
  - When there are no `counts`: `{loaded}{+ if next_cursor} ITEMS`.

### C5. Footer: Show more and rows per page (D-PAGING r2; not drawn, product acceptance)
- Under the list, a `.psl-showmore` bar contains, left to right:
  - The shown text.
    - With no filters or search: `{loaded} of {counts[queue]} showing`. When there is no `next_cursor`: `All {loaded} showing`.
    - With filters or search: `{loaded} showing`. When there is no `next_cursor`: `All {loaded} showing`.
  - A Segmented control: `<div role="radiogroup" aria-label="Rows per page" class="psl-seg">` with three `psl-seg__opt` radios, 10, 20 and 50, under a visible mono label "ROWS PER PAGE". On phones it uses `psl-seg--phone` (44px).
  - While `next_cursor` is present, `psl-btn psl-btn--secondary psl-btn--sm`:
    - "Show {n} more", where n = min(limit, counts[queue] − loaded), with no filters or search;
    - "Show more" otherwise.
- On phones the bar wraps: the shown text, then the rows-per-page choice, then a full-width Show more.
- **Show more** sends the current view plus `cursor=next_cursor`, appends the items (skipping any id already shown) and takes the new `next_cursor`, `counts` and `as_of`. While it loads, the button is disabled with `aria-busy="true"`. Focus then moves to the first appended row's link. If it fails, the loaded rows stay and an inline `psl-callout--problem` reads "We couldn't load more. Your work is safe; nothing was changed." with a "Try again" button that retries the same cursor.
- The footer is not shown in the loading, error, empty or no-results states.

### C6. Staying current (D-UPDATES r2)
- A 15 000 ms interval runs only while `document.visibilityState === 'visible'`. It stops on `visibilitychange` to hidden. When the page becomes visible again and the last success is older than 15 s, it refreshes at once and restarts the interval. No poll starts while another request for the page is in flight.
- **A refresh** requests page 1 of the current view (same `limit`, no cursor) and merges:
  - The first-page rows are replaced by the new page in its order.
  - Rows the person loaded with Show more stay after them, minus any id now in the first page.
  - `counts` and `as_of` take the new values.
  - `next_cursor` stays the one from the last page loaded, unless only page 1 is loaded.
  - Focus, scroll position, the open filter panel and the search text are untouched.
  - No loading skeleton appears.
- **A failed refresh** keeps everything on screen. The updated text changes to `Couldn't refresh · updated HH:MM` (previous `as_of`) in a `role="status"` element, and the next tick retries. A 401 on refresh switches to the signed-out state.

### C7. Screen states (SCR-01 states and STATES boards)

| state | when | shows |
|---|---|---|
| loading | first load or any page-1 reload | tabs keep their last counts (or `–` before the first response); toolbar enabled; in place of the list, a `.psl-panel.shell-loading` with three `.psl-skel` row bars and `<span class="psl-loading" role="status">` "Loading your queue…". Old rows are never shown as current |
| default / my-work | 200 with items | C2/C3 |
| empty, Needs me | 200, no items, no q/line/state, queue needs_me | `.psl-empty`: `<h3>Nothing needs you right now</h3><p>New work will appear here.</p>`; plus, when `counts.waiting_on_others > 0`, a `psl-btn psl-btn--secondary` "See what's waiting on others" that switches to that tab |
| empty, other queues | 200, no items, no filters | `.psl-empty` heading: Waiting on others → "Nothing is waiting on others"; Done → "Nothing done yet"; Unassigned → "Nothing is unassigned". Body "New work will appear here." |
| no results | 200, no items, with q/line/state | `.psl-empty`: `<h3>No work matches</h3><p>Nothing in {queue label} matches your search and filters.</p>` + `psl-link` button "Clear filters" (clears q, line and state) |
| filter | panel open | C4 |
| lead-view | latest response has `counts.unassigned` | the fourth tab is present |
| error (401) | E-WORK-LIST 401 | the shell's `SignedOutState` with `pathname` `/my-work` |
| error (403) | E-WORK-LIST 403 | `.psl-empty`: `<h3>This queue isn't open to your role.</h3><p>{error.message}</p>`; when the queue is not needs_me, a link "Go to Needs me" to `/my-work` |
| error (404, server, network) | other failures | `.shell-errorcard role="alert"`: eyebrow `ERROR · COULDN'T LOAD`, "We couldn't load your queue. Your work is safe; nothing was changed.", `Reference {error.code} for support.` (plus `Last loaded HH:MM.` before it when an earlier response exists), and a "Try again" button that repeats the same page-1 request |

The tabs and toolbar stay rendered in every state except 401, so a person can change queue after an error.

### C8. Mock (E-WORK-LIST only)
- **New `frontend/mock/work-list.mjs`** exports `workList({ url, persona })`, which returns `{ status, body }`. It reads a new fixture, `frontend/mock/fixtures/E-WORK-LIST.rows.json`:

```json
{
  "as_of": "2026-11-10T09:42:00Z",
  "rows": [
    {"personas": ["finance_lead"], "queue": "needs_me",
     "item": {"id":"W-1001","title":"Lagoon Health · Milestone 2 invoice","line":"Prepare an invoice","reference":"INV-0412","kind":"decide","state":"waiting","station":{"index":4,"count":7,"name":"Finance review"},"waiting_on":"Finance Lead","age_seconds":7200,"sample":true}}
  ]
}
```

- **`server.mjs` change:** one branch after the scenario and CSRF checks, before the generic fixture return:

```js
if (route.operationId === 'E-WORK-LIST') { const r = workList({ url, persona }); return send(res, r.status, r.body); }
```

  plus its import. Scenario precedence is unchanged. `E-WORK-LIST.json` stays in place, unchanged, and stays loaded by the generic map.
- **Handler rules:**
  - Rows are filtered to the persona, then the queue, then `state` (exact), then `line` (exact), then `q` (case-insensitive substring of title, reference or line). They are sorted by `age_seconds` ascending, then by id.
  - `limit` defaults to 20. The cursor is opaque to clients; the mock may encode an offset, for example `o20`.
  - `next_cursor` is present only when more rows remain; it is never `null` or empty.
  - `counts` are computed from the persona's rows per queue, ignoring q, line and state. `unassigned` is present only for `finance_lead`.
  - Missing or unknown `queue`, a `limit` outside 10, 20 and 50, or an undecodable `cursor` → 404 `{code:"invalid_query", message:"We could not read that list request."}`. 404 is the only declared client error that fits.
  - `queue=unassigned` for a persona without `unassigned` → 403 `{code:"queue_not_open", message:"Only Leads can see unassigned work."}`.
  - Persona `none` gets 200 with empty items and zero counts (it never reaches the page anyway).
- **Fixture content** (all `sample: true`, all schema-valid):
  - `finance_lead`:
    - needs_me: 24 rows covering decide, do and fix only, including at least one `effect_uncertain`, one `owner_needed`, one `setup_needed`, one `ready` and one `followup_needed`, spread over at least 4 distinct lines.
    - waiting_on_others: 12 rows, all `started`, covering `processing`, `waiting` and `awaiting_reconciliation`.
    - done: 6 rows, including `verified` and `cancelled`.
    - unassigned: 2 rows.
  - `pm`: needs_me 0 rows (this gives the empty state), waiting_on_others 3 and done 2. No unassigned.
  - Keep W-1001, W-1002 and W-1003 exactly as in today's `E-WORK-LIST.json`. Use W-1004 (state ready), W-1005 (effect_uncertain) and W-1006 (verified) with those states for finance_lead, so rows link to F-03's fixtures. Other ids start at W-1101. Do not use W-1099.
  - No row has a line containing "payroll".

## Lanes
- **Frontend lane (builder)** owns:
  - `frontend/src/app/my-work/page.tsx`: swaps the placeholder for the My work page and keeps the `NotOpenState` check through `useMe()`.
  - `frontend/src/features/my-work/**`: components, `buildWorkQuery`, the state and kind maps, age formatting, the polling hook and `my-work.css`.
  - `frontend/mock/work-list.mjs`, `frontend/mock/fixtures/E-WORK-LIST.rows.json`, and the one import plus one branch in `frontend/mock/server.mjs`.
  - New tests: `frontend/tests/my-work*.test.ts(x)`, `frontend/tests/mock-work-list.test.ts` and `frontend/e2e/my-work.spec.ts`.
- **Backend lane:** no work. `apps/`, `config/` and `templates/` are untouched. T-MYWORK, including grants and the payroll exclusion, is a separate task.
- **Integration owner:**
  - Merges `frontend/mock/server.mjs` with F-03 (per-id E-WORK-ITEM and E-WORK-HISTORY) and F-04 (E-TASK-*). Each lane's change is a separate per-operation branch, so the merge is additive.
  - Confirms that W-1001 to W-1006 row ids and states agree with F-03's `fixtures/work/` files after the merge.
- **Shared files, owned elsewhere and not to be changed:**
  - `frontend/src/shell/**`, `frontend/src/api/**`, `frontend/src/styles/**` and `frontend/src/app/layout.tsx` are F-01. Import from them; do not edit them. If a change is truly unavoidable, keep it minimal and list it in build.md.
  - `frontend/mock/fixtures/E-WORK-LIST.json`, `E-WORK-ITEM.json`, `E-WORK-HISTORY.json` and `fixtures/work/**` (F-03).
  - `frontend/package.json`, `package-lock.json`, `playwright.config.ts` and `vitest.config.ts`.
  - `architecture/**`, `design/**` and the protected `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json`.
- **Ports:** app 3301, mock 3302. E2E: `cd frontend && E2E_PORT=3301 MOCK_PORT=3302 npx playwright test e2e/my-work.spec.ts`. Dev: `cd frontend && MOCK_PORT=3302 npm run dev -- -p 3301`.

## Acceptance criteria
1. **Queue tabs and counts (A-MYWORK).** As finance_lead, `/my-work` shows the tabs Needs me 24, Waiting on others 12, Done 6 and Unassigned 2, in that order, each count in a `.psl-badge`. — verify: open http://localhost:3301/my-work with the mock on 3302 and look. Add a component test with stubbed `fetch` asserting tab names, order and badge text equal to the response `counts`.
2. **Unassigned only when present (lead-view).** With the `pm` persona (cookie `psl_mock_persona=pm`) there is no Unassigned tab. A response whose `counts` omits `unassigned` renders three tabs, and a zero count shows "0". — verify: component test with two stubbed responses; e2e at 390px for finance_lead shows four tabs and the tablist scrolls sideways (`scrollWidth > clientWidth` on the tablist, `document.documentElement.scrollWidth <= 390`).
3. **Each tab requests its queue.** Clicking each tab sends `queue=needs_me|waiting_on_others|done|unassigned` with `limit=20`, and the URL gains `?queue=…`. Arrow keys move the selection. — verify: component test inspecting stubbed `fetch` request URLs and `window.location.search`; a keyboard test with ArrowRight, Home and End.
4. **Kinds come from the API (A-MYWORK).** Needs me shows only DECIDE, DO and FIX tags. Every one of the four kinds renders with its mapped tag and class. A row with `kind: "started"` and state `action_needed` shows STARTED, which proves kind is not derived from state. — verify: mock test that every finance_lead needs_me item has kind in {decide, do, fix}; component test on a crafted response.
5. **State words and colours.** Each of the 11 states renders the CMP-05 words and family class from the C2 table. — verify: table-driven unit test over the state map, plus a component test that the rendered `.psl-tag` text and class match.
6. **Station bar and age.** `{index:4,count:7,name:"Finance review"}` with state `waiting` renders 7 segments (3 `d`, the 4th `w`), the text "Station 4 of 7 · Finance review" and the bar `aria-hidden`. Verified renders "All N stations done". `age_seconds` 30 → `1m`, 7200 → `2h`, 86400 → `1d`. — verify: unit tests.
7. **Sample labels (R-SAMPLE).** Every row with `sample: true` shows SAMPLE DATA, and a row with `sample: false` shows none. — verify: component test counting `.psl-sample` inside the list against the number of sample rows.
8. **Row links.** Each title (desktop) or card (phone) links to `/work/{id}`. — verify: component test asserting `href="/work/W-1001"`.
9. **Search.** Typing "lagoon" sends one request with `q=lagoon` 300 ms after the last keystroke. Clearing the box sends a request with no `q` parameter, and no request ever contains `q=` with an empty value. A search with no match shows "No work matches" and Clear filters. — verify: fake-timer component test inspecting request URLs; e2e typing "zzz" at 1440px shows the no-results state.
10. **Filters.** Choosing Line "Prepare an invoice" and State "Action needed" in the panel, then Show results, sends `line=Prepare%20an%20invoice&state=action_needed`. The Filter badge shows 2, chips show both values, and the URL holds both. Removing a chip or using Clear all reloads without it. Esc closes the panel without applying and returns focus to Filter. There is no Project or Waiting-on control. — verify: component test, and the SCR-01 filter state at 390px (bottom sheet) and 1440px (popover) in e2e.
11. **Paging (D-PAGING r2).** At the default, the first request has `limit=20`. finance_lead Needs me shows 20 rows, "20 of 24 showing" and "Show 4 more". Clicking it sends `cursor=<next_cursor>`, shows 24 rows, then "All 24 showing" with no button. Choosing 10 in Rows per page sends `limit=10` without a cursor, shows 10 rows and sets `?limit=10` in the URL. A reload keeps 10. — verify: component test with request inspection; e2e on http://localhost:3301/my-work?limit=10.
12. **URL restore.** Opening `/my-work?queue=done&q=lagoon&state=verified&limit=50` sends exactly those values. Invalid values (`queue=bogus`, `limit=7`, `state=nope`) fall back to needs_me, 20 and no state. Nothing is written to localStorage, sessionStorage or document.cookie. — verify: component test, plus an assertion that the storage lengths are unchanged and the cookie string is unchanged.
13. **Polling (D-UPDATES r2).** With fake timers, a new page-1 request goes out at 15 000 ms while visible. None goes out while `document.visibilityState` is `hidden`. One goes out on return to visible after more than 15 s. — verify: component test stubbing `visibilityState` and dispatching `visibilitychange`.
14. **A refresh keeps loaded rows.** After Show more (24 rows) and focus on row 22's link, a poll whose page 1 changes row 1's state updates row 1 and keeps 24 rows. `document.activeElement` stays the same link, and no `role="status"` loading text appears. The counts and the updated time take the new values. — verify: component test.
15. **A failed refresh keeps the screen.** A poll that rejects (network) or returns 500 keeps the rows and shows "Couldn't refresh · updated 10:42". A poll that returns 401 shows the signed-out callout with `next=%2Fmy-work`. — verify: component tests.
16. **Empty (SCR-01-*-empty).** As `pm`, Needs me shows "Nothing needs you right now" and a "See what's waiting on others" button, which selects Waiting on others. — verify: e2e at 390px and 1440px with the pm cookie.
17. **Wrong role.** As `pm`, `/my-work?queue=unassigned` shows "This queue isn't open to your role." with the mock's message and a "Go to Needs me" link, and no rows. — verify: e2e, plus a mock test that the pm unassigned request returns 403 with a schema-valid error body.
18. **Load failures.** A 404, 500 or network failure on E-WORK-LIST shows the STATES error card ("We couldn't load your queue. Your work is safe; nothing was changed.", `Reference {code} for support.`, Try again). Try again repeats the request and recovers. A 401 shows the shell's signed-out callout. — verify: component tests with stubbed `fetch`; e2e uses `page.route('**/api/v1/work*')` to return 500 (not the scenario cookie, which would also fail `/me`).
19. **Loading.** While E-WORK-LIST is pending, skeleton bars and `role="status"` "Loading your queue…" show, with no rows from the previous view. A late response from an earlier view does not replace the current one. — verify: component test resolving two stubbed responses out of order; e2e holding the route open.
20. **Mock honours the query and stays on contract.** For each persona × queue × limit (10, 20, 50), following `next_cursor` to the end returns every row of that queue exactly once, and each page has at most `limit` items. `counts` equal the row totals. `q`, `line` and `state` narrow the results. Every 200 and error body validates against the v3 E-WORK-LIST schemas with the existing Ajv setup. The existing `tests/mock-contract.test.ts` still passes unchanged. — verify: new `frontend/tests/mock-work-list.test.ts`; `npm test`.
21. **Accessibility (A-ACCESSIBILITY).** Axe (WCAG 2.2 AA tags, as in `e2e/frame.spec.ts`) reports no violations at 390×844 and 1440×900 for default, filter open, empty (pm), no results, loading, error and lead-view. Focus-visible outlines show on tabs, Filter, chips, the rows-per-page options, Show more and row links. With `reducedMotion: 'reduce'` nothing animates. — verify: `cd frontend && E2E_PORT=3301 MOCK_PORT=3302 npx playwright test e2e/my-work.spec.ts`, with the browser context `timezoneId: 'Africa/Lagos'`. If this cannot run inside checks.sh, record the command and its output in build.md.
22. **Product acceptance items are visible.** build.md lists, with screenshots at 390px and 1440px: the rows-per-page control in the list footer, and the filter panel with Line and State only. — verify: build.md content.

## Out of scope
- **Absent from the v3 contract, so not built.** Each is listed for the v4 revision:
  - Project and Waiting-on filters; the multi-select Line checkboxes and "Show all 25 lines" (the contract has one `line` value and no line list) (PMO-0-1, PMO-0-2).
  - The agent avatar on rows (no agent flag) (PMO-0-3).
  - The "46 records you can see" total.
  - "Show N items" on the panel button (no count-only call).
  - The state words "Awaiting Finance decision" and "Cancellation requested" (not in the state enum).
  - The empty board's "Where your work is" groups, the "While you're free" agent suggestions, WhatsApp alert copy and its Start work button.
  - Verified rows showing a clock time ("09:12") instead of an age.
- Start work split button and drawer (CMP-23, FE-M2), and the floor tracks (CMP-08, FE-M3).
- The work item page `/work/[id]` (F-03), decisions (F-04), notifications, and All exceptions (SCR-10).
- Connecting to Django (FE-CONNECT-1) and any `apps/api` work, including T-MYWORK, grants and the payroll exclusion.
- Changes to openapi.json, new npm dependencies, changes to the scenario mechanism or personas, and repointing the mock or generator from v2-reviewed.
- Sorting controls, column choices, numbered pages, infinite scroll and saved views.
- Client-side filtering, sorting or role checks of any kind.

## Assumptions
- Line options come from the rows loaded for the view plus the applied line. This is the readiness Scope; the contract has no line list.
- Line is a single-choice radio group rather than the board's checkboxes, because `line` is one value.
- State is a native select with "Any state". The board draws a select; native keeps keyboard and screen-reader behaviour without a new component.
- The panel button reads "Show results", not "Show N items", because no count-only request exists.
- `counts` are treated as unfiltered queue totals, because D-PAGING says "counts per queue returned separately". This is why filtered counts read "N OF M" and "N+ OF M".
- The rows-per-page control sits inside the `.psl-showmore` footer as a Segmented radiogroup. Segmented's README covers short single choices, and the coordinator asked for placement under the list with "Show more".
- A refresh re-fetches page 1 only and keeps the rows loaded later. Cursors for later pages may be stale, and readiness forbids dropping rows the person loaded.
- On return to visibility, the page refreshes at once if the data is older than 15 s. "While visible" is read as: current when seen.
- A failed refresh shows a quiet note, not the error card. Replacing loaded work on a transient failure would be worse.
- State tags use CMP-05 sentence case ("Effect uncertain") rather than the board's uppercase sample strings. The StateTag README and DS preview use sentence case. Product acceptance can flip this.
- Kind tags use the person family for DECIDE, DO and FIX and the neutral family for STARTED, matching the colours on the board.
- Followup_needed uses the "stopped" bar segment and the person family. CMP-05 words: "Stopped: …".
- Phone cards show `waiting_on` on their own line, which the phone board leaves out. Readiness lists `waiting_on` on every row.
- Empty copy for Needs me is "Nothing needs you right now" (readiness and CMP-07), not the board's "You're all caught up". The body is "New work will appear here." without the alert promise, because notifications are not built.
- Copy for the other empty queues and the 403 view is written here, because no board covers them.
- The mock answers a malformed query with 404 `invalid_query`. 404 is the only declared client error that fits, and the frontend never sends one.
- The mock answers pm's `queue=unassigned` with 403. This gives a testable wrong-user case without inventing a role rule in the frontend.
- Times show in the browser's time zone. Tests pin Africa/Lagos, so 09:42Z shows as 10:42 as on the board.
- Search debounce is 300 ms, a common value; sources are silent.
- After Show more, focus moves to the first new row. This is accessible practice for appended content; sources are silent.
- URL changes use `router.replace`, so filtering does not fill the back-button history.
