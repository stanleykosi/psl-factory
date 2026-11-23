# A person can sign in, see a plain error, and sign out

> Tasks: FE-SIGNIN part (a) (SCR-17 default and error states; sign-out from the SCR-15 account menu). Architecture: package v9 (D-SIGNIN r2 and D-AUTH r3 approved as built, D-175), live API 1.22.0 (`contracts/psl-factory.openapi.json`). Design: exception D-173 (not a client approval); screens: SCR-17 (`SCR-17-desktop`, `SCR-17-mobile`, `SCR-17-desktop-error`, `SCR-17-mobile-error`) and the sign-out entry of SCR-15 (`SCR-15-desktop-account`, `SCR-15-mobile-account`). Out: `SCR-17-*-reset` (F-59) and `SCR-17-*-setup` (F-60).

## Summary
- A new public page `/sign-in` signs a person in with `GET`/`POST /api/v1/session`, shows one plain error for a wrong sign-in, and goes to a safe page afterwards.
- "Sign out" appears in the top-bar name menu (desktop) and the phone menu, calls `POST /api/v1/session/logout`, and returns to `/sign-in`.
- Every signed-out screen links to `/sign-in?next=<where you were>` through the one shared `SignedOutState`; the F-57 frame state uses it too, so the "Sign-in opens in a later release" text goes away.
- The CSRF token is read from the session response and re-read after every sign-in and sign-out. No attempt counts, pause times or password rules appear anywhere.
- No backend change. The mock gains `POST /session` and `POST /session/logout` in the live shape so the design engineer's app on port 3000 can show every state.

## Context
Where this lives today (branch `fe-signin-sign-in-reset-and-set-up`, folder `/Users/Hunchoo/psl-factory/frontend`):
- `src/api/client.ts`: `refreshSession()` does `GET /api/v1/session` and stores the token (`setCsrfToken`). `call()` refreshes the token on a `csrf_failed` 403 and never repeats the request. `src/api/errors.ts` maps statuses to kinds (`invalid` 422, `rate_limited` 429, `csrf`, `server`, `network`) and has fixed wording for csrf and 429.
- `src/app/layout.tsx` wraps every page in `AppShell` (`src/shell/AppShell.tsx`), which always calls `GET /me`, draws the top bar and phone bar, and on 401 shows `FrameSignedOutState` (`src/shell/FrameStates.tsx`: "Sign-in opens in a later release", no link). That is wrong for a sign-in page, so the shell needs a public branch.
- `SignedOutState` (`src/shell/FrameStates.tsx`) links to `SIGN_IN_URL` (`src/shell/sample.ts`, default `/accounts/login/`, a retired Django page). About 30 screens use it. Their tests assert the old href.
- `src/shell/TopNav.tsx` draws the name and role words as plain text and says there is no account menu; `src/shell/PhoneBar.tsx` has a menu disclosure with destinations only. `src/components/Menu.tsx` (`MenuButton`, `useMenuButton`), `TextField`, `Checkbox`, `Button` (busy state), `Callout` (kind `problem`, `announce`, `focusOnShow`) and `useToast` exist and are used here.
- `src/shell/useRoleWords.ts` reads `GET /role-dashboard` once when `AppShell` mounts.
- The mock: `mock/session.mjs` answers `GET /session` (scenario `401` gives a signed-out reply) and `mock/server.mjs` routes it; `tests/mock-live-me.test.ts` validates mock bodies against the live contract.

Live behaviour checked on 23 Nov against a local API-only Django (PG16, port 55433):
- `GET /session` signed out: `200 {csrf_token, signed_in:false, next_url:"/accounts/login/"}`. That `next_url` is a retired page; the page must never follow a signed-out `next_url`.
- `POST /session` with a wrong password or an unknown name: `422 {"code":"sign_in_failed","message":"Check the sign-in details."}`. No `fields`. The two cases are identical.
- `POST /session` success: `200 {csrf_token (new), signed_in:true, next_url}`. `next_url` is the request's `next_url` if it is on the same host, otherwise the person's landing page: `/` for someone with a team or visible work, `/getting-started/` for someone with neither. `//evil.example` and `https://evil.example/x` are discarded server-side. A same-host value such as `/api/v1/me` or `/accounts/login/` is returned as sent, so the page must validate too.
- `username` accepts a work email or a sign-in name (`FactorySignInForm`, `apps/core/design_views.py`).
- `remember` true keeps the session cookie past the browser (default Django session age; do not state how long). `remember` false (or absent) ends the session when the browser closes. The API has no sign-in attempt limit in code today, so 429 cannot be provoked live; it is covered by unit and mock tests.
- `GET /me/onboarding` for a person with no team and no work: `{admitted:false, can_create_workspace:false, next_url:"/getting-started/"}`. `/getting-started/` is a retired page with no frontend route.
- `POST /session/logout {}` with a stale token: `403 {code:"csrf_failed"}` and the session stays active. With a fresh token: `200 {csrf_token (new), signed_in:false, next_url:"/accounts/login/"}`. Empty body to `POST /session`: `422 invalid_input` with `fields`.

## Contract

### Route and shell
- Route `/sign-in` (`src/app/sign-in/page.tsx`, a small server page exporting `metadata.title = "Sign in"` that renders a client `SignInView`). Query `next` is optional.
- `AppShell` becomes a thin wrapper: when the path is in `PUBLIC_PATHS` (`['/sign-in']`; F-59 and F-60 add their own) it renders `children` alone with no `/me` read, no bars, no alert feed and no role-words read. Otherwise it renders the existing frame, moved unchanged into an inner `FramedShell`. Because the frame mounts fresh each time the person leaves a public path, a sign-in always reads `/me` and the role words again and a sign-out leaves no old name behind (this closes F-57 TECH-1-3).
- `DemoBar` (mock only) stays in the root layout.

### Safe destination (`src/shell/signInNext.ts`, `safeNext(value): string | null`)
Used on the `next` query before it is sent, and on the server-returned `next_url` before it is followed. Returns the value only when all of these hold, otherwise `null` (the caller then uses `/`):
- it is a string of at most 2048 characters starting with a single `/`;
- it has no `//` or `/\` at the start, no backslash, no control characters and no `:` before the first `/`, `?` or `#`, and is the same after one `decodeURIComponent` (so `/%2F%2Fevil.example` is rejected);
- its path (before `?`) is `/` or starts with one of the frame's page routes: `/my-work`, `/projects`, `/overview`, `/assistant`, `/setup`, `/clients`, `/work`, `/exceptions`, `/finance`, `/notifications`, `/settings`. It is not `/sign-in`, `/api/...`, `/accounts/...`, `/getting-started/` or any retired Django path.
The list is one exported constant next to `DESTINATIONS` in `src/shell/destinations.ts` so a new route cannot be forgotten.

### Page load
1. Show the loading state (`Loading`, "Preparing sign-in…") and call `refreshSession()` (`GET /api/v1/session`). The token comes from the response body, never from the cookie.
2. `signed_in: true` (a signed-in person opening `/sign-in`): do not show the form. Run "after sign-in" below with `next` from the query.
3. `signed_in: false`: show the form.
4. The read fails (network, 5xx, 429): show a page-level `Callout kind="problem"` "We couldn't get sign-in ready. Nothing was changed." with a "Try again" button that repeats step 1. No form until it succeeds, because a POST without a token cannot work.

### Form (default state)
- Desktop board `SCR-17-desktop`: dark brand column with "PSL FACTORY" and "Work you can see moving, from first draft to verified."; form column headed "Sign in". Phone board `SCR-17-mobile`: heading "Sign in to continue", 48px phone-size controls (`TextField phone`), full-width button. Same component, one breakpoint (the existing 720px).
- Fields: "Work email" (`TextField`, `type="text"`, `autocomplete="username"`, `autocapitalize="none"`, `spellcheck=false`; not `type="email"` because the API also accepts a sign-in name), "Password" (`type="password"`, `autocomplete="current-password"`), checkbox "Keep me signed in" (phone: "Keep me signed in on this phone"), primary button "Sign in".
- The form element has `method="post"` and `onSubmit` with `preventDefault`, so a script failure can never put the password in the address bar.
- Empty field on submit: no request; inline messages "Enter your work email." and "Enter your password." under the empty field(s), focus on the first.
- While the request runs the button is busy ("Signing in…") and ignores more presses.

### `POST /api/v1/session`
- Request (JSON, `X-CSRFToken` from the last session read): `{ "username": "<as typed, trimmed>", "password": "<as typed>", "remember": true|false, "next_url": "<safeNext(query next)>" }`. `remember` is always sent as a boolean from the checkbox (default unchecked). `next_url` is omitted when `safeNext` gives `null`.
- 200 `{csrf_token, signed_in:true, next_url}`: call `setCsrfToken(csrf_token)` at once, then "after sign-in".
- Errors, each shown in one `Callout kind="problem"` above the form (`announce`, `focusOnShow`), password field cleared, username kept, no field marked invalid:

| Result | Wording (fixed; the server message is never shown) |
|---|---|
| 422 `sign_in_failed` | "That email and password don't match." |
| 422 other (`invalid_input`) | "We couldn't read those details. Check them and try again." |
| 403 `csrf_failed` (token already refreshed by `call()`) | "Your session was refreshed. Press Sign in again. Nothing was changed." |
| 429 | "Too many sign-in tries. Try again later." |
| network failure | "We could not reach PSL Factory. Check your connection and try again." |
| 5xx, 503, any other status | "Sign-in isn't working right now. Try again in a moment. Nothing was changed." |

  No wording names a field, says whether the name exists, or contains a number of tries or a time.
- Nothing is stored: the password is not kept in state after the request, in the URL, in storage or in a log line.

### After sign-in (also used for the signed-in visit)
1. `GET /api/v1/me/onboarding` once.
2. `admitted: false`: stay on `/sign-in`, replace the form with a `Callout kind="info"` "You're signed in, but no work is open to you yet. Ask your administrator." and a "Sign out" button (same call as the menu). Do not follow `next_url` (it is `/getting-started/`). No wording about the rule behind admission (A-48 is open) and no create-workspace offer (`can_create_workspace` is not used).
3. `admitted: true`: `router.replace(safeNext(session.next_url) ?? '/')`. `/` is `HomeRedirect`, which goes to the person's first destination.
4. The onboarding read fails: fall back to step 3 (the frame itself then shows its own states).

### Sign-out (`POST /api/v1/session/logout`, body `{}`)
- Entry: desktop, the name and role words in `TopNav` become a menu button (`MenuButton`/`useMenuButton`, accessible name "Account menu: <name>") that opens a menu with a header (name, role words when known) and one item "Sign out" with detail "Signs you out on this device", drawn as `SCR-15-desktop-account`. Phone, a "Sign out" row after the destinations in the existing `PhoneBar` menu, below a separator. No other account items are added.
- 200: `setCsrfToken(csrf_token)` then `router.replace('/sign-in')` (no `next`). The old frame unmounts, so name, role words, alert feed and all page data are gone.
- 403 `csrf_failed`: stay where you are; toast "Your session was refreshed. Press Sign out again. Nothing was changed." (the token is already re-read). The request is not repeated by the app.
- Network or 5xx: stay; toast "We couldn't sign you out. Try again." The person is still signed in and the menu still works.
- The same button on the not-admitted callout above uses the same call and wording.

### Signed-out states elsewhere
- `SIGN_IN_URL` defaults to `/sign-in` and the `NEXT_PUBLIC_SIGN_IN_URL` override is removed, so no environment can point back to a retired page. `SignedOutState` builds `/sign-in?next=<encodeURIComponent(path and query)>` as today.
- `AppShell` shows `SignedOutState` (path plus `window.location.search`) for a 401 from `/me`; `FrameSignedOutState` and its "later release" sentence are deleted. The frame does not redirect by itself.

### Forgot your password, invitation
- Until F-59 the sign-in page shows "Forgot your password?" as plain text, not a link or button: "Forgot your password? Reset opens in a later release. Ask your administrator for help." It calls no recovery endpoint. F-59 replaces the sentence with a link.
- No "I have an invitation" link: the boards do not draw one, and invitations arrive as an emailed link to `/staff/join/` (F-60).

### Screen states
| State | What shows |
|---|---|
| Loading | "Preparing sign-in…" skeleton; no form |
| Ready | The form as above |
| Submitting | Busy button, fields kept |
| Error | Callout per table above on the ready form |
| Cannot get ready | Callout with "Try again" (no form) |
| Signed in, not admitted | Info callout and "Sign out" |
| Signed in, admitted | No page; redirect |

### Fixtures (mock, validated against the live contract)
- Sample sign-in accepted by the mock only: username `sample.user`, password `sample-password` (a sample, never real credentials; it is in `mock/session.mjs` and not in any build that reaches production).
- Token values: signed out `mock-csrf-signed-out`; after sign-in the persona's `me.<persona>.csrf_token`; after sign-out `mock-csrf-signed-out-2`. A token that is not the current one gets `403 {code:"csrf_failed", message}`.
- Session state in a cookie `psl_mock_session` (`in` default, `out` after logout). While `out`, `GET /me`, `/role-dashboard` and every authenticated read answer 401 and `GET /session` answers `signed_in:false`. Scenario cookies `401`, `429`, `503`, `500` also work on `POST /session` (existing mechanism); `GET /me/onboarding` answers `{admitted:true,...,next_url:"/"}` for every persona except `none`, which gets `admitted:false`, `next_url:"/getting-started/"`.
- `POST /session` returns `next_url` the way live does: the request's value when it starts with `/` and not `//`, else `/`.

## Lanes
- Frontend lane (owns all of it): `frontend/src/app/sign-in/**`, `frontend/src/features/sign-in/**` (view, form, `signInNext.ts` may sit here and be re-exported), `frontend/src/shell/AppShell.tsx`, `TopNav.tsx`, `PhoneBar.tsx`, `FrameStates.tsx`, `sample.ts`, `destinations.ts`, `frontend/mock/session.mjs`, `frontend/mock/server.mjs` (the session and logout routes and `me/onboarding` only), mock fixtures, and the tests below including the edits to the existing tests that assert `/accounts/login/`.
- Backend lane: none. No endpoint, schema or setting changes (`config/settings.py` `LOGIN_URL` stays).
- Integration owner: the builder runs the live checks (criteria 14 to 22) and records the commands and output in `build.md`.
- Shared files: `AppShell.tsx` and `FrameStates.tsx` are used by every screen, so existing frame tests must still pass untouched except for the sign-in link assertions. `frontend/src/api/live-schema.d.ts` is generated from the contract; do not edit it. `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` are not touched.

## Acceptance criteria
Verification kinds: unit = `npm test` (vitest), mock = the app on the mock (`npm run dev`, port 3000, or Playwright e2e), live = `next start` against local API-only Django. Live setup: Postgres 16 on 127.0.0.1:55433; Django `PGDATABASE=psl PGUSER=psl PGHOST=127.0.0.1 PGPORT=55433 PSL_ENV=development PSL_DJANGO_UI=0 .venv/bin/python manage.py runserver 127.0.0.1:8000`; frontend `cd frontend && NEXT_PUBLIC_API_MODE=live API_ORIGIN=http://127.0.0.1:8000 npm run build && npx next start -p 3100`; if Django answers 403 `csrf_failed` to a correct token, add `PSL_FRONTEND_ORIGINS=http://127.0.0.1:3100`. Give two local accounts a throwaway password with `manage.py shell` on the local database only: one admitted (`live-lead` or `live-multi`; confirm with `GET /me/onboarding`) and `live-none` (not admitted). Never commit these.

Page and form
1. `/sign-in` renders with no `/me` call and no top bar or phone bar. — verify: unit (render `AppShell` at `/sign-in` with a spy fetch: only `GET /api/v1/session` is called); mock (page at `/sign-in` shows the form and no "My work" link).
2. Desktop and phone layouts match `SCR-17-desktop` and `SCR-17-mobile` for the default state (brand column, headings, labels, "Keep me signed in", "Sign in" button; no "You'll go straight to INV-0412" line, no mobile footer sentence about roles). — verify: mock, design fidelity run at 1440 and 390 wide.
3. Submitting with an empty field makes no request and shows "Enter your work email." / "Enter your password." — verify: unit (no POST on the fetch spy).
4. The form has `method="post"`; submitting never changes the address bar to include the password. — verify: unit (attribute) and mock (type a password, press Enter, address stays `/sign-in`).
5. `POST /session` body is `{username, password, remember, next_url?}` with `remember` a boolean and the `X-CSRFToken` set from the last `GET /session` body. — verify: unit (assert body and header on both checkbox states).
6. Each error in the table shows exactly the fixed wording, password cleared, username kept, focus on the callout, and no number or time anywhere on the page. — verify: unit with fixtures for 422 `sign_in_failed`, 422 `invalid_input` with `fields`, 403 `csrf_failed`, 429, a thrown network error, 500 and 503; assert the server `message` text never appears; mock with the scenario cookies 429, 503 and 500.
7. A 403 `csrf_failed` re-reads the token and a second press succeeds without a reload. — verify: unit (second POST carries the new token); mock (use a wrong token via the mock's scenario).
8. A failed `GET /session` on load shows "We couldn't get sign-in ready" with "Try again" and no form; Try again recovers. — verify: unit.

Destination and redirects
9. `safeNext` rejects `https://evil.example`, `//evil.example`, `/\evil.example`, `javascript:alert(1)`, `/%2F%2Fevil.example`, `/api/v1/me`, `/accounts/login/`, `/getting-started/`, `/sign-in`, a value over 2048 characters, an empty string and a non-string; it accepts `/`, `/my-work`, `/projects/P-0101?tab=money`. — verify: unit table test.
10. `/sign-in?next=%2Fmy-work`: after a good sign-in the browser is at `/my-work`; with `next=https%3A%2F%2Fevil.example` or `next=%2F%2Fevil.example` it ends at `/` then the first destination and never leaves the site, and the POST body has no `next_url`. — verify: unit (router spy) and mock (Playwright).
11. If the server returns a `next_url` the page would not allow (`/accounts/login/`), the page goes to `/`. — verify: unit.
12. After a good sign-in as an admitted person the frame shows the new person's name and role words (not the previous person's). — verify: mock (sign in, check the top bar name and `GET /role-dashboard` called again after the sign-in; sign out, sign in as another persona via the DemoBar cookie, name changes); live (criterion 17).
13. Not admitted: after sign-in as `none` (mock) or `live-none` (live) the page stays on `/sign-in` with "You're signed in, but no work is open to you yet. Ask your administrator." and a working "Sign out"; the browser never loads `/getting-started/`. — verify: unit and live.

Live (all through `next start`, port 3100)
14. Wrong password for the admitted account: the page shows "That email and password don't match." and `POST /api/v1/session` returned 422 `sign_in_failed`. An unknown username returns a byte-identical 422 body and the same page text. — verify: live (browser, plus `curl` through the proxy comparing the two bodies).
15. Right password: `POST /session` 200, the browser goes to `/`, then the person's first destination, and `GET /api/v1/me` returns 200. — verify: live.
16. Open redirect: `http://127.0.0.1:3100/sign-in?next=//evil.example` and `?next=https://evil.example` followed by a good sign-in end on a page of the app (never another host); a `curl` `POST /api/v1/session` with `next_url:"//evil.example"` returns a `next_url` that is not `//evil.example`. — verify: live.
17. Role words: the top bar after sign-in shows the signed-in person's name and the role words from `GET /role-dashboard` without a reload. — verify: live (screenshot of the bar; the network log shows `/me` and `/role-dashboard` after the sign-in).
18. Signed-in visit: with a session, opening `/sign-in` shows no form and lands on the person's first destination (or the not-admitted message for `live-none`). — verify: live.
19. Remember: with the box ticked the session cookie has an expiry; unticked it is a session cookie (no `Expires`). — verify: live (`curl -i` through the proxy, `Set-Cookie` for `sessionid`).
20. Sign-out: from the name menu the browser goes to `/sign-in`, `GET /api/v1/me` then answers 401, and going Back to `/my-work` shows "You're signed out. Sign in" with the link `/sign-in?next=%2Fmy-work`. — verify: live.
21. Stale token on sign-out: sign in in tab A, sign in again in tab B (rotates the token), press "Sign out" in tab A: the toast "Your session was refreshed. Press Sign out again. Nothing was changed." shows, the person is still signed in (`GET /me` 200), and a second press signs out. Also `curl -X POST .../api/v1/session/logout` with a wrong `X-CSRFToken` returns 403 `csrf_failed`. — verify: live.
22. Token rotation: the `csrf_token` in the sign-in response differs from the one read before it, and the next write after sign-in (any existing write, e.g. alert settings save) succeeds with the new token. — verify: live (network log).

Menu, frame and the retired link
23. The top-bar name opens an account menu with "Sign out"; keyboard: Enter opens, arrows move, Esc closes and returns focus to the name, Tab leaves. On a phone the menu has "Sign out" after the destinations. Axe finds no violations on `/sign-in`, the open menu and the error state. — verify: mock (Playwright with `expectNoAxeViolations`, as in `e2e/frame.spec.ts`).
24. Sign-out failure keeps the person where they are: a 500 or network error shows "We couldn't sign you out. Try again." and the menu still works. — verify: unit.
25. `grep -rn "accounts/login" frontend/src frontend/tests frontend/e2e` returns only the negative assertion in `tests/next-config.test.ts` and nothing in `src`; every test and e2e spec that asserted `/accounts/login/?next=…` now asserts `/sign-in?next=…` with the same encoded path. — verify: the grep, and `npm test` passing.
26. The frame's signed-out state (401 from `/me`) shows "You're signed out." with a "Sign in" link to `/sign-in?next=<path>`, and the text "Sign-in opens in a later release" appears nowhere. — verify: unit and mock (`e2e/frame.spec.ts` updated; the old "no link" assertions at lines about 140 and 308 now expect the link).
27. Forgot password: the page shows the plain sentence, no link or button for it, and no request goes to `/accounts/recovery/*`. — verify: unit (no link by that name, fetch spy) and mock.

Mock
28. The mock answers `POST /api/v1/session` and `POST /api/v1/session/logout` with bodies that validate against the live contract (200, 422 `sign_in_failed`, 403 `csrf_failed`), rotates tokens as in Fixtures, rejects a non-current token, and `GET /me/onboarding` validates too. — verify: unit (extend `tests/mock-live-me.test.ts` pattern with the live 200 and error schemas).
29. On port 3000 a full round works: sign in with the sample pair, see the frame, sign out, land on `/sign-in`; a wrong pair shows the error. — verify: mock (Playwright `e2e/sign-in.spec.ts`).

## Out of scope
- Password reset page and recovery endpoints (F-59); invitation set-up page, `/staff/join/`, WhatsApp number step (F-60). The "Forgot your password" text must not call any recovery endpoint.
- Attempt counters ("3 tries left"), pause times ("15 minutes"), "At least 12 characters", link lifetimes, or any number the API does not return (A-46, A-47). No lockout logic in the page.
- "You'll go straight to INV-0412" or any record name before sign-in (leak, G-SCR17-2).
- Deciding who may sign in, or any sentence about which roles have accounts (the mobile footer line on the boards; A-48 open).
- The other items of the SCR-15 account menu (alert settings link, My roles, Delegate while away, Change password, the email line), the account page of `SCR-15-mobile-account`, and any change to SCR-15 alert settings or SCR-21 staff invite.
- Creating a workspace for a new person (`can_create_workspace`), `/getting-started/`.
- Automatic redirect from the frame to `/sign-in`, session-timeout detection, "switch user", remember-me duration text.
- Backend changes (signed-out `next_url` still says `/accounts/login/`, the invitation `next_url`, `LOGIN_URL`); see the leftover list.

Leftover list from the `SignedOutState` repoint (not fixed here):
- `config/settings.py` `LOGIN_URL` and `LOGOUT_REDIRECT_URL` still say `/accounts/login/`; `GET /session` signed out and `POST /session/logout` return `next_url:"/accounts/login/"`; `landing()` can return `/getting-started/`; the accept-invitation reply (F-60) returns `/accounts/login/?next=…`. Backend to move these to `/sign-in` or drop them; the page ignores them meanwhile.
- `tests/next-config.test.ts` keeps `/accounts/login` as a path the proxy must not forward; it stays.
- Any doc or guide text that names `/accounts/login/` is not edited here.

## Assumptions
- Route is `/sign-in`: short, readable, free of the retired `/accounts/` prefix the proxy no longer forwards.
- The page is reached by a public-path branch in `AppShell` rather than route groups, because moving every page into a group is a far larger change.
- After sign-out the person goes to `/sign-in` (not to the frame's signed-out state): it clears all frame data and gives the obvious next step.
- Empty-field messages ("Enter your work email.") are client-side only and reveal nothing; the boards draw no field errors.
- `next_url` is checked on our side as well as the server's because the server returns same-host values such as `/api/v1/me` or retired pages as sent.
- Not-admitted wording is deliberately plain and rule-free; A-48 stays open.
- The 429 wording "Try again later." has no number, as readiness requires; the API has no sign-in 429 today, so it is tested by mock only.
- The sample mock sign-in pair is mock-only and carries no authority.
- No automatic retry of a sign-out after `csrf_failed`, matching the frame's rule that a refreshed token never repeats the request (A-3 is unanswered).

## Conflicts with the boards
Decide once before the build starts; each has a recommendation, and the spec follows it unless told otherwise.
1. **Sign-in label.** Boards say "Work email". The API takes an email or a sign-in name, and the local test accounts have no email. Recommendation: label "Work email or sign-in name" (the server's own label). The spec draws the board's "Work email" with a text input until decided. The wrong-details message then reads "That email or sign-in name and password don't match."
2. **"You'll go straight to INV-0412, waiting for your review."** Drawn on all four boards. Removed (leak of a record name to a signed-out person, G-SCR17-2). Recommendation: leave it out; no replacement line.
3. **Attempt count and pause time** in the error board ("3 tries left before sign-in pauses for 15 minutes"). Removed (A-46, A-47). Recommendation: keep only "That email and password don't match."
4. **Mobile footer "Only PMO, Finance, HR and leadership roles have accounts. Ask your admin if you need one."** Removed: it states an admission rule the API does not return (A-48). Recommendation: leave it out, or the design engineer supplies words that name no role.
5. **"Forgot your password?"** is drawn as a link. Until F-59 it is plain text with "Reset opens in a later release. Ask your administrator for help." Recommendation: accept the plain text now; when F-59 lands it becomes the drawn link. The sentence "Ask your administrator for help" is new copy; the design engineer may prefer to drop it.
6. **Account menu (SCR-15).** The board draws Alert settings, My roles, Delegate while away, Change password and an email line besides "Sign out". Only the name header and "Sign out" are built (the other items have no screens or sources yet; the email needs `GET /account`). Recommendation: accept; add the rest with FE-ALERTS-MENU.
7. **Phone sign-out.** `SCR-15-mobile-account` is a full account page. The spec adds "Sign out" to the existing phone menu instead of a new page. Recommendation: accept; the page arrives with FE-ALERTS-MENU.
8. **Frame signed-out text.** Replaces the F-57 sentence (D-174 said "no link until SCR-17") with the shared "You're signed out. Sign in". Recommendation: accept.
9. **New states with no board:** loading ("Preparing sign-in…"), cannot get ready (with "Try again"), and signed in but not admitted (info callout with "Sign out"). Recommendation: accept as plain callouts from the design system; the design engineer may want a board for the not-admitted state.
