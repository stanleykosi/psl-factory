STATUS: READY
COMMIT: 07d078ef95aed97f36a412c6214ee8bc778ab9d0
BUILDER: builder
LANE: full

## Summary
- Signed-in people now see an alert bell with an unread badge in the desktop top bar and in the phone bar. From 1080px a red "N need you" chip sits next to it. Bar order is links, bell, name, then Start work last (D-54).
- The bell opens one drawer, which AppShell renders. On desktop it is a 420px panel under the bar with a scrim. On phone it is a full-height sheet with a grab bar and "Needs you" / "For your information" tabs. Every row has one Open link: it marks the alert read with one POST and goes to the work.
- "Needs you" uses a local PROPOSAL type `AlertWithNeed` (`needs_you?: boolean`). When no loaded item carries a boolean `needs_you`, only "For your information" shows and there is no chip. `schema.d.ts` is untouched.
- Fetching: one read when /me is ready and one more each time the drawer opens. There is no timer. Only one request runs at a time. The tab refreshes on return only if the list is more than 5 minutes old. Nothing more is read after a 401. Marking read updates local state only.
- No sign-out or account menu was added (D-SIGNIN stays open; record the deferral in the PR). Follow-up for the backend developer: add `needs_you` to E-NOTIFICATIONS through the contract-change route.

## Changes
- `frontend/src/features/alerts/AlertParts.tsx` (new): code taken out of NotificationsPage so the page and the drawer share it: `AlertAvatar`, `AlertBody` (text and meta line), `useOpenAlert` (POST read on an unread plain click, then `router.push`, no retry; `onRead` hears an accepted read) and `AlertsLoadError` (the error card).
- `frontend/src/features/alerts/AlertsBell.tsx` (new): the bell button (`aria-haspopup="dialog"`, `aria-expanded`, `aria-controls="alerts-drawer"`, accessible name from `bellName`), the badge, and the chip (desktop only, hidden below 1080px by CSS).
- `frontend/src/features/alerts/AlertsDrawer.tsx` (new): the dialog. It holds the groups, the phone tabs (roving tabindex, Left/Right arrows), the loading, empty, error, 401 and 403 states, and the footer links. Focus goes to Close on open and stays inside. Escape, the scrim and Close all close it. The page behind does not scroll. The drawer's top is measured from the top bar.
- `frontend/src/features/alerts/useAlertsFeed.ts` (new): feed state, `refresh` (in-flight guard; a 401 stops further reads), `markRead` (that item read, `unread_count` down by one, never below 0), and the 5-minute stale refresh when the tab becomes visible. A body with no `items` array counts as a load error.
- `frontend/src/features/alerts/types.ts`: `AlertWithNeed`, marked `PROPOSAL: not in v7`.
- `frontend/src/features/alerts/model.ts`: added `workHref` (moved here), `needsYou`, `needsYouKnown`, `badgeText` (`99+`) and `bellName`.
- `frontend/src/features/alerts/NotificationsPage.tsx`: now imports the shared parts. Its behaviour is unchanged.
- `frontend/src/features/alerts/alerts.css`: drawer and sheet classes (`alerts-layer`, `alerts-dscrim`, `alerts-drawer`, `alerts-grp`, `alerts-drow`, `alerts-open`, `alerts-tabs`, `alerts-dfoot`, …). The 200ms slide and fade are switched off under reduced motion. The avatar `img` rule is widened from `.alerts-link` to `.alerts-row`.
- `frontend/src/shell/AppShell.tsx`: owns the feed, the open state and the one drawer. The drawer counts as open only on the path it was opened on, so any route change closes it. Focus goes back to the bell that opened it. While it is open, `inert` is set on the skip link, the phone bar and `main`.
- `frontend/src/shell/TopNav.tsx`: order is brand, links, bell, name, then `.shell-navend` (Start work, SampleLabel). The doc comment is updated (no account menu or sign-out, D-SIGNIN).
- `frontend/src/shell/PhoneBar.tsx`: the bell goes in the end slot before "+ Start". It comes after the menu in the DOM, so Tab goes Menu, (menu links when open), bell, "+ Start". It also shows on back-link pages.
- `frontend/src/styles/shell.css` (tokens only), section (g):
  - Bell is 36px (44px on phone). Badge is -2px / -3px, 17px tall. The open state has a white 2px border on an `--ink-strong` fill. The chip is 24px with 12px text and shows from 1080px.
  - The first of bell, name and Start work takes the free space.
  - Fitting the bar needed some tightening. Measured without it, the name was cut at 720px and the bar overflowed by 34px at 1080px. Now:
    - Bell, name and Start work are 12px apart.
    - Start work's right margin is dropped when it is last.
    - From 1080px to 1279px, link padding is 10px.
    - From 720px to 1079px, the bell is 32px with no gaps around it and link padding is 2px.
  - These only apply when the bell is present.
- `frontend/mock/alerts.mjs` and `frontend/mock/proposals/alerts-needs-you.json` (new): the `needs-you` scenario with the concept page's six alerts.
  - I added `delivered_via` to each item so the meta line reads "Chidi · WhatsApp · 09:42", as criterion 12 shows. The spec's example fixture has no `delivered_via`.
  - The existing `board` scenario is unchanged.
- Tests:
  - New: `frontend/tests/alerts-bell.test.tsx` (32 vitest tests) and `frontend/e2e/alerts-bell.spec.ts` (33 Playwright tests at 1440, 390, and the 720/900/1079/1080 bar widths, with axe).
  - New `frontend/tests/bell-feed.ts` helper: page tests answer the shell's bell read with an empty list before their own fetch stubs see it.
  - Applied that helper in `shell`, `work-item`, `work-item-board`, `projects`, `projects-journey`, `my-work`, `decide`, `response`, `setup-rules` and `alerts-settings`.
  - Updated `shell.test.tsx` (button list now includes the two bells; one test name), `setup-rules.test.tsx` (the bell is excluded from the "no controls" count) and `alerts.test.tsx` (see criterion 39).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Bell in the top bar at 1440: e2e "the bell sits right of the links…" checks the boxes (links < bell < chip < name < Start work), red badge `4`, badge -2px top / -3px right of the padding box, 17px tall. See `round-1/visual/desktop-closed.jpg`.
2. [x] Chip `3 need you`: 24px tall, white 12px text on signal red, touching the bell. e2e bar-width tests: visible at 1080 and 1440; hidden at 1079, 900 and 720, where the badge still shows.
3. [x] Accessible names: `Alerts, 4 unread, 3 need you` (needs-you), `Alerts, 1 unread` (board), `Alerts` (failed). Checked in vitest and e2e.
4. [x] Board scenario: no chip, only a "For your information" group, no tabs (vitest, plus e2e at desktop and phone).
5. [x] All needs-you alerts read: no chip, and Needs you still lists its 3 rows with count 3 (vitest).
6. [x] No `unread_count`: no badge (vitest).
7. [x] `unread_count: 120` shows `99+` (vitest).
8. [x] /me loading, signed out, errored or without sections: no bell and zero notifications requests (vitest ×4; e2e for a 401 on /me).
9. [x] Phone order Menu, PSL FACTORY, bell (≥44×44), "+ Start". On `/frame-fixtures/phone-back` it is `← Queue`, bell, "+ Start" (e2e boxes).
10. [x] Dialog "Alerts" is 420px wide, flush right, starts at the bar's bottom edge and runs to the viewport bottom. Scrim is `rgba(20, 24, 26, 0.4)` (e2e at 1440×900, measured after the slide ends).
11. [x] Order: header, "Needs you" header (signal-tint) with count 3, n1 to n3, "For your information" header with count 3, n4 to n6, footer links left and right (e2e innerText order). See `visual/desktop-open.jpg`.
12. [x] Each row has an avatar, the text, a meta line like `Chidi · WhatsApp · 09:42` and one Open. Needs you Opens are filled blue, the others outlined. Unread rows are tinted with 600 weight text. There is no NEW tag. 6 `Open:` links (e2e and vitest).
13. [x] Bell open state: white 2px border on an rgb(53,61,65) fill, `aria-expanded` true while open and false after close (e2e).
14. [x] Footer links go to `/notifications` and `/settings/alerts` and close the drawer (e2e).
15. [x] Open on n1: one POST `/api/v1/notifications/n1/read` with `X-CSRFToken: mock-csrf-finance_lead`, URL becomes `/work/w-inv-lh-002`, drawer closed (e2e).
16. [x] Open on read n5: no POST, navigates (e2e and vitest).
17. [x] POST 500: still navigates, exactly one POST (e2e route override and vitest).
18. [x] Double-click on Open sends one POST (e2e `dblclick` and vitest).
19. [x] After marking n1 read and going back: badge `3`, chip `2 need you` (e2e).
20. [x] Ctrl, Cmd, Shift and middle click act as a normal link: no POST, no push (vitest ×4).
21. [x] Focus starts on Close. 12 Tabs and 12 Shift+Tabs stay inside the dialog. `main` is inert. Wheel scrolling does not move the page (e2e).
22. [x] Escape, Close and a scrim click all close it, and focus returns to the desktop bell. On phone, Escape returns focus to the phone bell (e2e and vitest).
23. [x] Tab order: Setup, bell, Start work, More ways to start, then out of the bar. On phone: Menu, bell, "+ Start" (e2e). The existing frame test (menu open: Menu then its links) still passes.
24. [x] Normal motion: animation `alerts-slide-in` 0.2s, transition 0s. Reduced motion: animation `none` for the drawer, scrim and phone sheet (e2e).
25. [x] axe WCAG 2.2 AA finds no violations with the drawer open at 1440 and with the sheet open at 390 (also checked: bar closed at 1440, empty state).
26. [x] Sheet top at 36px, bottom at 844, grab bar visible, Close ≥44×44, two tabs ≥44px tall, `Needs you` with count pill `3` (e2e). See `visual/phone-open.jpg`.
27. [x] Opens on Needs you with n1 to n3. Open buttons are ≥44px tall and ≥60px wide. Arrow keys and clicks switch to n4 to n6. No tabs in `board` (e2e).
28. [x] No horizontal scroll at 390 with the sheet open (e2e).
29. [x] With `page.clock`: 1 read on load, 2 after opening, still 2 after a 70s fast-forward. No re-read after marking read (vitest).
30. [x] Opening twice quickly while a read is held leaves one request in flight (vitest with a deferred response).
31. [x] While the first read is pending: no badge, and the drawer shows `Loading…` with `role="status"` (vitest and e2e with a gated route).
32. [x] `empty` scenario: "No alerts yet.", footer links, no badge or chip (e2e and vitest).
33. [x] "Nothing needs you right now." and "No other alerts." under their headers (vitest).
34. [x] Read failure: the error card with the wording and reference. Try again sends one read and shows the list (e2e and vitest).
35. [x] 401: "You're signed out." with `Sign in` to `?next=%2Fmy-work`, and no further reads when the drawer is reopened. 403: "Your account can't use PSL Factory." (e2e and vitest).
36. [x] Switching persona (finance_lead to pm) changes the list and counts. The drawer only shows what the server returned (e2e).
37. [x] Text `<b>needs you</b>` with `needs_you: false` shows as literal text under For your information (vitest).
38. [x] `git diff --stat d97b99b -- frontend/src/api/schema.d.ts` is empty. `grep -rn needs_you frontend/src` finds only the PROPOSAL type, the model readers and a comment; otherwise it appears in the mock and the tests. `tests/api-schema-drift.test.ts` passes.
39. [x] `/notifications` behaves as before; `e2e/alerts.spec.ts` passes unchanged. **Deviation:** `tests/alerts.test.tsx` needed two assertions updated. They count every `GET /api/v1/notifications`, and the shell's bell read (required by Fetching) is the same request with no query, so the test can't tell them apart:
    - `calls.length` goes from 1 to 2 (page plus bell, both held at the gate).
    - The bare re-read list goes from `['?q=…', '']` to `['?q=…', '', '']`.
    The page's own requests are the same as before. The spec's "unchanged" and its Fetching contract can't both hold.
40. [x] The bar fits at 720, 900, 1079 and 1080 on `/`, `/projects` and `/notifications`: no horizontal scroll, the name is not cut, the 28px right gutter is kept, and everything is on one line (e2e, 12 cases). The existing frame.spec width and fit tests pass. This needed the spacing changes listed under shell.css.
41. [x] No sign-out or account control: the e2e check for a "sign out" or "account" button finds none, and the shell test for this still passes.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-15 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exits 0: Django check passes, eslint has 0 warnings, tsc passes, vitest has 43 files and 1126 tests passing, and `next build` succeeds.
- `E2E_PORT=4801 MOCK_PORT=4802 npx playwright test` (full suite): 302 passed, 4 failed. The 4 failures also happen on the base sources, run the same way:
  - `overview.spec.ts:126`
  - `projects.spec.ts:152` (phone)
  - `projects.spec.ts:199` (phone)
  - `projects.spec.ts:421`
  These are not caused by this branch. The new `alerts-bell.spec.ts` passes 33 of 33. `frame`, `start-work`, `my-work` and `alerts` specs all pass.
- Visual check on a production build (`next start` on 4801, mock on 4802, scenario needs-you), side by side with concept 3's mock-ups. Images are in `delivery/features/F-15/round-1/visual/`: `desktop-open.jpg`, `desktop-closed.jpg`, `phone-open.jpg`, `phone-closed.jpg`. Both servers were stopped afterwards and `test-results/` was deleted.
- Expected differences from the concept, all from the spec:
  - 56px real bar instead of the concept's 48px.
  - SCR-15 40px mascot avatars and sans meta line instead of the concept's 28px letter avatars and mono meta line.
  - SCR-15 unread tint (signal-tint mix) instead of the concept's action-tint.
  - Row meta shows the delivery channel (`metaLine`) instead of the reference.
- No board fidelity score is possible: the bell has no `.dc.html` board.
