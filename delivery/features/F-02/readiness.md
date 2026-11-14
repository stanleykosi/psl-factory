DECISION: READY
RISK: medium
SURFACES: ui
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-02 is FE-MYWORK, the My work page (SCR-01). Its only dependency, T-FRONTEND-SHELL, is merged (F-01, a41d472), and it has no other gates. It is one observable outcome: a person opens My work and sees their queues from GET /api/v1/work (E-WORK-LIST) through the contract mock.
- Gates are met:
  - D-PAGING r2 and D-UPDATES r2 are approved at their latest revision (model.json).
  - The client approved the design for SCR-01 and the STATES boards (design/review.json, canvas 1794581312-b166, 13 Nov 2026).
  - Architecture v3 passed validation and is complete. E-WORK-LIST, A-MYWORK and FE-MYWORK did not change from v2-reviewed (impact.json).
- Recorded exceptions apply, with their limits. The scope gate is an EXCEPTION: an early start for local artifact generation only, and PSL approval is still required. D-API-STYLE and D-AUTH are working assumptions. F-02 reads one GET endpoint, sends no writes, and authorises no release.
- Medium risk. The feature combines several behaviours on one screen: queues, search, filter, cursor paging with a choice of 10/20/50 rows, and 15 s polling. It uses the cross-layer query contract, and its mock work touches `frontend/mock/server.mjs`, which F-03 and F-04 share while all three are built in parallel. It touches no data, money, identity or writes.
- Product acceptance is required. Two parts are not drawn on the approved boards: the rows-per-page control, which D-PAGING r2 requires, and dropping the Project and Waiting-on filters, which E-WORK-LIST has no parameter for. The design engineer must see both.

## Findings
- PMO-0-1 | non-blocking | medium | integration | The approved filter panel (SCR-01-desktop-filter, CMP-22) offers Line, Project, State and Waiting on. E-WORK-LIST accepts only `q`, `line` and `state` (openapi.json /api/v1/work), so the Project and Waiting-on filters cannot be built without inventing parameters. F-02 ships Line and State only (see Scope). The contract owner should add the two parameters, or the design should drop them, before FE-CONNECT-1.
- PMO-0-2 | non-blocking | medium | integration | E-WORK-LIST provides no list of line filter options. It also does not say whether the `line` parameter takes a line key or the display title that rows carry in `line`. E-LINES lists only the lines a person may start, which is a different set. F-02 uses the row `line` value as is (see Scope). Settle this before FE-CONNECT-1.
- PMO-0-3 | non-blocking | low | integration | SCR-01 rows show an agent avatar (CMP-18) when an agent holds the item. Row items carry only `waiting_on` as free text, with no agent flag or name. F-02 shows no avatar rather than guess one from the text.
- PMO-0-4 | non-blocking | medium | integration | `frontend/mock/server.mjs` returns one fixed body for every operation, whatever the query. F-02 needs `queue`, `q`, `line`, `state`, `limit` and `cursor` to change the answer. F-03 will probably need E-WORK-ITEM answered by id. Both are parallel edits to one shared file. The integration owner should expect a merge in it. Each lane's change should be a small per-operation handler, not a rewrite. The mock still reads `architecture/packages/v2-reviewed/openapi.json`; for E-WORK-LIST that equals v3 (impact.json), so F-02 must not repoint it.

## Scope
**Outcome (one, observable):** at `/my-work`, a signed-in person sees the approved My work page (SCR-01) on desktop (1440px) and phone (390px). The page is driven only by E-WORK-LIST against the contract mock, and it passes A-ACCESSIBILITY in every state below.

**In:**
1. **Queue tabs (CMP-06).**
   - The tabs are Needs me, Waiting on others and Done, in that order. Unassigned is fourth and appears only when the response's `counts.unassigned` is present. The backend decides who is a Lead; the frontend does not check roles for this.
   - Counts sit in square count badges taken from `counts`. A count of zero shows "0".
   - Each tab maps to `queue=needs_me|waiting_on_others|done|unassigned`.
   - On phones the tab bar scrolls sideways, and labels never wrap.
   - The `lead-view` state (SCR-01-mobile-lead) is the persona whose response includes `unassigned`.
2. **Work list (CMP-07, CMP-03, CMP-05, CMP-16).** Each row shows:
   - A kind tag from the API `kind`: decide → DECIDE, do → DO, fix → FIX, started → STARTED, styled as the board shows. Never derive the kind from `state`; the board's prototype script does, and that must not be copied.
   - The title, linking to `/work/{id}`. That route belongs to F-03, so the link is not expected to resolve until the lanes are integrated.
   - The line and the mono reference.
   - The mini station bar from `station.index`/`count`, with "Station n of m · name".
   - The state tag from the contract's `state` enum, in CMP-05 wording and colour families.
   - `waiting_on` as given.
   - The age, formatted from `age_seconds`.
   - The SAMPLE DATA label on rows with `sample: true`.

   On phones, rows stack. There is no agent avatar (PMO-0-3).
3. **Search and filter toolbar (CMP-22).**
   - Search sends `q`. Debounce it, and never send an empty `q` (minLength 1).
   - Filters are State, with options from the contract's `state` enum, and Line, with options from the distinct `line` values in the rows loaded for the current queue plus any line already applied. The `line` value is sent exactly as the rows give it (PMO-0-2).
   - The toolbar shows the Filter button with its count, the result count, removable chips and Clear all, plus a no-results state.
   - On phones: a search box, a 44px filter icon and a bottom sheet.
   - Project and Waiting-on filters are out (PMO-0-1).
4. **Paging (D-PAGING r2).**
   - A rows-per-page choice of 10, 20 or 50, default 20, sent as `limit`.
   - "Show more" appears while `next_cursor` is present and appends the next page using `cursor`.
   - Changing the rows-per-page choice, the queue, the search or a filter reloads from the first page.
   - Neither control is drawn: use existing design-system controls, place them under the list, and list them in build.md for product acceptance.
5. **Staying current (D-UPDATES r2).**
   - Poll every 15 s while the page is visible, and stop while the document is hidden.
   - A refresh updates the counts and rows without dropping rows the person already loaded with Show more, moving focus, or resetting scroll.
   - Show when the data was last updated, from `as_of`.
6. **URL state.** The queue, `q`, filters and `limit` live in the URL's search parameters, so a reload or a shared link restores them. Use no localStorage, sessionStorage or cookies.
7. **States.**
   - default and my-work: the populated boards.
   - empty: the SCR-01-*-empty boards. The Needs me copy is "Nothing needs you right now". Other queues use the shared STATES pattern.
   - loading: skeleton rows from the STATES boards.
   - error: STATES error with Try again, mapped through the existing ApiError (401, 403, 404, network).
   - filter: the filter panel open (SCR-01-*-filter).
   - lead-view: as in item 1.
8. **Mock.**
   - Extend `frontend/mock/fixtures/E-WORK-LIST.json`, or add sibling fixture files, with sample rows for every queue and every `kind`, at least one `effect_uncertain` and one `owner_needed` row, enough rows to page at 10 and 20, and per-persona counts: `finance_lead` gets `unassigned`, `pm` does not.
   - Make the smallest handler change in `server.mjs` so E-WORK-LIST honours `queue`, `q`, `line`, `state`, `limit` and `cursor`.
   - Every mock response must still validate against openapi.json in the existing contract test.
9. **Tests.**
   - Unit and component tests:
     - each queue requests the right `queue`;
     - Needs me shows only decide, do and fix rows;
     - badges equal `counts`;
     - Unassigned is hidden when absent;
     - `limit` is 10, 20 or 50, default 20, and Show more uses `next_cursor`;
     - an empty `q` is never sent;
     - polling pauses while the page is hidden;
     - sample rows are labelled.
   - Playwright and axe at 390px and 1440px for each state in item 7. As in F-01, if this cannot run inside checks.sh, record the command and result in build.md.

**Out:**
- The Start work split button and drawer (CMP-23, FE-M2).
- The floor tracks (CMP-08, FE-M3). The board's `tracks` data is not rendered on My work.
- The work item page and history (FE-WORKITEM, F-03).
- Decisions (FE-DECIDE, F-04).
- Notifications.
- The All exceptions screen (SCR-10).
- Connecting to the real API (FE-CONNECT-1).
- Any backend or `apps/api` work, including T-MYWORK.
- Changes to openapi.json.
- New npm dependencies.
- Changes to `src/shell/**` or `src/api/**` beyond what the page cannot do without. Any such change must be minimal and listed in build.md.

**Ownership:** `frontend/src/app/my-work/**`, `frontend/src/features/my-work/**` and the E-WORK-LIST fixture(s), plus the minimal E-WORK-LIST handler in `frontend/mock/server.mjs`.

**Task IDs:** FE-MYWORK (R-MYWORK, R-VOLUME, R-SAMPLE, D-PAGING, D-UPDATES).
**Acceptance:** A-MYWORK, frontend half: kinds, counts and sample labels. The payroll exclusion is enforced by the backend and only rendered here. Also A-ACCESSIBILITY for this page.
**Endpoint:** E-WORK-LIST (GET /api/v1/work), through the contract mock only.

## Risk
I rated it medium, not low:
- It combines several behaviours that interact: queues, search, two filters, cursor paging with a page-size choice, and visibility-aware polling that must not disturb rows the person loaded.
- It is the first feature to use E-WORK-LIST's query contract, which FE-CONNECT-1 inherits.
- It changes `frontend/mock/server.mjs`, a file shared with F-03 and F-04 while the lanes run in parallel (PMO-0-4).

It is not high: it is read-only, it sends no writes or CSRF-bound actions, and it involves no money, identity, migrations or deployment. Visibility rules (INV-ACCESS, INV-RESTRICTED) stay in the backend.

Surfaces:
- `ui`: SCR-01 and the shared STATES boards, components CMP-03/05/06/07/16/22.

The surfaces exclude `api` and `contract-change`, because openapi.json is consumed, not changed. They exclude `dependency`, because no packages are added. They exclude `auth`, because the page reads only `/me` through the existing shell.

Product acceptance is required. The rows-per-page control and its placement are not on the approved boards, and the filter panel ships without Project and Waiting on. The design engineer should confirm both on the built page.

## Notes
- I could not run `design.py check`; my role is read-only and has no shell. Under `config.json` `design_gate: required`, the coordinator should confirm it passes against the approved canvas before build.
- The design's own open question, "which column matters most after the work title", is still open in design/components.md. It does not block this feature: build the column order the approved boards show.
- Carried item QA-3-2 (the mock does not validate write bodies) does not apply. F-02 sends no writes, and it stays carried for F-04.
- The project's AGENTS.md describes the Django factory build loop. This frontend task keeps its records through the delivery workflow in `delivery/`.

## Questions
None.
