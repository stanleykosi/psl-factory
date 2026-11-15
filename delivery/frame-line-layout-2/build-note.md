STATUS: READY (frame items 1 to 3 and TECH-3 done; the 90 visual bar on the SCR-25 boards is still NOT reached, see Result)
COMMIT: bef1968cf9633e4ca497304b984c5465b2c65320
BRANCH: frame-line-layout-2 (base origin/dlv-00-delivery-setup incl. PR #33), pushed, no PR
BUILDER: builder
LANE: frontend

## What changed (all keyed on data, no line key)
1. Project tab bar (desktop, WorkItemView.tsx `ProjectBar`): drawn under the title on the line header when `workspace.context.project.case_id` exists. Tabs come from PROJECT_TABS (projects/model.ts). Journey is the one built page, so it is the one link (`/projects/<case_id>`); Milestones, Documents, Money, Registers, Actions are plain spans (not links, not focusable), as F-18 did for the RFP tabs. No current tab, no counts (the item carries none). No project in the context = no bar. Phone boards draw no tab bar (survey in pass 1), so none on phones.
2. Line title ~35px: local custom property `--title-line: 35px` on `.work-header--line`, applied at 720px and up only. tokens.css is generated from design/system tokens.json (a drift test guards it), so the token is local to work-item.css rather than a design-system edit; promote it if you want it in tokens.json. Phones measure 22px on every line board and already draw 22px. My Work and other pages keep 40px.
3. Section placement (Workspace.tsx `inSide`): the checklist section goes to the side column when `item.agent.status === 'working'` (contract: agent.status enum) and the section kind is `checklist`. The agent note moves to the main column beside it in that case (the boards draw it left of the panel). The disabled Decide step stays under it (AC 11). No line key. Phone: the side column already flows into one column; the side checklist rows keep words and status on one line (workspace.css, phone block only).
4. TECH-3: phone "+ Start" overlapping the bar word. The bar word on line pages now sits just before the bell/Start slot (`work-barref--line`). Scoped to line pages on purpose: my first unscoped version moved the word on SCR-02 phone boards and dropped them by 0.1 to 0.3 (then scoped it; identical again). Non-line pages still draw the word at the right edge, so TECH-3 remains open for them.

## Measured (production build, FRAME_FIXTURES=1, ports 4851 to 4853, fidelity tool default, F-21's fixtures/driver/exceptions in a scratch worktree, deleted, nothing of F-21 committed)
F-21 SCR-25, coverage with exceptions 100 on all 8 before and after. Visual:
| board | before (pass 1 base, re-run now) | after |
| desktop default | 72.0 | 75.3 |
| desktop invalid | 78.6 | 78.3 |
| desktop assembling | 79.0 | 76.9 |
| desktop review | 70.0 | 73.9 to 75.5 (two runs) |
| mobile default | 71.0 | 70.8 |
| mobile invalid | 76.7 | 76.5 |
| mobile assembling | 78.1 | 76.2 |
| mobile review | 80.6 | 80.4 |
Net sum up (606.1 to about 610), but two boards fell: the assembling boards. The side-panel placement is what the board draws, yet the page has a subtitle line the assembling board does not draw (the bar sits under the title, then the subtitle, then the panel, about 37px lower than the board) and the Decide panel below the checklist, which the board does not have. Phone boards lose 0.2 each from the bar word moving off the right edge (the overlap fix). Run-to-run noise about 1.5 on some desktop boards.
SCR-02 (F-14's 26 boards, F-14 driver and exceptions, pm and finance personas): before vs after identical on all 26 after the scope fix (a first load-flaky run showed 3 outliers that re-ran identical). Coverage with exceptions 100 on all 26. (The pass-1 note's "drift vs F-14" is not seen now: coverage is 100 everywhere.)
F-17 regions (round-3 driver): identical to F-17 round 3 on all 21 (text-cites 86.2, checklist 91.9, facts 94.5 ...); unknown-money 1440 72.3 to 75.6 (one extra exception counted), 390 89.3 to 89.4. Uncertain-send lock: e2e workspace W-2008 and F-21 weekly W-2205 pass.

## Tests and checks
- `bash delivery/checks.sh` exit 0 (lint, tsc, 49 files / 1376 vitest, build). One earlier run had a loading-state timeout in decide-board.test.tsx under load; it passed on rerun and in isolation.
- Playwright (4851/4852): work-item, workspace, work-item-board, projects, start-work: 137 passed. F-21's weekly.spec.ts (run in the scratch tree with its fixtures): 25 passed.
- test-results deleted; servers stopped by port; scratch worktree removed.
- Added tests (tests/workspace.test.tsx): project bar built from the context (Journey the only link, href /projects/C-0211, no tabbable plain tabs); no bar without a project; checklist in the side column while the agent works and in the main column otherwise. Changed assertions: none.

## Result and what is left
- Not 90. Remaining frame-level gaps: the meta/subtitle line sits between title and tab bar and the assembling board has none; the Decide panel under the side checklist (board has none while assembling, AC 11 needs it); the board's panel header (agent avatar, WORKING tag, step x of y, Ask Tola) which needs agent step data in the workspace; the board's tab counts (4/6/6/9) which the item does not carry; the default/invalid boards draw no tab bar at all (the bar is on them now, per D-81). The score on default/review rose; invalid is flat.
- Contract questions: (a) project tab counts and the current tab for the bar (tab_counts exists on E-PROJECT, not on the work item); (b) whether the bar should hide on boards that do not draw it (default/invalid) which needs a view/section field; (c) a field naming the phone back label ("Project", "Delivery") still missing; (d) a section-level tag (WORKING) and an agent header for the side panel.
- A visual regression waiver for the two assembling boards, or a decision on moving the subtitle below the bar, is the design engineer's call.
