VERDICT: PASS
COMMIT: 752ab93e4edc6fe7f3b9f85c410b377cff051bc9
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (round 2, UI-only feature against the contract mock)

## Summary
- I tested the shared build on :4011 against the contract mock on :4012. Both servers run from the f-10 worktree, and the build (08:01) is newer than the head commit (07:59). The month-end e2e spec passed 24 of 24 there, the 42 month-end unit tests passed, and a further 8 browser probes of my own passed.
- Money: an unknown cash value is never shown as 0 or left blank. The default data shows "₦4.7M + Unknown", the unknown variant "Unknown" and the known variant "₦4.7M" in a white cell. I sent 13 edge bodies (bad amount, empty amount, `known.unknown: true`, v4-only unknown, v4 unknown with an amount, negative, USD, a missing summary, a partial summary and others), and each showed either "Unknown" or the correct compact value, with the matching full value in `aria-describedby`.
- Access: restricted rows never get a link. I injected `work_id` W-9 and W-10 into restricted rows, and neither href appeared at 1440 or at 390. The pm and none personas, 403, 404, another month and a bad period show nothing about the month. A 401 shows the signed-out state, and its sign-in `next` points back to `/finance/month-end?period=2026-10`. A 500 and a network failure show the error card, and Try again (by mouse and by keyboard) loads the board.
- Each Open link and "Import the missing statement" (desktop, and phone at 390) reaches its `/work/W-160x` page, which renders without "not found". At 390 nothing scrolls sideways in any scenario. The keyboard reaches every link with a 2px solid outline.
- Not proved: there is no real E-MONTH-END backend, so everything ran on mock sample data. Real tenant isolation, real `finance.read` enforcement, how the server marks rows restricted, and the work items' own access checks are untested. The mock's work items are all the same default item ("Lagoon Health · Milestone 2 invoice"), so I proved only that each link reaches a work-item page, not that it reaches the right task.

## Findings
None.

## Verified
- UI-1-1 | verified | e2e "empty month" passed on :4011 at 1440 and 390, and asserts that `.monthend-empty` is under 200px tall. My probe at 390 with `psl_mock_month_end=empty` showed the summary "0 of 0 done · 0 waiting", 0 cards, no bar, and scrollWidth 390 = clientWidth 390.
- UX-1-1 | verified | e2e keyboard test on :4011: the first `Open` link has the accessible description "Bank statements", and all 7 targets take focus with a 2px solid outline. Its visible text and name are still "Open". The unit test (passed) resolves all six descriptions to the six titles in order.

## Evidence
- e2e: `cd /Users/Hunchoo/psl-factory-worktrees/f-10/frontend && NODE_PATH=$PWD/node_modules npx playwright test -c <scratchpad>/qa.config.ts finance-month-end`. The scratchpad config used baseURL `http://localhost:4011`, had no webServer, and has been deleted. Result: 24 passed (1.4m). It covered:
  - desktop: the board in order, keyboard, unknown and known cash, and the v4-only contract body
  - both widths: empty, pm, none, 403 = 404 DOM, 2026-09, five bad periods with no request, and no debug text
  - phone: board-phone, the 7 default cards, axe on unknown and contract, keyboard, and "← Finance" both through history and in a fresh tab
- Unit: `npx vitest run tests/finance-month-end` gave 2 files and 42 tests passed.
- Mock, called directly (`curl` on `:4012/api/v1/finance/month-end`):
  - `?period=2026-10` gives 200 with 7 tasks; the Payroll row has `restricted: true` and no `work_id`.
  - Cookie `psl_mock_persona=pm` or `none` gives 403 `{forbidden, "Month-end is for Finance."}`.
  - `?period=2026-09`, no period, and `?period=Oct` each give 404.
  - Scenarios 401, 403 and 404 give those statuses.
  - Scenario 500 gives 200: v4 declares no 500 for E-MONTH-END, so the mock leaves it alone (by design). I tested the browser's 500 path with `route.fulfill(500)`.
  - The variants unknown, empty, known, contract and board-phone return the bodies the spec describes. The contract body has no summary and no detail.
- Browser probes (scratchpad spec, deleted):
  - Only one month-end request was sent in 6 s after the page opened, so there is no polling.
  - Month-end 401 only (the `x-mock-scenario` header on that one request): "You're signed out. Sign in", linking to `/accounts/login/?next=%2Ffinance%2Fmonth-end%3Fperiod%3D2026-10`.
  - 500: "We couldn't load the month-end checklist. Your work is safe; nothing was changed. Reference server_error for support." Try again sent a second request and the board appeared.
  - An aborted request shows "Reference network_error". Try again by Tab plus Enter loads the board.
  - Cash cell results:

    | Body | Cell |
    |---|---|
    | `4.7M`, `""` or `known.unknown: true` | Unknown (amber, "Not known yet.") |
    | v4 `999950000.00` | ₦1B |
    | `-1250.00` | -₦1.3K |
    | USD `1200.00` | USD 1.2K |
    | `999.99` with `has_unknown` | ₦999.99 + Unknown |
    | no summary, or `{done: 2}` only | counts Unknown, Unknown, Unknown |

  - Phone 390, for each of default, board-phone, unknown, known, empty and contract: scrollWidth 390. The contract summary reads "Unknown done · Unknown waiting". The bar appears only when `next_action` is returned. The visible links are only `/my-work` and `/work/W-1601`.
- Screenshots were taken in the scratchpad and deleted afterwards. The worktree `git status --porcelain` is empty, and I stopped no server.

## Notes
- Product question, not a defect: a cash body whose known part is exactly `0.00` with `has_unknown` shows "₦0.00 + Unknown". That follows the spec, since a known zero is a fact and the Unknown is still shown. The backend should only send `known` when that zero has been confirmed.
- Very large amounts have no unit above B: `123456789012345678.99` shows "₦123456789B". The full value in the description is correct. This is cosmetic and unlikely to matter.
- On the phone, a restricted card shows its where-text and tag but not `restricted_label`. That matches the board, since phone cards have no last cell, and it never links.
