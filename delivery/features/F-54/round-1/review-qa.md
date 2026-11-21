VERDICT: CHANGES
COMMIT: b73aff3f69fb0795c6c673fd301995b3a31c530a
REVIEWER: qa
AUTHORITY: integrated QA

## Summary
- Full e2e suite on this head, on my own ports (mock 4961, app 4962, production build): 1124 passed, 0 failed (26.6 min). The live dev server (4951/4952) was not touched.
- Driven by hand (Playwright against 4952 with the real mock): footer disabled states, grow to 50 then change queue, search or rows-per-page, failed Show more and failed rows-per-page, the assistant list retry, and the hr persona. All behave as specified except one: Projects does not use the total it receives (QA-1-1).
- Failed appends keep the rows shown and offer a retry. The assistant list has no footer, shows an inline retry, and loads the next page after retry.
- Not proved: Setup Rules and Templates and the project tabs by hand (only through the e2e); 74 rows (and 15) exist in no mock fixture, so the 15 and 74 cases were fabricated by intercepting the Projects response in the browser. The Rules and Templates fetch and reveal path has no real backend (contract mock only).

## Findings
- QA-1-1 | blocking | medium | frontend | Projects ignores the total it is given, so the footer cannot apply the "inactive" rule or show "10 of N". A list of 15 projects (response `total: 15`, `next_cursor` on page one) showed "10 showing" with 10 / 20 / 50 all enabled; 74 showed "10 showing" with the same three enabled. Expected (spec rules, D-137): "10 of 15 showing" with 50 disabled, and "10 of 74 showing". Cause: `usePagedRows` in `frontend/src/features/projects/ProjectsList.tsx:190` is not passed `total`, though `list.total` (line 151) and the `total` used for the result text (line 296) are already known. Same pattern should be checked on other lists whose response carries a total (project tabs, notifications, clients, exceptions return none, so they are right to say "N showing"). Without the fix, the only visible effect on today's mock is Projects with 15-20 rows; with the real backend any total in that range shows an option that adds nothing.
- QA-1-2 | non-blocking | low | frontend | When a larger rows-per-page choice fails to load (cursor request aborted), the footer marks 20 selected while 10 rows show, with "We couldn’t load more. Nothing was changed. Try again". The rows stay and Show more retries, so nothing is lost; only the selection state is ahead of the rows. Reproduced on /projects with the cursor request aborted (frontend/src/features/projects/ProjectsList.tsx, onSize -> navigate).
- QA-1-3 | non-blocking | low | backend (mock) | The hr stand-in persona (D-142) can open /exceptions by URL and the endpoint returns 25 rows for hr (`GET /api/v1/exceptions?limit=50` with `psl_mock_persona=hr`). The navigation offers only My work and Assistant, and Projects shows "This section isn’t open to your role", as asked, but Exceptions is not closed. D-142 says "empty queues"; what HR may see is PSL's to define (D-PAYROLL-VISIBILITY open), so this is only noted for the coordinator.

## Verified
- Fixes: none in round 1 (build.md `## Fixes` is None), so nothing to reproduce.
- Criterion 1: e2e `history draws Overview's header and column grid` passed in the full run (desktop and phone).
- Criterion 2/4: footer starts at 10 on Projects, Exceptions, My work, Clients (e2e). By hand: pm Projects (4 rows) "All 4 showing", 20 and 50 disabled; pm My work Waiting on others (3 rows) "All 3 showing", 20 and 50 disabled; finance Projects (22) 10 / 20 / 50 enabled (50 correctly active, 22 is above 20); My work (24 total) "10 of 24 showing", "Show 10 more".
- Grow in place: My work 50 shows "All 24 showing" and keeps `limit=50` in the URL; focus stays on the chosen 50 radio. Exceptions 50 -> 25 rows, then 10 -> 10 rows "10 of 25 showing" without a fetch.
- Filter after growing to 50: My work, switching to Waiting on others gave the correct 12 rows ("All 12 showing"), back to Needs me 24, search "Kora" 3 rows ("All 3 showing"). Projects, search "Kora" 1 row, clearing it 22 rows. The limit 50 is kept, rows are the filtered ones.
- Failed Show more (Projects, cursor request aborted): rows stay at 10, alert "We couldn’t load more. Nothing was changed. Try again"; the retry added rows (20). Failed larger rows-per-page: rows stay, same alert (see QA-1-2).
- Criterion 8: conversation list (25 synthetic conversations, window 1440x500): no `.psl-showmore` footer; the first page shows 10; scrolling the last into view with page 2 returning 500 keeps 10 rows and shows alert "Couldn’t load more. Try again" and a Try again button; retry loads 20. The e2e for scroll, last-row focus and the D-140/141 layout passed in the full run.
- hr persona: nav links are My work and Assistant only; /my-work shows 0 records and empty queues; /assistant shows "No conversations yet", Zainab only; /projects shows "This section isn’t open to your role. Go to My work".
- 15 and 74 rows: fabricated via browser route interception (see QA-1-1): no disabled options and no total on Projects. Unit tests for the 3 and 15 rows rule pass in the e2e/unit evidence in build.md; the real mock shows the 3-row rule working on pm.
