DECISION: READY
RISK: medium
SURFACES: ui, dependency
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- Re-rated at the first-pass scope (readiness-first-pass.md) now that the coordinator has settled both blockers.
- PMO-0-1 is settled. SCR-12 (the project Money tab and the E-REPORT drill-down) leaves F-08. It goes to a follow-on feature that starts after F-07 merges.
- PMO-0-2 is settled. This round F-08 does not mount F-06's preview. The Overview shows the floor and a plain "See all exceptions" link to `/exceptions`, the route F-06 owns (F-06/readiness.md:39). The 3-row preview gets mounted in a small follow-up once F-06 merges.
- The gates still pass:
  - FE-M3-OVERVIEW (architecture v5) depends only on T-FRONTEND-SHELL, which is merged.
  - The client approved SCR-06 on 13 Nov 2026.
  - D-UPDATES is approved at r2.
  - The scope gate is the recorded early-start exception: mock-only and unreleased.
- Risk is medium because of the new `three` dependency and the shared mock seam. It writes nothing and shows no money. Product acceptance is required for the 3D floor, which is described only in prose, and for the PMO-0-4 tag rendering.

## Findings
- PMO-0-1 | verified | settled by the coordinator: SCR-12, E-REPORT and the Money tab are out of F-08 and go to a follow-on after F-07.
- PMO-0-2 | verified | settled by the coordinator: link only to `/exceptions` this round; F-06 owns the list component; the preview mount is a follow-up after F-06 merges.
- PMO-0-3 | non-blocking | medium | integration | This is unchanged from the first pass. Append only `'E-OVERVIEW'` to `M1_OPERATIONS` (frontend/mock/server.mjs:24) and do not restructure server.mjs. The integration owner resolves the one-line merge with F-05, F-06 and F-07.
- PMO-0-4 | non-blocking | low | integration | This is unchanged. E-OVERVIEW has no field for the line avatar, the subtitle or the tag colour. Show `note` word for word in a neutral tag, and use the signal tone only when a station has `needs_person: true`. Never parse `note`. List these gaps in build.md.
- PMO-0-5 | non-blocking | medium | product | This is unchanged. In the 3D floor, tokens show each station's `count`, orange where a person is needed. Motion happens only when a 15-second poll changes a count, never as a loop. Record this interpretation for product acceptance.

## Scope
The first-pass Scope in readiness-first-pass.md is binding. It has these changes:

**Outcome (one, observable):** a Lead opens Overview and sees every line they may see, with its stations and the work at each. They also see the four totals and the time they were taken. They can switch to a 3D floor that shows the same figures. With reduced motion, or with no WebGL, they get the flat view. Under the floor, a "See all exceptions" link goes to `/exceptions`. This works at 390px and 1440px on the contract mock, and A-OVERVIEW (frontend half) and A-ACCESSIBILITY pass.

**In:** items 1 to 5, 7 and 8 of the first pass stand as written (route, data and polling, totals, flat floor, toggle and 3D floor, mock, tests). Item 6 is replaced:
6. **Exceptions place.** Under the floor goes a section with a plain Next.js link, "See all exceptions", to `/exceptions`. Below it goes the static line "Your own exceptions also appear in My work · Needs me, marked Fix." Keep the section's markup so the follow-up can add the preview without restructuring the page.
   - There is no E-EXCEPTIONS fetch, import, fixture or label.
   - There is no "See all N" count.
   - Tests check the link's text and href only. They do not navigate to it, because `/exceptions` may not exist until F-06 merges.

**Out:** everything the first pass lists as out. In addition:
- the `ExceptionsPreview` / `ExceptionsList` mount (the follow-up after F-06);
- any import from `src/features/exceptions/**`;
- SCR-12, E-REPORT and the project Money tab (the follow-on after F-07).

**Ownership:** the first-pass file list stands. F-08 must not touch:
- `src/shell/**`
- `src/api/**`
- `src/app/exceptions/**`
- `src/features/exceptions/**`
- `frontend/mock/exceptions.mjs`
- `frontend/mock/fixtures/exceptions/**`
- any project or report route

This replaces the first pass's `src/app/overview/exceptions/**`, because F-06 put its route at `/exceptions`.

**Task IDs:** FE-M3-OVERVIEW (R-OVERVIEW and R-MOTION). R-REPORTS moves to the SCR-12 follow-on. **Endpoints:** E-OVERVIEW (read only). **Acceptance:** A-OVERVIEW on the frontend side, plus A-ACCESSIBILITY.

**Follow-ups to record (they are not F-08 scope):**
- (a) The preview mount after F-06 merges: import F-06's exported component in compact mode into `features/overview/OverviewPage.tsx` in place of the plain link.
- (b) The SCR-12 follow-on after F-07 merges. Before its readiness check it needs one product answer: where a person opens a report from.

## Risk
I rated it medium:
- The page is read-only and shows no money or identity data.
- It adds the first runtime npm dependency since the app frame: `three`, pinned exactly, with `@types/three` as a devDependency, in frontend/package.json and the lockfile. That needs a client-only dynamic import, a WebGL and reduced-motion fallback, and care with bundle weight. That is the `dependency` surface.
- It shares the `M1_OPERATIONS` seam (server.mjs:24, tests/mock-contract.test.ts:69-76) with three parallel lanes.
- It shows factory-wide counts. These must come from E-OVERVIEW as returned (INV-ACCESS), never be computed in the browser, and always show their `as_of` time.

Surfaces are `ui` (SCR-06 on desktop and phone) and `dependency` (three). Moving SCR-12 out removes `payments`. There is no `api` or `contract-change`, because it reads one existing GET and changes nothing in schema.d.ts or openapi.json. There is no `security` or `auth`, because gating comes from `/me` destinations and the backend.

## Notes
- I still cannot run `design.py check` (I have no shell). The coordinator should confirm that it passes for canvas 1794581312-b166 before the spec is written.

## Questions
None.
