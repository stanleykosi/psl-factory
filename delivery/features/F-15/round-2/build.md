STATUS: READY
COMMIT: abf4b7a0660a481a3b97648b400f86fe8bdcce4c
BUILDER: builder
LANE: full

## Summary
- Phone bar now fits at 320, 360 and 375px: below 380px the sides are 8px, the wordmark 13px and the bell-to-Start gap 4px. The wordmark ends at least 8px before the bell and every control stays 44px. The 390px boards are unchanged (16px sides).
- The tight header (2px link padding, 32px bell) now applies only at 720-759px. From 760px up the earlier 4px link padding is back, and the bell and the name are 8px apart from 720 to 1079 (12px from 1080).
- After Open or a footer link on phone, focus lands on the bell of the new page (the phone bar remounts on a route change, so the bell is looked up again).
- A list read that returns after a mark-read no longer brings the badge back up; a 401 on mark-read stops further reads; the drawer top offset is recomputed when the viewport crosses 720px; the scrim uses `--scrim`.
- Gate (`delivery/checks.sh`) passes; full e2e suite 318/318 (one run had 2 failures from my own first CSS version at 390; fixed and the three affected specs re-run green).

## Changes
- `frontend/src/styles/shell.css`: section (g) tight band narrowed to 720-759px with a 4px item gap and 8px bell-to-name; 720-1079 keeps the flex gap as the bell-to-name space; new `max-width: 379.98px` phone block.
- `frontend/src/features/alerts/alerts.css`: drawer scrim `background: var(--scrim)`.
- `frontend/src/shell/AppShell.tsx`: remembers which bar opened the drawer and looks its bell up again on close; `onLeave` (Open, footer links) re-focuses the bell after the path changes.
- `frontend/src/features/alerts/AlertsDrawer.tsx`: `onLeave` prop; top offset in its own layout effect keyed on `phone`; passes `feed.stop` to `useOpenAlert`.
- `frontend/src/features/alerts/AlertParts.tsx`: `useOpenAlert` takes an optional `onError` and reports an `ApiError` from the mark-read.
- `frontend/src/features/alerts/useAlertsFeed.ts`: keeps ids marked read this session and re-applies them (and the badge) to a list that arrives later; `stop(error)` sets the 401 stop.
- Tests: `tests/alerts-bell.test.tsx` (phone Open and footer focus, stale refresh, 401 on POST, offset on resize); `e2e/alerts-bell.spec.ts` (phone bar at 320/360/375/390, Open and Alert settings focus on phone, top bar at 720/760/900/1079/1080/1440, scrim assertion updated to the token colour `rgba(31, 36, 39, 0.45)`).

## Fixes
- UI-1-1 | abf4b7a | phone bar below 380px tightened; e2e asserts brand-to-bell gap of 8px or more at 320/360/375/390
- UI-1-2 | abf4b7a | tight layout only at 720-759px; 4px link padding restored from 760; 8px bell-to-name at 720-1079
- TECH-1-1 | abf4b7a | focus returns to the new bell after Open and footer links; unit and e2e tests on phone
- TECH-1-2 | abf4b7a | session-read ids re-applied to a late list, badge count corrected
- TECH-1-3 | abf4b7a | 401 on mark-read stops further reads (test)
- TECH-1-4 | abf4b7a | offset recomputed when `phone` flips (test)
- UI note (scrim token) | abf4b7a | `var(--scrim)`

## Acceptance criteria
1. [x] No overlap on phone at 320/360/375 with at least 8px: measured in e2e (`phone bar at narrow widths`), passes; screenshots `round-2/visual/phone-bar-320.png`, `phone-bar-360.png`.
2. [x] Header at 720, 760, 900, 1079, 1080, 1440 has no overlap or cutting, 8px or more bell-to-name: e2e `top bar across 720 to 1440` passes. Measured on the production build (x ranges): 720 links 188-467, bell 473-505, name 513-578 (not cut), Start ends 692; 760 links 192-491, bell 505-541, name 549-614; 900 bell 645-681, name 689-754. Screenshots `top-bar-720.png`, `top-bar-900.png`.
3. [x] Focus after Open and footer link on phone: unit tests and e2e at 390.
4. [x] Round-1 behaviours (feed counts, drawer, tabs, axe) unchanged: bell spec and full e2e pass.

## Validation
- `bash delivery/checks.sh` in the worktree: exit 0, 43 files, 1131 tests, lint and typecheck clean.
- `npx playwright test` full suite: 316 passed and 2 failed on the first run (`frame.spec.ts` back-link left offset 16 and `start-work.spec.ts` right inset 16 at 390, caused by my first 400px breakpoint); breakpoint moved to 380px; `alerts-bell`, `frame` and `start-work` specs re-run: 80 passed.
- Visual check on a production build served on ports 4801 (app) and 4802 (mock), then stopped by port. The measurements above come from that build.
- Not re-run after the 400 to 380 change: the other specs in the suite, which passed with the 400 version and do not touch widths between 380 and 400.
- `test-results` removed; no node_modules link.
- A first cleanup attempt used a broad `pkill`, which the permission system refused; I did not retry it and stopped the two servers by port instead.

## Blocked
None.
