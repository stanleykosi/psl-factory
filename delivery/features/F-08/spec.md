# A Lead opens Overview and sees every line, its stations and the work at each, flat or as a 3D floor

> Tasks: FE-M3-OVERVIEW (R-OVERVIEW, R-MOTION; R-REPORTS moves to the SCR-12 follow-on). Architecture: package v5, manifest digest `a91bc3ce41f97d59afd80bf918b8462d2a5d3eaf3ff7bace23cde79b751e8606` (`architecture/packages/v5/manifest.sha256`). The mock stays on the v4 contract, where `/api/v1/overview` is byte-identical to v5. Decision D-UPDATES r2 (approved). Design: approved canvas version 1794581312-b166 (`design/review.json`); screens: SCR-06, states default and reduced-motion. Artboards: SCR-06-desktop and SCR-06-mobile (`design/canvas/project/`). The 3D floor follows scope C-05 (`architecture/sources/scope-v2.md:78`) and `design/system/project/README.md` § Motion.

## Summary
- `/overview` replaces the placeholder with SCR-06. It shows four totals from E-OVERVIEW, one row per returned line with one square per station, each line's `note` as a tag, and "Updated <time> WAT" from `as_of`. It polls every 15 s while the tab is visible. The browser never computes a count (INV-ACCESS).
- A Flat / 3D floor switch (Flat by default) loads a plain three.js floor only when 3D is chosen. The floor shows the same lines, stations and counts. It moves only when a poll changes a count. Under reduced motion, without WebGL, below 720px, or if the floor fails to load, there is no 3D: the flat view still shows every line and every station count.
- Under the floor, a plain "See all exceptions" link goes to `/exceptions`, with the static My work line. There is no E-EXCEPTIONS fetch or import.
- The new runtime dependency is `three` at exactly 0.187.0, with `@types/three` 0.187.0 as a devDependency. A test proves the default Overview load contains no three.js code.
- Mock: the `E-OVERVIEW` fixture from the SCR-06 sample, three variants picked by a cookie in `frontend/mock/overview.mjs`, and a server.mjs change of one import, one `M1_OPERATIONS` entry and one dispatch line.

## Context
- **Route today:** `frontend/src/app/overview/page.tsx` renders `DestinationPage destination="overview"` (`frontend/src/shell/DestinationPage.tsx`). That gives a placeholder, or `NotOpenState` when `/me` destinations lack `overview`. Its metadata title is "Overview · PSL Factory". Keep that title.
- **Frame:**
  - `frontend/src/shell/AppShell.tsx` exports `useMe()`.
  - `frontend/src/shell/destinations.ts` exports `visibleDestinations`.
  - `frontend/src/shell/FrameStates.tsx` exports `LoadingState`, `SignedOutState({pathname})` and `NotOpenState({first})`, plus the `shell-errorcard` / `shell-eyebrow` / `shell-reference` / `shell-errorcard__action` classes in `frontend/src/styles/shell.css`.
  - The page pattern to copy is `frontend/src/features/my-work/MyWorkPage.tsx`: gate on `me.destinations` first, then render the feature.
- **API:**
  - `frontend/src/api/client.ts` exports `api` and `call()`. `frontend/src/api/errors.ts` maps 401/403/404 to `ApiError.kind` unauthenticated/forbidden/not_found. Anything else is server, and a failed fetch is network (`networkError()`).
  - `frontend/src/api/schema.d.ts:327` already has `/api/v1/overview`, so there is no regeneration and no contract repoint.
  - `frontend/src/api/types.ts` holds the derived types.
- **Polling pattern:** `frontend/src/features/my-work/MyWork.tsx:189-217`. `POLL_MS = 15_000`, an interval only while `document.visibilityState === 'visible'`, and an immediate refresh on return when the last success is older than 15 s. Its error card with "Last loaded …" is at `MyWork.tsx:333-347`.
- **Time:** `formatWat()` in `frontend/src/features/work-item/labels.ts:136` gives "14 Nov 16:40" in Africa/Lagos time. Import it; do not edit labels.ts.
- **Design system classes (do not edit `tokens.css` or `psl-bundle.css`; `tests/styles-drift.test.ts` guards them):**
  - `psl-seg` / `psl-seg__opt` (radiogroup with `aria-checked`, as in `WorkItemHistory.tsx:37`);
  - `psl-tag`, `psl-tag--neutral` and `psl-tag--person` (signal tint);
  - `psl-empty`, `psl-callout--warning|info`, `psl-loading` / `psl-busy` and `psl-link`.
  - Each feature defines its own visually-hidden class (`.my-work__sr` in `my-work.css:4`), so overview gets `.overview__sr`.
- **Mock:**
  - `frontend/mock/server.mjs:24` `M1_OPERATIONS` decides what is served. The rest answer 501.
  - `readFixture(id)` loads `fixtures/<id>.json` for every listed operation except E-ME (`server.mjs:184`).
  - Cookies are parsed into `cookies` before dispatch (`server.mjs:214`). The dispatch chain is at `server.mjs:222-231`. `frontend/mock/work-list.mjs` is the pattern for a handler module.
  - `frontend/tests/mock-contract.test.ts:69-89` automatically checks every `M1_OPERATIONS` entry: 200 and schema-valid for each persona (`finance_lead`, `pm`, `none`), and every declared error through `X-Mock-Scenario`. E-OVERVIEW declares 401, 403 and 404.
- **Tests that touch this route:** `frontend/e2e/frame.spec.ts:108-118` expects pm on `/overview` to get "This section isn't open to your role." with a link to `/my-work`. That must keep passing unchanged. `tests/shell.test.tsx` renders `DestinationPage` directly and is unaffected.
- **Board facts (SCR-06-desktop):**
  - Eyebrow, then h1 "Factory floor", then the View group "Flat | 3D floor" with Flat selected.
  - Four tiles: IN PROGRESS 18, NEED A PERSON 5, STOPPED 3, VERIFIED THIS MONTH 28.
  - A "Lines" section with 8 rows. Each row is a 210px name column, a station track with 26px squares on a 2px ink rule, and a 150px right tag.
  - Below: the exceptions panel and the legend sentence.
  - SCR-06-mobile: h1, a summary line, rows stacked (name and tag, then the squares), and no View switch.
  - Lines and station counts per row: Pre-sale 5, Planning 5, Release 5, Closing 4, Invoices 7, Month-end 5, Cash and BU 4, Payroll 5.
- **Nothing exists today** under `frontend/src/features/overview/` or `frontend/src/features/floor/`. `three` is not in `frontend/package.json`.

## Contract

### GET /api/v1/overview (E-OVERVIEW, read only)
- **Request:** `call(api.GET('/api/v1/overview'))`. There are no parameters and no body.
- **Type:** add `export type Overview = paths['/api/v1/overview']['get']['responses'][200]['content']['application/json'];` in `frontend/src/features/overview/types.ts`. Do not put it in `src/api/types.ts`, which is outside this lane.
- **200:** `{ as_of: date-time, totals: { in_progress, need_a_person, stopped, verified_this_month }, lines: [{ line, stations: [{ name, count, needs_person }], note }] }`. All integers are ≥ 0, and `additionalProperties` is false everywhere. There is no `sample` field, so no SAMPLE DATA tag is drawn (decisions-2026-11-14 (c)).
- **Permission and tenant rule:** "Leads, CEO, CTO; counts from visible records." The backend filters by grants (INV-ACCESS).
  - The frontend renders `totals`, `lines`, `stations` and `count` exactly as returned, in returned order. It never sums, filters, sorts or derives a figure.
  - The page fetches only when `useMe().destinations` includes `overview`. Otherwise it renders `NotOpenState` and sends no E-OVERVIEW request.
  - Nothing else from `/me` (roles, name) changes what is shown.
- **Errors:**
  - 401: `SignedOutState pathname="/overview"`. Polling stops.
  - 403 or 404: `psl-empty` with h3 "The factory floor isn't open to your role." and the server `message` as the paragraph. No figures are shown, and polling stops.
  - Network or 5xx: an error card (`shell-errorcard`, `role="alert"`) with:
    - eyebrow "ERROR · COULDN'T LOAD";
    - "We couldn't load the factory floor. Your work is safe; nothing was changed.";
    - "Last loaded <formatWat(as_of)> WAT." (only if an earlier load succeeded), then "Reference <code> for support.";
    - a Try again button that fetches again.

    The tiles, lines and 3D floor are **not** shown while this card is up, so old figures never pass as current. Polling continues, and the next success replaces the card.
- **Idempotency/versioning:** this is a read, so retrying is safe. Requests never overlap: a tick is skipped while one is in flight. A response that arrives after a newer one has rendered is dropped (compare `as_of`, or use a request sequence number).
- **Polling (D-UPDATES r2):** every 15 000 ms while the tab is visible; no requests while it is hidden; an immediate fetch on return when the last success is more than 15 s old. Reuse the `MyWork.tsx` approach, re-implemented locally in `features/overview/useOverview.ts`. Do not import from `features/my-work`.

### Screen states (SCR-06)
Common to every state: the page `<title>` is "Overview · PSL Factory" and the h1 is "Factory floor".

1. **Loading:** `LoadingState` (role status "Loading…").
2. **Not open:** see Permission. This is `NotOpenState` with the first visible destination, exactly as today.
3. **Error:** see Errors above.
4. **Empty (`lines: []`):**
   - The eyebrow and the four tiles still show as returned.
   - In place of the lines: `psl-empty` with h3 "No lines to show yet." and "Lines appear here when work you can see starts."
   - No View switch and no legend.
   - The exceptions section still shows.
5. **Default (flat), at ≥ 720px:**
   - **Eyebrow** (`<p>`, mono 12px): "FACTORY FLOOR · UPDATED <time dateTime={as_of}>{formatWat(as_of)}</time> WAT". The word "LIVE" is not used.
   - **h1 row:** "Factory floor" on the left. On the right, the View switch: `<div role="radiogroup" aria-label="View" class="psl-seg">` with two `button.psl-seg__opt` `role="radio"` options, "Flat" and "3D floor", using arrow-key roving focus as in `WorkItemHistory.tsx`. Flat is checked on first load. The choice is not persisted.
   - **Totals:** a 4-column bordered strip in board order. The labels are "IN PROGRESS", "NEED A PERSON", "STOPPED" and "VERIFIED THIS MONTH" (mono 11px, written in capitals in the markup, not CSS-transformed). The values are `totals.in_progress`, `need_a_person`, `stopped` and `verified_this_month` (Archivo 800 28px). The markup is a `<dl>`: each tile is a `<div>` holding a `<dt>` and a `<dd>`.
   - **Lines:** `<section aria-label="Lines">` containing a `<ul>`, with one `<li>` per `lines[]` entry in the order returned. Each row has three columns (210px / flexible / 150px):
     - **Name:** `line` (Archivo 700 16px). There is no avatar and no subtitle, because the contract has no field for either (PMO-0-4).
     - **Track:** an `<ol aria-label="<line> stations">` with one `<li>` per station, in order, on a 2px ink rule (`aria-hidden` decoration). Each square is 26px with a 2px ink border:
       - `needs_person: true`: signal fill (`--signal`), whatever the count;
       - else `count > 0`: ink fill;
       - else: white (surface) fill.

       When `count > 0`, the count is printed inside the square (mono 11px, `--on-strong`, `aria-hidden`). Each `<li>` carries visually-hidden text: "<name>: <n> item" or "<name>: <n> items", plus ", needs a person" when `needs_person`. With 0 it reads "<name>: 0 items".
     - **Tag:** `note` word for word in `psl-tag`. Use `psl-tag--person` when any station on that line has `needs_person: true`, otherwise `psl-tag--neutral`. Never parse or re-case `note` (PMO-0-4).
   - **Legend** (hint style, under the lines): "Each square is a station; dark squares hold work, orange ones need a person. The number in a square is how many items are there."
6. **3D floor (chosen, WebGL available, no reduced motion, ≥ 720px):**
   - While the floor module loads: in place of the track area, a `psl-loading` status reading "Loading the 3D floor…". The switch already shows 3D floor checked.
   - Once loaded: a `<canvas>` 480px high and the full width of the Lines panel, with `role="img"` and `aria-label` "3D factory floor: <n> lines. The same figures are listed in the flat view below." The flat `<ul>` stays in the DOM, wrapped in `.overview__sr`, so screen readers and find-in-page still reach every line and count. The totals, eyebrow and exceptions section stay visible.
   - The scene, built with plain `three` and no addons, orbit controls or gsap:
     - It has a fixed camera, angled down at the floor.
     - Each line is a strip with its name as a text sprite (a CanvasTexture), in returned order.
     - Each station is a square block on that strip. Its colour follows the flat rule, read from CSS custom properties (`--ink`, `--signal`, `--surface`) at mount, never hard-coded hex.
     - Above each station sits a count sprite with the exact `count`, plus up to 10 small token cubes (`min(count, 10)`). The sprite always carries the full figure.
   - **Motion (PMO-0-5, README § Motion):**
     - It renders on demand only. There is no idle `requestAnimationFrame` loop.
     - When a poll returns a station whose `count` or `needs_person` changed, that station's tokens are added or removed with a 280 ms ease-out rise or fade, the colour changes, and then rendering stops.
     - Stations, matched by line and station name, that are new or gone in a poll are added or removed without animation.
     - The first render does not animate.
   - Returning to Flat disposes the renderer, geometries, materials and textures, and calls `renderer.forceContextLoss()`.
   - **Fallback while in 3D:** if the floor module fails to import, `new WebGLRenderer` throws, or a `webglcontextlost` event fires:
     - switch to Flat;
     - show `psl-callout--warning` "We couldn't show the 3D floor, so it's shown flat." above the lines;
     - hide the 3D option for the rest of the page's life.
7. **Reduced motion or no WebGL (the SCR-06 reduced-motion state):**
   - When `matchMedia('(prefers-reduced-motion: reduce)').matches`, or `webglAvailable()` is false, there is no View switch. The flat view (state 5) shows, with one hint line under the h1:
     - "Motion is turned down on this device, so the floor is shown flat." (reduced motion takes precedence), or
     - "This device can't show the 3D floor, so it's shown flat."
   - If reduced motion turns on while 3D is shown, the page switches to Flat at once with no transition. The switch reappears only if reduced motion turns off again.
8. **Phone (< 720px, SCR-06-mobile):**
   - h1 "Factory floor", then the eyebrow line.
   - The totals sit in a 2 × 2 grid with the same four labels and values, in the same `<dl>` markup.
   - Each line stacks: name and tag on one row, then the full-width track. Squares stay 26px; a long track (7 stations) shrinks the gaps, and the page never scrolls sideways at 390px.
   - There is no View switch and no hint line. If the window narrows below 720px while 3D is shown, the page switches to Flat.
9. **Exceptions place (all non-error states):** under the legend sits `<section className="overview-exceptions" aria-labelledby="overview-exceptions-title">` with:
   - h2 `id="overview-exceptions-title"` "All exceptions · everyone's";
   - a Next.js `<Link href="/exceptions" className="psl-link">See all exceptions</Link>`;
   - `<p>` "Your own exceptions also appear in My work · Needs me, marked Fix."

   Keep this wrapper so follow-up (a) can put the preview in place of the link without restructuring the page. There is no count, no fetch and no import from `src/features/exceptions/**`.

### Floor module boundary (keeps three.js out of the initial bundle)
- `frontend/src/features/floor/support.ts` has no `three` import. It exports:
  - `webglAvailable(): boolean`, which tries `webgl2` then `webgl` on a throwaway canvas inside try/catch and releases it via `WEBGL_lose_context` if present;
  - `diffCounts(prev, next)`, a pure function returning the stations whose count or `needs_person` changed, matched by `line` + station `name`.
- `frontend/src/features/floor/Floor3D.tsx` is a client component, `export default function Floor3D({ lines, onFailure })`. It is the **only** module that imports `three` (statically, or through a sibling `scene.ts` that only it imports).
- `frontend/src/features/overview/**` loads it only with `import('@/features/floor/Floor3D')` inside the handler or effect that runs after 3D is chosen, or with `next/dynamic(() => import(...), { ssr: false })` rendered only in the 3D state. Either way, a rejected import must reach the fallback in state 6. No file outside `features/floor/**` imports `three` or `@/features/floor/Floor3D` statically.

### Dependency
- `frontend/package.json` `dependencies` gets `"three": "0.187.0"`, and `devDependencies` gets `"@types/three": "0.187.0"`. Both are exact, with no `^` or `~`. Install with `npm install --save-exact` so `frontend/package-lock.json` changes only for these two packages and their own transitive entries.
- No other package is added or bumped.

### Mock
- **`frontend/mock/fixtures/E-OVERVIEW.json`:**
  - `as_of` is `"2026-11-14T15:40:00Z"` (16:40 WAT).
  - Totals: `{ in_progress: 18, need_a_person: 5, stopped: 3, verified_this_month: 28 }`.
  - The 8 board lines in board order, with the station counts per line listed in Context. Station names come from the factory's real line stations where the guide names them, otherwise short plain names (Assumption 6). Squares follow the board: Pre-sale is dark, white, orange, white, white, and so on, with `count > 0` for dark squares, `needs_person: true` for orange squares and `count: 0` for white squares.
  - `note` values are the board tags: "1 WAITING", "1 STOPPED", "1 UNCERTAIN", "ON TRACK", "2 WAITING", "ON TRACK", "ON TRACK", "2 PROBLEMS".
  - The line totals deliberately do not add up to `totals` (for example, station counts summing to 21 against 18), so tests can prove nothing is summed.
- **`frontend/mock/fixtures/overview/`** holds three variants, each schema-valid:
  - `empty.json`: `lines: []`, totals all 0;
  - `zero.json`: the 8 lines with every `count: 0`, every `needs_person: false` and totals all 0;
  - `changed.json`: the default fixture with at least two counts changed, one `needs_person` flipped, a later `as_of` (`2026-11-14T15:40:15Z`) and changed totals.
- **`frontend/mock/overview.mjs`** follows `work-list.mjs`. It exports `OVERVIEW_VARIANTS = ['empty', 'zero', 'changed']` and `overview({ cookies })`, which returns `{ status: 200, body }`: the variant named by cookie `psl_mock_overview` when it is in the list, otherwise the default fixture. It reads its files once at load.
- **`frontend/mock/server.mjs`** gets exactly three changes:
  - `import { overview } from './overview.mjs';` next to the `work-list.mjs` import;
  - `'E-OVERVIEW'` appended to `M1_OPERATIONS`;
  - one dispatch line before the final `return send(res, 200, fixtures[...])`: `if (route.operationId === 'E-OVERVIEW') { const r = overview({ cookies }); return send(res, r.status, r.body); }`.

  Scenarios (`X-Mock-Scenario: 401|403|404`) already run before dispatch. Every persona gets 200, because the frontend gates on `/me` (PMO-0-3). Update the header comment of server.mjs by at most one line naming the cookie.

## Lanes
- **Frontend lane (owns all build work):**
  - `frontend/src/app/overview/page.tsx`
  - `frontend/src/features/overview/**` (OverviewPage.tsx, useOverview.ts, types.ts, overview.css, and a small `useMedia` hook)
  - `frontend/src/features/floor/**`
  - `frontend/mock/overview.mjs`
  - `frontend/mock/fixtures/E-OVERVIEW.json` and `frontend/mock/fixtures/overview/**`
  - `frontend/package.json` and `frontend/package-lock.json`, for `three` and `@types/three` only
  - `frontend/tests/overview*.test.tsx`, `frontend/tests/floor*.test.ts` and `frontend/tests/mock-overview.test.ts`
  - `frontend/e2e/overview.spec.ts`
- **Backend lane:** none. T-FLOOR, `apps/**` and the real API are not touched.
- **Integration owner:** the three-line change to `frontend/mock/server.mjs` (import, `M1_OPERATIONS` entry, dispatch line). F-05, F-06 and F-07 each make the same kind of edit. The integration owner resolves those merges by keeping every lane's entries and lines; it does not restructure the file. If another lane's lockfile change lands first, the integration owner also rebases `package-lock.json`.
- **Must not touch:**
  - `src/shell/**` and `src/api/**`
  - `src/app/exceptions/**`, `src/features/exceptions/**`, `frontend/mock/exceptions.mjs` and `frontend/mock/fixtures/exceptions/**`
  - any project or report route
  - `src/features/my-work/**`, `src/features/work-item/**` (import `formatWat` only) and `src/features/decide/**`
  - `src/styles/tokens.css` and `src/styles/psl-bundle.css`
  - `tests/mock-contract.test.ts`, `e2e/frame.spec.ts` and `architecture/**`
  - `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json`

## Acceptance criteria
Unit and component tests run under vitest (`// @vitest-environment jsdom` where needed) with `fetch` stubbed and `TZ=Africa/Lagos`. The e2e runs are `cd frontend && E2E_PORT=3801 MOCK_PORT=3802 npx playwright test e2e/overview.spec.ts`, with `timezoneId: 'Africa/Lagos'` and the default persona `finance_lead` unless stated.

1. The totals render exactly as returned, never summed. Verify: `tests/overview.test.tsx` renders the default fixture and finds dt/dd pairs "IN PROGRESS"/18, "NEED A PERSON"/5, "STOPPED"/3 and "VERIFIED THIS MONTH"/28, although the station counts sum to a different number. A second fixture with totals `{0,0,0,0}` but non-zero stations shows four 0s.
2. Every returned line and station is shown in order, with an exact count. Verify: in the component test, the "Lines" section has 8 `<li>` rows in fixture order. Each `<ol aria-label="<line> stations">` has as many items as the fixture's stations, and each item's text includes "<name>: <count> item(s)", which proves singular and plural.
3. Square state follows `count` and `needs_person`, and the tag tone follows `needs_person` only. Verify: in the component test, a station with `needs_person: true, count: 0` has the needs-person class and ", needs a person" in its text; `count: 3, needs_person: false` has the work class and a visible "3"; `count: 0, needs_person: false` has the empty class and no numeral. Pre-sale's tag reads exactly "1 WAITING" with `psl-tag--person`, and Closing's reads "ON TRACK" with `psl-tag--neutral`. A fixture `note` of "all good" renders as "all good", unparsed and not re-cased.
4. The coverage time shows. Verify: the component test finds "FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT" and a `<time dateTime="2026-11-14T15:40:00Z">`.
5. Empty lines. Verify: with cookie `psl_mock_overview=empty`, e2e at 1440 shows four 0 tiles, "No lines to show yet.", no `radiogroup` "View" and the "See all exceptions" link. The component test covers the same with `lines: []`.
6. All-zero lines. Verify: with `psl_mock_overview=zero` (e2e) or `zero.json` (component), all squares are empty-styled, no numerals are shown and tags appear verbatim.
7. Wrong user: a person without `overview` never fetches E-OVERVIEW. Verify: a component test with the `me.pm.json` fixture shows "This section isn't open to your role." with a link to `/my-work`, and `fetch` was never called with `/api/v1/overview`. `e2e/frame.spec.ts:108` still passes unchanged.
8. 401, 403 and 404 from E-OVERVIEW. Verify: in the component test, 401 renders "You're signed out." with a sign-in link whose `next` is `/overview`. 403 and 404 each render "The factory floor isn't open to your role." plus the server message and no tiles. After each, advancing fake timers 30 s makes no further overview request. In e2e, `page.route('**/api/v1/overview', …)` fulfils 403 with the mock's 403 body (a scenario cookie would also hit `/me`). The page shows the not-open text with no axe violations.
9. Provider failure, no stale figures. Verify: in the component test, the first load succeeds, then the 15 s poll gets a 500 (or a rejected fetch). The page shows `role="alert"` with "We couldn't load the factory floor. Your work is safe; nothing was changed.", "Last loaded 14 Nov 16:40 WAT." and "Reference <code> for support.", and **no** totals `<dl>` or Lines section. Try again with a 200 restores the figures.
10. Polling follows visibility. Verify: with fake timers in the component test, there is a second request at 15 000 ms and none before. With `document.visibilityState` stubbed to `hidden` and `visibilitychange` dispatched, no request happens over 60 s. Back to `visible` after more than 15 s triggers one immediate request. There is never more than one request in flight: a slow response plus a tick gives one request.
11. Out-of-order responses never win. Verify: in the component test, poll A is slow and poll B fast with a later `as_of`. After both resolve, B's figures and time show.
12. The 3D option follows reduced motion, WebGL and width. Verify: in the component test, with `@/features/floor/support` mocked:
    - `matchMedia('(prefers-reduced-motion: reduce)')` true gives no radiogroup "View" and the hint "Motion is turned down on this device, so the floor is shown flat.";
    - `webglAvailable()` false gives no radiogroup and "This device can't show the 3D floor, so it's shown flat.";
    - the phone query true gives no radiogroup and no hint;
    - otherwise the radiogroup "View" has "Flat" checked.
13. three.js is not loaded until 3D is chosen. Verify:
    - **Component:** `vi.mock('@/features/floor/Floor3D', factory)`, where the factory sets a spy flag. The flag is false after the Overview renders in Flat. Choosing "3D floor" sets it, and a canvas-stub `role="img"` named "3D factory floor: 8 lines…" appears while the flat list is still in the DOM.
    - **Static:** `tests/overview-imports.test.ts` reads every file under `src/app/overview/**` and `src/features/overview/**` and fails on `from 'three'` or a static `from '@/features/floor/Floor3D'`.
    - **Bundle (e2e, chromium):** collect every JS response on `/overview` until loaded. None contains the string `__THREE__`. After clicking "3D floor", at least one does.
14. The 3D floor shows the same figures, renders on demand and moves only on change. Verify:
    - `tests/floor.test.ts` checks that `diffCounts` returns exactly the changed stations between `E-OVERVIEW.json` and `overview/changed.json`, and none for identical inputs.
    - In e2e at 1440 (chromium with WebGL), click "3D floor". `canvas[role=img]` is visible and its WebGL context exists. `addInitScript` counts `requestAnimationFrame` calls: after the floor settles (1 s), the count does not grow over the next 2 s.
    - Using `page.clock`, set cookie `psl_mock_overview=changed` and advance 15 s. The station sr text shows the changed counts, rAF calls rise during the transition and stop again within 1 s. A screenshot is saved (`overview-3d-1440.png`) for product acceptance.
15. The no-WebGL fallback still shows every line and count. Verify: in e2e, `addInitScript` makes `HTMLCanvasElement.prototype.getContext` return null for `webgl`/`webgl2`. `/overview` shows no "View" switch, the "can't show the 3D floor" hint, 8 line rows, and station items whose sr text includes each count. There are no axe violations.
16. A runtime failure in 3D falls back to flat. Verify: in the component test, the mocked `Floor3D` calls `onFailure()`, or the mocked import rejects. The page shows the warning "We couldn't show the 3D floor, so it's shown flat.", "Flat" content returns and the radiogroup is gone.
17. Reduced motion (SCR-06 reduced-motion state). Verify: in e2e, `page.emulateMedia({ reducedMotion: 'reduce' })` at 1440 shows the flat view with the reduced-motion hint and no "3D floor" option. There are no axe violations, and a screenshot is saved.
18. Exceptions place. Verify: the component test finds h2 "All exceptions · everyone's", a link named "See all exceptions" with `href="/exceptions"`, and the text "Your own exceptions also appear in My work · Needs me, marked Fix." No request to `/api/v1/exceptions` is made. Tests do not navigate the link. `grep -rn "features/exceptions" frontend/src/features/overview frontend/src/app/overview` prints nothing.
19. Layouts and accessibility at 390px and 1440px (A-ACCESSIBILITY). Verify: e2e at 1440 × 900 and 390 × 844 for the default flat view, and at 1440 for 3D. Each has axe with WCAG 2.2 AA tags (the `my-work.spec.ts` helper pattern) and zero violations, `document.documentElement.scrollWidth <= innerWidth`, and screenshots `overview-1440.png` and `overview-390.png`. At 390 there is no "View" radiogroup, the totals form 2 columns, and every line name and tag is visible. Keyboard: Tab reaches "Flat" and "3D floor", arrow keys move the selection, and the focus outline is 2px solid. The "See all exceptions" link is reachable.
20. Mock contract. Verify:
    - `tests/mock-overview.test.ts` validates `E-OVERVIEW.json` and each `overview/*.json` against the v4 `E-OVERVIEW` 200 schema with Ajv 2020 strict. `overview({ cookies: { psl_mock_overview: v } })` returns each variant, and an unknown value returns the default.
    - Through `startMockServer({ port: 0 })`, `GET /api/v1/overview` with the cookie returns the variant.
    - The unchanged `tests/mock-contract.test.ts` passes, now including E-OVERVIEW 200 for all three personas and 401, 403 and 404 by scenario.
21. Dependency pinned. Verify: `node -e "const p=require('./frontend/package.json');console.log(p.dependencies.three,p.devDependencies['@types/three'])"` prints `0.187.0 0.187.0`. `git diff main -- frontend/package.json` shows only those two lines added. `npm ci` in `frontend/` succeeds, and `delivery/checks.sh` passes (lint, typecheck, vitest, `next build`).
22. The mock seam stays small. Verify: `git diff main -- frontend/mock/server.mjs` shows only the import, the `M1_OPERATIONS` entry, the dispatch line and at most one header-comment line.

## Out of scope
- The `ExceptionsPreview` / `ExceptionsList` mount, any E-EXCEPTIONS fetch, fixture, label or "See all N" count, and any import from `src/features/exceptions/**`. This is follow-up (a) after F-06 merges: import F-06's exported component in compact mode into `features/overview/OverviewPage.tsx` in place of the link.
- SCR-12, E-REPORT, R-REPORTS and the project Money tab. This is follow-on (b) after F-07 merges, and it needs a product answer first: where a person opens a report from.
- SCR-52 leadership line screens, Projects (F-07), Start work (F-05) and SCR-10 (F-06).
- Line avatars, line subtitles ("RFP · commercial") and status colours parsed from `note`. The contract has no fields for them (PMO-0-4).
- Clicking a line or station to drill down, filters, search or links into work items. The contract carries no ids.
- Orbit or zoom controls, a camera animation, idle or looping motion, mascot poses, gsap, three.js addons (`three/examples/**`), post-processing and any second dependency.
- Remembering the Flat/3D choice across visits.
- Backend T-FLOOR, `apps/**`, any `openapi.json` or `schema.d.ts` edit, and repointing the mock from v4 to v5.
- A visible SAMPLE DATA tag (decisions-2026-11-14 (c)), and any edit to `SampleLabel`.
- Restructuring `server.mjs` or `mock-contract.test.ts`, and editing shell navigation.

## Assumptions
1. The eyebrow reads "FACTORY FLOOR · UPDATED <date time> WAT" instead of the board's "FACTORY FLOOR · LIVE". Polling every 15 s is not live, and AGENTS.md asks for an explicit timestamp.
2. Station counts are printed inside the squares, and the legend gains one sentence explaining the number. The board's squares are blank, but the coordinator requires every station count to be visible in the flat fallback. Flagged for product acceptance.
3. Below 720px there is no 3D option, matching SCR-06-mobile, which draws no View switch.
4. On the phone, all four totals show in a 2 × 2 grid instead of the board's two-figure summary line, because readiness's outcome requires the four totals at 390px.
5. On a poll failure the figures are hidden behind the error card with "Last loaded …", as My work does. This is the smallest rule that never shows old figures as current.
6. The fixture station names are sample names (the board shows none). They are not business facts and carry no policy.
7. The 3D look is a fixed angled camera, square station blocks, count sprites, and up to 10 token cubes with a 280 ms ease-out on change only. The floor exists only in prose (SCR-06 note, README § Motion), and PMO-0-5 asks for exactly this interpretation. Flagged for product acceptance.
8. `three` 0.187.0 is pinned because it is the current release on 14 Nov 2026 (`npm view three version`), with the matching `@types/three` 0.187.0.
9. 404 from E-OVERVIEW is shown like 403. The endpoint uses 404 for "not visible", and both mean the person cannot see the floor.
10. The phone and reduced-motion hint wording is plain-language copy written here. The board has none for these conditions.
