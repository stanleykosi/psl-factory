VERDICT: PASS
COMMIT: 7632c22d4fc8a3096beec1ba09bf3a46472a4c30
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

## Checked
- Diff 5026aa73...7632c22d (6 frontend files, no backend, no contract, no permission or money code). Ran `npx vitest run tests/workspace.test.tsx tests/work-item.test.tsx` in the worktree: 80 passed.
- Trigger: the line header uses only `tab === 'overview' && shown.workspace !== undefined`; the overview uses `item.workspace`. No line names or ids. Crumbs, status, subtitle come from existing workspace fields.
- Pages without a workspace take the old `WorkItemHeader`, and the old overview branch; History tab always keeps the old header. Only `work-overview--line` is a new class, and only for workspace items. The builder's identical SCR-02 scores on 26 boards are consistent with the code.
- Screen readers: facts, stations, agent card and next step stay in `work-sr` (the existing visually-hidden pattern); none contains a link or button (the quiet NextStep omits the exceptions link; the visible one is drawn once after the workspace). The started line stays in sr. Crumbs, subtitle and status moved out of the workspace header rather than copied, so no duplicates. The reference appears in the phone bar word and the sr facts, which is not a duplicate announcement of concern.
- History reachable: a "Work item" nav with a History link, desktop in the crumb row, phone in the meta row. The tabs strip is not drawn on the same page, so no duplicate landmark name.
- Test change: subtitle, status and crumb nav are looked up on `screen` and asserted not inside the workspace container; the tone class, crumb text, no-link and aria-current assertions are kept. Not weaker; it checks the move.
- `.ws-decide--flow { z-index: auto }` is correct (a static flex item still honours z-index) and is inside the same phone media block. The workspace e2e is reported as 99 passing; unit tests pass.

## Findings
- TECH-F-1 | non-blocking | low | design engineer / F-21 owner | Coverage with exceptions drops on three F-21 boards, and visual stays 70 to 81 (builder's note, honestly reported). F-21's fidelity exceptions need updating, or the workspace must supply the agent panel. SCR-02 drift against F-14's recorded scores already exists on the base; someone should re-baseline.
- TECH-F-2 | non-blocking | low | builder | `LineHeader`'s doc comment is one long line, and a phone "+ Start" overlap with the bar word is pre-existing; neither needs action here.
