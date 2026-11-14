# Alert bell in the top bar, with a drawer of "Needs you" and "For your information"

> Tasks: FE-ALERTS-MENU (split: bell and drawer only). Architecture: v7 package manifest (D-ALERTS-ENTRY listed in its decisions, `architecture/sources/decisions-2026-11-15-alerts-entry.md`). Design: approved canvas covers SCR-15 only; the bell has no `.dc.html` board and rests on the design engineer's decision of 15 Nov 2026 over `design/concepts/alerts-bell-concepts.html` (concept 3 inside concept 1's drawer). Screens: SCR-15 rows (`design/canvas/project/SCR-15-desktop.dc.html`, `SCR-15-mobile.dc.html`) for alert row styling; CMP-01 top bar and phone bar from `SCR-01-desktop.dc.html` / `SCR-01-mobile.dc.html`.

## Summary
- A signed-in person sees an alert bell with an unread count in the desktop top bar (beside their name) and in the phone bar. It opens a full-height right-side drawer on desktop and a full-height sheet on phone.
- The drawer groups alerts under "Needs you" and "For your information". Every row has one Open action that marks the alert read (one request) and goes to the work.
- A red "N need you" chip sits beside the bell from 1080px up; below that only the badge shows.
- "Needs you" depends on a PROPOSAL field, an optional `needs_you: boolean` on each notification. Without it every alert shows under "For your information" and the chip is hidden. No backend work, and `schema.d.ts` is not hand-edited.
- Sign-out and the account menu stay out (D-SIGNIN is open). The deferral is recorded under Out of scope and goes in the PR.

## Context
- Shell: `frontend/src/shell/AppShell.tsx` loads `/me` once and renders `TopNav` (inside `.shell-topbar`, from 720px) and `PhoneBar` (inside `.shell-phone`, below 720px) side by side, one hidden by CSS. `TopNav.tsx` today renders brand, links, `.shell-navend` (Start work `StartWorkButton variant="bar"`, `SampleLabel`) and then `.psl-nav__who` (name and role). Its doc comment says "no bell or account menu in this release"; that comment is updated. `PhoneBar.tsx` renders Menu, brand or back link, `SampleLabel`, and the Start slot.
- Styles: `frontend/src/styles/shell.css` (breakpoints 720px phone, 1080px desktop; section (f) hides the role below 1080px); tokens in `frontend/src/styles/tokens.css` (`--control-md: 44px`, `--bp-phone`, `--bp-desktop`).
- Alerts feature, to reuse and not duplicate: `frontend/src/features/alerts/model.ts` (`metaLine`, `agentImage`, `agentName`, `countLine`), `types.ts` (`Alert`, `AlertList`, `MarkReadResult`), `alerts.css` (`.alerts-row`, `.alerts-row--unread`, `.alerts-text`, `.alerts-meta`, `.alerts-sr`), `useIsPhone.ts` (below 720px). `NotificationsPage.tsx` holds the private `AlertRow`, `workHref` and the open-and-mark-read logic (`openAlert`: POST read, then `router.push`, no retry); extract what the drawer shares into the alerts feature rather than copying it.
- Frame states to reuse: `frontend/src/shell/FrameStates.tsx` (`LoadingState`, `SignedOutState`, `ForbiddenState`), `LoadErrorState` wording from the `/notifications` error card.
- Contract (v7, already in `frontend/src/api/schema.d.ts`): E-NOTIFICATIONS `GET /api/v1/notifications` returns `items[]` (`id`, `work_id`, `agent`, `text`, `at`, `read`, `reference?`, `delivered_via?`, `delivered_at?`, `digest_at?`, `in_app_reason?`), `next_cursor?`, `as_of`, `total?`, `unread_count?`. E-NOTIFICATION-READ `POST /api/v1/notifications/{notification_id}/read`. The API client in `frontend/src/api/client.ts` already sends `X-CSRFToken` on writes from the token `AppShell` sets.
- Mock server for the frontend lane: `frontend/mock/alerts.mjs` (scenario cookie `psl_mock_alerts`: board, phone, empty, many, bare, stale, invalid, locked) with fixtures in `frontend/mock/fixtures/` and the precedent `frontend/mock/proposals/setup.json` for proposal-only data.

## Contract

### Operations (no new endpoints)
1. **Read alerts**: `GET /api/v1/notifications` with no query parameters (server default page; `limit` never sent). Used for the bell badge, the chip and the drawer. Own alerts only; the server decides what a person may see. Errors: 401 signed out, 403 forbidden, any other or network failure is a load error.
2. **Mark read**: `POST /api/v1/notifications/{notification_id}/read`, no body, `X-CSRFToken` header. Sent only when the row is unread and Open is clicked. Idempotent on the server, so one request per click and no retry. Whatever happens the person still goes to the work (same rule as `NotificationsPage.openAlert`).

### PROPOSAL: `needs_you`
- PROPOSAL (not in v7): an optional boolean `needs_you` on each item of E-NOTIFICATIONS. `true` means the alert waits on this person (a decision or an exception). The backend developer owns adding it through the normal contract-change route; that is a separate task.
- Frontend type: a local type in the alerts feature, e.g. `type AlertWithNeed = Alert & { needs_you?: boolean }`, with a comment `PROPOSAL: not in v7`. `schema.d.ts` is not edited, and `tests/api-schema-drift.test.ts` still passes.
- Reading rule: `needs_you === true` goes under "Needs you"; `false`, absent or any non-boolean goes under "For your information". Never defaulted or guessed from the text.
- "Needs-you known": at least one loaded item carries a boolean `needs_you`. If none does, the field is treated as not supplied.

### Bell (desktop top bar, 720px and up)
- Only rendered when `/me` is ready. While `/me` loads, errors, or has no sections, there is no bell (as the nav is withheld today).
- A `<button type="button">` with a bell icon, `aria-haspopup="dialog"`, `aria-expanded` true while the drawer is open, `aria-controls` the drawer id. Accessible name: `Alerts` when counts are unknown; `Alerts, 3 unread` with an unread count; `Alerts, 3 unread, 2 need you` when the chip shows. Zero unread: `Alerts`.
- Badge: unread count from `unread_count` of the latest successful response. Shown only when it is a number above zero; `99+` above 99. Absent or error means no badge (unknown is not zero). Marked-read alerts lower it locally (see Fetching).
- Chip "N need you": count of loaded items with `needs_you === true` and `read === false`. Hidden when 0, when needs-you is not known, or when the list failed to load. From 1080px up only; below it the badge alone.
- Position in the bar, left to right: brand, links, (auto gap), bell, chip, name (and role from 1080px), Start work (`StartWorkButton variant="bar"`), with `SampleLabel` unchanged in `.shell-navend`. See Conflicts with the boards, item 1.
- Tab order: links, bell, Start work. The name is text. Start work is the last focusable item in the bar.

### Bell (phone bar, below 720px)
- In `PhoneBar`, between the brand (or back link / note) and `+ Start`; order Menu, brand, bell, `+ Start`. 44x44px target (`--control-md`). Same badge and accessible name. No chip on phone (the Needs you tab carries the count).
- Reachable on pages that set a back link as well (`usePhoneBack`): the bar shows `← label`, the bell and `+ Start`, no Menu.
- Tab order: Menu, bell, `+ Start`.

### Drawer (one instance, rendered by `AppShell`)
`AppShell` owns the alerts feed and the open state and renders one drawer; `TopNav` and `PhoneBar` only render the trigger button. Focus returns to whichever trigger opened it.

Desktop (720px and up):
- `role="dialog" aria-modal="true" aria-labelledby` its heading "Alerts". Fixed to the right edge, from the bottom edge of the top bar to the bottom of the viewport; width 420px (`max-width: 100%`); `--surface` background; 2px `--ink` left border; scrolls inside.
- Scrim over the page below the bar: `rgba(20,24,26,.4)`. Clicking it closes the drawer. The page behind is inert (`inert` on the bar's siblings and `main`) and does not scroll.
- Header row: "Alerts" (display 15px/20px, weight 800) at left, a `Close` button at right (text "Close", min 32x32, 2px `--ink` border), 10px 14px padding, 2px bottom border.
- Group header "Needs you" (only when needs-you is known): mono 11px/16px uppercase, letter-spacing .06em, padding 6px 14px, `--signal-tint` background and `--signal-ink` text, count of items in the group at the right. Then its rows. Then group header "For your information" in `--surface-subtle` / `--ink-muted` with its count, then its rows. When needs-you is not known, only the "For your information" group shows (header and count); there is no "Needs you" header, because that would claim nothing needs the person.
- Row: grid `avatar | text and meta | Open`. Avatar, text and meta lines reuse SCR-15 styling and helpers (`agentImage`, `.alerts-text`, `metaLine` for "Chidi · WhatsApp · 09:42"), 40px avatar. Unread rows use `.alerts-row--unread` (tinted, text weight 600). No NEW tag in the drawer. See Conflicts, item 3.
- **Open**: an `<a>` to `/work/{work_id}` (same `workHref` as the Alerts page), the only focusable thing in the row. Min height 28px, padding 0 10px, 2px `--ink` border, weight 600. In "Needs you" it is the primary style (`--action` fill, white text); in "For your information" it is the secondary style (`--surface` fill, `--ink` text). Its accessible name is `Open: <alert text>`.
- Footer, pinned to the bottom: 2px top border, `--surface-subtle`, padding 10px 14px. Left link "See all alerts" to `/notifications`; right link "Alert settings" to `/settings/alerts`. Both `--action-ink`, underlined, weight 600. Following either closes the drawer.
- Motion: slides in from the right in 200ms with the scrim fading in. Under `prefers-reduced-motion: reduce` there is no transition at all.

Phone (below 720px):
- Full-height sheet: starts 36px below the top of the viewport and runs to the bottom; a 40x4px grab bar (`--ink-subtle`, radius 2px) centred 8px below its top edge (decorative; dragging is not built); `--surface`, 2px `--ink` top border; scrim behind it.
- Header "Alerts" and a `Close` button 44x44px minimum.
- Tabs directly under the header: `role="tablist"`, two equal columns "Needs you" (with a signal-coloured count pill, white 11px text) and "For your information", each min 44px tall, 2px `--ink` bottom border, selected tab `--ink` fill with `--surface` text. Left/Right arrows move between tabs. The default tab is "Needs you" when it has items, otherwise "For your information". When needs-you is not known there are no tabs, only the single list headed "For your information".
- Rows as on desktop; Open min 44px tall, min 60px wide. Footer min 48px tall, same two links.
- Opening the sheet slides it up from the bottom in 200ms, none under reduced motion.

Keyboard and focus (both):
- On open, focus moves to the Close button. Tab and Shift+Tab cycle inside the drawer (Close, [tabs on phone], Open links in document order, See all alerts, Alert settings). Escape closes. On any close focus returns to the trigger that opened it.
- Opening an alert, following a footer link, or any route change closes the drawer.

### Fetching (no polling storms)
- `AppShell` makes one E-NOTIFICATIONS request when `/me` becomes ready, and one more each time the drawer opens (the list already held stays on screen during that refresh; the loading state shows only when there is nothing yet). One request in flight at a time; opening twice quickly does not stack requests.
- No timer, no interval. A refresh when the tab becomes visible again is allowed only if the last load is more than 5 minutes old.
- Marking read updates local state only (that alert read, `unread_count` down by one, never below zero); it does not refetch.
- A 401 anywhere stops further requests until reload.

### States (drawer body; the bell stays visible except where noted)
| State | Bell | Drawer body |
|---|---|---|
| Loading (no data yet) | no badge, no chip | `LoadingState` skeleton, "Loading…" with `role="status"` |
| Empty (no items) | no badge | "No alerts yet." with the footer links |
| Needs you empty (needs-you known, none) | as counts | "Nothing needs you right now." under its header |
| For your information empty (other group has items) | as counts | "No other alerts." under its header |
| Error (network, 5xx) | no badge, no chip | error card as on `/notifications`: "ERROR · COULDN'T LOAD", "We couldn't load your alerts. Your work is safe; nothing was changed.", `Last loaded 10:42.` when known, `Reference <code> for support.`, `Try again` (one request). If a list was loaded before, it stays visible and the card shows above it |
| 401 | no badge | "You're signed out." with a `Sign in` link (`SignedOutState` pattern, `next` = current path) |
| 403 | no badge | "Your account can't use PSL Factory." plus the server message (`ForbiddenState` pattern) |
| Success | badge and chip as defined | the two groups |

### Fixture examples
PROPOSAL fixture for the mock (new scenario `needs-you` in `frontend/mock/alerts.mjs`, data in `frontend/mock/proposals/alerts-needs-you.json`, the same six alerts as the concept page; the existing `board` scenario is unchanged and carries no `needs_you`):
```json
{
  "items": [
    {"id":"n1","work_id":"w-inv-lh-002","agent":"chidi","text":"Invoice for Lagoon Health is waiting for your review","at":"2026-11-15T08:42:00Z","read":false,"reference":"INV-LH-002","needs_you":true},
    {"id":"n2","work_id":"w-plan-kl-01","agent":"tola","text":"The project plan for Kestrel Logistics needs your sign-off","at":"2026-11-15T07:15:00Z","read":false,"reference":"PLAN-KL-01","needs_you":true},
    {"id":"n3","work_id":"w-pay-oct","agent":"zainab","text":"October payroll has 2 problems for HR","at":"2026-11-15T06:10:00Z","read":false,"reference":"PAY-OCT","needs_you":true},
    {"id":"n4","work_id":"w-uat-lh","agent":"tola","text":"The UAT response for Lagoon Health is due tomorrow","at":"2026-11-15T06:30:00Z","read":false,"reference":"UAT-LH","needs_you":false},
    {"id":"n5","work_id":"w-inv-lh-001","agent":"chidi","text":"Milestone 1 invoice was verified","at":"2026-11-14T10:00:00Z","read":true,"reference":"INV-LH-001","needs_you":false},
    {"id":"n6","work_id":"w-ms-kl-02","agent":"tola","text":"Milestone 2 for Kestrel Logistics is complete","at":"2026-11-12T10:00:00Z","read":true,"reference":"MS-KL-02","needs_you":false}
  ],
  "as_of": "2026-11-15T09:00:00Z",
  "unread_count": 4
}
```
Expected: badge `4`, chip `3 need you`, accessible name `Alerts, 4 unread, 3 need you`; Needs you lists n1 to n3 (count 3), For your information lists n4 to n6 (count 3). With the unchanged `board` scenario (no `needs_you`): badge from its `unread_count`, no chip, single "For your information" group.

## Visual reference (no board, no fidelity score)
There is no `.dc.html` board for the bell, so the fidelity tool cannot score it. Reviewers open `design/concepts/alerts-bell-concepts.html` (concept 3, the "Desktop, 880 px wide, shown open" and "Phone, 390 px wide, shown open" mock-ups) next to the running app and compare side by side at **1440** and **390** wide, in the mock with the `needs-you` scenario, under the mock-up's "Close the mock-ups" off state for the closed bar. The concept page is drawn at 880px with a 48px bar; the app's real bar is 56px high at 1440 (`.psl-nav__in` `min-height: 56px`), so positions are checked relative to the bar, not as absolute pixels. Wording, order, colours, and the sizes in Contract are the testable parts.

## Lanes
- **Frontend lane (all of the build)**:
  - New in `frontend/src/features/alerts/`: `AlertsBell.tsx` (trigger button, badge, chip), `AlertsDrawer.tsx` (dialog, groups, tabs, states, focus handling), `useAlertsFeed.ts` (fetching and local mark-read), the shared row and open logic extracted from `NotificationsPage.tsx` (which then imports it; its behaviour does not change), a local `AlertWithNeed` type marked PROPOSAL.
  - Edited: `frontend/src/shell/AppShell.tsx` (feed, open state, one drawer), `TopNav.tsx`, `PhoneBar.tsx`, `frontend/src/styles/shell.css` (bell, chip, breakpoint at 1080px, tokens only) and `frontend/src/features/alerts/alerts.css` (drawer and sheet classes, prefixed `alerts-`), the `TopNav` doc comment.
  - Tests and mock: `frontend/tests/alerts-bell.test.tsx` (vitest, component level), `frontend/e2e/alerts-bell.spec.ts` (Playwright at 1440 and 390, axe WCAG 2.2 AA, as `e2e/alerts.spec.ts` does), `frontend/mock/alerts.mjs` and `frontend/mock/proposals/alerts-needs-you.json` (scenario `needs-you`).
- **Backend lane**: no work in this feature. Adding `needs_you` to E-NOTIFICATIONS is a separate contract-change task, owned by the backend developer; record it in the PR as the follow-up.
- **Integration owner**: owns the PR, the D-SIGNIN deferral note, confirming `frontend/src/api/schema.d.ts` is untouched, and that the existing shell e2e specs (`e2e/frame.spec.ts`, `e2e/start-work.spec.ts`, `e2e/my-work.spec.ts`) still pass with the bell present.
- **Shared files**: `AppShell.tsx`, `TopNav.tsx`, `PhoneBar.tsx`, `shell.css` wrap every page; the frontend lane owns them for this feature and no other lane edits them. `NotificationsPage.tsx` is touched only to import the extracted pieces. `delivery/config.json`, `delivery/checks.sh`, `delivery/merge-policy.json` are not touched.
- **Review routing**: technical review sonnet; UI review opus (side by side with the concept page at 1440 and 390); UX review sonnet (flows, wording, keyboard, states); QA opus; product acceptance (PMO) required, since the bell is outside the approved canvas.

## Conflicts with the boards
Places where this spec adds, moves or removes something an approved board (or the built shell) draws. Defaults below are what gets built unless the design engineer decides otherwise before the build.
1. **Start work moves right of the name (CMP-01, SCR-01 desktop).** The board and built bar put Start work, then the name. The concept (and its keyboard note, Start work last) puts bell, chip, name, Start work. Default: follow the concept. Alternative: keep the board order (Start work, bell, chip, name), in which case Start work is not last in tab order. Recommendation: the concept order, since the design engineer chose it later and it keeps Start work the final stop.
2. **Bell, chip and drawer are new items in CMP-01 and the phone bar.** No board draws them. Recommendation: accept; the concept page is the reference.
3. **Rows in the drawer differ from SCR-15 rows.** SCR-15 draws the whole row as one link with a NEW tag and no Open button; the drawer has an Open link as the only action, no NEW tag (unread is the tint and bold text), and the avatar is SCR-15's 40px, not the concept's 28px. Recommendation: accept; the drawer is a triage list, and the tint plus the badge already show unread.
4. **SCR-15 toolbar is not carried over.** No search, Filter, agent filters (concept 1's All / Unread / agent pills are dropped in favour of the two groups) or count line in the drawer. They stay on `/notifications`. Recommendation: accept.
5. **Phone sheet instead of SCR-15-mobile's page.** `/notifications` stays the full page; the sheet is a quick view only. Recommendation: accept.
6. **Chip hides below 1080px**, as the concept says; the SCR-01 bar has no such element. Recommendation: accept.

## Acceptance criteria
Verify with the mock server (`frontend` dev with the contract mock; cookie `psl_mock_alerts=needs-you` unless said) and the running app. "Concept page" is `design/concepts/alerts-bell-concepts.html`.

Bell and counts
1. At 1440 wide, a signed-in person sees a bell button in the top bar, left of their name and right of the page links, with a red badge `4` at its top-right (about -2px top, -3px right, min 17px tall) — verify: open `/` in the mock, screenshot beside concept 3's desktop mock-up; badge position, colour and order bell, chip, name, Start work match.
2. A red chip reading `3 need you` (24px tall, white 12px text, touching the bell) sits right of the bell at 1440 and 1080, and is absent at 1079, 900 and 720 where only the badge shows — verify: resize in the browser or `e2e/alerts-bell.spec.ts` at those widths.
3. The bell's accessible name is `Alerts, 4 unread, 3 need you` in `needs-you`, `Alerts, 4 unread` in a scenario with no `needs_you`, and `Alerts` with no counts when the list failed — verify: `getByRole('button', { name })` in the e2e and vitest tests.
4. With no `needs_you` anywhere (scenario `board`), the chip is absent, the drawer shows only a "For your information" group, and there is no "Needs you" header or tab — verify: open the drawer in `board`.
5. With `needs_you` present but every needs-you alert read, the chip is absent and the Needs you group still shows its rows and the count of items — verify: vitest with a fixture where n1 to n3 are read.
6. When the response has no `unread_count`, the badge is absent (not `0`) — verify: vitest with a response missing `unread_count`.
7. Counts above 99 show `99+` — verify: vitest with `unread_count: 120`.
8. While `/me` is loading, errored, or signed out, no bell renders and no notifications request is made — verify: vitest and e2e intercept; request count is zero.
9. On phone (390 wide) the phone bar shows Menu, PSL FACTORY, bell (44x44px), then `+ Start`; on a sub-page with a back link it shows `← label`, bell, `+ Start` — verify: e2e at 390 on `/` and on a page that sets `usePhoneBack`, element boxes measured ≥ 44x44.

Drawer, desktop
10. Clicking the bell opens a dialog named "Alerts" fixed to the right edge, 420px wide (±1px), starting at the bottom edge of the top bar and reaching the viewport bottom, with a dimmed scrim over the rest of the page — verify: e2e bounding boxes at 1440x900; compare with concept 3.
11. Inside, top to bottom: header "Alerts" with `Close`; "Needs you" group header (signal-tint background) with count `3`; rows n1 to n3; "For your information" header with count `3`; rows n4 to n6; footer with "See all alerts" at the left and "Alert settings" at the right — verify: e2e reads the order; screenshot beside the concept.
12. Each row shows avatar, alert text, a meta line like `Chidi · WhatsApp · 09:42` (from `metaLine`), and one `Open` link; Needs you Open links are filled blue, For your information Open links are outlined; unread rows are tinted with bold text and there is no NEW tag — verify: screenshot, and `getByRole('link', { name: /^Open:/ })` count equals 6.
13. The bell shows an open state while the dialog is open (white 2px border, darker fill) and `aria-expanded="true"`; it returns to `false` on close — verify: e2e assertion.
14. The footer links go to `/notifications` and `/settings/alerts` and close the drawer — verify: click each; URL and absence of the dialog.

Open and mark read
15. Clicking Open on an unread alert sends exactly one `POST /api/v1/notifications/n1/read` with a non-empty `X-CSRFToken` header, then navigates to `/work/w-inv-lh-002`, and the drawer is closed there — verify: Playwright request listener (count 1, header present) and `page.url()`.
16. Clicking Open on a read alert sends no POST and navigates to the work — verify: request listener count 0 for n5.
17. If the mark-read POST fails (500) or the network drops, the person still arrives at the work and nothing is retried (one request) — verify: e2e with a route override returning 500.
18. Double-clicking Open sends one POST — verify: listener count 1.
19. After marking n1 read and returning to the page (browser back), the badge reads `3` and the chip `2 need you` — verify: e2e; the mock keeps state per persona.
20. Open with a modifier key (Ctrl/Cmd/Shift click, middle click) behaves as a normal link and sends no POST, as on `/notifications` — verify: vitest.

Keyboard, focus, motion
21. On open, focus is on `Close`; Tab and Shift+Tab never leave the dialog (cycle Close, six Open links, See all alerts, Alert settings); the page behind cannot be tabbed to or scrolled — verify: e2e presses Tab 12 times and checks `document.activeElement` is inside the dialog.
22. Escape closes the drawer and focus returns to the bell (desktop) or to the phone bell (phone); clicking the scrim or `Close` does the same — verify: e2e `toBeFocused()` on the trigger.
23. Tab order in the bar is page links, bell, Start work, with Start work last; on phone it is Menu, bell, `+ Start` — verify: e2e Tab sequence at 1440 and 390 for a person with startable lines.
24. With `prefers-reduced-motion: reduce` the drawer and sheet appear without any CSS transition or animation; otherwise the slide is about 200ms — verify: e2e `emulateMedia({ reducedMotion: 'reduce' })` and computed `transition-duration` is `0s` (or none).
25. axe (WCAG 2.2 AA tags as in `e2e/alerts.spec.ts`) reports no violations with the drawer open at 1440 and 390 — verify: `expectNoAxeViolations` in the new spec.

Phone sheet
26. At 390 wide the sheet starts about 36px from the top of the viewport and reaches the bottom, with a grab bar, header "Alerts", `Close` at least 44x44px, then two tabs of at least 44px height: `Needs you` with a count pill `3` and `For your information` — verify: e2e boxes; screenshot beside concept 3's phone mock-up.
27. The sheet opens on "Needs you" and shows n1 to n3 with filled `Open` buttons of at least 44px height and 60px width; selecting the other tab (click or arrow keys) shows n4 to n6; with no needs-you data there are no tabs — verify: e2e on `needs-you` and `board`.
28. Page has no horizontal scroll at 390 with the sheet open — verify: `scrollWidth <= innerWidth`.

Fetching
29. A page load issues one notifications request; opening the drawer issues one more; no further requests occur over 70 seconds idle, and after marking read there is no refetch — verify: e2e request counter with a fake clock (`page.clock`) advancing 70s.
30. Opening the drawer twice quickly leaves at most one request in flight — verify: vitest with a deferred response.

States and failures
31. While the first request is pending the drawer shows the loading skeleton with "Loading…" and the bell shows no badge — verify: vitest/e2e with a delayed route.
32. With the `empty` scenario the drawer shows "No alerts yet." and the footer links; no badge or chip — verify: e2e.
33. With `needs-you` where Needs you has none, its header shows "Nothing needs you right now."; where For your information has none it shows "No other alerts." — verify: vitest.
34. On a 500 or network failure the drawer shows the error card with "We couldn't load your alerts. Your work is safe; nothing was changed." and `Try again`; clicking it sends one request and on success shows the list — verify: e2e route override.
35. On a 401 the drawer shows "You're signed out." with a `Sign in` link whose `next` is the current path, and no further notifications requests are made; a 403 shows "Your account can't use PSL Factory." — verify: e2e route overrides.
36. A person only ever sees their own alerts: the drawer renders exactly the items the server returns for them and never filters or fetches by another user; switching mock persona (cookie) changes the list and the counts — verify: e2e with two personas.
37. Text in an alert (even if it says "needs you" or looks like a script/HTML) is rendered as plain text and does not change which group it is in — verify: vitest with an item whose text is `<b>needs you</b>` and `needs_you: false`; it sits under For your information as literal text.

Contract and regressions
38. `frontend/src/api/schema.d.ts` is byte-identical to before the change; `needs_you` appears only in a local type marked `PROPOSAL` — verify: `git diff --stat -- frontend/src/api/schema.d.ts` is empty and `grep -rn "needs_you" frontend/src` shows the local type, the mock and tests.
39. `/notifications` behaves exactly as before (rows, mark-read on open, filters, states) — verify: existing `tests/alerts.test.tsx` and `e2e/alerts.spec.ts` pass unchanged.
40. Every other page keeps its layout: the top bar still fits at 720px with the badge and no chip, with no overlap or wrapping between links, bell, name and Start work, and no horizontal scroll — verify: e2e at 720 and 1080 on `/`, `/projects`, `/notifications`.
41. No sign-out or account menu control is added — verify: grep and screenshot show none.

## Out of scope
- Sign-out, the account menu and account links (D-SIGNIN open). Record the deferral in the PR.
- Any backend change, including adding `needs_you` to E-NOTIFICATIONS, and editing `schema.d.ts` by hand.
- Alert settings and preference screens, WhatsApp and email message content, the assistant, and any "Mark all read".
- Search, filters, agent pills, "Show more" or paging inside the drawer (go to `/notifications`).
- Polling, websockets, push or sound for new alerts.
- Swipe-to-close on the phone sheet and a drag-to-resize grab bar (the grab bar is decorative).
- Changes to Start work (CMP-23) other than its position in the desktop bar, and to the Menu.

## Assumptions
- The drawer lists the first server page only; "See all alerts" covers the rest. Reason: concept 3 has no paging, and the default page covers a triage view.
- The chip counts unread `needs_you` alerts on the loaded page, and the group header counts all items in that group on the page. Reason: the concept shows the same number for both; the server gives no needs-you total.
- Unknown `needs_you` means no "Needs you" group at all, not an empty one. Reason: unknown is not zero (AGENTS.md invariants).
- Open marks read only on an unread row and does not wait for the answer beyond that single call; failure still navigates. Reason: matches `NotificationsPage.openAlert`.
- Real bar height (56px) and the SCR-15 40px avatar are used instead of the concept's 48px bar and 28px avatar. Reason: the concept is a scaled mock-up at 880px; boards and built shell win for sizes they define.
- Phone sheet closes by `Close`, Escape and the scrim, not by swipe. Reason: swipe adds a gesture library or custom handlers for little gain; flagged for the design engineer under Out of scope.
- Refresh on tab visibility only after 5 minutes. Reason: keeps the badge from going stale without polling.
- Focus goes to `Close` on open. Reason: the concept says "focus moves in" without naming an element, and Close is a stable first stop.
