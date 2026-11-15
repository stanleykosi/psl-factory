STATUS: READY
COMMIT: effdc3f55c827a61a258ee44f6904654cbd6eaee
BUILDER: builder
LANE: full

## Summary
- New `/clients` list and `/clients/[clientId]` detail on the contract mock only (D-CLIENTS-VIEW still proposed; no real backend is claimed). One commit.
- The list shows name, projects, owed, billing contact set/missing, an "as of" line and Show more by `next_cursor`. The detail shows the `blocked[]` banner, the billing contact (form only when `can_change === true`), projects (linking to `/projects/{case_id}`) and money. Unknown reads "Unknown", absent reads "Not given" or is left out.
- Save sends one `PUT` (CSRF, exactly `{expected_revision, name, email}`), guarded against a double press, never resent. 200, 409, 403 and unclear failures read the client once; 422 puts messages beside inputs and focuses the first invalid one.
- Mock: `mock/clients.mjs` plus fixtures, replies validated against v7; `server.mjs` has the import, three operation IDs, one dispatch line, one `resetClients()` call.
- Fidelity: coverage 100% after approved exceptions on all four boards; visual passes only on SCR-35-mobile (92.5). Three boards are under 90 (see Acceptance 1 and 2).

## Changes
- `frontend/src/features/clients/`: `api.ts` (typed calls; save reads the raw reply for 422 `fields`), `useClients.ts`, `useClient.ts`, `ClientsList.tsx`, `ClientDetail.tsx`, `BillingContactForm.tsx`, `ClientStates.tsx` (no-access page), `labels.ts`, `clients.css` (tokens only), `index.ts`.
- `frontend/src/app/clients/page.tsx`, `frontend/src/app/clients/[clientId]/page.tsx` (titles "Clients · PSL Factory", "Client · PSL Factory").
- `frontend/mock/clients.mjs`, `frontend/mock/fixtures/clients/**` (list, CL-3501/02/03/07/08/08.next/09), `frontend/mock/fixtures/E-CLIENTS.json`, `E-CLIENT.json`, `E-CLIENT-CONTACT.json` (needed because `server.mjs` reads `fixtures/<operationId>.json` for every M1 operation; this avoids editing that line).
- `frontend/mock/server.mjs`: only the import, `...CLIENT_OPERATIONS` in `M1_OPERATIONS`, `resetClients()` in the reset block, one dispatch line.
- `frontend/tests/mock-contract.test.ts`: additive table entries only (see Decisions below).
- Tests: `tests/clients.test.tsx` (31), `tests/clients-mock.test.ts` (14), `e2e/clients.spec.ts` (16 runs, 8 states at 390 and 1440).
- Factory: `fidelity-exceptions.json`, `round-1/fidelity/**`.

## Decisions and deviations to review
- Persona none gets 403 on all three operations, as the spec says. The existing generic `tests/mock-contract.test.ts` called every M1 operation with `X-1` ids, an empty PUT body and expected 200 for every persona. I added only table entries: `client_id: 'CL-3501'` in PATH_VALUES, a valid `E-CLIENT-CONTACT` body, and `{none: 403}` for the three operations in PERSONA_STATUS. No `expect` was removed or loosened. This file is outside the lane list; needed for the gate.
- Saved state and the CL-3508 first-409 are kept per persona and client in the mock (so the generic test's five personas can each PUT once without a 409).
- Tamarind Loans has `billing_contact_set: true` (the spec's row says "false", but acceptance 5 and "2 missing" require only Lagoon Health and Ojo Foods to be missing; I followed the acceptance criteria).
- CL-3507 has sample true and all three amounts unknown; there is no "money absent" variant (CL-3509 covers absent `money`).
- 403 and 404 use a clients-specific `ClientNoAccess` (`ClientStates.tsx`, modelled on F-07's `ProjectNoAccess`) instead of the shared `NoAccessState`, because that one says "work item" and links to "my queue". Same pattern: one h1, nothing about the record, no id or name.
- The list table has a STATE column holding the Set / Billing contact missing tag (the board's 4th column), beside BILLING CONTACT, so "Set" appears twice per set row.
- The count line also shows on phone (the phone board has none); the contract requires `as_of`.
- The board's phone card is not a link; ours has the name as the link with a card-wide hit area.
- Acceptance 18 grep: other features' `src` already contain these sample names (`projects/model.ts`, `response/`, etc.). The new test checks only `features/clients` and `app/clients`; both are clean.

## Fixes
None (round 1).

## Acceptance criteria
1. [ ] Desktop fidelity: coverage 100% after exceptions on both boards; visual below 90: SCR-35-desktop 85.9 (gap 4.1), SCR-35-desktop-detail 79.3 (gap 10.7). Cause list: the board's Search/Filter row is not built (count line takes its row height to keep the table aligned); the detail board's page is much taller (Legal name, Billing address, Tax ID, Contacts, a blue "Save client details" with explanatory text; Conflicts 8 and 12) while ours ends after the billing contact, the board draws empty fields with orange borders and "Not set" placeholders (not derived by the page), and the Save button is grey until both inputs are filled. Needs a design-engineer decision: accept these scores, or add the missing fields (backend contract proposal below).
2. [ ] Phone fidelity: SCR-35-mobile passes (coverage 100, visual 92.5). SCR-35-mobile-detail visual 76.7 (gap 13.3): the board has a sticky white bottom bar holding the blue Save button, orange-bordered empty inputs, the Billing address field and no Projects or Money panels; ours stacks the Projects and Money panels below the form (Conflicts 4, 8) and the Save button is grey/disabled when empty. Same decision as item 1.
   `round-1/fidelity/scores.txt`:
   ```
   SCR-35-desktop | 1440 | 61.1 | 100 | 85.9 | False
   SCR-35-mobile | 390 | 30.4 | 100 | 92.5 | True
   SCR-35-desktop-detail | 1440 | 52.9 | 100 | 79.3 | False
   SCR-35-mobile-detail | 390 | 25 | 100 | 76.7 | False
   ```
   side-by-side: `/Users/Hunchoo/psl-factory/delivery/features/F-19/round-1/fidelity/<board>-<width>/side-by-side.png` (SCR-35-desktop-1440, SCR-35-mobile-390, SCR-35-desktop-detail-1440, SCR-35-mobile-detail-390). Scored on a production build (`API_ORIGIN` set at build) with FRAME_FIXTURES=1, cookie `psl_mock_persona=pm`.
3. [x] Exceptions limited and explained: 39 entries, each with role, name, category, reason, `approved_by: "design engineer, 15 Nov (D-71)"`. Map: search area, Search, Filter, "6 CLIENTS · 2 MISSING BILLING CONTACT" = Conflicts 5; "1 active", "1 closed", "Prospect · RFP", "Active · PM Tunde Bello · 4 milestones" = 3; four email/dash entries = 2; NEEDS DETAILS, READY, PROSPECT = 1; "← Projects", "← Clients" = 14 (frame bar name); CLIENT DETAILS, Legal name, Lagoon Health Ltd, Billing address, both address texts, Tax ID, Unknown, Save client details, "Changes are recorded…" = 8; "Not set", "Billing email", the phone banner sentence = 7; CONTACTS and its two lines = 12. Conflicts 4, 6, 9, 10, 15 add elements (no exception needed); 11 needs none (the 40/26px frame sizes are kept); 13 (D-70): no Clients link was added and no `features/projects/**` change, so no exception.
4. [x] Titles and phone bar: e2e reads h1 computed size (40px at 1440, 26px at 390), one h1 on list, detail and not-open; phone bar link "Back to Projects" (list) and "Back to Clients" (detail, not-open); no back link in `main`.
5. [x] List from data only: `tests/clients.test.tsx` "shows the six clients…" asserts order, tags, Tamarind 0, links, and absence of "@", active, closed, Prospect, READY, NEEDS DETAILS, PROSPECT.
6. [x] Owed and unknown: tests on list, CL-3501, CL-3507, CL-3509 (Unknown / Not given / formatted amount); a known "0.00" shows as ₦0.00. `grep 0\.00 src/features/clients` empty (asserted in a test).
7. [x] Count line and paging: component test with a recording fetch (one request per press under a double click, `cursor=o10`, then `o20`, "10 clients loaded as of…", "25 clients as of …", missing figure only on the complete list, failed second page keeps rows with Try again); mock test for cursor paging and limit.
8. [x] List states: empty, 5xx (Try again only reads), 401 (`next=%2Fclients`), 403 (persona none) tested.
9. [x] Detail from data only: tests on CL-3501, CL-3509, CL-3503, CL-3507; board-only text (Tax ID, address, Legal name, Contacts, PM, milestones) absent.
10. [x] Save request: Save off until both non-blank; double press makes one PUT with CSRF header and body exactly `{expected_revision:3,name,email}`; one reload; "Billing contact saved." status; banner gone.
11. [x] Save errors: 409 (CL-3508) reload once, typed text kept, "Current: …", notice, next press carries revision 3; 422 per-field messages with `aria-invalid`/`aria-describedby`, entries kept, no reload, focus on first invalid; 403 reload decides; 401 callout; network error and 502 one reload, no second PUT; failed reload turns the form off with a reading-only Try again.
12. [x] Tenant and permission: CL-3599 (404) and persona none (403) show the no-access page without id, name or title; the mock gives persona none 403 on all three operations and a PUT without CSRF gets 403 (mock test). `grep "useMe|roles|destinations"` in `features/clients` is empty (asserted).
13. [x] Nothing derived: invoice appears only in the two static copy lines, returned `blocked[]` and the Invoiced label; only the three `api.*` calls exist (asserted by a source test).
14. [x] Mock matches v7: `clients-mock.test.ts` checks 200/403/404/409/422 shapes against the v7 schemas, order, paging, limit, the 409-then-newer flow, stored contact, all fixtures against the schema, CL-3509 bare. `npx vitest run tests/clients-mock.test.ts tests/clients.test.tsx` passes (45 tests).
15. [x] Accessibility: `E2E_PORT=4631 MOCK_PORT=4632 npx playwright test e2e/clients.spec.ts` gives 16 passed at 390 and 1440, with axe (wcag2a, 2aa, 21a, 21aa, 22aa) on list, empty list, Show more, error, detail, detail with 422, read-only detail, not-open; no sideways scroll; focus rings; Tab order name, email, Save; 44px targets (phone cards, inputs, Save, Show more); reduced motion shows no transitions or running animations. An existing crumb link-in-text-block axe issue was fixed with an underline, as F-07 does.
16. [x] Tokens only: the grep returns nothing (also asserted in a test).
17. [x] Existing behaviour: `checks.sh` 51 test files, 1442 tests pass; diff shows no edit to `src/shell`, `src/api`, `features/projects`, architecture, package files or protected files; `server.mjs` has 4 added lines and one line extended (M1_OPERATIONS) only.
18. [x] No new dependency; no hard-coded sample names in the clients code (see deviations).
19. [x] This file.

## Contract proposals for the backend developer (not built; D-CLIENTS-VIEW proposed)
- `readiness` enum on list items if the three board states (READY / NEEDS DETAILS / PROSPECT) are wanted (Conflicts 1).
- `billing_contact_email?` on list items (2).
- `projects_active`, `prospect`, per-project `pm` and `milestones` (3).
- `legal_name`, `address`, `tax_id` and a client-details write (8); `contacts[]` (12).
- One `name`: the board uses "Lagoon Health" in the list and "Lagoon Health Ltd" on the detail; the mock fixtures use each (15), a real backend returns one.
- A `total` on the list if an exact "n clients" count is wanted while more pages exist (5).
- 422 `fields[].name` values `name` and `email`; the mock refuses an email without "@" only.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-19 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 (Django check, lint, typecheck, 51 files / 1442 tests, production build). A first run under load showed two timeouts in other files (`setup-rules`, `work-item-board`) that passed alone and in the final run.
- `npx vitest run tests/mock-contract.test.ts tests/clients-mock.test.ts tests/clients.test.tsx tests/setup-rules.test.tsx tests/work-item-board.test.tsx`: 386 passed.
- Playwright `e2e/clients.spec.ts` on 4631/4632: 16 passed.
- Fidelity run once per board at the end after one earlier pass to list the missing items (an earlier pass ran against a build without `API_ORIGIN` and was discarded). Servers on 4631 and 4632 stopped; `frontend/test-results` removed; `git status` clean after the push.

## Blocked
Not blocked. Open design-engineer decision: three boards are under visual 90 (items 1 and 2) for causes that are approved exceptions or out of the spec's scope.
