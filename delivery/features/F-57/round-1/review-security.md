VERDICT: PASS
COMMIT: 84f3a3e9959b9c9cebe0746a9324c3795d5290da
REVIEWER: reviewer-security
AUTHORITY: reviewer-security

## Summary
- CSRF token lives in a module variable only (no localStorage, sessionStorage or cookie writes in src apart from the mock-only DemoBar persona cookie). It is refreshed from GET /session after 401 and after 403 csrf_failed, and a failed write is never repeated by the client.
- 401 and 403 reveal nothing new: csrf, bad_request, too_large, unsupported, rate_limited and read_limited show fixed client wording; the 429 Retry-After number is not shown. Other kinds still show the server message, as before.
- The frame no longer reads or renders django_url or work_desk_url (grep of src finds none outside the generated schema), and the signed-out state has no link to /accounts/.
- The mock is not reachable from a production build: DemoBar and the /__mock/reset rewrite need NODE_ENV not production and NEXT_PUBLIC_MOCK_DEMO=1. The /api/v1 rewrite is the only unconditional one, and API_ORIGIN picks its target. The download rewrites are unchanged exact paths.
- The menu follows /me destinations, which is advisory only. D-174 accepted the unfiltered menu, and the server still enforces access per request. No new dependency, only a generated types file.

## Findings
None.

## Notes
- Non-blocking, low. `call()` on a `csrf` error awaits `refreshSession()`, which itself goes through `call()`. If GET /session ever returned 403 csrf_failed, this would recurse without a bound. Django does not do that for a GET, and the mock's session route is answered before the scenario check. A one-line guard would be harmless (frontend/src/api/client.ts:62-65).
- Non-blocking, low. The sign-out token rotation is not exercised yet because the frame has no sign-out. The sign-in flow in wave 1 (SCR-17) must call `refreshSession()` or `setCsrfToken` after both sign-in and sign-out. Django rotates the token on login, and the builder's live run showed the stale token giving 403 csrf_failed and the fresh one giving 200.
- Pre-existing and declared by the builder: the shared `SignedOutState` still links to /accounts/login/ on about 30 screens. This is the same Django login URL as before, not new exposure, and it is for wave 1.
- Pre-existing: the sign-in token returned to a signed-out caller by GET /session is expected, since it is the pre-login token.
- Role words are read from role-dashboard and shown as text, so React escapes them. A failure shows nothing and leaks nothing.
- Review limits: I did not start Django. I judged from the diff and the builder's live-run record, as the coordinator asked. I did not run npm ci or copy the frontend.
