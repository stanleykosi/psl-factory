STATUS: READY
COMMIT: 4f3831d4aef9088f75beb7aaaeda518fa14ee3f4
BUILDER: builder
LANE: full

## Summary
- `/work/[id]` and `/work/[id]/history` are unchanged in behaviour from round 1, apart from the round-2 fixes below. The gate and all 38 e2e tests pass at this head.
- The no-access board now matches SCR-02-desktop-permission: a grey "NO ACCESS" tag and a filled dark "Back to my queue" button (UI-1-2).
- Below 720px the stations are now a vertical list with the status on the right, as on the approved mobile boards. This replaces the sideways-scrolling row (design-owner decision, 14 Nov 2026). From 720px up the row of boxes is unchanged.
- The mock and the fixture-directory test now treat only `W-<digits>.json` as items and `W-<digits>.history.json` as histories. F-04 sidecars such as `W-1201.next.json` will not break them (TECH-1-1, TECH-1-2).
- If a poll gets 401, 403 or 404, the page drops the old item and shows the signed-out or no-access state, and polling stops (TECH-1-3).

## Changes
- `frontend/src/features/work-item/WorkItemStates.tsx`: on `NoAccessState`, the eyebrow is now `psl-tag psl-tag--neutral` and the link uses `psl-btn psl-btn--dark psl-btn--lg`. The board's dark button is the bundle's `--dark` variant; the plain `psl-btn` is action blue.
- `frontend/src/features/work-item/work-item.css`: adds `.work-noaccess__tag` (align start). Below 720px, adds rules that lay the stations out as a list: a 2px ink frame, rows on a `30px / 1fr / auto` grid, 1px rule-soft dividers, and a status tint for the current station only. Agent stations are action tint (blue), person stations signal tint, waiting stations waiting tint, and verified stations verified tint. Done and not-started stations are plain surface, with muted ink for not started. Only token variables are used, and the bundle CSS is untouched.
- `frontend/src/features/work-item/WorkItemOverview.tsx`: updated the comment on the track region. No markup change.
- `frontend/src/features/work-item/useWorkItem.ts`: the poll catch now sends an `ApiError` of kind unauthenticated, forbidden or not_found to the error state and stops scheduling. `WorkItemView` already renders those as SignedOutState or NoAccessState. Other errors still keep the last good item and show the warning.
- `frontend/mock/server.mjs`: per-id lookup only happens when the path id matches `^W-\d+$`. Anything else, including `W-1004.history`, falls back to the default fixtures.
- `frontend/tests/mock-contract.test.ts`: the fixture-directory test filters on `^W-\d+(\.history)?\.json$`. A new test checks that `/api/v1/work/W-1004.history` returns the default E-WORK-ITEM. Existing tests are not changed.
- `frontend/tests/work-item.test.tsx`: the no-access test now asserts the tag and button classes. A new polling test covers 403, 404 and 401 on a poll: the item is gone, the matching state shows, and there are no further fetches.
- `frontend/e2e/work-item.spec.ts`: replaced the "only the track scrolls sideways" test. The new test checks that at 390px the track does not overflow, that rows stack top to bottom with the same left edge and width, and that each status sits on the name's line to its right. The page-width assertion (`scrollWidth <= 390`) is kept.

## Fixes
- UI-1-1 | none (decision) | The design owner decided on 14 Nov 2026 to keep the design system's blue agent-station colour (`psl-station--agent`); the board's amber is superseded. No code change. The phone list follows the same decision: the agent row uses the blue action tint. The reviewer can close this on that decision.
- UI-1-2 | 7d2a270 | The no-access board uses a grey `psl-tag--neutral` "NO ACCESS" tag and a filled dark `psl-btn--dark psl-btn--lg` "Back to my queue", as on SCR-02-desktop-permission.
- UI note (phone station track) | dca0c3d | Design-owner decision (14 Nov 2026): below 720px all stations show as a vertical list with the status on the right, replacing the sideways scroll. The e2e test was changed to match. spec.md still says "Below 720px the track scrolls sideways" (Screen states item 5, AC 4). The coordinator should update the spec text to this decision.
- TECH-1-1 | 99b181f | The fixture-directory test only treats `W-<digits>.json` as items and `W-<digits>.history.json` as histories, and ignores other sidecars.
- TECH-1-2 | 99b181f | The mock only does per-id lookup for `^W-\d+$` ids, so `/api/v1/work/W-1004.history` now returns the default item. A test covers this.
- TECH-1-3 | 4f3831d | A 401, 403 or 404 on a poll replaces the stale item with the signed-out or no-access state and stops polling. Other poll failures still keep the last good item with the warning. A unit test covers this.

## Acceptance criteria
1. [x] W-1004 shows six facts: unit test and e2e "W-1004 shows the A-WORKITEM facts" (unchanged, passing).
2. [x] Unknown or missing facts read "Unknown": unit tests pass.
3. [x] State tag wording and class for all 11 states: table-driven unit test passes.
4. [x] Station track: the 7-status mapping and `aria-current` unit test passes. At 390px the page `scrollWidth <= 390`. Per the design-owner decision, the stations are now a vertical list with the status on the right, and the e2e asserts this. I checked screenshots of W-1003 and W-1005 at 390, and W-1003 at 1440 still shows the row of boxes.
5. [x] Agent card never offers a decision: unit tests on W-1003 and W-1002 pass.
6. [x] Reduced motion: both e2e motion tests pass.
7. [x] Decision link only when the person can act: unit tests pass.
8. [x] Next-step callout: the W-1005 unit test passes, and the 390 screenshot shows the warning callout with no buttons.
9. [x] SAMPLE DATA with the API mode set to live: unit test passes.
10. [x] No access: unit tests for 403 and 404 pass and now also assert the grey tag and dark button classes. The e2e for W-1099 passes. I checked a screenshot of /work/W-1099 at 1440: grey tag, dark filled button, no id.
11. [x] 401 shows SignedOutState with next=/work/W-1001: unit test passes.
12. [x] Error card with Try again: unit test passes.
13. [x] History order and WAT times: unit test passes.
14. [x] Restricted rows: unit test passes.
15. [x] History is read-only: unit test passes.
16. [x] Filter and paging requests: unit test and the e2e history test (10 rows, then 12 after Show more, then no Show more) pass.
17. [x] Mock per-id selection, fallback and history parameters: mock-contract tests pass, plus the new sidecar-id test.
18. [x] Every fixture is schema-valid: the directory test passes, now limited to `W-<digits>` item and history files.
19. [x] Polling: all unit tests pass, plus the new access-lost-on-poll test.
20. [x] Accessibility: axe e2e on W-1001, W-1003, W-1004/history and W-1099 at 390 and 1440 has no violations. The focus-ring e2e passes.
21. [x] Gate: `delivery/checks.sh` exits 0.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-03 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0: lint, typecheck, vitest (7 files, 141 tests passed) and next build. I ran it on the final tree before committing; there were no code edits after it.
- `cd frontend && E2E_PORT=3201 MOCK_PORT=3202 npm run test:e2e`: 38 passed, including the 14 work-item tests.
- Visual check: I ran `next start -p 3201` against the mock on 3202 and took Playwright screenshots of /work/W-1003, W-1005 and W-1006 at 390x844, and of /work/W-1003 and W-1099 at 1440x900. The screenshots are in `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/` (m-1003.png, m-1005.png, m-1006.png, d-1003.png, d-1099.png). I stopped only the processes listening on 3201 and 3202.
- Pushed with `git push origin refs/heads/fe-workitem-open-one-work-item-and-read-its-history:refs/heads/fe-workitem-open-one-work-item-and-read-its-history` (9bb054b..4f3831d). `git status --porcelain` is empty.

## Blocked
