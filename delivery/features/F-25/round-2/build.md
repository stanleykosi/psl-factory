STATUS: READY
COMMIT: b9c62eb095afab1a2df87f562ffef833678e021c
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the five blocking UI findings (column widths, one-line cells, bold only on names and titles, phone card text sizes, card gap) and the non-blocking technical, UX and UI items listed under Fixes.
- One recorded fidelity run on all 8 boards: coverage is 100% after exceptions on all 8; visual 90.4 on SCR-29-desktop (pass) and between 76.7 and 84.3 on the other seven. Visual waivers stay a design-engineer decision.
- `delivery/checks.sh` passes (86 files, 1875 tests) and the projects plus project-tabs e2e pass (58 of 58) on this head. Still contract mock only; nothing is released.

## Changes
- `project-tabs.css`: fixed-layout milestones table (13/14/24/27/22% with five columns; 11/20/20/13/20/16% with CHANGES), `white-space: nowrap` with ellipsis on every milestones cell except CONTRACT AMOUNT; first-cell bold only for milestone names (`.ptabs__ms`) and action titles (`.ptabs__actions-table`); the "From" line is 12px, weight 400; cards use `gap: var(--space-6px)` and 14px base; milestones card main line 13px, invoice and paid lines 12px muted (`.ptabs__cardnote`); route line 18px high.
- `MilestonesTab.tsx`, `RegistersTab.tsx`, `ActionsTab.tsx`: table classes; invoice cell reads `Unknown` when `invoice.state` is absent or unlisted; one empty-state sentence via `TabEmpty` (`TabParts.tsx`).
- `ProjectJourney.tsx`: the extra `caseId` prop is gone; `ProjectTabContent` gets `journey.case_id`. The file's diff is now one import and one branch.
- Tests: `mock-project-tabs.test.ts` no longer asserts money 501; `project-tabs.test.tsx` title is "documents keeps its coming-next panel", a new case for an invoice with no or unknown state, and a check that the empty sentence appears once.
- `fidelity-exceptions.json`: the three severity-marker entries are now category "frame item"; visual waiver numbers updated from round 2.

## Fixes
- UI-1-1 | b9c62eb0 | milestones table is `table-layout: fixed` with the board's percentage widths; Registers and Actions tables are not affected.
- UI-1-2 | b9c62eb0 | no wrapping in MILESTONE, INVOICE, PAID, CHANGES (and COMPLETION); CONTRACT AMOUNT may wrap. Long values are cut with an ellipsis rather than wrapped.
- UI-1-3 | b9c62eb0 | the blanket first-cell bold rule is removed; bold only on milestone names and action titles; issue references stay weight 400.
- UI-1-4 | b9c62eb0 | phone milestone card: 13px main line, 12px muted invoice and paid lines.
- UI-1-5 | b9c62eb0 | card gap is `--space-6px`; card base 14px.
- UI-1-6 | b9c62eb0 | severity-marker exceptions have category "frame item", still "builder proposal, pending design engineer".
- UI-1-7 (part) | b9c62eb0 | route line height 18px. Moving the line above the tab bar stays out of F-25's lane.
- TECH-1-1 | b9c62eb0 | money 501 assertion dropped from `mock-project-tabs.test.ts`.
- TECH-1-2 | b9c62eb0 | test renamed to documents only.
- TECH-1-3 | b9c62eb0 | `caseId` prop removed; `journey.case_id` used.
- TECH-1-5 | b9c62eb0 | missing or unknown invoice state shows Unknown; new test.
- UX-1-1 | b9c62eb0 | the empty sentence is the heading and appears once (milestones, registers, actions, and the no-match sentence).

Left as agreed: TECH-1-4, TECH-1-6, UX-1-3 (accepted); UI-1-8, UI-1-9, UI-1-10 (frame, shared component, README, covered by waivers).

Not changed, with the reason: **UX-1-2** (due dates "4 Nov"). The boards draw "04 Nov" (SCR-29-desktop cell `04 Nov`, SCR-29-mobile `due 04 Nov`) and the shared board-date formatter `formatDayMonth` writes the two-digit day, so the page already matches the boards; boards win. If the design engineer wants "4 Nov" it is a board change plus a shared formatter change, not an F-25 change.

## Acceptance criteria
1. [ ] Desktop boards: coverage 100% after exceptions on all four; visual SCR-38-desktop 82.4, SCR-38-desktop-changed 79.1, SCR-11-desktop 82.8, SCR-29-desktop 90.4 (pass). Three below 90 with waivers proposed (open design-engineer decision).
2. [ ] Phone boards: coverage 100% after exceptions on all four; visual SCR-38-mobile 76.7, SCR-38-mobile-changed 80.8, SCR-11-mobile 77.6, SCR-29-mobile 84.3. All below 90; waivers proposed.
3. [x] Exceptions limited and explained; the markers are the only builder-proposal coverage entries (`fidelity-exceptions.json`).
4. [x] One fidelity run this round: `round-2/fidelity/` and `scores.txt`.
5-27. [x] Unchanged from round 1; the project-tabs unit, model, mock and e2e tests all pass on this head.
28. [x] This file.

Fidelity scores (coverage / with exceptions / visual), round 1 visual in brackets:
| Board | Width | Coverage | With exceptions | Visual | Pass |
|---|---|---|---|---|---|
| SCR-38-desktop | 1440 | 95.3 | 100 | 82.4 (73.1) | no |
| SCR-38-desktop-changed | 1440 | 90.5 | 100 | 79.1 (73.0) | no |
| SCR-11-desktop | 1440 | 94.0 | 100 | 82.8 (84.6) | no |
| SCR-29-desktop | 1440 | 93.3 | 100 | 90.4 (90.2) | yes |
| SCR-38-mobile | 390 | 86.4 | 100 | 76.7 (80.8) | no |
| SCR-38-mobile-changed | 390 | 75.0 | 100 | 80.8 (83.1) | no |
| SCR-11-mobile | 390 | 81.5 | 100 | 77.6 (77.7) | no |
| SCR-29-mobile | 390 | 92.6 | 100 | 84.3 (76.8) | no |

Why some scores fell: SCR-38-mobile and -changed, and SCR-11-desktop, scored a little lower although the cards now match the board's text sizes and gap (visible in `side-by-side.png`). The remaining drift is the approved extra Paid line on every card, which pushes each later card down, and the SCR-11 reference weight now matching the board. The fixes were required by the review and the numbers are as measured.

## Validation
- `bash delivery/checks.sh` on this head: exit 0, 86 test files, 1875 tests passed, lint, typecheck and production build clean. A first run during very high machine load (load average above 500) failed 28 tests in 14 files that start a mock server (timeouts); the re-run at normal load passed everything.
- `E2E_PORT=4790 MOCK_PORT=4791 npx playwright test e2e/project-tabs.spec.ts e2e/projects.spec.ts`: 58 passed, 0 failed.
- Fidelity: production build with `API_ORIGIN=http://127.0.0.1:4791`, `next start -p 4790`, mock on 4791, `--wait-ms 1500`; one recorded run. Servers stopped, `test-results` deleted, worktree clean.

## Verified
Round 1 had no `## Fixes`, so there is nothing for the reviewers to verify from my side. For round 2 the claims to retest are the Fixes above; my own evidence: column widths and one-line cells in `round-2/fidelity/SCR-38-desktop-1440/side-by-side.png` and `SCR-38-desktop-changed-1440/side-by-side.png`; card sizes and gap in `SCR-38-mobile-390/side-by-side.png`; unit tests for Unknown invoice state and the single empty sentence in `tests/project-tabs.test.tsx`.
