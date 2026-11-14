VERDICT: PASS
COMMIT: 02d59d8bb2216a7242a02454b957d4a0b0fdde49
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (frontend against the contract mock only, UI-only per coordinator)

## Summary
- Tested on the shared build at http://localhost:3311 with the mock at http://127.0.0.1:3312. Both run from the f-02 worktree; `.next/BUILD_ID` was written at 07:36, after head 02d59d8 was committed at 07:30. I did not start or stop any server. I drove Chromium at 1440x900 and at 390x844 (mobile, touch), timezone Africa/Lagos.
- `e2e/my-work.spec.ts` ran against the shared build with a temporary scratchpad config (base URL 3311, no webServer, deleted afterwards): 15 passed, 0 failed, in 44.7 s.
- My own journeys all pass at both widths:
  - queues, keyboard tab switching, search, all four filters with chips and "Show N items", rows per page, Show more and URL restore;
  - empty Needs me with "While you're free", the finance_lead, pm and none personas, and the board sample;
  - polling, a failed refresh, and the 401 signed-out state.
- QA-2-2 is verified. Rows W-1001 to W-1006 open the work item they show: the title, reference and state match on every one.
- NOT PROVED: there is no real Django API, so real permissions, real cursors, the payroll exclusion and E-PROJECTS (the mock returns 501) are untested. The `suggestions` field is a proposal, served only by the board sample. "Not now" is not stored anywhere. The mock still answers unknown ids with the W-1001 item.

## Findings
- QA-3-1 | non-blocking | low | frontend | Carried over from QA-2-3. The mock answers any id it has no fixture for with W-1001's body. `GET /api/v1/work/W-1007` and `GET /api/v1/work/W-1115` both return 200 with `id: W-1001`. So the 18 rows numbered W-11xx, and the board sample's W-14xx rows, open "Lagoon Health · Milestone 2 invoice" under their own URL. W-1401 looks correct only because it has the same title. Expected: a 404 for unknown ids, which the mock already does for W-1099. Source: `frontend/mock/server.mjs` (work-item lookup).
- QA-3-2 | non-blocking | low | product | "Not now" hides a suggestion only until the page reloads. I dismissed one, opened "Draft minutes" (which goes to /assistant), pressed Back, and all 3 suggestions were shown again. This is as build.md describes (there is no endpoint), but people will see dismissed suggestions come back. It needs the dismissal endpoint when the `suggestions` field is adopted.
- I confirm UX-3-1: after "Not now" is pressed with the keyboard, focus falls to the document start ("Skip to main content") at both widths. I did not reproduce UX-3-2. On the phone, opening the sheet and pressing Esc straight away put focus back on "Filter" in my run.

## Verified
- QA-2-2 | verified | Browser test as finance_lead: for each id I opened its queue with `limit=50`, clicked the row link, and read the item page.
  - W-1001: "Lagoon Health · Milestone 2 invoice", INV-0412, WAITING.
  - W-1002: "Harbour Bank · Receipt for INV-0398".
  - W-1003: "Delta Foods · Weekly client update".
  - W-1004: "Lagoon Health · Milestone 3 invoice", INV-0419, READY TO CONTINUE.
  - W-1005: "Kora Logistics · Milestone 1 invoice", INV-0405, EFFECT UNCERTAIN.
  - W-1006: "Delta Foods · Milestone 1 invoice", INV-0388, VERIFIED.
  - Each row's title (and, on phone cards, its state) matches the `/work/<id>` page at 1440 and 390. The list API rows for W-1004, W-1005 and W-1006 also match `GET /api/v1/work/<id>`.
- QA-2-1 | verified | `curl` to the mock returns 404 `invalid_query` for each of these: `queue=needs_me&q=`, `&line=`, `&waiting_on=everyone`, `&limit=7`, `&cursor=zz` and `queue=bogus`. When the page itself is opened with `?queue=bogus&limit=7&state=nope&waiting_on=everyone&line=`, it sends only `/work?queue=needs_me&limit=20` and shows 20 rows.

## Evidence
Requests seen by the page are in brackets.

- **e2e.** `NODE_PATH=frontend/node_modules npx playwright test -c <scratchpad>/pw.config.ts` (testDir is the worktree's e2e folder, testMatch `my-work.spec.ts`, baseURL http://localhost:3311): 15/15 passed. This covers axe at 390 and 1440 for every state, loading and reduced motion, the error and Try again path, wrong role, focus rings, and the phone kind tag.
- **Default view, finance_lead, both widths.**
  - Tabs read "Needs me 24, Waiting on others 12, Done 6, Unassigned 2". 20 rows show, the footer reads "20 of 24 showing" with "Show 4 more", and the records line reads "44 records you can see · updated 10:42".
  - The page width (scrollWidth) is 1440 and 390, so there is no sideways scroll. No page errors; the only console errors are the expected 501s from E-PROJECTS.
- **Queues.** Clicking each tab sends its own request:
  - Waiting on others: [`queue=waiting_on_others&limit=20`], 12 rows.
  - Done: 6 rows.
  - Unassigned: 2 rows.
  - Needs me: 20 rows.
  - Each queue except Needs me is reflected in the URL (`?queue=…`).
- **Keyboard on the tabs.** ArrowRight moves to Waiting on others and focus follows. End goes to Unassigned, Home to Needs me, and ArrowLeft from Needs me wraps to Unassigned.
  - Enter on a focused row link opens `/work/W-1115`, and Back returns to `/my-work?limit=10` with 10 rows.
- **Search.**
  - "lagoon" sends one request [`q=lagoon`] and gives 2 Lagoon Health rows; the URL becomes `?q=lagoon`.
  - "INV-0412" gives 1 row.
  - Clearing the box sends no `q`.
  - "zzzz" shows "No work matches. Nothing in Needs me matches your search and filters." with "Clear filters", which brings back 20 rows and an empty box.
- **Filters, both widths.**
  - Line shows 4 lines plus "Show all 6 lines" ("All 6 lines" on the phone), which expands to 6. Checking a second line unchecks the first.
  - Project offers only "Any project", because E-PROJECTS returns 501 in the mock.
  - State has 11 states, and Waiting on has Me, Someone else, An agent, Someone outside PSL and No owner yet.
  - Line "Prepare an invoice" with State "Action needed" shows "Show 2 items". Applying it sends [`line=invoice&state=action_needed`] and gives 2 rows. The Remove Line and Remove State chips appear, and the phone button reads "Filter, 2 on".
  - Changing to Waiting on "Me" shows "Show 9 items" and gives 9 rows (`?line=invoice&waiting_on=me`). Removing the Line chip gives `?waiting_on=me`, and "Clear all" gives `/my-work` with 20 rows.
  - Esc closes the panel.
  - Opening `?project=CASE-NOPE` gives 0 rows and a "Project CASE-NOPE ×" chip.
- **Rows per page.**
  - 10 sends [`limit=10`]: 10 rows, "10 of 24 showing", "Show 10 more".
  - 50 sends [`limit=50`]: 24 rows, "All 24 showing".
  - 20 gives 20 rows and "Show 4 more".
- **Show more.** It sends [`limit=20&cursor=o20`] and gives 24 rows with "All 24 showing". Focus goes to the first added row (/work/W-1118).
- **URL restore and storage.** `?queue=done&q=delta&state=verified&limit=50` restores the Done tab, the search "delta" and 2 rows. localStorage and sessionStorage are both empty.
- **Live refresh.**
  - About 16 s after load, one page-1 request goes out on its own [`queue=needs_me&limit=20`].
  - With the list request forced to 500, the next refresh keeps the 20 rows and shows "Couldn't refresh · updated 10:42".
  - With the cookie `psl_mock_scenario=401`, the page shows "You're signed out. Sign in", linking to `/accounts/login/?next=%2Fmy-work`.
- **pm, standard sample.**
  - Tabs read "Needs me 0, Waiting on others 3, Done 2", with no Unassigned tab.
  - The page shows "Nothing needs you right now", "3 things you started are moving. We'll alert you on WhatsApp when one needs you." and "See what you started". That opens `?queue=waiting_on_others` with 3 rows.
  - "Where your work is" shows on desktop only. "While you're free" is absent, which is correct without `suggestions`.
  - `?queue=unassigned` shows "This queue isn't open to your role. Only Leads can see unassigned work." with "Go to Needs me" (the mock returns 403).
- **pm, board sample** (cookie `psl_mock_worklist=board`).
  - "While you're free" shows Tola's avatar (alt "Tola · PMO agent") and 3 suggestions, each with an action and "Not now".
  - The caught-up image has alt "Tola, the PMO agent" and loads.
  - "Not now" (pressed with Enter) leaves 2 suggestions. Dismissing all of them removes the panel.
  - "Draft minutes" opens /assistant, which is the "not built yet" placeholder.
  - Page width is 1440 and 390, no sideways scroll.
- **finance_lead, board sample.** Tabs read 3/5/28/1. The W-1401 row opens /work/W-1401 with a matching title, but only by chance (see QA-3-1).
- **Persona none.** The page says "No sections are open to your role yet. Ask a Lead or Admin to check your roles."
- **Direct calls to the mock.**
  - Status by persona and queue (with `limit=50`):
    - finance_lead: 200 for all four queues (24/12/6/2).
    - pm: 200 for the first three (0/3/2) and 403 `queue_not_open` for unassigned.
    - none: 200 with every queue empty.
  - Item calls: `/work/W-1099` returns 404 `not_found`, and `/work/W-1007` returns 200 with W-1001's body (QA-3-1).
- **Clean-up.** The scratchpad scripts, the config and the test output are deleted. The worktree is clean (`git status` shows nothing). The 3311 and 3312 servers are still running.
