VERDICT: PASS
COMMIT: 84f3a3e9959b9c9cebe0746a9324c3795d5290da
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- The shared token is correct. `api` and `liveApi` use one module-level `csrfToken` and one `csrfMiddleware`. `refreshSession()` stores the token. `AppShell` keeps the session token after a 401 or csrf failure and clears it only on other errors.
- `csrf_failed` is its own kind with fixed wording. `call()` refreshes the session once and then throws. It never repeats the original request, and a failed refresh is swallowed so the `csrf` error still surfaces.
- The `/me` 401 path cannot loop. It makes one `/session` call, and at most one more `/me` read only when `signed_in` is true. A csrf failure on `/me` makes one retry. Both retries are straight-line code with no recursion in `load()`.
- The mock fixtures, `/session` and `/role-dashboard` are validated with Ajv against `contracts/psl-factory.openapi.json`. Every persona is covered, and `roles` and extra keys fail. The error table, `fields` on 422 and `idempotency_conflict` match `spec.md`. All six `hasDestination` callers are switched, and no `me.destinations.includes` remains.
- I found no blocking issue. There are three non-blocking points, listed below. I did not rerun the tests, because `checks.md` shows the gate passed on this head.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `refreshSession()` calls `call()`, and `call()` calls `refreshSession()` on a `csrf` error (`frontend/src/api/client.ts:46-65`). If `GET /session` ever answered 403 `csrf_failed`, the two would recurse without end. The live contract does not allow this today. A raw `liveApi.GET` inside `refreshSession`, or a guard flag, would remove the risk.
- TECH-1-2 | non-blocking | low | frontend | The mock `startable_lines` keep the v7 keys instead of live keys such as `pmo-weekly-report/v1` (`frontend/mock/fixtures/me.*.json`). `spec.md` says the fixtures use real live keys. The builder disclosed this, and the frame only tests `length > 0`, so nothing breaks. It needs a follow-up when the per-line adapter lands.
- TECH-1-3 | non-blocking | low | frontend | `useRoleWords` reads once per mount of the layout (`frontend/src/shell/useRoleWords.ts`). "Try again" after a `/me` error does not re-read it, and a sign-in in the same page session (SCR-17, wave 1) would not refresh it. This matches `spec.md` ("once per page load"). SCR-17 will need to re-trigger it.

## Verified
- Not applicable (round 1).

## Notes
- The shared `SignedOutState` still links to `/accounts/login/` on about 30 other screens. That code existed before F-57, and F-57 does not make it worse. A follow-up belongs in wave 1, SCR-17.
- Criterion 14 (the csrf text shown on the mock `/settings/alerts` page) was not driven in a browser. Unit tests and the live API-level check cover the behaviour.
- `design.py check` and `npm ci` were not run by the builder. The gate in `checks.md` is the authority.
