DECISION: READY
RISK: high
SURFACES: ui, api, security, auth
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-60 is part (c) of the SCR-17 split (D-176): an invited person opens /staff/join/, sees the invitation, and sets up their account. Part (a) is F-58 and part (b) is F-59.
- The gates are clear. D-SIGNIN r2 and D-AUTH r3 are approved as built (architecture v9, D-175), and the design is covered by exception D-173. The boards are SCR-17-desktop-setup and SCR-17-mobile-setup, and the work stays well under 8 boards.
- F-58 is not merged. Build F-60 stacked on branch fe-signin-sign-in-reset-and-set-up, and do not merge F-60 before F-58. This is a limited exception for the D-180 push. Rebase onto main once F-58 lands.
- RISK is high because the page sets a password and creates an account. PRODUCT-ACCEPTANCE is required because the flow and its copy are new.
- A-47, A-48, A-54 and G-SCR17-5 shape copy only. Handle them as F-58 did under D-177 to D-179: draw only what the API returns, and keep generic words with no numbers.

## Scope
Task FE-SIGNIN (SCR-17), part (c). Binding for the spec writer.

**In**
- Boards SCR-17-desktop-setup and SCR-17-mobile-setup, with a validation state only if the boards draw one.
- Page /staff/join/. The token comes from the URL fragment. Never send it to the server except in the POST body, and never log it. Clear it from the address bar after reading.
- POST /api/v1/accounts/invitations/preview `{token}` returns `{name, email, expires_at, workspaces[{..., access}]}`. Show the name, email, workspaces and access words as returned. Show a plain expired or invalid state without saying which one applies, unless the API does.
- POST /api/v1/accounts/invitations/accept `{token, password, confirm, review_alerts?}` returns 201 `{complete, next_url}`. Send `review_alerts` only if the board draws that choice. Follow `next_url` only as the server returns it, and only if it is a same-site path.
- GET /api/v1/me/onboarding after accepting, for the first-run landing. If `admitted` is false, show it plainly with no invented rule (A-48).
- Handle CSRF the way F-58 does.
- Re-read the session after accept, so the frame shows the new role words.

**Out**
- Password rules and invitation validity. Do not hard-code "At least 12 characters" or "works for 72 hours" (A-47, A-54). Show `expires_at` if the preview returns it. Show server validation messages as returned.
- The WhatsApp number add and code check (G-SCR17-5). No operation exists. Leave the step out, or draw it as "not available yet" per the design engineer's ruling. The spec must settle this, and it must not call any endpoint for it.
- Sign-in, error and sign-out (F-58). Reset and recovery (F-59). Inviting people (SCR-21).
- Any rule about who may be admitted. The backend owns it.

**For the spec writer to settle**
1. Wording for an expired, used or invalid invitation.
2. The per-field and password-mismatch error states, within what the API returns.
3. Whether the WhatsApp step is dropped or shown as unavailable. Record the board conflict with D-177-style wording for the design engineer.
4. Fidelity exceptions for each board conflict, filed in the same form as F-58's fidelity-exceptions.json.

**Local testing**
Run against the live API with Postgres on 127.0.0.1:55433. Cover preview, accept, an expired or used token, a password mismatch, the `next_url` follow, and the role words after accept. Mocked-API tests do not count as live evidence.

## Risk
RISK is high. The page sets a password from a bearer token in a URL fragment, which is an identity and account-creation path (D-SIGNIN r2, D-AUTH r3, contracts/psl-factory.openapi.json 1.22.0). SURFACES are ui, api, security and auth. I left out contract-change because F-58 already changed the shared pieces, and this feature only adds a page. I left out product-decision because the unknown policy numbers and the WhatsApp step are bound out of scope above.
