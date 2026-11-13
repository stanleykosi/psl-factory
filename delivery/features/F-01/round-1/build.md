STATUS: READY
COMMIT: f6e9a9ecdc299700381927a13d66386138d83e5c
BUILDER: builder
LANE: full

## Summary
- New Next.js 16 (App Router, TypeScript) app in `frontend/`. `delivery/checks.sh` passes from the worktree: Django check, npm ci, lint, typecheck, 87 vitest tests and the production build.
- The frame calls `GET /api/v1/me` once through the generated `openapi-fetch` client. It renders the CMP-01 top bar (720px and wider) or the phone bar with a menu disclosure (below 720px), shows only the person's destinations and always shows SAMPLE DATA unless `NEXT_PUBLIC_API_MODE=live`.
- A local `node:http` contract mock built from openapi.json serves all six M-1 operations. It offers 3 personas, 401/403/404/409/422 scenarios and a CSRF check, and returns 501 for everything else. Every response validates against the schema (Ajv 2020, strict).
- Styles come from the design system only: `tokens.css` and `psl-bundle.css` are generated and drift-tested, plus a small `shell.css`. Fonts are self-hosted, with no Google Fonts call.
- Browser accessibility run (`npm run test:e2e`, Playwright + axe, WCAG 2.2 AA tags): 11/11 passed. It ran locally because it needs a downloaded browser (see Validation).
- Not pushed: the coordinator's prompt forbids pushing, so COMMIT is the local head of `t-frontend-shell-nextjs-app`.

## Changes
All under `frontend/` (52 files, one commit `f6e9a9e`):
- `package.json` / `package-lock.json`: exact-pinned dependencies (the versions from the coordinator's list, plus `@types/node 24.19.2`, `@types/react(-dom) 19.3.0`). Scripts: `dev`, `mock`, `gen:api`, `gen:styles`, `lint` (`--max-warnings 0`), `typecheck`, `test`, `test:e2e`, `build`, `start`. No gsap or three.
- `.gitignore`: node_modules, .next, playwright-report, test-results, tsbuildinfo, `next-env.d.ts`, and `AGENTS.md` (`next dev` writes an agent-rules file there; it is tool output, not project content).
- `tsconfig.json`, `next.config.ts` (rewrites `/api/v1/:path*` to `${API_ORIGIN ?? http://127.0.0.1:4010}`), `eslint.config.mjs` (next core-web-vitals + typescript + the full jsx-a11y recommended rules), `vitest.config.ts`, `playwright.config.ts` (app on 3101, mock on 3102).
- `scripts/gen-styles.mjs`: generates `src/styles/tokens.css` (one `:root` var per token, verbatim) and `src/styles/psl-bundle.css` (bundle.css minus line 1 and the preview helpers). `scripts/dev.mjs` starts the mock and `next dev` together and stops both.
- `src/api/schema.d.ts` (generated), `client.ts` (`api`, `call`, `setCsrfToken`, CSRF middleware), `errors.ts` (`ApiError`, status-to-kind mapping), `types.ts`.
- `mock/server.mjs` and `mock/fixtures/*.json` (3 `me.<persona>` files and 5 operation fixtures; every work item has `sample: true`).
- `src/app/layout.tsx`, `page.tsx` (redirects to the first destination) and five route pages with `<Destination> · PSL Factory` titles.
- `src/shell/`: `AppShell` (the /me states and the `useMe` context), `TopNav`, `PhoneBar`, `FrameStates`, `DestinationPage`, `HomeRedirect`, `destinations.ts`, `sample.ts`, `icons.tsx`, `SampleLabel.tsx`.
- `src/styles/fonts.css`, `shell.css`.
- `tests/` (vitest): styles drift, schema drift, client types, client unit tests, mock contract and jsdom shell tests with axe. `e2e/frame.spec.ts` (Playwright).

Deviations from the spec's letter, each for a stated reason (reviewers please judge):
1. **Archivo font name.** `@fontsource-variable/archivo` registers the family as "Archivo Variable", but tokens.json asks for `Archivo`. `src/styles/fonts.css` declares the same package woff2 files (wdth+wght, latin and latin-ext) under the name `Archivo`. `layout.tsx` imports fonts.css, then the Plex Sans 400/500/600 and Plex Mono 400/500 fontsource CSS (five files, not "three"), then tokens, bundle and shell. The browser test asserts `document.fonts.check('800 17px Archivo')` and zero requests to Google Fonts.
2. **shell.css goes slightly beyond the (a)–(f) list:**
   - `#phone-menu .psl-menuitem { min-height: var(--control-md) }`: criterion 9 requires every target to be at least 44px, and the tokens.json size note says the same for phone. Bundle menu items are 40px.
   - `.shell-topbar .psl-nav__in { max-width: 1320px; margin: 0 auto }`: the approved SCR-01 and STATES boards centre the bar content at 1320px together with the page. Without it, the bar and the page do not line up at 1440px.
   - Small layout classes for the page title (SCR-01 h1: display font, 112%, 800, 36px desktop and 26px phone), the loading panel, the error stack and the who-line at the top of the phone menu.
   - Token variables only. The only literal values are sizes copied from the boards; there are no colours.
3. **TopNav inline style** `{marginLeft:'auto', flex:'none'}` on the SAMPLE DATA wrapper, like the TopNav preview's inline span. Without `flex:none`, the label wrapped to two lines at 768px.
4. **Phone menu panel sits outside the dark header** (a sibling of `header.psl-phonebar.psl-on-dark`), so menu items get the blue `--focus` ring on the white panel instead of an invisible white one. The e2e test asserts this.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Gate passes: `cd worktree && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0. The log shows "== frontend: install, lint, typecheck, test, build", then npm ci (449 packages), lint clean, tsc clean, "Test Files 6 passed (6) / Tests 87 passed (87)" and "Compiled successfully". The lockfile is committed, and every package.json version is exact.
2. [x] Single style source: `tests/styles-drift.test.ts` regenerates both files and compares them to the committed copies. It also checks that bundle = line 1 + psl-bundle.css + the preview tail exactly, that all `var(--x)` names used are defined, that there is no googleapis and no `.ds` selector, and that shell.css has no colours. The spec's hex grep (globs quoted for zsh) has no matches outside tokens.css and psl-bundle.css.
3. [x] No runtime font call: e2e test 1 records zero `fonts.googleapis.com`/`fonts.gstatic.com` requests on `/` → `/my-work`. The fonts come from `.next/static/media`.
4. [x] Client current: `tests/api-schema-drift.test.ts` runs the openapi-typescript CLI into a temp file and compares it byte for byte. `tests/client-types.test.ts` has `call(api.GET('/api/v1/me'))` typed as `Me`, and a `// @ts-expect-error` wrong path. `tsc --noEmit` is green, so that line is a real type error.
5. [x] Error mapping: `tests/client.test.ts` covers:
   - 401/403/404/409/422, giving the kind plus the body's code and message
   - 500 with HTML, giving `server`/`unexpected_response`
   - 503 with a body, giving `server`
   - 403 `{}`, giving `forbidden`/`unexpected_response`
   - a rejected fetch, giving `network`
   - a non-JSON 2xx, giving `network`
   - that every request is same-origin `/api/v1/` with `credentials: 'include'`
6. [x] CSRF: after `setCsrfToken('t1')`, POST and PUT carry `X-CSRFToken: t1` and GET carries none. A POST before any token throws `csrf_unavailable` with zero fetch calls. The `localStorage|sessionStorage|document.cookie` grep over `src` is empty.
7. [x] Mock contract: `tests/mock-contract.test.ts` (47 tests) starts the mock on a random port. It covers:
   - each M-1 operation × 3 personas, and each declared error status via `X-Mock-Scenario`, all Ajv-2020-validated
   - a write without the token, and a write with another persona's token: both 403 `csrf_failed`
   - E-LINES: 501 `not_mocked`
   - `sample: true` on all list items and the item record
   - `NODE_ENV=production` exits 1 with "refuses to start"
8. [x] Navigation follows /me:
   - `npm run dev -- -p 3101` (mock on 3102): a browser at 1440 opening `/` was redirected to `/my-work`. Links were My work..Setup, with `aria-current` on My work, "SAMPLE DATA" and "Ada Okafor · Finance Lead". The e2e test asserts a 3px `rgb(200, 64, 28)` (signal) underline.
   - With `psl_mock_persona=pm`: My work, Projects and Assistant only. `/overview` shows "This section isn’t open to your role." with a "Go to My work" link.
   - jsdom tests cover finance_lead, pm and none.
   - I used port 3101 instead of 3000, as the coordinator instructed.
9. [x] Phone bar (e2e at 390×844):
   - With the menu closed there is no `navigation "Main"` in the accessibility tree. Menu, PSL FACTORY and SAMPLE DATA are visible.
   - Menu sets `aria-expanded="true"`; the 5 links show with My work current.
   - Esc closes the menu and focuses Menu. Choosing Projects goes to `/projects` and closes the menu.
   - Menu and every menu link are at least 44×44.
   - `scrollWidth <= innerWidth` at 390, 768 and 1440. At 768 the bar's own `scrollWidth <= clientWidth` and SAMPLE DATA stays on one line.
10. [x] Frame states:
    - Cookie `401`: "You’re signed out." with a link to `/accounts/login/?next=%2Fmy-work` and no destination links.
    - `403`: the forbidden callout.
    - `404`: the error callout, "Reference not_found for support." Try again after clearing the cookie loads the 5-link bar.
    - Persona none: "No sections are open to your role yet."
    - Delayed /me (Playwright route gate): a `role=status` "Loading…" and no links.
    - jsdom covers all of these, plus 500 and network.
11. [x] A-ACCESSIBILITY:
    - axe with `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa` found 0 violations on `/my-work` 1440, `/my-work` 390 with the menu closed and open, `/overview` as pm, 401 at both widths, and the 403/none and 404 states.
    - Tab 1 focuses "Skip to main content"; Enter focuses `main`.
    - Each top-bar link and the Menu button show a 2px solid `rgb(255, 255, 255)` outline, equal to computed `--focus-on-strong`.
    - With `reducedMotion: 'reduce'`, the loading and loaded frames have zero non-zero `transition-duration` and zero running animations.
    - jsdom axe (contrast excluded) ran on the TopNav and PhoneBar with the menu open, and on the 401 frame.
12. [x] R-SAMPLE:
    - With the default env, `.psl-sample` shows in every state tested (loaded, loading, 401, 403, 404, none) at 1440 and 390.
    - `NEXT_PUBLIC_API_MODE=live API_ORIGIN=http://127.0.0.1:3102 next build && next start -p 3101`, with the mock still behind the rewrite, gave `{"live_sample_labels_1440":0,"live_sample_labels_390":0}` once "Ada Okafor · Finance Lead" had loaded. The live build's `.next/static` contains no "SAMPLE DATA".
13. [x] Mock stays out: after `npm run build`, `grep -rl "Tunde Bello\|mock-csrf\|psl_mock_scenario" .next/static` is empty, and `grep -rn "from ['\"].*mock/" src` is empty.
14. [x] No out-of-scope controls: the jsdom test asserts the only button is Menu, with no "Start", "Sign out" or "Notifications" text even with the menu open. There is no gsap or three in package.json.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (from the worktree): exit 0. Log: `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/checks.log`.
- `npm test`: 6 files, 87 tests passed.
- **Browser run (not part of checks.sh).** checks.sh runs no browser, so the Playwright run was done locally:
  - Command: `PLAYWRIGHT_BROWSERS_PATH=<session scratchpad>/ms-playwright npx playwright install --only-shell chromium` (Chromium headless shell, revision 1254, version 158.0.8127.18), then `npm run test:e2e`.
  - Result: "11 passed (20.2s)". The suite builds the app, starts the mock on 3102 and runs `next start` on 3101.
  - The temporary browser was deleted afterwards, as instructed. To re-run: `npx playwright install --only-shell chromium && npm run test:e2e`. The machine cache has revision 1243, which is too old for @playwright/test 1.65.0.
- Manual checks: `npm run dev -- -p 3101` and the live-mode build were driven by short Playwright scripts (results above). Every server I started was stopped, and nothing is listening on 3101 or 3102.
- Install note: npm warns `EBADENGINE` because jsdom 31.0.1 wants Node ≥24.15 and this machine has 24.12.0. All jsdom tests pass. Upgrading Node to ≥24.15 removes the warning.

## Notes for reviewers and next tasks
- **The 768px bar is tight.** With all five destinations (finance_lead) at 768–~900px, the who-text ellipsis per (f) squeezes the name down to nothing. The name stays in the DOM and in the phone menu, but is not visible on the bar at that width. There is no horizontal scroll. Showing the name there needs a design decision (wrap, as the boards' `flex-wrap` does, or a shorter who-line). That is the design owner's call.
- **Rewrites are fixed at build time.** Next resolves `rewrites()` at `next build`, so `API_ORIGIN` must be set for the build (or dev) that will serve it. `next start` alone does not re-read it. This matters for FE-CONNECT-1.
- Copy in the placeholder, not-open, no-sections, 401, 403 and error states follows the spec's C5 table verbatim. The mock's scenario messages and fixture contents are sample text.
- `frontend/AGENTS.md` is regenerated by `next dev` and is git-ignored. Its text tells agents to read Next's bundled docs; I treated it as tool output, not instructions.

## Blocked
None.
