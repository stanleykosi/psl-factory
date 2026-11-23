VERDICT: PASS
COMMIT: 57ae81e83de4ca0de7560998684f6e419241185e
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead, light panel D-180)

## Summary
- I reviewed only the round-2 change, 15c8e6bd..57ae81e8: one commit touching 3 files in the sign-in feature, 16 lines added. I also read round-2/build.md. Nothing outside the builder's lane changed: no shared component, token, mock, contract or backend file.
- The Password field now gets the shared `is-error` class after a failed sign-in, but not while its own empty-field error shows. `TextField` merges the class into `cx(...)` alongside its own `is-error` (`frontend/src/components/TextField.tsx:26`), so the two never clash. `problem` is cleared when a real submit starts (`SignInView.tsx:89`), so the border goes away on the next try.
- The label weight change and the 52px phone inputs only apply inside `.signin-form`. The shared `.psl-label` weight (600) and the `--control-phone` token (48px) are left alone for other screens. The `Sign in` heading added to the loading, "cannot get ready" and not-admitted views leaves one h1 in each view.
- The new unit test checks that the error class lands on Password and not on the username field. No existing test was changed. I ran `npx vitest run tests/sign-in.test.tsx` and all 51 tests passed. I ran no other checks; the gate passed on this head.
- Impact on round 1: the session contract, `safeNext`, the CSRF handling, sign-out and the mock are unchanged, so my round-1 PASS still stands. TECH-1-1 (non-blocking, the mock has no `401` scenario on `POST /session`) is still open and was not in this round's Fixes.

## Findings
None.

## Verified
- TECH-1-1 | reopen | Not in this round's Fixes and not blocking. `frontend/mock/session.mjs` still has no 401 in `SCENARIO_ERRORS`, so the mock behaves as described in round 1.

## Notes
- The Fixes in build.md (UI-1-1, UI-1-2, UI-1-3 and UX-1-1) belong to the UI and UX reviewers. From the technical side, each one is wired correctly as described above.
- The error border shows for every sign-in problem: 422, 403 csrf, 429, 500, 503 and network errors. The boards only draw it for a wrong email and password, and a border on Password after a 503 or 429 slightly suggests the password was the cause. This is for the UX lens to decide. The fix would be to set the class only when `signInProblem` maps to the `sign_in_failed`/`invalid` case.
- The border is visual only. The Password field has no `aria-invalid` after a failed sign-in. That is acceptable because the callout gets focus and is announced.
- The spec text says the phone controls are 48px (`TextField phone`). The board, and UI-1-2, say 52px. The build follows the board, which is the agreed rule. The 52px is a literal value in `sign-in.css` rather than a token, which is fine for a one-screen override.
