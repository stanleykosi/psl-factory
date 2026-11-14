STATUS: READY
COMMIT: b6b4e25c64c758886df0b98151e9c67d52ccd039
BUILDER: builder
LANE: full

## Summary
- `/my-work` is now the SCR-01 My work page. It shows queue tabs with count badges (Unassigned only when `counts.unassigned` is present), a table on desktop and stacked cards on phones, a toolbar (search, Line and State filter, chips, result count) and a footer (shown text, 10/20/50 rows per page, Show more).
- The page reads only E-WORK-LIST through `call(api.GET('/api/v1/work'))`. Queue, `q`, `line`, `state` and `limit` live in the URL (`router.replace`); nothing is stored anywhere else. It polls page 1 every 15 s while the tab is visible and merges the result without dropping rows loaded with Show more.
- Every state in C7 is built: loading, default, empty (per queue), no results, filter, lead-view, 401, 403, and 404/500/network.
- The contract mock answers E-WORK-LIST from `mock/work-list.mjs` over a new per-persona fixture. One import and one branch were added to `server.mjs`. `E-WORK-LIST.json` is unchanged.
- Round 1: first build. No review findings yet.

## Changes
- `frontend/mock/work-list.mjs` (new): `workList({ url, persona })`. Filters by persona, queue, state, line and q; sorts by age then id; paginates with the opaque cursor `o<offset>`. Counts are unfiltered and include `unassigned` for finance_lead only. A malformed query returns 404 `invalid_query`; pm asking for unassigned returns 403 `queue_not_open`.
- `frontend/mock/fixtures/E-WORK-LIST.rows.json` (new):
  - finance_lead: needs_me 24 (decide/do/fix only, over 5 lines), waiting_on_others 12 (all started), done 6, unassigned 2.
  - pm: waiting_on_others 3, done 2.
  - W-1001..W-1003 are byte-equal to `E-WORK-LIST.json`; W-1004 is ready, W-1005 effect_uncertain and W-1006 verified. Other ids start at W-1101/W-1201. No W-1099 and no payroll lines.
- `frontend/mock/server.mjs`: the `workList` import plus one `E-WORK-LIST` branch after the scenario and CSRF checks. Scenario precedence is unchanged.
- `frontend/src/app/my-work/page.tsx`: renders `MyWorkPage`; the metadata title is unchanged.
- `frontend/src/features/my-work/`:
  - `model.ts`: types from `schema.d.ts`, `buildWorkQuery`, URL parse/write, CMP-05 state map, kind map, mini-bar segments, age/time formats, result-count, footer text and merge helpers. All pure.
  - `MyWork.tsx`: the page. It ignores responses for older views (sequence number), polls with visibility handling, debounces search by 300 ms, moves focus after Show more, and includes the tabs and footer.
  - `FilterPanel.tsx`: a desktop popover or phone bottom sheet. It edits a draft; Esc, close or a click outside discards it, and focus returns to Filter.
  - `WorkRows.tsx`: the desktop table and the phone cards.
  - `MyWorkPage.tsx`: the `useMe()` NotOpen check plus the `<Suspense>` boundary.
  - `icons.tsx`
  - `my-work.css`: tokens only, switches at 720px, adds `my-work__*` classes next to bundle classes.
- Tests (new):
  - `tests/mock-work-list.test.ts`: v3 schemas with Ajv.
  - `tests/my-work-model.test.ts`
  - `tests/my-work.test.tsx`: AppShell + page, stubbed `fetch` backed by the real mock handler, a navigation store mock.
  - `e2e/my-work.spec.ts`
- Not touched: `src/shell/**`, `src/api/**`, `src/styles/**`, `layout.tsx`, `architecture/**`, `design/**`, package/lock/configs, protected delivery files.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Tabs and counts: the component test asserts Needs me 24 / Waiting on others 12 / Done 6 / Unassigned 2 in `.psl-badge`. Seen on http://localhost:3301/my-work (mock on 3302), and checked by the e2e default test at 1440 and 390.
2. [x] Unassigned only when present:
   - The pm component test shows 3 tabs and `0` for Needs me.
   - A no-counts test shows `–` and "Count unavailable".
   - e2e at 390 (finance_lead) shows 4 tabs, tablist `scrollWidth > clientWidth`, and page `scrollWidth <= 390`.
3. [x] Each tab requests its queue: the component test clicks all four and checks `queue=…&limit=20` and `window.location.search`. The keyboard test covers ArrowRight, End, Home and ArrowLeft (wraps), with a roving tabindex.
4. [x] Kinds from the API:
   - A crafted response shows the 4 kinds with their mapped tags and classes.
   - `started` + `action_needed` shows STARTED.
   - The Needs me component test shows only DECIDE/DO/FIX.
   - The mock fixture test checks the kinds.
5. [x] State words and colours: a table-driven unit test covers all 11 states plus an unknown state (raw value, neutral). A component test renders all 11 and checks tag text and class.
6. [x] Station bar and age: unit tests show 4/7 waiting as `d,d,d,w,,,` with "Station 4 of 7 · Finance review", and verified as `All N stations done` ending in `v`. Ages: 30 → 1m, 7200 → 2h, 86400 → 1d. The component test checks `aria-hidden` on the bar.
7. [x] Sample labels: the component test checks that the `.psl-sample` count in the panel equals the number of sample rows, and that a `sample: false` row has none.
8. [x] Row links: `href="/work/W-1001"` on the desktop title. On phones the whole card is the link (component test).
9. [x] Search:
   - Fake-timer test: 4 keystrokes 100 ms apart, then exactly one `q=lagoon` request at +300 ms; focus stays in the box.
   - Clearing sends no `q`, and no request ever has an empty `q`.
   - Enter applies at once.
   - "zzz" shows "No work matches" + Clear filters (component and e2e at 1440/390).
10. [x] Filters:
    - The component test sends `line=Prepare%20an%20invoice&state=action_needed`, shows badge 2, chips "Line Prepare an invoice" / "State Action needed", and puts both in the URL.
    - Removing a chip, then Clear all, reloads without them.
    - Esc discards the draft and returns focus to Filter.
    - There is no Project or Waiting-on control.
    - e2e covers the bottom sheet at 390 and the popover at 1440.
11. [x] Paging:
    - The component test shows 20 rows, "20 of 24 showing" and "Show 4 more". Clicking it sends `cursor=o20`, shows 24 rows, "All 24 showing" and no button, with focus on row 21.
    - Choosing 10 sends `limit=10` with no cursor and sets `?limit=10`.
    - e2e on `/my-work?limit=10` shows 10 rows, keeps 10 after a reload, and Show more appends.
12. [x] URL restore: `?queue=done&q=lagoon&state=verified&limit=50` sends exactly those values. Invalid values fall back to needs_me, 20 and no state. localStorage/sessionStorage lengths and `document.cookie` are unchanged (component test).
13. [x] Polling (fake timers, stubbed `visibilityState`):
    - No request at 14 999 ms; one at 15 000 ms.
    - None during 60 s hidden.
    - An immediate one on return to visible, then the interval resumes.
14. [x] Refresh keeps rows: after Show more (24 rows) with focus on row 22, a poll that changes row 1 to verified and `needs_me` to 25 updates row 1 and keeps 24 rows. `activeElement` is unchanged, there is no `role=status`, and the badge reads 25 and the text "Updated 10:57".
15. [x] Failed refresh: network and 500 polls keep the rows, show "Couldn’t refresh · updated 10:42" in `role=status`, and the next tick recovers. A 401 poll shows the signed-out callout with `next=%2Fmy-work`.
16. [x] Empty (pm): "Nothing needs you right now" + "See what’s waiting on others" selects that tab and shows 3 rows (component and e2e at 390 and 1440).
17. [x] Wrong role: pm `?queue=unassigned` shows "This queue isn’t open to your role.", "Only Leads can see unassigned work.", a "Go to Needs me" link to `/my-work`, and no rows (component and e2e). The mock test checks the 403 body against the v3 schema.
18. [x] Load failures:
    - 404/500/network show the STATES error card with the exact four children; Try again repeats the same query and recovers (component).
    - "Last loaded 10:42." appears when an earlier response exists.
    - 401 shows the signed-out callout.
    - e2e uses `page.route('**/api/v1/work*')` returning 500.
19. [x] Loading:
    - Skeleton (3 `.psl-skel`) and status "Loading your queue…"; tabs show `–` before the first response.
    - A late needs_me response after switching to Done is ignored.
    - A page-1 reload drops the old rows and keeps the last counts.
    - e2e holds the route open.
20. [x] Mock: for each persona × queue × limit, following `next_cursor` returns every row exactly once with at most `limit` per page. Counts equal the totals; q/line/state narrow results. Every 200 and error body validates against the v3 `/api/v1/work` schemas (Ajv 2020, strict). The existing `tests/mock-contract.test.ts` passes unchanged.
21. [x] Accessibility:
    - Axe (WCAG 2.2 AA tags) shows no violations at 390×844 and 1440×900 for default/lead-view, filter open, empty (pm), no results, loading, error and 403.
    - Focus-visible rings are 2px solid on tabs, Filter, the chip remove button, the row link, the rows-per-page option and Show more.
    - With `reducedMotion: 'reduce'` there are no transitions and no running animations in main while loading.
    - Context `timezoneId: 'Africa/Lagos'`.
22. [x] Product acceptance items: screenshots from the e2e run (`test-results/`, copied to the paths below).
    - Rows-per-page control in the list footer:
      - 1440: /private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/f02-screens/my-work-1440.png (footer at the bottom: "20 of 24 showing · ROWS PER PAGE 10/20/50 · Show 4 more")
      - 390: /private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/f02-screens/my-work-390-footer.png (wraps: shown text, then rows per page, then full-width Show more)
    - Filter panel with Line and State only:
      - 1440 popover: /private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/f02-screens/my-work-1440-filter.png
      - 390 bottom sheet: /private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/f02-screens/my-work-390-filter.png
    - Also in that folder: the empty (pm) and error screenshots at both widths.
    - To regenerate: `cd frontend && E2E_PORT=3301 MOCK_PORT=3302 npx playwright test e2e/my-work.spec.ts`; PNGs land in `frontend/test-results/*/`.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-02 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exits 0:
  - Django check: no issues.
  - npm ci, lint (0 warnings) and tsc pass.
  - vitest: 9 files, 192 tests passed.
  - `next build` compiled, and `/my-work` prerenders.
- `cd frontend && E2E_PORT=3301 MOCK_PORT=3302 npx playwright test` (the whole suite, `npm run test:e2e` with the ports): 38 passed (1.0m). That is 14 new in `e2e/my-work.spec.ts` and 24 existing in `e2e/frame.spec.ts`, which still pass against the new page, including its axe runs on /my-work.
- Manual look: `MOCK_PORT=3302 npm run dev -- -p 3301`. I checked desktop default, filter applied, phone default, phone filter sheet and pm empty, then stopped only the 3301/3302 listeners.

## Notes for review
- Line choice and phone filter-button label:
  - The filter Line choice is a single-choice radio group (contract has one `line` value), as the spec's Assumptions say.
  - The phone filter button keeps `aria-label="Filter"` exactly as the spec states (the board used "Filter, 2 on").
- Phone panel and button styles:
  - The phone sheet holds Clear and Show results in its footer (the spec puts both in the footer; the board shows Clear in the sheet head).
  - "Show results" uses `psl-btn--dark`, as the boards draw it in ink.
- The `Updated HH:MM` text carries `role="status"` only while a refresh has failed, so the frame's "no status after load" checks still hold.
- When the selected queue has no tab (pm on `?queue=unassigned`), the tab panel is labelled "Unassigned" with `aria-label`, and the first tab takes the roving tabindex.
- The phone card mini-bar stretches through the feature classes `my-work__mini`/`my-work__minibar` set beside the bundle classes; no bundle or shell selector is restyled.
- Next dev printed "Generated AGENTS.md for AI agents"; no file appeared in the worktree (`git status` clean).
