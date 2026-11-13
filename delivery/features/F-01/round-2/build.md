STATUS: READY
COMMIT: 96aa11efcea1cc7c596159d1b1e72aa79f2fca40
BUILDER: builder
LANE: full

## Summary
- The top bar now fits at 720px. Between 720px and 1080px the spacing is tighter and the bar shows the person's name only, on one line. From 1080px it shows the full "name · role". The role stays in the accessible text at every width. This fixes UI-1-1 and UI-1-2, and UX-1-1, which is the same issue.
- The error frame (404, server and network) now uses the STATES error card instead of the pink callout strip (UI-1-3). The card has a white surface, a 2px signal-red border, the mono eyebrow "ERROR · COULDN'T LOAD", the message, the reference line and a 50px bordered "Try again" button.
- Small non-blocking fixes:
  - TECH-1-1: a malformed cookie no longer crashes the mock.
  - TECH-1-4: the SAMPLE DATA wrapper's inline style moved into shell.css.
  - UX-1-2: unknown addresses show a plain not-found page with a link back.
  - The dev frame now also works when opened on 127.0.0.1.
- `delivery/checks.sh` exits 0, with 89 vitest tests. The browser suite passes 21/21, up from 11: the new tests cover the bar at 8 widths, the error card at 1440 and 390, and the not-found page. The branch is pushed.

## Design-owner decision (UI-1-2)
The design engineer decided this on 13 Nov 2026:
- At desktop-bar widths where "name · role" does not fit (720px up to 1080px, the bp-desktop token), show the person's name only, on one line.
- From 1080px up, show the full "name · role".
- The role must stay available to screen readers at all widths.

How it is built:
- `.psl-nav__who` now holds two spans: `.shell-who-name` and `.shell-who-role` (" · Finance Lead").
- From 720px to 1079.98px, the role span is visually hidden with the usual technique (absolute, 1px, `clip-path: inset(50%)`). Its text stays in the DOM and in the accessible text, which still reads "Ada Okafor · Finance Lead".

## Changes
- `frontend/src/shell/TopNav.tsx`: the who-line is split into name and role spans. The SAMPLE DATA wrapper uses the class `shell-navend` instead of an inline style.
- `frontend/src/styles/shell.css`, rule (f), applies from 720px to 1079.98px only:
  - bar padding goes from 28px to `--space-4` (16px)
  - the gap goes from 24px to `--space-2` (8px)
  - nav link side padding goes from 14px to `--space-2` (8px)
  - the role span is visually hidden
  - `min-width: 0` plus an ellipsis stay on the who-line as the last resort for long names

  The STATES error card rules are new (`.shell-errorcard`, `.shell-eyebrow`, `.shell-errorcard__action`, which is 200px wide on desktop and full width on phone). The unused `.shell-stack` rule is gone. Token variables only, no colours.
- `frontend/src/shell/FrameStates.tsx`: `LoadErrorState` renders the STATES card with `role="alert"`. It contains the eyebrow, the message, "Reference {code} for support." and a `psl-btn psl-btn--secondary psl-btn--lg psl-btn--block` Try again button. The "Last loaded …" part of the board's line is left out, because the frame has never loaded at that point.
- `frontend/src/shell/DestinationPage.tsx` and `frontend/src/app/not-found.tsx`: new `UnknownPage`. It uses the `.psl-empty` pattern with "This page doesn't exist." and "Go to {first destination}". The title is "Page not found · PSL Factory".
- `frontend/next.config.ts`: `allowedDevOrigins: ['127.0.0.1']`.
- `frontend/mock/server.mjs`: `decodeCookie` keeps the raw value when `decodeURIComponent` throws.
- Tests:
  - `frontend/tests/shell.test.tsx`: the who-line name and role parts for 3 personas, the error card structure for 404, 500 and network, and the not-found page.
  - `frontend/tests/mock-contract.test.ts`: the malformed-cookie case.
  - `frontend/e2e/frame.spec.ts`: the error card's look and structure at 1440 and 390, the bar at 720, 740, 768, 820, 900, 1079, 1080 and 1440, and the not-found page.

## Fixes
- UI-1-1 | 5a1289f | Compact bar spacing from 720px to 1079px. `scrollWidth` equals the viewport width at all 8 tested widths, from 720 to 1440. Before the fix it was 725 at 720.
- UI-1-2 | 5a1289f | Name only from 720px to 1079px, and "name · role" from 1080px, per the design owner's decision above. The name is fully shown with no truncation for all three personas at 720, 768, 820 and 1079. Measured name widths: Ada Okafor 65/65px, Tunde Bello 69/69px, Sample Person 88/88px.
- UX-1-1 | 5a1289f | Same fix as UI-1-2.
- UI-1-3 | 5a1289f | Error frame replaced with the STATES error card. Measured in the browser: background rgb(255,255,255), border 2px solid rgb(200,64,28), eyebrow 11px Plex Mono rgb(154,47,16), Try again 50px tall. The button is full width on phone. There is no `.psl-callout--problem` left.
- TECH-1-1 | 077ad81 | A malformed `%` cookie falls back to the default persona, and the mock keeps serving. The new test hung against the old mock and passes against the new one.
- TECH-1-4 | 5a1289f | The TopNav inline style moved to `.shell-navend` in shell.css.
- UX-1-2 | 473d833 | Added a not-found page with a link to the first destination.
- Dev on 127.0.0.1 (UI reviewer's note) | 96aa11e | This was a real dev-only defect. `next dev` logged "Blocked cross-origin request to Next.js dev resource /_next/hmr from 127.0.0.1", so the frame never hydrated and stayed on "Loading…". After adding `allowedDevOrigins: ['127.0.0.1']`, the frame loads on http://127.0.0.1:3101/my-work and the log has no "Blocked" lines. Production builds are unaffected.

Left as is:
- TECH-1-2: `API_ORIGIN` should fail closed in production builds. That belongs with FE-CONNECT-1, and the spec chose this seam.
- TECH-1-5: jsdom 31.0.1 wants Node ≥24.15, and this machine runs 24.12. Raising `engines` would not remove the warning, and pinning jsdom down means changing dependencies. The tests pass, so upgrading Node is the clean fix.
- UX-1-3: the duplicated "My work" heading is a product/design call. The spec's C5 table prescribes it.
- Loading-card eyebrow: the reviewer did not verify the loading frame. I did not change it. It still matches the spec's "grey bars + Loading…" with `role="status"`, and e2e test 7 covers it.

## Acceptance criteria
1. [x] Gate: `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` from the worktree exits 0. Django check passes. Frontend: npm ci, lint (0 warnings), tsc, "Test Files 6 passed / Tests 89 passed", and "Compiled successfully".
2. [x] Single style source: the drift tests still pass. The new shell.css rules use token variables only, apart from the 14px padding, 11px eyebrow and 200px button width copied from the STATES board.
3. [x] No font CDN calls: e2e test 1 still passes.
4. [x] to 7. [x] Client, error mapping, CSRF and the mock contract: unchanged and passing. The mock has one extra test (48).
8. [x] Navigation follows /me, re-checked on the dev server (`npm run dev -- -p 3101`, mock on 3102):
   - At 1440 the bar shows 5 links and "Ada Okafor · Finance Lead".
   - The pm persona sees 3 links.
   - From 720px to 1079px the bar shows the name only, per the design decision.
9. [x] Phone bar: unchanged and passing. There is no horizontal scroll at 390, at 720, 740, 768, 820, 900, 1079 and 1080, or at 1440.
10. [x] Frame states: 404 shows the STATES error card with "Reference not_found for support.", and Try again loads the bar (e2e 6). The card is also checked at 390 (e2e 10). 401, 403, none and loading still pass.
11. [x] Accessibility: axe (wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa) reports 0 violations on the existing pages. It also reports 0 on the bar at 720 and 1080, on the 404 card at 1440 and 390, and on the not-found page.
12. [x] SAMPLE DATA is visible in every state at both widths, including the new error card and the 720px bar.
13. [x] and 14. [x] Mock code stays out of the app, and there are no out-of-scope controls. Unchanged; the build passed.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0. The log is in `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/checks-r2.log`.
- Browser suite: 21 passed (24.3s). The suite builds the app, then starts the mock on 3102 and `next start` on 3101.
  - Command: `PLAYWRIGHT_BROWSERS_PATH=<scratchpad>/ms-playwright npx playwright install --only-shell chromium`, then `npm run test:e2e`.
  - The first run had 2 failures: `getByRole('alert')` also matched Next's route announcer. I scoped the locator to `main`, and the second run was clean.
- Manual check on the dev server, `MOCK_PORT=3102 npm run dev -- -p 3101`:
  - I measured the bar at 720 to 1440 for all three personas, on both localhost and 127.0.0.1.
  - I took screenshots of the error card at 1440 and 390, the bar at 720, 768 and 1080, and the not-found page. They are in `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/r2/`.
  - I stopped the dev server afterwards. Nothing I started is listening on 3101 or 3102. The other next-server on 3123 was not touched.
- `git status --porcelain` is empty. I pushed with `git push -u origin refs/heads/t-frontend-shell-nextjs-app:refs/heads/t-frontend-shell-nextjs-app` (f6e9a9e..96aa11e). Commit messages carry no AI attribution.

## Notes for reviewers
- From 720px to 1079px the bar gutter is 16px, while the page below keeps 28px. The bar's brand therefore sits 12px left of the page title at those widths. That is the cost of fitting five links, SAMPLE DATA and the name at 720px on one row. From 1080px both are 28px, as on SCR-01.
- At exactly 1080px, finance_lead's full "Ada Okafor · Finance Lead" fits with 0px to spare. From 1080px, rule (f) does not apply, so a much longer real role label could still overflow at 1080 to about 1100px. Revisit this with FE-CONNECT-1 when real role labels arrive.
- The not-found copy ("This page doesn't exist." and "Go to …") is new wording. The design owner may want to adjust it.

## Blocked
None.
