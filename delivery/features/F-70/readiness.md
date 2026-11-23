DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- One outcome: SCR-22 (Project list) and SCR-07 (Project journey, Journey tab) read from live API 1.22.0 through the live client that F-56/F-57 set up (merged, PR 97). Both screens are already built and approved (F-07 DONE), so this is conformance work on approved boards plus honest handling of parts live cannot fill.
- Dependencies are integrated: live types, drift test, session/CSRF/error layer and the live `/me` frame are on main (F-57 DONE, merge 44878365). No write is involved, so the evidence_id blocker (short list item 1) does not touch this feature.
- Parts the live API cannot fill (next milestone, tab counts, "what is next", Tola's summary, station line, line count, invoices verified / paid) are design questions for the design engineer, not blockers. Each is dropped or shown as not available, never invented and never shown as zero.
- Size: about 8 boards (list: loaded, empty, search and status tabs, error; journey: loaded, empty, more rows, error). One PR is realistic: the work is two models, two hooks and their tests.
- Not run by this check (no shell): `design.py check` and the tests. The builder gate must run both. The backend answers to B-1 to B-6 and B-32 to B-34 are open and are worked around, not waited on.

## Scope
Task FE-CONNECT-1 (screen connection part, SCR-22 and SCR-07). The spec writer follows this as binding. Live operations used, all read-only: `GET /api/v1/projects`, `GET /api/v1/projects/{case_id}`. Work-row links go to `/work/{id}` (integer id from `items[].id` or `api_url`) and the page for that id is not part of this feature.

In, SCR-22 `/projects`:
- Use the live-typed client. Send `status=active|closed|all` and `q` (max 120) explicitly; the frontend default stays "active" (live default is `all`). Page with `cursor` and `next_cursor`.
- Row fields: `case_id`, `title`, `sample`, `manager` (null shows no manager, not a made-up name), `phase`, `lifecycle`, `reviews`, `exceptions`. `reviews` and `exceptions` feed "needs a person" and "stopped" on the best reading of B-32; flag that reading in the spec and the PR. Null counts are unknown, never 0.
- Dropped or not available (design questions, section below): next milestone with due date, reference, Active/Closed/All count badges, "N projects" total, rows-per-page choice (page size is fixed by the backend).

In, SCR-07 `/projects/[caseId]`, Journey tab:
- Title and client crumb from `title`; the split on " · " is the best reading of B-1. If the string has no separator, show the whole title and no client crumb.
- `revision`, `sample`, project manager and route from `facts.engagement` only when present (needs `engagement.read`; `manager` can be null).
- Facts strip from live `facts`: total pieces of work, waiting, stopped, finance stages, next finance milestone, and `finance.limited` shown as a plain "figures may be partial" note. Absent values are shown as not available. "Invoices verified" and "Paid" are not fed from `finance.delivered` (B-6 open); drop them from the strip until answered.
- Work rows from `items[]` (20 a page, `page` and `next_page`): line title, reference, state as given display text, started and updated times. The tag colour cannot come from a code (B-2 open); show the live words in one neutral tag and do not match on words. No station line.
- Tab bar from live `tabs[]` for the keys the frontend already routes (`journey`, `milestones`, `documents`, `money`, `registers`, `actions`); no counts. The tab screens themselves keep their v7 client until their own features.
- Delivery tab: no live tab exists. Keep the route, and show a plain "not available yet" state instead of mock data. No substitute from `department-handoffs` without a design decision.
- Mock: the mock `GET /projects` and `GET /projects/{case_id}` move to the live shape and are validated against the live contract in a test, as F-57 did for `/me`. Fixtures and tests that depend on the v7 project shape move with it; the tab screens that still call the v7 project tab endpoints keep working on the mock.
- Loading, empty, 403, 404 and error states through the shared error layer.

Out, binding: all tab contents (SCR-11, 12, 29, 38, 08), the Delivery tab content, `POST /assistant/conversations` from the "Ask me about this project" link (stays a link to `/assistant`), any write, and any backend change. No new business rule, no derived "what is next", no invented station, no derived count that pages cannot supply (a total from one page is not a total).

## Design questions for the design engineer (not blockers)
1. Next milestone and reference on each list row: drop, or wait for B-33?
2. Count badges on Active / Closed / All and the "N projects" line: drop, or show only once a status is loaded and say "20 or more" when `next_cursor` is set?
3. Journey: drop "What is next", Tola's project summary and the "Station 4 of 7" line, or hold them as empty slots? (B-3, B-4)
4. Facts strip: replace "invoices verified" and "paid" with live "finance stages", "next milestone" and "waiting" / "stopped"? (B-6)
5. Delivery tab: hide it while there is no live source, or keep it showing "not available yet"?
6. Status tag on work rows: one neutral tag with the live words, until B-2 gives a code.

## Risk
Medium. No money, migration or write, and both screens are built, but the project read is shared by every project tab and by the work-row links, and the mock shape change touches the v7 project fixtures that the tabs still use (frontend/src/features/projects, model.ts, useProject.ts, mock fixtures). Surfaces: ui (list, journey, tab bar), api and contract-change (live operations replace v7 ones, mock validated against the contract), product-decision (dropped parts and the readings of B-1 and B-32). Product acceptance is required because what people see changes: counts, next milestone, summary and Delivery content are gone or marked not available.
