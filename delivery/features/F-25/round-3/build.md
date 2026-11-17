STATUS: READY
COMMIT: bde3607cd73fa2c9e106b668a40d44196cd2cb2c
BUILDER: builder
LANE: full

## Summary
- Round 3 removes the ellipsis rule from the Milestones cells: the fixed board column widths stay, and a narrower window wraps a value instead of cutting it. A new 1024px e2e proves the owed amount, invoice state, proof and change are fully visible.
- The route line uses a unitless line height (1.3); the empty-state sentence is an h2 under the page h1; waiver reasons are replaced with the UI review's texts at the new scores.
- One fidelity run on all 8 boards with board fonts loaded (no font warning in any report): coverage 100% after exceptions on all 8; SCR-29-desktop passes (90.2); seven boards stay below 90 with waivers proposed.
- checks.sh passes (86 files, 1875 tests) and the projects plus project-tabs e2e pass (59 of 59). Contract mock only; nothing is released.

## Changes
- `project-tabs.css`: deleted `.ptabs__ms td:not(:nth-child(2)) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis }`; `.ptabs__route` line-height is `1.3` (14px body gives 18.2px, as the board's 18px).
- `TabParts.tsx`: `TabEmpty` heading is `h2`.
- `e2e/project-tabs.spec.ts`: new "desktop 1024" case (changed milestones, P-0101): the four cells are visible by name, no cell has `scrollWidth > clientWidth` or an ellipsis, no sideways page scroll.
- `fidelity-exceptions.json`: every `visual_waivers` reason is the review's text; scores from round 3; still "builder proposal, pending design engineer".

## Fixes
- UI-2-1 | bde3607c | ellipsis rule deleted, fixed widths kept; narrower windows wrap.
- TECH-2-1 | bde3607c | closed by the same change; the 1024px e2e checks nothing is clipped.
- UI-2-4 | bde3607c | unitless line height instead of 18px.
- UX-2-1 | bde3607c | empty sentence is an h2.
- UI-2-2 | fidelity re-run | all 8 board renders have fonts loaded (no `Fonts:` warning in any `round-3/fidelity/*/report.json`); SCR-11-desktop is 84.8.
- UI-2-3 | fidelity-exceptions.json | waiver reasons replaced (factory file, in the main folder).

## Acceptance criteria
1. [ ] Desktop boards: coverage 100% after exceptions on all four; visual SCR-38-desktop 78.1, SCR-38-desktop-changed 75.1, SCR-11-desktop 84.8, SCR-29-desktop 90.2 (pass). Three below 90: waivers proposed, pending the design engineer.
2. [ ] Phone boards: coverage 100% after exceptions on all four; visual SCR-38-mobile 76.7, SCR-38-mobile-changed 80.8, SCR-11-mobile 77.6, SCR-29-mobile 84.3. All below 90: waivers proposed.
3-28. [x] Unchanged from rounds 1 and 2; the project-tabs tests pass on this head.

Fidelity scores, round 3 (coverage / with exceptions / visual; round 2 visual in brackets):
| Board | Width | Coverage | With exceptions | Visual |
|---|---|---|---|---|
| SCR-38-desktop | 1440 | 95.3 | 100 | 78.1 (82.4) |
| SCR-38-desktop-changed | 1440 | 90.5 | 100 | 75.1 (79.1) |
| SCR-11-desktop | 1440 | 94.0 | 100 | 84.8 (82.8, bad font render) |
| SCR-29-desktop | 1440 | 93.3 | 100 | 90.2 (90.4) |
| SCR-38-mobile | 390 | 86.4 | 100 | 76.7 (76.7) |
| SCR-38-mobile-changed | 390 | 75.0 | 100 | 80.8 (80.8) |
| SCR-11-mobile | 390 | 81.5 | 100 | 77.6 (77.6) |
| SCR-29-mobile | 390 | 92.6 | 100 | 84.3 (84.3) |

The two SCR-38 desktop boards fell by about 4 points against round 2 with the same board render. The column starts still match the board to within a pixel or two (checked in `SCR-38-desktop-1440/side-by-side.png` and `diff.png`); I did not find the cause of the remaining drop (cell text offsets and the approved frame differences are visible in the diff). The numbers are as measured and I did not tune the page to the tool.

## Validation
- `bash delivery/checks.sh` on this head (run when `uptime` was near 12): exit 0, 86 test files, 1875 tests passed, lint, typecheck and build clean. Earlier runs under machine load (average 20 to 500, other worktrees running) failed in untouched files (one `setup-rules` test, then six mock-server test files); the isolated re-run of the `setup-rules` file passed (42 tests) and the full re-run at lower load passed everything.
- `E2E_PORT=4790 MOCK_PORT=4791 npx playwright test e2e/project-tabs.spec.ts e2e/projects.spec.ts`: 59 passed, 0 failed (includes the new 1024px case). All requests go to the mock on 4791.
- Fidelity: production build with `API_ORIGIN=http://127.0.0.1:4791`, `next start -p 4790`, mock 4791, `--wait-ms 1500`; Google Fonts reachable; one recorded run in `round-3/fidelity/`. Servers stopped by PID; `test-results` deleted; worktree clean.

## Verified
- UI-2-1 / TECH-2-1: `e2e/project-tabs.spec.ts` "desktop 1024" passes on this head; `grep -n "text-overflow\|nowrap" frontend/src/features/projects/project-tabs.css` has no rule on the milestones cells.
- UX-2-1: `grep -n "<h2>" frontend/src/features/projects/TabParts.tsx` shows `TabEmpty`; the project-tabs component tests that read the empty sentence pass.
- UI-2-4: `grep -n "ptabs__route" frontend/src/features/projects/project-tabs.css` shows `line-height: 1.3`.
- UI-2-2: no report in `round-3/fidelity/` carries a `Fonts:` warning.
