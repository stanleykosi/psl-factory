DECISION: READY
RISK: medium
SURFACES: ui, api, security, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Gates are clear. D-API-STYLE r3 and D-AUTH r3 are approved as built (package v8, D-172). The design exception for the current version is recorded (D-173, design/review.json). F-56 (part a) is merged at e80c3276, so the dependency is integrated.
- One outcome: the frontend talks to the live API 1.22.0 next to the v7 mock. It has generated live types with a drift test, a live-typed client, session and error handling per the live contract, and an app frame that loads from live GET /api/v1/me.
- The three open product points are answered in D-172: role words come from role-dashboard `positions[]` with the name alone on failure, the sign-in gap until wave 1 is accepted, and the mock `/me` moves to the live shape. Backend questions A-1, A-2 and A-4 stay open and are worked around, not waited on.
- Size: large for one PR but one coherent contract layer. About 56 frontend files mention `roles`, `destinations`, `startable_lines` or the error codes, mostly tests and fixtures. The cut is below. Do not split unless the builder cannot hold it in one review.
- Not run by this check (no shell): `design.py check` and the tests. The builder gate must run both.

## Scope
Task FE-CONNECT-1, part b. No new operation IDs. It uses live `GET /api/v1/me`, `GET /api/v1/session`, `GET /api/v1/role-dashboard` (read only, for role words). The spec writer follows this as binding.

In:
1. Types and client.
   - Add `src/api/live-schema.d.ts`, generated from `contracts/psl-factory.openapi.json` by a package script. Add a drift test that fails when the generated file differs from the contract.
   - Add a live-typed client next to the v7 one. It shares the CSRF middleware and the error reader. Unconnected screens keep the v7 client and mock.
2. Session and errors (frontend/src/api/client.ts, errors.ts).
   - `GET /session` supplies a token before sign-in and after rotation. Store it with `setCsrfToken`.
   - 403 `csrf_failed` is handled apart from `forbidden`. Refresh the token through `GET /session` and tell the person to press the action again. Never auto-retry a write (A-3 is unanswered).
   - Give 429, 503 `read_limited`, 400, 413 and 415 their own error kinds. Show no retry-after value, because A-5 is unanswered.
   - 422 always keeps `fields`. Recognise `idempotency_conflict` (409), replacing `idempotency_key_reused` in `useStartWork.ts`.
   - A 401 gives the signed-out state with no link to retired Django login pages. A download 401 or 302 is existing backend behaviour (A-55); only note it.
3. Frame on live `GET /me` (AppShell, TopNav, PhoneBar, destinations, HomeRedirect, DestinationPage, types).
   - `destinations[]` are objects `{key,title,django_url}`; look them up by `key`. `django_url` and `work_desk_url` are never used as links. `clients` is a known key.
   - There is no `roles` field. The menu is the same six entries for everyone, so do not invent per-role hiding (A-2 open). Pages already answer 403 and 404 through the shared error layer.
   - `startable_lines` uses the live line keys. `assistant_agents` is unchanged.
   - Role words (top bar, phone menu, Setup frame text) come from `GET /role-dashboard` `positions[]`. If the read fails or is empty, show the name alone and never an invented role.
4. Mock. Mock `/me` moves to the live shape (D-172 engineering rule) and is validated against the live contract in a test. Fixtures and tests that depend on v7 `/me` move with it. The mock must also serve a role-dashboard `positions[]` fixture in the live shape.
5. Hardening carried from F-56 (small): `next-config.test.ts` asserts each exact download destination (TECH-1-2). The F-57 acceptance run does a live check through `next start` against the live API using `-L` or slash-less paths (QA-1-2), plus a mock-mode `npm run dev` check of Reset demo.

Out, binding: SCR-17 sign-in, recovery and invitation pages (wave 1). Any screen's own data (wave 2+). The per-line workspace adapter and evidence picker (wave 3). Work-id format changes. DemoBar behaviour (stays mock-only). Any backend change. Screens other than the frame keep the v7 client and mock.

Known and accepted (D-172): against the live API a signed-out person has no sign-in page until wave 1. This matters only against live, not the mock.

Suggested cut if one review proves too big: (i) types, drift test, live client and error and session layer with unit tests; then (ii) the frame on live `/me`, mock `/me` shape and role words. Part (i) merges cleanly alone. Take the cut only if the builder or reviewers ask.

## Risk
Medium. There is no money or data migration, but the change sets how every later screen handles session, CSRF and 403, and it is a cross-layer contract change (live OpenAPI 1.22.0 against the v7 mock, frontend/src/api/client.ts and errors.ts, about 56 files that touch the old `/me` shape). Surfaces: ui (frame, role words, menu), api and contract-change (generated types, mock validated against the live contract), security and auth (CSRF refresh, no auto-retry of writes, 401 and 403 handling), product-decision (role-words fallback and an unfiltered menu, both accepted in D-172 but not seen by PSL). Product acceptance is required because what people see in the top bar and menu changes (no role words on failure, same menu for everyone) and PSL has not seen it.
