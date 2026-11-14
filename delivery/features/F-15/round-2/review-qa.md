VERDICT: PASS
COMMIT: abf4b7a0660a481a3b97648b400f86fe8bdcce4c
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (frontend production build with the contract mock; F-15 has no backend lane)

## Summary
- I tested head abf4b7a on the shared production build (http://localhost:4811, `next start` from the f-15 worktree, built 21:32 after the 21:27 head commit, clean tree) with the contract mock at http://127.0.0.1:4812. I reset the mock before and after. Data was synthetic: the `needs-you`, `empty` and default scenarios, and the finance_lead, pm and none personas.
- Every spec journey in my brief passed:
  - The bell and badge show on 10 main pages at 1440 and 390.
  - The chip shows only at 1080 and up.
  - The header holds at 720, 760, 900, 1079, 1080 and 1440 on five pages, with Start work last.
  - The drawer opens and closes by click, Escape, scrim and Close, and focus returns on desktop and phone, including after Open and the footer links.
  - Open sends one mark-read with CSRF and still navigates when the POST gets a 500 or the network drops.
  - Reads: one on load, one per open, none on a 70 s or 6 min clock, none after mark-read, none after a 401.
  - The empty, 500/Try again, 401, 403, no-sections and pm states all behave as specified.
  - The phone sheet at 320, 360 and 390 has tabs that work by click and arrow keys.
  - axe found 0 violations at 1440 and at 320/360/390 with the drawer open.
- Full Playwright suite, run once against the build: 316 passed, 2 failed. Both failures open `/frame-fixtures/phone-back`, which returns 404 unless the server sets `FRAME_FIXTURES=1`, and the shared server was started without it. This is the environment, not the product. The same back-link bar passed on three real back-link pages.
- Direct API calls to the mock:
  - Mark-read without CSRF: 403 `csrf_failed`.
  - Mark-read with another person's CSRF: 403.
  - Mark-read with the person's own CSRF: 200; a repeat call also returns 200 with the same body (idempotent).
  - The pm list holds pm's own items only.
- Not proved:
  - The real Django E-NOTIFICATIONS endpoint and server-side ownership. The mock stands in, and the feature has no backend lane.
  - `needs_you` is a PROPOSAL field that only the mock supplies.
  - A 500 and a network drop on the list, and a 401/403/500 on mark-read, were injected with Playwright `page.route`. The mock has no scenario for them.
  - The tab-visibility refresh was triggered by a synthetic `visibilitychange` event.

## Findings
None.

## Verified
- UI-1-1 | verified | Phone bar at 320: Menu 8-52, bell 182-226, + Start 230-312, all 44px tall. At 360: bell 222-266, Start 270-352. At 390: Menu 16-60, bell 240-284, Start 292-374. No horizontal scroll at any width, and the 320 screenshot shows no overlap (`qa-evidence/phone-320-sheet.png`).
- UI-1-2 | verified | Header x ranges on /my-work, /exceptions, /projects, /work/W-1004 and /setup (same on all five):
  - 720: links 188-467, bell 473-505, name 513-578, Start 582-652.
  - 760: bell 505-541, name 549-614.
  - 1080: bell 605-641, chip 641-717, name 729-882, Start 894-1012.
  - 1440: bell 905-941, chip 941-1017.
  - At every width: no link overlaps another, no link wraps, the name is not cut, and there is no horizontal scroll. The last two stops in the bar are "Start work" and "More ways to start".
- TECH-1-1 | verified | After Open on n1 and after Alert settings, focus is on the new page's bell: on desktop 1440 and on phone at 320, 360 and 390. The footer link "See all alerts" does the same on desktop.
- TECH-1-2 | verified (integration level) | After Open on n1 the badge reads 3. After browser back it still reads 3, with the chip at "2 need you". The late-list race itself is covered by the builder's unit test; I did not reproduce it on the build.
- TECH-1-3 | verified | When `/notifications/*/read` returns 401, the person still lands on `/work/w-inv-lh-002`. Reopening the drawer sends 0 further list reads.
- TECH-1-4 | not re-run at integration level | This fix is about the drawer offset when the window is resized while the drawer is open. The sheet sits at top 36 and height 808 (844 viewport) at 320, 360 and 390 when opened at that width. I did not test resizing while open; the builder's unit test covers it.
- UI scrim note | verified | Closing by clicking the scrim works on desktop and on phone. The token colour is covered by the passing `alerts-bell.spec.ts` assertion `rgba(31, 36, 39, 0.45)`.

## Notes
- Journeys and their numbers are in `round-2/qa-evidence/qa-journeys.log`. Highlights:
  - Mark-read requests: `[{"path":"/api/v1/notifications/n1/read","csrf":"mock-csrf-finance_lead"}]`.
  - A double-click on Open sends 1 POST.
  - 401: the Sign in link is `/accounts/login/?next=%2Fprojects`.
  - 500: the card reads "ERROR · COULDN'T LOAD We couldn't load your alerts. Your work is safe; nothing was changed. Reference server_error for support. Try again". Try again sends 1 read and shows 6 rows with badge 4.
  - The none persona gets 0 bells and 0 reads.
  - pm gets "Alerts, 1 unread", a single "For your information" group with 2 rows, and 0 tabs on phone.
- Screenshots: `qa-evidence/desktop-1440-drawer.png`, `phone-320-sheet.png` and `phone-390-sheet.png`. The full-suite failure summary and its cause are in `qa-evidence/full-e2e-summary.log`.
- TECH-2-1 (non-blocking, already open) reproduces on the build:
  - Steps: on /notifications, choose "See all alerts", which leads to the same path. Then click the "Projects" link in the top bar.
  - Result: focus lands on the bell, not where the navigation would leave it.
  - This is a low-severity focus slip, not a new finding.
- When the drawer is opened, closed and opened again quickly, it sends two reads, one after the other. Nothing stacked: the first had finished before the second open. This is within the spec's "one per open".
- After 6 minutes idle, a `visibilitychange` event triggered one refresh, and a second event straight after triggered none, which matches the 5-minute rule.
- The scrim colour differs from spec line 50 (`rgba(20,24,26,.4)`). This is the token change the UI reviewer accepted in round 1.
- For the integration owner: the shared review server should be started with `FRAME_FIXTURES=1`, as `playwright.config.ts` does, so that the two phone back-link fixture tests can run against it.
- Method: I ran Playwright headless from the worktree's node_modules with scratch configs that start no web server. Scratch specs and test output were deleted afterwards, and the worktree is clean. I started no servers and stopped none.
