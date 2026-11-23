# Alerts list, drawer and alert settings on the live API

> Tasks: FE-ALERTS. Architecture: package v9 re-specced on live API 1.24.0 (`contracts/psl-factory.openapi.json`, `frontend/src/api/live-schema.d.ts`; D-185). Design: approved canvas version 1794581312-b166 (`design/review.json`); screens: SCR-15 (artboards SCR-15-desktop, SCR-15-mobile, SCR-15-desktop-settings, SCR-15-mobile-settings; the email/whatsapp variants are delivery wording only). Account artboards are out.

## Changes for 1.24.0
Re-spec under D-185. Every D-182 answer is kept (F-61 Q2, Q4, Q5, Q6 and Q7 unchanged; Q1 and Q3 now follow the data, below).
- GET /notifications now takes `page` and returns `unread` (total for the whole inbox), `page`, `next_page` (25 per page) and `daily_summary`. Items gain `at`, `agent`, `target_kind`, `api_url` (nullable). Backend answers A-42, A-43, A-44, A-45.
- Rows show the agent avatar and name and the time, as the board draws, when the item has them (`agent`/`at`); nothing is faked when null. The "no avatar, no time" rule (D-182 Q1a) applies only to items where they are null.
- The badge and the "need you" count come from `unread` (server total), not from the loaded list. The local count is kept only as a fallback for the drawer before the first load.
- `/notifications` pages with "Load more" using `next_page`. The "N alerts" total is still not supplied: the page says how many are loaded and how many are unread.
- Links come from `target_kind` and `api_url` (work, project, conversation), not only from `django_url`.
- The board's daily digest line is filled by `daily_summary` (in-app). No digest time, quiet hours or per-event switches exist in 1.24.0 (A-44: email and WhatsApp remain deferred), so settings stay two switches plus receipts.
- Still not in the API, so still hidden: search, agent filter, unread-only filter (only `page` is accepted), per-event rows, digest time, quiet hours, locked rows, phone-number block.
- Unchanged and out: the Account tab and account-menu items (D-182 Q7).
- New questions: 7 to 9 at the end.

## Summary
- The bell drawer and `/notifications` read `GET /api/v1/notifications` and show "Needs you" (`group: action`) and "For information" (`group: update`) with "as of" coverage, agent, time, typed links, paging and the in-app daily summary.
- Opening an alert marks it read through `POST /api/v1/notifications/{id}/read` with `{}`. The badge comes from the server's `unread` total.
- `/settings/alerts` shrinks to two switches (email, WhatsApp), each with a "ready" state, plus the recent delivery receipts. It saves with `POST /api/v1/me/alert-preferences` and handles a stale revision.
- Every part of the board the live API still cannot fill (search, filters, per-event settings, digest time, quiet hours) is hidden, never faked, and listed as a board conflict below.
- The v7 mock behaviour for these screens is removed from the code path. The mock stays only as test fixtures.

## Context
Built today (before this re-spec) against the v7 mock contract (`/Users/Hunchoo/psl-factory-worktrees/lane-a/frontend`, branch from origin/main):
- `src/features/alerts/useAlertsFeed.ts`: the bell's feed. It already calls `api.GET('/api/v1/notifications')`, reads `list.unread_count`, and keeps a `readIds` guard against stale lists.
- `src/features/alerts/AlertsDrawer.tsx`, `AlertsBell.tsx`, `AlertParts.tsx` (`AlertAvatar`), `AlertsFilterPanel.tsx`, `NotificationsPage.tsx` (cursor paging, `fetchPage` with `q`, `agent`, `unread`, `limit`), `AlertSettingsPage.tsx` (`api.PUT` with `buildPrefsBody`, a `stale` notice already exists), `model.ts` (`metaLine`, `workHref`, `needsYou`, `parseView`, `buildAlertQuery`, `draftFrom`, `buildPrefsBody`, `selectsShown`), `types.ts` (types from `@/api/schema`, the v7 contract).
- Live client: `src/api/client.ts` exports `liveApi` (typed by `src/api/live-schema.d.ts`) and `call()`. `liveApi` and `api` share the CSRF token. The live operations are `notifications_inbox`, `notifications_mark_read`, `notifications_preferences` and `notifications_save_preferences`.
- Callers: `src/app/notifications/page.tsx`, `src/app/settings/alerts/page.tsx`, `src/shell/AppShell.tsx`, `TopNav.tsx`, `PhoneBar.tsx`.
- Tests: `tests/alerts*.test.ts(x)`, `e2e/alerts.spec.ts`, `e2e/alerts-bell.spec.ts`, mock `mock/alerts.mjs`.

## Contract

Use `liveApi` with `call()` for every operation. Change `types.ts` to read from `@/api/live-schema`.

### GET /api/v1/notifications?page=<n>
- Query: `page` integer 1 to 10000, default 1. No other parameter exists: no `q`, `agent`, `unread` or `limit`.
- 200: `{ items: [{ id, title, subject, detail, group: "action"|"update", read, django_url, at, agent, target_kind, api_url }], as_of, page, next_page, unread, daily_summary }`. All of `at`, `agent`, `target_kind`, `api_url` are nullable. At most 25 items. `next_page` is null on the last page. `unread` counts unread alerts across all pages. `daily_summary` is `{ date, actions_open, unread_updates_today, unread_without_timestamp, scope: "current_inbox" }`.
- Permission: the signed-in person's own alerts. The server scopes; the client sends no user or tenant id.
- Errors: 401 gives the signed-out state; 403, 5xx and network give the error state with Retry; 400/422 on `page` give the error state. A body without an `items` array is a load error, never "no alerts".
- Fixture: `{ "items": [ { "id": "<64 hex>", "title": "Assistant reply", "subject": "Lagoon Health", "detail": "Tola", "group": "update", "read": false, "django_url": "/assistant/7/", "at": "2026-11-23T09:58:00Z", "agent": "tola", "target_kind": "conversation", "api_url": "/api/v1/assistant/conversations/7" }, { "id": "<64 hex>", "title": "Invoice review", "subject": "Ojo Foods", "detail": "INV-0398", "group": "action", "read": true, "django_url": "/work/abc123/", "at": null, "agent": null, "target_kind": "work", "api_url": "/api/v1/work/abc123" } ], "as_of": "2026-11-23T10:42:00Z", "page": 1, "next_page": 2, "unread": 7, "daily_summary": { "date": "2026-11-23", "actions_open": 3, "unread_updates_today": 2, "unread_without_timestamp": 1, "scope": "current_inbox" } }`

Display rules:
- Row: agent avatar (`AlertAvatar`, via `agentKey`) and agent name when `agent` is set; title (primary); subject and detail as the secondary line; time when `at` is set (today as clock, earlier as day and month, in WAT, using `dayWords`/`formatClock` already in `model.ts`). When `agent` is null use the neutral avatar slot or none; when `at` is null show no time (older alerts have none). The "via WhatsApp / digest" wording stays removed (email and WhatsApp are deferred).
- "Needs you" lists `group: action`; "For information" lists `group: update`, within the loaded pages, server order kept. Each heading shows its loaded count.
- Coverage line: "As of <time in WAT>" from `as_of`, on the drawer and `/notifications`. Counts say "loaded" and never claim a total of alerts.
- Unread: badge and the "unread" text use `unread` from the latest page-1 response; opening a row lowers it by one locally after the 200, and the next load replaces it. Badge uses `badgeText` (hidden at 0, "99+" above 99). The bell name uses `bellName` with `need` = unread items in `group: action` among the loaded items. Before the first successful load the count is unknown and the badge is hidden (unknown is not zero).
- Paging: the drawer reads page 1 only and links to `/notifications` ("See all", with unread total). `/notifications` shows a "Load more" button while `next_page` is not null, which requests that page and appends; ids already shown are not duplicated. A failed next page keeps the loaded rows and shows a retry notice. Page 1 refresh (open, tab return) resets the list.
- Daily summary (`/notifications`, above the groups, and a one-line version at the top of the drawer): "Today, <date>: <actions_open> need you, <unread_updates_today> new updates, <unread_without_timestamp> older unread." Zero values are shown as 0 (the backend returned them); each part is omitted only if the field is missing. Wording of the line is question 7.
- Open the work: one helper in `model.ts`, `alertHref(item)`, replaces `workHref`. It maps the typed link from `target_kind` and `api_url`: `api_url` of the form `/api/v1/work/<id>` gives `/work/<id>`; `/api/v1/projects/<id>` gives `/projects/<id>`; `/api/v1/assistant/conversations/<id>` gives `/assistant/<id>`. If `api_url` is null or unrecognised, fall back to `django_url` of the form `/work/<id>/` giving `/work/<id>`. The id is a single non-empty path segment (no `/`, `.`, `?`, `#`). The result is always a same-origin path starting with one `/`; never an absolute URL, `//` URL or `javascript:`. No match: the row has no link and no open control. The retired Django page is never linked.
- Opening a row (the link or Enter on the row): mark read first (fire and forget), then navigate. A row with no link has a "Mark as read" button only when unread.

### POST /api/v1/notifications/{notification_id}/read
- Request: body `{}`, header `X-CSRFToken` (added by the client middleware). `notification_id` is the item's `id`, URL-encoded.
- 200: `{ id, read }`. Apply `read: true` to that item locally only after the 200. The response carries no count (A-45); adjust the local `unread` as described.
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
| Empty | "No alerts" (existing empty state), no group headings; the daily summary still shows if returned | same | not applicable; receipts empty line above |
| Error | existing error panel with Retry | same | same, with Retry |
| Signed out (401) | existing `SignedOutState` | same | same |
| Success | summary line, grouped list, as-of line | summary, grouped list, as-of line, Load more when `next_page` | two switches, receipts |

## Lanes
- Frontend lane owns everything: `frontend/src/features/alerts/*`, `frontend/tests/alerts*.test.ts(x)`, `frontend/e2e/alerts*.spec.ts`, and the mock `frontend/mock/alerts.mjs` (reshaped to the live bodies, with `POST`).
- Backend lane: none. No backend change.
- Integration owner (lane A coordinator): the check against the live Django on the lane port, and `src/api/live-schema.d.ts`, which is generated and stays unchanged.
- Shared files read-only for this feature: `src/api/client.ts`, `src/api/errors.ts`, `src/shell/*` (only the import of `useAlertsFeed` may change if its return shape changes), `src/components/*`.
- Do not touch `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.

## Acceptance criteria
1. With the live backend and an account that has alerts, the bell drawer lists them under "Needs you" and "For information" by `group`, each row with title and subject/detail, and an "As of" time from `as_of` — verify: open the app, click the bell; compare with `curl -b <cookie> /api/v1/notifications`.
2. Rows with `agent` set show that agent's avatar and name, and rows with `at` set show the time in WAT; rows where they are null show neither and no placeholder text — verify: component test with both kinds; look at the page.
3. `/notifications` shows the same grouping, the as-of line and the daily summary line with the returned numbers; there is no search box, agent filter, Filter button, unread filter or total-alerts figure — verify: open at 1440 and 390; `grep -rn "agent=\|q=" frontend/src/features/alerts` finds no request use.
4. When `next_page` is not null, "Load more" requests `?page=<next_page>` and appends without duplicates; at `next_page: null` the button is gone; a failed page keeps the rows and offers retry — verify: component test with three mocked pages and a 500.
5. The bell badge equals `unread` from the server (not the loaded count), is hidden at 0 and before the first load, shows "99+" above 99, and drops by one only after a successful mark-read 200 — verify: unit tests on `badgeText`; component test with `unread` 0, 3, 120 and 40 items loaded with `unread` 60.
6. Opening an unread alert sends `POST /api/v1/notifications/{id}/read` with body `{}` and an `X-CSRFToken` header — verify: Playwright test asserting the request, then the badge.
7. A failed mark-read (500) leaves the row unread, shows a retryable notice, and still navigates when the row has a link; a 403 or 404 shows "no longer available" and refreshes — verify: component tests.
8. `alertHref` maps `api_url` `/api/v1/work/<id>`, `/api/v1/projects/<id>` and `/api/v1/assistant/conversations/<id>` to `/work/<id>`, `/projects/<id>` and `/assistant/<id>`; falls back to `django_url` `/work/<id>/`; and returns no link for null, absolute, `//`, `javascript:`, multi-segment or unrecognised values — verify: unit tests over those inputs; no `href` containing `/accounts/` or the Django host in the DOM.
9. `/settings/alerts` shows exactly an Email and a WhatsApp switch with Ready or Not ready yet text, and the recent receipts; no per-event rows, digest select, quiet-hours select, locked rows or phone-number block — verify: open at 1440 and 390.
10. Saving sends `POST /api/v1/me/alert-preferences` with exactly `{revision, email_requested, whatsapp_requested}`, shows "Saved", and the next save uses the returned revision — verify: Playwright test asserting both bodies.
11. A 409 on save shows the stale notice, drops the draft after Reload and does not retry by itself; a 422 shows the server message — verify: component tests.
12. Receipts show Queued, Not confirmed, Delivered and Held; an `uncertain` receipt is never worded or coloured as delivered — verify: component test over all four states.
13. A 401 on any of the four operations shows the signed-out state and sends no further alert reads — verify: component tests for bell, page and settings.
14. A different signed-in person sees only the list the server returns; the client sends no user or tenant identifier — verify: code review of request construction; Playwright with live-lead and live-none shows different lists and totals.
15. A list response with no `items` array shows the error state, not "No alerts" — verify: component test.
16. The v7 alert operations are gone from the app code: no `E-NOTIFICATIONS`, `E-NOTIFICATION-READ`, `E-ALERT-PREFS` or `api.PUT('/api/v1/me/alert-preferences'` under `frontend/src` — verify: `grep -rn` returns nothing; `npm run typecheck` passes.
17. Existing tests asserting removed behaviour (`alerts-model`, `alerts-mock`, `alerts`, `alerts-settings`, `alerts-bell`, `e2e/alerts*.spec.ts`) are rewritten to the live 1.24.0 shapes, not deleted; new tests cover criteria 2, 4, 5, 7, 8, 11, 12 and 15 — verify: `git diff --stat` and the gate.

## Out of scope
- The Account tab, `/me/account`, `/me/account/password`, the account-menu items, "My roles", "Delegate while away", the phone entry and any WhatsApp number add or verify (waiting on the open part of D-ALERTS-ENTRY).
- Backend changes and new endpoints.
- Per-event switches, digest time, quiet hours, locked rows, search, agent filter and unread filter: the API still has no data for them (A-43 supplies a cursor and counts only, A-44 defers email and WhatsApp), so they are not shown and not simulated.
- Client-side search or filtering of the loaded pages (question 3 stays as decided).
- Sending, testing or re-trying a delivery from this screen. Receipts are read only.
- Polling or push for new alerts. The existing refresh-on-open and tab-return behaviour stays.
- Redesigning layout beyond removing the parts above.

## Assumptions
- Typed links: `api_url` values are `/api/v1/work/<id>`, `/api/v1/projects/<case_id>` and `/api/v1/assistant/conversations/<id>` (read from `apps/core/alerts.py` in the backend checkout; the OpenAPI gives only `string`). Reminder and invoice-review alerts may carry neither `at` nor `api_url`; they fall back to `django_url`, then to no link.
- `agent` is a persona key (for example `tola`); `agentKey` already maps those keys. An unknown key shows the neutral avatar.
- The daily summary is shown only on the alerts surfaces, not as its own screen, since the boards draw a digest line only.
- Delivery times and the as-of line are shown in WAT (Africa/Lagos), as `formatClock` in `model.ts` already does.
- State words "Not confirmed" for `uncertain` and "Held" for `held` are plain-language choices for the design engineer to rename.
- The feed type exposes `unread` (server total); the old optional `unread_count` is removed.
- The group headings keep the existing board wording "Needs you" and "For information".
- Page size is fixed at 25 by the server; the board's "rows per page" footer stays hidden.
- Saving two unchanged switches is blocked client-side (Save disabled) to avoid pointless revision bumps.
- The 403 on mark-read is treated as "not available" like 404, because the contract lists both without a body that tells them apart.

## Conflicts with the boards
- SCR-15-desktop / mobile: unread filter, agent filter, search, the "N alerts" total and the footer page-size control stay removed (the API has `page` only; unread total exists but not an alert total). Recommendation: keep removed (Q3).
- SCR-15-desktop / mobile: "via WhatsApp 10:40" and "digest 17:00" meta line stays removed (email and WhatsApp deferred). Agent avatar, name and time are now drawn as the board shows when present.
- SCR-15-desktop-settings / mobile-settings: per-event switches, locked rows, daily digest time, quiet hours and the verified-number block stay removed (A-44). Recommendation: keep removed (Q2).
- Added, not on a board: "As of" line, Ready/Not ready yet text, "Recent deliveries" block, "Load more" button, and the daily summary line wording (Q7 to Q9).

## Questions for the design engineer
1. (Decided D-182, now mostly superseded) Rows show avatar, agent and time when the item has them; for items without, title over subject/detail only.
2. Settings without per-event switches, digest and quiet hours (A-44). Options: (a) recommended: the card shows only Email and WhatsApp switches with Ready state and receipts, nothing else; (b) also show the old rows greyed out with "Not available yet", which keeps the board look but promises something; (c) hold the settings page back until the backend decides.
3. (Decided D-182, kept) Search, agent filter and unread filter (A-43 still has no query for them). Options: (a) recommended: remove them for this release and show "N alerts loaded" with the as-of time; (b) keep an unread-only toggle and a text search that filter the loaded list on the client, with "filtered from the loaded alerts" wording; (c) keep the full toolbar and wait for paging.
4. Recent deliveries block is new on the settings board. Options: (a) recommended: add it under the switches as a plain list, with "uncertain" worded "Not confirmed"; (b) show only a one-line summary of the last delivery per channel; (c) leave receipts out until the board is redrawn.
5. Alerts with no usable link (no work id in `django_url`). Options: (a) recommended: the row is not clickable and has a Mark as read button; (b) the row stays clickable and only marks read; (c) hide such alerts.
6. Wording of the receipt states. Options: (a) recommended: Queued, Not confirmed, Delivered, Held; (b) Waiting to send, Could not confirm, Delivered, On hold; (c) your own wording.
7. Wording of the daily summary line (new, A-44; presentation only). Options: (a) recommended: "Today, 23 Nov: 3 need you, 2 new updates, 1 older unread" as one quiet line above the groups, plain text, no card; (b) a small three-figure strip (Need you / New today / Older unread); (c) show only the "need you" figure.
8. Paging control on `/notifications`. Options: (a) recommended: a "Load more" button under the list with "Showing N loaded, M unread"; (b) numbered pages using `page`; (c) infinite scroll.
9. Rows with no agent or time (reminders and older alerts). Options: (a) recommended: neutral avatar slot and no time, so the row alignment holds; (b) no avatar and no time (compact rows); (c) show "Earlier" instead of a time.
