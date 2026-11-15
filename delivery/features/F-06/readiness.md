DECISION: READY
RISK: low
SURFACES: ui, api
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-06 now covers only the All exceptions list: SCR-10, read from E-EXCEPTIONS. This is the "F-06A" from readiness-full-not-ready.md, and the coordinator has accepted that split. Recording a response (SCR-16), reconcile, resume and cancel move to a later feature, which waits for an architecture v6 proposal that closes PMO-0-1 to PMO-0-5 from the earlier assessment.
- The gates are clear. FE-M2B is planned in architecture v5 with no unresolved gates (packages/v5/delivery.md:995-1026). Its only dependency, FE-WORKITEM (F-03), is merged. The client approved SCR-10 (design/review.json:23, canvas 1794581312-b166). E-EXCEPTIONS is fully typed (packages/v5/handoff.md:4260-4374) and is already in the v4 contract the mock loads (frontend/src/api/schema.d.ts:222).
- It is a read-only list filtered by the person's grants, with no writes and no amounts, so risk is low.
- No duplication with F-08. F-06 owns one reusable `ExceptionsList` component. F-08's Overview (13 Nov decision: "Overview shows the factory floor and everyone's exceptions") links to `/exceptions` or embeds that component. F-08 does not build its own list.
- FE-M2B stays open after this merges. A-RESPONSE and A-RECONCILE belong to the later response and reconcile feature.

## Findings
- PMO-0-1 | non-blocking | low | integration | SCR-10 shows a few things E-EXCEPTIONS cannot supply (carried from PMO-0-6 of the full assessment):
  - the reference under each title;
  - the search box and the Filter button;
  - the "4 OPEN" total (SCR-10-desktop.dc.html:30, 44).

  The rows carry only `work_id, what, title, doing, who_acts, since`, and the endpoint takes only `cursor` and `limit`. Expected: leave these out, invent nothing, and list them in build.md for product acceptance and the backend developer. Show "N shown" (rows loaded), never a total.
- PMO-0-2 | non-blocking | low | integration | Four lanes edit `frontend/mock/server.mjs` at the same time (M1_OPERATIONS at line 24, dispatch at line 215). Expected: put the E-EXCEPTIONS handler in its own `frontend/mock/exceptions.mjs`, following `work-list.mjs`. The server.mjs change is then one entry appended to `M1_OPERATIONS` and one dispatch line. Rebase on whichever lane merges first.
- PMO-0-3 | non-blocking | low | frontend | E-EXCEPTIONS is used by both "Overview and All exceptions page" (handoff.md:4281). If F-06 and F-08 each wrote their own fetch, the Overview and `/exceptions` could disagree on paging and `as_of`. Expected: F-06 exports both the fetch hook and the list component from `src/features/exceptions/index.ts`. F-08 imports them and does not edit them. Changes go through the exceptions lane.

## Scope
**Binding for the spec writer.**

**Outcome (one, observable):** a Lead opens `/exceptions` and sees every exception their grants allow. Each row shows:
- the kind tag (`what`);
- how long it has waited (`since`);
- the work title, linked to `/work/<work_id>`;
- what is being done (`doing`) and who acts (`who_acts`).

The person can choose 10, 20 or 50 rows per page and use "Show more". The page shows "As of <as_of, Africa/Lagos>". It works at 390px and 1440px on the contract mock, and A-ACCESSIBILITY passes.

**In:**
1. **Route.** `frontend/src/app/exceptions/page.tsx` (new; no existing route or placeholder) renders the list.
2. **Component and hook.** These go in `frontend/src/features/exceptions/**`. Export `ExceptionsList` and its data hook from `index.ts` so F-08 can reuse them (PMO-0-3).
   - The component takes an optional `limit` and an optional "compact" flag, so it can be embedded with no page chrome.
   - It also takes a "See all exceptions" link target.
   - It must not depend on the `/exceptions` page.
3. **Read.** E-EXCEPTIONS is read with `limit` (10/20/50, default 20, D-PAGING) and `cursor`. "Show more" appears only when `next_cursor` is present. Rows appear in the order returned, with no client-side sorting or filtering.
4. **Kind tags, as drawn on the board.** `effect_uncertain` is amber "Send uncertain". `owner_needed`, `setup_needed`, `blocked` and `followup_needed` are orange or red. The footer sentence is "The factory never resends...", as drawn. Times are in Africa/Lagos.
5. **States.** Default and empty come from the SCR-10 boards. Loading and error (with Try again) come from the shared patterns. A 401 goes through the existing `SignedOutState`. A 403 (not a Lead) shows a no-access view through the F-01 `ApiError` mapping. There are no action buttons anywhere on the list. Rows link to the work item only, where any action lives.
6. **No SAMPLE DATA tag.** Use the existing NEXT_PUBLIC_SHOW_SAMPLE_LABEL rule (sources/decisions-2026-11-14.md (c)): hidden by default, and no new tag. The E-EXCEPTIONS rows have no `sample` field, so nothing is drawn per row.
7. **Link from the work item page.** In `frontend/src/features/work-item/WorkItemOverview.tsx`, `NextStep` (line 164), add one "See all exceptions" link to `/exceptions`. Show it only for the states effect_uncertain, awaiting_reconciliation, owner_needed, setup_needed and followup_needed. That is the only F-03 edit allowed: an import and a few lines, listed in build.md. The link target is already named in F-03/spec.md:250.
8. **Mock** (PMO-0-2).
   - The handler goes in `frontend/mock/exceptions.mjs`. Fixtures go in `frontend/mock/fixtures/exceptions/`, valid against the schema and paged by `limit`/`cursor` the same way as F-03's history.
   - Fixtures cover at least 25 rows across all five kinds, so a 20-row page shows "Show more", plus one empty scenario.
   - Each `work_id` points to an existing per-id work fixture (W-1005 for effect_uncertain) or to a new one from **W-1501 up** for the other kinds.
   - The mock stays on the v4 contract. E-EXCEPTIONS is identical in v5.
9. **Tests.**
   - Component tests: kind mapping, order kept, paging requests (`limit`, `cursor`), empty, 401, 403, and the compact embedded mode.
   - Mock contract tests in their own file (`frontend/tests/exceptions-mock.test.ts`), or appended to `mock-contract.test.ts`.
   - Playwright and axe at 390px and 1440px for default and empty.

**Out:**
- Recording a response (SCR-16), reconcile, resume and cancel (E-WORK-ACTION), E-RESPONSE and E-EVIDENCE-UPLOAD. These are the later feature, after v6. The RFP outcome states are parked.
- Search, filter, the reference and the total count (PMO-0-1).
- The Overview page itself and where the list sits on it (F-08).
- Any top-bar highlight for /exceptions, or any other shell change.
- New npm dependencies.
- Any edit to openapi.json, `src/api/**`, `src/shell/**` or `architecture/**`.

**Ownership (disjoint from F-05, F-07 and F-08):**
- Owns:
  - `frontend/src/app/exceptions/**`
  - `frontend/src/features/exceptions/**`
  - `frontend/mock/exceptions.mjs`
  - `frontend/mock/fixtures/exceptions/**`
  - `frontend/mock/fixtures/work/W-15xx*.json`
  - `frontend/tests/exceptions*.test.ts(x)`
  - `frontend/e2e/exceptions.spec.ts`
- Shared touches, additive only, all listed in build.md:
  - the one-entry, one-line registration in `frontend/mock/server.mjs`;
  - the `NextStep` link in `WorkItemOverview.tsx`;
  - `mock-contract.test.ts`, if appended rather than a new file.
- Does not touch:
  - F-05's Start work files;
  - F-07's projects files;
  - F-08's `src/app/overview/**`, floor and reports files;
  - `decide/**`, `my-work/**`, `src/shell/**`, `src/api/**`.

**F-06 / F-08 boundary.** F-06 owns the exceptions list, its hook and its mock. F-08 owns where the list sits on the Overview. F-08 either links to `/exceptions` or imports `ExceptionsList` in compact mode, with no edits to `src/features/exceptions/**`. If F-08 merges first, it shows a link only and adds the embed after F-06 merges. It must not build a second list or a second E-EXCEPTIONS fixture set.

**Task IDs:** FE-M2B, R-EXCEPTION part only. R-RESPONSE stays open for the later feature. **Endpoint:** E-EXCEPTIONS (GET /api/v1/exceptions, read, on the contract mock). **Acceptance:** A-ACCESSIBILITY. A-RESUME is mapped to E-EXCEPTIONS but belongs to backend T-EXCEPTIONS. A-RESPONSE and A-RECONCILE are not in this feature.

## Risk
I rated it low. The feature is a read-only list with no writes, no CSRF-bearing calls, no amounts and no external messaging. The backend does the grant filtering ("Leads; filtered by grants", handoff.md:4284). The frontend only has to render 401 and 403 correctly and offer no actions. Surfaces are `ui` (a new route and states) and `api` (it consumes a new endpoint through the mock). The small shared edits to `server.mjs` and `WorkItemOverview.tsx` are additive and contained, so they do not add a contract-change surface. Product acceptance is required: this is a new screen for the client, and SCR-10 is built without the reference, search, filter and total (PMO-0-1), so the design engineer must see the reduced board.

## Notes
- I did not run `design.py check`, because my role is read-only. The approval in design/review.json covers SCR-10.

## Questions
None.
