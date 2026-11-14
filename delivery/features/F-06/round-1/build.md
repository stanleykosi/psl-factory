STATUS: READY
COMMIT: 808e022dd99ef05d39614d16acdfbe4fb0e44f55
BUILDER: builder
LANE: full

## Summary
- New route `/exceptions` (SCR-10): E-EXCEPTIONS rows in API order with a kind tag, "since <t>", the title linked to the work item, what is being done and who acts. It has 10/20/50 rows per page, Show more (only when `next_cursor` is present), "N shown" (rows loaded, never a total), "As of" in WAT and the board's footer sentence.
- The list is read-only. A 401 shows `SignedOutState`. A 403 or 404 shows "This list is for Leads" with no rows, count or as_of. A server or network error shows `WorkErrorCard` with Try again. A Show more failure keeps the rows and shows a warning.
- `src/features/exceptions/index.ts` exports `ExceptionsList` (`limit`, `compact`, `maxRows`, `seeAllHref`) and `useExceptions`, so F-08 can embed the list without editing it.
- Mock: `frontend/mock/exceptions.mjs` serves 25 fixture rows, paged by limit and cursor. It answers pm 403, none an empty list, and the cookie `psl_mock_exceptions=empty` an empty list. There are 24 new work items, W-1501 to W-1524.
- `NextStep` shows "See all exceptions" for effect_uncertain, awaiting_reconciliation, owner_needed, setup_needed and followup_needed.

## Changes
- `frontend/src/app/exceptions/page.tsx`: the route, with metadata title "All exceptions · PSL Factory".
- `frontend/src/features/exceptions/`:
  - `types.ts`: derived contract types.
  - `labels.ts`: `KIND_TAGS` as a `Record<ExceptionKind,…>`, the limits, and `sinceText` (HH:mm on the same Lagos day, otherwise D Mon).
  - `useExceptions.ts`: a request counter drops stale answers, Show more appends, and a 401 on Show more goes to signed out.
  - `ExceptionsList.tsx`: a table at 720px and wider, cards below, plus every state, and compact mode.
  - `ExceptionsPage.tsx`: the h1, the sub-line and the full list.
  - `exceptions.css` (token variables only).
  - `index.ts`.
- `frontend/mock/exceptions.mjs`, `frontend/mock/fixtures/E-EXCEPTIONS.json` (25 rows, newest first, all five kinds, 3 effect_uncertain), and `frontend/mock/fixtures/work/W-1501.json` to `W-1524.json`:
  - each work item matches its row's title, and its state is mapped from the row's kind;
  - `tasks: []`, `sample: true`;
  - references come from the new INV/RCP/UPD/CST-06xx range, so none collides with an existing fixture.
- Shared edits (additive; the integration owner resolves merge order with F-05, F-07 and F-08):
  - `frontend/mock/server.mjs`: one import, `'E-EXCEPTIONS'` appended to `M1_OPERATIONS`, and one dispatch line after E-WORK-LIST. Nothing else.
  - `frontend/tests/mock-contract.test.ts`: the `PERSONA_STATUS` map (`{ 'E-EXCEPTIONS': { pm: 403 } }`), with the generic loop expecting `PERSONA_STATUS[id]?.[persona] ?? 200` and validating against that status. F-07 and F-08 can add entries to the map.
  - `frontend/src/features/work-item/WorkItemOverview.tsx`: the `EXCEPTION_STATES` constant and one conditional `Link` in `NextStep` (`Link` was already imported).
- Tests: `frontend/tests/exceptions.test.tsx`, `frontend/tests/exceptions-mock.test.ts` and `frontend/e2e/exceptions.spec.ts`.
- Not drawn, for product acceptance and backend T-EXCEPTIONS (PMO-0-1): the reference under each title, the search box, the Filter button, and the "N OPEN" total. E-EXCEPTIONS supplies none of them (rows carry only work_id, what, title, doing, who_acts and since; the query takes only cursor and limit).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Default list: e2e "default list" checks h1, sub-line, the 4 headers, 20 rows, first row SEND UNCERTAIN linking to /work/W-1005, "20 shown", "As of 14 Nov 11:05" and the footer at 1440x900. Unit test too.
2. [x] Order kept: unit "keeps the order returned" (shuffled stub).
3. [x] Kind mapping: unit "maps every kind". Only effect_uncertain uses `psl-tag--waiting`.
4. [x] Times: unit test gives 10:02Z → "since 11:02", 2026-11-10T08:30Z → "since 10 Nov", and 23:30Z on the 13th → "since 00:30" (same Lagos day). The `time` title uses formatWat.
5. [x] Paging: the unit test checks the URLs `?limit=20`, `?limit=20&cursor=o%3A20`, `?limit=10`, `?limit=10&cursor=o%3A10` and `?limit=50`. 50 replaces the rows, and Show more disappears without `next_cursor`. In e2e, 20 rows plus Show more gives 25, then no Show more. A superseded-limit answer is dropped (unit).
6. [x] Show more failure: unit test with a 500 on the cursor page; the 20 rows stay and the warning copy shows.
7. [x] Empty: unit test, plus e2e with the cookie at 390 and 1440 (no table, Show more or footer; As of shown).
8. [x] Signed out: unit test (next=%2Fexceptions). In e2e, cookie `psl_mock_scenario=401` gives the frame's signed-out state with next=/exceptions. A list-only 401, injected as an `X-Mock-Scenario` header on the list request, shows the page's own state.
9. [x] Wrong user: e2e with persona pm at 390 and 1440 shows "This list is for Leads" and "Go to My work", with no rows, "shown" or "As of". Unit test with a 403 stub.
10. [x] 404: unit test, plus e2e at 390 and 1440. The e2e adds `X-Mock-Scenario: 404` to the list request only, because the `psl_mock_scenario=404` cookie also hits E-ME and the frame then shows its own error card before the page renders.
11. [x] Provider failure: unit tests for 503 and a network error show the eyebrow, the message, "Reference <code> for support." and Try again; Try again makes one new `?limit=20` request. e2e covers a 503, then Try again.
12. [x] No actions: unit test. In the default state the only button is Show more and the only links are the 20 title links (/work/...). No reconcile, resume, cancel, resend or ask text appears.
13. [x] Compact: unit "compact" checks `?limit=10`, 3 rows, no h1, select, button, footer or "shown", As of kept, and one See all link (`/exceptions`, or the given `seeAllHref`). The 403 and empty states render inside it with h3.
14. [x] Exports: `index.ts` exports both. `grep -rn "@/app\|src/app" frontend/src/features/exceptions` returns nothing.
15. [x] Phone: e2e at 390 shows 20 cards (tag, since, link, doing, "Who acts: …") and scrollWidth ≤ 390. Show more and Try again are each at least 44px tall.
16. [x] axe (wcag2a/2aa/21a/21aa/22aa): no violations for the default, empty and both no-access states at 1440 and 390, the error state, and the W-1503 page. Tabbing to the title link and Show more gives a 2px solid outline (desktop; the title link also at 390).
17. [x] Mock contract: `tests/exceptions-mock.test.ts` and `mock-contract.test.ts` pass:
    - 200 for finance_lead and none, 403 for pm, and 401/403/404 via the scenario header;
    - limit=10 cursors walk all 25 rows once, in order;
    - limit=7 counts as 20; `nonsense` and `o:99` cursors give the first page;
    - the empty cookie returns `items: []`.
18. [x] Rows match items: "rows match their work items" (file exists, same title, state per kind, no actionable task). The existing "every fixture in fixtures/work is schema-valid" check passes for W-1501 to W-1524 (`sample: true`).
19. [x] Rows open their item: in e2e, the first title opens /work/W-1005 ("Kora Logistics · Milestone 1 invoice"), and W-1503 opens its own item ("Northwind Clinics · Weekly client update").
20. [x] Work item link: the unit test renders `NextStep` for all 11 states and exactly the 5 listed show the link. In e2e, W-1005 shows it and W-1003 and W-1006 do not.
21. [x] Shared edits small: `git diff 435f158 -- frontend/mock/server.mjs` is 3 added lines plus the changed M1 line. WorkItemOverview changes only the constant and NextStep; mock-contract changes only the map and its use in the loop. Nothing under src/api, src/shell, architecture or delivery changed.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-06 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exits 0: Django check, npm ci, lint (0 warnings), typecheck, vitest with 15 files and 359 tests passing, and next build (`/exceptions` listed as static).
- `cd frontend && E2E_PORT=3601 MOCK_PORT=3602 npm run test:e2e`: 97 passed, 14 of them in `e2e/exceptions.spec.ts`.
- I looked at the 1440 and 390 screenshots and fixed one thing: the tag column now stays on one line.
- `frontend/test-results` deleted afterwards. All results are mock results (contract mock, v4); no real backend was used.

## Blocked
