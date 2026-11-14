STATUS: READY
COMMIT: 55e81940bdf715f222ebd7f15f26a9150d981915
BUILDER: builder
LANE: full

## Summary
- `/my-work` is the SCR-01 My work page. It reads E-WORK-LIST only, keeps its state in the URL, refreshes every 15 s, and builds every C7 state. Round 1 behaviour is unchanged.
- Round 2 fixes UI-1-1. On phone cards the kind tag (DECIDE, DO, FIX, STARTED) now always sits on its own line above the title, as `SCR-01-mobile-lead.dc.html` draws it (a column with 4px gap, aligned left). Every card header now has the same layout and spacing.
- A new e2e test at 390px checks all 20 cards. On each one the tag ends above the title, the tag and title share a left edge, and the offsets match every other card. Without the CSS fix the test fails; with it, it passes.
- Round 2 also fixes TECH-1-2: the mock now gives persona `none` an empty 200 for `queue=unassigned`, as C8 says. It used to return a 403.
- `server.mjs` is unchanged from round 1 (one import plus one branch), as the coordinator asked.

## Changes
- `frontend/src/features/my-work/my-work.css`: adds `.my-work__card .my-work__work { flex-direction: column; align-items: flex-start; gap: var(--space-1); }` and updates the phone-card comment. The desktop table keeps the tag inline beside the title, because the rule is scoped to `.my-work__card`.
- `frontend/e2e/my-work.spec.ts`: a new `phone 390 card headers` test. It measures the tag and title boxes against each card's box.
- `frontend/mock/work-list.mjs`: the 403 for `queue=unassigned` now applies only to non-lead personas other than `none`. A comment cites C8.
- `frontend/tests/mock-work-list.test.ts`: the test now also checks that persona `none` gets 200 for `queue=unassigned`, with empty items and zero counts, validated against the v3 schema.

## Fixes
- UI-1-1 | a3ecdcd | Phone cards stack the kind tag above the title on every card (following SCR-01-mobile). New e2e test checks header alignment at 390px.
- TECH-1-2 | 55e8194 | The mock gives persona `none` an empty 200 for `queue=unassigned` instead of a 403. Covered by a mock test.

Left as is:
- TECH-1-1 (non-blocking, owner integration): the textual merge conflict with F-03 in `server.mjs` is for the integration owner to resolve (keep both branches). The coordinator said to keep the `server.mjs` change as it is.
- TECH-1-3 (non-blocking): `navigate` reads `viewRef.current`, so two navigations in one tick would drop the first. No current action does that, and the reviewer gave it as something to remember, not a change to make. Fixing it means reworking URL state for a case that does not happen.

## Acceptance criteria
Criteria 1 to 22 are as in round 1 (see round-1/build.md). They were re-run this round through the gate and the full e2e suite. All of them pass.
1. [x] UI-1-1, card headers consistent at 390: `phone 390 card headers › kind tag sits on its own line above the title on every card` passes. For all 20 finance_lead cards the tag is stacked, its left edge matches the title's, and every card's offsets equal the first card's. With the CSS change stashed, the same test fails (`stacked` false on card 1, which has a short title).
2. [x] C8 persona `none`: `tests/mock-work-list.test.ts` passes, including the new unassigned assertion.
3. [x] Desktop unchanged: all 1440 e2e tests pass, including axe and the focus rings.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-02 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exits 0. Results: Django check clean; lint with 0 warnings; tsc passes; vitest 9 files, 192 tests passed; `next build` passes and `/my-work` prerenders.
- `cd frontend && E2E_PORT=3301 MOCK_PORT=3302 npm run test:e2e`: 39 passed (1.2m). The 39 are 15 in `my-work.spec.ts` (14 from round 1 plus the new one) and 24 in `frame.spec.ts`.
- Negative check: the new test alone, with the round-2 CSS stashed, gives 1 failed.
- Afterwards nothing is listening on 3301 or 3302. `git status --porcelain` is empty, and HEAD equals `origin/fe-mywork-my-work-shows-a-person-s-queues-with-sea` (55e8194).

## Blocked
None.
