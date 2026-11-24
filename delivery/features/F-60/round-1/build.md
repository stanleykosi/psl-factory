STATUS: READY
COMMIT: 4a11ce3fad40faff4ec8634923caf253a05ea6e4
BUILDER: builder
LANE: full

## Summary
- New public page `/staff/join/` reads the invitation token from the URL fragment, clears it from the address bar, previews the invitation and lets the person choose a password (preview, then accept). Every D-182 recommended option is built; ready state is a plain heading and a "Sign in" link (D-151).
- Shared `BrandColumn.tsx`, `NewPasswordFields.tsx` (optional `hint`) and `useAfterSignIn.tsx` (extracted `afterSignIn` and the not-admitted body) created in `src/features/sign-in/`; `SignInView` uses them, behaviour unchanged (F-58 tests pass unedited).
- The mock gains the two invitation routes in the live shape (`mock/invitations.mjs`, fixture tokens `v m e u r`).
- Criteria 17, 19 and 22 are unproven live, mock-only by the design engineer's answer: "Mock-only for those three". Fidelity is NOT clean: see Validation (coverage 60% with the spec's exceptions; proposed extra exceptions listed, not applied).

## Changes
- `frontend/src/features/sign-in/BrandColumn.tsx`, `NewPasswordFields.tsx`, `useAfterSignIn.tsx`: new shared files (F-59 reuses). `SignInView.tsx`: edited only to use them.
- `frontend/src/features/join/JoinView.tsx`, `signInTarget.ts`, `welcome.ts`, `join.css`: the page, the strict `next_url` check, welcome sentences (access in bold, as the board), Lagos-time validity line.
- `frontend/src/app/staff/join/page.tsx`: route, title "Set up your account", `referrer: 'no-referrer'`.
- `frontend/src/shell/AppShell.tsx`: `/staff/join` added to `PUBLIC_PATHS` (shared file; one entry).
- `frontend/mock/invitations.mjs` (new), `mock/server.mjs` (two routes, reset hook, invitation paths exempt from the signed-out 401), `mock/session.mjs` (exports `currentToken`).
- Tests: `tests/join.test.tsx`, `tests/join-target.test.ts`, `tests/mock-invitations.test.ts`, `e2e/join.spec.ts`.
- `/Users/Hunchoo/psl-factory-main/delivery/features/F-60/fidelity-exceptions.json`: the spec's four entries, approved_by "design engineer, 23 Nov 2026, D-182".
- Shared-file note (checklist 9): `AppShell.tsx` and `SignInView.tsx` only as above. No Workspace/InlineDecide files touched.

## Fixes
- none (round 1)

## Acceptance criteria
1. [x] No `/me` call, no bars: unit (`join.test.tsx`, only session read + preview) and e2e (no navigation).
2. [x] Fragment cleared; token in no URL, storage, cookie or console; only in the two JSON bodies: unit (replaceState, storage and console spies, request URLs and bodies) and e2e.
3. [x] No fragment / wrong length / other characters: unavailable state, no request (7 unit cases).
4. [x] `referrer: 'no-referrer'` in page metadata (unit reads source) and `meta[name=referrer]` is `no-referrer` (e2e).
5. [x] Reload after clearing shows unavailable (e2e).
6. [x] Welcome line, validity line, read-only email, hint, confirm, "Finish setup"; two-group and three-workspace wording: unit and e2e.
7. [~] Layouts vs boards: see fidelity. `grep` for `72 hours|WhatsApp|review_alerts` in `src/features/join` is empty (unit asserts it). Fidelity coverage not 100% (see Validation).
8. [x] Expired, used, unknown: identical unavailable markup (unit snapshot compare; e2e compares text for e, u, x); text says "may have expired".
9. [x] `<b>x</b>` name shown literally (unit).
10. [x] 429, 503, 500, network on preview: "We couldn’t open your invitation…" with Try again; recovers (unit and e2e scenario cookies).
11. [x] Three client messages, focus on the right field, no accept request (unit).
12. [x] Accept body exactly `{token,password,confirm}` with the last session token; form `method="post"`; Enter keeps the address (unit and e2e).
13. [x] Each accept failure row (invalid_input with/without fields, unknown field into callout, action_unavailable with preview recheck, renewed token to unavailable, invitation_unavailable, csrf twice, 429, 500, 503, network with "try signing in" sentence), both fields cleared, email kept (unit, one per row; e2e for short password, mismatch, 503, renewed).
13a. [x] One automatic csrf retry with the same body and a new token; two failures show "Press Finish setup again" (unit counts two accept calls).
14. [x] Ready state: heading "Your account is ready." focused, "Sign in with sola.martins@psl.example.", Sign in link to `/sign-in`, no callout; reused token shows unavailable (unit, e2e desktop and phone); `no-success-callouts` test passes in the full run.
14a. [x] `signInTarget` family (22 refusing inputs, one accepting) in `join-target.test.ts`.
15. [x] `signed_in: true` after accept: admitted goes to safe `next_url` or `/`, never `https://evil.example`, `/accounts/login/`, `//evil.example`; not admitted shows F-58 notice with working Sign out (unit).
16. [x] `SignInView` unchanged in behaviour: `sign-in.test.tsx`, `sign-in-next.test.ts` and `e2e/sign-in.spec.ts` pass unedited.
17. [ ] Not proved live: unproven live, mock-only by the design engineer's answer: "Mock-only for those three". Proved on the mock (preview shows returned name, email, expiry, workspaces).
18. [x] Live: curl shows server-side refusal paths below; page has no length check (unit greps `.length` out of `NewPasswordFields.tsx` and the join sources). A short-password refusal against a real invitation was not seen live; mock path covers the message display.
19. [ ] Not proved live: unproven live, mock-only by the design engineer's answer: "Mock-only for those three". Proved on the mock: set-up reaches the ready state with a link to `/sign-in`.
20. [~] Live: an unknown 43-character token previews as 422 `invitation_unavailable` (curl below). Used, expired and superseded real tokens were not exercised live (no invitation); mock fixtures `e u r` cover the page.
21. [x] Live curl: random token gets the 422 unavailable body; missing or wrong `X-CSRFToken` gives 403 `csrf_failed` on preview and accept.
22. [ ] Not proved live: unproven live, mock-only by the design engineer's answer: "Mock-only for those three". Mock: a used token becomes unavailable on the second visit (e2e).
23. [x] Axe clean on ready, field-error, page-error, unavailable and ready-done, desktop and phone (e2e); keyboard order email, New password, Confirm, Finish setup; problem callout takes focus.
24. [x] `staff/join` not in `next.config.ts` (unit grep); `next-config.test.ts` passes in the full run.
25a. [x] Hint present once, linked by `aria-describedby`; none rendered when not passed (unit).
25. [x] Mock responses validate against the live contract (preview 200, accept 201, 422 shapes, 403) and reject a non-current token (`mock-invitations.test.ts`).

## Validation
- `npx tsc --noEmit`, `npx eslint . --max-warnings 0`: clean.
- Full `npx vitest run` (through the lock): 164 files, 3948 tests passed.
- `npx playwright test e2e/join.spec.ts` (through the lock, after the e2e fix in 1de80870): 13 passed. The earlier run of join plus sign-in specs had `sign-in.spec.ts` all passing and 4 join failures, all test setup (Next redirects `/staff/join/` to `/staff/join`; the mock starts signed in): fixed in the test, not the page.
- `delivery/checks.sh` not run by me (the gate does that).
- Live curl against local Django (API-only, port 8004, Postgres 55433, now stopped):
  - preview, unknown 43-char token: 422 `{"code":"invitation_unavailable","message":"This invitation is unavailable."}`
  - preview, token `short`: 422 `invalid_input` with `fields:[{name:"token",...}]`
  - preview with no CSRF header: 403 `csrf_failed`
  - accept with wrong CSRF header: 403 `csrf_failed`
  - accept, unknown token, good password pair: 422 `action_unavailable` "This invitation is unavailable." (not `invitation_unavailable`; the page settles it with a preview recheck, as specced)
- No real invitation was created: qa-seed has no invite authority (403), and I did not use any other route.
- Fidelity: one run per board on a production build (`API_ORIGIN` set at build, mock 4967, app 4966), reports in `round-1/fidelity/`. A first run on a build without `API_ORIGIN` never reached the form (preview failed) and is discarded.

| Board | Coverage with exceptions | Visual |
|---|---|---|
| SCR-17-desktop-setup @1440 | 60% (6/10) | 90.1 |
| SCR-17-mobile-setup @390 | 60% (6/10) | 55.6 |

  The 4 unmatched board items on both boards are: `sola.martins@psl.example`, `••••••••••••` (the values drawn inside the board's input boxes; the page shows them as input values the tool does not read as text), `+234 802 *** 1190` and "We'll send a code to check it. You can change this later." (WhatsApp, removed per D-182 Q2). The spec's WhatsApp exception names a textbox label; the tool lists the value and sentence as Text. Proposed for the design engineer, NOT applied: add exceptions for these four Text items ("input values the tool cannot read" for the email and dots; "removed content, D-182 Q2 a" for the two WhatsApp items). The two spec exceptions "Welcome, Sola…" and "This invitation works until <date>." matched as text (welcome at 96% similarity, validity line listed as extra); "Confirm new password" listed as extra. Phone visual 55.6 is below 90: the board draws a full-width dark brand band at the top; I did not iterate (one run). Not a waiver request; the design engineer decides. Small differences the tool names: heading 32px vs board 30px (desktop), 26 vs 24 (phone), small text 14px vs 12px: these are the shared sign-in tokens (F-58 settled).
- Servers: Django 8004 (PID 35000) stopped; 4966 and 4967 are no longer listening; 3000 and 3001 untouched.

## Blocked
Not blocked. Open for the coordinator: criteria 17, 19, 22 mock-only by the design engineer's answer; fidelity coverage 60% pending the extra exceptions above; phone visual 55.6.

## Coordinator merge of main 3b7df6cc
- Merged as 4a11ce3f with no conflicts; package-lock.json unchanged; `npx tsc --noEmit` reports 0 errors.
