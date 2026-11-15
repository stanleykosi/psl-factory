DECISION: NOT-READY
RISK: medium
SURFACES: ui, dependency
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- The gates pass:
  - FE-M3-OVERVIEW (architecture v5) depends only on T-FRONTEND-SHELL, which is merged, and delivery.md says "Unresolved gates: none".
  - The client approved SCR-06, SCR-10 and SCR-12 on 13 Nov 2026 (design/review.json, canvas 1794581312-b166).
  - The only decision this feature uses is D-UPDATES, approved at r2 (polling every 15 s).
  - The scope gate is the recorded early-start EXCEPTION (manifest.json scope_gate). It allows mock-only, unreleased work, as F-01 to F-04 had.
- It is not ready as one parallel lane because SCR-12 is not on the Overview. The canvas labels SCR-12 "Project · Money": the board sits under Projects, with the project tab bar and the Money tab selected. The Money tab belongs to F-07 (FE-M3-PROJECTS: A-PROJECT "project journey and money tab", E-PROJECT-TAB `money`). Two parallel lanes would both build the Money tab. FE-M3-OVERVIEW's own acceptance is A-OVERVIEW only; A-REPORT is a T-PROJECTS (backend) acceptance.
- Proposed split:
  - **F-08 keeps** the Overview: the SCR-06 floor (flat view, 3D view, reduced motion), the four totals, and the place for everyone's exceptions. F-08 is READY at that scope as written below.
  - **A new follow-on feature** takes the SCR-12 drill-down (E-REPORT). It starts after F-07 merges.
- Exceptions without duplication: F-06 owns everything that reads E-EXCEPTIONS, both the full SCR-10 list and the 3-row preview drawn under the floor. F-08 owns the Overview page and mounts F-06's preview component. Whichever lane merges second adds that one mount line.
- Risk is medium. This is the first new npm dependency since the app frame (`three`), and the page shows counts derived from records. It writes nothing and shows no money. Product acceptance is required: the 3D floor has no drawn board, only a note on SCR-06 and two lines in the design system README.

## Findings
- PMO-0-1 | blocking | high | pmo | SCR-12 overlaps F-07. design/canvas/project/canvas.json:4350 labels it "SCR-12 · Project · Money". The SCR-12-desktop board highlights Projects and shows the project tab bar with Money selected (SCR-12-desktop.dc.html:15-17), and canvas.json:4197 says reading the leadership report "is SCR-12". The stage table on that board (stage, amount, invoice, paid) is E-PROJECT-TAB `money`, which A-PROJECT gives to F-07. Only the "Where ₦4,250,000 comes from" panel is E-REPORT (`figures[].sources`). E-REPORT has no list endpoint and no link from the Overview, so F-08 would have to invent both a route and an entry point. Expected: take R-REPORTS / SCR-12 out of F-08 and put it in a follow-on that depends on F-07 (the project tab bar and the Money tab). It adds the source drill-down to the Money tab's figures from E-REPORT and shows Unknown, never 0 (INV-UNKNOWN). Actual: the coordinator assigns SCR-12 to F-08 while F-07 runs in parallel.
- PMO-0-2 | blocking | medium | pmo | F-06 and F-08 both need the exceptions under the floor (decisions-2026-11-13.md item 5). The SCR-06 board draws three rows of E-EXCEPTIONS plus "See all 4", linking to SCR-10 (SCR-06-desktop.dc.html:17). If F-08 builds its own table, F-06's row labels, the `what` wording (including `blocked`, which work-item/labels.ts:20-32 has no label for), the empty state and the E-EXCEPTIONS fixture all get built twice. Expected: F-06's scope includes an exported `ExceptionsPreview` (first 3 rows, "See all" link) next to its list. F-08 mounts it in `features/overview/OverviewPage.tsx`, and whichever lane merges second adds that import and mount line. F-08 creates no E-EXCEPTIONS fixture, label or handler. The coordinator should confirm this, and the SCR-10 route (proposed `/overview/exceptions`, because canvas.json:4188 puts SCR-10 under Overview), with F-06's readiness before either spec is written.
- PMO-0-3 | non-blocking | medium | integration | `frontend/mock/server.mjs:24` (`M1_OPERATIONS`) is a shared line: F-05, F-06, F-07 and F-08 each append operations to it. `tests/mock-contract.test.ts:69-76` also expects every listed operation to return 200 for every persona, including `pm` and `none`, although E-OVERVIEW is "Leads, CEO, CTO". Expected: F-08 appends only `'E-OVERVIEW'`, and the integration owner resolves that one-line merge. The mock may return 200 to every persona, because the frontend gates on `/me` destinations (the `pm` and `none` personas have no `overview`). The 403 path is covered by `X-Mock-Scenario`. F-08 must not restructure server.mjs.
- PMO-0-4 | non-blocking | low | integration | Some board elements have no E-OVERVIEW field:
  - the agent avatar and the subtitle on each line ("RFP · commercial"); `lines[]` has only `line`, `stations` and `note`;
  - the colour of the right-hand status tag (amber for waiting, orange for stopped and uncertain, green for on track); `note` is free text.

  Expected: omit the avatar and subtitle. Show `note` verbatim in a neutral tag, using the signal tone only when a station on that line has `needs_person: true`. List both in build.md for product acceptance and for the backend developer. Do not parse `note` text to choose a colour.
- PMO-0-5 | non-blocking | medium | product | The 3D floor exists only as prose: the SCR-06 note ("the 3D floor shows the same lines in three.js with work moving between stations") and design/system/project/README.md:46-51 ("Motion explains a change of state; it never decorates", tokens between square stations). E-OVERVIEW has counts only and no movement of single items. Expected: tokens show `count` at each station, with orange for `needs_person`. Movement happens only when a 15-second poll changes the counts, never as a loop. Record this interpretation for product acceptance.

## Scope
F-08 is binding at this scope once the coordinator records the split (PMO-0-1) and the exceptions ownership (PMO-0-2).

**Outcome (one, observable):** a Lead opens Overview and sees every line they may see, with its stations and the work at each, plus the four totals and the time they were taken. They can switch to a 3D floor showing the same figures. With reduced motion, or with no WebGL, they get the flat view. Everyone's exceptions appear under the floor through F-06's component. This works at 390px and 1440px on the contract mock, and A-OVERVIEW (frontend half) and A-ACCESSIBILITY pass.

**In:**
1. **Route.** `frontend/src/app/overview/page.tsx` replaces the DestinationPage placeholder. Components live in `frontend/src/features/overview/**`. A person whose `/me` destinations lack `overview` gets the existing NotOpenState (src/shell/DestinationPage.tsx:15-16). 401, 403 and 404 go through the existing ApiError mapping.
2. **Data.** Read E-OVERVIEW (`GET /api/v1/overview`) through the existing typed client; schema.d.ts already has the path, so there is no contract repoint. Poll every 15 s while the tab is visible and pause when it is hidden (D-UPDATES r2). Show `as_of` as the coverage time ("Updated 16:40", in WAT, using the existing `formatWat`). On error, never show old figures as current.
3. **Totals.** Four tiles from `totals`: in progress, need a person, stopped, verified this month, with the board's wording.
4. **Flat floor (SCR-06 default and reduced-motion, desktop and phone).** One row per `lines[]` entry with the line name, one square per station, and `note` as the right-hand tag (PMO-0-4). A square is dark when `count > 0`, orange when `needs_person`, and white when empty. Each square has an accessible name ("<station>: <count> items, needs a person"). The legend sentence comes from the board. When `lines` is empty, show the shared empty pattern.
5. **View toggle and the 3D floor.**
   - The Flat / 3D floor toggle defaults to **Flat**, as on the board.
   - The 3D floor lives in `frontend/src/features/floor/**`. It uses plain `three`, pinned to an exact version, with `@types/three` as a devDependency. It is loaded with a client-only dynamic import the first time 3D is chosen, so the default Overview load does not include three.js.
   - It shows the same lines and stations with tokens per count, orange where a person is needed. Motion happens only on a count change (PMO-0-5). It has a fixed camera, no orbit controls and no gsap.
   - Under `prefers-reduced-motion: reduce`, or when WebGL is unavailable, the 3D option is not offered and the flat view shows (A-OVERVIEW: "reduced motion shows the flat view").
   - The canvas has a text alternative. The totals and a visually-hidden flat list stay readable while 3D is shown.
6. **Exceptions place.** A section under the floor where F-06's `ExceptionsPreview` is mounted (PMO-0-2). Below it goes the static line "Your own exceptions also appear in My work · Needs me, marked Fix."
7. **Mock.** `frontend/mock/fixtures/E-OVERVIEW.json`, valid against the v4 schema and drawn from the SCR-06 sample: 8 lines and the board's totals. Variants go under `frontend/mock/fixtures/overview/` (no lines; all counts zero) if the builder needs them. Append `'E-OVERVIEW'` to `M1_OPERATIONS` (PMO-0-3). The visible SAMPLE DATA tag stays off (decisions-2026-11-14.md (c)).
8. **Tests.**
   - Unit and component tests:
     - the counts render exactly as returned;
     - the station square states follow `count` and `needs_person`;
     - reduced motion and no WebGL offer no 3D option;
     - polling stops while the tab is hidden;
     - three.js is not imported until 3D is chosen (the floor module is mocked in jsdom).
   - Mock contract tests for the fixture.
   - Playwright and axe at 390px and 1440px for flat, 3D (chromium) and reduced motion (emulated).

**Out:**
- SCR-12, E-REPORT and the project Money tab (PMO-0-1: the follow-on after F-07, and F-07).
- SCR-52 leadership report line screens.
- The SCR-10 list, the E-EXCEPTIONS fixture and labels, and the preview component (F-06).
- Projects (F-07) and Start work (F-05).
- Mascot pose motion and gsap.
- Backend T-FLOOR, the real API and any openapi.json edit.

**Ownership:** F-08 may change only these files:
- `frontend/src/app/overview/page.tsx`
- `frontend/src/features/overview/**`
- `frontend/src/features/floor/**`
- `frontend/mock/fixtures/E-OVERVIEW.json` and `frontend/mock/fixtures/overview/**`
- the one `M1_OPERATIONS` entry in `frontend/mock/server.mjs`
- `frontend/package.json` and `package-lock.json`, for `three` and `@types/three` only
- `frontend/tests/overview*.test.tsx`, `frontend/tests/mock-overview.test.ts` and `frontend/e2e/overview.spec.ts`

It must not touch:
- `src/shell/**` (the destination already exists)
- `src/api/**`
- `src/app/overview/exceptions/**`
- any project or report route

**Task IDs:** FE-M3-OVERVIEW (R-OVERVIEW and R-MOTION; R-REPORTS moves to the follow-on).
**Endpoints:** E-OVERVIEW (read). E-EXCEPTIONS is read only through F-06's component.
**Acceptance:** A-OVERVIEW on the frontend side, plus A-ACCESSIBILITY. "Counts match visible work" is enforced by the backend (INV-ACCESS); the frontend shows only what is returned.

## Risk
I rated it medium:
- The page is read-only and shows no money.
- It adds the first runtime dependency since the app frame: `three` in frontend/package.json:21-29, plus the lockfile. Next.js rendering on the server needs a client-only import, and bundle weight and WebGL fallback have to be handled. That is the `dependency` surface.
- It joins a shared mock seam with three parallel lanes (server.mjs:24, mock-contract.test.ts:69).
- It displays factory-wide counts that must come from the API, never be computed in the browser (INV-ACCESS, AGENTS.md "explicit coverage and timestamps").

Surfaces:
- `ui`: SCR-06 on desktop and phone.
- `dependency`: three.

Excluded surfaces:
- `api` and `contract-change`: it reads one existing GET and repoints nothing.
- `security` and `auth`: gating comes from `/me` and the backend.
- `payments`: SCR-12 money moves out.

## Notes
- I could not run `design.py check` because I have no shell; the coordinator should confirm it passes for 1794581312-b166.
- The follow-on for SCR-12 needs one product answer before its readiness check: where a person opens a report from. E-REPORT has no list endpoint, and only the Money tab is drawn.
- The E-EXCEPTIONS contract has no total count. F-06's "See all N" can show N only when there is no `next_cursor`; otherwise it should read "See all". F-06 should carry this.

## Questions
None. The blockers are about scope and lane ownership, and the coordinator settles them, not the client.
