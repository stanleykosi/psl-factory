STATUS: READY
COMMIT: 02db3e841a47c4d83ed907c5bba467ef3a05a164
BUILDER: builder
LANE: full

## Summary
- New route `/finance/month-end?period=YYYY-MM` shows the SCR-36 Month-end checklist from one E-MONTH-END read. Desktop has the as-of line, the four-cell strip, the task table, Chidi's note and "Import the missing statement". Phone has the summary line, the task cards and a pinned action bar.
- Cash reads "₦4.7M + Unknown", "₦4.7M" or "Unknown", and never 0. The full value is exposed through `aria-describedby`. Counts, tags, labels, restriction and links all come from the response. The restricted Payroll row shows "HR only" and never links.
- The D-MONTH-END-VIEW r1 (v7 proposal) fields are typed locally, and all of them are optional. A pure v4 body renders: Unknown counts and cash, `line`, and the STATE_TAGS words.
- Mock: `frontend/mock/finance.mjs` serves the desktop board's data, plus the `board-phone`, `known`, `unknown`, `empty` and `contract` variants (cookie `psl_mock_month_end`). pm and none get 403; any other period gets 404.
- Design fidelity passes on both boards: desktop 1440 visual 97.8, phone 390 visual 94.9, 100% of elements after exceptions. Reports are in `round-1/fidelity/`.

## Changes
- `frontend/src/app/finance/month-end/page.tsx`: a server component. It validates `period` (exactly one `YYYY-MM`, month 01-12) and otherwise calls `notFound()` with no request. Metadata title is "Month-end · PSL Factory".
- `frontend/src/features/finance/month-end/proposal.ts`: `MonthEndBase` (v4), `MonthEndProposal` and `MonthEndTaskProposal` (the v7 D-MONTH-END-VIEW r1 names, all optional), and `MonthEnd`.
- `frontend/src/features/finance/month-end/model.ts`: pure display rules.
  - `parsePeriod`, `periodNames`, `asOfLine`, `countText`, `doneText`.
  - `compactAmount` uses BigInt, rounds half away from zero, uses B/M/K units and steps up a unit when needed.
  - `cashView`, `taskTag` (tone map), `taskEnd` (restricted never links), `nextAction` (only with `work_id`) and `AGENT_NAMES`.
- `frontend/src/features/finance/month-end/useMonthEnd.ts`: one read per open, no polling. A request counter drops superseded answers. `retry` re-reads.
- `frontend/src/features/finance/month-end/MonthEndView.tsx`: renders the board and its states.
  - Loading uses `LoadingState`. 401 uses `SignedOutState` with next `/finance/month-end?period=…`.
  - 403 and 404 both show `MonthEndNoAccess`. server and network show `WorkErrorCard` with the month-end message.
  - Empty shows `psl-empty` with "No month-end tasks you can see for {Month YYYY}."
  - The phone "← Finance" is an `<a href="/my-work">`. Its click calls `router.back()` when `history.length > 1`.
  - The avatar is `next/image` `unoptimized` with `/agents/{agent}.png` and `alt=""`, using the base's PR #12 files, not copies.
- `frontend/src/features/finance/month-end/MonthEndStates.tsx`: the no-access view (NO ACCESS tag, h1, line, "Back to my queue").
- `frontend/src/features/finance/month-end/month-end.css`: both layouts as drawn. It uses token variables and edits no shared CSS.
- `frontend/mock/finance.mjs`: `monthEnd({url, persona, cookies})` and `contractBody(body)`.
- `frontend/mock/fixtures/E-MONTH-END.json` (the spec's default fixture), plus `frontend/mock/fixtures/finance/month-end.{board-phone,known,unknown,empty}.json`.
- `frontend/mock/server.mjs`: exactly 3 lines (the import, `'E-MONTH-END'` appended to `M1_OPERATIONS`, and the dispatch line). Still v4.
- `frontend/tests/mock-contract.test.ts`: entries only.
  - `QUERY['E-MONTH-END']`.
  - `PERSONA_STATUS {'E-MONTH-END': {pm: 403, none: 403}}` and `CONTRACT_BODY {'E-MONTH-END': contractBody}`, introduced in F-06's exact shape because F-06 is not merged. On rebase, merge the two maps' entries.
- `frontend/tests/finance-month-end.test.tsx` (35 tests) and `frontend/tests/finance-month-end-mock.test.ts` (7 tests).
- `frontend/e2e/finance-month-end.spec.ts` (24 tests, 1440 and 390, with axe).
- `delivery/features/F-10/fidelity-exceptions.json`: Start work and More ways to start (frame, F-05, D-04(a)). No other exception was needed, because the tool reported no other missing element.
- Untouched: `architecture/**`, `frontend/src/api/**`, `frontend/src/shell/**`, tokens, bundle and shell CSS, and the `delivery/` protected files (`git diff --stat b91ca6a -- architecture frontend/src/api frontend/src/shell` is empty).

**Proposal fields for the backend developer (T-FINANCE, D-MONTH-END-VIEW r1, as in v7):**
- Top level: `as_of` (date-time), `coverage`, `summary{done, waiting, in_progress, total}`, `cash_received_detail{known{amount?, currency, unknown}, has_unknown, unknown_note?}`, `agent_note{agent: tola|chidi|zainab, text}`, `next_action{label, work_id?}`.
- Per task: `title`, `detail`, `status_label`, `tone` (neutral|person|agent|stopped|uncertain|verified|restricted), `restricted`, `restricted_label`.
- The tone-to-colour mapping in the spec's Assumptions needs backend confirmation.

**Notes for review and product acceptance:**
- **Phone "← Finance" placement (D-08 interpretation).** It sits at the top right of the page's first line, level with the h1, rather than on its own line under the frame bar.
  - On its own line it pushed every card down by 22 to 42 px, and the phone visual score was 77 to 79.
  - In this position the page below starts where the board's does: visual 94.9.
  - It is still the first focusable element in the page, has a 44 px target and a visible focus outline.
  - It moves into the frame's phone-bar slot with D-13. The design engineer should confirm or reject this placement.
- **The fidelity tool's `--cookies` does not reach the API.** The tool sets cookies for the page URL, so Playwright scopes them to path `/finance/`. The browser never sends them to `/api/v1/...`, so a `psl_mock_month_end=board-phone` run actually serves the default data (7 cards).
  - The reported phone run (94.9) therefore has the extra Payroll card below the six board cards.
  - With six cards (checked by temporarily defaulting the mock to `board-phone`, then reverted) the score was 97.3.
  - The e2e tests set the cookie at path `/` and do get the board-phone data. This is a tool limitation (the same one F-07 recorded) and is not changed here.
- **AC10 with persona `none`.** The frame (F-01, `src/shell/**`) stops at "No sections are open to your role yet." before any page renders, because `none` has no destinations.
  - The month-end no-access view therefore cannot appear for `none`. The mock still answers `none` with 403.
  - e2e asserts that the frame state shows and that nothing about the month appears.
  - "Scenario 403 and 404 render identical DOM" is tested by applying the scenario header only to the month-end read. The `psl_mock_scenario` cookie also hits `/me`, so the frame's ForbiddenState would show instead.
- **Avatar files.** `frontend/public/agents/*.png` on the base (PR #12) have md5 `da53372b…`, `8a35aac4…` and `fc4cfd33…`, not the spec's `e07868f1…` and so on. Per the coordinator, they are used as-is and not copied or re-exported.
- **DONE cell colours.** The cell is white text on #22764A, as the board draws it. The spec's "#22764A on white" is read as that pairing.
- **Visible text.** The h1 holds both month forms, "October 2026" (desktop) and "Oct" (phone). CSS hides the one that does not apply, so `textContent` in jsdom contains both.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] **Desktop board.**
   - e2e "the board in order…" asserts the text order: FINANCE / MONTH-END; h1; FROM RECORDS YOU CAN SEE · UPDATED 10:42; strip "2 of 7 / 3 / 2 / ₦4.7M + Unknown"; the 7 rows; Chidi; the action.
   - It also asserts the tag classes (person, done, waiting) and the `/agents/chidi.png` avatar with `alt=""`.
   - A unit test checks the full row cell texts.
2. [x] **Phone board.**
   - e2e "the phone board…" at 390 with `board-phone`: "← Finance", h1 innerText "Month-end · Oct", "2 of 7 done · 3 waiting", 6 cards with title, tag and where-text.
   - The action is `position: sticky`, with its bottom within 40 px of the viewport bottom.
   - The strip, table and note are hidden, and there are no Open links.
3. [x] **Design fidelity.**
   - SCR-36-desktop at 1440: PASS, coverage 100% with exceptions, visual 97.8.
   - SCR-36-mobile at 390 (`--cookies psl_mock_month_end=board-phone`, default data served, see Notes): PASS, coverage 100% (23/23), visual 94.9.
   - Reports: `delivery/features/F-10/round-1/fidelity/SCR-36-desktop-1440/` and `…/SCR-36-mobile-390/`.
4. [x] **Unknown is never 0.**
   - The unit `cashView` table covers every Contract example plus ₦999.50, ₦1K and 999950 → ₦1M.
   - It also covers: malformed "4.7M" and "" → Unknown; `known.unknown: true` with an amount → Unknown; detail absent with v4 `unknown: true` → Unknown.
   - e2e: default "₦4.7M + Unknown" (description "Known so far ₦4,712,500.00; the rest is not known yet."); `unknown` → "Unknown"; `known` → "₦4.7M" in a white cell. No value matches empty, "0" or "₦0".
5. [x] **Restricted rows never link.**
   - Unit: a restricted task with `work_id: "W-9"` has no link, and `/work/W-9` is nowhere in the DOM.
   - A restricted task with no label shows "Restricted". A task with no `work_id` has an empty last cell.
   - e2e: the Payroll row shows "HR only" and has 0 `<a>`.
6. [x] **Links go to work items.**
   - e2e: the visible hrefs in main are `/work/W-1601`…`/work/W-1606`, then `/work/W-1601` for the action (desktop). On the phone they are `/my-work` and `/work/W-1601`.
   - No href on the page contains `SCR-`, `.dc.html` or `claude.ai`.
7. [x] **Counts are taken as returned.**
   - Unit: `summary {5, 0, 9, 4}` shows "5 of 4", "0", "9".
   - No summary shows "Unknown" ×3 and "Unknown done · Unknown waiting".
8. [x] **v4-only body (contract).**
   - e2e and unit over `contractBody(default)`: no errors, no as-of line, all four cells Unknown, `line` with WAITING / ACTION NEEDED / VERIFIED.
   - 6 links; the Payroll last cell is empty; no note or action.
9. [x] **Period handling.**
   - e2e: no period, `2026-13`, `Oct`, a repeated period and an empty period each show "This page doesn’t exist.", with zero requests to `/api/v1/finance/month-end`.
   - `2026-09` shows the no-access view. Unit tests cover `parsePeriod`.
   - `grep -rn "new Date" frontend/src/features/finance frontend/src/app/finance` finds nothing (formatClock is imported).
10. [x] **Wrong user (pm), with a caveat for none.**
    - pm: e2e shows the no-access h1 and "Back to my queue", with no ₦, digits or task names.
    - none: the frame state is shown instead (see Notes).
    - 403 vs 404: identical `main` innerHTML in e2e (scenario header on the month-end read only) and identical DOM in the unit test.
11. [x] **Signed out.**
    - The frame's `/me` 401 path is F-01's and unchanged.
    - Unit: month-end 401 shows "You’re signed out." with Sign in href `/accounts/login/?next=%2Ffinance%2Fmonth-end%3Fperiod%3D2026-10`.
12. [x] **Load failure.**
    - Unit: 500 shows the month-end error message and "Reference server_error for support."; Try again re-reads and shows the table.
    - A network failure shows "Reference network_error".
    - A superseded answer is ignored, tested as an answer to a superseded period that arrives after the newer read. The same request counter guards retries.
13. [x] **Empty.**
    - e2e at both widths with `empty`: "No month-end tasks you can see for October 2026."; the strip reads "0 of 0", "0", "0", "Unknown" (desktop) and the summary reads "0 of 0 done · 0 waiting" (phone).
    - No table, cards, note or bar.
14. [x] **Mock contract.**
    - `npm test`: 15 files and 367 tests pass.
    - The mock tests cover: finance_lead 200; pm and none 403 with the declared shape; 2026-09, a missing period and a repeated period 404; every variant v7-valid as served and v4-valid after `contractBody`; and the generic loop covering E-MONTH-END.
    - architecture and `src/api` are unchanged.
15. [x] **Accessibility.**
    - axe (wcag2a/aa, 21a/aa, 22aa) reports 0 violations at 1440 and 390 for: default, board-phone, unknown, empty, contract, pm, none and invalid period.
    - Tabbing reaches all 6 Open links and the action (desktop), and "← Finance" and the action (phone), each with a 2px solid outline.
    - The table has a thead row. The avatar has `alt=""`.
16. [x] **Back link.**
    - e2e: from `/my-work` to the page, clicking "← Finance" returns to `/my-work` via history.
    - Opened in a fresh tab (`window.open`, `history.length` 1), it follows its href to `/my-work`.
    - It is hidden at 1440.
17. [x] **No sample tag, no debug identifiers.** e2e at both widths finds no "SAMPLE DATA", no `W-16xx`, no `action_needed` and no process-ID pattern in the page text.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-10 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0: Django check, npm ci, lint (0 warnings), typecheck, vitest 15 files / 367 tests, next build.
- `cd frontend && E2E_PORT=4001 MOCK_PORT=4002 npm run test:e2e` gave 107 passed (the full suite, including 24 in `e2e/finance-month-end.spec.ts`).
- Fidelity, run on `MOCK_PORT=4002 npm run dev -- -p 4001`:
  - `node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright frontend/node_modules/playwright/index.mjs --board design/canvas/finance/project/SCR-36-desktop.dc.html --page "http://localhost:4001/finance/month-end?period=2026-10" --width 1440 --exceptions delivery/features/F-10/fidelity-exceptions.json` gave PASS, visual 97.8.
  - The same command for SCR-36-mobile at `--width 390 --cookies psl_mock_month_end=board-phone` gave PASS, visual 94.9.
- The dev server on 4001/4002 was stopped afterwards, and `frontend/test-results` was deleted.
- All tests ran against the contract mock (sample data). There is no real backend for E-MONTH-END yet (T-FINANCE).

## Blocked
