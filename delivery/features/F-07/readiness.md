DECISION: READY
RISK: medium
SURFACES: ui, api
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-07 is READY on a narrower scope: the projects list (SCR-22) and one project's journey (SCR-07), desktop and phone, on the contract mock. E-PROJECTS and E-PROJECT are fully typed, and A-PROJECT's JR-08 half ("open project, see every line and what is next; no grant: 404") can be shown end to end.
- The project tabs (Milestones, Documents, Money, Registers, Actions) are split out. E-PROJECT-TAB returns `items[]` with `additionalProperties: true` and "Row shape per tab, documented in handoff", but handoff.md documents no row shape. A builder would have to invent every tab field, so the tabs are not buildable without guessing.
- Gates are in place:
  - FE-M3-PROJECTS is `planned` and depends only on T-FRONTEND-SHELL (merged, F-01).
  - validation.json lists `"FE-M3-PROJECTS": []`, and delivery.md says "Unresolved gates: none".
  - The four endpoints are unchanged from v4 to v5 (impact.json). D-PAGING r2 is approved.
  - The client approved SCR-07, -08, -11, -12, -22, -29 and -38 on 13 Nov (design/review.json, 1794581312-b166 and the Finance canvas 1794579902-95a3).
  - The architecture scope gate runs under the recorded early-start exception (manifest.json scope_gate), the same basis F-01 to F-04 used.
- Risk is medium. The work is read-only and shows no money, but it is the first consumer of two new endpoints. It must keep "no grant: 404" from leaking anything, and it edits the shared mock server while three other lanes do the same.
- Product acceptance is required. Several board elements have no contract field and will be left out (listed under Scope), so the design engineer must see the reduced boards.

## Findings
- PMO-0-1 | non-blocking | high | backend | E-PROJECT-TAB has no row shapes. openapi.json and handoff.md:4923-4929 say `"additionalProperties": true, "description": "Row shape per tab, documented in handoff"`, and no such section exists anywhere in architecture/packages/v5. A-PROJECT ("unknown stage amount is unknown, not 0; invoices and receipts separate", model.json:8799-8811) depends on the Money tab rows. Expected: before the tab features below start, the architecture gets a revision with typed rows for milestones, documents, money, registers and actions, including the amount object with `unknown`, as E-WORK-ITEM already has. Until then, no tab is built. The frontend may not draft these shapes itself, because Money carries contract amounts and payment state.
- PMO-0-2 | non-blocking | medium | integration | Some SCR-22 and SCR-07 board elements have no contract field, so F-07 omits them, invents nothing, and lists them in build.md for product acceptance and the backend developer:
  - SCR-22: the Active / Closed / All I can see tabs and their counts, the Filter button (E-PROJECTS takes only `q`, `cursor` and `limit`), and the columns Next milestone, Needs a person and Stopped. The row has only `case_id`, `title`, `pm`, `stage` and `sample`.
  - SCR-07: the PM / route / "8 pieces of work across 6 lines" sub-line, the six-cell facts strip (contract stages, invoices verified, waiting, stopped, next milestone, paid), each line's reference (RFP-0031) and detail line ("Station 2 of 5 · client UAT"), the tab counts, and Tola's project summary aside. E-PROJECT returns only `case_id`, `title`, `lines[{line, state, work_id}]` and `next`.
- PMO-0-3 | non-blocking | medium | integration | Four lanes edit `frontend/mock/server.mjs` at the same time (F-05, F-06, F-07 and F-08 each add operations to `M1_OPERATIONS` at line 24 and a dispatch branch near lines 226-234). Expected: F-07 puts its handlers in a new `frontend/mock/projects.mjs`, following the `work-list.mjs` pattern. Its server.mjs change is limited to appending `'E-PROJECTS', 'E-PROJECT'` to the operation list and adding one dispatch line. It rebases on whichever lane merges first. E-PROJECT-TAB and E-DOCUMENT keep answering 501.
- PMO-0-4 | non-blocking | low | frontend | `frontend/e2e/frame.spec.ts:238-241` expects an h1 "Projects" at /projects, and `tests/shell.test.tsx:217` renders /projects. Expected: the new list page keeps the h1 "Projects", and both tests stay green or are updated in the same commit.
- PMO-0-5 | non-blocking | low | frontend | The Money tab board is SCR-12 ("Report with drill-down", J-11). Its "Where ₦4,250,000 comes from" aside is report drill-down, which is E-REPORT and belongs to F-08 (FE-M3-OVERVIEW, R-REPORTS). Expected: when the money-tab feature is specified, the stage table goes to the projects lane and the drill-down component comes from F-08, so the two are not built twice.

## Scope
**Outcome (one, observable):** a signed-in person opens Projects from the top bar and sees the projects their grants cover, with PM and where each stands. They can search the list and choose 10, 20 or 50 rows per page. They open a project and see every line's work in the order returned, each with its state, plus what is next. Each line opens its work item. A project they may not see shows the not-found state and nothing else. This works at 390px and 1440px on the contract mock, and the JR-08 half of A-PROJECT and A-ACCESSIBILITY pass on the mock.

**In:**
1. **Projects list, SCR-22** (`frontend/src/app/projects/page.tsx`, replacing the DestinationPage placeholder):
   - It reads E-PROJECTS with `q`, `cursor` and `limit` (10/20/50, default 20, D-PAGING r2), using the CMP-22 toolbar's search field. No Filter button and no Active/Closed tabs (PMO-0-2).
   - Columns are Project (a link to `/projects/<case_id>`), PM and "Where it is" (`stage`, shown as returned). A "Show more" control appears when `next_cursor` is present. The result count is the number of rows loaded, not a total.
   - It has the shared empty, loading and error states (STATES boards) and the closing note "You see projects your roles cover." The phone layout follows SCR-22-mobile.
2. **Project journey, SCR-07** (`frontend/src/app/projects/[caseId]/page.tsx`):
   - It reads E-PROJECT and shows the breadcrumb, title, `next` ("What is next"), and the ordered `lines[]`.
   - Each line shows its `line` name and its `state`, using the existing `STATE_TAGS` from `src/features/work-item/labels.ts` (import only, no edit). Each line links to `/work/<work_id>`.
   - The empty state (no lines) follows SCR-07's empty board.
   - A 404 shows the not-found state and never reveals the title (JR-08 failure).
   - 401 and 403 go through the existing F-01 `ApiError` mapping.
   - The phone layout follows SCR-07-mobile.
3. **Project tab bar:** build it as a component in `src/features/projects/`, with only **Journey** rendered in this feature. The split features add their tabs. There are no dead or disabled tabs, and this goes to product acceptance.
4. **Sample label:** use the existing `SampleLabel` and the NEXT_PUBLIC_SHOW_SAMPLE_LABEL rule (decisions-2026-11-14 (c)). The tag is hidden by default, and `sample` is still read from the payload.
5. **Mock** (PMO-0-3):
   - E-PROJECTS and E-PROJECT go in `frontend/mock/projects.mjs`, with fixtures in `frontend/mock/fixtures/projects/`. All are `sample: true` and valid against the contract the mock loads (v4; these endpoints are identical in v5).
   - E-PROJECTS covers several projects, including a single-project page and a multi-page set for cursor paging, and supports `q` matching on title.
   - E-PROJECT covers per-case fixtures: a full journey across every state in the enum, an empty project, and a reserved no-access case_id that answers 404.
   - Lines point at existing `fixtures/work/W-*` ids where possible.
   - Persona filtering is optional. If used, it follows the existing cookie.
6. **Tests:**
   - Unit and component tests:
     - only returned fields render, with nothing drawn for the omitted elements;
     - the state tags map from the enum;
     - the 404 shows no project data;
     - paging sends `cursor` and `limit`, and search sends `q`.
   - A mock contract test for the new fixtures, in its own test file.
   - Playwright and axe at 390px and 1440px for the list, the journey, the empty state and not-found.

**Out (proposed split; each is its own feature):**
- **Projects · Milestones and Money tabs** (SCR-38 default and changed, SCR-12 project money). Gated on PMO-0-1 typed rows. Risk high (payments: contract amounts, Unknown, invoice and paid as separate facts, finance.read). Closes A-PROJECT's money half. It coordinates the drill-down with F-08 (PMO-0-5).
- **Projects · Registers and Actions tabs** (SCR-11, SCR-29). Gated on PMO-0-1. Risk medium. Issue and change detail (SCR-30, SCR-31) and the retrospective (SCR-33) are work-item and line screens, not tabs, and stay out.
- **Projects · Documents tab and document review** (SCR-08 via E-DOCUMENT). E-DOCUMENT is typed, but the Documents tab list has no board (the tab links straight to one version) and no row shape (PMO-0-1). SCR-08's Approve and Return are a version decision that belongs to the existing decide route (F-04, E-TASK-DECIDE), so that feature must reuse it rather than add a second decision path.
- SCR-43 delivery overview and the other line screens; backend and `apps/api` work (T-PROJECTS); the real API (FE-CONNECT-1); any openapi.json edit; any repoint of the mock contract from v4 to v5; new npm dependencies.

**Ownership (disjoint from F-05, F-06 and F-08):**
- `frontend/src/app/projects/**`
- `frontend/src/features/projects/**`
- `frontend/mock/projects.mjs`
- `frontend/mock/fixtures/projects/**`
- F-07's own test files (`frontend/tests/projects*.test.ts(x)` and `frontend/e2e/projects*.spec.ts`)

Shared touches limited to:
- the two-line registration in `frontend/mock/server.mjs`;
- the /projects assertions in `e2e/frame.spec.ts` and `tests/shell.test.tsx`, if they must change.

All must be listed in build.md. No edits to `src/shell/**`, `src/api/**`, `src/features/work-item/**` or `fixtures/work/**`.

**Task IDs:** FE-M3-PROJECTS (R-PROJECT), first part. The tab parts above complete it.
**Endpoints:** E-PROJECTS and E-PROJECT (read, through the contract mock). E-PROJECT-TAB and E-DOCUMENT are not used.
**Acceptance:** JR-08 success and failure on the frontend side, and A-ACCESSIBILITY. A-PROJECT's money-tab clause moves to the Milestones and Money feature.

## Risk
I rated it medium. The feature is read-only and shows no amounts. It does consume two new endpoints (E-PROJECTS, E-PROJECT), and the frontend must honour INV-ACCESS through "no grant: 404" without leaking the project title. It also changes the shared contract mock (`frontend/mock/server.mjs:24`, 226-234) while F-05, F-06 and F-08 change the same file (PMO-0-3), and it replaces a route that the frame tests assert on (PMO-0-4).

Surfaces:
- `ui`: SCR-22 and SCR-07.
- `api`: the first reads of E-PROJECTS and E-PROJECT through the generated client and the mock.

Excluded surfaces:
- `payments`: the Money and Milestones tabs are split out.
- `contract-change`: no repoint and no openapi edit.
- `security` and `auth`: the page only renders 401, 403 and 404 through the existing mapping.
- `product-decision`: the omitted elements are recorded for product acceptance, not decided here.

## Questions
None.
