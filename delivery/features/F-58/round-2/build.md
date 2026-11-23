STATUS: READY
COMMIT: 57ae81e83de4ca0de7560998684f6e419241185e
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the three blocking UI findings and adds headings to the sign-in loading, "cannot get ready" and not-admitted views (UX-1-1).
- SEC-1-1 (full-page navigation on sign-out) not done: it would change the router-based sign-out and its tests; left for the coordinator to decide.

## Changes
- `frontend/src/features/sign-in/SignInView.tsx`: Password input gets the shared `is-error` class (error border token `--signal`) after a failed sign-in; `<h1 class="signin-title">Sign in</h1>` in the three non-form views.
- `frontend/src/features/sign-in/sign-in.css`: `.signin-form .psl-label` uses `--text-label-weight` (500); phone inputs `min-height: 52px` under 720px.
- `frontend/tests/sign-in.test.tsx`: new test that only Password takes the error class after a failed sign-in.

## Fixes
- UI-1-1 | 57ae81e83de4ca0de7560998684f6e419241185e | Password field has the error border after a failed sign-in
- UI-1-2 | 57ae81e83de4ca0de7560998684f6e419241185e | phone inputs 52px
- UI-1-3 | 57ae81e83de4ca0de7560998684f6e419241185e | labels at the label token weight (500)
- UX-1-1 | 57ae81e83de4ca0de7560998684f6e419241185e | heading "Sign in" in loading, unready and not-admitted views

## Acceptance criteria
1. [x] Unchanged from round 1 except the above; `tests/sign-in*.test.*` 111 pass (including the new error-border test).

## Validation
- `npx tsc --noEmit`, `npm run lint` clean; `npx vitest run tests/sign-in` 111 passed. I did not re-run the full vitest, Playwright, or `delivery/checks.sh` (it runs `npm ci`); the change is limited to the sign-in feature files.
- Fidelity, one run per board on a production build (mock on 4961, app on 4960, cookie `psl_mock_session=out`, wait for `.signin-form input`, fidelity-exceptions.json). Reports in `round-2/fidelity/`.
| Board | Coverage with exceptions | Visual (round 1) |
|---|---|---|
| SCR-17-desktop @1440 | 100% | 86.9 (86.9) |
| SCR-17-desktop-error @1440 | 100% | 82.0 (81.9) |
| SCR-17-mobile @390 | 100% | 58.2 (65.1) |
| SCR-17-mobile-error @390 | 100% | 52.0 (59.3) |
- Visual is under 90 on all four. Desktop and phone gaps are covered by the design engineer's waiver extension (D-178, removed INV line, unfilled sample values). Phone visual fell after the 52px inputs; I did not iterate (one run). The error boards are scored against the same default page (no failed sign-in is reproduced at load), so the red border cannot show in that run.
- Servers on 4960 and 4961 stopped; 3000/3001 untouched.
