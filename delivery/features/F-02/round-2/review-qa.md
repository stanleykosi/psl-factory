VERDICT: PASS
COMMIT: 55e81940bdf715f222ebd7f15f26a9150d981915
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (frontend against the contract mock only)

## Summary
- Ran frontend/ at this head (copied from `git archive`, `next build`, `next start` on 3341) against the contract mock on 3342, with a Chromium session at 1440 and 390 wide, timezone Africa/Lagos. Stopped only those two ports afterwards.
- Every journey I drove passed: tabs and counts (24/12/6/2), tab switching with arrow, Home and End keys, search with debounce, Line and State filter with chips, Show more, rows per page 10/20/50 with reload, URL restore and invalid fallback, 15 s polling, failed refresh, load error with recovery, 401, pm empty state, pm unassigned 403, persona none, phone layout.
- Direct mock calls: paging to the end for every persona, queue and limit returns each row once with counts equal to totals. Both round-2 fixes are verified.
- NOT PROVED: this is UI against the mock only. No real Django API, real permissions, grants, payroll exclusion or real cursors were exercised. Row links to /work/[id] were checked for their href only (F-03 not merged). The F-02 and F-03 branches both edit `frontend/mock/server.mjs` at the same place; the coordinator resolves that at merge, and I did not test the merged result.

## Findings
- QA-2-1 | non-blocking | low | frontend | The mock accepts an empty `q=` (`GET /api/v1/work?queue=done&q=` returns 200 and ignores it), while the v3 contract says `q` has minLength 1. The UI never sends an empty `q` (checked: clearing the search box sent no `q`), so nothing breaks here, but the mock would hide that bug if the UI regressed. Source: `frontend/mock/work-list.mjs`.

## Verified
- UI-1-1 | verified | At 390x844 as finance_lead the first card, which has a short title ("Ikeja Retail · Planning budget"), shows the DO tag on its own line above the title, left-aligned, and the same for the DO and DECIDE cards below it (screenshot `.../scratchpad/qa/m1.png`). Document scrollWidth is 390, also with the filter sheet open. The tablist scrolls sideways (scrollWidth 535, clientWidth 356).
- TECH-1-2 | verified | `GET /api/v1/work?queue=unassigned` with cookie `psl_mock_persona=none` returns 200 `{"items":[],"as_of":...,"counts":{"needs_me":0,"waiting_on_others":0,"done":0}}`. In the browser, persona none on /my-work shows "No sections are open to your role yet." pm unassigned still returns 403 `queue_not_open`.

## Evidence
Scripts: `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/qa/qa.mjs` and `qa2.mjs`.

API (curl, mock 3342):
- finance_lead `queue=needs_me|waiting_on_others|done|unassigned&limit=20`: 20 (next_cursor `o20`) / 12 / 6 / 2 items; counts 24/12/6/2.
- pm needs_me: 0 items, counts `{0,3,2}` with no `unassigned`. pm unassigned: 403 "Only Leads can see unassigned work."
- Missing queue, `queue=bogus`, `limit=7`, `cursor=garbage`: 404 `invalid_query`. `X-Mock-Scenario: 401`: 401 `not_signed_in`. POST: 501.
- `q=zzz`: 0 items. `line=Prepare an invoice&state=action_needed&limit=50`: 2 items.
- Following next_cursor for finance_lead and pm, every queue, limit 10/20/50: each row exactly once, at most `limit` per page, total equals `counts[queue]` (21 combinations ok).

Browser, 1440 (finance_lead):
- Tabs "Needs me 24, Waiting on others 12, Done 6, Unassigned 2". First request `?queue=needs_me&limit=20`; 20 rows; footer "20 of 24 showing", "ROWS PER PAGE 10 20 50", "Show 4 more"; "24 ITEMS"; 22 SAMPLE DATA labels; first link `/work/W-1115`.
- Show more sent `cursor=o20`, gave 24 rows, "All 24 showing", no button, and focus moved to the first appended row link.
- Choosing 10 sent `limit=10` with no cursor, 10 rows, URL `?limit=10`; reload kept 10 rows.
- Tabs sent the right `queue`; URL gains `?queue=`. End selected Unassigned, Home selected Needs me.
- Search "lagoon": one request `q=lagoon`, 2 rows, "2 OF 24 ITEMS". Clearing sent a request with no `q`. "zzz" shows "No work matches" and "Clear filters", which restores 10 rows.
- Filter panel: Line and State only; Esc closes it and focus returns to Filter. Choosing Prepare an invoice and Action needed sent `line=Prepare%20an%20invoice&state=action_needed`; badge 2; two chips; "2 OF 24 ITEMS"; 2 rows. Removing the State chip and "Clear all" each reloaded without those filters.
- `?queue=done&q=lagoon&state=verified&limit=50` sent exactly those values. `?queue=bogus&limit=7&state=nope` sent `queue=needs_me&limit=20`. localStorage 0, sessionStorage 0, cookie holds only the mock persona.
- Polling: one further page-1 request after about 15 s. With the route forced to 500, the rows stayed (20) and the status read "Couldn’t refresh · updated 10:42". I did not test the hidden-tab pause by hand (component tests cover it).
- 500 on load: error card with "We couldn’t load your queue. Your work is safe; nothing was changed." and "Reference server_error for support."; after the route was restored, Try again showed 20 rows. 401: "You’re signed out. Sign in" with link `/accounts/login/?next=%2Fmy-work`.
- pm: tabs Needs me 0, Waiting on others 3, Done 2 (no Unassigned); "Nothing needs you right now" with "See what’s waiting on others", which switches to `?queue=waiting_on_others` with 3 rows. `?queue=unassigned` shows "This queue isn’t open to your role." with "Only Leads can see unassigned work." and "Go to Needs me" (`/my-work`), and no rows.

Not run by me: axe scans, the loading-state race test, focus-ring checks and the filter-panel Clear button; the builder's gate and e2e suite cover these (not re-run). Not exercised: the "Show more" failure callout and a 401 during a refresh.
