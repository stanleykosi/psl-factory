VERDICT: PASS
COMMIT: 808e022dd99ef05d39614d16acdfbe4fb0e44f55
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (UI against the contract mock only; no real backend)

## Summary
- Drove the shared production build of this head (app http://localhost:3611, mock http://127.0.0.1:3612) with Playwright (Chromium, Africa/Lagos) and curl. The journey All exceptions, then a row, then its work item, then back (the "See all exceptions" link and browser Back) works for the Lead.
- All personas and states behave as specified: Lead (finance_lead), PM (403 view, no rows), none, empty, 401, 403/404, network error with Try again, Show more failure, keyboard and phone at 390.
- This is UI-only against the contract mock. This is not INTEGRATED_QA_PASSED evidence for the real backend (see "Unproved").

## Findings
None.

## Verified
- Round 1, no fixes to retest.

## Evidence (exact steps and results)
- Lead at 1440: GET /exceptions gives title "All exceptions · PSL Factory", an h1, headers WHAT HAPPENED / WORK / WHAT'S BEING DONE / WHO ACTS, and 20 rows. Row 1 reads "SEND UNCERTAIN since 11:02, Kora Logistics · Milestone 1 invoice, ... Nothing resent." The page shows "20 shown", "As of 14 Nov 11:05", the footer sentence and only one button (Show more).
- Paging: Show more gives 25 rows and the button disappears. Rows per page 10 gives 10 rows. 50 gives 25 and no Show more.
- Journey: the first title opens /work/W-1005 (h1 "Kora Logistics · Milestone 1 invoice"). It has one "See all exceptions" link, which returns to /exceptions with 20 rows. A second row opened /work/W-1501, and browser Back returned to /exceptions with 20 rows. /work/W-1003 has no "See all exceptions" link.
- Direct API through the mock with a persona cookie:
  - finance_lead gets 200 and rows.
  - Cursor `limit=10&cursor=o:20` returns the next page.
  - `limit=7` is treated as 20.
  - pm gets 403 with `{"code":"forbidden",...}`.
  - none gets 200 with `items: []`.
  - Header `X-Mock-Scenario: 401` gets 401.
- PM at 1440 and 390: h1 and sub-line stay, with "This list is for Leads", "Your own exceptions appear in My work, under Needs me." and a "Go to My work" link that reaches /my-work. No rows, no count, no As of, and no horizontal scroll (scrollWidth 1440 and 390).
- None persona: the app frame shows "No sections are open to your role yet" and the list is not reached. This is the frame's rule (F-01), and nothing leaks.
- Empty (cookie `psl_mock_exceptions=empty`): "No exceptions. Everything is moving or verified. As of 14 Nov 11:05".
- Errors, injected on the list request only:
  - 401 shows "You're signed out. Sign in".
  - 403 and 404 show the Leads view.
  - A network abort shows "We couldn't load the exceptions. Your work is safe; nothing was changed.", a reference and Try again. Try again gives 20 rows.
  - A 503 on the cursor page keeps 20 rows and shows "We couldn't load more exceptions".
  - Cookie scenario 401 shows the frame's signed-out state.
- Keyboard: Tab goes skip link, top bar, the rows-per-page select, then each title link, with a 2px solid outline everywhere I looked.
- Phone 390: 20 cards, no table, scrollWidth 390, card text "tag since, title, doing, Who acts: ...", Show more 44px tall.

## Notes
- Scenario 500 is ignored by the mock because E-EXCEPTIONS declares only 401/403/404. I used a network abort and a stubbed 503 instead.
- Screenshots were taken in the scratchpad and are not kept.

## Unproved
- The real backend T-EXCEPTIONS: grant filtering, tenant scoping, the real shape and order of data, real pagination cursors, and real 401/403 behaviour. The mock's PM 403 and none-empty rules are mock choices.
- Real work-item data behind each row, with no pm-or-grant combination beyond the three personas.
- axe, and the builder's own e2e suite, were not re-run by me. Browsers other than Chromium are untested.
