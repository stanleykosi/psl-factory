VERDICT: PASS
COMMIT: 15c8e6bd1aa8c17eefc1f3365473714f6700eb3f
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead, light panel D-180)

## Summary
- I read the spec, build.md and the full frontend diff from base to head (src, mock, existing-test edits, the new unit tests). I ran no extra checks: the gate passed on this head and every claim held up on reading the code.
- The contract matches the spec. `POST /session` sends `{username trimmed, password, remember boolean, next_url?}` and the token from the last session read. The new token is stored after sign-in and after sign-out. A stale token on sign-out or sign-in re-reads the token through `call()` and never repeats the request. Errors show the fixed wording and never the server's message.
- `safeNext` is strict: a single leading `/`, no backslash or control characters, no dot segments, and the raw value and its once-decoded form must both pass. Only `/` and the `FRAME_ROUTES` prefixes are allowed. It runs on the `next` query and on the returned `next_url`. `FRAME_ROUTES` matches the folders under `src/app`. I found no way out to another site and no way back into a retired page.
- The `PUBLIC_PATHS` branch in `AppShell` mounts `FramedShell` fresh after a public page, so `/me` and the role words are read again after a sign-in (this closes F-57 TECH-1-3). The frame's 401 state now uses the shared `SignedOutState`. `FrameSignedOutState` is deleted. There is no backend change.
- Existing tests changed only where the signed-out link moved, or where the name became a button in the Tab order and button lists. The cash-forecast branch-diff guard was narrowed to allow only `/api/v1/me/onboarding`. That guard checks every changed file on the branch, so the narrowing is fair: the `/me` read stays forbidden. No test was skipped or weakened.

## Findings
- TECH-1-1 | non-blocking | low | frontend | The spec's Fixtures say the scenario cookies `401`, `429`, `503` and `500` all work on `POST /session`. Expected: `401` gives a 401 there too. Actual: `SCENARIO_ERRORS` covers only 429, 500 and 503. Under scenario `401` a sign-in with the sample pair succeeds and sets `psl_mock_session=in`, but the frame keeps answering 401. This affects the mock only (`frontend/mock/session.mjs:29`, `guarded` at :52). Either add 401 to the list or record that scenario 401 is just the starting state for showing the form.

## Notes
- `src/api/client.ts` is not in the spec's lane list. The `csrfHeader` constant (3 lines) only satisfies the live contract's typed `X-CSRFToken` parameter, and the middleware still sets the real value. It is small and correct, so I accept it.
- The account button's accessible name is "Account menu: <name> · <role words>" (`frontend/src/shell/AccountMenu.tsx:17`). The spec says "Account menu: <name>". Adding the role words keeps the visible words inside the accessible name, and the tests match the prefix, so I accept it.
- Criterion 25's grep also finds `/accounts/login/` in the test data of `tests/sign-in.test.tsx` and `tests/mock-live-me.test.ts`. These are server replies that the page must refuse, and criterion 11 requires them, so the criterion's literal wording cannot hold. Nothing in `src` mentions it.
- The "couldn't get sign-in ready" callout uses `announce={false}` (`SignInView.tsx:131`). If "Try again" fails a second time, nothing new is announced. This is for the UX lens to judge, not a blocker.
- The local `main` ref is behind `origin/main`. The architecture v9 commit `12181de9` in base..HEAD is already on `origin/main` and is not part of the builder's change.
