VERDICT: PASS
COMMIT: c26c9f34deee37f0078dbc4f852fec363bf35f6c
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (frontend production build with the contract mock)

## Summary
- Exercised: the shared production build at http://localhost:4511 (process cwd is the f-14 worktree at c26c9f3, `.next/BUILD_ID` written 16:57, after the 16:53 head commit) with the contract mock at http://127.0.0.1:4512. I ran headless Playwright from the worktree's node_modules and reset the mock with `POST /__mock/reset` before and after every journey that changes data. 61 of 61 journey checks pass (`qa-evidence/journeys.txt`). axe is clean on 28 of 28 pages at 1440 and 390 (`qa-evidence/axe.txt`).
- Journeys: every board state W-1701 to W-1711 at both widths, with the board's persona. The live items W-1001 to W-1006 have no `presentation` and no state panel, and their unknown facts read "Unknown". Also: history with filters and paging, the Overview/History tabs (D-45), Open the decision, wrong user (W-1002, W-1608), and F-09's response entry (W-1601) and reconcile panel (W-1711 errors, W-1603 success). Then See all exceptions, no access (404 and 403), signed out (401), 500 then Try again, polling, and the pinned phone bar at 390.
- Read only holds. The work item and history pages sent only GETs to `/api/v1/me`, `/api/v1/work/{id}` and `/history`. The only writes were F-09's `POST /api/v1/work/{id}/actions`, one per press, and F-04's claim after navigating to `/decide`, which is the decide page and not this page.
- Not proved: a real backend and PostgreSQL. There is no backend lane, so this is frontend plus the contract mock. The 500 came from a Playwright route stub, and 401/403/404 came from the mock's `X-Mock-Scenario` header on the work item request. Hidden-tab polling was simulated by overriding `document.visibilityState`. I did not test the reduced-motion check or keyboard focus outlines; unit tests and e2e cover those.
- One non-blocking finding: on the W-1711 board fixture, no reconcile answer can succeed in the mock (QA-4-1). The page handles this correctly. The success path was proved on W-1603 through the same F-14 page.

## Findings
- QA-4-1 | non-blocking | low | integration | The awaiting-reconciliation board item cannot record a reconcile answer in the mock. Repro: reset the mock. `POST http://localhost:4511/api/v1/work/W-1711/actions` with `{"expected_revision":5,"action":"reconcile","outcome":"unknown"}`, the finance_lead CSRF token and the cookie `psl_mock_persona=finance_lead` returns `501 {"code":"not_mocked"}`. The cause is that `mock/fixtures/response/` has no `W-1711.{delivered,not_delivered,unknown}.json` sidecar. In the browser, Unknown and Not delivered both end in "We couldn't confirm your answer. Reload the work item…". Choosing "It arrived" shows "Proof can't be uploaded for this item" with Record disabled, because `mock/fixtures/work/W-1711.json` has no `case_id` or `case_revision`. Expected: the board item can be walked to a recorded answer, as W-1603 can (W-1603 not_delivered: one POST, then the page reloads to PROCESSING at revision 7). Actual: on W-1711 only the error and uncertain branches can be reached. The product code behaves correctly here: a 501 is treated as an uncertain effect and is never re-sent. Only the demo data falls short. Suggested fix: add `case_id`/`case_revision` to W-1711 and the three outcome sidecars, in F-09's fixtures folder.

## Verified
- TECH-3-1 | verified | /work/W-1002 at 1440 (finance_lead): the "revision 1" box spans x 1130.9-1187.4, y 85-100, and the "Work item" tabs nav spans x 1199.4-1352, y 77-109. They do not overlap, and both are visible.
- UI-3-2 | verified | "See all exceptions" is a `psl-btn--secondary work-exceptions` button on W-1708, W-1709, W-1710 and W-1711 at both widths, and on no other W-17xx item. Clicking it on W-1708 at 1440 opens /exceptions ("All exceptions"). At 390 on W-1708, scrolled to the end, the button (y 405-449) sits above the pinned bar (y 734.5-844) and is not covered.
- UX-3-1 | verified | Measured at 390 in the browser: the phone button is 44px high on W-1708, W-1709, W-1710 and W-1711. On desktop it is 50px.

## Results by journey (commands: `node qa-evidence/qa-journeys.mjs`, `node qa-evidence/qa-axe.mjs`)
- **Board states (W-1701 to W-1711, 1440 and 390):**
  - Every page has one h1 and both tabs (Overview → /work/{id}, History → /work/{id}/history; W-1705 shows "History 7").
  - The desktop panel headings match AC 12.
  - There is no sideways scroll; scrollWidth is 390 or less.
  - No Approve or Reject button appears, and the only requests are GETs.
  - Sent reads "Unknown" on W-1710 and W-1711 at both widths, never 0 or blank.
- **Live W-1001 to W-1006:**
  - The API bodies have no `presentation`, and no `.work-statepanel` renders.
  - Each item shows six facts. Every fact whose contract status is unknown reads "Unknown": W-1005 sent and receipt_recorded, W-1001 and W-1004 receipt_recorded.
  - The tabs are present.
- **Open the decision:** W-1701 links to `/work/W-1701/decide?task=T-1701` and opens SCR-03 ("Station 4 · Finance review"). The work item page itself sent no write.
- **Wrong user:** W-1002 (`you_can_act: false`) has no link or button in its task panel. W-1608, an F-09 response task with `you_can_act: false`, has no entry.
- **F-09 response entry:** W-1601 shows "Record the client's response" linking to `/work/W-1601/respond?task=T-1601`, and it opens "Record the client's UAT response".
- **Reconcile on W-1711 (F-09 panel mounted in F-14's slot):**
  - The options are delivered, not_delivered and unknown.
  - Scenario 409 shows "This item changed. Reload it to see the latest."
  - Scenario 403 shows "Your role does not allow this."
  - Scenario 422 shows "Check the highlighted fields and try again."
  - A 501 (no sidecar) shows the uncertain warning with "Reload the work item".
  - Each press sends exactly one POST. The 390 flow behaves the same, with "Record and continue" pinned (`resp-actionbar`, fixed).
  - Success was proved on W-1603 (see QA-4-1).
- **History:**
  - W-1705/history at 1440 has the tabs Overview and History 7, the filter (All 7, Decisions 2, Agent work 2, Evidence 1), 7 rows and the About history aside. Choosing Decisions sends `kind=decisions&limit=20` and shows 2 rows.
  - W-1004/history: rows per page 10 shows 10 rows. Show more sends `cursor=o%3A10` and shows 12 rows, after which Show more is gone. Rows per page 50 sends `limit=50`.
  - At 390, W-1705/history shows "History · INV-0412", the "← Invoice" back link to /work/W-1705 in the frame bar, and "+ 2 earlier entries".
- **Phone:**
  - W-1701 shows "← Queue" to /my-work in the frame bar, not inside `main`.
  - "See his steps" toggles `aria-expanded` from false to true.
  - The decide panel is `position: fixed` with its bottom at 844 before and after scrolling.
  - On W-1706, "Preview the invoice" shows the "TEST TEMPLATE · NOT PSL'S REAL INVOICE" preview, and the disclosures send no request.
- **No access:**
  - W-1099 (404) and W-1001 with scenario 403 or 404 show, at both widths, a single h1 "You can't open this work item", the NO ACCESS tag and "Back to my queue" to /my-work.
  - The id is absent from the visible text and from the title ("Work item · PSL Factory").
  - The id does appear in Next's RSC flight script as the route param, as it does in the URL. That is not visible and not a leak beyond the URL.
- **Signed out:** a 401 on E-WORK-ITEM shows "You're signed out. Sign in" with `/accounts/login/?next=%2Fwork%2FW-1001`.
- **500 then retry:** the page shows "We couldn't load this work item… Reference server_error for support. Try again". Try again sends a second GET and the item renders with six facts.
- **Polling, over 11 s visible and then 11 s hidden:**
  - W-1703 re-read from 1 to 3 times while visible, then stopped when hidden (3 to 3).
  - W-1704 and W-1711 never re-read (1, 1, 1).

## Notes
- UI-3-1 (pruning the exceptions file) is data for the fidelity gate and outside the QA lens. The UI review re-ran all 26 boards at this head.
- UI-4-1 (button order in the desktop owner-needed and setup-needed panels) is open and non-blocking from the UI review. It does not change any journey outcome.
- The mock was reset after the run (204). I started and stopped no servers, copied or built nothing, and deleted my scratch files.
