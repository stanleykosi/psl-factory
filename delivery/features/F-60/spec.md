# An invited person opens their link and sets up their account

> Tasks: FE-SIGNIN part (c) (SCR-17 set-up state). Architecture: package v9 (D-SIGNIN r2 and D-AUTH r3 approved as built, D-175), live API 1.24.0 (`contracts/psl-factory.openapi.json`, main b8542c79; D-185 re-spec). Design: exception D-173 (not a client approval), following F-58's settled calls D-177 to D-179 and the D-182 answers; screens: SCR-17 (`SCR-17-desktop-setup`, `SCR-17-mobile-setup`). Out: sign-in, error and sign-out (F-58, merged), reset and recovery (F-59), inviting people (SCR-21).

## Changes for 1.24.0
Re-spec under D-185. Every D-182 answer is kept (all eight recommended options). What changed:
- Not stacked any more: F-58 is merged on main, so F-60 builds on main.
- A-47 answered (12-character minimum on invitation set-up; no rule object in the API): the board's "At least 12 characters" hint line is now drawn under New password. The page still checks no length itself; the server decides and its message is shown as returned.
- A-54 answered (no universal 72 hours; `expires_at` is the real expiry; `join_url` is built from the request host): the validity line stays as "This invitation works until <date>." from `expires_at`; no duration is ever written. The invite origin and route are a deployment check, not a build blocker.
- Accept's `next_url` is now `/sign-in` (with `?next=%2Fsettings%2Falerts` only when `review_alerts` is sent; the page never sends it). Accept still does not sign the person in (read in `apps/core/factory_api/accounts.py`). The "Sign in" button follows that `next_url` through a strict check; a retired or foreign value falls back to `/sign-in`.
- The ready state is a plain heading and button, not a success callout (D-151, `tests/no-success-callouts.test.ts`), the same treatment as F-59's "Your password is changed."
- A-48 answered (show "no work is available", with sign-out or contact-Admin): F-58's not-admitted wording is reused as it is; "A-48 open" is removed.
- A-3 / D-185: after a `403 csrf_failed` the page retries the accept once automatically (the request was rejected before the handler), then shows the message. Previously it asked the person to press again.
- WhatsApp (G-SCR17-5): 1.24.0 adds no operation to add or verify a number (`/me/alert-preferences` only reads and saves "requested" flags for a signed-in person; the backend answers say WhatsApp stays deferred). The block stays out. No new question.
- Shared with F-59 (being updated): `BrandColumn.tsx` and `NewPasswordFields.tsx` in `src/features/sign-in/`, created by whichever feature builds first.
- Paths now point at the main checkout (`/Users/Hunchoo/psl-factory/frontend`).

## Summary
- A new public page `/staff/join/` reads the invitation token from the URL fragment, shows who is invited and what they have been given (`POST /api/v1/accounts/invitations/preview`), and lets them choose a password (`POST /api/v1/accounts/invitations/accept`), with the board's "At least 12 characters" hint (A-47).
- Wrong, expired or already-used links show one plain "This invitation can't be used" state that does not say which reason applies.
- After set-up the page shows "Your account is ready." with a "Sign in" button to the F-58 page. The backend does not sign the person in on accept; its `next_url` is `/sign-in`.
- The invitation's own `expires_at` is shown as the validity line; no duration is written. No WhatsApp step (no operation exists). Server messages for a rejected password are shown as returned.
- Frontend only, on main (F-58 merged). Shares `BrandColumn` and `NewPasswordFields` with F-59. The mock gains the two invitation routes in the live shape.

## Context
Where this lives today (main, folder `/Users/Hunchoo/psl-factory/frontend`):
- `src/features/sign-in/SignInView.tsx`: the pattern. Phases `loading | unready | ready | not-admitted`; `refreshSession()` then a form; `call(liveApi.POST(..., { params: csrfHeader, body }))`; `setCsrfToken`; fixed wording per error kind in `signInProblem`; inline `afterSignIn(destination)` (reads `/me/onboarding`, `admitted: false` sets `not-admitted`, else `router.replace`); `useSignOut.ts`; `Callout` (`kind="problem"`, `focusOnShow`), `TextField` (`phone`), `Button` (`busy`, `busyLabel`), `Loading`, `Skeleton`, `useIsPhone`. Layout classes in `src/features/sign-in/sign-in.css` (`.signin`, `.signin-brand`, `.signin-form`, `.signin-title`, breakpoint 719.98px). The brand column is the `brand` constant inside `SignInView`.
- `src/shell/AppShell.tsx` line 50 `PUBLIC_PATHS = ['/sign-in']` (matched with the trailing slash stripped): public paths render with no `/me` read and no bars.
- `src/shell/signInNext.ts` `safeNext(value)`: the only way a server-returned path is followed. `FRAME_ROUTES` (`src/shell/destinations.ts`) includes `/settings`; it does not include `/sign-in`, so `safeNext('/sign-in')` is `null`.
- `src/api/client.ts` (`call`, `csrfHeader`, `refreshSession`, `setCsrfToken`, `liveApi`; `call` refreshes the session after a `csrf` error), `src/api/errors.ts` (`ApiError` kinds `invalid`, `csrf`, `rate_limited`, `network`, `server`; `fields` must be read from the 422 body, as `postStep` does), generated `src/api/live-schema.d.ts` (do not edit; preview and accept are in it, accept's body allows the optional `review_alerts`).
- `tests/no-success-callouts.test.ts` (D-151): `kind="success"` callouts are allowed only in allowlisted files. This page adds none.
- Mock: `frontend/mock/session.mjs`, `frontend/mock/server.mjs` (route table, `psl_mock_session` cookie, scenario cookies 401/429/503/500, `CSRF_FAILED`).
- Tests to copy the style of: `frontend/tests/sign-in.test.tsx`, `tests/mock-live-me.test.ts`, `e2e/sign-in.spec.ts`.
- Backend (read only, `/Users/Hunchoo/psl-factory`): `apps/core/factory_api/accounts.py` `preview_invitation` and `accept_invitation`; `apps/identity/staff.py` `pending` and `accept`; `apps/core/factory_api/staff_access.py` builds `join_url` as `<request host>/staff/join/#<token>` (the fragment is the bare 43-character token, no `token=`).
- No frontend route `/staff/join/` exists. `next.config.ts` forwards only `/api/v1/*`, so the page is served by Next.

Live behaviour read from the backend code (builder re-checks live, criteria 17 to 22):
- Preview and accept are unauthenticated (`authenticated=False`) but both need the `X-CSRFToken` header from `GET /api/v1/session`.
- Token must match `^[A-Za-z0-9_-]{43}$`; otherwise the request is rejected as `invalid_input` before the domain runs.
- Preview, any unusable invitation (unknown, expired, already accepted, superseded by a newer invite, authority changed, no role) answers `422 {"code":"invitation_unavailable","message":"This invitation is unavailable."}`. All reasons look the same.
- Preview 200: `{name, email, expires_at, workspaces[{name, access}]}`; first workspace is the invitation's own, then any extra reviewed access. `access` is words such as the role description; show it as returned.
- Accept: `password` and `confirm` 1 to 128 characters. Different values: `422 invalid_input` "The passwords differ." with no `fields`. Weak password: Django's message is raised from `staff.accept` and mapped by `validation_problem` to `422 action_unavailable` with the first message (for example "This password is too short. It must contain at least 12 characters."). An invitation that stopped being usable between preview and accept answers `invitation_unavailable` (if the failure is a permission) or `422 action_unavailable` with "This invitation is unavailable." (if it is a validation error); a sign-in name that already exists gives the same text. So the code alone does not tell a password problem from an unusable invitation on accept.
- Accept 201 `{complete:true, next_url}`. In 1.24.0 `next_url` is `/sign-in`, or `/sign-in?next=%2Fsettings%2Falerts` when `review_alerts` is sent (the page never sends it). The accept does NOT sign the person in (the handler never logs in), and it does not rotate the CSRF token.
- Backend answers (`delivery/connect/backend-answers.md`): A-47 12-character minimum plus Django's validators on invitation set-up, no rule object in the API; A-48 `admitted:false` means "no work is available" with sign-out or contact Admin, no redirect to a Django form; A-54 expiry is the invitation's own `expires_at`, `join_url` is built from the request host and the Next.js invite origin and route are verified at deployment.
- The accepted invitation cannot be accepted again (`admission` exists), so a retry after success gives `invitation_unavailable`.

## Contract

### Route and shell
- Route `/staff/join/` (`src/app/staff/join/page.tsx`, small server page, `metadata.title = "Set up your account"`, renders client `JoinView` from `src/features/join/JoinView.tsx`). Add `'/staff/join'` to `PUBLIC_PATHS` in `AppShell.tsx` (no `/me`, no bars). Trailing-slash and bare forms both work (the existing strip handles `/staff/join/`).
- Reuse the sign-in layout: the shared `src/features/sign-in/BrandColumn.tsx` (the `brand` aside moved out of `SignInView`) and the shared `src/features/sign-in/NewPasswordFields.tsx` (below), both also used by F-59. Whichever of F-59 or F-60 builds first creates them in its first commit; the other imports them unchanged and does not reformat them. Reuse the `.signin*` classes (import `../sign-in/sign-in.css`; add only a few `.join-*` rules in `src/features/join/join.css`, tokens only). `SignInView` must look and behave exactly as before.
- `NewPasswordFields` is two `TextField`s, "New password" and "Confirm new password" (`type="password"`, `autoComplete="new-password"`, `maxLength` 128, `phone` size on a phone), the three client checks below with their focus handling and messages, and an optional `hint` prop. F-60 passes `hint="At least 12 characters"`; the text is a fixed string from PSL's A-47 answer and is linked to the field with `aria-describedby`. F-59 decides its own hint under its spec.

### Token handling (security)
- On first render read `window.location.hash`, strip the leading `#`, keep the value in a ref (memory only), then call `history.replaceState(null, '', location.pathname + location.search)` so the address bar and history entry no longer hold it. The token is never put in a query string, `localStorage`, `sessionStorage`, cookie, console output, error text or any URL; it is sent only in the JSON body of the two POSTs. A reload after clearing therefore shows the unavailable state (the person uses the emailed link again).
- A missing fragment or a value not matching `^[A-Za-z0-9_-]{43}$` goes straight to the unavailable state with no request.
- Add `<meta name="referrer" content="no-referrer">` for this page through the page's `metadata` (`referrer: 'no-referrer'`).

### Page load
1. Loading: `Loading` "Opening your invitation…" with the sign-in skeleton.
2. `refreshSession()` (`GET /api/v1/session`), then `POST /api/v1/accounts/invitations/preview` `{token}` with `X-CSRFToken`.
3. 200: show the set-up form.
4. 422 `invitation_unavailable`, or any 4xx other than 429/403-csrf: unavailable state.
5. Network, 5xx, 429, or the session read failing: "We couldn't open your invitation. Nothing was changed." `Callout kind="problem"` with "Try again" (repeats step 2 with the token still held in memory). 403 `csrf_failed` repeats the session read once automatically via `call()`'s refresh, then shows the same callout.

### Set-up form (default state)
Boards `SCR-17-desktop-setup` and `SCR-17-mobile-setup`: brand column ("PSL FACTORY", as in sign-in); form column headed "Set up your account"; phone uses 48px controls and a full-width button. One component, one breakpoint.
- Welcome line (from the preview, nothing invented): "Welcome, <name>. You've been given <access> for <workspace names>." Group `workspaces[]` by identical `access` text, keep returned order, and write one sentence per group with the names joined "A", "A and B", "A, B and C", for example "You've been given PMO for Ojo Foods and Kora Logistics." With several groups the first starts "You've been given…" and the next ones "You've also been given…". `name`, `access` and workspace names are rendered as returned, as text (never as HTML).
- Validity line, below the welcome line, secondary text: "This invitation works until <expires_at>." in the existing Lagos-time date formatting used by the frame (`Intl.DateTimeFormat`, `Africa/Lagos`, as elsewhere in `src`). It is shown only because the preview returns it; no duration is stated.
- Field "Work email": read-only `TextField` (`readOnly`, not `disabled`, so it is announced and selectable), value `email` from the preview, `autocomplete="username"`, `name="username"` (helps password managers; it is never submitted).
- Field "New password": `type="password"`, `autocomplete="new-password"`, `name="new-password"`, `maxLength` 128. Hint line under it as the board draws: "At least 12 characters" (A-47: PSL's 12-character minimum; the API returns no rule object). The page never compares the length itself; a refused password shows the server's message.
- Field "Confirm new password": `type="password"`, `autocomplete="new-password"`, `maxLength` 128. Required by the API (not on the board; D-182 Q1 (a); see Conflicts).
- Primary button "Finish setup" (busy label "Setting up…", ignores more presses while busy).
- Below the button: "Wrong roles? Ask the person who invited you; you can't change your own roles." (board text, kept).
- The form has `method="post"` and `onSubmit` with `preventDefault`, so a script failure can never put a password in the address bar.
- No WhatsApp field, no "We'll send a code to check it" sentence (G-SCR17-5; D-182 Q2 (a)): 1.24.0 still has no operation to add or verify a number, the alert preferences need a signed-in person and accept does not sign in, and the backend answers keep WhatsApp deferred. No `review_alerts` choice (the boards draw none; `review_alerts` is never sent).

### Client checks before sending (no request when one fails)
| Check | Message under the field | Focus |
|---|---|---|
| New password empty | "Enter a new password." | New password |
| Confirm empty | "Enter the new password again." | Confirm |
| Values differ | "The two passwords don't match." under Confirm | Confirm |

The page checks no length, character or word rules.

### `POST /api/v1/accounts/invitations/accept`
- Request: `{ "token": "<held token>", "password": "<as typed>", "confirm": "<as typed>" }` with `X-CSRFToken`. No other key.
- 201 `{complete:true, next_url}`: go to "After set-up" below. Clear both password fields and the held token from memory.
- Failures (password fields cleared in every case; each shown in one `Callout kind="problem"` above the form with `announce` and `focusOnShow` unless stated):

| Result | What shows |
|---|---|
| 422 `invalid_input` with `fields` | each field's server `message` under the matching input (`password` under New password, `confirm` under Confirm); a name the page does not know goes into the callout |
| 422 `invalid_input` without `fields` | callout with the server `message` as returned |
| 422 `invitation_unavailable` | switch to the unavailable state (below) |
| 422 `action_unavailable` or any other 422 | callout with the server `message` as returned; then call preview once more with the held token: if it now answers `invitation_unavailable`, switch to the unavailable state instead |
| 403 `csrf_failed` | `call()` refreshes the token; the page repeats the same accept once, automatically, with the same body (A-3: the request was refused before the handler, nothing executed). If that also fails, the row for its result applies; a second `csrf_failed` shows "Your session was refreshed. Press Finish setup again. Nothing was changed." |
| 429 | "Too many tries. Try again later." |
| network failure | "We could not reach PSL Factory. Check your connection and try again." |
| 5xx, 503, other | "Set-up isn't working right now. Try again in a moment. Nothing was changed." |

The server `message` is shown only for 422 and only verbatim, as plain text. Because a failed accept may or may not have created the account, a network error or 5xx after sending shows an extra sentence: "If this keeps happening, try signing in; your account may already be set up." with a link to `/sign-in`.
- Nothing is stored: neither password is kept in state after the request, in the URL, in storage or in a log line.

### After set-up
1. Call `refreshSession()` (the token and `signed_in`).
2. `signed_in: false` (what the backend does): show the ready state as plain text, not a success callout (D-151): heading "Your account is ready." (focus moves to it), the line "Sign in with <email>." (email from the preview) and a primary "Sign in" link to the target below. Same treatment as F-59's "Your password is changed."
3. Sign-in target from the accept's `next_url`, by a helper `signInTarget(nextUrl)` in `src/features/join/signInTarget.ts`: split off the query; the path must equal `/sign-in`, and the only allowed query key is `next`, whose once-decoded value must pass `safeNext`; then the target is `/sign-in` or `/sign-in?next=<encodeURIComponent(value)>`. Anything else (`/accounts/login/…`, an absolute URL, `//host`, other keys) gives plain `/sign-in`. Today's server value `/sign-in` gives `/sign-in`; the `?next=` form can appear only if a later backend adds it, because the page never sends `review_alerts`.
4. `signed_in: true` (a person already signed in in this browser, or a future backend that signs in on accept): `GET /api/v1/me/onboarding`; `admitted: false` shows F-58's not-admitted body and "Sign out" (A-48: "You're signed in, but no work is open to you yet. Ask your administrator."); `admitted: true` does `router.replace(safeNext(next_url) ?? '/')`; an onboarding read failure falls back to `/`. To avoid two copies, move F-58's `afterSignIn` and the not-admitted body into `src/features/sign-in/useAfterSignIn.ts` and use it from both views; `SignInView` behaviour must not change.
5. The role words shown in the frame after the new person signs in come from F-58's fresh frame mount; this page adds no role-words read.

### Unavailable state
`Callout kind="problem"` (not announced as an alert on first paint if the page just loaded; announced when switched to after a failed accept) with the heading "This invitation can't be used" and text "It may have expired or already been used. Ask the person who invited you to send a new one." and a plain link "Already set up? Sign in" to `/sign-in`. The page never says whether the link expired, was used, was replaced, or never existed. No form, no name, no email.

### Screen states
| State | What shows |
|---|---|
| Loading | "Opening your invitation…", skeleton, no form |
| Cannot open | Problem callout with "Try again", no form |
| Unavailable | Heading, text, sign-in link, no form |
| Ready | Welcome line, validity line, three fields (hint "At least 12 characters" under New password), "Finish setup" |
| Submitting | Busy button, fields kept |
| Field error | Messages under the field per tables above |
| Page error | Callout above the form per table above |
| Ready (done) | Heading "Your account is ready.", "Sign in with <email>.", "Sign in" button (no callout) |
| Signed in, not admitted | As F-58 |

### Mock and fixtures (frontend lane)
Mock routes in `mock/server.mjs` and a new `mock/invitations.mjs` (kept out of `session.mjs`), live shapes, both requiring the current CSRF token (else `403 csrf_failed`) and a body that validates (token 43 chars of `[A-Za-z0-9_-]`, else `422 invalid_input` with `fields`):

| Token (43 characters) | Preview | Accept |
|---|---|---|
| `'v'.repeat(43)` valid, one workspace group | `{name:"Sola Martins", email:"sola.martins@psl.example", expires_at:"2026-11-26T14:00:00Z", workspaces:[{name:"Ojo Foods", access:"PMO"},{name:"Kora Logistics", access:"PMO"}]}` | 201 `{complete:true, next_url:"/sign-in"}` the first time; afterwards that token behaves as used |
| `'m'.repeat(43)` two access groups | `workspaces:[{name:"Ojo Foods", access:"PMO"},{name:"Kora Logistics", access:"Finance Lead"}]`, same name and email | as above |
| `'e'.repeat(43)` expired | `422 {code:"invitation_unavailable", message:"This invitation is unavailable."}` | same |
| `'u'.repeat(43)` used | same | same |
| `'r'.repeat(43)` renewed between preview and accept | preview as valid | `422 {code:"action_unavailable", message:"This invitation is unavailable."}` and every later preview 422 `invitation_unavailable` |

Accept rules in the mock: passwords differ gives `422 invalid_input` "The passwords differ." (no `fields`); password shorter than 12 characters gives `422 action_unavailable` "This password is too short. It must contain at least 12 characters."; the word `password1234` gives `422 action_unavailable` "This password is too common."; anything else is accepted. Scenario cookies `401` (ignored: unauthenticated route), `429`, `503`, `500` apply to preview and accept as to `POST /session`. Mock `/staff/join/#<token>` URLs are the fixtures; there is no real credential anywhere.

## Lanes
- Frontend lane (owns all of it): `frontend/src/app/staff/join/**`, `frontend/src/features/join/**`, `frontend/src/features/sign-in/BrandColumn.tsx`, `NewPasswordFields.tsx` and `useAfterSignIn.ts` (extracted from `SignInView.tsx`, which is edited only to use them; `BrandColumn` and `NewPasswordFields` are shared with F-59, created by whichever builds first), `frontend/src/shell/AppShell.tsx` (the one `PUBLIC_PATHS` entry), `frontend/mock/invitations.mjs`, `frontend/mock/server.mjs` (two routes only), tests below. F-59 owns `frontend/src/features/recovery/**` and its own `PUBLIC_PATHS` entries; the two edits to the one array merge on rebase.
- Backend lane: none. No endpoint, schema or setting changes. Backend leftovers go on the list below.
- Integration owner: the builder runs the live checks (criteria 14 to 22) against local API-only Django and records commands and output in `build.md`.
- Shared files: `AppShell.tsx`, `SignInView.tsx`, `sign-in.css` are F-58's (merged); edits are the minimum above, and F-58's tests must pass unchanged. `src/api/live-schema.d.ts`, `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` and every path in `protected_paths` are not touched.

## Acceptance criteria
Verification kinds as in F-58 (spec on main, `delivery/features/F-58/spec.md`): unit = `npm test` (vitest), mock = the app on the mock (`npm run dev`, port 3000, or Playwright e2e), live = `next start` against local API-only Django (Postgres on 127.0.0.1:55433; start commands in F-58's spec). For live, create invitations locally with `POST /api/v1/setup/{case_id}/invitations` as an existing local lead (or the Django shell on the local database); take the token from `join_url` after `#`. Never commit tokens or passwords.

Page and token
1. `/staff/join/` renders with no `/me` call and no top bar or phone bar. — verify: unit (render `AppShell` at `/staff/join/` with a fetch spy: only `GET /api/v1/session` and the preview POST); mock (no "My work" link).
2. After the page reads the fragment, the address bar is `/staff/join/` with no `#`, and the token appears in no URL, storage (`localStorage`, `sessionStorage`, `document.cookie`) or console output; it is sent only in the JSON body of preview and accept. — verify: unit (spy on `history.replaceState`, storage and `console`; assert request URLs and bodies); mock (Playwright reads `page.url()` and storage after load).
3. No fragment, a fragment of the wrong length, or one with other characters shows the unavailable state and sends no preview request. — verify: unit.
4. The page's response sets `Referrer-Policy`/`<meta name="referrer" content="no-referrer">`. — verify: mock (page source or `document.querySelector('meta[name=referrer]')`).
5. After the fragment is cleared, a reload shows the unavailable state. — verify: mock (Playwright reload).

Preview and layout
6. A valid link shows "Set up your account", "Welcome, Sola Martins. You've been given PMO for Ojo Foods and Kora Logistics.", the validity line with the date from `expires_at`, a read-only "Work email" with the preview email, "New password" with the hint "At least 12 characters", "Confirm new password" and "Finish setup". With the two-group fixture the text reads "You've been given PMO for Ojo Foods. You've also been given Finance Lead for Kora Logistics." — verify: unit (both fixtures) and mock.
7. Desktop and phone layouts match `SCR-17-desktop-setup` and `SCR-17-mobile-setup` apart from the exceptions in "Conflicts with the boards". The page shows "At least 12 characters" under New password, no "72 hours" or other duration, no WhatsApp field or code sentence, and no `review_alerts` control. — verify: mock (design fidelity run at 1440 and 390 wide; `grep -rn "72 hours\|WhatsApp\|review_alerts" frontend/src/features/join` returns nothing).
8. Expired, used and wrong-token fixtures (`'e'`, `'u'`) show the identical unavailable text and link; the text never contains "expired" as a statement of fact. — verify: unit (snapshot equal for both) and mock.
9. The `name`, `access` and workspace values are rendered as text: a fixture name containing `<b>x</b>` shows the literal characters. — verify: unit.
10. Preview with 429, 503, 500 or a thrown network error shows "We couldn't open your invitation. Nothing was changed." with "Try again" and no form; Try again recovers. — verify: unit and mock (scenario cookies).

Submit
11. Empty password, empty confirm and mismatch show the three messages from the table, make no accept request, and focus the right field. — verify: unit.
12. The accept body is exactly `{token, password, confirm}` (no `review_alerts`) with `X-CSRFToken` from the last session read, and `method="post"` on the form means a submitted form never changes the address bar. — verify: unit (assert body keys and header) and mock (press Enter, address stays `/staff/join/`).
13. Each failure in the accept table shows exactly the specified outcome, both password fields cleared, the email kept: 422 `invalid_input` with `fields` (messages under fields); 422 without fields; 422 `action_unavailable` "This password is too short…" (callout with the server text; preview recheck still valid, form stays); the renewed-token fixture (`'r'`) lands in the unavailable state; 403 `csrf_failed` twice (the text above, the form stays); 429; 500/503; network error (extra "try signing in" sentence). — verify: unit with one fixture per row; mock for 429/503/500 scenario cookies.
13a. A `403 csrf_failed` on accept is retried once automatically with the same body and the refreshed token; success then shows the ready state, and two failures in a row show the "Press Finish setup again" text. — verify: unit (fetch spy counts exactly two accept calls with equal bodies and different `X-CSRFToken`).
14. Success on the mock: a good password pair gives the heading "Your account is ready." (focused), "Sign in with sola.martins@psl.example." and a "Sign in" link to exactly `/sign-in`; it is not a success callout and `tests/no-success-callouts.test.ts` passes with no allowlist change. Opening the same token again shows the unavailable state. — verify: unit and mock (`e2e/join.spec.ts`).
14a. `signInTarget` returns `/sign-in` for `/sign-in`, `/accounts/login/`, `https://evil.example`, `//evil.example` and `/sign-in?next=https%3A%2F%2Fevil.example`; and `/sign-in?next=%2Fsettings%2Falerts` for `/sign-in?next=%2Fsettings%2Falerts`. — verify: unit.
15. If the session read after accept says `signed_in: true`, the page runs the onboarding path: `admitted:false` shows the F-58 not-admitted message with working "Sign out"; `admitted:true` goes to the safe `next_url` or `/`; a `next_url` of `https://evil.example` or `/accounts/login/` is never followed. — verify: unit (router spy).
16. `SignInView` is unchanged in behaviour after the extraction: the existing `tests/sign-in.test.tsx`, `tests/sign-in-next.test.ts` and `e2e/sign-in.spec.ts` pass without edits. — verify: `npm test` and the e2e spec.

Live (through `next start`, port 3100, local API-only Django)
17. Preview of a fresh local invitation returns the real name, email, `expires_at` and workspaces and the page shows them as returned. — verify: live (browser at `/staff/join/#<token>`, network log).
18. A password shorter than 12 characters is refused by the server and the page shows the server's message in the callout; the page's own code compares no length (the only "12" is the hint text); a mismatch is stopped by the page. — verify: live; `grep -rn "length" frontend/src/features/join frontend/src/features/sign-in/NewPasswordFields.tsx` shows no password-length check.
19. A good accept returns 201, the page shows the ready state, the account exists (`manage.py shell`: user with the invitation's username), and signing in on `/sign-in` with the email and the new password lands on the person's first destination, with the top bar showing the invited person's name and the role words from `GET /role-dashboard`. — verify: live (screenshot of the bar; network log shows `/me` and `/role-dashboard` after sign-in).
20. Used, expired and superseded tokens (accept once then reuse; set `expires_at` in the past in the local database; issue a resend with `preceding_id`) all show the identical unavailable page; `curl` of preview for each returns `422 invitation_unavailable` with the same body. — verify: live.
21. Wrong tenant and wrong user: a token for one invitation never reveals another invitation's data; a 43-character random token returns the same 422 body as an expired one; the preview and accept requests with a missing or wrong `X-CSRFToken` return 403 `csrf_failed` and change nothing (the invitation can still be accepted afterwards). — verify: live (`curl` through the proxy).
22. Race: two tabs accept the same token with a good password; one gets the ready state, the other the unavailable state (or the callout then unavailable), and exactly one account exists. — verify: live.

Frame, access and tests
23. Axe finds no violations on `/staff/join/` in the ready, field-error, page-error, unavailable and ready-done states, desktop and phone; keyboard: Tab order email (skipped as read-only is acceptable only if it is focusable), New password, Confirm, Finish setup; the problem callout takes focus on a failed submit. — verify: mock (Playwright with `expectNoAxeViolations`, as in `e2e/frame.spec.ts`).
24. `grep -rn "staff/join" frontend/next.config.ts` is empty (no proxy to Django), and `tests/next-config.test.ts` still passes. — verify: grep and `npm test`.
25a. The "At least 12 characters" hint is present once under New password, announced with the field (`aria-describedby`), and the shared `NewPasswordFields` renders no hint when none is passed. — verify: unit.
25. The mock routes validate against the live contract (200, 201, 422 `invitation_unavailable`, 422 `invalid_input`, 403 `csrf_failed`) and reject a non-current token. — verify: unit (extend the `tests/mock-live-me.test.ts` pattern).

## Out of scope
- Any password rule other than the hint text "At least 12 characters": no length, strength or word checks in the page, and no "works for 72 hours" or any duration the API does not return (A-54).
- The WhatsApp number, its "send a code" step and any wording for it (G-SCR17-5: no operation exists in 1.24.0). The page calls no alert or WhatsApp endpoint.
- Alert review after set-up: `review_alerts` is not sent and `/settings/alerts` is not followed from this page. Alert settings are SCR-15.
- Sign-in, sign-out, errors (F-58), password reset and recovery (F-59), inviting, resending or revoking invitations (SCR-21).
- Any rule about who may be admitted, which roles may have accounts, or the "Only PMO, Finance…" sentence (A-48; the backend owns it).
- Automatic sign-in after set-up, "switch user", handling a person who is already signed in as someone else when they open an invitation link (beyond the `signed_in: true` branch above), changing a person's roles from this page.
- Backend changes. Leftovers for the backend: accept still does not sign the person in; accept answers a mixed `action_unavailable` for both unusable invitations and weak passwords (the page settles it with a preview recheck); no password-rule object; the invite origin in `join_url` is the request host, so deployment must check it is the Next.js origin and route `/staff/join/` (A-54).

## Assumptions
- The first sign-in after set-up is the F-58 page, because accept creates the user without a session; the "Your account is ready" state is a plain heading and button (D-151), not drawn.
- The welcome line uses the full `name` as returned (the board says "Sola"); inventing a first name from free text would be a guess.
- Workspaces are grouped by identical `access` text so the board's one-sentence form is kept when everyone's access is the same; several groups read as several sentences.
- "Work email" stays the board's label because the preview returns an email; the person signs in with it (the sign-in field takes an email or a sign-in name). The sign-in name is not shown because the preview does not return it.
- A confirm field is added because the API requires `confirm`; sending the same value twice without a second field would defeat its purpose.
- The server's validation text is shown verbatim for 422 (readiness: "show server validation messages as returned"), in a callout rather than under the password field, because on accept the code alone cannot separate a password message from an unusable invitation; a preview recheck settles which.
- The invitation's `expires_at` is shown as a date-time in Lagos time, the frame's convention, with no "hours left" arithmetic.
- The `Referrer-Policy`/meta tag is added because the token travels in a link people click from email; fragments are not sent in referrers, so this is a second layer.
- Mock token strings are letter repeats because the contract fixes 43 characters; the passwords in the mock (shorter than 12, `password1234`) mirror live messages only for testing the wording path, and carry no authority.

- The hint "At least 12 characters" is a fixed string taken from PSL's A-47 answer, because the API returns no rule object; if PSL changes the minimum, the string changes in `NewPasswordFields` usage. The server still decides.
- `next_url` is followed only through `signInTarget` (path exactly `/sign-in`, optional safe `next`), because `safeNext` rejects `/sign-in` itself and the server value is advisory.
- One automatic retry after `csrf_failed` on accept, per A-3 and D-185; the accept carries no idempotency key and the refusal happens before the handler.
- The `signed_in: true` branch stays although the backend does not sign in on accept, because readiness binds the onboarding read and a person may open a link while signed in.
- The invite origin check (A-54) belongs to deployment, not this feature; the page works on whatever frontend origin serves `/staff/join/`.

## Conflicts with the boards
Each has a recommendation; the spec follows it. D-182 settled the first four. Proposed entries for `fidelity-exceptions.json` (F-58's form, `delivery/features/F-58/fidelity-exceptions.json`; filed by the integration owner, approver text from the design engineer). The "At least 12 characters" removal from the earlier spec is gone: the hint is drawn now.
```json
{ "exceptions": [
  { "role": "textbox", "name": "Confirm new password", "category": "added field", "reason": "The API requires `confirm`; the board draws one password field (D-182 Q1 a).", "approved_by": "<design engineer, D-182>" },
  { "role": "textbox", "name": "WhatsApp number for alerts (optional)", "category": "removed content", "reason": "G-SCR17-5: no operation exists in 1.24.0; the field and \"We'll send a code to check it. You can change this later.\" are left out (D-182 Q2 a).", "approved_by": "<design engineer, D-182>" },
  { "role": "text", "name": "Welcome, Sola. You've been given PMO for Ojo Foods and Kora Logistics.", "category": "data wording", "reason": "Name, access words and workspaces come from the preview as returned; full name rather than first name (D-182 Q6, Q8).", "approved_by": "<design engineer, D-182>" },
  { "role": "text", "name": "This invitation works until <date>.", "category": "data wording", "reason": "The board's duration is replaced by the invitation's real `expires_at` (A-54: no universal 72 hours; D-182 Q5 a).", "approved_by": "<design engineer, D-182>" }
] }
```
- Board text that stays: "At least 12 characters", "Wrong roles? Ask the person who invited you; you can't change your own roles.", "Finish setup".
- Undrawn states added as plain design-system treatments: loading, cannot open, unavailable, ready (done, heading and button, not a callout), and the signed-in not-admitted state reused from F-58.
- Board duration wording versus the dated line: kept as the dated line. If the board's sentence names "72 hours", the page must not, because the backend says the duration varies.

## Questions for the design engineer
D-182 settled the eight questions of the first spec (all recommended options); they are not asked again. 1.24.0 adds no new product behaviour for this page. One presentation question remains:
1. The "ready" state after "Finish setup" (D-151 forbids a success callout).
   - (a) Recommended: a plain heading "Your account is ready." with "Sign in with <email>." and a "Sign in" button, the same shape as F-59's "Your password is changed."
   - (b) A toast "Your account is ready." and an immediate move to `/sign-in` (no stop on this page; the person may miss the message).
