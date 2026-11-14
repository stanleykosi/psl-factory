VERDICT: CHANGES
COMMIT: eab6dffa85a3636cea84a414ea5ca4b55ab90534
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (frontend against the contract mock only)

## Summary
- Built and ran frontend/ at eab6dff (copied with `git archive` into `scratchpad/qa3`, `next build`, `next start` on 3341, mock on 3342, Chromium at 1440 and 390 wide, timezone Africa/Lagos). Stopped only those two processes afterwards.
- All My work journeys from my earlier pass still pass on the combined head: tabs and counts (24/12/6/2), keyboard tab switching, search, filters and chips, Show more, rows per page, URL restore and invalid fallback, polling, failed refresh, load error and recovery, 401, pm empty state, pm unassigned 403, persona none, phone layout.
- Cross-feature journey: every row link W-1001..W-1006 opens its own work item page, and W-1099 shows the "NO ACCESS" page. But for W-1004, W-1005 and W-1006 the page that opens is a different item from the row clicked (different client, title and reference). W-1001, W-1002, W-1003 match. Cause is mock fixtures (QA-2-2).
- NOT PROVED: UI against the mock only. No real Django API, real permissions, cursors or payroll exclusion. Rows W-1101..W-1120 have no per-id fixture; the mock serves the default item for any unknown id.

## Findings
- QA-2-2 | blocking | medium | frontend | The list and the item page disagree for three of the six rows the mock shares. List row W-1004 reads "Lagoon Health · Milestone 1 invoice, INV-0405" but `/work/W-1004` shows "Lagoon Health · Milestone 3 invoice, INV-0419". List row W-1005 reads "Harmattan Bank · Go-live invoice, INV-0409" but `/work/W-1005` shows "Kora Logistics · Milestone 1 invoice, INV-0405". List row W-1006 reads "Kora Logistics · Milestone 1 invoice, INV-0399" but `/work/W-1006` shows "Delta Foods · Milestone 1 invoice, INV-0388". State and station do agree (Ready to continue / Effect uncertain / Verified). A person clicking the row lands on a different invoice, so the journey "open the matching item" fails in the mock. This is fixture data, not component logic, but the mock is the contract that both sides build to. Expected: the list row and `work/<id>` fixture describe the same title, reference and client for each id. Source: `frontend/mock/fixtures/E-WORK-LIST.rows.json` against `frontend/mock/fixtures/work/W-1004.json`, `W-1005.json`, `W-1006.json`.
- QA-2-3 | non-blocking | low | frontend | The mock answers an unknown id with the default item. `GET /api/v1/work/W-1007` with finance_lead returns 200 with `id: W-1001`, so any list row without a fixture (W-1101..W-1120, 18 of 24 rows on the first tab) opens W-1001's page under the URL of another id. Clicking W-1115 in the browser would show the wrong item the same way. A 404 for unknown ids (the mock already does that for W-1099) would catch this. Source: `frontend/mock/server.mjs` near line 68.
- QA-2-1 | non-blocking | low | frontend | Carried over from my earlier pass: the mock accepts an empty `q=` (returns 200 and ignores it) while the v3 contract says `q` has minLength 1. The UI never sends an empty `q`. Source: `frontend/mock/work-list.mjs`.

## Verified
- UI-1-1 | verified | Re-ran the phone check at 390x844 as finance_lead: document scrollWidth 390, also with the filter sheet open; tablist scrolls sideways (scrollWidth 535, clientWidth 356); first row link `/work/W-1115`.
- TECH-1-2 | verified | `GET /api/v1/work?queue=unassigned` with persona none returns 200 with empty items and zero counts; browser shows "No sections are open to your role yet." pm unassigned still returns 403 "Only Leads can see unassigned work."

## Evidence
Scripts (scratchpad): `qa/qa.mjs`, `qa/qa2.mjs` (My work journeys), `qa3/x.mjs` (cross-feature journey); screenshots in `qa3/shots/w-W-100x.png`. The scratchpad root is `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad`.

Cross-feature journey (finance_lead). I opened each queue with `limit=50`, clicked the row link, read the item page, then used Back.
- W-1001 (Needs me, "DECIDE Lagoon Health · Milestone 2 invoice, INV-0412, Station 4 of 7 Finance review, Waiting"): opens `/work/W-1001`, same title and reference, state WAITING, "04 Finance review: Needs a person". Match. Back returns to `/my-work?queue=needs_me&limit=50` with 24 rows.
- W-1002 (Needs me, "Harbour Bank · Receipt for INV-0398, RCP-0117, Station 2 of 5, Action needed"): opens the same item, ACTION NEEDED, "02 Match receipt: Needs a person". Match.
- W-1003 (Waiting on others, "Delta Foods · Weekly client update, WCU-0031, Station 3 of 5, Processing, Agent"): opens the same item, PROCESSING, "03 Draft update: Agent working". Match. Back returns to the waiting_on_others tab with 12 rows.
- W-1004 (Needs me, "Lagoon Health · Milestone 1 invoice, INV-0405, Ready to continue"): opens "Lagoon Health · Milestone 3 invoice, INV-0419", READY TO CONTINUE. Title and reference mismatch (QA-2-2).
- W-1005 (Needs me, "Harmattan Bank · Go-live invoice, INV-0409, Effect uncertain"): opens "Kora Logistics · Milestone 1 invoice, INV-0405", EFFECT UNCERTAIN. Mismatch (QA-2-2).
- W-1006 (Done, "Kora Logistics · Milestone 1 invoice, INV-0399, Verified"): opens "Delta Foods · Milestone 1 invoice, INV-0388", VERIFIED. Mismatch (QA-2-2). Back returns to the done tab with 6 rows.
- W-1099 in the browser: "NO ACCESS. You can't open this work item. It belongs to a project or line you don't have access to. Nothing about it is shown here, not even its name or amount." with a "Back to my queue" link. Direct call: `GET /api/v1/work/W-1099` returns 404 `{"code":"not_found"}`, so no title leaks.
- `GET /api/v1/work/W-1007` returns 200 with W-1001's body (QA-2-3).

My work journeys on the combined head (qa.mjs and qa2.mjs output, same values as before):
- Tabs "Needs me 24, Waiting on others 12, Done 6, Unassigned 2"; first request `?queue=needs_me&limit=20`; 20 rows, "20 of 24 showing", "Show 4 more", 22 SAMPLE DATA labels.
- Show more sent `cursor=o20` and gave 24 rows, "All 24 showing", focus on the first appended link. Limit 10 sent `limit=10` and persisted on reload. End and Home keys selected Unassigned and Needs me.
- Search "lagoon": one request, 2 rows, "2 OF 24 ITEMS"; clearing sent no `q`; "zzz" shows "No work matches" and "Clear filters" restores rows. Esc closed the filter panel and focus returned to Filter. Line and State filters sent `line=Prepare%20an%20invoice&state=action_needed`, badge 2, chips removable, Clear all reloaded unfiltered.
- `?queue=done&q=lagoon&state=verified&limit=50` restored exactly; `?queue=bogus&limit=7&state=nope` fell back to `queue=needs_me&limit=20`. localStorage 0, sessionStorage 0.
- Polling: one more page-1 request after about 15 s; forced 500 kept 20 rows with "Couldn't refresh · updated 10:42"; load error card shows the plain message and "Reference server_error for support", and Try again recovers to 20 rows; 401 shows "You're signed out. Sign in" linking to `/accounts/login/?next=%2Fmy-work`.
- pm: Needs me 0, Waiting 3, Done 2, empty state with "See what's waiting on others" (3 rows after switching); pm `queue=unassigned` shows "This queue isn't open to your role." with "Go to Needs me". Persona none: "No sections are open to your role yet."
- Status codes (curl, mock): finance_lead needs_me 200, unassigned 200; pm needs_me 200, unassigned 403; none needs_me 200, unassigned 200.
- Not run by me: axe scans, loading-state race test, focus rings, hidden-tab polling pause, the Show more failure callout, 401 during refresh, and the work item page's History tab.
