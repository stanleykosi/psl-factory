# Staff accounts, read-only: see who has an account and what each person can reach

> Tasks: FE-SETUP-ROLES. Architecture: package revision not stamped in feature.json (baseline fields are null); D-ADMIN-AUTHORITY is still open at revision 1, so every write is held. Design: approved canvas, SCR-21 boards (SCR-21-desktop, SCR-21-mobile; the invite and deactivate boards are not built here); screens: SCR-21.

## Summary
- Replaces the "Staff accounts comes next" placeholder at `/setup/staff` with the live staff list (`GET /api/v1/staff`), built straight on the live contract.
- Adds one person's page (`GET /api/v1/staff/{person_id}`) showing their access by workspace.
- Read-only. No Invite, Deactivate, Restore, Resend or Edit roles control is drawn as active, because PSL has not said who holds Admin (D-ADMIN-AUTHORITY, D-182).
- Board parts the live API cannot fill are hidden, not faked (D-182): the "8 people" count, "Last signed in", "Invite sent N days ago", "Deactivated <date>", and roles written per workspace.
- Who may open it is whatever the server decides (A-53): the list shows to whoever the server serves it to; a 403 shows the existing not-open state. No Admin role is guessed.

## Context
- `frontend/src/features/setup/ReservedTab.tsx` is the placeholder; `frontend/src/app/setup/(tabs)/staff/page.tsx` renders `<ReservedTab tab="staff" />`.
- The tab already exists: `SETUP_TABS` in `frontend/src/features/setup/SetupFrame.tsx` has `{ key: 'staff', label: 'Staff accounts', href: '/setup/staff' }`, and `staff` is in `PHONE_FRAME`. The layout matches tabs by path prefix, so `/setup/staff/<id>` keeps the "Staff accounts" tab selected.
- Shared Setup pieces to reuse: `SetupLayoutFrame`/`SetupGate`, `useSetupRead` (tell the frame the read's state), `RulesReadState` (loading, signed-out, 403/404 to `NotOpenState`, other errors to `WorkErrorCard` with retry; pass `what="staff accounts"`), `useSetupPaging`, `useSetupPhoneBack`, `asApiError` from `useSetupRules.ts`, and the Setup read hooks' shape in `useTemplates.ts`.
- Live client: `liveApi` and `call` from `frontend/src/api/client.ts`; types from `frontend/src/api/live-schema.d.ts`. Existing example of a live-only read: `frontend/src/shell/useRoleWords.ts`.
- Live-only mock routes live in `frontend/mock/session.mjs` and are wired in `frontend/mock/server.mjs` (the `SESSION_PATH`/`ROLE_DASHBOARD_PATH` branch). The pattern to copy is `frontend/tests/mock-live-me.test.ts` (fixtures and served bodies validated by Ajv against `contracts/psl-factory.openapi.json`).
- Live contract (1.22.0), both reads need a signed-in session and answer 401/403/404/422/503 in the standard error body:
  - `GET /api/v1/staff?page&invitations_page&q&status=all|active|inactive` returns `{people[<=25]{id,name,username,email,active,workspace_count,access,departure_available,reactivation_available}, invitations[<=25]{id,case_id,name,username,email,access,expires_at,status: pending|expired|accepted|superseded}, next_page, next_invitations_page, observed_at, available}`.
  - `GET /api/v1/staff/{person_id}?page` returns `{person{id,name,username,email,active}, workspaces[<=20]{case_id,name,access,primary_role|null,can_edit_profile,can_assign_primary_role}, next_page}`.
- Board: `design/canvas/project/SCR-21-desktop.dc.html` and `SCR-21-mobile.dc.html` (list: search, filter, person, roles, account state, row action; invited and deactivated rows).

## Contract
### Route and gate
- `/setup/staff`: the list. `/setup/staff/[personId]`: one person (new `frontend/src/app/setup/(tabs)/staff/[personId]/page.tsx`). Both sit under the existing Setup tabs layout and gate (no Setup destination, no call).
- No client-side role check decides who sees the tab content. The server's answer does (A-53). Hiding the tab for roles the server refuses is not done here (tab list is lane A's and unchanged).

### Reads
| Call | Sent when | Notes |
|---|---|---|
| `GET /api/v1/staff` | page opens; search (`q`, trimmed, max 120) and status filter (`all` default, `active`, `inactive`) change; "Show more" | `page` and `invitations_page` are separate counters. People and invitations append independently, in the order served. Changing `q` or `status` resets both to the first page. |
| `GET /api/v1/staff/{person_id}` | person page opens; "Show more" workspaces | Follows `next_page`. `person_id` is the integer from the list row. |

### List screen states
- **Loading:** shared `LoadingState`.
- **Success:** header "Staff accounts", search box, status filter (All, Active, Inactive), then the people table (desktop) or cards (phone). Each person row: name, email, `access` string as the person's roles text, account state ACTIVE or DEACTIVATED from `active`, and a link to the person page. If `invitations[]` is non-empty, an "Invited, not set up" group below lists name, email, `access`, and expiry from `expires_at` ("Expires <date>" for `pending`; "Expired" for `expired`); `accepted` and `superseded` rows are shown as "Accepted" and "Replaced by a newer invitation", not as pending.
- **Empty:** no people and no invitations for the current search/filter: "No staff accounts to show." with a note that a search or filter may be hiding people (shared `EmptyState`).
- **Not available:** `available: false` in the body: say the list could not be read in full right now, show what came back, and show `observed_at` as "As of <time>". (Assumption A-2 below.)
- **Forbidden / not found:** 403 or 404 shows `NotOpenState` via `RulesReadState`; nothing about the list or about who may open it is revealed. 401 shows `SignedOutState`.
- **Error (network, 5xx, 422):** `WorkErrorCard` "We couldn’t load the staff accounts. Your work is safe; nothing was changed." with retry. A failed "Show more" keeps the rows already on screen and shows an inline retry.
- **Hidden (no live data):** people count, "Last signed in", "Invite sent N days ago", "Deactivated <date>", roles per workspace. The `access` string is shown as served and is not split or reworded.
- **Actions column:** the board's row actions (Edit roles, Deactivate, Resend invite, Restore) are not drawn. `departure_available` and `reactivation_available` are read but not used to draw controls in this feature.

### Person screen states
- Header: the person's name, email, username, and account state (from `person.active`), with a "Staff accounts" back link (phone: `useSetupPhoneBack`-style back to the list).
- **Success:** "Access by workspace": one row per workspace with `name`, `access`, and `primary_role` ("No primary role set" when null). Two read-only lines per row render the server's flags: "Profile can be edited by you" / "Primary role can be assigned by you" only when `can_edit_profile` / `can_assign_primary_role` is true; when false, no line is drawn. No button is attached to either flag (writes held).
- **Empty:** no workspaces: "This person has no workspace access."
- **Loading, forbidden, not found, signed-out, error:** as the list. A person id that is not a positive integer shows the not-open state without a call.
- **Hidden:** per-workspace role wording beyond `access` and `primary_role`; last sign-in; dates.

### Fixture examples (mock, live-shaped)
`GET /api/v1/staff` desktop fixture (shape; values are sample data for tests):
```json
{"people":[{"id":11,"name":"Ada Okafor","username":"ada.okafor","email":"ada.okafor@psl.example","active":true,"workspace_count":2,"access":"Finance Lead","departure_available":true,"reactivation_available":false},
{"id":19,"name":"Ife Johnson","username":"ife.johnson","email":"ife.johnson@psl.example","active":false,"workspace_count":0,"access":"No access","departure_available":false,"reactivation_available":true}],
"invitations":[{"id":4,"case_id":"00000000-0000-4000-8000-000000000004","name":"Sola Martins","username":"sola.martins","email":"sola.martins@psl.example","access":"PMO","expires_at":"2026-11-26T09:00:00Z","status":"pending"}],
"next_page":null,"next_invitations_page":null,"observed_at":"2026-11-23T12:00:00Z","available":true}
```
`GET /api/v1/staff/11`: `{"person":{"id":11,"name":"Ada Okafor","username":"ada.okafor","email":"ada.okafor@psl.example","active":true},"workspaces":[{"case_id":"…","name":"Lagoon Health","access":"Finance Lead","primary_role":"finance-lead","can_edit_profile":true,"can_assign_primary_role":false},{"case_id":"…","name":"Harmattan Bank","access":"Finance Lead","primary_role":null,"can_edit_profile":false,"can_assign_primary_role":false}],"next_page":null}`.

### Mock
- New `frontend/mock/staff.mjs` (routes `/api/v1/staff` and `/api/v1/staff/{id}`, per persona, scenarios via the existing `X-Mock-Scenario`/cookie convention including 401, 403, 404, 503 and an `empty` data scenario) and fixtures under `frontend/mock/fixtures/staff/`, wired in `frontend/mock/server.mjs` beside the session branch. Staff list answers 403 for personas without access (the mock decides, the app does not). The mock must have at least 30 people (to exercise `next_page`), one inactive person, an invitation of each status, and `available: false` under a scenario. No write routes.
- Every fixture and served body is validated with Ajv against the live contract schemas, as `tests/mock-live-me.test.ts` does.

## Lanes
- **Frontend lane (lane B):** new `frontend/src/features/setup/staff/` (list view, person view, hooks, api reads, css), `frontend/src/app/setup/(tabs)/staff/page.tsx` (swap `ReservedTab` for the list), `frontend/src/app/setup/(tabs)/staff/[personId]/page.tsx`, `frontend/mock/staff.mjs`, `frontend/mock/fixtures/staff/`, the one-branch wiring in `frontend/mock/server.mjs`, and new tests under `frontend/tests/`.
- **Backend lane:** none. No change to Django; reads exist in 1.22.0. Backend answers to A-50, A-52 and A-53 are open and do not block this.
- **Integration owner:** the lane B coordinator; runs the browser check against Django 8010 (Postgres 55433).
- **Shared, not edited here:** `frontend/src/api/` and `frontend/src/shell/` (lane A); `frontend/src/features/workspace/` (lane C); `SetupFrame.tsx` and `useSetupRules.ts` are used as they are (F-74 adds a workspace picker in Setup in parallel; do not touch its files; if `ReservedTab`'s `tab` type needs `staff` removed, leave it).
- Leave every path in `delivery/config.json` `protected_paths` unchanged.

## Acceptance criteria
1. With a signed-in account the server serves the list to, `/setup/staff` shows the "Staff accounts" tab selected and one row per person from `GET /api/v1/staff` (name, email, `access`, account state) — verify: open the page against the Django API on 8010 and the mock; the rows match the response body.
2. A person with `active: false` reads as deactivated and an `active: true` person as active, from the data only — verify: mock fixture with both; rows show the two states.
3. Pending, expired, accepted and superseded invitations each read differently, and the "expires" text uses `expires_at` — verify: mock fixture with one of each; component test.
4. The page never shows a people count, "Last signed in", "Invite sent … ago", or "Deactivated <date>" — verify: component test asserts none of those strings render with the full fixture.
5. No Invite, Edit roles, Deactivate, Restore or Resend control exists anywhere on the list or person page, active or disabled — verify: component test finds no button or link with those names; no non-GET request is made on either screen (test asserts the fetch log).
6. Typing in search sends `q` (trimmed, no more than 120 characters) and returns to the first page; choosing Active or Inactive sends `status`; All sends none or `all` — verify: component test reads the request URLs.
7. "Show more" on people follows `next_page` and appends; the invitations group pages by `next_invitations_page` independently; both disappear when the next page is null — verify: mock with 30+ people; row count goes 25 then more.
8. 403 and 404 on `GET /staff` show the existing not-open state and nothing about the list — verify: scenario 403 in the mock; page shows `NotOpenState` text, no table, no frame error. (Wrong user.)
9. 401 shows the signed-out state with a sign-in link; a network or 5xx failure shows the error card with retry, and retry reloads — verify: scenarios 401 and 503.
10. A failed "Show more" keeps the rows already shown and offers a retry — verify: component test, second request fails.
11. `available: false` shows the partial-list notice with "As of <observed_at>" and still shows returned rows — verify: mock scenario.
12. Empty answer shows the empty state, and with a search active mentions the search may be hiding people — verify: scenario `empty` and a `q` with no match.
13. `/setup/staff/<id>` shows the person and one row per workspace with `name`, `access`, and `primary_role` or "No primary role set" — verify: open from a list row; matches `GET /staff/{id}`.
14. A workspace row shows the "can edit profile" / "can assign primary role" lines only when the flags are true, and no control sits beside them — verify: fixtures with each flag combination.
15. A person id the server does not know (404), or one with no access (403), shows the not-open state; a non-numeric id shows it with no request — verify: `/setup/staff/abc` and `/setup/staff/99999`. (Wrong tenant/user.)
16. Invalid input is not sent: a search over 120 characters is cut at 120 and a page counter outside 1 to 10000 is never produced — verify: unit test on the request builder.
17. Every fixture and every mock-served body for both reads validates against `contracts/psl-factory.openapi.json`, and a fixture with an extra key fails — verify: new `frontend/tests/mock-live-staff.test.ts` (run `npx vitest run tests/mock-live-staff.test.ts` from the lane-b `frontend/`).
18. The phone layout (390 px) shows cards with no horizontal scroll and the phone back link on the person page — verify: page at phone width in the Next.js dev server (4970/4971).
19. The frame stays across the list and person pages and drops when a staff read loses access (as other Setup tabs do) — verify: scenario 403 on the second read.
20. Typecheck, lint and the existing tests pass with no change to `src/api`, `src/shell` or `src/features/workspace` — verify: `git diff --stat` for those paths is empty.

## Out of scope
- All writes: invite, resend, deactivate, restore, edit roles or team scope, profile edit, departure; the review-then-confirm flows (SCR-21-invite, SCR-21-deactivate boards); A-51 and A-54.
- Technical delegations (`/staff/delegations/{authority_id}`); the SCR-13 Roles tab; the Setup case-id picker (F-74).
- Deciding who is Admin or who may see this page; hiding the tab by role; any client-side permission rule.
- Counts, last sign-in, sent and deactivated dates, role-per-workspace wording (hidden until the backend adds the data: A-50, A-52).
- Backend changes; new v7 mock operations beyond the live-shaped staff mock.
- Reading `departure_available` or `reactivation_available` to draw anything.

## Assumptions
- A-1: Route for one person is `/setup/staff/[personId]` using the integer id, because the contract keys on it and the layout already matches by prefix.
- A-2: `available: false` means the list may be partial or not fully readable; the contract says only that. Shown as a notice with `observed_at`, no data hidden. Backend should confirm (add to A-50).
- A-3: People page size is the server's 25; no `limit` is sent; "Show more" uses the shared paging footer behaviour of `useSetupPaging` where it fits, else a plain "Show more" button.
- A-4: Invitation `accepted` and `superseded` rows are shown (the server returns them) in plain words rather than filtered, so nothing the server sends is dropped silently.
- A-5: The `access` string is shown verbatim as the board's "Roles" column, and the column is headed "Access" because it is not the per-workspace roles text the board draws.
- A-6: The board's "Filter" button is built as a status select (All, Active, Inactive) because `status` is the only filter the live read has.
- A-7: Mock personas that get 403 are those without Setup access in `mock/fixtures/me.*.json`; if none maps, `pm` and `none` are denied, as in `mock/templates.mjs`.

## Conflicts with the boards
D-182 already decided these; recorded only so the design engineer sees the full set on the SCR-21 boards.
- "8 PEOPLE" count: hidden (no count in the live read). Recommend: show when the backend adds a total (A-50).
- "LAST SIGNED IN" column: removed. Recommend: add back with the data (A-50).
- "Invite sent 2 days ago" on invited rows: replaced by "Expires <date>" from `expires_at`, which is what the API has. Recommend: keep the board wording once `invited_at` exists.
- "DEACTIVATED 30 OCT" date: the state reads "DEACTIVATED" with no date.
- Roles column written as "Finance Lead · Lagoon Health, Harmattan Bank": shown as one `access` text as served, with per-workspace access on the person page; column headed "Access".
- Row actions (Edit roles, Deactivate, Resend invite, History kept) and the "Invite someone" button: not drawn (writes held). Recommend: add when D-ADMIN-AUTHORITY is answered.
- Search and Filter: Filter becomes a three-way status choice (A-6).
- The board has no person page; this adds one (list row opens it) because the live read for one person is the only source of access by workspace. Recommend: design engineer draws it or accepts this one; the invite and deactivate boards stay unbuilt.
- The board's copy "Who can manage accounts is for PSL to confirm" and the Admin chip: not shown.

## Flags for the PR
- A-53 (who may open it) is built on the server's answer, not on an Admin role; reviewers should confirm the 403 shows honestly and no control looks active.
