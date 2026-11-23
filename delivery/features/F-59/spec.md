# A person who forgot their password asks for a link, sets a new password, and signs in

> Tasks: FE-SIGNIN part (b) (SCR-17 reset). Architecture: package v9 (D-SIGNIN r2 and D-AUTH r3 approved as built, D-175), live API 1.24.0 on main (`contracts/psl-factory.openapi.json`, `frontend/src/api/live-schema.d.ts`), backend answers `delivery/connect/backend-answers.md` (A-3, A-5, A-47, A-54) and D-185. Design: exception D-173 (not a client approval), following F-58's settled calls D-177 to D-179 and `delivery/features/F-58/fidelity-exceptions.json`; D-182/D-183 answers (Q1 to Q7 accepted as recommended) kept; screens: SCR-17 (`SCR-17-desktop-reset`, `SCR-17-mobile-reset`). Out: sign-in, error, sign-out (F-58, merged), invitation set-up (F-60).

## Changes for 1.24.0
Re-spec under D-185. The four recovery operations are unchanged in the 1.24.0 contract (same paths, bodies and responses); what changed is the data the answers supply.
- Not stacked: F-58 is merged on main. F-59 branches from main, PR targets main, no merge-order rule. The "stacked on F-58 branch" text is removed.
- A-47 now answers: recovery links last 30 minutes and recovery passwords have a 12-character minimum with the server's validators. The page now draws what the board draws: "...we'll send a reset link that works for 30 minutes." and a hint "At least 12 characters" under New password. Both are display text kept in one named constants file; the page still makes no length, strength or similarity check (the server decides and its message is shown). Replaces the "no number, no hint" calls and old Q1 and Q5 recommendations (their D-182/D-183 answers were "no number until the backend adds it"; D-185 switches them on). Criteria 3, 13, 23 and the Out of scope list change with it.
- A-3: after a 403 `csrf_failed` the page refreshes `GET /session` and retries the same request once on its own; only a second failure shows the callout. (Replaces "Press the button again".) Safe because the CSRF check rejects the request before the handler runs.
- A-54: the emailed link is built from the request host and carries the token as a fragment; the backend says to verify the frontend origin and route at deployment. Criterion 28 becomes a deployment check on the real origin, not a "record for the backend" note.
- A-5: 429 carries a JSON `code` and `message` but no guaranteed `Retry-After`. The page keeps its fixed 429 wording with no time. No change.
- Still not supplied (unchanged, no new question): cooldown, link-expiry reason, a rules endpoint. `POST /link` still answers `ready:false` for every unusable link.
- Questions for the design engineer: old Q1 and Q5 are superseded by D-185; one new question (8).

## Summary
- Two new public pages: `/accounts/recovery/` asks for a work email (`POST /api/v1/accounts/recovery/request`, always 202) and then shows "Check your email."; `/accounts/recovery/link/` opens the emailed link, reads the token from the URL fragment, and lets the person choose a new password.
- The page never says whether an address has an account. It draws the board's "works for 30 minutes" and "At least 12 characters" (A-47, 1.24.0 answers; display text only, no client rule) and shows the server's own message for a refused password.
- A link that cannot be used (wrong, expired, used, or reloaded after the token was cleared) shows one plain "This link can't be used" state with a way to ask again. The page does not say which reason applies.
- After the change the page says "Your password is changed." with a "Sign in" button to the F-58 page. The backend does not sign the person in (checked in `apps/core/factory_api/accounts.py`) and the page does not either.
- F-58's plain "Forgot your password? Reset opens in a later release…" sentence becomes the drawn link. Frontend only, built on main (F-58 is merged). The mock gains the four recovery routes in the live shape.

## Context
Where this lives today (main, folder `/Users/Hunchoo/psl-factory/frontend`; F-58's sign-in is merged. Line numbers are from F-58's branch: the builder re-finds them):
- `src/features/sign-in/SignInView.tsx`: the pattern. Phases `loading | unready | ready | not-admitted`; `refreshSession()` then a form; `call(liveApi.POST(..., { params: csrfHeader, body }))`; `setCsrfToken`; fixed wording per error kind in `signInProblem`; `Callout` (`kind="problem"`, `focusOnShow`), `TextField` (`phone`), `Button` (`busy`, `busyLabel`), `Loading`, `Skeleton`, `useIsPhone`. Line 189 holds the plain "Forgot your password? Reset opens in a later release. Ask your administrator for help." sentence in `<p className="signin-forgot">`. The brand column is the `brand` constant at line 105. Layout classes in `src/features/sign-in/sign-in.css` (`.signin`, `.signin-brand`, `.signin-form`, `.signin-title`, `.signin-forgot`, breakpoint 719.98px).
- `src/shell/AppShell.tsx` line 50: `PUBLIC_PATHS = ['/sign-in']`, matched by exact equality after one trailing slash is stripped, so `/accounts/recovery` and `/accounts/recovery/link` each need an entry. Public paths render with no `/me` read and no bars.
- `src/api/client.ts` (`call`, `csrfHeader`, `refreshSession`, `setCsrfToken`, `liveApi`), `src/api/errors.ts` (`ApiError` kinds `invalid`, `csrf`, `rate_limited`, `network`, `server`; `fields` must be read from the 422 body as `postStep` does), generated `src/api/live-schema.d.ts` (do not edit; it already holds the four recovery operations at lines 59 to 103).
- `tests/no-success-callouts.test.ts` (D-151): `kind="success"` callouts are allowed only in allowlisted files. Nothing on this page uses one (see Contract, "Done").
- Mock: `mock/session.mjs`, `mock/server.mjs` (route table, `psl_mock_session` cookie, scenario cookies 401/429/503/500, `CSRF_FAILED`). Tests to copy: `tests/sign-in.test.tsx`, `tests/mock-live-me.test.ts`, `e2e/sign-in.spec.ts`.
- No frontend route `/accounts/recovery/` or `/accounts/recovery/link/` exists. `next.config.ts` forwards only `/api/v1/*`, so Next serves both pages.

Live behaviour read from the backend code (`apps/core/factory_api/accounts.py`, `apps/core/recovery_views.py`, `apps/core/account_delivery.py`) and confirmed unchanged in the 1.24.0 contract; the builder re-checks live (criteria 20 to 28). Backend answer A-47: 30-minute recovery lifetime, 12-character minimum with the server's password validators, `ready` as the only status field, no password-rule object:
- All four recovery operations are unauthenticated but need the `X-CSRFToken` header from `GET /api/v1/session` on the POSTs.
- `POST /accounts/recovery/request` `{email}` (string, max 254, email format): 202 `{requested:true}`. The handler returns the same body whether or not a route, account, usable password or email address exists, and whether or not a cooldown (`RECOVERY_COOLDOWN`) is running, so the page cannot learn more. A malformed address is the only 422 (`invalid_input`, from the schema, with `fields`).
- `POST /accounts/recovery/link` `{token}` (string, max 128): always 200 `{ready:boolean}`. A wrong, tampered, expired, consumed or route-changed token answers `ready:false`, not an error. A good token answers `ready:true`, clears any earlier binding, cycles the session key and stores the binding in the session. The token is a signed value (about 80 characters, contains `:`); the page checks only that it is 1 to 128 characters and does not assume the 43-character form of the invitation token.
- `GET /accounts/recovery/password`: 200 `{ready:boolean}`, true only when this session holds a still-valid binding (expiry, consumption and route are rechecked on each call). It works after the token has been cleared from the address bar, as long as the same browser session is used.
- `POST /accounts/recovery/password` `{new_password1, new_password2}` (each a password string): 200 `{complete:true}` and the binding is consumed. No binding or a binding that stopped being valid: `422 {code:"recovery_unavailable", message:"This recovery session is unavailable."}`. A refused password: `422 invalid_input` with message "Check the new password fields." and `fields[{name, message}]` using the names `new_password1` and `new_password2` (Django's messages, for example too short, too common, all numbers, too like the account's details, or "The two password fields didn't match."). The rules and the length are the server's (A-47); the page only displays the two documented figures and never enforces them.
- Success does not sign the person in and does not touch the CSRF token the page holds. Every other recovery response, including 202, carries no new token. The page still re-reads `GET /session` when a form opens, as F-58 does, because the link POST cycles the session key.
- The emailed link is built by `recovery_path` as `<reverse("factory_recovery_token")>#<token>`. The host comes from the request host (A-54: built from the request host, token as fragment; verify the frontend origin at deployment). The page only has to work at `/accounts/recovery/link/` on the frontend origin.

## Contract

### Routes and shell
- `/accounts/recovery/` (`src/app/accounts/recovery/page.tsx`, small server page, `metadata.title = "Reset your password"`, renders client `RecoveryRequestView` from `src/features/recovery/RecoveryRequestView.tsx`).
- `/accounts/recovery/link/` (`src/app/accounts/recovery/link/page.tsx`, `metadata.title = "Choose a new password"`, `metadata.referrer = 'no-referrer'`, renders client `RecoveryLinkView` from `src/features/recovery/RecoveryLinkView.tsx`). Both trailing-slash and bare forms work.
- Add `'/accounts/recovery'` and `'/accounts/recovery/link'` to `PUBLIC_PATHS` in `AppShell.tsx` (no `/me`, no bars). F-60 adds `'/staff/join'` to the same array literal; the two one-line edits will conflict on rebase and the integration owner merges them as one list.
- Reuse the sign-in layout: the shared `src/features/sign-in/BrandColumn.tsx` (the `brand` aside moved out of `SignInView`), exactly as F-60 specifies. Whichever of F-59 or F-60 builds first creates `BrandColumn.tsx`; the other imports it unchanged. Both import `../sign-in/sign-in.css` and add only a few `.recovery-*` rules in `src/features/recovery/recovery.css`, tokens only. `SignInView` must look and behave exactly as before apart from the one link below.
- Display figures (A-47): `src/features/sign-in/password-policy.ts` exports `RECOVERY_LINK_MINUTES = 30` and `MIN_PASSWORD_LENGTH = 12` with a comment "documented in backend answer A-47; display only, the server decides". Shared with F-60 (first builder creates it). Nothing else in the code holds either number, and no check compares a password's length.
- Shared password fields: F-60 and this page both draw "New password" and "Confirm new password" (same attributes: `type="password"`, `autoComplete="new-password"`, `maxLength` 128, `phone` size on a phone). Extract `src/features/sign-in/NewPasswordFields.tsx` (two `TextField`s plus the three client checks, focus handling and the "At least 12 characters" hint under New password, taken from `MIN_PASSWORD_LENGTH`) once; first builder creates it, the other reuses it. If neither lane wants to extract, copy is acceptable for the D-180 push but the wording and the three messages below must be identical to F-60's.

### The one change to F-58's page
In `SignInView.tsx` replace the line 189 sentence with `<p className="signin-forgot"><Link href="/accounts/recovery/">Forgot your password?</Link></p>` (Next `Link`, existing link styling; centred as D-178 placed the sentence). Remove "Reset opens in a later release. Ask your administrator for help." F-58's tests that assert the plain text (its criterion 27) change to assert the link; nothing else in `SignInView` changes. F-58's exception entry for `Forgot your password?` ("plain text until F-59") ends with this change: the integration owner removes it from the exceptions in force for this feature (see Questions for the design engineer, Conflicts).

### Ask for a link (`/accounts/recovery/`)
Boards `SCR-17-desktop-reset` and `SCR-17-mobile-reset` (the builder confirms in `design/canvas/project/SCR-17-*-reset.dc.html` whether "Check your email." is a second panel on the same artboard or a second state; both states are drawn).
- No session read is needed to render. On submit the page calls `refreshSession()` then the POST, so the token is always current (F-58's rule: re-read whenever a form is used). A failed read is shown as the network or 5xx wording below.
- Layout: brand column; form column headed "Reset your password" (phone: same, 48px controls via `TextField phone`, full-width button). Intro text as the board draws it: "Enter your work email. If it has an account, we'll send a reset link that works for 30 minutes." (minutes from `RECOVERY_LINK_MINUTES`, A-47). Field "Work email" (`TextField`, `type="email"` is acceptable here because the API takes only an email; `name="email"`, `autoComplete="email"`, `autoCapitalize="none"`, `spellCheck={false}`, value trimmed on send). Primary button "Send reset link" (busy "Sending…", ignores more presses while busy). A text link "Back to sign in" to `/sign-in`. `method="post"` and `onSubmit` with `preventDefault`.
- Client check before sending: empty or no "@" gives "Enter your work email." under the field, focus on it, no request. Nothing else is judged client-side.
- `POST /api/v1/accounts/recovery/request` `{"email": "<trimmed>"}` with `X-CSRFToken`.

| Result | What shows |
|---|---|
| 202 (any body) | "Check your email" state below |
| 422 `invalid_input` with `fields` | the server `message` for `email` under the field; any other name goes into a callout |
| 403 `csrf_failed` | refresh `GET /session` and retry the same request once (A-3); only if that also fails: callout "Your session was refreshed. Press Send reset link again. Nothing was changed." |
| 429 | callout "Too many tries. Try again later." |
| network failure | callout "We could not reach PSL Factory. Check your connection and try again." |
| 5xx, 503, other | callout "Reset isn't working right now. Try again in a moment. Nothing was changed." |

Callouts are `Callout kind="problem"` above the form with `announce` and `focusOnShow`; the typed email is kept. The same 202 state appears for every valid address, with identical text and timing behaviour; nothing differs for an unknown address or a running cooldown.

Check your email state (replaces the form; heading, text, link; no callout):
- Heading "Check your email."
- Text "If <typed email> has an account, a link is on its way. It won't say whether the account exists, to keep accounts private." (the board's own words; the email is the person's own typed text, rendered as text).
- Link "Back to sign in" to `/sign-in`. A secondary text button "Use a different email" returns to the form (email kept). Focus moves to the heading.
- No second send button and no countdown (the cooldown is not exposed, so none is invented).

### Open the link (`/accounts/recovery/link/`)
Token handling (security), same method as F-60:
- On first render read `window.location.hash`, strip the leading `#`, keep the value in a ref (memory only), then call `history.replaceState(null, '', location.pathname + location.search)` so neither the address bar nor the history entry keeps it. The token is never put in a query string, `localStorage`, `sessionStorage`, a cookie, console output, error text or any URL; it goes only in the JSON body of `POST /accounts/recovery/link`. The link page must have no analytics or third-party script and the metadata sets `referrer: 'no-referrer'`.
- A fragment of 0 characters, or more than 128, skips the POST and goes to the status check below (step 2), not straight to unusable.

Page load:
1. Loading: `Loading` "Opening your link…" with the sign-in skeleton.
2. Token held: `refreshSession()` then `POST /accounts/recovery/link` `{token}`. No token held (no fragment, or reload after clearing): `GET /accounts/recovery/password`; `ready:true` means this browser still holds a valid binding, `ready:false` means unusable.
3. Link POST `ready:true`: `refreshSession()` once more (the session key was cycled), drop the token from memory, show the new-password form. `ready:false`: unusable state.
4. Network error, 5xx, 429, or the session read failing: callout "We couldn't open your link. Nothing was changed." with "Try again" (repeats step 2 with the token still held; if the page was already cleared and reloaded the person uses the email link again). 403 `csrf_failed` re-reads the session and retries the POST once (A-3), then shows the same callout.

### New password form (state after a good link)
No board draws this state (see Questions for the design engineer 2). It reuses the layout of the sign-in form column.
- Heading "Choose a new password". Intro: "Choose a new password for your account." No username or email is shown (the API returns neither). Under "New password" the hint "At least 12 characters" (as the board and the set-up page draw it; from `MIN_PASSWORD_LENGTH`).
- Fields: "New password" (`type="password"`, `autoComplete="new-password"`, `name="new_password1"`, `maxLength` 128, hint line "At least 12 characters" under it, A-47) and "Confirm new password" (same attributes, `name="new_password2"`). Primary button "Change password" (busy "Changing…"). `method="post"` and `onSubmit` with `preventDefault`, so a script failure can never put a password in the address bar.
- Client checks, no request when one fails (same three messages as F-60): "Enter a new password." (focus New password), "Enter the new password again." (focus Confirm), "The two passwords don't match." under Confirm (focus Confirm). The page checks no length, character or word rules even though it shows the 12; the server decides and its message appears after a refusal.
- `POST /api/v1/accounts/recovery/password` `{ "new_password1", "new_password2" }` with `X-CSRFToken`. No other key. Both fields are cleared after every attempt and never kept in state after the request.

| Result | What shows |
|---|---|
| 200 `{complete:true}` | Done state |
| 422 `invalid_input` with `fields` | each field's server `message` under `new_password1` (New password) or `new_password2` (Confirm); a name the page does not know goes into the callout; messages shown verbatim as plain text |
| 422 `invalid_input` without `fields` | callout with the server `message` as returned |
| 422 `recovery_unavailable` | unusable state, announced |
| 403 `csrf_failed` | refresh `GET /session`, retry the same body once automatically (A-3; nothing ran, and the fields are held only until the retry ends); only if that also fails: callout "Your session was refreshed. Press Change password again. Nothing was changed." with both fields cleared |
| 429 | callout "Too many tries. Try again later." |
| network failure | callout "We could not reach PSL Factory. Check your connection and try again." plus "Your password may already be changed. If this keeps happening, try signing in." with a link to `/sign-in` |
| 5xx, 503, other | callout "Changing your password isn't working right now. Try again in a moment. Nothing was changed." plus the same extra sentence and link |

Callouts are `Callout kind="problem"` above the form with `announce` and `focusOnShow`. The server `message` is shown only for 422 and only verbatim. The extra "may already be changed" sentence is there because a lost reply could hide a completed change (the binding is consumed on success, so a retry would answer `recovery_unavailable`).

### Done state
Heading "Your password is changed." with the line "Sign in with your new password." and a primary "Sign in" link/button to exactly `/sign-in` (no `next`). Focus moves to the heading. It is plain text, not a success callout (D-151, `tests/no-success-callouts.test.ts`, which must still pass with no new allowlist entry). The page does not sign the person in, does not call `GET /me` or `/me/onboarding`, and does not follow any server `next_url` (none is returned). Reloading the page afterwards (no fragment, binding consumed) shows the unusable state.

### Unusable state
Heading "This link can't be used". Text "It may have expired or already been used. You can ask for a new one." A primary link "Send me a new link" to `/accounts/recovery/` and a text link "Back to sign in" to `/sign-in`. No form. It never says whether the link expired, was used, was replaced or never existed, and says nothing about an account. Shown without an alert announcement on first paint after load; announced when reached from a failed password change.

### Screen states
| Page | State | What shows |
|---|---|---|
| Ask | Ready | Heading, intro (with "works for 30 minutes"), "Work email", "Send reset link", "Back to sign in" |
| Ask | Submitting | Busy button, field kept |
| Ask | Field error / page error | Message under the field / callout per table |
| Ask | Sent | "Check your email." as above |
| Link | Loading | "Opening your link…", skeleton, no form |
| Link | Cannot open | Problem callout with "Try again", no form |
| Link | Unusable | As above |
| Link | Ready | "Choose a new password", two fields with the "At least 12 characters" hint, "Change password" |
| Link | Submitting | Busy button, fields kept empty of old values after a failure |
| Link | Field error / page error | Per table |
| Link | Done | "Your password is changed." with "Sign in" |

### Mock and fixtures (frontend lane)
Routes in `mock/server.mjs` (four route entries only) with the handlers in a new `mock/recovery.mjs` (kept out of `session.mjs`), live shapes, both POSTs requiring the current CSRF token (else `403 csrf_failed`) and a body that validates (`email` a string with "@" else `422 invalid_input` with `fields[{name:"email",...}]`; `token` a string of at most 128 characters). Binding kept in the existing `psl_mock_session` cookie mechanism as `recovery=<state>`.

| Token (fragment) | `POST /link` |
|---|---|
| `mock-recovery-good` | `200 {ready:true}` and binds this browser session; the first successful `POST /password` consumes it |
| `mock-recovery-expired` and `mock-recovery-used` | `200 {ready:false}` |
| anything else | `200 {ready:false}` |

- `POST /request`: `202 {requested:true}` for any address with "@" (the same body for `unknown@psl.example` and `ada.okafor@psl.example`).
- `GET /password`: `{ready:true}` while bound and not consumed, otherwise `{ready:false}`.
- `POST /password`: with no binding `422 {code:"recovery_unavailable", message:"This recovery session is unavailable."}`; mismatch `422 invalid_input` message "Check the new password fields." with `fields[{name:"new_password2", message:"The two password fields didn't match."}]`; fewer than 12 characters `fields[{name:"new_password1", message:"This password is too short. It must contain at least 12 characters."}]`; `password1234` `fields[{name:"new_password1", message:"This password is too common."}]`; anything else `200 {complete:true}` and the binding is consumed. The numbers and wording are test text mirroring live, never rules the page knows.
- Scenario cookies `429`, `503`, `500` apply to all four routes as to `POST /session`; `401` is ignored (unauthenticated routes).
- Mock `/accounts/recovery/link/#mock-recovery-good` is the fixture; there is no real credential anywhere.

## Lanes
- Frontend lane (owns all of it; branch from main): `frontend/src/app/accounts/recovery/**`, `frontend/src/features/recovery/**`, `frontend/mock/recovery.mjs`, `frontend/mock/server.mjs` (four routes only), `frontend/src/shell/AppShell.tsx` (the two `PUBLIC_PATHS` entries), the one-line link edit in `frontend/src/features/sign-in/SignInView.tsx` and its `tests/sign-in.test.tsx` assertion, tests below.
- Shared with F-60: `frontend/src/features/sign-in/BrandColumn.tsx`, `NewPasswordFields.tsx` and `password-policy.ts` (extracted from `SignInView.tsx`; whichever feature builds first owns the first commit, the other imports unchanged and does not reformat it), `AppShell.tsx` `PUBLIC_PATHS` (one list, integration owner merges), `sign-in.css` (F-58's; add nothing beyond what extraction needs).
- Backend lane: none. No endpoint, schema or setting changes (the 1.24.0 recovery operations are unchanged). Backend leftovers listed under Out of scope.
- Integration owner: the builder runs the live checks (criteria 20 to 28) against local API-only Django and records commands and output in `build.md`; resolves the `PUBLIC_PATHS`, `BrandColumn`, `NewPasswordFields` and `password-policy.ts` overlap with F-60.
- `src/api/live-schema.d.ts`, `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` and every other path in `protected_paths` are not touched.

## Acceptance criteria
Verification kinds as in F-58: unit = `npm test` (vitest), mock = the app on the mock (`npm run dev`, port 3000, or Playwright e2e), live = `next start` against local API-only Django (Postgres on 127.0.0.1:55433; start commands in F-58's spec; add `PSL_FRONTEND_ORIGINS=http://127.0.0.1:3100` if Django answers 403 `csrf_failed` to a correct token). For live, give a local account a throwaway password and a recovery route as `CONTACT_DELIVERY` allows (or create the `AccountDelivery` row in `manage.py shell` and take the token from `account_delivery.recovery_token(row)`), and open `/accounts/recovery/link/#<token>`. Never commit tokens or passwords.

Entry link and pages
1. The sign-in page shows "Forgot your password?" as a link to `/accounts/recovery/` and no longer contains "Reset opens in a later release" or "Ask your administrator for help"; it still calls no recovery endpoint until the person opens the page and submits. — verify: unit (role `link` by that name; fetch spy sees no `/accounts/recovery/*` call on `/sign-in`; `grep -rn "later release" frontend/src/features/sign-in` returns nothing); mock.
2. `/accounts/recovery/` and `/accounts/recovery/link/` render with no `/me` call and no top bar or phone bar. — verify: unit (render `AppShell` at both paths with a fetch spy: no `GET /me`, no `GET /role-dashboard`); mock (no "My work" link).
3. Desktop and phone layouts match `SCR-17-desktop-reset` and `SCR-17-mobile-reset` for the ask and the "Check your email." states apart from the added "Use a different email" button; the ask intro reads "...a reset link that works for 30 minutes." — verify: mock, design fidelity run at 1440 and 390 wide; `grep -rn "30\b\|12\b" frontend/src/features/recovery frontend/src/features/sign-in` finds the two figures only in `password-policy.ts` (and its test).

Ask for a link
4. An empty address or one without "@" makes no request and shows "Enter your work email." with focus on the field. — verify: unit (no POST on the fetch spy).
5. The request body is exactly `{email}` with the trimmed address and `X-CSRFToken` from a session read made at submit time; `method="post"` on the form means pressing Enter never changes the address bar. — verify: unit (body keys and header) and mock (press Enter; the address stays `/accounts/recovery/`).
6. A 202 shows "Check your email." with the typed address, and the text and DOM are identical for a known address and `unknown@psl.example` (same snapshot). — verify: unit and mock.
7. Server 422 `invalid_input` shows the server message under the field; 403 `csrf_failed` is retried once with the same body after a session read (the fetch spy sees two POSTs and one extra `GET /session`, and no callout when the second succeeds; a second 403 shows the callout); 429, a thrown network error, 500 and 503 each show exactly the specified wording, keep the typed address, never show the server `message` for non-422 and show no number or time. — verify: unit with one fixture per row; mock with scenario cookies 429, 503, 500.

Open the link and set the password
8. After the page reads the fragment the address bar is `/accounts/recovery/link/` with no `#`; the token appears in no URL, storage (`localStorage`, `sessionStorage`, `document.cookie`) or console output and is sent only in the JSON body of `POST /accounts/recovery/link`. — verify: unit (spy on `history.replaceState`, storage and `console`; assert request URLs and bodies); mock (Playwright reads `page.url()` and storage after load).
9. The page's metadata gives `<meta name="referrer" content="no-referrer">`. — verify: mock (`document.querySelector('meta[name=referrer]')`).
10. A good link (`mock-recovery-good`) shows "Choose a new password" with the two fields and "Change password"; a wrong, expired or used fixture shows the identical unusable text and links, and the text never states which reason applies. — verify: unit (snapshot equal across the three) and mock.
11. After the token is cleared, a reload with no fragment calls `GET /accounts/recovery/password`: it shows the form while the binding is still valid and the unusable state when not (after a completed change). No `POST /link` is sent without a held token. — verify: unit and mock (Playwright reload).
12. Empty password, empty confirm and mismatch show the three messages, make no request and focus the right field; the body is exactly `{new_password1, new_password2}`. — verify: unit.
13. Server refusals: 422 `invalid_input` with `fields` shows each message under the right field with both fields cleared; 422 without `fields` shows the callout; 422 `recovery_unavailable` shows the unusable state; 403 `csrf_failed` (one automatic retry with the new token, then the callout only if it fails again); 429; 500/503 and a network error (the extra "may already be changed… try signing in" sentence with a link). No code compares a password's length: `grep -rn "\.length" frontend/src/features/recovery` shows only the emptiness and match checks. — verify: unit with one fixture per row; mock for the scenario cookies.
14. A good change shows "Your password is changed." with a "Sign in" link to exactly `/sign-in`; it is not a success callout (`tests/no-success-callouts.test.ts` passes unchanged); the page makes no `/me` or `/me/onboarding` call and does not follow any URL. Reloading afterwards shows the unusable state. — verify: unit and mock (`e2e/recovery.spec.ts`).
15. Passwords are never kept after the request: the form fields are empty after a failure and after success, and neither password is in the URL, storage, a rendered error or a log line. — verify: unit (spies as in criterion 8).
16. Rendered text is escaped: a server `message` containing `<b>x</b>` shows literally. — verify: unit.
17. Keyboard and accessibility: Tab order is field to button to link; the problem callout takes focus on a failed submit; focus goes to the heading on "Check your email." and on Done; axe finds no violations in the ask, sent, loading, ready, field-error, page-error, unusable and done states, desktop and phone. — verify: mock (Playwright with `expectNoAxeViolations`, as in `e2e/frame.spec.ts`).
18. The mock routes validate against the live contract (202, 200 `{ready}`, 200 `{complete}`, 422 `invalid_input`, 422 `recovery_unavailable`, 403 `csrf_failed`) and reject a non-current token. — verify: unit (extend the `tests/mock-live-me.test.ts` pattern).
19. F-58 (merged) is unharmed: `tests/sign-in.test.tsx` (except the forgot-password assertion changed by criterion 1), `tests/sign-in-next.test.ts` and `e2e/sign-in.spec.ts` pass; `grep -n "recovery" frontend/next.config.ts` is empty and `tests/next-config.test.ts` passes. — verify: `npm test` and the e2e spec.

Live (through `next start`, port 3100, local API-only Django)
20. Request for a real local account and for `unknown@psl.example` both return 202 `{requested:true}`; the response bodies and headers (except `Date`) are identical, and a second request inside the cooldown also returns 202 with the same body. — verify: live (`curl` through the proxy comparing bodies; browser shows the same page).
21. A real link opened in the browser: `POST /link` returns 200 `{ready:true}`, the address bar loses the `#`, the form appears, and `GET /password` returns `{ready:true}` before and after a reload. — verify: live (network log and `curl` with the cookie jar).
22. A tampered token, a random 80-character token and a token for another account's consumed request each return 200 `{ready:false}` and the page shows the identical unusable state; no other account's data appears. — verify: live.
23. A password refused by the server (shorter than 12 characters, or one on its common list) shows the server's message under the field and leaves the link usable; the hint "At least 12 characters" is shown before any attempt and the page itself does not stop a short password. A mismatch is stopped by the page. — verify: live.
24. A good password returns 200 `{complete:true}`; the same link opened again shows the unusable state and `POST /password` without a binding returns 422 `recovery_unavailable`; signing in on `/sign-in` with the old password gives 422 `sign_in_failed` and with the new password succeeds. — verify: live (`manage.py shell` shows `check_password` true for the new password).
25. A missing or wrong `X-CSRFToken` on `POST /request`, `/link` and `/password` returns 403 `csrf_failed` and changes nothing (the link still works afterwards). — verify: live (`curl`).
26. An expired link (move the delivery row's `created_at` back past the server's limit in `manage.py shell`) and a link whose account route or password changed after it was sent both give the unusable state. — verify: live.
27. Race: two tabs set a good password with the same link; one gets Done, the other the unusable state, and exactly one change is recorded (`consumed_at` set once). — verify: live.
28. The link in the emailed message (read from the delivery record or the local mail backend) has the form `<host>/accounts/recovery/link/#<token>` and opens the page without redirecting through a Django route. A-54 says the host is the request host, so when the request comes through the Next.js proxy the host is the frontend origin: check it for a request made through `next start` (port 3100) and record the result; if the host is not the frontend origin, note it for deployment and do not change the PR. — verify: live and a note in `build.md`.

## Out of scope
- Invitation set-up page, `/staff/join/`, the WhatsApp step (F-60). Sign-in, sign-out, session behaviour or any change to `SignInView` beyond the one link (F-58). Change password for a signed-in person (SCR-15 account menu, `POST /account/password`).
- Any number the backend has not documented: a cooldown, "try again in N minutes", a resend counter, a different lifetime. The only figures drawn are the two A-47 ones (30 minutes, 12 characters), display only. No client-side length, strength or similarity checks.
- Deciding who may reset, which addresses have accounts, or whether a recovery email route exists (backend). No sentence saying whether an address has an account.
- Automatic sign-in after the change, redirect to `/sign-in?next=`, "switch user", signing out other sessions, a "was this you" note.
- The emailed message's text and host (A-54): the host follows the request host; if it points elsewhere in a deployment, record it for the backend.
- Backend changes. Leftovers for the backend: `POST /request` cooldown is not exposed; `POST /link` answers 200 `{ready:false}` for every unusable link, so the page cannot tell expiry from reuse (by design here); no rules endpoint (the 12 and 30 are documented in A-47 but not returned); the emailed link host check at deployment.
- Rate-limit or lockout logic in the page. A shared design-system success banner (D-151 keeps success as plain state, not a callout).

## Assumptions
- Routes `/accounts/recovery/` (ask) and `/accounts/recovery/link/` (link and new password on one page): the second is fixed by the backend's `recovery_path` and the connection map; the first keeps the prefix the retired Django route used and is the shortest path that reads as the same feature. The ask page was not named in a source.
- The new-password form lives on the link page, not on a third route, because the binding is held in the session and `GET /password` already tells the page whether it may show it; one route means one unusable state.
- The link page calls `GET /password` when no fragment is held, so a reload keeps working while the binding is valid; the contract offers this call and readiness asked to cover a reload after clearing.
- Unusable wording and "Use a different email" are plain additions with no board; the person may find "ask for a new one" useful and it names no reason.
- The email is echoed on "Check your email." because the board draws it and it is the person's own typed text; it leaks nothing.
- "Done" is a heading and line, not a success callout, because D-151 forbids success callouts for action results and the test enforces it. F-60's spec says `Callout kind="success"` for its ready state; F-60's builder will meet the same test, so the two should use the same plain heading-and-button treatment, set once.
- Token validity is checked as 1 to 128 characters only, because the recovery token is a signed value of about 80 characters, not the 43-character invitation token.
- 429 wording has no number or time and does not show the server message (A-5: no guaranteed `Retry-After`); the API's recovery routes show no 429 locally, so it is covered by unit and mock only.
- The 30-minute and 12-character figures come from the written backend answer A-47, not from a response field, so they sit in one constants file with that source named; if PSL changes the policy that file is the single edit (see Question 8).
- The automatic csrf retry (A-3) applies to all three POSTs; the retry reuses the same body (no idempotency key exists on these routes, and none is needed because the CSRF check rejects before the handler).
- `remember`, `next_url` and `/me/onboarding` play no part: the person is never signed in here.
- Live evidence needs a local recovery route configured for a throwaway account; if `CONTACT_DELIVERY` cannot be set locally the builder creates the delivery row directly in the local database shell and says so in `build.md`. Mocked-API tests do not count as live evidence (readiness).

## Conflicts with the boards
With A-47 answered, the "works for 30 minutes" exception is no longer needed: the intro matches the board. The remaining conflicts are the numbered questions below. Proposed entries for the feature's `fidelity-exceptions.json` (F-58's form; filed by the integration owner once approved, approver text left for the design engineer):
```json
{ "exceptions": [
  { "role": "button", "name": "Use a different email", "category": "added control", "reason": "Lets the person correct a mistyped address after the 202; no board draws it.", "approved_by": "<design engineer, date, decision>" },
  { "role": "text", "name": "Forgot your password?", "category": "none", "reason": "Ends F-58's plain-text exception: it is the drawn link again (D-177).", "approved_by": "<design engineer, date, decision>" }
] }
```
Undrawn states added as plain design-system treatments: Loading, Cannot open, Unusable, Ready (new password), Done.

## Questions for the design engineer
1. SUPERSEDED (D-182/D-183 accepted "no duration"; D-185 switches the data on). The ask sentence now reads as the board draws it, "...a reset link that works for 30 minutes." No decision needed.
2. The new-password state has no board (the reset boards draw only "ask" and "Check your email.").
   - (a) Recommended: build it from the sign-in form column and the set-up pattern ("Choose a new password", two fields, "Change password"), then review it at the fidelity run.
   - (b) Hold the page until a board is drawn (the whole flow stays unusable meanwhile; not recommended).
   - Same as F-60 Q1 for the second "Confirm new password" field (the API needs `new_password2`): recommendation there is to add it; here it is built as in F-60 Q1(a), to be changed with it.
3. The unusable-link state has no board.
   - (a) Recommended: heading "This link can't be used", text "It may have expired or already been used. You can ask for a new one.", primary link "Send me a new link", text link "Back to sign in".
   - (b) The same without the "Send me a new link" button (only "Back to sign in").
   - (c) Name the exact reason (not possible: the API answers the same for every reason). Same pattern as F-60 Q7; the wording here differs because the next step is asking again, not asking an administrator.
4. After the change (no board; the backend does not sign the person in).
   - Same as F-60 Q4, with the recommendation (a): a plain "Your password is changed." state with a "Sign in" button to the F-58 page. It is drawn as heading and text rather than a success callout (D-151).
5. SUPERSEDED (as Q1). The board's "At least 12 characters" hint is drawn under New password (A-47 now answers 12). No decision needed. The server's message still shows after a refusal.
6. "Use a different email" on "Check your email." (not drawn).
   - (a) Recommended: keep the small text button so a mistyped address can be fixed without reloading.
   - (b) Remove it; the person uses the browser back button or reloads (matches the board exactly).
7. F-58's plain "Forgot your password?" exception. The sentence returns to the drawn link in this feature.
   - (a) Recommended: link only, no helper words, centred as D-178 placed the sentence.
   - (b) Keep a helper line such as "We'll email you a link." under it (adds copy the boards do not draw).
8. Where the 30-minute and 12-character figures come from (new with 1.24.0; presentation only).
   - (a) Recommended: show them as the board draws, kept in one constants file that names backend answer A-47, because the API returns no value for either. The page never enforces them.
   - (b) Show them only once the backend returns them in a response (the figures stay hidden; the board's lines are missing until then; not recommended since PSL has stated the policy).
