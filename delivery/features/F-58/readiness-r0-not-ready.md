DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- The gates are clear. D-SIGNIN r2 and D-AUTH r3 are approved as built (architecture v9, D-175). The design is covered by exception D-173. FE-SIGNIN depends only on the app frame, and F-56 and F-57 are on main.
- The slice is too big for one reviewable PR. It has 8 boards, 4 forms, two fragment-token pages, CSRF handling, a frame change, a role-word refresh and a clean-up across about 30 screens. Cut it into F-58a, F-58b and F-58c below.
- NOT-READY is for the size only. Once the cut is accepted, F-58a is READY at RISK high, because it is sign-in and session code. I did not need to ask the client anything.
- I could not run `design.py check` because this run has no shell. The coordinator must run it and confirm it passes before the spec starts.
- Several design lines cannot be filled from the live API (see Scope). Each needs a one-line client answer when its slice is specced, not now.

## Scope
Task FE-SIGNIN (SCR-17). Binding for the spec writer: do not decide who may sign in, and do not add endpoints or rules the API does not return.

**Recommended cut. Each part is one PR, in this order.**

**F-58a: sign in, error, sign out, frame hookup.** This is the base of the others.
- Boards: SCR-17-{desktop,mobile} and SCR-17-{desktop,mobile}-error.
- Endpoints: GET and POST /api/v1/session, and POST /api/v1/session/logout. Optionally GET /api/v1/me/onboarding for the first-run redirect.
- The form sends `{username, password, remember?, next_url?}` with a CSRF token. A 422 `sign_in_failed` shows one message and names no field. A 429 shows a plain "try again later". Follow `next_url` only as the server returns it.
- Sign-out uses the SCR-15 account-menu "Sign out" entry, and the frame returns to signed out.
- Replace the F-57 signed-out wording with a link to the sign-in page. The D-174 text said "no link until SCR-17".
- After sign-in, refresh the session and re-read the role words (F-57 TECH-1-3). Sign-in and sign-out both rotate the CSRF token.
- Repoint the signed-out state that about 30 screens link to (the retired /accounts/login/) through the shared `SignedOutState`, not screen by screen. If that cannot be done in one change, the leftovers go on a list for the spec to settle. They do not widen this PR.

**F-58b: forgotten password.**
- Boards: SCR-17-{desktop,mobile}-reset.
- Endpoints: POST /accounts/recovery/request, which returns 202 with the same answer for every address. POST /accounts/recovery/link takes the token from the URL fragment. GET and POST /accounts/recovery/password with `{new_password1, new_password2}`, then back to sign in.
- Page: /accounts/recovery/link/. Read the token from the fragment, send it in the JSON body, and clear the fragment from the address bar straight away.
- Never show whether an address has an account.

**F-58c: account set-up from an invitation.**
- Boards: SCR-17-{desktop,mobile}-setup.
- Endpoints: POST /accounts/invitations/preview and /accept, with the token in the fragment. /accept sends `{token, password, confirm, review_alerts?}` and returns 201 `{complete, next_url}`.
- Page: /staff/join/. The preview shows name, email, `expires_at` and the workspaces with their access words.
- If the invitation is expired, superseded or accepted, show the backend's refusal plainly.

**Out of scope for all three, per the API (the design lines it cannot fill):**
- "3 tries left", "pauses for 15 minutes", "link works for 30 minutes", "At least 12 characters" and "works for 72 hours". None appears in any response (A-46, A-47). The spec must either draw only what the API returns, such as `expires_at`, or keep the line as generic words with no number. Do not hard-code the numbers.
- "You'll go straight to INV-0412" before sign-in. It is a leak (G-SCR17-2).
- WhatsApp number add and code check on set-up (G-SCR17-5). The API has no operation for it.
- Deciding who may sign in. Admission is the backend's, and `admitted: false` from /me/onboarding is shown plainly (A-48 is open).
- Any change to the staff-invite screen (SCR-21) or the SCR-15 alert settings, which is the next wave 1 feature.

**Local testing.** I could not find the backend's email settings from here, and they are not recorded in the Project folder.
- Reset and invitation emails come from the backend's provider. A local run should use the backend's own non-sending email setup, such as Django's console, file or in-memory backend if it has one. Confirm this with the backend developer.
- The test then reads the link out of that captured message. For an invitation, POST /setup/{case_id}/invitations also returns a `join_url`.
- The frontend never builds or sends email. Delivery stays "not proven" until a real provider is checked, and the test notes must say so.
- Use the Postgres 16 instance on 127.0.0.1:55433 with the local test accounts. Mocked-API tests do not count as live evidence.

## Risk
RISK is high because this is sign-in, session, CSRF rotation and one-time tokens in URL fragments. A mistake here exposes accounts or blocks every person (contracts/psl-factory.openapi.json 1.22.0, D-SIGNIN r2, D-AUTH r3). The surfaces are ui, api, auth and security, plus contract-change for the shared signed-out state, the frame's role words and the retired /accounts/login/ links. product-decision applies because the design shows numbers and wording the API cannot supply. PRODUCT-ACCEPTANCE is required because these are new flows with new copy, and PSL still has to approve the design changes since 13 Nov (D-173 is an exception, not an approval). Open backend questions A-46 to A-49, A-54 and A-55 shape the copy, not the build, so they do not block F-58a to F-58c.

## Questions
None.
