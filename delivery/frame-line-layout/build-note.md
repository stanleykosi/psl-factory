STATUS: READY (frame change done; the 90 visual bar on the SCR-25 boards is NOT reached, see "Result")
COMMIT: 7632c22d4fc8a3096beec1ba09bf3a46472a4c30
BRANCH: frame-line-layout (base origin/dlv-00-delivery-setup 5026aa73), pushed, no PR
BUILDER: builder
LANE: frontend

## Summary
- A work item whose item carries a `workspace` block (Overview tab only) now gets a line header: workspace crumbs, title with the status tag at the far end, subtitle as the one meta line, then the workspace. No line-specific code; the trigger is `item.workspace`.
- On those pages the facts strip, station track, agent card, next step, started line and Overview/History tabs are not drawn. The contract data stays in the page for screen readers only (same pattern as the state boards). "See all exceptions" stays visible on exception states.
- History keeps one link: right end of the crumb row (desktop), end of the meta row (phone).
- Non-line pages are unchanged (SCR-02 scores identical to the base commit, below).
- Visual on the 8 F-21 SCR-25 boards rose 1 to 12 points but stays 70 to 81. The rest of the gap is workspace content, not frame (see Result).

## 1. Survey: what the line boards draw (design/canvas/project and finance/project, local; desktop 1440 and phone 390)
Desktop common pattern (SCR-25, 28, 41, 42, 44, 46, 49, 51, 53..59, all variants):
- Crumb line at y=84, mono, uppercase, `PROJECTS / <project> / <item> · <ref>` (Finance: `FINANCE / MONTH-END / ...`, Payroll: `PAYROLL · RESTRICTED / ...`; SCR-41: `PRE-SALE / ENGAGEMENTS / EN-0042`). Nothing at its right end.
- Title line at y=119, h1 about 35px, one status tag at the far right end of the same line (YOUR REVIEW, ASSEMBLING, PROCESSING; SCR-42/44/46/49 draw the state word as a tag too).
- Optional single meta line at y=174 (SCR-25 default, SCR-28 default, SCR-41, SCR-42).
- Project tab bar (Journey / Milestones / Documents / Money / Registers / Actions; 7 or 8 tabs on SCR-42/44/46/49) under the title, and on SCR-44/46/49 a second sub-tab bar (Overview / Release / Go-live / Hypercare ...).
- Then two columns: sections on the left, agent or Decide panel on the right (about 340 wide).
- Absent on every line board: facts strip, the 4-station track, a separate agent card above the work, the Next step callout, Overview/History tabs, a started line, a revision.
Phone common pattern: bar with `← <back>` left and one mono word right (REVIEW / DECIDE / READY, or the reference: EN-0042, MIN-0141, ACC-0010, WCR-0216); h1 22px at y=70; at most one small meta line; then content; decision boards pin the action buttons at the bottom. No tag line, no tabs.
Boards that differ:
- SCR-25 default (desktop): no `Projects /` in the crumb and no tab bar; meta line under the title.
- SCR-25 review/received/returned phone: no meta line; SCR-25 phone default bar has no right word.
- SCR-42, 44, 46, 49: crumb plus a state tag in a title block and the tab bars; SCR-44/46/49 have the second tab bar.
- SCR-53 to 59 (Finance, Payroll; the Finance canvas is local): a numbered station row of 5 to 9 line-specific stations ("01 Chidi investigates ... 07 Verified") directly under the title, plus a SAMPLE DATA tag beside the status; phone has "STATION n OF m · NAME" under the title. SCR-56 actuals, SCR-53 quarantined/units and SCR-59 followup omit the row. These are line stations, not the item's four contract stations, so the frame does not draw them; that needs data (a decision for the design engineer / backend), not frame code.
- Phone back label varies per board ("← My work", "← Lagoon Health", "← Delivery", "← Project"); the frame still says "← Queue".

## 2. What changed (files)
- frontend/src/features/work-item/WorkItemView.tsx: new `LineHeader` used when tab is overview and `item.workspace` exists. Crumb nav from `workspace.context.crumbs` (fallback to the existing My work crumb), h1, status tag (workspace.status, else state tag) plus the sample label at the far end, subtitle line, History link, phone bar word = the reference. The started line stays in a screen-reader-only block. History tab pages keep the old header.
- frontend/src/features/work-item/WorkItemOverview.tsx: for `item.workspace`, facts, stations, agent card and next step are wrapped in `work-sr`; "See all exceptions" is drawn on exception states.
- frontend/src/features/work-item/work-item.css: line header styles (appended block).
- frontend/src/features/workspace/Workspace.tsx: the workspace header no longer draws crumbs, status and subtitle (the frame header does); title (when it differs), byline/version and agent note stay.
- frontend/src/features/workspace/workspace.css: `.ws-decide--flow` gets `z-index: auto`. Found by the e2e test below: a flex item keeps its z-index when static, so the flowing Decide panel sat over the reconcile panel's pinned "Record and continue" button once the page became short enough for them to meet. Latent F-17 bug exposed by this layout.
- frontend/tests/workspace.test.tsx.
Elements kept in a place the boards allow: History link (crumb row right end on desktop; meta row on phone), "See all exceptions" (after the workspace), the phone status tag (meta row on phone, since the boards show it only as a bar word and the person needs "Your review"), SAMPLE DATA beside the status tag.
Not done on purpose: the project tab bar and the link crumbs (no data or contract field); phone back label (data does not name it).

## 3. Changed assertions (one)
- tests/workspace.test.tsx "W-2001 shows subtitle, status word, byline, version, crumbs and the agent note": subtitle, status word and the `Where this sits` crumb navigation are now looked up on the page (`screen`) instead of inside the workspace container, because the frame header now draws them above the workspace. Added: they are asserted NOT inside the workspace container, so the move is checked and the test is not weaker. Every other assertion is untouched.

## 4. Evidence
Production build, mock on 4852, app 4851, fidelity tool at default settings.
SCR-02 (F-14's 26 boards, F-14 exceptions, pm persona, F-14's driver act-wait.mjs, F-14's recorded heights): my head and the base commit 5026aa73 give identical coverage-with-exceptions and visual on all 26 (so SCR-02 is unchanged by this task).
BUT: both differ from F-14's recorded final scores. Base vs F-14 final: desktop 89.6 vs 90.9, mobile-processing 89.8 vs 91.7, mobile-waiting 88.7 vs 90.2, mobile-verified 89.1 vs 90.6, mobile-issue 88.8 vs 90.3; coverage with exceptions below 100 on desktop (95.1), verified (96.4), cancelled (93.8), effect-uncertain (96.8), awaiting-reconciliation (94.1), history (89.3). This drift is already on dlv-00-delivery-setup (later merges, e.g. title 40px, phone back link, F-17/F-21 frame changes, or exceptions-file changes), not caused here. Someone should re-baseline SCR-02 or fix it; I did not.
F-17 region driver (regions.json, round-3 driver): same pass/fail and scores as F-17 round 3 (text-cites 86.2, facts 94.5, checklist 91.9 ...); only unknown-money 1440 (72.3 to 75.6) and step-form (45.2 to 45.7) moved, both up, and one extra exception counted for unknown-money. Output in the session scratchpad only.
F-21 boards on F-21's branch fixtures (mock dir, StepForm.tsx and Sections.tsx checked out from 051ea680 into the worktree, built, driven with F-21's own drive-states.mjs, F-21's run.sh and exceptions; never committed, restored afterwards). Before = base commit with those fixtures (reproduces F-21's recorded numbers exactly); after = my head:
| board | before | after | coverage with exceptions after |
| desktop 1440 default | 69.1 | 72.0 | 100 |
| desktop invalid | 70.2 | 78.6 | 100 |
| desktop assembling | 76.6 | 79.0 | 96.4 |
| desktop review | 68.2 | 70.0 | 96.9 |
| mobile 390 default | 72.5 | 71.0 | 100 |
| mobile invalid | 71.5 | 76.8 | 100 |
| mobile assembling | 69.1 | 78.1 | 85.7 |
| mobile review | 73.8 | 80.6 | 100 |
Tests and checks: `bash delivery/checks.sh` exit 0 (lint, tsc, 49 files / 1373 vitest, build). Playwright work-item, workspace, work-item-board: 99 passed. An earlier whole-suite run had 3 to 7 unrelated vitest timeouts while the machine load was above 60; they pass alone and on the clean rerun.

## Result and what is left (for the design engineer / F-21 owner)
- The frame no longer pushes content about 400px down. What still separates SCR-25 from the board is workspace content and F-21 data: the agent note and byline rows above the sections, extra sections the board does not draw (This week, Who receives it), the agent panel versus the Decide panel on the assembling board, the project tab bar, the 40px frame title versus the board's about 35px, and the status tag's vertical position. 90 is not reachable from the frame alone.
- Coverage with exceptions fell on 3 F-21 boards because the old agent card used to supply words the boards draw: assembling "WORKING" (the board's panel tag), mobile assembling "WCR-0216" and "WORKING", desktop review "Overview" (nav tab of the board's main nav) and some "moved" items. F-21's fidelity-exceptions.json needs an update, or the workspace (not frame) must supply the agent panel; the frame does not.
- Pre-existing, seen not fixed: on phones the frame's "+ Start" button overlaps the bar word (same on SCR-02 pages today; the phone-back note TECH-3).
- The Finance and Payroll boards' own station row needs line-specific station data.
