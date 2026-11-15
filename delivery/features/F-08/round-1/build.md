STATUS: READY
COMMIT: ea088f9b0606c0e8e5fdfa1d047cd46619a96d13
BUILDER: builder
LANE: full

## Summary
- `/overview` now shows SCR-06 instead of the placeholder. It has the "FACTORY FLOOR · UPDATED <time> WAT" eyebrow, the four E-OVERVIEW totals, one row per returned line with a square and a screen-reader count per station, and each line's `note` word for word. It polls every 15 s only while the tab is visible. The browser never sums or derives a figure.
- A Flat / 3D floor switch (Flat by default) loads `features/floor/Floor3D` with a dynamic `import()` only after 3D is chosen. The floor is plain three.js: a fixed angled camera, one strip per line, a block per station, a count sprite, and up to 10 tokens. It renders on demand, with a 280 ms ease-out only when a poll changes a station. Reduced motion, no WebGL, a width under 720px, or any failure gives the flat view; a failure also shows a warning.
- Under the legend, the exceptions place has the h2, a plain "See all exceptions" link to `/exceptions` and the My work line. There is no E-EXCEPTIONS fetch or import.
- The mock serves E-OVERVIEW from the SCR-06 board, with `empty`, `zero` and `changed` variants picked by cookie `psl_mock_overview`. server.mjs changes by exactly the import, the `M1_OPERATIONS` entry, the dispatch line and one header-comment line.
- `three` 0.187.0 and `@types/three` 0.187.0 are pinned exactly. `npm view` shows both were published on 2026-10-30, more than two weeks ago.

## Changes
- `frontend/package.json`, `frontend/package-lock.json`: `three` 0.187.0 (dependency) and `@types/three` 0.187.0 (devDependency). The lockfile adds only these and their transitive entries (`@dimforge/rapier3d-compat`, `@tweenjs/tween.js`, `@types/stats.js`, `@types/webxr`, `fflate`, `meshoptimizer`). On macOS, `npm install` pruned the optional `@emnapi/core` and `@emnapi/runtime` entries, so I restored them verbatim from the base lockfile. `npm ci` passes.
- `frontend/src/app/overview/page.tsx`: renders `OverviewPage`. The title "Overview · PSL Factory" is unchanged.
- `frontend/src/features/overview/OverviewPage.tsx`: checks `/me` destinations first (`NotOpenState`, no fetch), then renders the factory floor in every state: loading, signed out, not open (403/404), error card, empty, flat, 3D and phone. It also has the View radiogroup with roving focus and arrow keys, the reduced-motion and no-WebGL hints, the fallback callout and the exceptions place.
- `frontend/src/features/overview/useOverview.ts`: the E-OVERVIEW read and D-UPDATES polling, re-implemented locally.
  - A tick is skipped while a request is in flight.
  - A response older than one already shown (by request sequence) is dropped.
  - 401, 403 and 404 stop polling; 5xx and network failures keep polling.
  - It keeps the last `as_of` for "Last loaded …".
- `frontend/src/features/overview/useMedia.ts`: `matchMedia` through `useSyncExternalStore`.
- `frontend/src/features/overview/types.ts`: `Overview` derived from `schema.d.ts`.
- `frontend/src/features/overview/overview.css`: SCR-06 layout from tokens only. It covers the 210px / flexible / 150px rows, 26px squares on a 2px ink rule, the 4-column totals (2 × 2 below 720px), the stacked phone rows, the 480px floor and `.overview__sr`.
- `frontend/src/features/floor/support.ts`: has no three import. It holds `webglAvailable()`, `diffCounts()`, `floorLabel()` and the `FloorProps` type.
- `frontend/src/features/floor/Floor3D.tsx`: the default-export client component.
  - It creates its own canvas, so a remount never reuses a context that was given back.
  - It reads `--ink`, `--signal`, `--surface`, `--steel`, `--font-display` and `--font-mono` at mount.
  - It calls `onFailure` if `WebGLRenderer` throws or on `webglcontextlost`.
  - On unmount it disposes everything and calls `forceContextLoss`.
- `frontend/src/features/floor/scene.ts`: the three.js scene, imported only by Floor3D.
  - A structural change (a line or station added or gone) rebuilds without animation. It seeds the stations that stay with their old figures, so their changes still animate.
- `frontend/mock/overview.mjs`, `frontend/mock/fixtures/E-OVERVIEW.json`, `frontend/mock/fixtures/overview/{empty,zero,changed}.json`: the fixtures follow the board square pattern. Station counts sum to 21 against `in_progress` 18. `changed` changes Pre-sale/Brief 1→2 and Invoices/Milestone 3→1, flips Payroll/Approve `needs_person`, and has `as_of` 15:40:15Z and new totals.
- `frontend/mock/server.mjs`: the three-line seam plus one header-comment line.
- Tests:
  - `tests/overview.test.tsx` (24)
  - `tests/overview-floor.test.tsx` (4)
  - `tests/overview-floor-reject.test.tsx` (1)
  - `tests/overview-imports.test.ts`
  - `tests/floor.test.ts`
  - `tests/mock-overview.test.ts`
  - `e2e/overview.spec.ts` (10)

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Totals as returned. Evidence: `overview.test.tsx` finds dt/dd 18/5/3/28 while the station counts sum to 21. Zero totals with non-zero stations show four 0s.
2. [x] Every line and station in order. Evidence: 8 rows in fixture order. Each `<ol aria-label="<line> stations">` has the fixture's station count, and the text reads "Brief: 1 item" and "Scope: 2 items", covering singular and plural.
3. [x] Square state and tag tone. Evidence:
   - Proposal (0, needs a person) has the `--person` class and ", needs a person".
   - Milestone (3) has the `--work` class and shows "3".
   - Qualify (0) has the `--empty` class and no numeral.
   - Pre-sale reads "1 WAITING" with `psl-tag--person`, and Closing reads "ON TRACK" with `psl-tag--neutral`.
   - "all good" renders verbatim.
4. [x] Coverage time. Evidence: the eyebrow reads "FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT", with `<time dateTime="2026-11-14T15:40:00Z">`.
5. [x] Empty lines. Evidence: the component test, and e2e with cookie `empty`, show four 0 tiles, "No lines to show yet.", no View radiogroup and the link. Axe is clean.
6. [x] All-zero lines. Evidence: the component test and e2e with cookie `zero` show every station `--empty`, no numerals and the notes verbatim.
7. [x] Wrong user. Evidence: pm sees "This section isn’t open to your role." with a `/my-work` link, and no `/api/v1/overview` call is made. `e2e/frame.spec.ts` passes unchanged in the full e2e run.
8. [x] 401, 403 and 404. Evidence:
   - Component: 401 shows the signed-out callout, with the link `/accounts/login/?next=%2Foverview`. 403 and 404 show "The factory floor isn’t open to your role." with the server message and no `<dl>`. Each makes exactly one request after 30 s of fake time.
   - e2e: `page.route` 403 shows the same, with axe clean.
9. [x] Provider failure. Evidence: after a good load, a poll that gets 500 or a rejected fetch shows `role=alert` with the copy, "Last loaded 14 Nov 16:40 WAT." and "Reference server_error|network_error for support.", with no `<dl>` and no Lines section. Try again restores 8 rows.
10. [x] Polling. Evidence:
    - No request at 14 999 ms; one at 15 000 ms.
    - None over 60 s while hidden, then one immediate request on return.
    - With a slow response, a further 30 s of ticks still makes 2 calls in total.
11. [x] Out-of-order. Evidence: a slow poll A is overtaken by Try again B, which has a later `as_of`. After A resolves, B's 99 and 16:41 still show.
12. [x] 3D option. Evidence: with `support` mocked:
    - Reduced motion: no radiogroup, and the motion hint. It takes precedence over no WebGL.
    - No WebGL: no radiogroup, and the device hint.
    - Phone: no radiogroup and no hint.
    - Otherwise: "Flat" checked.
13. [x] three.js loads only after 3D is chosen. Evidence:
    - Component: the `Floor3D` mock factory flag is false in Flat and true after clicking "3D floor". `img` "3D factory floor: 8 lines…" appears, and the flat list stays inside `.overview__sr`.
    - Static: `overview-imports.test.ts` finds no `from 'three'` or static Floor3D import.
    - e2e: no first-load script contains `__THREE__`, and a script loaded after the click does. `next build` puts three in its own chunk.
14. [x] 3D floor. Evidence:
    - `floor.test.ts`: `diffCounts` returns exactly Brief, Milestone and Approve, and `[]` for identical inputs.
    - e2e at 1440: the canvas is visible, 480px high, and has a WebGL context. The rAF count stays flat over 2 s after settling. With `page.clock` plus cookie `changed`, a 15 s fastForward updates the sr texts (Brief 2, Milestone 1, Approve 1 with no "needs a person") and the tiles (19/4/3/29). The rAF count rises and is flat again within 1 s.
    - Screenshot `overview-3d-1440.png` taken (viewport only, see Notes).
15. [x] No-WebGL fallback. Evidence: e2e with `getContext` returning null for webgl/webgl2 shows no switch, the device hint, 8 rows, and 40 station sr texts including "Milestone: 3 items". Axe is clean.
16. [x] Runtime failure. Evidence: the mocked Floor3D's `onFailure()` (`overview-floor.test.tsx`) and a rejected import (`overview-floor-reject.test.tsx`) each show the warning callout, return the flat rows and remove the radiogroup.
17. [x] Reduced motion. Evidence: e2e with `emulateMedia({ reducedMotion: 'reduce' })` shows the hint and no "3D floor". Axe is clean, and a screenshot was taken (`overview-1440-reduced-motion.png`).
18. [x] Exceptions place. Evidence: the component test finds the h2, the link with href `/exceptions` and the My work line, with no `/api/v1/exceptions` call. The `grep -rn "features/exceptions" …` prints nothing.
19. [x] Layouts and accessibility. Evidence:
    - e2e at 1440 (flat, and 3D) and at 390: axe WCAG 2.2 AA shows zero violations, and `scrollWidth <= innerWidth`.
    - Screenshots `overview-1440.png` and `overview-390.png` were taken.
    - At 390: no radiogroup, 2 grid columns, and every name and tag visible.
    - Keyboard: Tab reaches Flat with a 2px solid ring. ArrowRight moves to 3D floor and selects it; ArrowLeft moves back. The link is reachable by Tab.
20. [x] Mock contract. Evidence:
    - `mock-overview.test.ts`: all four fixtures pass Ajv 2020 strict against the v4 schema; `overview()` returns each variant, or the default for an unknown cookie; the server honours the cookie.
    - `mock-contract.test.ts` (unchanged) now covers E-OVERVIEW 200 for all three personas and 401/403/404.
21. [x] Dependency pinned. Evidence: the `node -e` check prints `0.187.0 0.187.0`, the package.json diff is those two lines, and `npm ci` inside `checks.sh` passes.
22. [x] Mock seam. Evidence: `git diff d8e454f -- frontend/mock/server.mjs` shows only the import, the `M1_OPERATIONS` entry, the dispatch line and one header-comment line.

## Validation
- `df -h /System/Volumes/Data`: 13–14 GiB free before installs and builds.
- `npm view three@0.187.0 version` gives 0.187.0, published 2026-10-30T08:09Z. `npm view @types/three@0.187.0 version` gives 0.187.0, published 2026-10-30T18:05Z.
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` in the worktree exited 0:
  - Django check: no issues.
  - `npm ci`, eslint (0 warnings) and `tsc` passed.
  - vitest: 19 files, 376 tests passed.
  - `next build` passed.
- `cd frontend && E2E_PORT=3801 MOCK_PORT=3802 npm run test:e2e`: 93 passed. That includes the 10 in `e2e/overview.spec.ts` and the unchanged `frame.spec.ts`.
- `frontend/test-results` was removed afterwards. No server was left on 3801 or 3802.

## Notes
- PMO-0-4: E-OVERVIEW has no field for line avatars, subtitles ("RFP · commercial") or tag colours, so none are drawn. `note` is shown verbatim in a neutral tag, or in a person tag when any station has `needs_person`.
- PMO-0-5 and Assumption 7 are flagged for product acceptance. The tokens queue in front of each station block, in ink or signal. The count sprite always carries the exact figure, including 0. Motion is a 280 ms ease-out only on poll changes; there is no idle loop.
- Assumption 2: station counts are printed in the squares, and the legend explains them.
- A Playwright full-page screenshot briefly sets the window width to 1px. Under the spec's rule (below 720px means Flat), that correctly drops the 3D floor, so the 3D screenshot is viewport-only.
- `floorLabel` reads "1 line" for a single line and "<n> lines" otherwise.
- Follow-ups (not F-08):
  - (a) Mount F-06's preview in place of the link once F-06 merges.
  - (b) The SCR-12 follow-on after F-07 merges.
- Integration: F-06 and F-07 also append to `M1_OPERATIONS` and add a dispatch line to server.mjs. Keep every lane's entries when merging.
- Two notes on instructions:
  - The session's commit-attribution reminder asked for a `Co-Authored-By` trailer. The user's CLAUDE.md and the coordinator forbid it, so the commits have none.
  - The user's memory asks to confirm before pushing. The coordinator's notes and the delivery contract required this push, so I pushed the task branch only.

## Blocked


## Integration with the base (coordinator, 14 Nov 2026)
After the builder pushed d20a96e, the coordinator merged the base into this branch as ea088f9 (no conflicts): the base gained the decide colour-flake test fix (PR #10), architecture v6 files, delivery records and the removal of tracked .lock files. No F-08 file changed.
