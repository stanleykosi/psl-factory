# Clients and client details read live client groups and workspace contacts

> Tasks: FE-CONNECT-1. Architecture: v9 package (D-SIGNIN r2 revision on main); live contract `contracts/psl-factory.openapi.json` (operations `clients_directory`, `clients_group`, `workspaces_client`, `clients_contact_history`). Design: approved SCR-35 boards (F-19, DONE); screens: SCR-35 (artboards SCR-35-desktop, SCR-35-mobile, SCR-35-desktop-detail, SCR-35-mobile-detail).

## Summary
- `/clients` lists live client groups and ungrouped projects from `GET /clients`, with search, a billing filter and paging.
- `/clients/[clientId]` opens a group (`GET /clients/groups/{group}`) when the id is a group key, or one workspace's contacts (`GET /clients/{case_id}`) when the id is a case id.
- The billing tag comes from live `billing` (recorded / needed / unknown) and `contacts_needed`. Unknown is shown as unknown, never as "Set", zero or "missing".
- Owed, the money panel and the "blocked" lines are hidden (default B4). No figure is invented. Money stays at `/projects/{case_id}/money`.
- The add-billing-contact form stays visible but disabled with its reason (default B6). No write is sent, neither the retired v7 `PUT` nor `POST /clients/{case_id}/contacts`.
- The v7 mock serves the clients operations in the live shape so design review keeps working.

## Context
- Routes: `src/app/clients/page.tsx`, `src/app/clients/[clientId]/page.tsx` (uses `routeCaseId` from `src/features/projects/model.ts`, which only URL-decodes the segment).
- Feature: `src/features/clients/` (`ClientsList.tsx`, `ClientDetail.tsx`, `BillingContactForm.tsx`, `ClientStates.tsx`, `labels.ts`, `api.ts`, `useClients.ts`, `useClient.ts`, `clients.css`). Today these call the v7 client `api` (`GET /clients` with `limit/cursor`, `GET /clients/{client_id}`, `PUT /clients/{client_id}/billing-contact`) and the v7 types from `src/api/schema.d.ts`.
- Live client: `liveApi` and live types `src/api/live-schema.d.ts` in `src/api/client.ts` (used already by `src/shell/AppShell.tsx`). `next.config.ts` proxies `/api/v1` to `API_ORIGIN` (mock on 4971 by default, Django 8010 for live checks).
- Mock: `mock/clients.mjs` serves the v7 shapes and validates them against the v7 schema; fixtures in `mock/fixtures/clients/` (`list.json`, `CL-35xx.json`). It is wired in `mock/server.mjs` via `CLIENT_OPERATIONS`. Existing tests: `tests/clients.test.tsx`, `tests/clients-mock.test.ts`, `e2e/clients.spec.ts`.
- Precedent for a mock moved to the live shape and validated against the live contract: `tests/mock-live-me.test.ts`.

## Contract

All reads use `liveApi` through `call(...)`. Session cookie, same origin, no CSRF needed for reads. A 401 shows the existing signed-out state; 403 and 404 show the existing `ClientNoAccess` (nothing about the record is revealed, and the tab title stays "Client · PSL Factory"). 5xx, 503 and network failure show the existing `WorkErrorCard` with retry. A 200 that lacks the required fields below is treated as `unexpected_response`.

### `GET /api/v1/clients` (clients_directory)
Query: `q` (text), `billing` (`recorded|needed|unknown`), `clients_page` (groups, from 1), `page` (ungrouped projects, from 1). 25 rows each.
Response 200:
```json
{
  "groups":   [{"key": "9f2c…64 chars", "label": "Acme Logistics", "project_count": 3, "contacts_needed": 1}],
  "next_group_page": 2,
  "projects": [{"case_id": "0b6f…uuid", "title": "Warehouse portal", "client": "Kora Foods", "billing": "needed"}],
  "next_page": null
}
```
- `client` may be null (the project row then shows "Not given").
- Permission and tenant: the server returns only what the person may see; the page adds no filtering of its own.
- Row order is as returned: groups first, then ungrouped projects, in one table.
- Row display:
  - Group row: name `label`, link to `/clients/{key}`, PROJECTS `project_count`. Billing cell: `contacts_needed > 0` reads "N billing contact(s) needed" with the "Billing contact missing" tag; `contacts_needed == 0` reads "None needed" with the neutral tag. (Best reading of B-46; flagged.)
  - Ungrouped project row: name `client` if present, else `title`, with the project title as the second line when `client` is present; link to `/clients/{case_id}`; PROJECTS "1". Billing: `recorded` is "Set" (neutral tag), `needed` is "Missing · invoices can't start" (the "Billing contact missing" tag), `unknown` is "Unknown" (an unknown tag, never "Set").
- Count line: "N clients loaded as of <time>" using the response time the page was read (no `as_of` in live; use the client clock at read, WAT, and say "loaded", never a total). The "N missing billing contact" suffix counts only rows with `needed` or `contacts_needed > 0`, and is shown only when no further page exists.
- Paging: one "Show more" footer. It first requests the next `clients_page` while `next_group_page` is non-null, then the next `page` while `next_page` is non-null. Rows already shown are never replaced and never duplicated (de-duplicate by `key` / `case_id`, because the live response returns both lists on every call). The builder confirms against Django 8010 whether a call with `page=2` also returns groups, and keeps whichever lists it needs.
- Search and filter: the existing board has no search box. Do not add one (see Conflicts). `q` and `billing` are supported by `api.ts` and read from the URL query (`/clients?q=…&billing=needed`) only, so they are testable and deep-linkable.
- States: loading (`LoadingState`), empty (`EmptyState` "No clients"), error, success.

### `GET /api/v1/clients/groups/{group}` (clients_group)
Path `group` is the opaque key, sent URL-encoded. Query `page`.
Response 200: `{"key", "label", "projects": [{"case_id","title","client","billing"}], "next_page": int|null}`.
- Page: breadcrumb "Clients / <label>", title `label`. Projects panel lists each project (title links to `/projects/{case_id}`; a second link "Billing contacts" goes to `/clients/{case_id}`), each with its billing tag (same mapping as above). "Show more" while `next_page` is non-null.
- Billing contact panel: disabled form, see below, with the line "Billing contacts are recorded for each project. Open a project's billing contacts from the list."
- Unknown group: 404, `ClientNoAccess`.

### `GET /api/v1/clients/{case_id}` (workspaces_client)
Response 200: `{case_id, title, revision, sample, contacts: [{contact_id, version, purpose: "project"|"billing", customer, client_name, name, email, role}], django_url}`.
- Page: breadcrumb "Clients / <title>", title `title`, `SampleLabel` when `sample` is true. "Billing contact" panel: each `purpose == "billing"` contact as a read-only block (customer, name, email, role, "version N"). When there is none, the read-only block says "No billing contact recorded" only when the project's billing is known to be needed; otherwise "Not set". Contacts with `purpose == "project"` are listed in a second read-only block, "Project contacts". Projects panel: this workspace, linking to `/projects/{case_id}`.
- History: a "Show history" control calls `GET /clients/{case_id}/contacts/history?purpose=billing` (and `customer` when the contact has one) and lists versions newest first with "Show more" on `next_page`. Read only. Failure shows an inline retry; it does not clear the page.
- `revision` is kept in memory for the future write; it is not shown.

### Billing contact form (disabled, default B6)
The existing `BillingContactForm` fields stay visible (name, email, with the existing Save button) but are disabled (`disabled`, not hidden) and show: "Waiting for the evidence picker and the backend answer." The form never calls `saveBillingContact`; remove the v7 `PUT` call from the live path. It sends no `POST /clients/{case_id}/contacts` and never reads `contacts/options`. Pressing Enter in a field does nothing.

### Money, owed, blocked (default B4)
Not rendered: the OWED column and card line, `MoneyPanel`, the "blocked" `Callout`s. The detail page shows a link "Money for this project" to `/projects/{case_id}/money` on the workspace view only (no link on the group view).

### Route id (default B5)
`/clients/[clientId]`: after `routeCaseId` decoding, a segment matching a UUID is a workspace `case_id`; anything else is a group key. A key can change if grouping changes (B-42); a stale key shows `ClientNoAccess`, and the list is the way back. Fixture examples: group key `a1b2…` (64 hex) → group page; `0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b10` → workspace page.

### Mock
`mock/clients.mjs` serves `GET /clients`, `/clients/groups/{group}`, `/clients/{case_id}`, `/clients/{case_id}/contacts/history` in the live shape, validated against the live contract's response schemas (replace the v7 `E-CLIENTS`/`E-CLIENT` validators; drop `E-CLIENT-CONTACT`). Fixtures cover: groups plus ungrouped projects; a group needing contacts; a group with all recorded; a project with `billing: "unknown"`; `client: null`; a workspace with project and billing contacts and history over two pages; the empty cookie state and the 25-row `many` state keep working (`psl_mock_clients`). The mock returns 404 for an unknown key or case id. Other mock operations stay as they are.

## Lanes
- Frontend lane (builder): `frontend/src/features/clients/**`, `frontend/src/app/clients/**`, `frontend/mock/clients.mjs`, `frontend/mock/fixtures/clients/**`, `frontend/tests/clients*.test.*`, `frontend/e2e/clients.spec.ts`.
- Backend lane: none. No backend change. Questions B-42 to B-46 stay open in `delivery/connect/backend-questions.md`.
- Integration owner: the lane B coordinator. Checks the pages against Django 8010 (accounts live-none, live-lead, live-multi, live-admin).
- Shared files: `src/api/**` and `src/shell/**` are lane A's, `src/features/workspace/**` is lane C's. This feature should not need any change there (`liveApi` already exists). If one is needed (for example a type export), it is a separate small commit named in `build.md`. `mock/server.mjs` is shared: change only the `CLIENT_OPERATIONS` wiring there, as its own small commit if needed. `src/shell/SampleLabel` is reused unchanged.

## Acceptance criteria
1. `/clients` against live shows one row per group and one per ungrouped project, groups first, in the order returned — verify: open `/clients` as live-lead on port 4970 (API_ORIGIN Django 8010) and compare the rows with `curl` of `GET /api/v1/clients` with the same session.
2. A group row shows `project_count` as PROJECTS and links to `/clients/<key>`; an ungrouped project row links to `/clients/<case_id>` — verify: page shows the rows; read the `href` of the first group and first project link.
3. A project with `billing: "unknown"` reads "Unknown" in the billing cell and state tag, never "Set" or "Missing"; `recorded` reads "Set"; `needed` reads "Billing contact missing" — verify: mock fixtures and `tests/clients.test.tsx` cases for the three values.
4. A group with `contacts_needed` of 2 reads "2 billing contacts needed" with the missing tag; `0` reads "None needed" — verify: component test.
5. No OWED column, no owed text on phone cards, no money panel and no "blocked" callout appears on `/clients` or `/clients/<id>`; no "0" or "₦0" appears as an amount — verify: component tests assert absence, and open both pages at 1440 and 390.
6. "Show more" fetches the next group page, then the next project page, and never repeats a row — verify: mock `many` state test with two group pages and two project pages; request log shows the `clients_page` and `page` values used.
7. `/clients?billing=needed` and `?q=<text>` send those query values on the request — verify: unit test of the request URL in `api.ts` tests.
8. `/clients/<group key>` shows the label, its projects with billing tags and links to `/projects/<case_id>`, and "Show more" while `next_page` is set — verify: mock group fixture with two pages.
9. `/clients/<case_id>` shows billing contacts (customer, name, email, role) read only, a separate "Project contacts" block, and the sample label when `sample` is true — verify: mock workspace fixture.
10. "Show history" lists versions newest first from `contacts/history?purpose=billing`, pages with "Show more", and a failed history call shows a retry without clearing the page — verify: test with a 503 on history.
11. The billing contact form is visible and disabled with the reason "Waiting for the evidence picker and the backend answer."; clicking Save and pressing Enter send no request — verify: test asserts `fetch` calls contain no `PUT /billing-contact` and no `POST /clients/*/contacts`; `grep -rn "billing-contact" frontend/src` finds no live call.
12. Wrong user: a 404 or 403 on a group key or a case id shows `ClientNoAccess` with no name, title or contact in the page or the tab title — verify: mock 404 and 403 tests. Wrong tenant: a case id from another tenant returns 404 from Django 8010 and shows the same state — verify: open it as live-none.
13. A 401 on either page shows the signed-out state with a return path to the same URL; a 503 or network failure shows "We couldn't load the clients/this client. Your work is safe; nothing was changed." with a working Retry — verify: tests with injected failures.
14. Invalid input: `/clients?billing=bogus` is not sent on the request (the filter is ignored) and the list loads; a 400 or 422 reply shows the error card — verify: unit test.
15. A group key with special characters (`/`, `%`) is sent URL-encoded once, not twice — verify: test on the request path.
16. The mock's four clients operations validate against the live contract schemas, and a deliberately wrong shape fails the validator — verify: `tests/clients-mock.test.ts` updated, in the style of `tests/mock-live-me.test.ts`.
17. The v7 mock still serves the other screens; design review of `/clients` and `/clients/<id>` works with `npm run mock` on 4971 — verify: open both pages on 4970 against the mock.
18. Layout stays on the approved boards at 1440 and 390 apart from the listed conflicts — verify: `design.py check` passes and the fidelity run (one run, layout changed) shows only the listed exceptions.
19. `src/api/client.ts` and `src/api/schema.d.ts` are unchanged unless named in `build.md` as a separate commit; `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` are unchanged — verify: `git diff --stat origin/main`.

## Out of scope
- Adding a billing contact: no `POST /clients/{case_id}/contacts`, no evidence picker, no `contacts/options` read. Held (F-73b, no id yet) until backend question B-45 and the shared evidence picker.
- Billing identities, project people, workspace-link reads and writes (live-only, undrawn).
- Any backend change, amount-owed per group (B-43), and which workspace's contact is "the client's" for a multi-project group (B-44).
- Search box, filter control, history control as new designed UI beyond the minimal "Show history" link (see Conflicts); a stable client id; client-side grouping or name lookup.
- Showing money for a client or group: stays at `/projects/{case_id}/money`.

## Assumptions
- B4 default: owed column, money panel and blocked lines are hidden (batched, recommended option 1).
- B5 default: the group key (or case id) is the route id (recommended option 1); a key can change if grouping changes.
- B6 default: reads now, contact form disabled with its reason (recommended option 1).
- B-46 best reading: `contacts_needed` is a count of billing contacts still needed, so 0 reads "None needed"; project `billing` recorded = set, needed = missing, unknown = unknown. Flag in the PR.
- A UUID-shaped segment is a case id and anything else a group key, because the live contract gives no other discriminator.
- The "N missing billing contact" suffix in the count line counts loaded rows only and appears when no more pages remain, as the board's count line does today.
- Mock moves to the live shape because the same `/api/v1/clients` URL cannot serve both shapes; v7 `E-CLIENT-CONTACT` is no longer served.
- Live has no `as_of`; the count line uses the time the page was read.
- A project's detail view (workspace contacts) is reached from group rows through a "Billing contacts" link, since B-44 is unanswered and no single group contact is chosen.

## Conflicts with the boards
1. OWED column (desktop) and "Owed:" card line (mobile) removed. Recommendation: accept (B4); live has no source. Alternative: show "Not available in the live data yet".
2. Money panel and "blocked" lines on the detail boards removed. Recommendation: accept (B4).
3. List mixes group rows and ungrouped project rows; the board draws only client rows. Recommendation: accept, same row design; the project row shows the project title as a second line.
4. Detail board draws one billing contact (name, email) for a client; live gives contacts per workspace with customer, role and version, so the group page has no single contact and shows a pointer instead. Recommendation: accept until B-44 is answered; design engineer to draw the group contact view later.
5. Added read-only blocks not on the boards: "Project contacts", "Show history" and version lines. Recommendation: keep them minimal as plain list text in the existing panel style; design engineer may rule them out, in which case remove them (nothing else depends on them).
6. Billing contact form is disabled with a reason line; the board draws it active. Recommendation: accept (B6).
7. The STATE column/tag gains an "Unknown" state the board does not draw. Recommendation: reuse the neutral tag style with the word "Unknown".
