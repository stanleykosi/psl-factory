DECISION: READY
RISK: high
SURFACES: ui, api, security, auth
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- The earlier NOT-READY (readiness-r0-not-ready.md) had one cause, the unmerged F-58. The coordinator's ruling clears it. F-59 builds stacked on branch fe-signin-sign-in-reset-and-set-up, as F-60 does. Its PR must not merge before F-58's, and it rebases onto main once F-58 lands. This is a limited exception for the D-180 push.
- Architecture (D-SIGNIN r2, D-AUTH r3, approved as built in v9 / D-175) and the live recovery API 1.22.0 cover this part. Design is covered by exception D-173.
- A-47 (password rules, link validity) and A-54 (link host) only shape copy. Handle them as D-177 to D-179 did: draw only what the API returns, with no numbers.
- RISK is high (account recovery, password change, token in the URL). PRODUCT-ACCEPTANCE is required (new flow and copy).

## Scope
Task FE-SIGNIN (SCR-17), part (b). Binding for the spec writer. One outcome: a person who forgot their password asks for a reset link, opens it at /accounts/recovery/link/ and sets a new password, then goes to sign in.

**In**
- Boards SCR-17-desktop-reset and SCR-17-mobile-reset, with any states the canvas draws on them (ask for the link, check your email, new password, done). About 8 boards at most. The spec writer confirms the states from the canvas and the connection map (delivery/connect/screens-a-frame-core.md, "SCR-17 · Sign in").
- Endpoints:
  - POST /api/v1/accounts/recovery/request `{email}` returns 202 `{requested}`. Give the same answer for every valid address. Say nothing about whether the address has an account.
  - POST /api/v1/accounts/recovery/link `{token}` returns 200 `{ready}`. The token comes from the URL fragment. Send it only in the POST body, then clear it from the address bar. Never put it in a query string, a log or a referrer.
  - GET /api/v1/accounts/recovery/password returns `{ready}`. POST `{new_password1, new_password2}` returns 200 `{complete}`. Then link to /sign-in. Do not sign the person in automatically.
- Change the F-58 "Forgot your password?" plain text into a link to the reset page (D-177). Remove the "Reset opens in a later release" hint.
- CSRF as F-58 does it: re-read the token from GET /session whenever a form is used. Show plain words for an invalid or expired link, for 429, and for network and 5xx failures. Name no field. Do not say whether an account exists.

**Out**
- The invitation set-up page and the WhatsApp step (F-60).
- Any number the API does not return, such as "link works for 30 minutes" or "at least 12 characters" (A-47). Use generic words or the server's own message as returned.
- Deciding who may reset. Admission and link validity belong to the backend.
- Any change to sign-in, sign-out or session behaviour beyond the one link.
- Which host the emailed link uses (A-54). The page only has to work at /accounts/recovery/link/ on the frontend origin. If the email points elsewhere, record it for the backend and do not widen the PR.

**Stacking and merge**
- Branch from fe-signin-sign-in-reset-and-set-up. The PR targets that branch or main with F-58 first, and it does not merge before F-58.
- After F-58 merges, rebase onto main and re-run the gate before merge.

**Local testing**
Run against the live API with Postgres on 127.0.0.1:55433. Cover the request, the link and the new password. Also cover an expired or reused link, mismatched passwords, a weak password refused by the server, and a reload of the link page after the token has been cleared. Mocked-API tests do not count as live evidence.

## Risk
RISK is high. This is account recovery: the token lives in the URL fragment, a password change is hard to undo, and mistakes can enable account takeover or user enumeration (D-SIGNIN r2, D-AUTH r3, contracts/psl-factory.openapi.json 1.22.0). SURFACES are ui, api, security and auth. I left out contract-change because it only edits the F-58 page link, and product-decision because the unknown rules are bound out of scope. Add the Opus security reviewer under D-180.
