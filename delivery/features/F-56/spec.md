# Remove the Django embed: the shell always draws our own frame, and the proxy forwards only the API and file downloads

> Tasks: FE-CONNECT-1 (part a only). Architecture: package v8 (OpenAPI 1.22.0; D-API-STYLE r3, D-AUTH r3, D-172). Design: approved canvas as already drawn by the shell in mock mode, no design change; screens: SCR-FRAME states only (loading, signed-out, forbidden, error, no-sections, ready), unchanged.

## Summary
- Delete `FactoryDesk` and its branch in `AppShell`, so the frame is always our own, whatever `/me` returns.
- `next.config.ts` stops proxying Django pages: no catch-all `fallback`, no `/accounts`, `/factory-forms`, `/static`, `/factory-assets` rewrites, no `NEXT_PUBLIC_FACTORY_ORIGIN`.
- The proxy forwards exactly `/api/v1/*` plus the six authenticated download routes (and the mock-only `/__mock/reset`).
- A unit test pins the rewrite set (exact, no catch-all, no shadowing of app routes).
- Frame mismatches with live `/me` (v7 shape, role words) stay for F-57; mock mode keeps working.

## Context
Main added the embed in the range `d6413009..9bac3109` (`git diff d6413009..9bac3109 -- frontend`, run for this spec). What bears on this feature:
- `frontend/src/shell/FactoryDesk.tsx` (new there, 25 lines): renders `<psl-work-client>` plus `/factory-assets/work-client.js`, and links to `django_url` and `/factory-forms...`.
- `frontend/src/shell/AppShell.tsx`: line 19 `import { FactoryDesk }`; lines ~73-76 the `native` constant (true when `/me` carries `work_desk_url`); line ~76 `me && !native ? visibleDestinations(...) : []`; line ~131 `if (native) return <FactoryDesk .../>`. The rest of the diff there is nothing else.
- `frontend/next.config.ts`: `env: { NEXT_PUBLIC_FACTORY_ORIGIN }`, five `beforeFiles` rewrites (`/api/v1`, `/factory-assets/work-client.js`, `/accounts/:path*`, `/factory-forms/:path*`, `/static/:path*`), the mock-only `/__mock/reset`, and `fallback: /:path((?!__mock(?:/|$)).*)` to the API origin. The fallback sends every unknown path to Django, so with the API-only deployment an unknown page shows a JSON 404 (`page_retired`).
- Other frontend changes in the range do not touch the shell or the proxy: `useStartWork.ts` (accepts 200 or 201 with `work_id`), `vitest.config.ts` (`pool: 'threads'`), `tests/source-files.ts` (helpers `sourceFiles`, `matchingSources`, reusable for a "no reference to removed pieces" test), `assistant-dictation`, `clients`, `payments`, `weekly` and other tests. None references `FactoryDesk`, `factory-forms`, `factory-assets` or `work_desk_url` (grep of `src`, `tests`, `e2e`, `mock`, `delivery/checks.sh` finds only `AppShell.tsx` and `FactoryDesk.tsx`).
- `frontend/src/shell/FrameStates.tsx` `SignedOutState` links to `SIGN_IN_URL` (`frontend/src/shell/sample.ts`, default `/accounts/login/`, overridable by `NEXT_PUBLIC_SIGN_IN_URL`). Removing the `/accounts` rewrite means that link reaches a Next 404 until wave 1 (SCR-17, D-172). Accepted; do not change it here.
- Backend routes: `config/urls.py` lines 27-37 define the six download routes (below). With `PSL_DJANGO_UI=0` the root URLconf is `config.urls` (`config/settings.py` lines 34-35), where every legacy page answers a JSON 404 `page_retired`.
- App pages that could be shadowed: `frontend/src/app/work/[id]/...` (`(item)`, `history`, `decide`, `outcome`, `respond`) and `projects/[caseId]/...` (`(tabs)`, `[tab]`, `documents/[documentId]`). There is no `src/app/cases`.

## Contract
No new endpoint, payload, error or permission. Django still enforces session, permission and tenant on every download; the proxy adds no authority and must not widen the exposed path set.

### Proxy rewrites (`frontend/next.config.ts`)
Keep, unchanged: `allowedDevOrigins: ['127.0.0.1']`; `{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }` in `beforeFiles`; `/__mock/reset` only when `NEXT_PUBLIC_MOCK_DEMO === '1'` and `NODE_ENV !== 'production'`. Remove: the `env` entry and the four Django rewrites and the `fallback`.

Add exactly these six, in `afterFiles` (so a real page always wins over a rewrite), each GET path forwarded to the same path on `apiOrigin`. Integer parameters use `(\\d+)`, UUIDs use the canonical 8-4-4-4-12 hex pattern, `kind` and `file_kind` use one segment (`:kind`), with no trailing wildcard:

| Django route name | Source pattern |
|---|---|
| `case_upload_download` | `/cases/:case(<uuid>)/files/:upload(\\d+)` (also `/` suffix) |
| `design_template_download` | `/projects/:case(<uuid>)/templates/:template(\\d+)/file` |
| `rfp_intake_attachment` | `/cases/:case(<uuid>)/rfp/intake/:intake(\\d+)/attachment` |
| `factory_invoice_milestone_proof` | `/work/:work(\\d+)/invoice-proof/:proof(\\d+)` |
| `finance_bank_proof` | `/cases/:case(<uuid>)/finance/invoices/:issue(\\d+)/payments/:receipt(\\d+)/proof/:kind` |
| `design_reminder_download` | `/cases/:case(<uuid>)/finance/reminders/:issue(\\d+)/drafts/:draft(\\d+)/:file_kind` |

Django's routes end in `/`. Next normalises a trailing slash on source patterns; the builder verifies, with a real request through `next dev`, that the Django URL with its trailing slash is reached (Django does not redirect with `APPEND_SLASH` for API-only if the slash is dropped; check, and if the slash is lost, set the destination explicitly with the trailing `/`). Not proxied: `finance/followup-inbox/...` (inbound webhook), `health/`, any `/accounts`, `/static`, or other Django page.

To make the set testable, `next.config.ts` keeps `export default nextConfig` and the test calls `await nextConfig.rewrites()` with `API_ORIGIN` set (the function already reads env at call time).

### Shell states (no change in what is drawn)
`AppShell` reads `/me` and draws, whatever the payload shape: loading (`LoadingState`), 401 signed-out (`SignedOutState`), 403 (`ForbiddenState`), other error (`LoadErrorState` with retry), no destinations (`NoSectionsState`), ready (nav, bell, children). A `/me` body that carries `work_desk_url` or `django_url` is not special: it goes through `visibleDestinations` like any other. Where the live `/me` does not match the frame's expected shape, the result may be wrong or fall into the error or no-sections state; that is F-57's and is not fixed here.

Fixture examples: the existing mock `/me` fixtures under `frontend/mock/fixtures` and `src/app/frame-fixtures` stay as they are.

## Lanes
- Frontend lane: `frontend/src/shell/AppShell.tsx`, `frontend/src/shell/FactoryDesk.tsx` (delete), `frontend/next.config.ts`, new `frontend/tests/next-config.test.ts`, and a new or extended shell test (below).
- Backend lane: none. No file under `apps/`, `config/`, `legacy_ui/` changes.
- Integration owner: runs the live-API check below and records its output; owns no files.
- Shared files: none. Do not touch `frontend/src/shell/sample.ts`, `FrameStates.tsx`, `frontend/mock/**`, `frontend/scripts/dev.mjs`, or any protected path (`delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`).

## Acceptance criteria
1. `frontend/src/shell/FactoryDesk.tsx` no longer exists, and nothing in `frontend/src`, `frontend/tests`, `frontend/e2e` or `frontend/mock` mentions `FactoryDesk`, `work_desk_url`, `django_url`, `factory-forms`, `factory-assets` or `NEXT_PUBLIC_FACTORY_ORIGIN`. — verify: a vitest test using `matchingSources` from `frontend/tests/source-files.ts` over those four folders (excluding the test file itself) returns an empty list; `cd frontend && npm test` passes.
2. The rewrite set is exactly the expected one. — verify: new `frontend/tests/next-config.test.ts` sets `API_ORIGIN`, calls `rewrites()` and asserts: `beforeFiles` is exactly the `/api/v1/:path*` rewrite; `afterFiles` has exactly six entries whose sources match the table; `fallback` is empty or absent; no source is `/:path*`, `/accounts/...`, `/static/...`, `/factory-forms/...`; every destination starts with `API_ORIGIN`; the config has no `env` key.
3. `/__mock/reset` is present only with `NEXT_PUBLIC_MOCK_DEMO=1` and non-production. — verify: the same test runs the config with the flag unset (absent), `'1'` (present once), and `'1'` with `NODE_ENV=production` (absent).
4. Each of the six patterns accepts its route and rejects near misses. — verify: the test converts each source with Next's path matcher (`next/dist/compiled/path-to-regexp`, or `next/dist/shared/lib/router/utils/path-match`) and asserts: a matching example for each (UUID `3f2b8c1e-1a4d-4c7e-9b0a-5d6e7f8a9b0c`, ids `12`) matches; a non-numeric id, a non-UUID case, an extra trailing segment (`/cases/<uuid>/files/1/extra`), and the unrelated `/finance/followup-inbox/<uuid>/key` and `/health` do not match.
5. No rewrite shadows an app route. — verify: the same test asserts every rewrite sits in `afterFiles`, and that none of the app routes `/work/12`, `/work/12/history`, `/work/12/decide`, `/work/12/outcome`, `/work/12/respond`, `/projects`, `/projects/<uuid>`, `/projects/<uuid>/documents/5`, `/projects/<uuid>/anything` matches any of the six sources.
6. The shell always draws our frame, even if `/me` still carries Django fields. — verify: a vitest render of `AppShell` (pattern of `frontend/tests/frame-fixtures.test.tsx`) with a `/me` mock body that includes `work_desk_url` and `django_url` destinations draws the standard frame states (ready nav from `destinations`, or the no-sections state), with no `psl-work-client` element and no link whose href contains `/factory-forms` or a `django_url`.
7. Signed-out, forbidden, error and loading states still draw as before. — verify: the existing shell tests (`frame-fixtures.test.tsx` and the other shell tests) pass unchanged; none is edited to relax an assertion.
8. Mock dev run unchanged. — verify: `cd frontend && npm run dev -- -p 3101` (mock on `127.0.0.1:4010`, or `MOCK_PORT` set to a free port if 4010 is taken) starts both; the home page and `/my-work` in a browser draw our frame (top nav, bell, page content), the browser console shows no failed request for `/factory-assets/work-client.js`, and Reset demo (DemoBar) still works. `npm run build` succeeds.
9. Unknown page is a Next 404, not Django JSON. — verify: with the dev run, `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3101/no-such-page` prints `404` and the body is the app's `not-found` page (HTML from `frontend/src/app/not-found.tsx`), not `{"error"...page_retired...}`; `/accounts/login/` and `/static/x.js` likewise return the Next 404 and never reach the API origin.
10. Live API-only check: a signed-out visit shows our frame. — verify (integration owner): start Django with `PSL_DJANGO_UI=0 PSL_ENV=development PGDATABASE=psl PGUSER=psl PGHOST=127.0.0.1 PGPORT=55432` and `python manage.py runserver 127.0.0.1:8000` (Postgres already on 55432, migrated), then `API_ORIGIN=http://127.0.0.1:8000 npm run dev -- -p 3102` (so `dev.mjs` runs the mock only for its own `4010`, with the demo bar off since the origin differs). Open `http://127.0.0.1:3102/` with no session: the page shows `SignedOutState` ("You're signed out." with the Sign in link), plus the frame chrome as drawn; it does not show the Django login widget or a raw JSON 404. `curl -i http://127.0.0.1:3102/api/v1/me` returns the API's 401 JSON through the proxy. Record the commands and the visible result in the build notes. A different state caused only by the v7-shaped `/me` against live data belongs to F-57; note it, do not fix it.
11. Download routes reach Django and keep its permission checks. — verify: in the live check, `curl -i http://127.0.0.1:3102/cases/3f2b8c1e-1a4d-4c7e-9b0a-5d6e7f8a9b0c/files/1/` (no session) returns Django's own 401/403/404 for that route (from `apps/agents/upload_views.download`, in API JSON form), not the Next 404 HTML, and not file content. Repeat for `/work/1/invoice-proof/1/`. Negative: `/cases/not-a-uuid/files/1/` returns the Next 404 and does not reach port 8000 (confirm in the runserver log).
12. Lint, typecheck and the gate pass. — verify: `cd frontend && npm run lint && npm run typecheck && npm test`, and `python delivery/design.py check` (or the repo's design check named in `delivery/checks.sh`) reports no new finding.

## Out of scope
- F-57: live types, live API client, session handling, error handling, the frame reading live `GET /me`, role words, the mock `/me` shape. Do not change the v7 mock or `roles`, `destinations`, `startable_lines` consumers.
- SCR-17 sign-in, recovery and invitation pages (wave 1); `SIGN_IN_URL` stays `/accounts/login/` and will 404 in Next until then (D-172). Do not add a stand-in page or redirect.
- Any screen's own data, DemoBar behaviour, any copy or design change.
- Any backend change, including enabling `APPEND_SLASH` behaviour or new download routes. Do not proxy `finance/followup-inbox/...` or `health/`.
- Do not reintroduce a catch-all, an `/static` proxy, or an env-var-driven link to a Django host.

## Assumptions
- Download rewrites go in `afterFiles`, not `beforeFiles`: a real page must win over a rewrite; the tight patterns make the order mostly moot, and this is the safer default readiness asked for.
- Expected trailing-slash handling: the destination keeps Django's trailing slash; builder confirms by request (criterion 11) because the Django routes require it.
- The `Sign in` link staying at `/accounts/login/` (a Next 404) until wave 1 is deliberate, per D-172 and readiness; changing it would alter the frame.
- Criterion 1 allows no mention of the removed names anywhere in the frontend, including comments; the removal note belongs in the commit message.
- Criterion 10 uses port 3102 for the live run so it does not clash with the mock run on 3101; ports are arbitrary.

## Conflicts with the boards
None. The spec removes only the embed, which no board draws, and leaves every state the boards draw (loading, signed-out, forbidden, error, no-sections, ready) as the shell already renders it. The one visible side effect, the Sign in link reaching a Next 404 until SCR-17 lands, is a gap not a board change; recommendation: accept per D-172.
