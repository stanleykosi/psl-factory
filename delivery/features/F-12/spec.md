# A person sees their own alerts, opens one to its work, and sets how they are alerted

> Tasks: FE-ALERTS (R-ALERTS; A-ALERTS frontend half, A-ALERT-PREFS, A-NOTIFICATIONS, A-ACCESSIBILITY; INV-ACCESS). Architecture: package `architecture/packages/v7`, manifest.json sha256 `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`, openapi.json info.version `0a4f10a08cfe`. D-NOTIFY-MODEL r3 and D-ALERT-PREFS-VIEW r1 are `proposed` and count only under the design engineer's recorded exception (decisions-2026-11-14-v2.md (g), decisions-2026-11-15.md (h)(i)): contract mock only, the backend developer may change or refuse any field, nothing is released. Base: `1827260` (the mock and generated client still load v4; F-13 repoints to v7 and is not merged). Design: canvas version 1794581312-b166 (design/review.json, client approval 13 Nov 2026); screens: SCR-15 (artboards SCR-15-desktop, SCR-15-mobile, SCR-15-desktop-settings, SCR-15-mobile-settings), plus the "EMPTY · NOTIFICATIONS" card and the loading and error cards on STATES-desktop and STATES-mobile (design/canvas/project/).

## Summary
- New route `/notifications` (SCR-15 default): the person's own alerts from E-NOTIFICATIONS. Each alert shows the agent avatar, the text, and how and when it was delivered or why it stayed in the app. Unread alerts show NEW. The page has search, Filter (agent, unread) and "N ALERTS". Opening an alert marks it read (E-NOTIFICATION-READ) and goes to `/work/<work_id>`.
- New route `/settings/alerts` (SCR-15 settings, "How you're alerted"): it reads E-ALERT-PREFS-READ and shows a per-event WhatsApp and email switch matrix, the digest time and quiet hours from the returned options, and the masked WhatsApp number. "Save settings" sends E-ALERT-PREFS (CSRF, revisioned). A 409 reloads the newer version and drops the edits, a 422 shows the message that names the field, and a 401 shows the signed-out state.
- Proposal fields are typed locally and are never defaulted. An element that needs a proposal field renders only when the API returns that field (readiness PMO-0-2). This lets F-12 build now on the v4-loading mock. It merges only after F-13 has merged and F-12 has been rebased onto it.
- The contract mock gets `mock/alerts.mjs`, a verbatim v7 overlay and board-shaped fixtures: four alerts (one restricted, one digest), plus empty, many, absent-fields, stale, invalid and locked scenarios. `server.mjs` gets a small listed seam.
- Nothing is sent anywhere. The four WhatsApp and email boards are backend message content and go to the design engineer as an exception request.

## Context
- **Routes today:** `frontend/src/app/` has `my-work`, `projects`, `overview`, `assistant`, `setup` and `work/[id]`, with no `notifications` or `settings`. Unknown paths fall to `src/app/not-found.tsx`. Every page renders inside `AppShell` (`src/app/layout.tsx`, `src/shell/AppShell.tsx`). AppShell loads E-ME once, calls `setCsrfToken`, handles 401/403/error for `/me`, and exposes `useMe()`. `destinationForPath` (`src/shell/destinations.ts`) does not know `/notifications` or `/settings/alerts`, so no top-bar item is highlighted there. That is correct, because no board highlights one.
- **Page pattern to copy:** `src/app/my-work/page.tsx` (static `metadata.title`) → `src/features/my-work/MyWork.tsx`. The parts to copy are:
  - the `role="search"` form with `psl-toolbar` / `psl-search`;
  - `SEARCH_DEBOUNCE_MS = 300` with the view held in the URL;
  - `useIsPhone()` on `(max-width: 719.98px)`;
  - ignoring late responses;
  - the `psl-showmore` footer.

  The CMP-22 panel pattern (popover on desktop, bottom sheet on phone, a draft that only "Show results" applies, Esc or a click outside discards) is in `src/features/my-work/FilterPanel.tsx`. F-12 writes its own `AlertsFilterPanel` on that pattern, because the my-work panel's facets are line and state.
- **Shared UI to import (read-only):**
  - from `src/shell/FrameStates.tsx`: `LoadingState` and `SignedOutState`;
  - from `src/features/my-work/icons.tsx`: `SearchIcon`, `FilterIcon` and `CloseIcon`;
  - from `src/features/decide/format.ts`: `AGENT_NAMES` (tola/chidi/zainab → Tola/Chidi/Zainab) and `formatClock` ("10:42" in Africa/Lagos);
  - from `src/features/work-item/labels.ts`: `formatWat`, as the pattern for day and month in WAT;
  - shell classes: `shell-title`, `shell-errorcard`, `shell-eyebrow`, `shell-reference`, `shell-errorcard__action`;
  - bundle classes in `src/styles/psl-bundle.css`: `psl-toolbar`, `psl-search`, `psl-input`, `psl-select`, `psl-btn` (`--lg`, `--xl`, `--block`, `--secondary`, `--dark`), `psl-tag psl-tag--person` (NEW, which is `--signal-tint` on `--signal-ink`, as drawn), `psl-avatar psl-avatar--40 psl-avatar--<agent>` (mascot tints `--mascot-*-tint`, as drawn), `psl-tablewrap`, `psl-table`, `psl-empty`, `psl-callout` (`--problem`, `--warning`, `--success`), `psl-showmore`, `psl-sheet*`, `psl-pop`, `psl-scrim`, `psl-radio` and `psl-check`.
  - The bundle has no switch class. The switch is feature CSS on tokens: `--ink`, `--surface` and `--disabled`.
- **Avatars:** `frontend/public/agents/{tola,chidi,zainab}.png` are on the base (commit 1827260, decision D-14). Readiness PMO-0-6 is therefore settled: F-12 adds no asset and uses `/agents/<agent>.png`.
- **API client:** `src/api/client.ts` exports `api = createClient<paths>()` from openapi-fetch, typed from the v4 `src/api/schema.d.ts`, with `csrfMiddleware` setting `X-CSRFToken` on every write, and `call()`. v4 has no GET `/api/v1/me/alert-preferences`, no POST `/api/v1/notifications/{notification_id}/read`, and none of the proposal fields. `src/api/errors.ts` maps 401→`unauthenticated`, 403→`forbidden`, 404→`not_found`, 409→`stale`, 422→`invalid`, other→`server`, and a network failure→`network`.
- **Mock:** `frontend/mock/server.mjs`:
  - `OPENAPI_PATH` is v4 (line 22);
  - `M1_OPERATIONS` is at line 24;
  - `createMockServer` reads `fixtures/<id>.json` for every M1 id except E-ME, so it crashes on a missing file;
  - persona and scenario (`psl_mock_scenario` / `X-Mock-Scenario`) are applied before dispatch, and only for statuses the route declares;
  - CSRF is checked for writes against `me[persona].csrf_token`;
  - `/__mock/reset` clears `overrides`.

  The handler pattern is `mock/work-list.mjs`: an `o<offset>` cursor, and 404 `invalid_query`.
- **v4 vs v7 for these operations:**
  - E-NOTIFICATIONS in v4 has only `cursor` and `limit`, and items `{id, work_id, agent, text, at, read}` with `additionalProperties: false`.
  - E-ALERT-PREFS (PUT) in v4 takes and returns only `{channel, frequency}`.
  - E-ALERT-PREFS-READ and E-NOTIFICATION-READ are v7-only.
  - The v7 path items are `/api/v1/notifications` (get), `/api/v1/notifications/{notification_id}/read` (post) and `/api/v1/me/alert-preferences` (get, put). None of them uses `$ref`.
- **Generic mock test:** `frontend/tests/mock-contract.test.ts` loops over `M1_OPERATIONS`. For every persona it expects 200 with a body valid against the operation in `OPENAPI_PATH` (v4), and it runs every declared error status. It sends `{}` as the body of any write that has no `BODY` entry. Path parameters it does not know become `X-1`.
- **Style guard:** `tests/styles-drift.test.ts` fails on any literal hex or rgba in `src/**/*.css|tsx`. The board's unread row colour `#FBF5F2` is not a token.
- **Records:** REC-NOTIFICATION ("one per person per event; carries no amounts or client details") and REC-ALERT-PREF ("one per person"). INV-ACCESS: own records only, checked by the backend.

## Contract
Frontend and mock both build against this. Shapes are the v7 operations, copied verbatim into the overlay `frontend/mock/proposals/alerts.json`. Types come from that overlay (Lanes). In the tables, *proposal* marks a field that v4 does not have: it must be tolerated when absent.

### E-NOTIFICATIONS · `GET /api/v1/notifications`
- **Query:**
  - `q`: proposal, minLength 1, never sent empty;
  - `agent`: proposal, one of `tola`, `chidi`, `zainab`;
  - `unread`: proposal, sent only as `true`;
  - `cursor`: from `next_cursor`;
  - `limit` is not sent, so the server default of 20 applies.
- **200:** `{ items: [{ id, work_id, agent, text, at, read, reference?, delivered_via?, delivered_at?, digest_at?, in_app_reason? }], next_cursor?, as_of, total?, unread_count? }`. Base: `items`, the six item fields and `as_of`. Proposal: everything with `?` except `next_cursor`.
- **Errors (`{code, message}`):**
  - 401 → `SignedOutState pathname="/notifications"` (search string included);
  - 403, 404, 5xx and network → the list error card.
- **Permission rule:** own alerts only, filtered by the backend. The page shows exactly the rows returned, in the order returned. It never filters, sorts or hides rows on the client, and it shows a restricted alert's text exactly as returned.
- **Idempotency:** a read with no CSRF and no polling. Try again, a new search, a filter change and Show more all re-read.
- **URL state:** `/notifications?q=<text>&agent=<key>&unread=1`. Empty values are omitted. An unknown `agent` or `unread` value is ignored. Nothing is stored in localStorage, sessionStorage or cookies.

### E-NOTIFICATION-READ · `POST /api/v1/notifications/{notification_id}/read` (proposal operation)
- **Request:** no body. `X-CSRFToken` comes from the shared middleware.
- **200:** `{ id, read: true, unread_count }`.
- **Errors:** 401, 403 (incl. `csrf_failed`), 404, 409, 422, 5xx and network all mean the same thing on the list. Navigation still happens, the row keeps NEW, and nothing retries.
- **Permission rule:** own alert only. Another person's id answers 404.
- **Idempotency:** marking an already-read alert is not sent from the UI. The mock answers 200 if it is repeated.

### E-ALERT-PREFS-READ · `GET /api/v1/me/alert-preferences` (proposal operation)
- **200:** `{ channel, frequency, revision, events: [{ key, label, whatsapp, email, timing?, timing_label?, locked_reason? }], digest_at?: { value?, options: [{value,label}] }, quiet_hours?: { value?, options: [{value,label}] }, whatsapp?: { masked_number?, verified }, note? }`.
- **Errors:**
  - 401 → `SignedOutState pathname="/settings/alerts"`;
  - 403, 404 (the operation does not exist on a backend without the proposal), 5xx and network → the settings error card;
  - a 200 with no `events` array also gets the error card.

  In all of these the page shows no matrix, no Save, and no channel or frequency editor (readiness PMO-0-2).
- **Permission rule:** own preferences only. The masked number is shown exactly as returned. It is never unmasked, reformatted, edited or copied into any request.

### E-ALERT-PREFS · `PUT /api/v1/me/alert-preferences`
- **Request (CSRF):** `{ channel, frequency, expected_revision?, events?, digest_at?, quiet_hours? }`:
  - `channel` and `frequency` go back exactly as GET returned them (PMO-0-4 a). They are never remapped, so a GET value outside the PUT enums produces the 422 that the API returns.
  - `expected_revision` is the GET `revision` exactly. It is omitted if GET returned none (PMO-0-4 b).
  - `events` is every returned event as `{ key, whatsapp, email }`, in returned order, with the current switch values. Locked events go back with their values as read.
  - `digest_at` is sent only when the digest select is shown and has a value: the chosen option's `value`.
  - `quiet_hours` is sent on the same rule: the chosen option's `value`.
  - The phone sends no `digest_at` and no `quiet_hours` (PMO-0-5).
- **200:** the same shape as the GET (v7 PUT response), with a new `revision`. The page replaces its state with this body.
- **Errors:**
  - 409 → re-read E-ALERT-PREFS-READ, discard every edit, render the new version, and show the stale callout;
  - 422 → keep the edits and show the returned `message` verbatim, which names the field(s);
  - 401 → `SignedOutState pathname="/settings/alerts"`;
  - 403 (incl. `csrf_failed`), 404, 5xx and network → keep the edits and show the save-problem callout with the returned message and code.

  None of these retries automatically.
- **Idempotency and versioning:**
  - one save in flight at a time: the button is `aria-disabled`, reads "Saving…", and further presses are ignored;
  - the revision guards concurrent edits;
  - nothing is partially written, per the operation description.

### Fixture examples (finance_lead, scenario `board`)
E-NOTIFICATIONS (times shown in WAT; the mock moves dates so that `as_of` is today):
```json
{ "items": [
  { "id": "N-0001", "work_id": "W-1001", "agent": "chidi", "text": "Invoice for Lagoon Health is waiting for your review", "at": "2026-11-14T09:42:00Z", "read": false, "reference": "INV-LH-002", "delivered_via": ["whatsapp", "email"], "delivered_at": "2026-11-14T09:42:00Z" },
  { "id": "N-0002", "work_id": "W-1002", "agent": "tola", "text": "The UAT response for Lagoon Health is due tomorrow", "at": "2026-11-14T07:30:00Z", "read": true, "delivered_via": ["email"], "digest_at": "2026-11-14T08:00:00Z" },
  { "id": "N-0003", "work_id": "W-1099", "agent": "zainab", "text": "October payroll has 2 problems for HR", "at": "2026-11-14T07:10:00Z", "read": true, "delivered_via": ["in_app"], "in_app_reason": "you are not HR" },
  { "id": "N-0004", "work_id": "W-1006", "agent": "chidi", "text": "Milestone 1 invoice was verified", "at": "2026-11-13T15:20:00Z", "read": true, "delivered_via": ["in_app"], "delivered_at": "2026-11-13T15:20:00Z" }
], "as_of": "2026-11-14T10:00:00Z", "total": 4, "unread_count": 1 }
```
E-ALERT-PREFS-READ (finance_lead, `board`):
```json
{ "channel": "both", "frequency": "immediate", "revision": 3,
  "events": [
    { "key": "decision_waiting", "label": "A decision is waiting for me", "whatsapp": true, "email": true, "timing": "immediate", "timing_label": "Straight away" },
    { "key": "info_requested", "label": "Information is requested from me", "whatsapp": true, "email": true, "timing": "immediate", "timing_label": "Straight away" },
    { "key": "work_stuck", "label": "Work I started is stuck", "whatsapp": true, "email": true, "timing": "immediate", "timing_label": "Straight away" },
    { "key": "work_verified", "label": "Work I started is verified", "whatsapp": false, "email": true, "timing": "daily_digest", "timing_label": "In the daily digest" },
    { "key": "everything_else", "label": "Everything else", "whatsapp": false, "email": true, "timing": "daily_digest", "timing_label": "In the daily digest" } ],
  "digest_at": { "value": "08:00", "options": [ { "value": "07:00", "label": "07:00" }, { "value": "08:00", "label": "08:00" }, { "value": "09:00", "label": "09:00" } ] },
  "quiet_hours": { "value": "20-07-weekends", "options": [ { "value": "20-07-weekends", "label": "20:00 to 07:00, and weekends" }, { "value": "20-07", "label": "20:00 to 07:00" }, { "value": "none", "label": "No quiet hours" } ] },
  "whatsapp": { "masked_number": "+234 803 *** 4412", "verified": true },
  "note": "Alerts never include amounts or client details beyond the name." }
```

### Presentation rules (pure functions in `src/features/alerts/model.ts`, unit-tested)
- **Agent:** the name is `AGENT_NAMES[agent]`. The avatar is `<img src="/agents/<agent>.png" alt="">` inside `psl-avatar psl-avatar--40 psl-avatar--<agent>`. The image is decorative, because the name is in the text. An agent key outside the three gets no image, a neutral `psl-avatar psl-avatar--40` circle, and the key as returned for the name.
- **Meta line** ("<Agent> · <how> · <when>", 12px, `--ink-muted`):
  - If `in_app_reason` is present: `<Agent> · In app only (<in_app_reason>)`, with no time.
  - Otherwise, *how* is shown only when `delivered_via` is present. Fixed order whatsapp, email, in_app; the words are "WhatsApp", "email" and "in app", joined with " and ", with the first letter capitalised: `["whatsapp","email"]` → "WhatsApp and email", `["email"]` → "Email", `["in_app"]` → "In app".
  - *when*: if `digest_at` is present, "<HH:MM of digest_at> daily digest". Otherwise use `delivered_at`, falling back to the base `at`: the same WAT day as now → "HH:MM"; the WAT day before → "yesterday"; older → "D Mon" ("12 Nov").
  - Board results: "Chidi · WhatsApp and email · 10:42", "Tola · Email · 09:00 daily digest", "Zainab · In app only (you are not HR)", "Chidi · In app · yesterday". With every proposal field absent, the line is "Chidi · 10:42".
- **Count line:** "N ALERTS" ("1 ALERT") from `total`, desktop only, as drawn. It is shown only when `total` is a number, including "0 ALERTS" when the API says 0.
- **Search and Filter:** shown only when the latest successful response carries `total` (readiness PMO-0-2). If a response lacks `total` while the URL has `q`, `agent` or `unread`, the page drops those from the URL (router `replace`) and reads once more without them. This lets the person get back to an unfiltered list.
- **Unread:** `read === false` gives the NEW tag (`psl-tag psl-tag--person`), a 600 weight on the text, and the row tint `color-mix(in srgb, var(--signal-tint) 40%, var(--surface))`, a token mix that stands in for the board's #FBF5F2 (Assumptions). The unread count is shown only when `unread_count` is returned: as "N unread" beside the "Unread only" checkbox in the Filter panel, and in the visually hidden text after the count line (", N unread"). It is never computed from rows.

### Screen states — SCR-15 list (`/notifications`, `metadata.title` "Notifications · PSL Factory")
| State | What shows |
|---|---|
| Loading | `LoadingState`. No rows from a previous view. |
| Default (1440), board SCR-15-desktop | In order: eyebrow "NOTIFICATIONS" (mono 12px, `--ink-muted`); a row with `h1.shell-title` "Notifications" and, right-aligned, the link "Alert settings" (`/settings/alerts`); CMP-22 `form role="search"` with the search field (visually hidden label "Search", placeholder "Search notifications", search icon, 44px, 2px ink border, flex 1 1 320px, max 460px), the button "Filter" (filter icon, `aria-haspopup="dialog"`, `aria-expanded`, inset 2px ink ring, white) and, right-aligned, the count line; then `ul aria-label="Alerts"` (white, 2px ink border). Each `li` is a 40px / 1fr / auto grid with 12px gap, 12px 16px padding and a 1px `--rule-soft` bottom border. It holds the avatar, then text (600 if unread, else 400) over the meta line, then NEW (unread only, top-aligned). The whole row content is one link to `/work/<work_id>` in ink colour with no underline, a `--surface-subtle` hover and the standard focus ring. Its accessible name is text, meta and "New" when unread. Then the `psl-showmore` "Show more" button while `next_cursor` is present. |
| Default (390), board SCR-15-mobile | In order: the page back link "← Home" (to `/`, under the frame's phone bar per D-08); `h1` "Notifications" (26px); search (flex 1) and a 44×44 icon button `aria-label="Filter"`; the same list (10px 12px row padding); then the link "Alert settings". No eyebrow and no count line, as drawn. No horizontal page scroll. |
| Filter open | CMP-22 `role="dialog" aria-label="Filter"`: a popover under the button on desktop, a bottom sheet on phone. Facets are exactly the v7 parameters (PMO-0-7): a radio group "Agent" (Any agent, Tola, Chidi, Zainab) and a checkbox "Unread only" with the "N unread" hint. "Show results" applies, "Clear" resets the draft, and Esc, close or a click outside discards. While filters are applied, the button reads "Filter · N", where N is the number of facets set. |
| Empty (no q or filter, zero items) | Header, settings link and (when `total` is returned) the toolbar stay. In place of the list: `psl-empty` with `h3` "No alerts yet." (STATES "EMPTY · NOTIFICATIONS"). |
| No results (q or filter set, zero items) | `psl-empty` with `h3` "No alerts match" and a button "Clear search and filters" that removes `q`, `agent` and `unread`. |
| Show more fails | The loaded rows stay. Below them, `psl-callout psl-callout--problem` reads "We couldn't load more. Nothing was changed." with "Try again". |
| Error | `shell-errorcard role="alert"`: "ERROR · COULDN'T LOAD" / "We couldn't load your alerts. Your work is safe; nothing was changed." / "Last loaded HH:MM. Reference {code} for support." The "Last loaded HH:MM." part appears only after an earlier success, using that response's `as_of` in WAT. Then the button "Try again" (`psl-btn--secondary psl-btn--lg psl-btn--block`, inside `shell-errorcard__action`), which re-reads the same view. |
| Signed out (401) | `SignedOutState` with `next` set to the encoded current path and search. |
| Opening an alert | If `read === false`: `preventDefault`, POST E-NOTIFICATION-READ, then `router.push('/work/<work_id>')` whether it succeeded or failed. If it is already read, ordinary link navigation. Modifier-clicks and middle-clicks keep the browser default (a new tab, no mark-read). The row is not optimistically changed. |

### Screen states — SCR-15 settings (`/settings/alerts`, `metadata.title` "Alert settings · PSL Factory")
| State | What shows |
|---|---|
| Loading | `LoadingState`. |
| Default (1440), board SCR-15-desktop-settings | In order: eyebrow "SETTINGS / ALERTS"; `h1.shell-title` "How you're alerted"; `psl-tablewrap` / `psl-table` (min-width 760px, visually hidden caption "Alerts for each kind of work") with column headers WHEN, WHATSAPP, EMAIL, TIMING. There is one row per returned event in order: WHEN holds `label` (with `locked_reason` under it in 13px `--ink-muted` when present); WHATSAPP and EMAIL each hold a switch; TIMING holds `timing_label` as returned, and is empty if absent. Then a wrapping row of two cards (flex 1 1 300px, 22px gap, white, 2px ink border, 16px padding). Card 1 is shown when `digest_at` or `quiet_hours` has options: a label "Daily digest at" with a select of `digest_at.options` (label text, value `value`, selected `digest_at.value`, plus a first empty option "Not set" only when `value` is absent), then a label "Quiet hours" with a select of `quiet_hours.options` on the same rule. Each pair is rendered only when its object has a non-empty `options`. Card 2 is shown when `whatsapp.masked_number` or `note` is present: "WhatsApp number", the mono line "<masked_number> · verified" (or "· not verified" when `verified` is false), then `note` (13px, muted). Then the "Save settings" button (`psl-btn`, action blue, 50px, max-width 260px). |
| Default (390), board SCR-15-mobile-settings | In order: the back link "← Notifications" (`/notifications`, under the phone bar per D-08); `h1` "How you're alerted" (24px); one white card per returned event (2px ink border, 12px padding) holding the bold `label`, `locked_reason` if present, a line with the switch + "WhatsApp" and the switch + "Email" (16px gap, 13px), and `timing_label` (12px, muted) if present. Then the line "Quiet hours <label of the option whose value equals quiet_hours.value>" (13px, muted), only when both exist. Then a footer stuck to the bottom of the viewport (white, 2px ink top border, 12px 16px 18px) holding "Save settings" full width (`psl-btn--xl psl-btn--block`, action blue). No digest select, no number card and no quiet-hours select, as drawn (PMO-0-5). Every returned event renders, including "Everything else". |
| Switch | `button type="button" role="switch" aria-checked` with `aria-label` "<WhatsApp\|Email>, <label>" (e.g. "WhatsApp, A decision is waiting for me"). It is 44×26 with a 2px `--ink` border, 2px padding and an 18px square knob. On: `--ink` fill with a `--surface` knob at the right. Off: `--surface` fill with an `--ink` knob at the left. Space and Enter toggle. There is a 44px hit area on the phone. Locked (event has `locked_reason`): `aria-disabled="true"`, `--disabled` colours, and no toggle. The visible text "WhatsApp"/"Email" on the phone is `aria-hidden`, because the switch already carries the name. |
| Saving | The button reads "Saving…" with `aria-disabled="true"`. Switches and selects stay as they are. |
| Saved (200) | The state is replaced by the response body. `psl-callout psl-callout--success role="status"`: "Your alert settings are saved." above the Save button. It clears on the next edit. |
| Stale (409) | The page re-reads E-ALERT-PREFS-READ and renders it with no edits kept. `psl-callout psl-callout--warning role="alert"`: "Someone changed these settings since you opened them. This is the latest version; make your changes again." Focus moves to the callout. If the re-read fails, the settings error card shows. |
| Invalid (422) | The edits are kept. `psl-callout psl-callout--problem role="alert"` above Save: "We couldn't save your settings." followed by the returned `message` verbatim (e.g. "Check these fields: channel."). Focus moves to the callout. |
| Save problem (403, 404, 5xx, network) | The edits are kept. `psl-callout psl-callout--problem role="alert"`: "We couldn't save your settings. Nothing was changed." + the returned message + "Reference {code} for support." Save stays available for a manual retry. |
| Load error, or no `events` | `shell-errorcard role="alert"`: "ERROR · COULDN'T LOAD" / "We couldn't load your alert settings. Your work is safe; nothing was changed." / "Reference {code} for support." (the code is `missing_events` when the 200 lacks `events`) / "Try again". No matrix, no cards, no Save. |
| Signed out (401) on read or save | `SignedOutState pathname="/settings/alerts"`. |

### Mock (`frontend/mock/alerts.mjs`)
- **Export:** `createAlertsMock({ overlay })` returns `{ handle({ operationId, url, raw, persona, cookies }) → { status, body }, reset() }`. It holds in-memory state per `persona:scenario` key.
- **Scenario selection:** the cookie `psl_mock_alerts`, else the env `MOCK_ALERTS_SCENARIO`, else `board`. The env exists because Playwright scopes a `url` cookie to the page's directory (`/settings/`), so a cookie set for `/settings/alerts` never reaches `/api`.
- **Scenarios:**
  - `board`: the fixtures above.
  - `phone`: the SCR-15-mobile-settings board's data. It has the first four events only, `timing_label` "Daily digest" on "Work I started is verified", and the quiet-hours option label "20:00 to 07:00 and weekends". The list is as in `board`.
  - `empty`: no items, `total: 0`, `unread_count: 0`.
  - `many`: 25 alerts, paged by 20 with `o<offset>` cursors.
  - `bare`: every proposal field is absent from E-NOTIFICATIONS, and E-ALERT-PREFS-READ and E-NOTIFICATION-READ answer 404 `not_found`.
  - `stale`: the first PUT for that state answers 409 and moves the stored record to `revision + 1` with "Work I started is stuck" email off (another person's save). Later PUTs follow the normal rules.
  - `invalid`: GET returns `channel: "sms"`. Any PUT that echoes it fails the request schema → 422 "Check these fields: channel.".
  - `locked`: as `board`, plus a locked event `{ key: "payroll_problems", label: "Payroll problems", whatsapp: false, email: false, locked_reason: "Only HR can receive payroll alerts outside the app" }`.
- **Personas:**
  - finance_lead (Ada Okafor) is as above.
  - pm (Tunde Bello) has two alerts of their own (`N-0101`, `N-0102`, none shared with finance_lead) and preferences with masked number "+234 805 *** 1180".
  - none (Sample Person) has one alert `N-0201` and default preferences. AppShell never shows this persona the page, but the generic contract test reads it.
- **E-NOTIFICATIONS rules:**
  - the persona's rows, filtered by `q` (case-insensitive substring of `text` or `reference`), `agent`, and `unread` (`true` → unread only, `false` → read only);
  - then paged by `limit` (default 20) and `o<offset>`;
  - `total` is the filtered count, and `unread_count` is all of the persona's unread alerts;
  - an invalid `limit`, an invalid `cursor`, an empty `q` or an unknown `agent` answers 404 `{code:"invalid_query", message:"We could not read that list request."}`;
  - dates are shifted by whole days so that the fixture's `as_of` falls on today in Africa/Lagos (so "10:42" and "yesterday" render as on the board on any day).
- **E-NOTIFICATION-READ rules:** the persona's own id → set `read: true` → 200 `{id, read: true, unread_count}`. A repeat gives the same 200. Any other id, including another persona's → 404 with `SCENARIO_BODIES[404]`.
- **E-ALERT-PREFS-READ:** the stored record.
- **E-ALERT-PREFS rules:**
  1. validate the body against the overlay PUT request schema (Ajv 2020, strict, with formats) → 422 "Check these fields: <names>." using the same field-name rule as `errorFields` in `server.mjs`;
  2. an unknown event key, or a changed value on a locked event → 422 `events`;
  3. `digest_at` or `quiet_hours` not among the options → 422 for that name;
  4. `expected_revision` present and not equal to the stored revision → 409 `SCENARIO_BODIES[409]`. If it is absent, the save is accepted, because a v6 body carries no revision;
  5. apply the sent fields, store `channel` and `frequency` as sent, increase `revision` by 1, and answer 200 with the full record.
- **Default fixtures** required by `createMockServer`: `fixtures/E-NOTIFICATIONS.json`, `fixtures/E-NOTIFICATION-READ.json`, `fixtures/E-ALERT-PREFS-READ.json` and `fixtures/E-ALERT-PREFS.json` (the `board` bodies). Scenario and persona data live in `fixtures/alerts/**`. No fixture carries `sample` or a SAMPLE DATA marker: these schemas have no `sample`, and the UI renders no `SampleLabel`.
- **`server.mjs` seam** (the whole edit, listed in build.md):
  1. one header-comment line;
  2. `import { createAlertsMock } from './alerts.mjs';` and load the overlay;
  3. in `createMockServer`, append `loadRoutes(overlay)` entries whose `(method, template)` the loaded openapi lacks (v4: GET alert-preferences and POST read);
  4. append `'E-NOTIFICATIONS', 'E-NOTIFICATION-READ', 'E-ALERT-PREFS-READ', 'E-ALERT-PREFS'` to `M1_OPERATIONS`;
  5. `const alerts = createAlertsMock({ overlay });` beside `overrides`;
  6. `alerts.reset();` in the `/__mock/reset` branch;
  7. one dispatch line after the CSRF check: `if (ALERT_OPERATIONS.includes(route.operationId)) { const r = alerts.handle({ operationId: route.operationId, url, raw, persona, cookies }); return send(res, r.status, r.body); }`, with `ALERT_OPERATIONS` exported from `alerts.mjs`.

  Items 5 and 6 go one step past readiness PMO-0-1 (c), because the mock needs state and a reset (Assumptions).

## Lanes
- **Frontend lane (builder) owns:**
  - `frontend/src/app/notifications/page.tsx` and `frontend/src/app/settings/alerts/page.tsx`. Both are thin pages with static `metadata.title`.
  - `frontend/src/features/alerts/**`:
    - `contract-proposal.ts`: the output of `openapi-typescript mock/proposals/alerts.json`, plus exported aliases;
    - `api.ts`: `const alertsApi = api as unknown as Client<AlertPaths>`. This reuses the shared client and its CSRF middleware, and is removed at rebase;
    - `model.ts`: the presentation rules, URL parse and build, and the PUT body builder;
    - `NotificationsPage.tsx`, `AlertsFilterPanel.tsx`, `AlertSettingsPage.tsx`, `AlertSwitch.tsx` and `alerts.css` (tokens and `color-mix` only).
  - `frontend/mock/alerts.mjs`, `frontend/mock/proposals/alerts.json`, the four default fixtures named above and `frontend/mock/fixtures/alerts/**`.
  - The `server.mjs` seam above.
  - A listed edit to `frontend/tests/mock-contract.test.ts`, and nothing else in that file:
    - (a) the four alert operations are taken from the overlay, so their schemas are v7's while the base still loads v4;
    - (b) `BODY['E-ALERT-PREFS'] = { channel: 'both', frequency: 'immediate' }`;
    - (c) a persona-aware path value for `notification_id` (finance_lead `N-0001`, pm `N-0101`, none `N-0201`).
  - New tests:
    - `frontend/tests/alerts-model.test.ts`;
    - `frontend/tests/alerts.test.tsx`;
    - `frontend/tests/alerts-settings.test.tsx`;
    - `frontend/tests/alerts-mock.test.ts`;
    - `frontend/e2e/alerts.spec.ts`.
- **Backend lane:** no files. T-ALERTS, JOB-ALERTS, the real endpoints and the providers are separate. The backend developer may change or refuse every proposal field. build.md lists PMO-0-4 (a)-(e) for them.
- **Integration owner:**
  - Merges F-12 only after F-13 has merged and F-12 has been rebased onto it (PMO-0-1 d). The rebase:
    - deletes the overlay route merge (seam item 3) and `mock/proposals/alerts.json`;
    - deletes `contract-proposal.ts` and the `api.ts` cast, using `api` and the regenerated v7 `schema.d.ts`;
    - reverts edit (a) to `mock-contract.test.ts`;
    - points the alerts fixture tests at `OPENAPI_PATH` (v7).
  - Resolves `server.mjs` and `mock-contract.test.ts` conflicts with the other lanes (F-05..F-11). Their edits are additive appends.
- **Shared files, owned elsewhere and not to be changed:**
  - `frontend/src/shell/**` (the bell, account menu and nav entry belong to FE-ALERTS-MENU);
  - `frontend/src/api/**` and `frontend/src/styles/**`;
  - `frontend/src/features/{my-work,work-item,decide}/**`, which are imported read-only;
  - `src/app/assistant/**`, `src/features/assistant/**` and `src/features/start-work/**`;
  - F-13's files: `src/api/schema.d.ts`, `package.json` `gen:api`, `tests/api-schema-drift.test.ts` and `src/api/client.ts`;
  - other lanes' mock files and fixtures;
  - `frontend/public/**`;
  - `package.json`, the lockfile, `playwright.config.ts` and `vitest.config.ts`;
  - `architecture/**` and `design/**`;
  - the protected `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json`.
- **Ports:** app 4201, mock 4202. E2E: `cd frontend && E2E_PORT=4201 MOCK_PORT=4202 npx playwright test e2e/alerts.spec.ts`. Dev: `cd frontend && MOCK_PORT=4202 npm run dev -- -p 4201`.

## Acceptance criteria
1. **The overlay is verbatim v7 and the core never drifts.** `tests/alerts-mock.test.ts` asserts:
   - the overlay's three path items deep-equal `architecture/packages/v7/openapi.json` at `/api/v1/notifications`, `/api/v1/notifications/{notification_id}/read` and `/api/v1/me/alert-preferences`;
   - every fixture under `fixtures/alerts/**`, and the four default fixtures, validate against the overlay's 200 schema;
   - for E-NOTIFICATIONS and E-ALERT-PREFS, the same bodies with the proposal properties removed validate against the v4 operation in `OPENAPI_PATH`, and so do the PUT request bodies the UI builds.

   Verify: `cd frontend && npx vitest run tests/alerts-mock.test.ts` passes. In build.md, record a negative run in which one overlay description is edited and the deep-equal fails, then revert it.
2. **Local types match the overlay.** A test regenerates `openapi-typescript mock/proposals/alerts.json` into a temp file and compares it with the generated part of `src/features/alerts/contract-proposal.ts`. Verify: the same vitest run passes, and `git diff --stat <base>..HEAD -- frontend/src/api frontend/package.json frontend/tests/api-schema-drift.test.ts` is empty.
3. **The generic mock test passes with the alert operations included.** Verify:
   - `npx vitest run tests/mock-contract.test.ts` passes, including "E-NOTIFICATIONS / E-NOTIFICATION-READ / E-ALERT-PREFS-READ / E-ALERT-PREFS succeeds for persona …" for all three personas and every declared error status;
   - `git diff <base>..HEAD -- frontend/tests/mock-contract.test.ts` shows only edits (a)-(c) from Lanes;
   - `git diff <base>..HEAD -- frontend/mock/server.mjs` shows only seam items 1-7.
4. **Own records only (wrong user).** `alerts-mock.test.ts` asserts:
   - pm's list never contains an id from finance_lead's list;
   - pm marking `N-0002` answers 404 `not_found`, and finance_lead's `N-0002` stays read as it was;
   - pm's preferences show "+234 805 *** 1180", never finance_lead's number.

   The UI never sends a person or user id. Verify: the vitest run passes, and `grep -rn "person\|user_id" frontend/src/features/alerts` finds no request parameter.
5. **CSRF on both writes.** Verify, in `alerts-mock.test.ts`:
   - a PUT or mark-read without `X-CSRFToken`, or with another persona's token, answers 403 `csrf_failed`;
   - in `alerts.test.tsx` and `alerts-settings.test.tsx`, the stubbed fetch sees `X-CSRFToken: mock-csrf-finance_lead` on the POST and the PUT.
6. **The list matches the board at 1440.** With the mock on `board`, `/notifications` shows, in order: "NOTIFICATIONS", "Notifications", "Alert settings", the search "Search notifications", "Filter", "4 ALERTS", then four rows:
   - "Invoice for Lagoon Health is waiting for your review" / "Chidi · WhatsApp and email · 10:42" / NEW;
   - "The UAT response for Lagoon Health is due tomorrow" / "Tola · Email · 09:00 daily digest";
   - "October payroll has 2 problems for HR" / "Zainab · In app only (you are not HR)";
   - "Milestone 1 invoice was verified" / "Chidi · In app · yesterday".

   The rows show `/agents/chidi.png`, `/agents/tola.png`, `/agents/zainab.png` and `/agents/chidi.png`. Only row 1 has the unread tint and 600 weight. Verify: `alerts.test.tsx` asserts the texts, order and attributes, and `e2e/alerts.spec.ts` asserts the same at 1440 and takes a screenshot.
7. **The list matches the board at 390.** At 390 the page shows "← Home", "Notifications", the search, the "Filter" icon button, the same four rows, then "Alert settings". There is no eyebrow and no count line, and `document.documentElement.scrollWidth <= innerWidth`. Verify: `e2e/alerts.spec.ts` at 390.
8. **Every meta-line rule holds.** `alerts-model.test.ts` covers:
   - each board line;
   - absent `delivered_via` → "Chidi · 10:42";
   - `["in_app","email"]` → "Email and in app";
   - an older date → "12 Nov";
   - an unknown agent → key as name and no image;
   - "1 ALERT" / "0 ALERTS";
   - no `total` → no count line.

   Verify: `npx vitest run tests/alerts-model.test.ts` passes.
9. **Absent proposal fields are never invented.** With `bare` (cookie `psl_mock_alerts=bare`):
   - `/notifications` shows the four texts with "<Agent> · <time>" meta lines;
   - there is no search, no Filter, no "ALERTS" count line and no "unread" text, so nothing reads "0 ALERTS" or "0 unread";
   - opening row 1 still goes to `/work/W-1001`, and back on the list row 1 still shows NEW;
   - `/settings/alerts` shows the settings error card ("We couldn't load your alert settings…", Reference `not_found`), with no table and no Save button.

   Verify: `e2e/alerts.spec.ts` "bare" test. `alerts-settings.test.tsx` also covers a 200 without `events` (Reference `missing_events`, no Save).
10. **Search and Filter send only the v7 parameters and show what is returned.** Verify, in `e2e/alerts.spec.ts`:
    - typing "payroll" leaves one row and "1 ALERT", and the URL has `q=payroll`;
    - Filter → Agent "Chidi" → Show results leaves two rows and "Filter · 1";
    - "Unread only" shows the hint "1 unread", and after Show results one row with NEW remains;
    - a query matching nothing shows "No alerts match", and "Clear search and filters" restores four rows;
    - at 390 the Filter opens as a bottom sheet;
    - the requests seen by `page.on('request')` carry only `q`, `agent`, `unread` and `cursor`.
11. **Opening an alert marks it read and goes to its work.** Verify, in `e2e/alerts.spec.ts` (with a `/__mock/reset` before):
    - clicking row 1 issues one POST `/api/v1/notifications/N-0001/read` with `X-CSRFToken` and lands on `/work/W-1001`;
    - going back shows row 1 without NEW, and the Filter hint reads "0 unread";
    - clicking an already-read row (row 4) sends no POST and lands on `/work/W-1006`;
    - clicking the restricted row 3 lands on `/work/W-1099`, which shows the existing no-access state and nothing about payroll beyond the alert text.

    `alerts.test.tsx` covers a mark-read that fails with 500 and one that fails with a network error: in both, navigation still happens, exactly one POST is sent, and NEW stays on the next render.
12. **List states follow STATES.**
    - With `empty`, the page shows "No alerts yet." in `psl-empty`, keeps "Alert settings" and shows "0 ALERTS".
    - While loading, `LoadingState` (role=status) shows and no rows do.
    - With `psl_mock_scenario=404` on the list request (e2e: `page.route` adding `X-Mock-Scenario: 404` to `/api/v1/notifications` only), the error card shows "ERROR · COULDN'T LOAD", "We couldn't load your alerts. Your work is safe; nothing was changed." and "Reference not_found for support.", and "Try again" re-reads and shows the four rows once the route is removed.
    - A network abort after a successful load (search change) shows "Last loaded HH:MM.".
    - With `many`, "Show more" loads rows 21-25 and disappears, and a failed Show more keeps the 20 rows and shows "We couldn't load more. Nothing was changed.".

    Verify: `alerts.test.tsx` and `e2e/alerts.spec.ts`.
13. **401 goes to the signed-out state.** A 401 on the list request shows `SignedOutState` with a sign-in link whose `next` is `%2Fnotifications` (plus the encoded search when present). A 401 on the settings read, or on the save, shows it with `next=%2Fsettings%2Falerts`. Verify: `alerts.test.tsx`, `alerts-settings.test.tsx`, and one e2e case through `page.route` adding `X-Mock-Scenario: 401` to the alerts request only.
14. **Settings match the board at 1440.** With `board`, `/settings/alerts` shows, in order:
    - "SETTINGS / ALERTS" and "How you're alerted";
    - the table WHEN / WHATSAPP / EMAIL / TIMING with five rows: the three "Straight away" events on/on, "Work I started is verified" off/on "In the daily digest", and "Everything else" off/on "In the daily digest";
    - "Daily digest at" with 08:00 selected and three options, and "Quiet hours" with "20:00 to 07:00, and weekends" selected;
    - "WhatsApp number", "+234 803 *** 4412 · verified" and "Alerts never include amounts or client details beyond the name.";
    - "Save settings".

    Verify: `alerts-settings.test.tsx` and `e2e/alerts.spec.ts` at 1440.
15. **Switches are real, named toggles.** Every switch is `role="switch"` with `aria-checked` matching the data and the name "WhatsApp, <label>" or "Email, <label>". Space toggles a switch. With `locked`, "Payroll problems" shows "Only HR can receive payroll alerts outside the app", its switches are `aria-disabled="true"` and do not change on click or Space, and the PUT sends them as read. Verify: `alerts-settings.test.tsx`, plus e2e `getByRole('switch', { name: 'WhatsApp, A decision is waiting for me' })`.
16. **Save sends exactly the contract body and gets a new revision (A-ALERT-PREFS, A-ALERTS frontend half).** Turning off "Email, Work I started is stuck", choosing digest "09:00" and pressing Save sends one PUT with `X-CSRFToken` and the body `{ channel: "both", frequency: "immediate", expected_revision: 3, events: [five {key, whatsapp, email} in order], digest_at: "09:00", quiet_hours: "20-07-weekends" }`. Nothing else is sent: no label, timing or number. The response shows revision 4 internally and "Your alert settings are saved.". A reload shows the saved values. A second save sends `expected_revision: 4`. Verify: `alerts-settings.test.tsx` asserts the body by deep-equal, and `e2e/alerts.spec.ts` checks the saved values after `page.reload()`.
17. **A stale save reloads the newer version and keeps no edits (409).** With `stale`, toggling "WhatsApp, A decision is waiting for me" off and pressing Save gives:
    - the callout "Someone changed these settings since you opened them. This is the latest version; make your changes again.", focused;
    - "WhatsApp, A decision is waiting for me" back on (the server's value), and "Email, Work I started is stuck" off (the other person's change).

    A second save then sends `expected_revision: 4` and succeeds. Verify: `e2e/alerts.spec.ts` "stale" test and `alerts-settings.test.tsx`.
18. **Invalid input is shown as returned and never remapped (422).** With `invalid`, Save sends `channel: "sms"` unchanged and shows "We couldn't save your settings. Check these fields: channel." in a focused `role="alert"` callout. The edits stay. Verify: `e2e/alerts.spec.ts` "invalid" test, plus `alerts-settings.test.tsx` asserting the sent `channel` is `"sms"`.
19. **Save failures keep the edits and do not retry.** A 500 or network failure on the PUT shows "We couldn't save your settings. Nothing was changed." with the reference, keeps the edits, and sends no further PUT until Save is pressed again. A double press while saving sends one PUT. Verify: `alerts-settings.test.tsx`.
20. **The phone settings match the board at 390 (PMO-0-5).** With the mock started as `MOCK_ALERTS_SCENARIO=phone`, `/settings/alerts` at 390 shows, in order:
    - "← Notifications" and "How you're alerted";
    - four event cards, each with its two named switches and "Straight away" / "Daily digest";
    - "Quiet hours 20:00 to 07:00 and weekends";
    - a bottom footer with "Save settings".

    There is no "Daily digest at" select and no "WhatsApp number". With `board`, a fifth card "Everything else" renders. A phone save body has no `digest_at` and no `quiet_hours`. There is no horizontal scroll. Verify: `e2e/alerts.spec.ts` at 390 and `alerts-settings.test.tsx` (phone media query).
21. **The masked number is never unmasked or sent.** The page shows `whatsapp.masked_number` byte-for-byte, and no request body contains "4412" or "masked". Verify: `alerts-settings.test.tsx` checks every PUT body, and `grep -rn "masked_number" frontend/src/features/alerts` shows read-only use.
22. **Navigation targets used by the backend messages are stable (PMO-0-3).** `/notifications` and `/settings/alerts` render their headings on a direct load. `/work/W-1001` opened signed out returns through `SignedOutState`'s `next`. Verify: `e2e/alerts.spec.ts` direct loads, plus an existing frame signed-out case (no frame edit).
23. **Accessibility (A-ACCESSIBILITY).** axe (wcag2a, 2aa, 21a, 21aa, 22aa) reports no violations on:
    - the list default, the Filter open, the empty state and the error state;
    - the settings default, the saved state, the stale state and the invalid state;

    each at 1440 and 390. Tab order follows the visual order. The focus ring is visible on rows, switches, selects and Save. Phone targets are at least 44px. Motion respects `prefers-reduced-motion`. Verify: `e2e/alerts.spec.ts` (pattern: `e2e/my-work.spec.ts`, `timezoneId: 'Africa/Lagos'`).
24. **Design-fidelity gate, 1440 and 390, on board data.** For each board and width, coverage must be 100% after approved exceptions and visual at least 90:
    - `SCR-15-desktop` on `/notifications` at 1440;
    - `SCR-15-mobile` on `/notifications` at 390;
    - `SCR-15-desktop-settings` on `/settings/alerts` at 1440 (mock `board`);
    - `SCR-15-mobile-settings` on `/settings/alerts` at 390 (mock started with `MOCK_ALERTS_SCENARIO=phone`).

    Verify, after `/__mock/reset`: `node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright frontend/node_modules/playwright/index.mjs --board design/canvas/project/<board>.dc.html --page http://localhost:4201/<route> --width <W> --exceptions delivery/features/F-12/fidelity-exceptions.json --wait-ms 800 --out delivery/features/F-12/round-<N>/fidelity/<board>-<W>` exits 0. Then `results.txt` lists all four PASS, and the UI reviewer's side-by-side reading finds no remaining difference.

    The STATES cards are pattern sheets, so the tool cannot score them against one page. Their SCR-15 elements (the empty text, the loading pattern, and the error card's eyebrow, sentence, reference line and Try again) are checked by criteria 12 and 23 and by the reviewer's side-by-side against STATES-desktop and STATES-mobile. This is listed as exception request E-5 below.
25. **The suite and build are green.** Verify: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build` exits 0, and `git diff --stat <base>..HEAD` lists only the paths under Lanes.

### Exception requests for the design engineer (to record in `delivery/features/F-12/fidelity-exceptions.json`; only the design engineer can approve them)
- **E-1:** SCR-15-desktop-whatsapp, SCR-15-mobile-whatsapp, SCR-15-desktop-email and SCR-15-mobile-email are rendered by the backend alert job (T-ALERTS / JOB-ALERTS), not the frontend. F-12 owns only their targets: "Review now" → `/work/<work_id>`, and the "alert settings" link → `/settings/alerts` (PMO-0-3).
- **E-2:** frame items: link "Start work" and link "More ways to start" (CMP-23, F-05's frame; `src/shell/**` is not F-12's), on SCR-15-desktop and SCR-15-desktop-settings.
- **E-3:** "Save settings" is drawn as a link (role link) and built as a button (role button), because it submits a form.
- **E-4:** the phone back links "← Home" and "← Notifications" sit under the frame's phone bar, not inside it (D-08, provisional). Request this only if the tool reports them as moved and the visual score falls below 90.
- **E-5:** STATES-desktop and STATES-mobile are checked element-by-element for the SCR-15 cards (criterion 24), not by a whole-board score.

## Out of scope
- The bell, the account menu, sign-out, a top-bar or phone-menu entry for Notifications, and any `src/shell/**` change (FE-ALERTS-MENU, D-ALERTS-ENTRY, D-SIGNIN). The SCR-15-desktop-account and SCR-15-mobile-account boards.
- The assistant (FE-ASSISTANT).
- Rendering or sending WhatsApp or email messages, templates, providers, the outbox, JOB-ALERTS and T-ALERTS. Nothing contacts WhatsApp or email.
- Backend, `apps/api`, the real API, migrations, and connecting to Django.
- F-13's repoint: `schema.d.ts`, `gen:api`, the drift test and `client.ts`. Editing `architecture/**`, `openapi.json` or `design/**`.
- A channel or frequency editor, an unread badge or count anywhere the boards do not draw one, a "Mark all read" action, deleting or archiving alerts, or rows-per-page controls.
- Showing `reference` or `delivered_at` as extra text, or computing totals or unread counts from rows.
- Polling or live refresh of the list (D-UPDATES r2 names My work, the work item and the overview only).
- Field-level highlighting from a 422 (the contract gives only a message), and parsing the message.
- Adding digest, quiet-hours selects or the number card to the phone. The design engineer may ask for them later (PMO-0-5).
- New npm dependencies, a SAMPLE DATA tag or `SampleLabel` on these pages, and avatar files (already on base).
- Changing `delivery/checks.sh`, `delivery/config.json` or `delivery/merge-policy.json`.

## Assumptions
- The settings page stays on `/settings/alerts` after a successful save and shows "Your alert settings are saved.", although the board's Save links to the list. A confirmation in place keeps the new revision visible and testable. This is flagged for product acceptance.
- The whole alert row is one link in ink colour (the board draws no link styling), so a person can open an alert anywhere on the row. Modifier-clicks open a new tab without marking the alert read.
- Mark-read is awaited before navigating, and failures still navigate (PMO-0-4 d). There is no optimistic NEW removal: the list is re-read on return, so it shows the server's truth.
- *when* falls back from `delivered_at` to the base `at`. `at` is a base field, so showing it invents no delivery claim. The channel words still appear only with `delivered_via` (readiness PMO-0-2). A digest alert shows the digest time, not the creation time, as drawn.
- Times are formatted in Africa/Lagos (`formatClock`, `formatWat`; the boards say "Times are WAT"), and "today" and "yesterday" are WAT days.
- The board's unread tint #FBF5F2 is not a token, and literal colours are banned by `tests/styles-drift.test.ts`. The tint is a `color-mix` of `--signal-tint` and `--surface`, and the fidelity visual score is the check.
- The loading state reuses the frame's `LoadingState`, like every merged list. The STATES sentence "Loading figures…" is the sheet's note for reports and queues.
- `total` is the filtered count, and `unread_count` is all of the person's unread alerts (the number a bell would show). The mock follows this, and build.md lists it for the backend developer.
- Locked events go back in the PUT with their values as read, rather than being omitted, so the `events` list stays complete. The mock rejects a changed locked value with a 422.
- The `phone` mock scenario carries the phone board's own wording ("Daily digest", "20:00 to 07:00 and weekends"), which differs from the desktop board. The UI shows `timing_label` and option labels verbatim, so the boards differ only in data (precedent D-04 f). This is flagged for product acceptance.
- `MOCK_ALERTS_SCENARIO` exists because Playwright scopes a `url` cookie to the page's directory. Without it, the phone settings fidelity run could not reach the mock.
- The `server.mjs` seam adds state construction and reset (items 5 and 6) beyond readiness PMO-0-1 (c), because saves and mark-read must persist within a run and `/__mock/reset` must clear them. The four default fixtures are required by `createMockServer`'s per-id load.
- `mock-contract.test.ts` gets a three-part listed edit, because its generic loop validates against v4 and cannot reach the two v7-only operations. The rebase reverts edit (a).
- "← Home" on the phone list links to `/` (HomeRedirect picks the first destination), as the board's "← Home" points at SCR-01.
- If the response lacks `total` while the URL has filters, the page drops the filters and re-reads once. Otherwise a person could be stuck on a filtered list with no visible control to clear it.
