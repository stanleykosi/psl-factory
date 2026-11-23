STATUS: READY
COMMIT: abf2482a0bbc656b975f1f1afda722df6cdf7941
BUILDER: builder
LANE: full

## Summary
- The Django embed is removed: `FactoryDesk.tsx` is deleted and `AppShell` no longer branches on `work_desk_url`, so the shell always draws our own frame.
- `next.config.ts` forwards only `/api/v1/*` (beforeFiles), the six authenticated download routes (afterFiles) and the mock-only `/__mock/reset`. The catch-all fallback, the four Django rewrites and the `env` entry are gone.
- Two new tests pin the rewrite set and prove the shell ignores Django fields on `/me`. The live API-only check and the mock run were done by hand, and the results are below.
- Two gate failures exist on the base and are not caused by this branch (see Validation). One live result differs from the spec's expectation (criterion 11, see below).

## Changes
- `frontend/src/shell/FactoryDesk.tsx`: deleted.
- `frontend/src/shell/AppShell.tsx`: removed the import, the `native` constant, and the early `return <FactoryDesk/>`. Destinations are always `visibleDestinations(me.destinations)`.
- `frontend/next.config.ts`: new rewrite set. Each download source uses `(\d+)` for ids, a hex 8-4-4-4-12 pattern for the case UUID and a single `:kind` / `:file_kind` segment. Each destination is the same path on `apiOrigin` with Django's trailing slash. `fallback: []`.
- `frontend/tests/next-config.test.ts` (new): criteria 1 to 5 (exact rewrite set, no `env`, mock-reset flag matrix, matcher accept and reject cases, no shadowing of app routes, and no mention of the removed names in src, tests, e2e or mock).
- `frontend/tests/shell-no-embed.test.tsx` (new): criterion 6. `/me` carries `work_desk_url` and Django-style fields; the frame draws, with no `psl-work-client` and no `factory-forms` link.
- Shared files: none touched.

## Fixes
None (round 1). At the coordinator's request, `frontend/tests/assistant-dictation.test.ts` was repaired (commit abf2482a): it now reads `legacy_ui/static/assistant-dictation.js` (path resolved from the test file), and the `no-this-alias` error is fixed in code by storing the instance on a holder object instead of aliasing `this`. `bash delivery/checks.sh` now passes in full: Django check, lint, typecheck, 153 test files and 3636 tests, and build.

## Acceptance criteria
1. [x] Embed gone, no mention of removed names: file deleted; the source scan in `next-config.test.ts` passes.
2. [x] Rewrite set exact: `next-config.test.ts` passes.
3. [x] `/__mock/reset` flag matrix: passes (absent, present once, absent in production).
4. [x] Patterns accept routes and reject near misses: passes, including each route matching only its own pattern.
5. [x] No shadowing of app routes: all six rewrites sit in `afterFiles`; the app-route list in the test matches none of them.
6. [x] Shell draws our frame with Django fields on `/me`: `shell-no-embed.test.tsx` passes.
7. [x] Existing shell tests unchanged and passing: full `npm test` gave 3632 tests passed, none edited. One file fails to load (see Validation, base issue).
8. [x] Mock run: used `next start` on 4960 with the mock on 4961. `npm run dev` cannot start because the design engineer's dev server holds Next's lock on this folder. A production build was used instead, so Reset demo (a dev-only route) was not exercised. `/` and `/my-work` draw the nav, bell, user and page content, `psl-work-client` count is 0, and no failed requests occur. `npm run build` succeeds.
9. [x] Unknown page is a Next 404 (against the API-only build): `/no-such-page` 404, with no `page_retired` in the body. `/accounts/login/` and `/static/x.js` end in a Next 404. Django was not hit: the runserver log shows no request for them.
10. [x] Live API-only check: Django `runserver --noreload` on 8000 with `PSL_DJANGO_UI=0` and Postgres on 55432 (no migration needed), and a build with `API_ORIGIN=http://127.0.0.1:8000` served by `next start -p 4960`. A headless Chromium visit to `/` with no session showed "Skip to main content | PSL FACTORY | You're signed out. Sign in", with no Django login and no JSON. `curl -i /api/v1/me` returned 401 JSON through the proxy.
11. [x] with a difference: `/cases/<uuid>/files/1/` and `/work/1/invoice-proof/1/` reach Django (log shows `GET ... 302`), not the Next 404. Django answers `302` to `/accounts/login/?next=...` (its `@login_required`), not a JSON 401. That is backend behaviour, so I did not change it. The browser then lands on `/accounts/login/`, which is a Next 404 until SCR-17. Negative `/cases/not-a-uuid/files/1/` gives the Next 404 and nothing reaches 8000.
    - Trailing slash: Next 308-redirects a request ending in `/` to the slash-less path, but the proxied request reaches Django with the trailing slash (log shows `.../files/1/`). The explicit trailing `/` in the destinations is therefore needed and verified.
12. [x] with a base failure: `npm run typecheck` passes. ESLint passes on every file I changed. The python design check was not run separately; `checks.sh` has no design step.

## Validation
- `bash delivery/checks.sh`: the Django check initially failed because the local venv lacked `pypdf`. I ran `.venv/bin/pip install pypdf==6.10.2`, the version pinned in `requirements.deploy.txt`, and it then passed. The script then stops at `npm run lint`: `tests/assistant-dictation.test.ts:15:53 no-this-alias`. This is main's file, which I did not touch. The same file also fails to load under vitest, because it reads `static/assistant-dictation...`, a folder missing from this checkout. Both are failures on the base branch. I ran the remaining gate steps by hand: typecheck passes, `npm test` shows 3632 tests passing with 1 file failing (assistant-dictation, load error), and `npm run build` passes.
- Superseded: after the assistant-dictation repair, the full gate passes (exit 0).
- Servers I started (Django 8000, next start 4960, mock 4961) are stopped and my temp files are removed. A production build of this branch is now in `frontend/.next`, built with the mock origin on 4961. The design engineer's dev server on 3000 was not touched, but a rebuild there may be wanted.
- No fidelity run: no board is owned and there is no design change.

## Blocked
Not blocked.
