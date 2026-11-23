# Alerts list, drawer and alert settings on the live API

> Tasks: FE-ALERTS. Architecture: package v9 (live API 1.22.0, `contracts/psl-factory.openapi.json`). Design: approved canvas version 1794581312-b166 (`design/review.json`); screens: SCR-15 (artboards SCR-15-desktop, SCR-15-mobile, SCR-15-desktop-settings, SCR-15-mobile-settings; the email/whatsapp variants are delivery wording only). Account artboards are out.

## Summary
- The bell drawer and `/notifications` read `GET /api/v1/notifications` and show "Needs you" (`group: action`) and "For information" (`group: update`) with "as of" coverage.
- Opening an alert marks it read through `POST /api/v1/notifications/{id}/read` with `{}`. The unread count and badge come from the loaded list, since the server returns none.
- `/settings/alerts` shrinks to two switches (email, WhatsApp), each with a "ready" state, plus the recent delivery receipts. It saves with `POST /api/v1/me/alert-preferences` and handles a stale revision.
- Every part of the board the live API cannot fill is hidden, never faked, and listed as a board conflict below.
- The v7 mock behaviour for these screens is removed from the code path. The mock stays only as test fixtures.

## Context
Built today against the v7 mock contract (`/Users/Hunchoo/psl-factory-worktrees/lane-a/frontend`, branch from origin/main):
- `src/features/alerts/useAlertsFeed.ts`: the bell's feed. It already calls `api.GET('/api/v1/notifications')`, reads `list.unread_count`, and keeps a `readIds` guard against stale lists.
- `src/features/alerts/AlertsDrawer.tsx`, `AlertsBell.tsx`, `AlertParts.tsx` (`AlertAvatar`), `AlertsFilterPanel.tsx`, `NotificationsPage.tsx` (cursor paging, `fetchPage` with `q`, `agent`, `unread`, `limit`), `AlertSettingsPage.tsx` (`api.PUT` with `buildPrefsBody`, a `stale` notice already exists), `model.ts` (`metaLine`, `workHref`, `needsYou`, `parseView`, `buildAlertQuery`, `draftFrom`, `buildPrefsBody`, `selectsShown`), `types.ts` (types from `@/api/schema`, the v7 contract).
- Live client: `src/api/client.ts` exports `liveApi` (typed by `src/api/live-schema.d.ts`) and `call()`. `liveApi` and `api` share the CSRF token. The live operations are `notifications_inbox`, `notifications_mark_read`, `notifications_preferences` and `notifications_save_preferences`.
- Callers: `src/app/notifications/page.tsx`, `src/app/settings/alerts/page.tsx`, `src/shell/AppShell.tsx`, `TopNav.tsx`, `PhoneBar.tsx`.
- Tests: `tests/alerts*.test.ts(x)`, `e2e/alerts.spec.ts`, `e2e/alerts-bell.spec.ts`, mock `mock/alerts.mjs`.

## Contract

Use `liveApi` with `call()` for every operation. Change `types.ts` to read from `@/api/live-schema`.

### GET /api/v1/notifications (no parameters)
- 200: `{ items: [{ id, title, subject, detail, group: "action"|"update", read, django_url }], as_of }`. No paging and no counts.
- Permission: the signed-in person's own alerts. The server decides; the client sends nothing to scope it.
- Errors: 401 gives the signed-out state; 403, 5xx and network give the error state with Retry. A body without an `items` array is a load error, never "no alerts".
- Fixture: `{ "items": [ { "id": "n1", "title": "Invoice INV-0412 needs your approval", "subject": "Lagoon Health", "detail": "Waiting since 09:10", "group": "action", "read": false, "django_url": "/work/abc123/" }, { "id": "n2", "title": "Receipt matched", "subject": "Ojo Foods", "detail": "Matched to INV-0398", "group": "update", "read": true, "django_url": "" } ], "as_of": "2026-11-23T10:42:00Z" }`

Display rules:
- Row: title (primary), subject and detail as the secondary line. No agent avatar and no time (A-42). Use the neutral avatar already in `AlertParts.tsx` if the row layout needs one; otherwise omit it.
- "Needs you" lists `group: action`; "For information" lists `group: update`. Each heading shows its loaded count. Within a group keep the server order.
- Coverage line: "As of <time in WAT>" from `as_of`, on the drawer and on `/notifications`. Counts say "loaded", for example "5 alerts loaded", and never claim a total.
- Unread count = number of loaded items with `read === false`. Badge uses `badgeText` (hidden at 0, "99+" above 99). The bell name uses `bellName` with `need` = unread items in `group: action`. Before the first successful load the count is unknown and the badge is hidden (unknown is not zero).
- Open the work: parse `django_url` with one helper in `model.ts` (`workHrefFromUrl`). It returns `/work/<id>` only when `django_url` is a same-origin path whose pattern is `/work/<id>/` (the id being a non-empty path segment); it must never produce an absolute URL, a `//` URL or a `javascript:` URL. If it does not match, the row has no link and no open control. The retired Django page is never linked (A-42).
- Opening a row (the link or Enter on the row): mark read first (fire and forget), then navigate. A row with no link has a "Mark as read" button only when unread.

### POST /api/v1/notifications/{notification_id}/read
- Request: body `{}`, header `X-CSRFToken` (added by the client middleware). `notification_id` is the item's `id`, URL-encoded.
- 200: `{ id, read }`. Apply `read: true` to that item locally only after the 200. Do not expect `unread_count` (A-45).
- Errors: 401 gives the signed-out state; 403 and 404 mean the alert is not this person's or is gone: show "This alert is no longer available" in a row-level notice and refresh the list; 403 with code `csrf_failed` is handled by `call()` (fresh token, request not repeated, "Try again" shown); 5xx and network leave the row unread with a quiet "Couldn't mark as read. Try again." notice. Navigation to the work still happens on a failed mark-read.
- Idempotent: marking an already-read alert is allowed. Do not send a second request for an id already in `readIds`.

### GET /api/v1/me/alert-preferences
- 200: `{ revision, email_requested, whatsapp_requested, email_ready, whatsapp_ready, recent_deliveries: [{ channel: "email"|"whatsapp", state: "queued"|"uncertain"|"delivered"|"held", created_at, delivered_at, receipt }] }`.
- Fixture: `{ "revision": 3, "email_requested": true, "whatsapp_requested": false, "email_ready": true, "whatsapp_ready": false, "recent_deliveries": [ { "channel": "email", "state": "delivered", "created_at": "2026-11-23T08:00:00Z", "delivered_at": "2026-11-23T08:00:04Z", "receipt": "r-77" }, { "channel": "whatsapp", "state": "uncertain", "created_at": "2026-11-22T17:00:00Z", "delivered_at": null, "receipt": null } ] }`

### POST /api/v1/me/alert-preferences
- Request: `{ revision, email_requested, whatsapp_requested }` with the revision from the last read. CSRF as above. Only the two booleans the person changed are meant to differ; send both.
- 200: `{ revision, email_requested, whatsapp_requested, email_ready, whatsapp_ready, ... }`. Replace the held preferences with the response and show "Saved". If the 200 body lacks `recent_deliveries`, keep the previous list.
- Errors: 409 (kind `stale`) shows the existing stale notice: "These settings changed elsewhere. Reload to see the latest." with a Reload button that re-reads and discards the draft. 422 shows the server message in the notice. 401 signed-out. 403 and 5xx and network keep the draft and show a retryable error. Save is disabled while saving and while nothing differs from the loaded values.
- A switch may be turned on while its `*_ready` is false: the request is saved and the row says "Not ready yet: you will not receive anything on this channel until it is set up". The client never blocks the request on `ready`; the server decides.

Settings display:
- Two rows, "Email" and "WhatsApp", each a switch bound to `*_requested`, with a status text from `*_ready` ("Ready" or "Not ready yet").
- "Recent deliveries": one line per receipt, newest first as returned: channel, state word, time (`delivered_at` when set, else `created_at`) in WAT. State words: queued "Queued", uncertain "Not confirmed", delivered "Delivered", held "Held". `uncertain` is never shown as delivered or with a success colour. `receipt` is shown only as secondary text when present.
- No receipts: "Nothing has been sent to you yet."

### Screen states
| State | Drawer | /notifications | /settings/alerts |
|---|---|---|---|
| Loading | existing skeleton rows | existing skeleton | existing skeleton |
| Empty | "No alerts" (existing empty state), no group headings | same | not applicable; receipts empty line above |
| Error | existing error panel with Retry | same | same, with Retry |
| Signed out (401) | existing `SignedOutState` | same | same |
| Success | grouped list, as-of line | grouped list, as-of line | two switches, receipts |

## Lanes
- Frontend lane owns everything: `frontend/src/features/alerts/*`, `frontend/tests/alerts*.test.ts(x)`, `frontend/e2e/alerts*.spec.ts`, and the mock `frontend/mock/alerts.mjs` (reshaped to the live bodies, with `POST`).
- Backend lane: none. No backend change.
- Integration owner (lane A coordinator): the check against the live Django on the lane port, and `src/api/live-schema.d.ts`, which is generated and stays unchanged.
- Shared files read-only for this feature: `src/api/client.ts`, `src/api/errors.ts`, `src/shell/*` (only the import of `useAlertsFeed` may change if its return shape changes), `src/components/*`.
- Do not touch `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.

## Acceptance criteria
1. With the live backend and an account that has alerts, the bell drawer lists them under "Needs you" and "For information" by `group`, each row with title and subject/detail, and an "As of" time from `as_of` — verify: open the app, click the bell; compare with `curl -b <cookie> /api/v1/notifications`.
2. `/notifications` shows the same grouping and as-of line, with no search box, no agent filter, no Filter button, no unread filter and no "total" figure — verify: open `/notifications` at 1440 and 390; `grep -rn "unread_count\|cursor\|agent=" frontend/src/features/alerts` finds no live request use.
3. The bell badge equals the number of unread items in the loaded list, is hidden at zero and before the first load, and shows "99+" above 99 — verify: unit test on `badgeText` and a component test with 0, 3 and 120 unread items.
4. Opening an unread alert sends `POST /api/v1/notifications/{id}/read` with body `{}` and an `X-CSRFToken` header; the row turns read and the badge drops by one only after the 200 — verify: Playwright test asserting the request body and header, then the badge.
5. A failed mark-read (500) leaves the row unread, shows a retryable notice, and still navigates when the row has a link; a 404 shows "no longer available" and refreshes the list — verify: component tests with mocked responses.
6. A row whose `django_url` is `/work/<id>/` links to `/work/<id>`; rows with an empty, absolute, `//`, `javascript:` or unrecognised `django_url` have no link and no control that opens a Django page — verify: unit tests for `workHrefFromUrl` with those inputs; no `href` containing `/accounts/` or the Django host in the rendered DOM.
7. Agent avatar, agent name, per-alert time and "via WhatsApp / digest" wording no longer appear on any alert row — verify: component test; look at the page.
8. `/settings/alerts` shows exactly an Email switch and a WhatsApp switch with Ready or Not ready yet text, and the recent receipts; there are no per-event rows, digest select, quiet-hours select, locked rows or phone-number block — verify: open the page at 1440 and 390.
9. Changing a switch and pressing Save sends `POST /api/v1/me/alert-preferences` with exactly `{revision, email_requested, whatsapp_requested}`, then shows "Saved" and uses the returned revision for the next save — verify: Playwright test asserting the body, then a second save sends the new revision.
10. A 409 on save shows the stale notice, keeps nothing of the draft after Reload, and does not retry by itself — verify: component test with a 409.
11. Receipts show the states Queued, Not confirmed, Delivered and Held; an `uncertain` receipt is not styled or worded as delivered — verify: component test over all four states.
12. A 401 on any of the four operations shows the signed-out state and sends no further alert reads — verify: component tests for the bell feed, the page and settings.
13. A different signed-in person sees only the list the server returns for them; the client sends no user or tenant identifier — verify: code review of request construction; Playwright with two accounts (live-lead, live-none) shows different lists.
14. A list response with no `items` array shows the error state, not "No alerts" — verify: component test.
15. The v7 alert operations are gone from the app code: no `E-NOTIFICATIONS`, `E-NOTIFICATION-READ`, `E-ALERT-PREFS` or `api.PUT('/api/v1/me/alert-preferences'` under `frontend/src` — verify: `grep -rn` returns nothing; `npm run typecheck` passes.
16. Existing tests that asserted removed behaviour (`alerts-model`, `alerts-mock`, `alerts`, `alerts-settings`, `alerts-bell`, `e2e/alerts*.spec.ts`) are rewritten to the live shapes, not deleted outright, and new tests cover criteria 3 to 6, 9 to 12 and 14 — verify: `git diff --stat` and the gate.

## Out of scope
- The Account tab, `/me/account`, `/me/account/password`, the account-menu items, "My roles", "Delegate while away", the phone entry and any WhatsApp number add or verify (waiting on the open part of D-ALERTS-ENTRY).
- Backend changes and new endpoints.
- Per-event switches, digest time, quiet hours, locked rows, search, agent filter, unread filter, paging and server counts: not shown and not simulated.
- Client-side search or filtering of the loaded list. Not built in this feature (see question 3).
- Sending, testing or re-trying a delivery from this screen. Receipts are read only.
- Polling or push for new alerts. The existing refresh-on-open and tab-return behaviour stays.
- Redesigning layout beyond removing the parts above.

## Assumptions
- `django_url` for work alerts has the form `/work/<id>/`. The live schema gives only `string` and the connection map says "parse the work id out or ask". If real values differ, rows simply have no link; flagged under A-42.
- Delivery times and the as-of line are shown in WAT (Africa/Lagos), as `formatClock` in `model.ts` already does.
- State words "Not confirmed" for `uncertain` and "Held" for `held` are plain-language choices for the design engineer to rename.
- `unread_count` stays optional in the feed type so that the drawer code keeps one shape, but it is always derived locally.
- The group headings keep the existing board wording "Needs you" and "For information".
- Saving two unchanged switches is blocked client-side (Save disabled) to avoid pointless revision bumps.
- The 403 on mark-read is treated as "not available" like 404, because the contract lists both without a body that tells them apart.

## Conflicts with the boards
The spec removes or changes these things the boards draw. Recommendation is in each question below.
- SCR-15-desktop / mobile: agent avatar and name, per-alert time, "via WhatsApp 10:40" and "digest 17:00" meta line (A-42).
- SCR-15-desktop / mobile: unread filter, agent filter, search, "N alerts" total count and the footer page size (A-43).
- SCR-15-desktop-settings / mobile-settings: per-event WhatsApp and email switches, locked rows, daily digest time, quiet hours, and the verified-number block (A-44).
- Added, not on a board: "As of" coverage line, Ready/Not ready yet text and the "Recent deliveries" receipts block on settings.

## Questions for the design engineer
1. Alert rows without agent avatar, name or time (the live items have none; A-42). Options: (a) recommended: show title over subject and detail, no avatar, no time; (b) keep a neutral PSL mark in the avatar slot so the row alignment on the board holds; (c) wait for the backend to add `at` and `agent`.
2. Settings without per-event switches, digest and quiet hours (A-44). Options: (a) recommended: the card shows only Email and WhatsApp switches with Ready state and receipts, nothing else; (b) also show the old rows greyed out with "Not available yet", which keeps the board look but promises something; (c) hold the settings page back until the backend decides.
3. Search, agent filter, unread filter and totals (A-43). Options: (a) recommended: remove them for this release and show "N alerts loaded" with the as-of time; (b) keep an unread-only toggle and a text search that filter the loaded list on the client, with "filtered from the loaded alerts" wording; (c) keep the full toolbar and wait for paging.
4. Recent deliveries block is new on the settings board. Options: (a) recommended: add it under the switches as a plain list, with "uncertain" worded "Not confirmed"; (b) show only a one-line summary of the last delivery per channel; (c) leave receipts out until the board is redrawn.
5. Alerts with no usable link (no work id in `django_url`). Options: (a) recommended: the row is not clickable and has a Mark as read button; (b) the row stays clickable and only marks read; (c) hide such alerts.
6. Wording of the receipt states. Options: (a) recommended: Queued, Not confirmed, Delivered, Held; (b) Waiting to send, Could not confirm, Delivered, On hold; (c) your own wording.
