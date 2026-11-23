STATUS: READY
COMMIT: 473090df18b54f3897f876ef417cac262980974e
BUILDER: builder
LANE: full

## Summary
- New public page `/sign-in` (GET/POST `/api/v1/session`, fixed plain error wording, `safeNext` on `next` and on the returned `next_url`, not-admitted notice, forgot-password as plain text). `AppShell` has a `PUBLIC_PATHS` branch with no `/me`, bars or role-words read; the frame mounts fresh after sign-in (closes F-57 TECH-1-3).
- Sign out: the name in the top bar is an account menu (name, role words, "Sign out"); the phone menu has "Sign out" after the destinations; both call `POST /api/v1/session/logout`, keep the new token and go to `/sign-in`. Failures keep the person in place with a toast.
- `SIGN_IN_URL` is now `/sign-in`; the frame's 401 state uses the shared `SignedOutState`; `FrameSignedOutState` and "Sign-in opens in a later release" are gone. All `/accounts/login/?next` test assertions now say `/sign-in?next`.
- Mock: `POST /session`, `POST /session/logout`, `GET /me/onboarding`, `psl_mock_session` cookie, token rotation, 401 on every other read after logout; validated against the live contract. Sample pair `sample.user` / `sample-password`.
- Live checks 14 to 22 done against local Django (PG16 55433) through `next start` on 3100. First field label is "Work email or sign-in name" (D-177).

## Changes
- `frontend/src/app/sign-in/page.tsx`, `src/features/sign-in/{SignInView.tsx,useSignOut.ts,sign-in.css}`: the page and the shared sign-out hook.
- `src/shell/signInNext.ts` (`safeNext`), `destinations.ts` (`FRAME_ROUTES`), `sample.ts`, `FrameStates.tsx`, `AppShell.tsx` (`PUBLIC_PATHS`, inner `FramedShell`), `AccountMenu.tsx` (new), `TopNav.tsx`, `PhoneBar.tsx`, `styles/shell.css`.
- `src/api/client.ts`: `csrfHeader` constant (the live contract lists X-CSRFToken as a write parameter; the middleware sets the value; same pattern the tests already used).
- `mock/session.mjs`, `mock/server.mjs` (session/logout/onboarding routes and the signed-out gate only; `send` takes optional headers).
- Tests: new `tests/sign-in-next.test.ts` (60 cases), `tests/sign-in.test.tsx` (50), `e2e/sign-in.spec.ts` (19), extended `tests/mock-live-me.test.ts`. Edited existing tests: link assertions (`/sign-in?next=`), `shell.test.tsx`, `shell-live.test.tsx` (signed-out wording), `alerts-bell.test.tsx` and `e2e/alerts-bell.spec.ts` (the name is now a button in the Tab order and button list), `setup-rules.test.tsx` (control exclusion list), `e2e/{frame,exceptions,setup,document-review}.spec.ts` (signed-out now has a link), `cash-forecast.test.tsx` (the branch-diff `/me` guard no longer trips on `/me/onboarding`).
- Shared files touched: `AppShell`, `FrameStates`, `TopNav`, `PhoneBar`, `shell.css` (all frame-wide, as the spec says).

## Fixes
- D-178-1 | 473090df18b54f3897f876ef417cac262980974e | the forgot-password sentence is centred at both widths
- D-178-2 | 473090df18b54f3897f876ef417cac262980974e | phone brand bar on /sign-in is 52px, the board's height (wordmark line-height uses --text-fact-line); the frame phone bar is untouched (CSS is scoped to .signin-wordmark)
- D-178-3 | 473090df18b54f3897f876ef417cac262980974e | delivery/features/F-58/fidelity-exceptions.json written (INV-0412 line, Work email label, error attempt count, phone footer, forgot link); the boards' sample values are not in the tool's missing lists, so they are not listed

## Acceptance criteria
1. [x] `/sign-in`: no `/me`, no bars. Unit `sign-in.test.tsx` (spy fetch: only `GET /api/v1/session`); e2e (no navigation, no "My work" link).
2. [x] Layout, with exceptions: fidelity run once on a production build (see Fidelity). Brand column, headings, labels, checkbox and button present; no INV line, no footer sentence.
3. [x] Empty fields: no POST, both messages, focus on first (unit and e2e).
4. [x] `method="post"` (unit); Enter in the password field keeps the address at `/sign-in` (e2e).
5. [x] Body `{username (trimmed), password, remember boolean, next_url?}` and `X-CSRFToken` from the last session read, both checkbox states (unit).
6. [x] All eight error cases show the fixed wording, password cleared, username kept, focus on the callout, no digits or time, server `message` never shown (unit); mock scenarios 429, 503, 500 (e2e).
7. [x] 403 re-reads the token, second press carries it (unit; e2e with a stale first token).
8. [x] Failed session read: "We couldn't get sign-in ready" plus Try again, no form (unit, 503 and network).
9. [x] `safeNext` table, 44 rejected and 14 accepted inputs, plus 2048 boundary. Family covered: absolute, protocol-relative, backslash, encoded slashes (upper and lower hex), CR/LF/NUL/tab, spaces, dot segments (plain and encoded), `/api`, `/accounts`, `/getting-started/`, `/sign-in`, case, near-miss prefix `/my-workshop`, non-strings. A naive `startsWith('/') && !startsWith('//')` check still accepts 10 of them (`/\evil.example`, `/%2F%2Fevil.example`, `/api/v1/me`, `/accounts/login/`, `/getting-started/`, `/sign-in`, `/my-work/../api/v1/me`, newline, `/MY-WORK`, `/my-workshop`), which the tests refuse.
10. [x] `?next=/my-work` is sent and followed; evil values are not sent and end at `/` (unit; e2e; live browser: ends at `/my-work`).
11. [x] Server `next_url` of `/accounts/login/`, `/api/v1/me`, `//evil.example`, `https://evil.example/x`, `/getting-started/`, `/sign-in` goes to `/` (unit).
12. [x] New person's name and role words after sign-in: e2e (finance_lead then ceo, name changes, old name gone) and live (Lena Lead · PMO Lead, then Mo Multi · Finance Lead, no reload).
13. [x] Not admitted: unit, e2e (mock `none`), live (`live-none`): notice, working Sign out, `/getting-started/` never requested.
14. [x] Live: wrong password and unknown name both `422 {"code":"sign_in_failed","message":"Check the sign-in details."}`, bodies identical (diffed through curl); page text "That email and password don't match." for both.
15. [x] Live: right password `POST /session 200`, lands `/` then `/my-work`, `GET /api/v1/me 200`.
16. [x] Live: `next=//evil.example` and `next=https://evil.example` end at `http://127.0.0.1:3100/my-work`, only host 127.0.0.1:3100 contacted, POST has no `next_url`. curl: `//evil.example` and `https://evil.example/x` returned `/`; `/api/v1/me` returned as sent (so the page validates).
17. [x] Live: top bar "Lena Lead · PMO Lead" with no reload; network log after sign-in: `POST session 200`, `GET me/onboarding`, `GET role-dashboard`, `GET me`.
18. [x] Live: signed-in visit to `/sign-in` shows no form and lands on `/my-work`; for `live-none` shows the not-admitted notice.
19. [x] Live curl `Set-Cookie` for `sessionid`: remember true has `expires`/`Max-Age`; remember false has neither.
20. [x] Live: menu Sign out goes to `/sign-in`, `GET /me` 401, no bars; opening `/my-work` shows "You're signed out." with `/sign-in?next=%2Fmy-work`.
21. [x] Live two tabs: tab B signs in again (200), tab A Sign out shows the toast "Your session was refreshed. Press Sign out again. Nothing was changed.", `GET /me` still 200, second press signs out (`GET /me` 401). curl wrong token on logout: 403 `csrf_failed`, session still active.
22. [x] Live: the sign-in response token differs from the one read before; a write with the old token is 403, a write with a token read after sign-in is accepted (`POST /me/alert-preferences` 200, revision 1 to 2, local DB). The alert settings page itself cannot load on this local database (`missing_events`, not part of this change), so the write was made by curl through the proxy.
23. [x] Account menu: Enter opens, arrows move, Esc closes and focus returns to the name, Tab leaves; phone Sign out after the destinations and 44px or taller; axe clean on `/sign-in`, error state, open menu, phone menu, not-admitted (e2e).
24. [x] Sign-out failure (500, network, 403) keeps place, shows the toast, menu still works (unit; e2e for 500).
25. [x] `grep -rn "accounts/login" frontend/src frontend/tests frontend/e2e`: tests/next-config.test.ts line 77 and my own negative/server-reply fixtures in `tests/sign-in.test.tsx` and `tests/mock-live-me.test.ts` (the `/accounts/login/` value live returns after logout, and server `next_url` values the page must refuse). Nothing in `src`. All old link assertions now say `/sign-in?next=`. Note: these extra mentions are test data, not links; say if you want the strings built differently.
26. [x] Frame 401 shows "You're signed out." with `/sign-in?next=<path>`; the old sentence appears nowhere (unit, e2e).
27. [x] Forgot password is plain text, no link or button, no `/accounts/recovery/*` request (unit, e2e).
28. [x] Mock bodies validate against the live contract (200, 422 `sign_in_failed`, 422 `invalid_input`, 403, onboarding); token rotation and non-current-token rejection tested.
29. [x] `e2e/sign-in.spec.ts` covers a full round on the mock, a wrong pair, and persona switch.

## Validation
- `npx tsc --noEmit`, `npm run lint`: clean.
- `npx vitest run`: one clean full pass, 158 files, 3823 tests.
- Playwright sign-in, frame, alerts-bell on 4960/4961 after the last CSS changes: 91 passed. Earlier wider run (also alerts, projects, exceptions, setup, document-review): 197 passed. One failure then (alerts-bell 760px bar width with the caret) fixed by hiding the caret below 900px; that spec was not re-run after the change, nor were frame.spec at 720 to 899px beyond the earlier passing run. The later CSS changes (menu text colour, sign-in column widths) were checked by screenshot only.
- `npm run build` (production, mock origin and live origin): succeeded.
- I did not run `delivery/checks.sh` itself because it runs `npm ci`, which the notes said not to do; its other steps (django check, lint, typecheck, test, build) were run individually. `manage.py check` was not run separately.
- Servers I started on 4960, 4961, 8000 and 3100 are stopped; I left 3000 and 3001 alone.

## Fidelity (re-run once per board with fidelity-exceptions.json, production build on the mock)
Reports and side-by-side images replaced in `round-1/fidelity/`.
| Board | Coverage (with exceptions) | Visual |
|---|---|---|
| SCR-17-desktop @1440 | 100% | 86.9 |
| SCR-17-mobile @390 | 100% | 65.1 |
| SCR-17-desktop-error @1440 | 100% | 81.9 |
| SCR-17-mobile-error @390 | 100% | 59.3 |
Coverage is 100% on all four. Phone visual (65.1, 59.3) is the approved waiver for the removed content. Desktop visual (86.9, 81.9) is also under 90 and needs a waiver or decision from the design engineer: the remaining difference is the removed INV line moving the form up, empty fields where the boards show pre-filled values and a ticked box, and the longer label. Phone bar measured 52px.

## Notes for the coordinator
- Shared bug fixed once: none found in shared code.
- Design points for the design engineer: (1) the caret on the name is hidden below 900px because the 720 to 899px bar has no room (alerts-bell width tests); (2) the account menu opens directly under the bar at its right edge; (3) the toast for a sign-out failure uses the "problem" toast style.
- Leftover (not fixed, per spec): backend still returns `/accounts/login/` and `/getting-started/` as `next_url`; the page ignores them.
- Alert settings page shows "couldn't load" on the local PG16 data for every account tried (`missing_events`); unrelated to this change.

## Blocked
Not blocked.

## Worktree note
A stray untracked `node_modules/` (only `.vite` and `.vitest-cache`) appeared at the worktree root when a mistyped command ran vitest from there; the permission system refused my `rm -rf` of it, so it is still there. Delete `/Users/Hunchoo/psl-factory/node_modules` before the gate (`git status --porcelain` shows only that). A stray vitest process from that command may also still be running (task b3sq5zc2h).
