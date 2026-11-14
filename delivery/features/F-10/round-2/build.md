STATUS: READY
COMMIT: 752ab93e4edc6fe7f3b9f85c410b377cff051bc9
BUILDER: builder
LANE: full

## Summary
- The SCR-36 month-end checklist is unchanged apart from two small fixes. Round 1's behaviour, mock and tests all still stand.
- UI-1-1: on phones, the empty "No month-end tasks you can see for October 2026." panel now stays the height of its text. It no longer fills the whole screen.
- UX-1-1: each of the six table "Open" links now carries its row's task title as its screen-reader description, for example "Open, link, Bank statements". The visible text and the link name stay "Open", as the board draws it.
- Fidelity was re-run with the fixed site-wide cookies. Desktop 1440 passes with visual 97.8. Phone 390 passes with visual 97.3, and it now really gets the six `board-phone` cards (round 1 scored 94.9 on seven).

## Changes
- `frontend/src/features/finance/month-end/month-end.css`
  - Inside the phone media query, `.monthend-empty { flex: none; }` is added, with a one-line reason.
  - On phones `.monthend-row` is `display: contents`, so the empty panel sat directly in the full-height column. With the desktop `flex: 999 1 600px` it grew to about 690px.
- `frontend/src/features/finance/month-end/MonthEndView.tsx`
  - Each row's title `<strong>` gets the id `monthend-task-{i}`.
  - `TaskEnd` takes a `titleId`, and the Open `<Link>` sets `aria-describedby={titleId}`.
- `frontend/tests/finance-month-end.test.tsx`: the board test now checks that the six links' descriptions resolve to the six task titles, in order.
- `frontend/e2e/finance-month-end.spec.ts`
  - The "empty month" test, at both 1440 and 390, now checks that the `.monthend-empty` box is under 200px tall. It was 690px at 390 before the fix.
  - The keyboard test now checks that the first Open link has the accessible description "Bank statements".

## Fixes
- UI-1-1 | 752ab93 | Inside the phone media query, `.monthend-empty` is now `flex: none`, so the empty panel is sized to its text. An e2e height check at 390 and 1440 covers it.
- UX-1-1 | 752ab93 | Each Open link is now described by its row's task title through `aria-describedby`, with the visible text and name still "Open". Unit and e2e tests cover it.
  - I tried an `aria-label` of "Open Bank statements" first. It made the fidelity gate FAIL on desktop: the tool matches links by accessible name, so the six board "Open" links counted as missing (coverage 86% with exceptions).
  - The description approach keeps the gate at 100% and still tells the links apart when a screen reader announces them.
  - A screen-reader links list still shows the name "Open" only. If reviewers want a row-specific name, the coordinator would need to approve six fidelity exceptions for the "Open" links.

## Acceptance criteria
Criteria 1 to 17 are as recorded in round-1/build.md. The full unit and e2e suites re-ran green on 752ab93. This round:
3. [x] **Design fidelity.** Both boards were re-run on 752ab93 with the site-wide cookies.
   - SCR-36-desktop at 1440: PASS. Coverage is 95.3% (41/43), or 100% with exceptions. Visual score 97.8.
   - SCR-36-mobile at 390 with `--cookies psl_mock_month_end=board-phone`: PASS. Coverage 100% (23/23), visual score 97.3. The page now served the six-card board-phone data.
   - The only extras are the frame's Menu and PSL FACTORY.
   - Reports are in `delivery/features/F-10/round-2/fidelity/SCR-36-desktop-1440/` and `…/SCR-36-mobile-390/`.
13. [x] **Empty.** e2e "empty month" at 1440 and 390 shows the message. The panel's bounding box is under 200px tall, and the strip and summary text are unchanged.
15. [x] **Accessibility.** axe still reports 0 violations in every state at both widths. The six Open links' descriptions are the task titles: the unit test checks all six, and the e2e test checks "Bank statements".

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-10 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0: Django check, npm ci, lint, typecheck, vitest 15 files / 367 tests, and next build.
- `cd frontend && E2E_PORT=4001 MOCK_PORT=4002 npm run test:e2e`: 107 passed.
- Fidelity ran on `MOCK_PORT=4002 npm run dev -- -p 4001` using `fidelity.mjs` with `--exceptions delivery/features/F-10/fidelity-exceptions.json`. Results are under criterion 3.
- Afterwards I stopped the dev server on 4001/4002, deleted `frontend/test-results`, and confirmed `git status --porcelain` was empty.
- All tests ran against the contract mock (sample data). There is no real backend for E-MONTH-END yet.

## Blocked
