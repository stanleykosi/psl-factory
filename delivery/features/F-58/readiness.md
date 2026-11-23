DECISION: READY
RISK: high
SURFACES: ui, api, security, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- The size problem is solved. The design engineer accepted the cut in D-176, so F-58 is part (a) only: sign in, the error state and sign out, with the frame hookup. F-59 is the reset and F-60 is the invitation set-up.
- The gates are clear. D-SIGNIN r2 and D-AUTH r3 are approved as built (architecture v9, D-175). The design is covered by exception D-173, and the coordinator reports `design.py check` gives EXCEPTION with passes true. I did not run it. The exception covers the design only; it is not client approval of the changes since 13 Nov.
- Dependencies are merged. F-56 (#96) and F-57 (#97) are on main, and the live API 1.22.0 has the session endpoints.
- RISK is high because it is sign-in, session and CSRF code. PRODUCT-ACCEPTANCE is required because it is a new flow with new copy.
- The spec writer must settle the points listed under "For the spec writer to settle". None of them needs the client now.

## Scope
Task FE-SIGNIN (SCR-17), part (a). Binding for the spec writer: do not decide who may sign in, and do not add endpoints or rules the API does not return. One outcome: a person can sign in, see a plain error, and sign out. The frame and every signed-out screen then point at the new page.

**In**
- Boards SCR-17-desktop, SCR-17-mobile, SCR-17-desktop-error and SCR-17-mobile-error. Build only the default and error states.
- Endpoints: GET and POST /api/v1/session, and POST /api/v1/session/logout. GET /api/v1/me/onboarding is optional, for the first-run redirect.
- The form sends `{username, password, remember?, next_url?}` with a CSRF token.
  - A 422 `sign_in_failed` shows one message and names no field.
  - A 429 shows a plain "try again later".
  - Follow `next_url` only as the server returns it.
  - `admitted: false` from /me/onboarding is shown plainly. A-48 is open, so do not invent wording about the rule.
- Sign-out uses the SCR-15 account-menu "Sign out" entry. The frame returns to signed out. Sign-in and sign-out both rotate the CSRF token, so re-read it each time.
- Frame hookup:
  - The F-57 signed-out wording gets a link to the new sign-in page. D-174 said "no link until SCR-17".
  - After sign-in, refresh the session and re-read the role words (F-57 TECH-1-3).
- Repoint the retired /accounts/login/ through the shared `SignedOutState`, which about 30 screens use. Do it in that one component, not screen by screen. A search shows 42 mentions of `/accounts/login` in 31 files. Most are in tests and e2e specs that assert the old link, and `frontend/src/shell/sample.ts` and `config/settings.py` also mention it. Update the assertions with the component. Anything that cannot be fixed in the one change goes on a list for the spec to settle. It does not widen this PR.

**Out**
- The reset page and the recovery endpoints (F-59). The set-up page, invitation endpoints and the WhatsApp number step (F-60). The "Forgot your password" link on the sign-in board may be drawn as inert or pointing at F-59's route, as the spec settles below. It must not call any recovery endpoint.
- Numbers the API cannot supply: "3 tries left", "pauses for 15 minutes", and any other attempt count or lock time (A-46, A-47). Draw only what the API returns, or keep generic words with no number. Do not hard-code them. The error board's attempt counter and pause time fall under this.
- "You'll go straight to INV-0412" before sign-in. It is a leak (G-SCR17-2). Show no record name to a signed-out person.
- Deciding who may sign in. Admission is the backend's.
- Any change to the staff-invite screen (SCR-21) or the SCR-15 alert settings.

**Local testing**
- Run against the live API with the Postgres 16 instance on 127.0.0.1:55433 and the local test accounts. Mocked-API tests do not count as live evidence.
- Cover sign in, a wrong password, a 429 if it can be provoked, sign out, a `next_url` follow, and the role words refreshing after sign-in.

## For the spec writer to settle
1. Where the sign-in page lives, and how the shell treats it. The route is not recorded in the architecture. The page must work with no session and no app frame chrome that needs one.
2. The "Remember me" option. Send `remember` only if the board draws it. Do not state how long it lasts.
3. What the "Forgot your password" and any "have an invitation" links do until F-59 and F-60 are built. Choose inert text or a link to the route F-59 will own. Do not leave a dead link that looks live.
4. How the page is protected from open redirects. `next_url` is followed only as the server returns it, and only if it is a same-site path.
5. What the error state says for each of 422, 429, a network failure and a 5xx. Use plain words, name no field, and do not say whether the username exists.
6. The CSRF handling. Say where the token is read from, and that it is re-read after sign-in and sign-out. Say what happens if the token request fails.
7. The leftover list from the `SignedOutState` repoint, if any.

## Risk
RISK is high. This is sign-in, session and CSRF rotation, and a mistake can expose accounts or lock everyone out (contracts/psl-factory.openapi.json 1.22.0, D-SIGNIN r2, D-AUTH r3). SURFACES are ui, api, auth and security, plus contract-change because the shared `SignedOutState`, the frame's role words and the retired /accounts/login/ links change for about 30 screens. I left out product-decision: the numbers and wording the API cannot supply are bound out of scope above, so no business rule is left to guess. PRODUCT-ACCEPTANCE is required because the flow and its copy are new, and D-173 is an exception, not a client approval. Open backend questions A-46 to A-49, A-54 and A-55 shape copy only and do not block this part.

## Questions
None.
