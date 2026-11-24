VERDICT: PASS
COMMIT: f2a1ebfd541d2a248f6e0ef7985b31b561ca7582
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Invitation token: read once from the fragment into a ref, the fragment is removed with `history.replaceState`, and the token goes only into the JSON bodies of preview and accept. A malformed or missing token sends no request. The page sets `referrer: 'no-referrer'`.
- CSRF: the single automatic accept retry fires only on `403 csrf_failed`. Django's `CSRF_FAILURE_VIEW` is the only place that code comes from, so the view never ran and the retry is safe (A-3). There is exactly one retry.
- `signInTarget` allows the exact `/sign-in` path plus at most one `next` that passes `safeNext`. Anything else falls back to `/sign-in`. The signed-in branch follows only `safeNext(next_url) ?? '/'`.
- A signed-out person without a working token sees one uniform unavailable state with no name, email or access. Preview data is shown only to whoever holds a token the server accepts.
- Scope was F-60's own diff (`git diff ae0525fb HEAD`, 17 files). The 4 targeted test files pass (138 tests). No new dependencies and no secrets.

## Findings
None.

## Verified
- (round 1: nothing to verify)

## Notes
- Scope: F-60's own commits only (4a197c18, 743665ec, 0543c88f, 1de80870). The F-86 and F-72 files that came in with the merges were not reviewed here.
- Token handling (`frontend/src/features/join/JoinView.tsx:76-84`): `TOKEN.test` runs before the token is kept. The fragment is cleared even when the value is invalid. The token is cleared from memory after a successful accept (line 125). No `console`, `localStorage`, `sessionStorage` or `document.cookie` use exists in `src/features/join`, `src/features/sign-in` or `src/app/staff` (grep found nothing). `src/app/layout.tsx` has no third-party or analytics script that could read `location.href` before the fragment is cleared. The e2e test checks that `page.url()` has no `#`, that storage does not hold the token, that the referrer meta is set, and that a reload shows the unavailable state.
- Next redirects `/staff/join/` to `/staff/join` with a 308. The browser keeps the fragment on the client across that redirect, so the token never reaches the server. Fragments are never sent in `Referer`, so the no-referrer meta is a second layer, as the spec says.
- CSRF retry (`JoinView.tsx:117-124`): `errors.ts:78` maps the `csrf` kind only for 403 with `csrf_failed`. `apps/core/error_views.py:52-56` is the only place that code is raised (`config/settings.py:64`), so a second accept never repeats work that already ran. If the session refresh inside `call()` fails, the second send fails the same way and shows the fixed wording.
- `signInTarget` (`frontend/src/features/join/signInTarget.ts`): it rejects other paths, a missing query, a second `?`, extra keys and a repeated `next`. `safeNext` checks both the raw and the decoded value. The result always starts with `/sign-in`, so a `javascript:` or off-site `href` cannot get through. The 22 refusing cases in `tests/join-target.test.ts` pass.
- Rendering: `name`, `access`, workspace names and 422 messages are rendered as React text, never as HTML. `tests/join.test.tsx` covers the `<b>x</b>` case. Server messages are shown only for 422, and the unavailable state renders no preview data even though the preview stays in memory.
- The mock exempts the invitation paths from the signed-out 401 (`mock/server.mjs`) and still requires the current CSRF token. Fixture tokens are letter repeats and test passwords are fixtures. `package.json` and the lockfile are unchanged.
- Pre-existing, backend, not blocking: I found no per-IP rate limit on the unauthenticated `invitations/preview` and `invitations/accept` endpoints in `apps/core/factory_api`. Tokens carry 256 bits, so guessing one is not feasible, but each accept still runs password hashing for an anonymous caller. This is worth a backend look under the abuse lens.
- Out of scope by the spec, noted only: if someone is already signed in as another person in this browser, a successful accept followed by `signed_in: true` sends them on as the existing session. Global browser history (address autocomplete) may still hold the original link with the fragment; `replaceState` only rewrites the tab's history entry.
- No live Django run in this review. The backend CSRF and unavailable behaviour was checked by reading `apps/core/factory_api/accounts.py:144-172` and `apps/core/error_views.py`. The builder's curl results for criterion 21 match that code. Criteria 17, 19 and 22 are mock-only by the design engineer's answer.
- Tests run: `npx vitest run tests/join.test.tsx tests/join-target.test.ts tests/mock-invitations.test.ts tests/sign-in-next.test.ts`: 4 files, 138 tests passed.
