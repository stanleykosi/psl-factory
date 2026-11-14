VERDICT: PASS
COMMIT: c4d0b05e5e25272eb9a66bf37cc0c390ba487c01
REVIEWER: reviewer-qa
AUTHORITY: integrated QA, round 2 (UI against the contract mock only; no real backend)

## Summary
- I tested the shared build of this head. The app runs from the f-06 worktree at c4d0b05 on http://localhost:3611, with the mock (`node mock/server.mjs`) on 127.0.0.1:3612. I used Chromium with the Africa/Lagos time zone, and curl.
- `e2e/exceptions.spec.ts` on this head: 16 passed (49 s). axe is clean for the default, empty, no-access and error states at 1440 and 390, and with the Filter popover open.
- A Lead can complete the whole journey: search, Filter, the "N OPEN" count, the paging bar, phone cards, opening a row's work item and coming back. Personas behave as specified: the Lead sees the list, PM gets the 403 "This list is for Leads" view with no search or Filter, and none gets the frame's no-sections state. Empty, 401, 404, 503, network failure, Show more failure and stale-answer handling also work.
- These results are UI-only. Search, Filter, "N OPEN" and the reference line use mock-only proposal fields (`q`, `what`, `open_count`, `ref`), which wait on architecture v7 (TECH-2-1, accepted by the coordinator). This is not INTEGRATED_QA_PASSED evidence for a real backend.
- I found no blocking problems and three non-blocking ones. The most important: when the rows-per-page choice changes, keyboard focus is lost. My work has the same problem.

## Findings
- QA-2-1 | non-blocking | medium | frontend | Keyboard focus is lost after a rows-per-page change or "Clear search and filter". `ExceptionsList.tsx:172` and `:249`: a radio change calls `setLimit`, and the hook (`useExceptions.ts:42`) sets `loading`. That replaces the body, including the paging bar, with `LoadingState`, so the focused radio is removed. Expected: focus stays on the chosen radio, so the arrow keys keep working (ARIA radiogroup pattern). Actual: after one ArrowLeft from "20", `document.activeElement` is BODY, a second ArrowLeft does nothing, and the next Tab lands on the first row link. A click on "10" and "Clear search and filter" (`:210`) also leave focus on BODY. My work (`/my-work`) behaves the same way, so this is a shared pattern and not new here. Fix both screens together: keep the loaded rows and bar mounted during a reload, or move focus back to the checked radio and the search box.
- QA-2-2 | non-blocking | low | frontend | Search and Filter are not kept when the person goes back. I searched "Northwind" (3 rows), opened /work/W-1503, then used browser Back. /exceptions showed 20 unfiltered rows and an empty search box. The spec does not require this, so it is a UX note: a Lead working through a narrowed list loses it after each row.
- QA-2-3 | non-blocking | low | frontend | The search box disappears while the list shows an error. `ExceptionsList.tsx:293` sets `searchable = state.status !== 'error'`. I searched "kora" and stubbed a 503: the error card appeared and the search box was gone, so the person cannot see or clear the search that failed. Try again reloads with the hidden "kora" and brings the box back with its text. Also, when a kind is chosen the Filter button's accessible name becomes "Filter 1" (the badge text). A visually hidden "kind selected" label would read better.

## Verified
- FID-1 | verified | The board elements are present and working on the shared build. Search applies through the API 300 ms after typing (`?limit=20&q=kora`, 3 rows, "3 OPEN"), and Enter applies at once (`q=INV-0405`, 1 row). Filter is a popover on desktop and a bottom sheet on phones (390 wide, from y=349). Esc and a click outside discard the draft without a request. Choosing Blocked sends `what=blocked`: 6 rows, all BLOCKED, "6 OPEN", a chip and a badge. Removing the chip reloads with no filter. The reference shows under the title (INV-0405). The phone shows "Exceptions · 25", "← Queue" and outlined cards (tag / title / doing). The paging bar sits below the table.
- TECH-2-1 (accepted, pending v7) | verified as accepted | Not retested against a real backend, because none exists. The mock honours `q`/`what`, and the page sends them on every request, including cursor pages.

## Evidence (exact steps and results)
- e2e, run on this head. Command: `cd /Users/Hunchoo/psl-factory-worktrees/f-06/frontend && npx playwright test -c <scratch>/qa.config.mjs`. The scratch config has `testDir` set to this worktree's `e2e`, `testMatch: exceptions.spec.ts`, `baseURL: http://localhost:3611`, Chromium, no `webServer`, and output in the scratchpad.
  - Result: 16 passed. These cover the default list plus Show more to 25, search and Filter, rows opening their own item, the work-item link on W-1005 only, cookie 401, list-only 401, 503 plus Try again, empty at 1440 and 390, no-access (pm and 404) at 1440 and 390, phone cards, phone tap-anywhere and phone Try again (44px).
  - Why I did not use the prescribed `E2E_PORT=3601 MOCK_PORT=3602` command: the repository config runs `npm run build` into the same `frontend/.next` that the shared 3611 server is serving (BUILD_ID rIpi87RpqGh6UueZL2tGc). That would break the shared build, and it breaks the no-build rule. The spec file and the build under test are the same head. No `frontend/test-results` was created.
- Direct API calls to http://127.0.0.1:3612/api/v1/exceptions, with the persona cookie:
  - Lead (finance_lead) results:
    - default: 200, 20 rows, `open_count` 25, `next_cursor` o:20
    - `limit=10`: 10 rows, o:10
    - `limit=10&cursor=o:20`: 5 rows, no cursor
    - `limit=7`: counts as 20
    - `cursor=nonsense`: gives the first page
    - `q=kora`: 3 rows
    - `q=kora&what=followup_needed`: 1 row
    - `what=blocked`: 6 rows
    - `what=bogus`: ignored (25 open)
    - `q=%'<script>`: 0 rows, 200
  - pm: 403 `{"code":"forbidden"}`, the same with `q=kora`. Through the app proxy on 3611, pm also gets 403.
  - none: 200 with `items: []`.
  - Cookie `psl_mock_exceptions=empty`: 200 with `items: []`.
  - `X-Mock-Scenario` header: 401 gives `not_signed_in`, and 404 gives `not_found`. 500 is ignored, because the operation does not declare it. That is expected, so I stubbed 500 and 503 in the browser instead.
- Browser, Lead at 1440:
  - The first request is `?limit=20`, and the page shows 20 rows.
  - Paging radio ArrowRight from 20 requests `?limit=50` and shows 25 rows. A click on 10 requests `?limit=10` and shows "Showing 10".
  - Show more requests `?limit=10&cursor=o%3A10` and shows 20 rows, with focus kept on Show more. On the last page Show more goes away.
  - Blocked at limit 10 requests `?limit=10&what=blocked` and shows 6 rows, with no Show more.
  - A search with no match shows "No exceptions match your search and filter." with no footer sentence. "Clear search and filter" restores the rows, clears the box and chip, and keeps limit 10.
- Opening a row and coming back:
  - The Northwind title opens /work/W-1503 (h1 "Northwind Clinics · Weekly client update"). It has one "See all exceptions" link and no buttons in main.
  - Back returns to /exceptions (see QA-2-2).
  - The "See all exceptions" link on /work/W-1005 returns to the list with 20 rows.
- Failures:
  - A 500 on the cursor page keeps 20 rows and shows "We couldn’t load more exceptions. Choose Show more to try again." Show more again gives 25 rows and the callout clears.
  - A 401 on the cursor page shows "You’re signed out." with Sign in to `/accounts/login/?next=%2Fexceptions`.
  - A 503 on a search shows the error card, and Try again gives 3 rows for "kora".
- Race: a "kora" answer delayed by 1.5 s, followed at once by "Northwind", ends on 3 Northwind rows and "3 OPEN". The stale answer was dropped.
- Keyboard, desktop Tab order: skip link, then the top bar (My work, Projects, Overview, Assistant, Setup), then the search box, Filter, and each title link in row order. Opening Filter with Enter puts focus inside the dialog. Esc returns focus to Filter. A 2px solid focus ring shows on the title link and on Show more (e2e).
- Phone 390:
  - The page shows "Exceptions · 25" and 20 cards. scrollWidth is 390.
  - The first card reads "SEND UNCERTAIN / Kora Logistics · Milestone 1 invoice / Chidi is checking for a delivery receipt by reference. Nothing resent."
  - Filter set to Setup needed gives "Exceptions · 5", 5 cards and a badge.
  - The rows-per-page radios are 44x44.
- Personas in the browser:
  - Lead: the list with search and Filter.
  - pm: the h1 and sub-line, then "This list is for Leads", with no search, Filter, rows, count or As of. "Go to My work" reaches /my-work.
  - none: the frame's "No sections are open to your role yet." The list is not reached.

## Notes
- QA-2-1 is listed as non-blocking because `/my-work` has the same behaviour and passed its own reviews. Fixing only this screen would make the two lists behave differently. Changing it is a frontend decision that covers both screens.
- I cover the compact embed (`ExceptionsList compact`) by unit test only (build.md AC13). No page mounts it yet; F-08 will.
- I left the shared servers on 3611 and 3612 running and started none of my own. I deleted my screenshots and scratch scripts.

## Unproved
- The real backend T-EXCEPTIONS: grant filtering, tenant scoping, real row order, real cursors, and real 401/403/404 behaviour. The mock's PM 403 and none-empty rules are mock choices.
- The proposal fields (`q`, `what`, `open_count`, `ref`) are not in architecture v4 to v6. If a backend ignores unknown query parameters, the list would look filtered while showing every row. If it rejects them, the list would fail (TECH-2-1, pending v7).
- Browsers other than Chromium. Real touch devices: I simulated phone taps with a mouse at 390 wide.
