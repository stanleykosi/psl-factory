STATUS: BLOCKED
COMMIT: 836563e79064f05dcd3f68df5535fae7459d5528
BUILDER: builder
LANE: full

Handed over mid-round at the coordinator's request (Codex continues). Code is pushed and the worktree is clean; the round is unfinished (see "What is left").

## Summary
- `/my-work` reads the live `GET /api/v1/work` and `GET /api/v1/work/counts` through the F-62 adapter. `isV7Row` and the v7 types are gone.
- Eight tabs (Needs me, Waiting on others, Started by me, Active, Decisions, Exceptions, Unassigned when counted or named, Verified). Counts come only from `/work/counts` ("N+" with the accessible name "at least N" when the total is unknown).
- New row layout: kind, title link `/work/{id}`, line title, reference, station bar, state with status label, owner, start age and update time.
- Rows per page, state filter, search, line and project filters, the 15 s refresh with "Couldn't refresh", coverage notes, and the caught-up view without the v7 groups.
- F-88 merged (main eb100065 merged in): the Unassigned tab is F-88's `UnassignedBids` with the uuid `?assign=`; it makes no `queue=unassigned` work-list request.

## Changes
- `src/features/work-list`: `useWorkList` takes `state`, `limit`, `enabled`; exposes `total`, `totalComplete`, `pageSize`, `refresh()`; exports `mergeRefresh`. New `useWorkCounts.ts`. Types gain `WorkLimit`, `WorkCounts`.
- `src/features/my-work`: `MyWork.tsx`, `model.ts`, `WorkRows.tsx`, `FilterPanel.tsx`, `CaughtUp.tsx`, `my-work.css` rewritten on the live shape. The "Verified outputs" link is removed (`grep my-work__verified` is empty).
- Shared components (additive): `Tabs`/`CountBadge` (`atLeast`), `ShowMore` (`moreLabel`), `ListToolbar` (`maxLength`).
- Mock: `mock/live-work.mjs` serves all eight queues with `limit`, `state`, `total`, plus `liveWorkCounts`; `mock/server.mjs` routes `GET /api/v1/work/counts` (scenario `counts_500`) and treats a request as live when it names a live-only queue or carries `page`. The decision desk's `needs_me&limit=50` still gets v7.
- Tests: rewritten `tests/my-work.test.tsx`, `tests/my-work-model.test.ts`; added to `tests/work-list.test.ts`; new `tests/mock-live-my-work.test.ts`; `e2e/my-work.spec.ts` moved to the live shape.
- `e2e/rfp-assign.spec.ts` was removed on main by F-88; nothing to restore.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Requests are `work?queue=needs_me&page=1&limit=10` and `/work/counts`; no `cursor`/`waiting_on`/`counts`: `my-work.test.tsx` "what the screen reads"; grep for `waiting_on|E-WORK-LIST|isV7Row` in `src/features/my-work` is empty.
2. [x] Eight tabs and queue values; `done`/`waiting_on_others` fall back: tests "queue tabs" and the model test.
3. [x] Row content and `/work/412` href: "rows" test. Not looked at in a browser at 1440 and 390 by me; the e2e at both widths passed (see Validation).
4. [x] Null owner/kind/reference/station: "draws a row with nothing optional".
5. [x] Tab counts, five cases: "queue tabs" tests.
6. [x] Records you can see (sum of `lines[].open`, "at least" when limited, absent without counts). Wording follows Q2a: "N open records you can see".
7. [x] Limit 10/20/50, restart at page 1, URL rules, 8/15 dropped: tests and e2e.
8. [x] State filter and chip, no "Waiting on": filter test.
9. [x] q/line/project and late answers dropped: "search" tests, adapter tests.
10. [x] Empty pages skipped, "Keep looking" after ten: tests.
11. [x] Result count rules: tests.
12. [x] Coverage notes: test.
13. [x] Caught-up view with `mine` count known or unknown: tests.
14. [x] "No work matches" and Clear filters: test and e2e.
15. [x] 403/401/500/network states: tests.
16. [x] Counts failure does not blank the list and the reverse: tests.
17. [x] Invalid URL values dropped: model tests (family of inputs).
18. [x] Unassigned: F-88 list, no `queue=unassigned` work request, uuid `assign`: "Unassigned (F-88)" tests and `assign-pm.test.tsx` pass.
19. [x] 15 s refresh of list and counts, failed refresh keeps rows: fake-timer tests.
20. [x] Verified tab replaces the link; `/verified` untouched.
21. [x] Existing `useWorkList` callers send no `limit`/`state`: adapter tests.
22. [~] Focus moves to the first added row after Show more (tested); rows-per-page keeps focus on the chosen size (added). Tab order not separately tested.
23. [x] Mock serves all eight queues and counts: `mock-live-my-work.test.ts`.

## Validation
- `tsc --noEmit` and eslint on the changed folders: clean (before the last two merges).
- Single vitest files passed: `my-work`, `my-work-model`, `assign-pm`, `work-list`, `mock-live-my-work`, `shell-live`, `next-config` (the last was started but its result was not read after the final main merge; re-run it).
- Playwright `e2e/my-work.spec.ts` (through the lock, production build, ports 4984/4985): 15 passed, including axe at 1440 and 390, before the F-88 merge.
- Full Playwright suite on the merged tree was started and I stopped it by PID after 190 of ~1100 tests. Failures seen so far: `assistant.spec.ts` (5 tests: axe/start draft, lines 47, 158, 180, 284) and `ceo.spec.ts` (2 tests: My work tabs on Done, and a `/work/W-5001` link). The assistant ones are probably not F-63 (compare with main); the ceo ones are F-63 (v7 ids and the Done tab).
- An earlier full run on the pre-merge tree (cut short when the merge removed mock fixtures) also showed: `conformance.spec.ts:54` (My work filters at 390), `hr.spec.ts:21` and `:94`, `frame.spec.ts:381`, `exceptions.spec.ts:48/58`, `delivery-release`, `engagement-planning:147`, `issue-detail:77`, `money:65`, `payments`. Not yet triaged against main.
- Servers: my Playwright run and the app/mock on 4984/4985 were stopped by PID. Nothing of mine is running.

## What is left
1. Re-run the full Playwright suite once on the merged tree through the lock; triage each failure against main. For specs that exercise My work (`ceo`, `hr`, `conformance` filters, `demo`, `frame`, likely `exceptions` and `decide-board`): update to the live shape with the same intent. The v7 specs use the Done tab, `/work/W-xxxx` links and demo-run rows; the live mock serves integer ids and no demo rows, so either keep those personas on v7 for that flow or give the mock the matching live rows. Nothing was weakened.
2. Fidelity: one run on a production build through the lock with `round-1/fidelity/run.sh` (SCR-01 boards at 1440 and 390; finance_lead with `psl_mock_worklist=board`, pm for the empty boards). Not run. Then write `fidelity-exceptions.json` in the feature folder (approved_by "design engineer, 24 Nov 2026, D-202") for: waiting-on filter, agent avatar, "While you're free", "Where your work is" groups, relabelled Age/STARTED column, "Done" to "Verified", and the extra tabs. The two filter boards (`SCR-01-desktop-filter`, `SCR-01-mobile-filter`) are left out of the run because the tool cannot open the filter panel; they are covered by component and e2e tests.
3. The mock's board dataset (`psl_mock_worklist=board`) is served in live shape from `personaData`; check the boards' text still lines up before scoring.
4. The builder checklist (`/Users/Hunchoo/psl-factory/delivery/builder-checklist.md`) was read but not walked item by item.
5. Live check against Django (qa-seed or live-lead) was not done: confirm that `lines[].open` excludes stopped and verified rows (spec assumption) and how the Unassigned count and 403 behave.

## Blocked
Not blocked by a dependency: this is a hand-over. The remaining work above needs a builder with lock time for the full suite and the fidelity run.

## Finish (D-210)
COMMIT: 0b1db7014b218b4c586106e034a82a11ecae870b (pushed to fe-connect-1-my-work-live)

No review agents, fidelity run or live Django check, by D-210.

- Merged origin/main (043fd0c7, with F-75, F-78, F-119B, F-103) without conflicts; `node --check mock/server.mjs` is clean.
- e2e changes (assertions moved to the specified behaviour, none weakened):
  - `ceo.spec.ts`: the Done tab is now Verified and checks a verified output row (`INV-0398 · Lagoon Health`); the row link is `/work/5001`, then the test opens the sample decision page at `/work/W-5001` (the mock draws that page under its v7 id). The alerts test at line 79 is untouched (not My work).
  - `hr.spec.ts:21`: Done to Verified, same verified row.
  - `conformance.spec.ts:54`: the "Waiting on" select is gone from the filter panel (spec), so the 44px check covers the two remaining selects.
- Checked against origin/main (same specs, same ports): these fail on main without F-63 and were left alone: `assistant.spec.ts` lines 47 (CV-2401 after the start, 1440 and 390), 158, 180, 284; `exceptions.spec.ts` lines 48 and 58 at both widths; `frame.spec.ts:381` (720px); `hr.spec.ts:94`. `assistant.spec.ts:321` failed once in the batch and passed alone, so flaky.
- Not re-checked on main, not triaged: `delivery-release`, `engagement-planning:147`, `issue-detail:77`, `money:65`, `payments` (the round-1 full run; outside the specs named for this finish).
- Results: Playwright on a production build, ports 4960/4961, through the lock: `my-work`, `ceo`, `hr`, `conformance`, `frame`, `exceptions`, `assistant`, `demo`, `decide-board` first run 98 passed, 16 failed, 3 skipped; after the fixes `ceo`, `hr`, `conformance`, `my-work` and `assistant:321` 38 passed, 2 failed (`ceo:33`, fixed and re-run 1 passed; `hr:94`, fails on main). Vitest `my-work`, `my-work-model`, `assign-pm`, `work-list`, `mock-live-my-work`, `shell-live`, `next-config`: 7 files, 235 tests passed. `tsc --noEmit` and eslint clean.
