# The app frame and API client run on API 1.24.0 data and rules

> Tasks: FE-CONNECT-1. Architecture: live contract `contracts/psl-factory.openapi.json` 1.24.0 (answers A-1 to A-5, A-55, A-56 in `delivery/connect/backend-answers.md`; D-185). Design: no new board; reuses the F-57/F-58 frame (CMP-01, SCR-15-desktop-account, STATES boards); screens: none new.

## Summary
- Role words come from `/me` `positions[]`. The extra `GET /role-dashboard` read stops.
- The menu comes from `/me` `destinations[]` using `url` and `available`. Setup and the other entries now vary by account.
- A 403 `csrf_failed` on a keyed write refreshes `GET /session` and repeats the same request once, with the same idempotency key. Only a second failure shows a message.
- 429 `rate_limited` and 503 `read_limited` show the server's `message`.
- A download answering JSON 401 shows the frame's signed-out state. The admin role loads with no `invite_minutes`.

## Context
- `frontend/src/api/client.ts`: `api` (v7) and `liveApi` (live) share `csrfMiddleware`. `call()` after a `csrf` error runs `refreshSession()` and throws, with no repeat (the D-174 rule). The `fetch` option of `clientOptions` is the one place every request passes.
- `frontend/src/api/errors.ts`: `FIXED_MESSAGES` replaces the body message for `csrf`, `rate_limited` and `read_limited`.
- `frontend/src/shell/useRoleWords.ts` reads `GET /api/v1/role-dashboard`. `AppShell.tsx` calls it and passes `roleWords` to `TopNav`, `PhoneBar` and `AccountMenu`.
- `frontend/src/shell/destinations.ts`: `visibleDestinations()` keeps an entry when `/me` lists its key, with a fixed `href`. It ignores `url` and `available`.
- `frontend/src/shell/FrameStates.tsx` has `SignedOutState`. `AppShell.tsx` shows it when the `/me` read fails with kind `unauthenticated`.
- `frontend/src/api/live-schema.d.ts` already holds 1.24.0 `/me`: `destinations[]{key,title,django_url,url,available}` and `positions[]{role,mode,name,area,focus,workspace,team,invite_url,manage_url}`. There is no `roles[]` and no `invite_minutes`. Do not regenerate beyond this.
- Idempotency keys live in the JSON body as `idempotency_key` (for example `useStartWork.ts`, `useWorkspaceStep.ts`, `newIdempotencyKey()` in `features/start-work/intake.ts`). They are not a header. Sign-in and sign-out (`features/sign-in/useSignOut.ts`) send no key.
- Downloads today are plain anchors (`features/documents/DocumentParts.tsx` line 84, `body_url`). The six routes now answer JSON 401 when signed out.

## Contract

### Role words (A-1)
- `useRoleWords` is replaced by a pure read of `me.positions`: `roleWordsFrom(me.positions)` keeps today's rule (trimmed `name`, unique, first-seen order, joined with ", ", `null` when none). `roleWords` is available as soon as `/me` is, with no second read and no loading gap.
- `AppShell` makes no `GET /role-dashboard` call. Remove the F-57 fallback that D-172 recorded.
- Fixture: positions `[{name:"PMO Lead",mode:"lead",workspace:"pmo",...},{name:"Finance Lead",...}]` gives "PMO Lead, Finance Lead".

### Menu (A-2, A-4)
- Entry for key K shows when `/me` `destinations` has K with `available: true` and K is one of my_work, projects, overview, assistant, setup. `clients` draws no link (as today). Labels and order stay from `DESTINATIONS`.
- The link target is the entry's `url`, never `django_url` and never `work_desk_url`. Accept `url` only when it is a relative path (one leading `/`, not `//`, no backslash or control character, no dot segment) or an absolute URL whose origin equals `window.location.origin` (reduced to path+query+hash). Anything else: the entry is hidden and nothing is followed. Put this check beside `safeNext` in `shell/signInNext.ts` or `destinations.ts`, reusing its rules.
- `destinationForPath` and the current-page marker keep matching on the static path prefixes.
- If every entry is hidden the frame shows the existing `NoSectionsState`.
- Mock path (v7 `/me`, no `url`/`available`): an entry with no `url` falls back to its fixed `href` and counts as available. Live 1.24.0 always sends both.
- `visibleDestinations()` and `hasDestination()` take the new rule. `hasDestination(me,'clients')` still tests the listed key, and now also `available`.

### CSRF retry (A-3), in `src/api/client.ts`
- Applies in the shared `fetch` of `clientOptions`, so `api` and `liveApi` both get it. Do not add a second layer in `call()`.
- A request is retried only when all hold: method is POST/PUT/PATCH/DELETE; the body is JSON with a non-empty string `idempotency_key` (read from a clone made before sending), or the request has an `Idempotency-Key` header; the response is 403 with JSON `code` exactly `csrf_failed`.
- Retry: `GET /session` once (stores the new token via `setCsrfToken`), set `X-CSRFToken` on a clone of the original request, and send it. Same method, URL and body bytes, so the key is unchanged. The body is never rebuilt and no new key is made.
- The retry's own outcome is final: success returns normally; any failure, including a second `csrf_failed`, is returned as that response and mapped as usual. No third attempt. If `GET /session` itself fails, return the original 403 (it maps to kind `csrf`).
- Never retried: other 403 codes, 401, 409, 422, 429, 5xx, network errors, GETs, and any write with no key (sign-in, sign-out, keyless writes such as E-RESPONSE and the workspace assign). For those the F-57/F-58 behaviour stays: kind `csrf`, one `refreshSession()` so the next press works, and the same toast or line.
- After a failed retry `call()` makes no further `GET /session`. Total `/session` reads per failing keyed write: one.
- Error text for kind `csrf` (second failure, or keyless write): see Question 1. The old "Press the action again" line is not shown for a keyed write on first failure, because the client repeats it itself.

### Limit errors (A-5)
- 429 `rate_limited` and 503 `read_limited`: `ApiError.message` is the body `message` and `code` the body `code`. When the body is malformed, keep today's fixed fallback text (`Too many requests. Try again shortly.` and `This needs a closer look and could not load. Try again shortly.`). `Retry-After` is neither required nor shown.

### Downloads (A-55)
- New in `src/api`: `download(url)`: same-origin GET with credentials. 2xx returns the `Blob` and the filename from `Content-Disposition` when present. A JSON 401 throws `ApiError` kind `unauthenticated` and calls a signed-out notifier. Any other failure maps through `errorFromResponse`. The client never expects or follows a 302.
- `AppShell` subscribes to the notifier (`onSignedOut` exported from `client.ts`). On it, the main area shows `SignedOutState` (copy unchanged: "You're signed out. Sign in" linking to `/sign-in?next=<current path>`) and the bars drop the name and menu as on a failed `/me`. The subscription is removed on unmount.
- Fixture: `GET /cases/c1/files/u1/` answers `401 {"code":"unauthenticated","message":"..."}`.

### Admin without `invite_minutes` (A-56)
- No code reads `invite_minutes`. A `/me` for an admin position (`role:"admin"`, `mode:"administrator"`, `invite_url:null`) renders the frame normally. With the dashboard read removed, a 422 there can no longer blank the frame.

### Screen states of the frame
- Loading: `LoadingState`, unchanged. Role words need no state of their own.
- Error on `/me`: `LoadErrorState` for server or network; `ForbiddenState` for 403; `SignedOutState` for 401. Unchanged.
- Empty: `NoSectionsState` when no entry is shown.
- Success: bars with the allowed menu, the name and the role words.

## Lanes
- Frontend lane A owns `frontend/src/api/client.ts`, `errors.ts`, `types.ts`, `frontend/src/shell/*` and the tests named below. Backend lane: none (no endpoint changes). Integration owner: merge order only.
- Shared files: `frontend/tests/destinations.ts` and `frontend/tests/shell-live.test.tsx` are being changed by the F-68 hotfix (branch `fe-connect-1-main-green-api-1-24`, which makes the 1.24.0 fixtures compile). Build F-67 on top of F-68 once merged and keep its fixture shapes; do not fork them.
- Do not edit `delivery/checks.sh`, `delivery/config.json` or `delivery/merge-policy.json`.

## Acceptance criteria
1. A `/me` with positions "PMO Lead" and "Finance Lead" shows "PMO Lead, Finance Lead" beside the name on both bars. The page makes no `GET /api/v1/role-dashboard` call. — verify: `frontend/tests/shell-live.test.tsx`, fetch stub calls contain no `/role-dashboard`; the account menu header shows the names.
2. A `/me` with no positions shows the name only, with no stray separator. — verify: same test file.
3. Destinations `my_work` (available), `setup` (`available:false`) show only My work in the menu; Setup is not in the bar or the phone menu. — verify: shell test reads link names on both bars.
4. Each link's `href` equals the destination `url`. A `django_url` of `/retired/` and a `work_desk_url` never appear in any `href`. — verify: shell test asserts hrefs and greps rendered HTML.
5. A destination `url` of `https://evil.example/x`, `//evil.example`, or `javascript:alert(1)` is not rendered as a link. A same-origin absolute URL becomes its path. — verify: unit test of the url check.
6. All destinations unavailable shows "No sections are open to your role yet." — verify: shell test.
7. A keyed POST (body has `idempotency_key: "k1"`) answering 403 `csrf_failed` then 200 sends exactly: POST, `GET /api/v1/session`, POST. Both POSTs carry byte-identical bodies with `k1`; the second carries the new token from the session read; the caller gets the 200 data. — verify: `frontend/tests/client.test.ts` fetch stub call log.
8. Two `csrf_failed` answers in a row give an error of kind `csrf` after exactly two POSTs and one `/session` read; no third POST. — verify: client test.
9. A 403 with another code (`forbidden`), a 401, a 409, a 422, a 429 and a 503 on a keyed write each cause exactly one POST and no `/session` read. — verify: client test, table-driven.
10. A keyed write whose retry returns 409 `idempotency_conflict` or 422 surfaces that error normally. A failing `GET /session` surfaces kind `csrf` after one POST. — verify: client test.
11. Duplicate-effect check: a stub backend that runs the handler only on non-403 answers and counts effects for key `k1` shows one effect after a `csrf_failed` then success. — verify: client test asserts count is 1.
12. A write with no `idempotency_key` (sign-out `POST /api/v1/session/logout`) answering `csrf_failed` is sent once, refreshes the token once, and keeps the existing toast. — verify: `frontend/tests/sign-in.test.tsx` and client test.
13. A GET is never retried on `csrf_failed`. A multipart or non-JSON body write is never retried. — verify: client test.
14. A 429 body `{code:"rate_limited",message:"Slow down for 30 seconds."}` gives an error whose message is that text and code `rate_limited`; the same for 503 `read_limited`. A 429 with an HTML body gives the fixed fallback text. A response with no `Retry-After` header causes no error. — verify: `frontend/tests/client.test.ts`.
15. `download('/cases/c1/files/u1/')` answering 401 JSON throws kind `unauthenticated` and the frame main area shows "You're signed out." with a Sign in link to `/sign-in?next=...`. No redirect is followed. — verify: client test plus a shell test that triggers the notifier.
16. `download` answering 200 returns the blob; 403 and 404 map to `forbidden` and `not_found` and do not show the signed-out state. — verify: client test.
17. An admin `/me` with no `invite_minutes` anywhere renders the frame with the Admin role words. — verify: shell test.
18. The v7 mock path still works: with a v7 `/me` (no `url`, no `available`) the five links appear at their fixed paths. — verify: `frontend/tests/shell.test.tsx` passes unchanged.
19. `npm run gen:api:live` produces no diff in `src/api/live-schema.d.ts`. — verify: `git diff --exit-code frontend/src/api/live-schema.d.ts` after running it.

## Out of scope
- Any screen's own writes or copy, alerts, Setup screens, new boards, backend changes, types regeneration beyond what 1.24.0 already generates.
- Converting the download anchor in `features/documents/DocumentParts.tsx` (outside src/api and src/shell) to use `download()`. Until that follow-up, a signed-out click on that link shows the browser's JSON 401 page. Needs a ticket for the documents lane.
- Retrying keyless writes (sign-in, sign-out) after `csrf_failed`; changing `useSignOut` toast text.
- Showing `Retry-After`, a countdown, or any mode/workspace words in the bar.
- Hiding or gating pages by `available` beyond the menu: screens keep their own 403 handling.
- A `roles[]` fallback or any read of `django_url` or `work_desk_url`.

## Questions for the design engineer
1. Wording when a keyed write fails `csrf_failed` twice (and for keyless writes). Recommendation: "Your session could not be refreshed. Reload the page and try again. Nothing was changed." in the existing error spot or toast. Alternative: keep the old "Your session was refreshed. Press the action again. Nothing was changed." for keyless writes only.
2. Role words: recommendation is names only, as the boards draw (A-1 also offers mode and workspace). Alternative: add workspace as small text in the account-menu header.
3. A 429 or 503 message from the server is shown as the server writes it. Recommendation: show it as is in the existing error or toast spot. Alternative: a fixed PSL sentence with the server text as the reference line.
4. When a download hits a signed-out session, recommendation: replace the main area with the signed-out callout (as on `/me`). Alternative: a toast with a Sign in link that keeps the page.

## Conflicts with the boards
- The menu now varies by account, while the site map (SITEMAP-desktop) and CMP-01 draw five links. Recommendation: accept; A-2/D-185 requires it and CMP-01 draws the full set only as the widest case.
- The csrf line "Your session was refreshed. Press the action again" disappears for keyed writes and the STATES/toast boards draw it. Recommendation: accept and update the board with Question 1's wording.
- Signed-out download uses the existing signed-out callout; no board draws it for a download. Recommendation: accept (Question 4).
- Role words: no change to the boards.

## Assumptions
- Keyless writes are not retried, though A-3 would allow it: readiness requires a key and sign-in/out are the only keyless writes in this scope.
- Detecting the key: JSON body `idempotency_key` or `Idempotency-Key` header, because that is how every keyed write in the code sends it.
- An unsafe destination `url` hides that entry instead of falling back to a fixed path, so a bad response cannot send the person somewhere unexpected.
- A missing `url` or `available` (v7 mock) is treated as the fixed path and available, so the mock keeps working.
- Role words stay "names only" (Question 2) so no board changes.
- After a failed retry, no extra `/session` read: the one already made holds the newest token.
- The download helper lives in `src/api` and the shell reacts through a notifier because only those two folders are in scope.
