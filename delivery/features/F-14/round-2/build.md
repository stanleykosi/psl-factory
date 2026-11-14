STATUS: READY
COMMIT: 5b9605a81d197187056995c793c626b1b3c2c55d
BUILDER: builder
LANE: frontend

## Summary
- Round 2 follows D-41 (follow the boards). Visual is at least 90 on 24 of 26 boards; coverage after exceptions is 100 on all 26. Round 1 had 6 of 26.
- Two boards stay under 90 and need F-09: desktop awaiting-reconciliation (87.7) and mobile awaiting-reconciliation (80.0). What is left on them is F-09's reconcile panel (callout, three radio choices, Record and continue). Drawing it would be new behaviour, so I stopped there.
- Overviews no longer draw the Overview/History tabs or a separate next-step block. The next-step text stays in the page for screen readers (`NextStep` keeps its name and props, with a marked F-06 slot inside its text). History is reached only as the history board draws it.
- Phones pin the action bar to the bottom of the screen, draw the reference in the frame's bar, use the phone boards' titles, wording and cut station lists, and show the full-pose mascots on the waiting and processing boards.
- F-09 seams are unchanged: `TaskPanels({ id, tasks })` props, one "Open the decision" expression, one ReconcilePanel slot. All 403 unit tests pass and the 82 e2e tests pass.

## Changes
- `frontend/src/features/work-item/WorkItemOverview.tsx`
  - Board layouts drop the visible next-step block. `NextStep` renders inside a `work-sr` wrapper; the F-06 slot is a comment inside its text.
  - Blocks a board does not draw (stations on the issue boards, the agent where none is drawn) stay in the page for screen readers only. Hidden station lists are not focusable.
  - Phone station lists can be cut to the first N stations (`stations_shown`); the rest stay for screen readers.
  - The limits line "Cannot approve, send or pay." is visible only where the board draws it (default desktop board, with its own text); elsewhere it is for screen readers.
  - Full-pose mascots on the waiting banner and the processing panel. The phone waiting note sets its first sentence in bold. The "Read:" prefix on step sources is for screen readers only.
  - The phone bar is a real bar for each state, or an empty room kept for another feature's control (`bar_slot`). The default board's phone decision panel is drawn as the pinned bar, with only the "Open the decision" link visible.
- `WorkItemView.tsx`: the reference-and-client eyebrow replaces the breadcrumb on the state boards. The revision is for screen readers when the board draws no started line. Tabs show only on history and on items without a board. On phones the reference (or HISTORY) sits at the end of the frame's bar, and phone titles come from the phone block.
- `WorkItemHistory.tsx`: on the desktop board, rows per page and "As of" sit in the side column. On the phone board the cards drop the kind chip and extra lines (still for screen readers), the list shows the five newest entries, and "+ N earlier entries" reveals the rest in place.
- `presentation.ts` and `labels.ts`: new optional PROPOSAL fields `eyebrow`, `phone` (a block that replaces desktop fields below 720px, plus `title`), `stations_shown`, `agent.limits`, `agent.plain`, `panel.large_title`, `panel.bar_slot`, `panel.bar_note`; `viewFor` and `agentPose`.
- `work-item.css`: header and spacing measured against the boards, the pinned phone bar, banner and panel sizes, the default decision card's room (with its small print inside), the issue board's column widths, and the no-access card (700px wide, 33px title).
- `frontend/public/agents/chidi-working.png` and `tola-waiting.png` (77 KB each), resized from `design/mascots/transparent/finance-working.png` and `design/mascots/web/pmo-waiting.png`. These are the images the processing and waiting boards use.
- Fixtures `W-1701` to `W-1709` and `W-1711`: eyebrows and phone blocks.
- Tests: mock-contract schema covers the new fields. New unit tests: no tabs or visible next step on board overviews, and the eyebrow on the state boards. The history tests expect five cards, then seven after "+ 2 earlier entries". The agent-card test finds the mascot by name prefix. e2e: the no-access title is 33px, the history focus test reaches Overview from the history page, and the phone history test expects five then seven cards.

## Fixes
- FID-1-1 | 5b9605a | 24 of 26 boards are at visual 90 or more (lowest: desktop issue 90.4). The two awaiting-reconciliation boards remain, see Blocked.

## Acceptance criteria
1. [ ] Desktop fidelity: coverage after exceptions is 100 on all 13. Visual is at least 90 on 12 of 13; desktop awaiting-reconciliation is 87.7 (F-09's panel).
2. [ ] Phone fidelity: coverage after exceptions is 100 on all 13. Visual is at least 90 on 12 of 13; mobile awaiting-reconciliation is 80.0 (F-09's panel).
3. [x] Exceptions: `fidelity-exceptions.json` is unchanged. Some entries (the five REF · CLIENT eyebrows, the tablist, the "Documents 2" tab) now match what the boards draw and are unused.
4. [x] Acceptance criteria 4 to 24 of round 1 still hold where D-41 did not change them. Changed by D-41: AC 12 (each board renders `NextStep`: it is present but visually hidden), and the Overview/History tabs on overviews (removed).

## Fidelity (production build on 4501, mock on 4502; `round-2/fidelity/<board>-<width>/`)
| board | width | coverage (raw / with exceptions) | visual | pass |
|---|---|---|---|---|
| SCR-02-desktop | 1440 | 70.7 / 100 | 91.6 | yes |
| SCR-02-mobile | 390 | 80 / 100 | 97.9 | yes |
| SCR-02-desktop-ready | 1440 | 90 / 100 | 97.1 | yes |
| SCR-02-mobile-ready | 390 | 88.9 / 100 | 98.6 | yes |
| SCR-02-desktop-processing | 1440 | 87.1 / 100 | 94.4 | yes |
| SCR-02-mobile-processing | 390 | 90 / 100 | 93.4 | yes |
| SCR-02-desktop-waiting | 1440 | 84.4 / 100 | 94 | yes |
| SCR-02-mobile-waiting | 390 | 78.9 / 100 | 91.7 | yes |
| SCR-02-desktop-verified | 1440 | 94.5 / 100 | 93.8 | yes |
| SCR-02-mobile-verified | 390 | 94.1 / 100 | 92.4 | yes |
| SCR-02-desktop-history | 1440 | 78.6 / 100 | 95.6 | yes |
| SCR-02-mobile-history | 390 | 95.5 / 100 | 97.2 | yes |
| SCR-02-desktop-issue | 1440 | 90.2 / 100 | 90.4 | yes |
| SCR-02-mobile-issue | 390 | 87 / 100 | 91.1 | yes |
| SCR-02-desktop-cancelled | 1440 | 93.8 / 100 | 95.2 | yes |
| SCR-02-mobile-cancelled | 390 | 94.4 / 100 | 97.9 | yes |
| SCR-02-desktop-owner-needed | 1440 | 94.5 / 100 | 92.1 | yes |
| SCR-02-mobile-owner-needed | 390 | 95 / 100 | 99.5 | yes |
| SCR-02-desktop-setup-needed | 1440 | 90 / 100 | 91.7 | yes |
| SCR-02-mobile-setup-needed | 390 | 88.9 / 100 | 97.8 | yes |
| SCR-02-desktop-permission | 1440 | 70.6 / 100 | 95.5 | yes |
| SCR-02-mobile-permission | 390 | 71.4 / 100 | 98.8 | yes |
| SCR-02-desktop-effect-uncertain | 1440 | 93.5 / 100 | 94.1 | yes |
| SCR-02-mobile-effect-uncertain | 390 | 94.4 / 100 | 98.1 | yes |
| SCR-02-desktop-awaiting-reconciliation | 1440 | 70.6 / 100 | 87.7 | no |
| SCR-02-mobile-awaiting-reconciliation | 390 | 59.3 / 100 | 80 | no |

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-14 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 (lint, typecheck, vitest 15 files, 403 tests, `next build`).
- `cd frontend && E2E_PORT=4501 MOCK_PORT=4502 npx playwright test e2e/work-item.spec.ts e2e/work-item-board.spec.ts e2e/decide.spec.ts`: 82 passed.
- Fidelity: `round-1/fidelity/_driver/prod.sh`, then `runall.sh`; only report.json and side-by-side.png per board are stored. Servers on 4501 and 4502 are stopped; `frontend/test-results` is deleted. Disk: 7.3 GB free.
- I did not merge dlv-00-delivery-setup into the branch.

## Blocked
Not blocked. Two boards cannot reach 90 without F-09's reconcile panel:
- desktop awaiting-reconciliation (87.7): the whole right column is the panel (heading, text, three radio choices, Record and continue, small print). The left side matches the board.
- mobile awaiting-reconciliation (80.0): the callout, the three choice boxes and the pinned Record and continue button.
- These are F-09 controls. An empty box in their place would look broken on live items and would invent layout F-09 owns. The coordinator should re-score both after F-09 mounts at the slot (`{/* F-09: ReconcilePanel mounts here */}`).
- Phone note for F-09: the page keeps an empty pinned-bar room on that board (`bar_slot`) for "Record and continue".
