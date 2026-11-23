STATUS: READY
COMMIT: 5262fbd45ea1743f1bbde3e0c5fc07eaa992e732
BUILDER: builder
LANE: full

## Summary
- Role words in the top bar now shorten with an ellipsis at every desktop width, so five long role names no longer push Start work off the bar or make the page scroll sideways.
- The full "name · roles" text stays in the bar's title and in the accessible text.
- The session read (`refreshSession`) no longer refreshes itself, so a `csrf_failed` answer from GET /session cannot loop.
- TECH-1-2, TECH-1-3, UX-1-1 and UX-1-2 are untouched, as asked.

## Changes
- frontend/src/styles/shell.css: `.psl-nav__who` gets `min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap` at all widths. The same rule is removed from the 720-1079px media query, where it was the only place it applied.
- frontend/src/shell/TopNav.tsx: `title` on the who span holds "name · role words" when there are role words.
- frontend/src/api/client.ts: `call(operation, refreshOnCsrf = true)`. `refreshSession` passes false.
- frontend/tests/client.test.ts: new unit test, GET /session answering 403 csrf_failed makes one session call and rejects with kind csrf.
- frontend/e2e/frame.spec.ts: two new tests (1440, 1280) with five long role names (role-dashboard routed in the page).

## Fixes
- UI-1-1 | 5262fbd4 | role words capped with an ellipsis at every desktop width; title keeps the full words
- TECH-1-1 | 5262fbd4 | refreshSession no longer re-enters itself on csrf_failed; unit test added

## Acceptance criteria
1. [x] Five long role names do not overflow the 1440 or 1280 bar: the new e2e tests check document scrollWidth equals the viewport, Start work's right edge is inside the viewport, the who line is one line and clipped, and the title and bar text hold the full words.
2. [x] Name-only and one role look as before: the existing "top bar at N px fits" tests (720 to 1440, one role "Ada Okafor · Finance Lead") and the name-only persona tests still pass.
3. [x] No recursion on csrf_failed from /session: the new unit test shows one session request.

## Validation
- `npm run lint`, `npm run typecheck`: clean.
- `npm test` (vitest, full): 156 files, 3706 tests passed.
- `E2E_PORT=4960 MOCK_PORT=4961 npx playwright test e2e/frame.spec.ts` (runs a production `next build` first): 27 passed.
- I did not run checks.sh, because it runs `npm ci` and I was told not to. The Django check is unchanged by this round.
- Fidelity tool not run: only truncation of the existing role span changed; no board geometry moved. The temp logs are deleted. Disk stays at 3.8 GB.
- I did not run the new e2e tests against the old CSS to see them fail.

## Blocked
None.
