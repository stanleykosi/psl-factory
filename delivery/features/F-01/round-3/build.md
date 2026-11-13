STATUS: READY
COMMIT: e20d2cebc4a77cd226513fbde4a3f29b9678a72c
BUILDER: builder
LANE: full

## Summary
- From 720px to 1079px the top bar now keeps the page's 28px side gutter. The PSL FACTORY wordmark and the page title start at the same left edge (x=28) at every width from 720px up. This fixes UI-2-1.
- To make room, only the space between the nav links got tighter at those widths. Each link's side padding went from 8px to 4px (`--space-1`). Nothing else visible changed.
- UI-1-1 and UI-1-2 still hold:
  - There is no horizontal scroll at 720, 740, 768, 820, 900, 1079, 1080, 1440 or 390.
  - From 720px to 1079px the bar shows the name in full. From 1080px it shows "name · role".
  - The role is in the accessible text at every width.
- There is a new browser test: the wordmark's left edge equals the page title's left edge (28px) at 720, 900 and 1079. The overflow tests are unchanged. The browser suite now passes 24/24.

## Design-owner decision (UI-2-1)
The design engineer decided this on 13 Nov 2026:
- Keep the edges aligned. From 720px to 1079px the top bar keeps the same 28px side gutter as the page, so the PSL FACTORY wordmark and the page title share a left edge.
- Make room by tightening only the gaps between the nav links, and nothing else visible, at those widths.

This is option (b) in the review. Option (a), recording the 16px gutter as an approved deviation, was not taken.

## Changes
- `frontend/src/styles/shell.css`, rule (f), applies from 720px to 1079.98px only:
  - The `padding: 0 var(--space-4)` override on `.psl-nav__in` is removed. The bundle's 28px gutter applies again, the same as `--space-6` on `.shell-main`.
  - Nav link side padding goes from `--space-2` (8px) to `--space-1` (4px). Link texts are now 8px apart instead of 16px. The hover and current-page underline is 4px narrower on each side, because it follows the link's box.
  - The rest of rule (f) is unchanged from round 2: the 8px gap between bar items, the hidden role span and the ellipsis as a last resort. The comment now records the decision.
- `frontend/e2e/frame.spec.ts`: a new test, "wordmark and page title share a left edge at {720, 900, 1079}px". It checks that `.psl-brand` left = 28 = `.shell-title` left, and that there is no horizontal scroll.

## Fixes
- UI-2-1 | e20d2ce | The bar gutter at 720 to 1079px is 28px again (it was 16px), and only the nav link padding tightened, from 8px to 4px.
  - Measured on the dev server (port 3101, mock on 3102), finance_lead and pm personas: the wordmark's left edge equals the title's left edge at 720, 740, 760, 768, 820, 900, 1079 and 1080 (both 28), and at 1440 (both 88).
  - `scrollWidth` equals the viewport width at all of those widths. The bar's own scrollWidth equals its clientWidth.
  - Free space left in the bar at 720px: 26px for finance_lead (5 links) and 133px for pm. With the old 8px link padding plus the 28px gutter it would have overflowed by about 14px.

Left as is (unchanged from round 2, all non-blocking): TECH-1-2, TECH-1-5 and UX-1-3, for the reasons given in round-2/build.md. The UI round-2 Notes are taste items, so I did not act on them.

## Acceptance criteria
1. [x] Gate: `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` from the worktree exits 0. Django check passes. Frontend: npm ci, lint, typecheck, "Test Files 6 passed / Tests 89 passed", and "Compiled successfully".
2. [x] Single style source: the drift tests pass. The change uses only the token `--space-1`.
3. [x] to 7. [x] Fonts, client, error mapping, CSRF and the mock contract: unchanged and passing. e2e test 1 still checks that there are no font CDN calls.
8. [x] Navigation follows /me:
   - 5 links for finance_lead and 3 for pm (e2e 1, 2 and 13 to 20).
   - From 720px to 1079px the name shows in full with the role hidden. From 1080px it shows "Ada Okafor · Finance Lead" (e2e 13 to 20).
   - The wordmark is aligned with the page title at 720, 900 and 1079 (e2e 21 to 23).
9. [x] Phone bar: no horizontal scroll at 390 (e2e 8 to 11). No horizontal scroll at 720 to 1440 (e2e 12 to 23).
10. [x] Frame states: 401, 403, none, 404 card and loading are unchanged and passing (e2e 4 to 7, 10 and 11).
11. [x] Accessibility: axe reports 0 violations, including on the bar at 720 and 1080 with the tighter links.
12. [x] SAMPLE DATA is visible in the bar at 768 (e2e 12) and in every state, as before.
13. [x] and 14. [x] Mock code stays out of the app, and there are no out-of-scope controls. Unchanged; the build passed.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0. The log is in `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/checks-r3.log`.
- Browser suite: 24 passed (38.2s). The suite builds the app, then runs the mock on 3102 and `next start` on 3101.
  - Command: `PLAYWRIGHT_BROWSERS_PATH=<scratchpad>/ms-playwright npm run test:e2e`.
- Manual measurement:
  - Dev server: `MOCK_PORT=3102 npm run dev -- -p 3101`.
  - Script: `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/measure-r3.mjs`.
  - The results are recorded under Fixes.
  - I stopped the dev server and mock afterwards. Nothing is listening on 3101 or 3102. The next-server on 3123 was not touched.
- `git status --porcelain` is empty. I pushed with `git push origin refs/heads/t-frontend-shell-nextjs-app:refs/heads/t-frontend-shell-nextjs-app` (96aa11e..e20d2ce). The commit message carries no AI attribution.

## Blocked
None.
