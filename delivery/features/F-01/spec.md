# The app frame loads who is signed in and shows only their sections, on phone and desktop, against a contract mock

> Tasks: T-FRONTEND-SHELL (R-FRONTEND, R-DEVICES, R-SAMPLE; acceptance A-ACCESSIBILITY). Architecture: package `architecture/packages/v2-reviewed`, manifest.sha256 `b4c07be41b26d2deeba67961f6de75734ed957e35291c75b0af9507b9a3dee08`, openapi.json info.version `8d6861316824`, base commit `116e154`. Design: canvas version 1794581312-b166 (design/review.json); screens: CMP-01 top bar and phone bar as drawn on SCR-01 (SCR-01-desktop, SCR-01-mobile), the shared empty/loading/error pattern (STATES-desktop, STATES-mobile), the site map (SITEMAP-desktop) for destination order.

## Summary
- New Next.js (App Router, TypeScript) app in `frontend/` that fits `delivery/checks.sh` as written: `npm ci`, `lint`, `typecheck`, `test`, `build`.
- Styles come only from the design system: `tokens.css` generated from `design/system/project/tokens.json` plus a synced copy of `components/bundle.css`, both drift-checked by tests. Fonts are self-hosted, so there is no Google Fonts call at runtime.
- Typed API client generated from `architecture/packages/v2-reviewed/openapi.json`. It is same-origin `/api/v1`, sends cookies, adds `X-CSRFToken` on writes and maps `{code, message}` errors. It holds no business rules.
- Local mock server built from the same openapi.json. It covers every M-1 operation, uses schema-valid sample fixtures, offers personas and error scenarios, and is reached through a Next.js rewrite on `/api/v1`.
- The frame: the desktop top bar (≥720px) and the phone bar with a menu (<720px), driven by `GET /api/v1/me`, with a visible SAMPLE DATA label. It passes axe WCAG 2.2 AA at 390px and 1440px, with focus-ring and reduced-motion checks.

## Context
- `frontend/` does not exist yet. `delivery/checks.sh` (protected) skips the frontend until `frontend/package.json` exists. After that it runs, inside `frontend/`, `npm ci --prefer-offline --no-audit --no-fund`, `npm run lint`, `npm run typecheck`, `npm test --if-present` and `npm run build`. Node v24.12.0 and npm 11.6.2 are on this machine.
- Contract: `architecture/packages/v2-reviewed/openapi.json` (OpenAPI 3.1.1, 30 operations, operationIds such as `E-ME`). Every response schema uses `additionalProperties: false`. Error bodies are `{code: string(minLength 1), message: string(minLength 1)}`. Security schemes: `Session` (cookie `sessionid`) and `Csrf` (header `X-CSRFToken`, required on every write). `sample: boolean` exists only on E-WORK-LIST items, E-WORK-ITEM and E-PROJECTS items. `unknown: boolean` appears only in non-M-1 schemas (month-end, payroll match, report).
- E-ME `GET /api/v1/me` returns 200 `{name, roles[], destinations[] ⊆ {my_work, projects, overview, assistant, setup}, startable_lines[], csrf_token}`, or 401/403/404 with the error body. It carries no `sample` field.
- M-1 operations: E-ME, E-WORK-LIST (`GET /api/v1/work`), E-WORK-ITEM (`GET /api/v1/work/{work_id}`), E-WORK-HISTORY (`GET /api/v1/work/{work_id}/history`), E-TASK-CLAIM (`POST /api/v1/tasks/{task_id}/claim`) and E-TASK-DECIDE (`POST /api/v1/tasks/{task_id}/decision`). The GETs declare 200/401/403/404. The POSTs declare 200/401/403/404/409 (stale revision)/422.
- Design system: `design/system/project/tokens.json` (color, type families/styles, spacing, radius, stroke, size, shadow, breakpoint `bp-phone` 720px and `bp-desktop` 1080px). `components/bundle.css` (501 lines) uses 49 `var(--…)` names, and no tokens.css exists in the repo. Its line 1 `@import`s Google Fonts, and its lines 491–501 are `.ds*` preview-only helpers.
- Classes the shell uses from bundle.css:
  - layout and text: `.psl`, `.psl-on-dark`, `.psl-brand`
  - top bar and phone bar: `.psl-nav`, `.psl-nav__in`, `.psl-nav__links`, `.psl-navlink` (current = `aria-current="page"`), `.psl-nav__who`, `.psl-phonebar`
  - menu: `.psl-pop`, `.psl-menu`, `.psl-menuitem`
  - labels, states and icons: `.psl-sample`, `.psl-empty`, `.psl-callout--warning`, `.psl-icon`
  - focus and reduced motion: the focus rule (lines 14–16) and the `prefers-reduced-motion` block (lines 484–488)
- Markup references: `design/system/project/components/TopNav/preview.html` and `README.md`, `Menu/README.md` and `SampleLabel/README.md`. In `design/canvas/project/SCR-01-mobile.dc.html` the phone bar shows PSL FACTORY on the left and "+ Start" on the right. The TopNav preview shows the menu variant: Menu icon, PSL FACTORY, Start.
- Existing Django sign-in is at `LOGIN_URL = '/accounts/login/'` (`config/settings.py:32`). The backend is untouched by this feature.

## Contract

### C1. Tooling and scripts (`frontend/package.json`)
- Exact-pinned dependencies with a committed `frontend/package-lock.json`.
  - Runtime: `next`, `react`, `react-dom` and `openapi-fetch`.
  - Fonts, self-hosted: `@fontsource-variable/archivo` (with the `wdth` axis, used by `font-stretch` 112% and 125%), `@fontsource/ibm-plex-sans` (400, 500, 600) and `@fontsource/ibm-plex-mono` (400, 500).
  - Dev: `typescript`, `eslint` with `eslint-config-next` and `eslint-plugin-jsx-a11y`, `openapi-typescript`, `ajv` (2020 dialect) with `ajv-formats`, `vitest`, `@testing-library/react`, `jsdom`, `axe-core`, `@playwright/test` and `@axe-core/playwright`.
  - Do not add GSAP or three.js here; they arrive with FE-M3.
- Scripts. All are non-interactive and none uses watch mode in checks.

| script | does |
|---|---|
| `dev` | `node scripts/dev.mjs`: starts the mock on 127.0.0.1:4010 and `next dev`, and stops both on exit |
| `mock` | the mock server alone |
| `gen:api` | `openapi-typescript ../architecture/packages/v2-reviewed/openapi.json -o src/api/schema.d.ts` |
| `gen:styles` | `node scripts/gen-styles.mjs` writes `src/styles/tokens.css` and `src/styles/psl-bundle.css` |
| `lint` | `eslint .` (zero warnings allowed: `--max-warnings 0`) |
| `typecheck` | `tsc --noEmit` |
| `test` | `vitest run` (unit, contract, drift, jsdom component and axe tests) |
| `test:e2e` | Playwright: builds the app, starts the mock and `next start`, then runs browser accessibility checks |
| `build` | `next build` |

- Generated files (`src/api/schema.d.ts`, `src/styles/tokens.css`, `src/styles/psl-bundle.css`) are committed, so `build` and `test` never need the generators to have run first.
- `frontend/.gitignore` covers `node_modules/`, `.next/`, `playwright-report/` and `test-results/`. Do not edit the root `.gitignore`.

### C2. Styles
- `gen-styles.mjs` emits one `:root` block with a custom property for every token. It uses `--<token name>` for color, spacing, radius, stroke, size, shadow and breakpoint, and `--font-display`, `--font-sans` and `--font-mono` from `type.families`. Values are copied verbatim.
- `psl-bundle.css` is `bundle.css` minus two parts: the line-1 Google Fonts `@import`, and the block from `/* ---------- preview-only layout helpers` to the end of the file. Every other byte is unchanged.
- `app/layout.tsx` imports, in order, the three fontsource CSS files, `tokens.css`, `psl-bundle.css` and `shell.css`.
- `shell.css` is the only hand-written stylesheet. It may contain only these:
  - (a) Show the top bar at `min-width: 720px` and the phone bar below it.
  - (b) Make the phone-bar menu `<button>` match `.psl-phonebar a`: `color: var(--on-strong)`, transparent background, no border, 44px minimum size, inline-flex.
  - (c) Position the phone menu panel under the bar.
  - (d) The skip link: visually hidden until focused.
  - (e) Page layout: `background: var(--steel)`, content max-width 1320px, gutters `var(--space-6)` on desktop and 16px below 720px.
  - (f) `overflow: hidden; text-overflow: ellipsis` on `.psl-nav__who` between 720 and 1079px.
  - It uses token variables only, with no literal colours, and does not restyle any bundle class.
- `<body class="psl">`, `<html lang="en">`.

### C3. API client (`frontend/src/api/`)
- `schema.d.ts` is generated. `client.ts` exports `api`, an `openapi-fetch` client typed by `paths`.
  - Base URL is `''` (same origin). The paths already start with `/api/v1`.
  - Requests use `credentials: 'include'`.
- `errors.ts` exports a class `ApiError extends Error` with `{status: number, kind, code: string, message: string}`.

| response | kind | code / message |
|---|---|---|
| 401 | `unauthenticated` | from body |
| 403 | `forbidden` | from body |
| 404 | `not_found` | from body |
| 409 | `stale` | from body |
| 422 | `invalid` | from body |
| other ≥400 | `server` | from body if it parses, else `code: "unexpected_response"` |
| fetch rejects / non-JSON | `network` | `code: "network_error"` |
| body missing or not `{code,message}` strings | as per status | `code: "unexpected_response"`, message `"Something went wrong."` |

- `call(op)` helper: it returns `data` on 2xx and throws `ApiError` otherwise. Feature code never reads raw `Response`.
- CSRF:
  - `setCsrfToken(token)` stores the token in a module variable only, never in localStorage, sessionStorage or a cookie.
  - Middleware adds `X-CSRFToken: <token>` to every POST, PUT, PATCH and DELETE, and never to a GET.
  - A write attempted before a token is set throws `ApiError{status: 0, kind: 'unauthenticated', code: 'csrf_unavailable'}` without sending a request.
- No retries, no caching of writes, no business logic. Do not interpret `destinations` or `roles` beyond rendering.

### C4. Mock server (`frontend/mock/`)
- `server.mjs` uses `node:http`, binds to `127.0.0.1` only and uses port `MOCK_PORT` (default 4010). It refuses to start when `NODE_ENV=production`.
- Routes are built by reading `openapi.json` paths and operationIds. Path templates are matched, so `/api/v1/work/{work_id}` is one route.
- Persona: cookie `psl_mock_persona`. The fixtures in `fixtures/me.<persona>.json` validate against the E-ME 200 schema.

| persona (default `finance_lead`) | name | roles | destinations |
|---|---|---|---|
| `finance_lead` | Ada Okafor | `["Finance Lead"]` | all five |
| `pm` | Tunde Bello | `["PM"]` | `my_work, projects, assistant` |
| `none` | Sample Person | `["Staff"]` | `[]` |

  Every persona has `csrf_token: "mock-csrf-<persona>"`.
- M-1 operations return deterministic fixtures from `fixtures/<operationId>.json`. Every item or record carries `sample: true` where the schema has `sample`. Unknown amounts and dates use `unknown: true` with no value wherever a schema has `unknown`.
- Scenario: cookie `psl_mock_scenario` or header `X-Mock-Scenario` takes a value in `401|403|404|409|422`. If the operation declares that status, the server returns it with a schema-valid body, for example `{code: "not_signed_in", message: "Sign in to continue."}`. If not declared, the scenario is ignored.
- CSRF check: a write without `X-CSRFToken` equal to the current persona's `csrf_token` gets 403 `{code: "csrf_failed", message: "Your session check failed. Reload and try again."}`.
- Operations outside M-1 return 501 `{code: "not_mocked", message: "Not available in the mock yet."}`.
- Every response is `application/json`. Nothing outside `frontend/mock/` and `frontend/scripts/` imports from `frontend/mock/`.
- `next.config` rewrites `/api/v1/:path*` to `${API_ORIGIN}/api/v1/:path*`, where `API_ORIGIN` defaults to `http://127.0.0.1:4010`. FE-CONNECT-1 later points `API_ORIGIN` at Django without code change.

### C5. Frame and states (`frontend/src/app/`, `frontend/src/shell/`)
- Routes: `/my-work`, `/projects`, `/overview`, `/assistant`, `/setup` map to `my_work`, `projects`, `overview`, `assistant`, `setup`. The display order is My work, Projects, Overview, Assistant, Setup. Labels are exactly those words.
- `/` sends the person to the first destination they have, in that order.
- `AppShell` (client component, in `app/layout.tsx`):
  - It calls `GET /api/v1/me` once per page load through `call()`.
  - On success it calls `setCsrfToken`.
  - It provides `me` through React context for later tasks.
- `TopNav` (React port of CMP-01, desktop):
  - Uses `<nav class="psl-nav psl-on-dark" aria-label="Main">` with the brand `PSL FACTORY`.
  - Renders one `<a class="psl-navlink">` per destination in `me.destinations`, using Next `Link`. The current route has `aria-current="page"`.
  - Then the SAMPLE DATA label, then `<span class="psl-nav__who">{name} · {roles.join(', ')}</span>`.
  - There is no Start work button, bell or account menu.
- `PhoneBar` (<720px):
  - `<header class="psl-phonebar psl-on-dark">` contains a `<button type="button" aria-label="Menu" aria-expanded aria-controls="phone-menu">` with the menu icon, then `PSL FACTORY`, then the SAMPLE DATA label. There is no Start.
  - Open: `<nav id="phone-menu" aria-label="Main" class="psl-pop psl-menu">`. It holds the person's name and roles as a first non-interactive line, then one `.psl-menuitem` link per destination, with `aria-current="page"` on the current one.
  - Esc and choosing a link both close the menu. Esc returns focus to the Menu button. The menu opens with no animation.
- SAMPLE DATA label: `<span class="psl-sample">SAMPLE DATA</span>` is shown whenever `NEXT_PUBLIC_API_MODE` is not exactly `live`. The default is mock, so the label is shown.
- Skip link "Skip to main content" is the first focusable element and targets `<main id="main" tabindex="-1">`.
- Document title is `<Destination> · PSL Factory`.
- States of the frame:

| state | bar | main |
|---|---|---|
| loading (`/me` pending) | brand and SAMPLE DATA only, no links, no name | STATES loading pattern: grey bars + "Loading…" with `role="status"` |
| success, destination built later | full bar | `<h1>` page title, then `.psl-empty` with `<h3>{Destination}</h3><p>This page is not built yet. It arrives in a later release.</p>` |
| success, `destinations: []` | brand, SAMPLE DATA, name | `.psl-empty`: "No sections are open to your role yet." / "Ask a Lead or Admin to check your roles." |
| success, route not in `destinations` | full bar, no `aria-current` | `.psl-empty`: "This section isn't open to your role." + link to the first destination (if any). The page content is not rendered. |
| 401 | brand and SAMPLE DATA | `.psl-callout--warning`: "You're signed out." + link "Sign in" to `${NEXT_PUBLIC_SIGN_IN_URL ?? '/accounts/login/'}?next=<current path, URL-encoded>` |
| 403 | brand and SAMPLE DATA | `.psl-callout--warning`: "Your account can't use PSL Factory." + the error `message` |
| 404, server, network | brand and SAMPLE DATA | STATES error pattern: "We couldn't load your account. Your work is safe; nothing was changed." · "Reference {code} for support." · button "Try again" re-calls `/me` |

Fixture example (`fixtures/me.pm.json`):
```json
{"name":"Tunde Bello","roles":["PM"],"destinations":["my_work","projects","assistant"],"startable_lines":["Weekly client update"],"csrf_token":"mock-csrf-pm"}
```

## Lanes
- **Frontend lane (builder)** owns everything under `frontend/`.
- **Backend lane**: no work in this feature. `apps/`, `config/` and `templates/` are untouched.
- **Integration owner**: no work. `API_ORIGIN` and `NEXT_PUBLIC_API_MODE` are the seam FE-CONNECT-1 uses.
- **Read-only inputs**, which this lane does not change:
  - `architecture/packages/v2-reviewed/**` (architecture)
  - `design/**` (design; the generated copies live in `frontend/src/styles/`)
  - `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json` (protected)
  - the root `.gitignore`

## Acceptance criteria
1. The gate passes with the frontend present — verify: from the feature worktree, `bash <main>/delivery/checks.sh` exits 0 and its log shows "== frontend: install, lint, typecheck, test, build" with every step succeeding. `frontend/package-lock.json` is committed, and every dependency in `package.json` is an exact version.
2. Styles have a single source — verify: `npm test` includes a drift test that does three things. It regenerates tokens.css and psl-bundle.css in memory and asserts they equal the committed files. It asserts every `var(--x)` in psl-bundle.css is defined in tokens.css. It asserts psl-bundle.css contains no `fonts.googleapis.com` and no `.ds-` selector. `grep -rnE '#[0-9A-Fa-f]{3,6}\b' frontend/src --include=*.css --include=*.tsx` matches only inside `src/styles/tokens.css` and `src/styles/psl-bundle.css`.
3. No runtime font call — verify: in `npm run test:e2e`, Playwright records zero requests to `fonts.googleapis.com` or `fonts.gstatic.com` when it loads `/my-work`.
4. The client is generated and current — verify: a vitest drift test runs openapi-typescript on openapi.json and asserts the output equals the committed `src/api/schema.d.ts`. `npm run typecheck` passes with `api.GET('/api/v1/me')` typed, and a deliberate wrong-path call in a `// @ts-expect-error` test line keeps typecheck green.
5. Error mapping — verify: vitest unit tests with a stubbed `fetch` cover each case below.
   - Each status 401, 403, 404, 409 and 422 with a valid body gives an `ApiError` with the kind from C3 and the body's `code` and `message`.
   - 500 with an HTML body gives `kind 'server'` and `code 'unexpected_response'`.
   - 403 with `{}` gives `kind 'forbidden'` and `code 'unexpected_response'`.
   - A rejected fetch gives `kind 'network'`.
   - Every request was made with `credentials: 'include'` and a same-origin URL starting `/api/v1/`.
6. CSRF header — verify: unit tests check each case below.
   - After `setCsrfToken('t1')`, POST and PUT carry `X-CSRFToken: t1`, and GET carries no `X-CSRFToken`.
   - Before any token is set, a POST throws `code 'csrf_unavailable'` and the stub records zero calls.
   - `grep -rn "localStorage\|sessionStorage\|document.cookie" frontend/src` returns nothing.
7. The mock matches the contract — verify: a vitest contract test starts the mock on a random port. Every mock response must validate with Ajv 2020 against the openapi.json schema for that operation and status. The test exercises:
   - for each M-1 operation, the success response for each persona, plus each declared error status via `X-Mock-Scenario`
   - a write without `X-CSRFToken`, which gets 403 `csrf_failed`
   - a write with another persona's token, which gets 403 `csrf_failed`
   - a non-M-1 operation, which gets 501 `not_mocked`

   The test also asserts that every E-WORK-LIST item and the E-WORK-ITEM record have `sample: true`, and that the server refuses to start with `NODE_ENV=production`.
8. Navigation follows `/me` — verify: run `npm run dev`, open `http://localhost:3000/` at 1440px wide with no cookies.
   - The page redirects to `/my-work`.
   - The top bar shows PSL FACTORY, My work (underlined orange, `aria-current="page"`), Projects, Overview, Assistant, Setup, SAMPLE DATA and "Ada Okafor · Finance Lead".
   - With cookie `psl_mock_persona=pm` it shows only My work, Projects and Assistant, and "Tunde Bello · PM". `/overview` shows "This section isn't open to your role." and a My work link.
   - jsdom component tests cover the same three personas.
9. Phone bar — verify: at 390×844 the desktop nav is hidden (not in the accessibility tree) and the phone bar shows Menu, PSL FACTORY and SAMPLE DATA. The menu follows the disclosure pattern:
   - Activating Menu sets `aria-expanded="true"` and shows the destinations with the current one marked.
   - Esc closes the menu and focus returns to Menu.
   - Choosing Projects navigates to `/projects` and closes the menu.
   - All targets are ≥44×44px.
   - There is no horizontal scroll at 390, 768 or 1440px (`document.documentElement.scrollWidth <= innerWidth`).
10. Frame states — verify: with cookie `psl_mock_scenario` set to each value, the page shows the main content from the C5 table.
    - `401`: "You're signed out." and a Sign in link whose href is `/accounts/login/?next=%2Fmy-work`. No destinations are shown.
    - `403`: the forbidden callout.
    - `404`: the error pattern with "Reference" and the error code. Pressing Try again after clearing the cookie loads the full bar.
    - Persona `none`: "No sections are open to your role yet."
    - While `/me` is delayed, a `role="status"` loading message shows and no destination links are shown.

    jsdom tests cover these states, and Playwright covers 401 and loading.
11. Accessibility (A-ACCESSIBILITY) — verify: `npm run test:e2e` runs `@axe-core/playwright` with tags `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa` and reports zero violations on each of these:
    - `/my-work` (finance_lead) at 1440×900
    - `/my-work` (finance_lead) at 390×844, menu closed and open
    - `/overview` as `pm`
    - the 401 state

    The same run asserts the following:
    - Tabbing from page load first focuses "Skip to main content", and activating it moves focus to `main`.
    - Each nav link and the Menu button, when focused by keyboard, has a computed `outline-style: solid` and `outline-width: 2px`, with `outline-color` equal to `--focus-on-strong` on the ink bar.
    - With `reducedMotion: 'reduce'`, no element in the frame has a non-zero `transition-duration` or a running animation.

    `npm test` also runs `axe-core` on the rendered TopNav and PhoneBar in jsdom (colour contrast excluded there). If the Playwright browser cannot be installed in the gate environment, `build.md` records the exact command, browser version and output of a local `npx playwright install chromium && npm run test:e2e` run. It must not be left unrun.
12. Sample labelling (R-SAMPLE) — verify: SAMPLE DATA (`.psl-sample`) is visible in every frame state at both widths with default env. With `NEXT_PUBLIC_API_MODE=live npm run build && npm start` (mock still behind the rewrite), the label is absent. That is the only way to hide it.
13. Mock code stays out of the app — verify: after `npm run build`, `grep -rl "Tunde Bello\|mock-csrf\|psl_mock_scenario" frontend/.next/static` returns nothing. `grep -rn "from ['\"].*mock/" frontend/src` returns nothing.
14. No out-of-scope controls — verify: the rendered frame contains no Start work or "+ Start" control, no bell, no account menu and no sign-out. `package.json` has no `gsap` or `three`.

## Out of scope
- The My work page, queues, toolbar and rows (FE-MYWORK); the work item, stations and history (FE-WORKITEM); claim and decide UI (FE-DECIDE). The client and mock cover their endpoints, but no screen for them is built.
- Sign-in screen SCR-17, sign-out, the account menu and any session or login mechanics: D-AUTH belongs to the backend developer. The shell only links to the configured sign-in URL on 401.
- The Start work split button, "+ Start" on the phone bar and the drawer (FE-M2). Omit them; do not ship disabled ones.
- The notification bell and centre (FE-M4). The factory floor, GSAP and three.js (FE-M3).
- Porting any other design component to React, or restyling or "fixing" bundle.css. Design changes go to the design owner.
- Any change to openapi.json, the backend (`apps/`, `config/`, T-FOUNDATION), the root `.gitignore` or the protected delivery files.
- Deployment, hosting, Docker or CI configuration (D-HOSTING is open). Real AI or alert providers.
- A Prism, MSW or other mock framework, or a state-management or UI library. Plain `node:http` plus fixtures is enough.
- Client-side retries, offline support, i18n and dark mode.

## Assumptions
- Mock is a separate `node:http` process behind a Next.js rewrite, not MSW and not Next route handlers. That keeps the app's `/api/v1` path identical for mock and Django, so FE-CONNECT-1 only changes `API_ORIGIN`.
- openapi-typescript plus openapi-fetch for the client. These are the smallest typed-from-schema pair that supports OpenAPI 3.1 and adds no runtime framework.
- Fonts are self-hosted with fontsource and bundle.css's `@import` is stripped from the synced copy. This avoids a third-party request on every load and network use during build. Same families, axes and weights, with no visual change.
- The SAMPLE DATA label is driven by `NEXT_PUBLIC_API_MODE` (default: label shown) because E-ME has no `sample` field. Fail-safe: only an explicit `live` hides it. The backend may later add a per-session sample flag, which is a contract question for FE-CONNECT-1.
- Who text renders `roles` as given (`name · roles.join(', ')`). The schema says roles are strings without labels, and the backend may return codes. FE-CONNECT-1 revisits this; the shell maps nothing.
- 401 links to `/accounts/login/?next=…` (existing Django `LOGIN_URL`, `config/settings.py:32`), overridable by `NEXT_PUBLIC_SIGN_IN_URL`. The URL is not decided here; it is the D-AUTH working assumption's same-origin Django sign-in.
- Phone navigation is a menu-button disclosure using `.psl-pop .psl-menu .psl-menuitem`. CMP-01 lists the states "collapsed to a menu button below 720px, menu open", but no canvas board draws the open menu. The person's name sits at the top of the open menu because the phone bar has no room for it.
- Copy for the placeholder, no-sections, not-open, 401 and 403 states is new. No board draws these states. The wording follows the README content rules and the STATES pattern; the approver may route it to the design owner.
- Persona names (Ada Okafor, Tunde Bello) and role labels are taken from the TopNav preview. The PM's destination set follows the preview ("A PM sees only…").
- Persona and scenario selection uses `psl_mock_*` cookies, so a browser session and Playwright can switch them without code. Headers are also accepted for the contract tests.
- `npm test` runs jsdom-only tests so checks.sh stays deterministic without a browser download. Browser axe, focus and motion checks live in `test:e2e`, with the fallback recording the readiness note requires.
- A destination's route is shown as not open when it is missing from `/me.destinations`. This is presentation only; the API enforces access per record.
