VERDICT: PASS
COMMIT: e20d2cebc4a77cd226513fbde4a3f29b9678a72c
REVIEWER: qa
AUTHORITY: integrated QA (UI-only against the contract mock; no backend exists yet)

## Summary
- Label: UI-ONLY. This is not INTEGRATED_QA_PASSED evidence. The frontend was exercised against the contract mock only, never against Django.
- Setup: `git archive` of `frontend/` at the head into a scratchpad copy (`.../scratchpad/qa`). `npm ci`, then `API_ORIGIN=http://127.0.0.1:3142 npm run build`, then mock on 3142 and `next start` on 3141. Opened on `localhost:3141` in headless Chromium (Playwright script `.../scratchpad/qa-scripts/qa.mjs`). Both processes were stopped afterwards and nothing is left listening on 3141 or 3142.
- Passed: every persona and route, the `/` redirect, all frame states (loading, 401, 403, 404, network, 500, none, route not allowed), the phone menu (Esc, link choice, focus return), the skip link, widths 390 to 1440, mock persona/scenario/CSRF behaviour, and the proxy rewrite. axe (wcag2a, 2aa, 21aa, 22aa) reported 0 violations in every state tried.
- UI-2-1 verified: wordmark left edge equals page title left edge (28) at 720, 900, 1079 and 1080; 88 at 1440; no horizontal scroll at any width tried.
- One non-blocking finding (a malformed 200 from /me crashes the app to the Next error page).
- Unproved: real sign-in and session cookie, CSRF with Django, permissions from real grants, real `/me` contents, anything on pages that are not built yet, and the production proxy path to Django.

## Findings
- QA-3-1 | non-blocking | low | frontend | A 200 response from `/api/v1/me` whose body is not the E-ME shape (tested with `{"bad":1}` through a Playwright route) is accepted as success. Expected: the "We couldn't load your account" error card, or at least no crash. Actual: pageerror `Cannot read properties of undefined (reading 'includes')`, and Next's full-page "This page couldn't load" screen with no bar and no SAMPLE DATA label. The spec's C3 only maps error bodies (`unexpected_response`), so this is outside the written contract; it matters when FE-CONNECT-1 meets a real server that drifts. Not reachable from the mock.
- QA-3-2 | non-blocking | low | frontend | Mock write endpoints do not validate request bodies: `POST /api/v1/tasks/T-1/decision` with `{}` returns 200 (verdict approve). The mock's 422 comes only from the scenario header. Not exercised by the frame (no writes yet); noted so later tasks do not trust the mock for input-validation paths.

## Verified
- UI-2-1 | verified | Browser measure of `.psl-brand` left vs `h1` left, finance_lead, `/projects`: 720 -> 28/28, 900 -> 28/28, 1079 -> 28/28, 1080 -> 28/28, 1440 -> 88/88. Document scrollWidth equals viewport width at 390, 719, 720, 900, 1079, 1080, 1440. All five links visible at 720 (name "Ada Okafor" only, width 65px); axe 0 violations at those widths.
- UI-1-1 / UI-1-2 (still hold) | verified | 720 to 1079: `.psl-nav__who` text is "Ada Okafor" (role hidden from sight; width 65). From 1080: "Ada Okafor · Finance Lead" (width 152). At 719 and below the top bar is hidden and the phone bar is shown.

## Evidence (commands, requests and results)
API through the Next rewrite (`curl localhost:3141/api/v1/...`):
- `GET /me` default: 200 Ada Okafor, 5 destinations, `csrf_token mock-csrf-finance_lead`. Cookie `psl_mock_persona=pm`: 200 Tunde Bello, `my_work, projects, assistant`. `=none`: 200 Sample Person, `destinations: []`. `=bogus`: falls back to finance_lead.
- `X-Mock-Scenario: 401|403|404` on `/me`: 401 `not_signed_in`, 403 `forbidden`, 404 `not_found`, each `{code, message}`. `409` on `/me` (not declared there): ignored, 200.
- `GET /work`, `/work/W-1`, `/work/W-1/history`: 200 fixtures. `GET /projects`: 501 `not_mocked`. Unknown path: 404 `not_found`.
- Writes (claim and decision): no token -> 403 `csrf_failed`; token of another persona (wrong user) -> 403 `csrf_failed`; matching token -> 200. Decision with `X-Mock-Scenario: 409` -> 409 `stale_revision`; `422` -> 422 `invalid`.
Browser (1440 unless stated):
- `/` redirect: finance_lead and pm -> `/my-work`; none stays on `/` with "No sections are open to your role yet. / Ask a Lead or Admin to check your roles." and the name in the bar.
- Routes: finance_lead sees all five links in order My work, Projects, Overview, Assistant, Setup; each route sets `aria-current` on its link, title `<Destination> · PSL Factory`, and the "This page is not built yet" empty state. pm sees three links; `/overview` and `/setup` show "This section isn't open to your role." with "Go to My work", no `aria-current`, and no page content (wrong role).
- Phone (390, pm): Menu button `aria-expanded` false -> true; menu lists "Tunde Bello / PM" then My work, Projects, Assistant; Esc closes it and focus returns to Menu; choosing Assistant navigates to `/assistant` and closes the menu. No Start button anywhere.
- Skip link: first Tab focuses "Skip to main content"; Enter moves focus to `main`. Focus outline is solid 2px under reduced-motion emulation.
- States: 401 shows "You're signed out." and a Sign in link to `/accounts/login/?next=%2Fprojects` (query on the path is dropped from next, only `/projects`; spec says current path). 403 shows "Your account can't use PSL Factory." plus the mock message. 404, network abort and 500 `{code:boom}` show the error card with "Reference not_found / network_error / boom for support." Try again after clearing the scenario cookie loads the full frame. Loading (delayed /me): `role=status` "Loading…", 0 nav links, SAMPLE DATA present. All these also checked at 390 with no horizontal scroll.
- SAMPLE DATA label shown in every state. No requests left localhost (no font CDN or other external calls).
- Not done: the repo's own e2e suite was not re-run here (the builder reports 24/24 and the checks gate); this QA used an independent script.

## Notes
- Per the coordinator, design-owner decisions of 13 Nov 2026 (name only 720-1079 with 28px gutter and tighter link gaps; full name · role from 1080) were taken as the expected behaviour and match what was observed.
