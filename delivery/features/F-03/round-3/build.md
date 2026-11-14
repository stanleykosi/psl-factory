STATUS: READY
COMMIT: 3f684410f771cf53c1103d40aaa7977b09c084b3
BUILDER: builder
LANE: full

## Summary
- `/work/[id]` and `/work/[id]/history` keep all the round-2 behaviour. Round 3 changes only how the station track is laid out and coloured.
- Below 1080px (the bp-desktop token) the stations are a vertical list with the status on the right, the same as on the phone. The row of boxes appears only from 1080px. Between 720px and 1080px nothing is clipped and nothing scrolls sideways (UI-2-1).
- From 1080px the effect-uncertain station is a solid amber block with white text, as on SCR-02-desktop-effect-uncertain. In the vertical list it stays a pale amber row, as on SCR-02-mobile-effect-uncertain.
- The gate passes (142 unit tests). All 47 e2e tests pass, 9 of them new.

## Design-owner decisions recorded (14 Nov 2026, design engineer)
- Station layout: below 1080px (bp-desktop) the stations are the vertical list at every width. The row of boxes appears only from 1080px. The coordinator to update spec.md Screen states item 5 and AC 4.
- Effect-uncertain station: in the row (from 1080px) it is a solid amber block with white text, using the `--waiting` background and border with `--on-strong` text. In the vertical list it keeps the pale amber row (`--waiting-tint` / `--waiting-ink`). Contrast check: white (#FFFFFF) on `--waiting` (#8A5A00) is 5.93:1. This passes WCAG AA for normal text (4.5:1), so I did not need a new colour. Only design-system tokens are used.

## Changes
- `frontend/src/features/work-item/work-item.css`:
  - The station-list rules moved out of the `max-width: 719.98px` block into their own `max-width: 1079.98px` block. The facts and history phone rules stay at 720px.
  - New `min-width: 1080px` rule: `.psl-station--waiting.work-station--uncertain` uses `var(--waiting)` for background and border and `var(--on-strong)` for text.
  - Comments updated.
- `frontend/src/features/work-item/WorkItemOverview.tsx`: `StationTrack` takes an optional `state`. When the item is `effect_uncertain`, the current station gets `work-station--uncertain`. `WorkItemOverview` passes `item.state`. The region comment now describes the 1080px rule.
- `frontend/tests/work-item.test.tsx`: new unit test. Only the current station of an effect-uncertain item gets the uncertain class, and a waiting item gets none. The existing W-1005 assertion now expects the exact class list including `work-station--uncertain`; it is still an exact match, so the test is not weaker.
- `frontend/e2e/work-item.spec.ts`: new tests on W-1005:
  - At 760, 900 and 1079: a vertical list of 7 rows, stacked, with the same left edge, every row inside the track, no scroll inside the track and no sideways scroll on the page.
  - At 1080 and 1440: a single row with all 7 stations inside the track, no scroll inside the track and no sideways scroll on the page.
  - At 1440 and 1080, the effect-uncertain station's computed colours are rgb(138, 90, 0) with white text. At 1079 and 390 they are rgb(255, 241, 214) with rgb(110, 71, 0) text.

## Fixes
- UI-2-1 | 3f68441 | Below 1080px the stations are the vertical list, not a clipped row. The row appears only from 1080px. e2e covers 760, 900, 1079, 1080 and 1440.
- UI-2 note (effect-uncertain station) | 3f68441 | Following the design-owner decision, from 1080px it is solid `--waiting` amber with `--on-strong` white text (5.93:1). Below 1080px it stays the pale amber row. Unit and e2e tests cover it.

## Acceptance criteria
1. [x] W-1004 shows six facts: unit test and e2e still pass.
2. [x] Unknown or missing facts read "Unknown": unit tests pass.
3. [x] State tag wording and class for all 11 states: unit test passes.
4. [x] Station track:
   - The 7-status mapping and `aria-current` unit test passes.
   - Per the design-owner decision, it is a vertical list below 1080px. e2e checks 390, 760, 900 and 1079.
   - It is a row with all 7 visible from 1080px. e2e checks 1080 and 1440.
   - Page `scrollWidth` is never wider than the viewport.
   - Screenshots of W-1005 at 900 (list), 1080 (row with solid amber Deliver) and 1440 checked.
5. [x] Agent card never offers a decision: unit tests pass.
6. [x] Reduced motion: both e2e motion tests pass.
7. [x] Decision link only when the person can act: unit tests pass.
8. [x] Next-step callout on W-1005: unit test passes, and visible in the screenshots.
9. [x] SAMPLE DATA with the API mode set to live: unit test passes.
10. [x] No access (403/404, grey tag, dark button): unit tests and the W-1099 e2e pass.
11. [x] 401 shows SignedOutState with next=/work/W-1001: unit test passes.
12. [x] Error card with Try again: unit test passes.
13. [x] History order and WAT times: unit test passes.
14. [x] Restricted rows: unit test passes.
15. [x] History is read-only: unit test passes.
16. [x] Filter and paging: unit test and the e2e history test pass.
17. [x] Mock per-id selection, fallback and history parameters: mock-contract tests pass.
18. [x] Every fixture is schema-valid: the directory test passes.
19. [x] Polling, including access lost on a poll: unit tests pass.
20. [x] Accessibility: axe e2e on W-1001, W-1003, W-1004/history and W-1099 at 390 and 1440 shows no violations. The focus-ring e2e passes.
21. [x] Gate: `delivery/checks.sh` exits 0.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-03 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0: lint, typecheck, vitest (142 passed) and next build. Run on the final tree before commit.
- `cd frontend && E2E_PORT=3201 MOCK_PORT=3202 npm run test:e2e`: 47 passed.
- Visual check: `next start -p 3201` against the mock on 3202. I took Playwright screenshots of /work/W-1005 at 900, 1080 and 1440, saved as:
  - `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/r3-w1005-900.png`
  - `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/r3-w1005-1080.png`
  - `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/r3-w1005-1440.png`

  I stopped only the processes listening on 3201 and 3202.
- Pushed with `git push origin refs/heads/fe-workitem-open-one-work-item-and-read-its-history:refs/heads/fe-workitem-open-one-work-item-and-read-its-history` (4f3831d..3f68441). `git status --porcelain` is empty.

## Blocked
