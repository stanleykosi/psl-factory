DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- The only gate missing is the dependency. F-58 (the /sign-in page, shared CSRF/session handling and the repointed `SignedOutState`) is not merged. It sits on branch fe-signin-sign-in-reset-and-set-up. F-59 changes the same page (the "Forgot your password?" text becomes a link, D-177) and reuses its form pieces.
- It becomes READY when F-58 is merged to main. No client question is needed. Merging F-58 needs the design engineer's batch approval (D-180: sign-in merges wait).
- Architecture (D-SIGNIN r2, approved as built in v9 / D-175) and the live recovery API 1.22.0 cover this part. The reset boards are the pair SCR-17-desktop-reset and SCR-17-mobile-reset. The spec writer must confirm from the canvas whether more reset states are drawn, and cap the work at about 8 boards.
- A-47 (password rules, link validity) and A-54 (link host) only shape copy. Settle them as D-177 did, by leaving out what the API does not return. They do not block this.
- RISK is high (account recovery, password change, token in the URL). PRODUCT-ACCEPTANCE is required (new flow and copy).

## Scope
Task FE-SIGNIN, part (b). Binding for the spec writer. One outcome: a person who forgot their password asks for a reset link, opens it at /accounts/recovery/link/ and sets a new password, then goes to sign in.

**In**
- Boards SCR-17-desktop-reset and SCR-17-mobile-reset, with any states drawn on them: ask for the link, "check your email", new password, done. About 8 boards at most.
- Endpoints:
  - POST /api/v1/accounts/recovery/request `{email}` -> 202 `{requested}`. Show the same answer for every valid address, and say nothing about whether the address has an account.
  - POST /api/v1/accounts/recovery/link `{token}` -> 200 `{ready}`. The page at /accounts/recovery/link/ reads the token from the URL fragment. It sends it in the body, then clears it from the address bar. It never puts the token in a query string, a log or a referrer.
  - GET /api/v1/accounts/recovery/password -> `{ready}`, and POST `{new_password1, new_password2}` -> 200 `{complete}`. After that, link to /sign-in. Do not sign the person in automatically.
- Turn the F-58 "Forgot your password?" plain text into a link to the reset page. Remove the "Reset opens in a later release" hint.
- CSRF as F-58 does it: re-read the token from GET /session whenever a form is used. Show plain words for an invalid or expired link (422 or similar), for 429 and for network and 5xx failures. Name no field and do not say whether an account exists.

**Out**
- The invitation set-up page and the WhatsApp step (F-60).
- Any number the API does not return: "link works for 30 minutes", "at least 12 characters" (A-47). Draw generic words with no number, or show the server's own message verbatim. Do not hard-code them (same approach as D-177).
- Deciding who may reset. Admission and link validity belong to the backend.
- Any change to sign-in, sign-out or session behaviour beyond the one link.
- Deciding which host the emailed link uses (A-54). The page only has to work at /accounts/recovery/link/ on the frontend origin. If the email points elsewhere, record it for the backend and do not widen this PR.

**Local testing**
Run against the live API on the Postgres instance at 127.0.0.1:55433. Cover the request, the link and the new password, plus an expired or reused link, mismatched passwords, a weak password refused by the server, and a reload of the link page after the token has been cleared. Mocked-API tests do not count as live evidence.

## Risk
RISK is high. This is account recovery: the token lives in the URL fragment and a password change is hard to undo, and mistakes can enable account takeover or user enumeration (D-SIGNIN r2, D-AUTH r3, contracts/psl-factory.openapi.json 1.22.0). SURFACES are ui, api, security, auth and contract-change (it edits the F-58 page). I left out product-decision because the unknown rules are bound out of scope. PRODUCT-ACCEPTANCE is required because the flow and copy are new. Add the Opus security reviewer under D-180.
