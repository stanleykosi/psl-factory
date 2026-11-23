STATUS: BLOCKED
COMMIT: 84f3a3e9959b9c9cebe0746a9324c3795d5290da
BUILDER: builder
LANE: full

## Summary
- Frontend work for F-57 is done and pushed: generated live types with a drift test, a live client (`liveApi`) beside the v7 one, `refreshSession()`, the new error kinds with `fields` kept, `idempotency_conflict`, and a frame that reads live `/me`, `/session` and `/role-dashboard`.
- The mock now answers the live `/me` shape, `GET /session` and `GET /role-dashboard`, validated against the live contract with Ajv, plus a `csrf_failed` scenario. Mock behaviour for the design engineer's app on port 3000 is unchanged (frame e2e passes).
- BLOCKED only on criterion 16 (live run through `next start`): the local PostgreSQL 14 cannot run the migrations (see Blocked), so no live check was possible. Per instructions I stopped there and did not touch the database further.
- `npm ci` was not run (the checks script's install step), because the design engineer's dev server uses this same `node_modules` and disk was near the 3 GB floor; every other step of `checks.sh` was run by hand, and all pass.
- Two judgement calls to confirm: the shared `SignedOutState` keeps its old link on the other screens (only the frame got the no-link wording), and mock `startable_lines` keep the v7 keys. Both are explained under Changes.

## Changes
- `frontend/package.json`, `src/api/live-schema.d.ts` (generated, 33,927 lines): script `gen:api:live`.
- `src/api/client.ts`: `liveApi` (same options, same CSRF middleware, one shared token); `refreshSession()`; `call()` on a `csrf` error refreshes the session once, never repeats the request, still throws the `csrf` error if the refresh fails.
- `src/api/errors.ts`: kinds `csrf`, `rate_limited`, `read_limited`, `bad_request`, `too_large`, `unsupported` added; fixed client wording for those kinds and for 403 `csrf_failed`; `ApiError.fields` (kept for every 422, `[]` otherwise).
- `src/api/types.ts`: `Me` from the live schema; `DestinationKey`; the old `Destination` type removed.
- `src/shell/`: `destinations.ts` (`visibleDestinations` matches by `key`, new `hasDestination`), `AppShell.tsx` (live `/me`; 401 gets one `/session` and, if `signed_in`, one more `/me`; `csrf_failed` gets one more `/me`; token kept after 401 and csrf), `useRoleWords.ts` (new; one `role-dashboard` read per page load, never awaited by the frame), `TopNav.tsx` and `PhoneBar.tsx` (role words only when present), `FrameStates.tsx` (new `FrameSignedOutState`: callout plus "Sign-in opens in a later release. Ask your administrator if you need access now.", no link), `DestinationPage.tsx`, `HomeRedirect.tsx` unchanged logic via `visibleDestinations`.
- `hasDestination` in `my-work/MyWorkPage`, `projects/{ProjectsPage,ProjectJourney,MoneyTab}`, `assistant/AssistantFrame`, `setup/SetupFrame`, `overview/OverviewPage`, `documents/DocumentReview`. (`ProjectsList`, `AssistantHome` only use `visibleDestinations(me.destinations)`, which still compiles and matches by key.)
- `features/start-work/useStartWork.ts`: `idempotency_key_reused` becomes `idempotency_conflict` (also in `mock/start-work.mjs` and its test).
- Mock: `mock/fixtures/me.*.json` in the live shape (no `roles`; `{key,title,django_url:'/retired/'}` destinations; `assistant_agents` always present); new `mock/session.mjs` and `mock/fixtures/role-dashboard.<persona>.json`; `mock/server.mjs` serves `/api/v1/session` and `/api/v1/role-dashboard` and the `csrf_failed` scenario (on `/me` and on writes); `mock/line-runs.mjs` and `mock/response.mjs` took their persona role word from `roleWords()` because they read the removed `me.roles` (this was a hidden crash that timed out five mock test files).
- Tests: new `api-live-schema-drift`, `mock-live-me`, `shell-live` (30 cases: live frame, role words, signed out, csrf, error states, `hasDestination` per page), extra cases in `client.test.ts` (session, csrf, error table, fields), `start-work.test.tsx` (409 `idempotency_conflict`), `next-config.test.ts` (exact `source` and `destination` of all six download rules, TECH-1-2). Existing tests moved to the new shapes; `tests/bell-feed.ts` now also answers `role-dashboard` by default (shared test helper, 25+ files use it); `tests/destinations.ts` helper. e2e: `frame.spec.ts`, `setup.spec.ts`, `exceptions.spec.ts`, `document-review.spec.ts` updated where a frame-level 401 used to show a sign-in link.
- Shared-file scope (checklist 9): none of Workspace, InlineDecide, WorkItemOverview, labels or Sections were touched.

Deviations to confirm:
- `SignedOutState` (used by about 30 screens for their own 401) is unchanged and still links to `/accounts/login/`; only the frame uses the new no-link state. Changing the shared one would rewrite many screen tests and the spec only describes the frame. The coordinator may want a follow-up that retires that link everywhere (wave 1, SCR-17).
- Mock `startable_lines` keep the v7 line keys (`invoice`, `weekly_report` ...), not live keys such as `pmo-weekly-report/v1`: several existing tests require `/me startable_lines` to equal the v7 E-LINES keys the mock also serves. The frame only tests `length > 0`.
- `tests/cash-forecast.test.tsx` has a diff guard that fails on any added `/api/v1/me` line under `src`; it now excludes `src/shell` and `src/api`.
- Fix-once candidate: any screen that treated 403 as "no permission" now sees `csrf` as a different kind and falls into its generic error line (for example the proof upload shows "Couldn't upload. Try again."), as the spec allows; no screen has a dedicated press-again line yet.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Live types match the contract: `tests/api-live-schema-drift.test.ts` regenerates and compares (passes); the script reads the same file the mock tests validate against. Not hand-run: `git diff` after `npm run gen:api:live` is clean because the drift test does the same comparison.
2. [x] `GET /session` stores the token: `tests/client.test.ts` "session" cases (token sent on the next live write; no token throws `csrf_unavailable`, nothing sent).
3. [x] 403 `csrf_failed` is its own kind, never retried: `client.test.ts` "403 csrf_failed" (one write, one `/session`, next write uses the new token; 403 `forbidden` makes no `/session` call).
4. [x] Error table: table-driven test for 400, 401, 403 (both codes), 404, 409 (`idempotency_conflict`, `stale_version`), 413, 415, 429 with `Retry-After` (no number in the message), 503 `read_limited`, 503 other, 500, network failure, non-JSON body.
5. [x] 422 keeps `fields`, `[]` when absent: `client.test.ts`.
6. [x] `rg idempotency_key_reused frontend/src` has no match; `start-work.test.tsx` has the 409 `idempotency_conflict` case.
7. [x] Frame on live `/me`: `shell-live.test.tsx` (five links in order, no Clients link, Projects current on `/clients`, Start work shows, no `/retired/` or `work_desk_url`/`django_url` value anywhere in links or text); `shell-no-embed.test.tsx` extended with real-looking paths.
8. [x] Callers use `hasDestination`: `rg "me\.destinations\.includes"` returns nothing; `shell-live.test.tsx` has one case per frame page (my-work, projects, assistant, setup, overview) showing `NotOpenState`.
9. [x] Role words: `shell-live.test.tsx` (PMO Lead, PMO Lead, Finance Lead gives "PMO Lead, Finance Lead" in `.shell-who-role` and the phone `<small>`; 500, 401, network failure, empty, blank names give the name alone with no error; frame renders while role-dashboard is pending; one read per page load).
10. [x] Signed out: `shell-live.test.tsx` (callout and later-release line, no anchor in `main`, no `/accounts/` in the DOM, one `/session`, token stored; `signed_in: true` reads `/me` once more). Also `e2e/frame.spec.ts`.
11. [x] Error and csrf states on `/me`: `shell-live.test.tsx` (429, 503 `read_limited`, 400, 500, network each show the card with its reference and Try again; 403 `forbidden` shows `ForbiddenState`; `csrf_failed` makes one `/session` and one `/me` retry only).
12. [x] Mock in the live shape: `tests/mock-live-me.test.ts` validates every `me.<persona>.json`, `role-dashboard.<persona>.json` and the running mock's `/me`, `/session`, `/role-dashboard` with Ajv against `contracts/psl-factory.openapi.json`; `roles` absent; an extra key or a string destination fails the same check. `mock-contract.test.ts` checks the `/me` 200 against the live schema.
13. [x] Mock looks the same: `npx playwright test e2e/frame.spec.ts e2e/demo.spec.ts` on ports 4960/4961: 25 passed, 3 skipped (the demo spec skips itself, as before); axe clean on desktop and phone. Fixtures were only reshaped. Also passed: `projects`, `setup`, `alerts-bell`, `alerts`, `exceptions`, `document-review` specs (after the 401 updates above). Not run by hand: the demo bar persona switch and Reset demo in a browser on port 3000 (I stayed off the design engineer's server); the persona and role words are covered by `mock-live-me.test.ts` and the frame e2e.
14. [ ] csrf notice on the mock page: client wording and the one-write-per-press rule are covered by unit tests (`client.test.ts`, `shell-live.test.tsx`) and the mock's `csrf_failed` scenario by `mock-live-me.test.ts`. I did not drive `/settings/alerts` Save in a browser, so the on-page text and the second press are unseen. Existing screens show it through their generic error line.
15. [x] Download rewrites asserted exactly: `next-config.test.ts` "each of the six download rules has exactly this source and destination".
16. [ ] Live run: not done, see Blocked.
17. [x] Whole gate except the install step and `design.py`: see Validation.

Design fidelity: not run. F-57 draws no new board; the spec's states reuse existing components, so there was no board of its own to score. The signed-out second line and the csrf wording are client text for the design engineer to read (D-174 accepted them).

## Validation
- `cd frontend && npm run lint`: clean. `npx tsc --noEmit`: clean.
- `npx vitest run` (full): 156 files, 3705 tests passed.
- `npm run build`: succeeded (production build). I did not run `npm ci` (see Summary).
- `cd /Users/Hunchoo/psl-factory && .venv/bin/python manage.py check`: no issues (with the PG env from checks.sh).
- `E2E_PORT=4960 MOCK_PORT=4961 npx playwright test e2e/frame.spec.ts e2e/demo.spec.ts`: 25 passed, 3 skipped. Same ports for `projects`, `setup`, `alerts-bell`, `alerts`, `exceptions`, `document-review`: passed after the e2e edits. The two `delivery/` items I could not run: `bash delivery/checks.sh` as one command (its `npm ci` step) and `python3 delivery/design.py check` (no `design.py` exists in the worktree or in `/Users/Hunchoo/psl-factory-main/delivery/`).
- `git status --porcelain` empty; head pushed to `origin/fe-connect-1-live-client`. My servers on 4960 and 4961 are stopped; the design engineer's 3000 and 3001 were not touched.

## Blocked
- Criterion 16 (live run via `next start` against Django): the local database at 127.0.0.1:55432 is PostgreSQL 14 and 180 migrations are unapplied. `manage.py migrate` stopped with `ProgrammingError: syntax error at or near "JSON"` on SQL using `e.body IS JSON OBJECT`, which needs PostgreSQL 16 or newer. As instructed I stopped: no drop, no reset, no Django server, no test account. Who can unblock: the coordinator or design engineer, by pointing me at a PostgreSQL 16+ instance (or running the live check with a database that already has the schema). Nothing in the frontend depends on it; criteria 16a to 16e (signed-out and sign-in through the proxy, the six-key menu, role words from a real session, a real `csrf_failed` and a single PUT, the proxy download status codes) remain unseen.
- The migrate attempt may have applied some early migrations before it failed; nothing was dropped.
- Disk dipped to 2.5 GB at times, then recovered to 3.5 GB; I kept going only for steps that need little space.
