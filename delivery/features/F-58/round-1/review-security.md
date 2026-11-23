VERDICT: PASS
COMMIT: 15c8e6bd1aa8c17eefc1f3365473714f6700eb3f
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- The sign-in page sends the CSRF token on sign-in and sign-out, and stores the new token after each one. The unit tests check the token on every request.
- The page always shows fixed wording when a sign-in fails. It never names the part that was wrong and never shows attempt counts, pause times or server text.
- The address the page goes to after sign-in only accepts paths on this site that belong to the app's frame. It checks the `next` value from the address bar and the `next_url` the server returns, both as given and after decoding once.
- No new packages, no secrets, and no backend change. The mock's sample login (`sample.user` / `sample-password`) is labelled as a sample and only works in the mock.
- Targeted check run: `vitest run tests/sign-in-next.test.ts tests/sign-in.test.tsx` passed 110 of 110 tests on this commit.

## Findings
- SEC-1-1 | non-blocking | low | frontend | Signing out switches pages inside the app (`router.replace('/sign-in')` in `frontend/src/features/sign-in/useSignOut.ts:27`) instead of loading the page fresh. Data the app holds in memory survives the sign-out: for example the last RFP frame kept by `frontend/src/features/rfp/frameMemory.ts:9`. On a shared device, the next person who signs in in the same tab and opens one of that RFP's tabs could briefly see the previous person's RFP header before their own read replaces it or fails. Expected: signing out clears everything the app holds in memory, for example by doing a full page load to `/sign-in` once the logout succeeds (the not-admitted notice on `/sign-in` can keep its current `onSignedOut` path). Actual: the module state stays in memory until the page reloads. The exposure is narrow: it needs the same tab and the same work item id, and the server still enforces access.

## Verified
None (round 1).

## Notes
- Access control stays on the server. `/sign-in` skips the frame (`PUBLIC_PATHS` in `frontend/src/shell/AppShell.tsx`), and this change hides nothing on the screen as a security measure. `destinations.ts` already says the screen is presentation only.
- Password handling: the form only appears after the session read on the browser side, so it is never in the server-rendered HTML and cannot be submitted before the page's script loads. It uses `method="post"`, so the password never lands in the address bar. The password field is cleared after every attempt.
- `csrfHeader` puts an empty `X-CSRFToken` to satisfy the types. The middleware then sets the real token (`headers.set`), and if no token is held it refuses to send the request. Tests at `frontend/tests/sign-in.test.tsx:168,180,277,328` check the real token on each request.
- Pre-existing, not introduced here: `ForbiddenState` (`frontend/src/shell/FrameStates.tsx`) shows the server's `error.message` word for word. That is fine while the API's messages stay plain, but it is not under the frontend's control.
- Sign-in rate limiting and checking `next_url` on the server are the backend's job (D-SIGNIN r2, no backend change in this feature). The client shows a fixed message for a 429 and only sends `next_url` after `safeNext` accepts it.
