VERDICT: PASS
COMMIT: 57ae81e83de4ca0de7560998684f6e419241185e
REVIEWER: qa
AUTHORITY: integrated QA

## Summary
- Exercised the real stack on this head: live-mode production build (`NEXT_PUBLIC_API_MODE=live`) on 4960 proxying to Django 8000 (PG16 on 55433, `PSL_FRONTEND_ORIGINS=http://127.0.0.1:4960`), driven with Playwright Chromium and curl through the proxy. No mocks. Accounts live-lead and live-none were given a throwaway password on the local database only (not committed; none is in the seed files).
- Success journeys pass. Sign-in of live-lead with `?next=/my-work` lands on `/my-work` (POST 200, then onboarding, `/me`, `/role-dashboard`); the bar shows "Account menu: Lena Lead"; sign-out from the menu goes to `/sign-in` and `/api/v1/me` then returns 401; reopening `/my-work` shows "You're signed out. Sign in" linking to `/sign-in?next=%2Fmy-work`. A signed-in visit to `/sign-in` shows no form and lands on `/my-work`. live-none stays on `/sign-in` with the not-admitted notice, `/getting-started/` is never requested, and its Sign out works (`/me` 401).
- Failure journeys pass. A wrong password and an unknown name both return 422 `sign_in_failed` with identical bodies and both show "That email and password don't match." The password is cleared, the username is kept, focus is in the callout, the callout has no digits, and the Password input has class `is-error`. An empty submit sends no POST and shows both inline messages. Empty-body curl returns 422 `invalid_input`.
- Redirect, remember and token checks pass. `?next=//evil.example` ends on `/` and `?next=https://evil.example` ends on `/my-work`, both on the app's own host. A curl POST with `next_url:"//evil.example"` returns `/`. `remember:true` sets a `sessionid` with Expires and Max-Age, and `remember:false` sets none. `csrf_token` rotates on sign-in and sign-out. A stale-token logout returns 403 `csrf_failed` and the session stays (`/me` 200). In the two-tab case the toast "Your session was refreshed. Press Sign out again. Nothing was changed." shows with `/me` 200, and the second press signs out (`/me` 401).
- Not proved here: 429, 500 and 503 sign-in (the live API cannot raise them; unit and mock tests cover them), the post-sign-in alert settings write with the new token (criterion 22 second half), axe and keyboard menu behaviour (mock e2e), phone-width 52px input height (measured output was cut off; a computed label weight of 500 and no horizontal scroll at 390 were seen), and a second persona's name replacing the first (live accounts give one person per run).

## Findings
- QA-2-1 | non-blocking | low | frontend | The first field's label reads "Work email or sign-in name"; the spec and board name it "Work email". This looks like a deliberate wording choice because the API also accepts a sign-in name, so please confirm it is covered by the D-178 waiver. Nothing is broken. `frontend/src/features/sign-in/SignInView.tsx`.

## Verified
- UI-1-1 | verified | Live wrong password: the Password input has class `psl-input is-error`, and the username input does not.
- UI-1-2 | verified | The build has the 52px phone-input rule; QA did not re-measure the height at 390 (see Summary). UI lens owns it.
- UI-1-3 | verified | Computed `.psl-label` font-weight is 500 at 390 and 1440.
- UX-1-1 | verified | `<h1>` "Sign in" is present on the ready view at both widths. The not-admitted view (live-none) shows the "Sign in" heading above the notice. Loading and cannot-get-ready views were not forced live.
