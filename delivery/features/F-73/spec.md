# Clients and client details read live client groups, owed amounts and workspace contacts, and record a billing contact

> Re-specified against 1.24.0 (D-185). Replaces the 1.22.0 spec; the reads are unchanged except where marked.

> Tasks: FE-CONNECT-1 (reads, owed on the group page, billing contact write per new product question 1). Architecture: v9 package; live contract `contracts/psl-factory.openapi.json` 1.24.0 (operations `clients_directory`, `clients_group`, `workspaces_client`, `clients_contact_history`, `clients_contact_options`, `workspaces_save_contact`). Design: approved SCR-35 boards (F-19, DONE); screens: SCR-35 (artboards SCR-35-desktop, SCR-35-mobile, SCR-35-desktop-detail, SCR-35-mobile-detail).

## Summary
- `/clients` lists live client groups and ungrouped projects from `GET /clients`, with search, a billing filter and paging.
- `/clients/[clientId]` opens a group (`GET /clients/groups/{group}`) when the id is a group key, or one workspace's contacts (`GET /clients/{case_id}`) when the id is a case id.
- The billing tag comes from live `billing` (recorded / needed / unknown) and `contacts_needed`. Unknown is shown as unknown, never as "Set", zero or "missing".
- New in 1.24.0: the group page shows what the group owes from `debt` (B-43): per currency, a known amount or "not known", the count of projects with an unknown amount, the date and a coverage note. The list still has no owed column (no list-level source). The invoiced/received money panel and the "blocked" lines stay hidden (no source). Money stays at `/projects/{case_id}/money`.
- New in 1.24.0: the billing contact can be recorded from a project's page with `POST /clients/{case_id}/contacts`, using a proof chosen from `GET .../contacts/options` (B-45). There is no upload route for this proof, so the form offers only proofs already recorded on the project; with none, it stays disabled with its reason. This is new product behaviour (New product questions, 1).
- B-46 is answered: `contacts_needed` counts the group's projects whose billing is "needed".
- The v7 mock serves the clients operations in the live shape so design review keeps working.

## Context
- Routes: `src/app/clients/page.tsx`, `src/app/clients/[clientId]/page.tsx` (uses `routeCaseId` from `src/features/projects/model.ts`, which only URL-decodes the segment).
- Feature: `src/features/clients/` (`ClientsList.tsx`, `ClientDetail.tsx`, `BillingContactForm.tsx`, `ClientStates.tsx`, `labels.ts`, `api.ts`, `useClients.ts`, `useClient.ts`, `clients.css`). Today these call the v7 client `api` (`GET /clients` with `limit/cursor`, `GET /clients/{client_id}`, `PUT /clients/{client_id}/billing-contact`; the retired `PUT` is removed) and the v7 types from `src/api/schema.d.ts`.
- Live client: `liveApi` and live types `src/api/live-schema.d.ts` in `src/api/client.ts` (used already by `src/shell/AppShell.tsx`); `liveApi` adds `X-CSRFToken` on writes through its middleware. Money amounts: reuse `Money`/`formatAmount` patterns in `src/features/clients/ClientsList.tsx` and `src/features/decide/format.ts`; state the one reused in `build.md`. `next.config.ts` proxies `/api/v1` to `API_ORIGIN` (mock on 4971 by default, Django 8010 for live checks).
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
  - Group row: name `label`, link to `/clients/{key}`, PROJECTS `project_count`. Billing cell: `contacts_needed > 0` reads "N projects need a billing contact" (1: "1 project needs a billing contact") with the "Billing contact missing" tag; `contacts_needed == 0` reads "None needed" with the neutral tag. (B-46 answered: `contacts_needed` counts the group's projects in the "needed" state; it does not count unknown ones, so the group page tags each project.)
  - Ungrouped project row: name `client` if present, else `title`, with the project title as the second line when `client` is present; link to `/clients/{case_id}`; PROJECTS "1". Billing: `recorded` is "Set" (neutral tag), `needed` is "Missing · invoices can't start" (the "Billing contact missing" tag), `unknown` is "Unknown" (an unknown tag, never "Set"; B-46: the billing scope could not be established).
- Count line: "N clients loaded as of <time>" using the response time the page was read (no `as_of` in live; use the client clock at read, WAT, and say "loaded", never a total). The "N missing billing contact" suffix counts the loaded group rows by `contacts_needed` (summed) plus loaded project rows with `needed`, and is shown only when no further page exists.
- Paging: one "Show more" footer. It first requests the next `clients_page` while `next_group_page` is non-null, then the next `page` while `next_page` is non-null. Rows already shown are never replaced and never duplicated (de-duplicate by `key` / `case_id`, because the live response returns both lists on every call). The builder confirms against Django 8010 whether a call with `page=2` also returns groups, and keeps whichever lists it needs.
- Search and filter: the existing board has no search box. Do not add one (see Conflicts). `q` and `billing` are supported by `api.ts` and read from the URL query (`/clients?q=…&billing=needed`) only, so they are testable and deep-linkable.
- States: loading (`LoadingState`), empty (`EmptyState` "No clients"), error, success.

### `GET /api/v1/clients/groups/{group}` (clients_group)
Path `group` is the opaque key, sent URL-encoded. Query `page`.
Response 200: `{"key", "label", "projects": [{"case_id","title","client","billing"}], "next_page": int|null, "debt": null | {"as_of": "2026-11-23", "workspace_count": 3, "limited": false, "totals": [{"currency": "NGN", "basis": "...", "known_owed": "1250000.00" | null, "unknown_owed_count": 1}]}}`. `debt` is required in the response and may be null.
- Owed panel (new in 1.24.0, B-43): shown in the money panel's place on the board. For each `totals` entry: "Owed" with the currency and `known_owed` formatted as money; when `known_owed` is null, "Not known" (never 0 or an empty amount); when `unknown_owed_count > 0`, the line "N projects with an amount not known". Under the entries: "As of <as_of> · <workspace_count> projects you can see" and, when `limited` is true, "May be incomplete: only part of this group is in your view or could be read." `basis` is shown as a quiet caption beside each amount, unchanged text. When `totals` is empty, "Nothing owed is recorded for the projects you can see." (This does not claim zero.) When `debt` is null: "Owed amount is not available for this group." Amounts of different currencies are never added together. The panel does not show invoiced or received (no source).
- Page: breadcrumb "Clients / <label>", title `label`. Projects panel lists each project (title links to `/projects/{case_id}`; a second link "Billing contacts" goes to `/clients/{case_id}`), each with its billing tag (same mapping as above). "Show more" while `next_page` is non-null.
- Billing contact panel: no form on the group page, only the line "Billing contacts are recorded for each project. Open a project's billing contacts from the list."
- Unknown group: 404, `ClientNoAccess`.

### `GET /api/v1/clients/{case_id}` (workspaces_client)
Response 200: `{case_id, title, revision, sample, contacts: [{contact_id, version, purpose: "project"|"billing", customer, client_name, name, email, role}], django_url}`.
- Page: breadcrumb "Clients / <title>", title `title`, `SampleLabel` when `sample` is true. "Billing contact" panel: each `purpose == "billing"` contact as a read-only block (customer, name, email, role, "version N"). When there is none, the read-only block says "No billing contact recorded" only when the project's billing is known to be needed; otherwise "Not set". Contacts with `purpose == "project"` are listed in a second read-only block, "Project contacts". Projects panel: this workspace, linking to `/projects/{case_id}`.
- History: a "Show history" control calls `GET /clients/{case_id}/contacts/history?purpose=billing` (and `customer` when the contact has one) and lists versions newest first with "Show more" on `next_page`. Read only. Failure shows an inline retry; it does not clear the page.
- `revision` is kept in memory for the write form; it is not shown. The form below the read-only block is described under "Billing contact form".

### Billing contact form (new in 1.24.0; see New product questions, 1)
Lives on the workspace page (`/clients/{case_id}`) only. The group page keeps the pointer line and no form.
- On opening the workspace page the page reads `GET /clients/{case_id}/contacts/options?purpose=billing` → `{revision, customers: string[], proofs: [{id, kind, version}]}`. A 403 or 404 on options disables the form with "You can't change billing contacts on this project." (the server decides; there is no `can_change`). A 503 or network failure shows an inline retry for options and leaves the form disabled; the page is not cleared.
- Fields: Customer (choose from `customers`), Client name, Name, Email, Role (text), and Proof of the contact instruction (choose from `proofs`, each shown as "<kind> · version <version>"; the integer id is the value and is never shown as the label). Prefill from the current billing contact when one exists (its `customer`, `client_name`, `role`, `name`, `email`).
- When `proofs` is empty the form is disabled with "No proof of this contact instruction is recorded on this project yet. Record it first, then come back." When `customers` is empty it is disabled with "No billing customer is available for this project yet."
- Save sends one `POST /api/v1/clients/{case_id}/contacts` with `{purpose: "billing", customer, client_name, name, email, role, evidence_id, expected_revision}`, where `expected_revision` is the `revision` of the options read (the same workspace revision as `GET /clients/{case_id}`). The Save control is busy after press and a ref blocks a second press; it is never resent automatically (no idempotency key exists; a conflict is read back).
- Response 200 `{contact_id, version, purpose, customer, client_name, name, email, role}`: toast "Billing contact saved", then re-read `GET /clients/{case_id}` and options so the new version and revision show. If the re-read fails: "Saved. We couldn't refresh the page; reload to see it." and Save stays disabled until options are read again.
- 409: "This project changed while you were editing. The latest values are loaded; check them and save again." Re-read the page and options; keep what the person typed in place where the field still exists. 422/400: show each `fields[]` message on its field (name, email, role, customer, client_name, evidence_id mapped to the proof field), the rest as a summary line, and focus the first invalid field. 401: signed-out state. 403: "You can't change billing contacts on this project." 404: `ClientNoAccess`. 413, 415, 5xx, 503 or network failure: "We couldn't confirm this was saved. Check the billing contact below before trying again." with the page re-read once; no automatic retry.
- Client-side checks before sending: all fields non-empty, email shaped like an address, proof chosen. These are conveniences; the server decides.
- Nothing calls `PUT /clients/{id}/billing-contact` (retired v7). `purpose: "project"` contacts are not written from this page.

### Money, owed, blocked (B4, partly switched on by 1.24.0)
Not rendered: the OWED column and card line on the list (no list-level owed), the invoiced/received money panel, the "blocked" `Callout`s. The group page's owed panel (above) is rendered from `debt`. The detail page shows a link "Money for this project" to `/projects/{case_id}/money` on the workspace view only (no link on the group view, where the owed panel and the project links take its place).

### Route id (default B5)
`/clients/[clientId]`: after `routeCaseId` decoding, a segment matching a UUID is a workspace `case_id`; anything else is a group key. A key can change if grouping changes (B-42); a stale key shows `ClientNoAccess`, and the list is the way back. Fixture examples: group key `a1b2…` (64 hex) → group page; `0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b10` → workspace page.

### Mock
`mock/clients.mjs` serves `GET /clients`, `/clients/groups/{group}`, `/clients/{case_id}`, `/clients/{case_id}/contacts/history`, `GET /clients/{case_id}/contacts/options` and `POST /clients/{case_id}/contacts` in the live shape, validated against the live contract's response schemas (replace the v7 `E-CLIENTS`/`E-CLIENT` validators; drop `E-CLIENT-CONTACT`). The POST checks `expected_revision` (409 when stale), returns 422 with `fields[]` for a bad email, and a new version with a bumped revision on success. Fixtures cover: group `debt` as known amount, as `known_owed: null` with `unknown_owed_count`, `limited: true`, empty `totals`, and `debt: null`; options with proofs, with none, and with no customers; groups plus ungrouped projects; a group needing contacts; a group with all recorded; a project with `billing: "unknown"`; `client: null`; a workspace with project and billing contacts and history over two pages; the empty cookie state and the 25-row `many` state keep working (`psl_mock_clients`). The mock returns 404 for an unknown key or case id. Other mock operations stay as they are.

## Lanes
- Frontend lane (builder): `frontend/src/features/clients/**`, `frontend/src/app/clients/**`, `frontend/mock/clients.mjs`, `frontend/mock/fixtures/clients/**`, `frontend/tests/clients*.test.*`, `frontend/e2e/clients.spec.ts`.
- Backend lane: none. No backend change. B-42 to B-46 are answered (`delivery/connect/backend-answers.md`).
- Integration owner: the lane B coordinator. Checks the pages against Django 8010 (accounts live-none, live-lead, live-multi, live-admin).
- Shared files: `src/api/**` and `src/shell/**` are lane A's, `src/features/workspace/**` is lane C's. This feature should not need any change there (`liveApi` already exists). If one is needed (for example a type export), it is a separate small commit named in `build.md`. `mock/server.mjs` is shared: change only the `CLIENT_OPERATIONS` wiring there, as its own small commit if needed. `src/shell/SampleLabel` is reused unchanged.

## Acceptance criteria
1. `/clients` against live shows one row per group and one per ungrouped project, groups first, in the order returned — verify: open `/clients` as live-lead on port 4970 (API_ORIGIN Django 8010) and compare the rows with `curl` of `GET /api/v1/clients` with the same session.
2. A group row shows `project_count` as PROJECTS and links to `/clients/<key>`; an ungrouped project row links to `/clients/<case_id>` — verify: page shows the rows; read the `href` of the first group and first project link.
3. A project with `billing: "unknown"` reads "Unknown" in the billing cell and state tag, never "Set" or "Missing"; `recorded` reads "Set"; `needed` reads "Billing contact missing" — verify: mock fixtures and `tests/clients.test.tsx` cases for the three values.
4. A group with `contacts_needed` of 2 reads "2 projects need a billing contact" with the missing tag; `0` reads "None needed" — verify: component test.
5. No OWED column or owed text on `/clients` (list, desktop or phone cards), no invoiced/received money panel and no "blocked" callout on any client page — verify: component tests assert absence; open both pages at 1440 and 390.
5a. The group page shows the owed panel from `debt`: a known amount formatted with its currency; `known_owed: null` reads "Not known" and never 0; `unknown_owed_count` of 2 reads "2 projects with an amount not known"; the as-of date and project count show; `limited: true` shows the "May be incomplete" line; empty `totals` reads "Nothing owed is recorded for the projects you can see."; `debt: null` reads "Owed amount is not available for this group." — verify: component tests for each of the five fixtures, then compare the page with `curl` of `GET /api/v1/clients/groups/<key>` as live-lead on 8010.
5b. Two currencies in `totals` show as two separate lines and are never summed — verify: component test.
6. "Show more" fetches the next group page, then the next project page, and never repeats a row — verify: mock `many` state test with two group pages and two project pages; request log shows the `clients_page` and `page` values used.
7. `/clients?billing=needed` and `?q=<text>` send those query values on the request — verify: unit test of the request URL in `api.ts` tests.
8. `/clients/<group key>` shows the label, its projects with billing tags and links to `/projects/<case_id>`, and "Show more" while `next_page` is set — verify: mock group fixture with two pages.
9. `/clients/<case_id>` shows billing contacts (customer, name, email, role) read only, a separate "Project contacts" block, and the sample label when `sample` is true — verify: mock workspace fixture.
10. "Show history" lists versions newest first from `contacts/history?purpose=billing`, pages with "Show more", and a failed history call shows a retry without clearing the page — verify: test with a 503 on history.
11. On a workspace page the options read is made with `purpose=billing`; with proofs and customers present the form is enabled, and the proof control labels each proof "<kind> · version N" without showing the integer id — verify: component test and the request log.
11a. Saving sends exactly one `POST /clients/{case_id}/contacts` with `purpose: "billing"`, the form values, the chosen proof's integer id as `evidence_id` and the options `revision` as `expected_revision`; a double click or Enter-then-click sends one request — verify: test counts `fetch` calls.
11b. After a 200 the page and options are re-read and the new version shows; if the re-read fails the "Saved. We couldn't refresh the page" line shows and Save stays disabled — verify: tests for both.
11c. A 409 shows the changed-while-editing message, reloads the latest values and sends nothing further; a 422 with `fields` marks each field and focuses the first; a 503 shows "We couldn't confirm this was saved" and never auto-resends — verify: three tests with injected replies and a request count.
11d. With empty `proofs` the form is disabled with "No proof of this contact instruction is recorded on this project yet…"; with empty `customers`, disabled with its reason; a 403 on options disables it with "You can't change billing contacts on this project." — verify: three tests, and no `POST` is possible (Save disabled, Enter sends nothing).
11e. Wrong user and wrong tenant for the write: a 403 on POST shows the no-permission message; a 404 shows `ClientNoAccess`; as live-none a case id from another tenant gives 404 on both reads — verify: tests, then open it as live-none on 8010.
11f. Nothing in `frontend/src` calls `PUT .../billing-contact`, and the group page has no form and sends no `POST` — verify: `grep -rn "billing-contact" frontend/src` finds nothing; test on the group page asserts no write.
12. Wrong user: a 404 or 403 on a read of a group key or a case id shows `ClientNoAccess` with no name, title or contact in the page or the tab title — verify: mock 404 and 403 tests. Wrong tenant: a case id from another tenant returns 404 from Django 8010 and shows the same state — verify: open it as live-none.
13. A 401 on either page shows the signed-out state with a return path to the same URL; a 503 or network failure shows "We couldn't load the clients/this client. Your work is safe; nothing was changed." with a working Retry — verify: tests with injected failures.
14. Invalid input: `/clients?billing=bogus` is not sent on the request (the filter is ignored) and the list loads; a 400 or 422 reply shows the error card — verify: unit test.
15. A group key with special characters (`/`, `%`) is sent URL-encoded once, not twice — verify: test on the request path.
16. The mock's six clients operations validate against the live contract schemas, and a deliberately wrong shape fails the validator — verify: `tests/clients-mock.test.ts` updated, in the style of `tests/mock-live-me.test.ts`.
17. The v7 mock still serves the other screens; design review of `/clients` and `/clients/<id>` works with `npm run mock` on 4971 — verify: open both pages on 4970 against the mock.
18. Layout stays on the approved boards at 1440 and 390 apart from the listed conflicts — verify: `design.py check` passes and the fidelity run (one run, layout changed) shows only the listed exceptions.
19. `src/api/client.ts` and `src/api/schema.d.ts` are unchanged unless named in `build.md` as a separate commit; `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` are unchanged — verify: `git diff --stat origin/main`.

## Out of scope
- Uploading or creating the proof of a contact instruction: 1.24.0 has no client-contact proof upload route, and a generic file upload id does not become that proof (B-45). The form only chooses among proofs already recorded. A shared evidence picker or upload is not built here.
- Writing `purpose: "project"` contacts.
- Billing identities, project people, workspace-link reads and writes (live-only, undrawn).
- Any backend change. A "master" billing contact for a group: B-44 is answered, contacts are per project and purpose, and a group never selects or creates one.
- An owed column on the list (no list-level source) and invoiced/received figures.
- Search box, filter control, history control as new designed UI beyond the minimal "Show history" link (see Conflicts); a stable client id; client-side grouping or name lookup.
- Showing money for a client or group: stays at `/projects/{case_id}/money`.

## New product questions (1.24.0)
1. Build the billing contact write now? Option 1 (recommended, built here): a form on each project's contact page that records a billing contact with `POST /clients/{case_id}/contacts`, choosing the proof from those already recorded on the project and showing a clear disabled reason when there is none. The design engineer accepted this as held in B6; the backend now answers B-45 with a route and a proof list, but no way to upload that proof, so the form is useful only where a proof already exists. Option 2: keep the form disabled as in B6 until a proof can be recorded from the client page. Option 3: build the write and a proof upload, which needs a new backend route. Not money-moving; the form adds fields the board does not draw (customer, client name, role, proof).

## Assumptions
- B4 (split by 1.24.0): the owed panel on the group page is built from `debt`; list OWED column, invoiced/received panel and blocked lines stay hidden because no field supplies them.
- B5 default holds: the group key (or case id) is the route id; B-42 confirms the key is an opaque grouping key that can change with the reviewed links.
- B6: replaced by New product question 1.
- B11: the "Unknown" tag, project rows in the list, the "Project contacts" and "Show history" blocks stay as accepted.
- B-44 answered: no group contact; the group page keeps the pointer to each project's contacts.
- B-46 answered: `unknown` means the billing scope could not be established; `contacts_needed` counts projects in the needed state, so 0 is not a claim that all are recorded.
- A UUID-shaped segment is a case id and anything else a group key, because the live contract gives no other discriminator.
- The "N missing billing contact" suffix counts loaded rows only and appears when no more pages remain.
- Mock moves to the live shape because the same `/api/v1/clients` URL cannot serve both shapes.
- Live has no `as_of` on the list; the count line uses the time the page was read. (The group `debt.as_of` is a date and is shown as given.)
- `basis` text in `debt.totals` has no documented vocabulary; it is shown unchanged as a caption.
- `expected_revision` is the options read's `revision`, assumed equal to the workspace `revision`; a mismatch surfaces as 409 and is read back.
- Customer is chosen from `customers`; Client name is free text prefilled from the current contact because the options carry no client name list.

## Conflicts with the boards
Removed since 1.22.0: the hide of the money (owed) amount on the detail board (now built from `debt`) and the disabled billing form (now live). Remaining:
1. OWED column (desktop) and "Owed:" card line (mobile) on the list removed. Recommendation: accept; no list-level owed in 1.24.0.
2. Detail boards: the money panel shows only Owed (from `debt`), without invoiced and received, and the "blocked" lines are removed. Recommendation: accept; the other figures have no source.
3. List mixes group rows and ungrouped project rows; the board draws only client rows. Recommendation: accept, same row design; the project row shows the project title as a second line.
4. Detail board draws one billing contact (name, email) for a client; live gives contacts per project with customer, role and version, and B-44 confirms a group has no single contact, so the group page shows a pointer. Recommendation: accept; design engineer to draw the group view later.
5. Added read-only blocks not on the boards: "Project contacts", "Show history" and version lines. Recommendation: keep them minimal in the existing panel style (B11).
6. Billing contact form gains Customer, Client name, Role and Proof fields the board does not draw (name and email only), plus disabled-reason lines. Recommendation: accept; the server requires them (B-45). Design engineer to draw the extra fields.
7. The STATE column/tag gains an "Unknown" state the board does not draw. Recommendation: reuse the neutral tag style with the word "Unknown".
8. The owed panel adds a coverage line, an as-of line and per-currency lines not on the board. Recommendation: accept, quiet secondary text.
