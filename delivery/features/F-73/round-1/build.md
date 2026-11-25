STATUS: READY
COMMIT: 34c24d0035b0ddab4fb1b28c424dda0e8138c10d
BUILDER: builder
LANE: full

## Summary
- `/clients` now lists live client groups and ungrouped projects from `GET /clients` (groups first, as returned), with `q` and `billing` read from the address, and one "Show more" that asks for the next group page, then the next project page, without repeating a row.
- `/clients/[clientId]` opens a group (`GET /clients/groups/{group}`) when the id is not a UUID, or one project's contacts (`GET /clients/{case_id}`) when it is. Group page shows projects with billing tags, and the owed panel from `debt`.
- Billing words: recorded = "Set", needed = "Missing · invoices can't start" / "Billing contact missing", unknown = "Unknown" (never Set, zero or missing). Group `contacts_needed` reads "N projects need a billing contact" or "None needed".
- Owed panel: per currency, a known amount or "Not known", "N projects with an amount not known", as-of date and project count, the "May be incomplete" line, and the empty and null cases. Never summed across currencies.
- The add-billing-contact write is held: a disabled "Add billing contact" with its reason. No POST or retired PUT exists in `src`. The clients mock now serves the live shape, validated against the live contract.

## Changes
- `src/features/clients/api.ts`: four live GETs through `liveApi`/`call`, typed from `live-schema.d.ts` (the v7 client and the PUT are gone).
- `labels.ts`: billing words, count line, `billing`/`q` rules, UUID-or-key rule, route path encoding.
- `useClients.ts`, `useClient.ts`: list paging with de-duplication; group, workspace and history hooks (200s missing required fields become `unexpected_response`).
- `ClientsList.tsx`: one table (CLIENT, PROJECTS, BILLING CONTACT, STATE; the OWED column and card line removed), phone cards, states. `src/app/clients/page.tsx` wraps it in Suspense for `useSearchParams`.
- `ClientDetail.tsx` (group view, workspace view, owed panel, history), `clients.css`. `BillingContactForm.tsx` deleted.
- Money amounts reuse the `Money` component from `@/components` for naira and `CODE amount` with `groupDigits` otherwise (same pattern the old list used).
- `mock/clients.mjs` rewritten to the live shape; `mock/fixtures/clients/live.json` replaces the v7 fixtures; `mock/server.mjs` gets a small hook for the two paths the v7 route table lacks (group page, history). `node --check` passes on both.
- Tests: `tests/clients.test.tsx` (35), `tests/clients-model.test.ts` (9), `tests/clients-mock.test.ts` (9), `tests/mock-contract.test.ts` and `tests/next-config.test.ts` (allow-list: `clients.mjs`, `clients-mock.test.ts`, one per line), `e2e/clients.spec.ts` rewritten, `e2e/text-focus.spec.ts` loses the clients field step (that field no longer exists).
- `src/api/**`, `delivery/**` unchanged. Shared code changed: only `mock/server.mjs` (the hook plus dropping the PUT operation from the client wiring).

## Fixes
None (round 1).

## Acceptance criteria
Scope per the coordinator: reads only; the write stays held (criteria 11 to 11f are not built; 11f is true: no write call in `src`).
1. [x] List rows, groups first, in order: mock list test; not checked against Django 8010 (no live server in this lane).
2. [x] Group row links `/clients/<key>`, project row `/clients/<case_id>`: list test reads the hrefs.
3. [x] unknown/recorded/needed words: model and list tests.
4. [x] `contacts_needed` 2 reads "2 projects need a billing contact", 0 "None needed": model test.
5. [x] No OWED column or owed text on the list (desktop and phone), no invoiced/received panel, no blocked line: component tests and Playwright at 1440 and 390.
5a. [x] Five debt fixtures (known, null amount, limited, empty totals, null debt): group tests.
5b. [x] Two currencies as two lines: Acme group test.
6. [x] Paging: group page 2 then project page 2, no duplicates; request log `['', '?clients_page=2', '?page=2']`.
7. [x] `q` and `billing` sent from the address: list test. 14: `billing=bogus` not sent: list and model tests; 400 shows the error card.
8. [x] Group page with two pages (27 projects).
9. [x] Workspace contacts read only, "Project contacts" block, sample label (with the build flag).
10. [x] History newest first, Show more, failed history shows retry and keeps the page.
12. [x] 403 and 404 show no access with no name; tab title stays "Client · PSL Factory" (Playwright).
13. [x] 401 signed-out with return path; 503 error card and Retry.
15. [x] Key `a/b%c` sent as `a%2Fb%25c`.
16. [x] Mock validates against the live contract; wrong shapes fail the validators.
17. [x] Both pages run on the mock (ports 4970/4971).
19. [x] `src/api/**` and `delivery/**` untouched.
18. Not run: the design-fidelity tool (lean mode; layout is the existing one minus the OWED column). Open question for the design engineer: the owed panel, the held-add control and the history block are not on the boards.

## Validation
- `npx tsc --noEmit`: clean. `npx eslint . --max-warnings 0`: clean. `node --check` on `mock/clients.mjs` and `mock/server.mjs`: clean.
- Full `npx vitest run`: 186 files, 4302 tests; first run had one failure (`next-config` allow-list), fixed. Re-run of `next-config`, `demo-mock`, `mock-contract`, `clients`, `clients-mock`, `clients-model`: 6 files, 410 tests, all pass.
- Playwright (`E2E_PORT=4970 MOCK_PORT=4971`, production build): `e2e/clients.spec.ts` 8 passed (list, group page, contacts and a no-access key, at 1440 and 390, axe WCAG 2.2 AA, no horizontal scroll). `e2e/text-focus.spec.ts` ran in the first pass and passed. Playwright started and stopped its own servers; nothing is left on 4970 or 4971.
- Not verified against Django 8010: whether a `page=2` call also returns groups (the code de-duplicates either way), and the real `debt` values.

## Notes for the coordinator
- Spec says group rows carry no `api_url`; the live contract requires it. The mock and types follow the contract; the page ignores it.
- Workspace page: the `GET /clients/{case_id}` response has no billing state, so a workspace with no billing contact says "Not set" (not "No billing contact recorded").
- Mock hook for two live-only paths is in shared `mock/server.mjs`.
