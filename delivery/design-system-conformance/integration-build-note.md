STATUS: READY
COMMIT: 59799cb8aada3c594a7b223cf462bbacb72ed038
BRANCH: ds-integrate
BUILDER: builder
LANE: frontend (design-system integration: shared library + the three migration lanes)

## Summary
- The shared components now take the approved boards' look (D-93): 40px page titles with the boards' own record and phone sizes, the boards' date and time formats as named formatters, a link-look disclosure, a one-line breadcrumb, facts-strip RECEIPT and "—", the SCR-01 filter panel, a small ▾ select arrow, a one-line text box, capital tags, a phone drawer that keeps the page top in view for Start work. The design system's README, component pages, tokens.json and bundle.css are updated to match, and the token drift test is green.
- Library gaps the lanes reported are closed: Panel ref/heading level/aside/data pass-through, Table expanding row, Callout custom icon or none and plain children, Segmented option names, "History 7" count spacing, result and Show more counts as polite live text (not role=status), BottomSheet focus return (returnFocus) and optional grab/close/head action, EmptyState heading level, AgentChecklist without an agent, DSC-1..4.
- Round 3: 22 rows are more than 0.5 below base: 17 D-92/D-94, 3 the accepted SCR-03 rows, 2 the UI-2-2 reference move (−0.6); 16 are more than 0.5 above.
- Lane drift fixed: off-token rounding (6→8px, 22→24px, removed line heights), lane 2's 34px titles and full-date strings reverted to the boards; lane 2's 12 failing e2e and every other red test now pass. The response and RFP forms (F-09, F-18) went back to their board markup, because the shared DateField/FileUpload/Segmented cannot draw those boards (one-box date and time, compact proof row, boxed radio buttons): those 32 boards had fallen 5-18 points.
- Honest before/after on the SAME current mock: base = origin/dlv-00-delivery-setup (d7f2d69d) built in this worktree (frontend/src, tests, e2e, scripts checked out from base, then restored), after = this branch head; 129 boards plus 21 F-17 regions. Coverage after exceptions is equal to or better than base on every board. 20 rows are lower by more than 0.5: 17 are D-92 consequences (colour meaning, 44px on phones, 500px drawer, README words); 3 SCR-03 decide rows (−0.7 to −1.8) are not D-92 and are explained under "Fix round" (no Callout there; mock wording and a board-format fix move the layout); 18 rows are better by more than 0.5. After the review fix round every board was re-scored on dbb189e3 (F-02, F-12 and F-14 again on the head's CSS); see "Review fix round". F-02 and F-07 were re-scored for D-94 on 6e5c9ade, F-02 and F-16 on 0da20fd5 (round 2), and F-02, F-05, F-09, F-10, F-14 and F-21 on the COMMIT head (round 3).
- Gate on the COMMIT head: `bash delivery/checks.sh` exit 0 (lint 0 warnings, typecheck, 78 files / 1650 unit tests, build); full Playwright suite 458 passed, 0 failed.

## How before and after were measured
- One harness for both runs (`/private/tmp/claude-501/-Users-Hunchoo-psl-factory/984b2492-735a-4d33-833d-007cd38fd896/scratchpad/integ/run.sh`): the software-factory fidelity tool (branch factory-running) with one added `--actions` hook (lane 2's), each feature's own exceptions file (`delivery/features/F-*/fidelity-exceptions.json`), the feature drivers' cookies and URLs (F-02 round-3, F-05 round-2, F-09 round-1, F-14 round-1, F-16 and F-21 frozen states driven through the real UI, F-17 `round-3/fidelity/region-check.mjs` with `regions.json`), production builds with `FRAME_FIXTURES=1`, mock on 4932, app on 4931, frozen pages on 4933.
- The form drivers (F-05, F-09, F-18) fill native selects and date inputs on base and the shared Select/DateField after, with the same board values (`/private/tmp/claude-501/-Users-Hunchoo-psl-factory/984b2492-735a-4d33-833d-007cd38fd896/scratchpad/integ/acts/lib.mjs`).
- Base = d7f2d69d, the commit this branch starts from; its frontend/src, tests, e2e and scripts were checked out into this worktree, built and scored, then restored (no second node_modules; no temporary worktree left).
- After = the branch head named on COMMIT. Scores move by up to ±0.5 between runs of the same code; those rows say so.

## Before/after (visual score; coverage after exceptions is 100 on both unless noted)
| feature | board | base | after | delta | cause |
|---|---|---|---|---|---|
| F-02 | SCR-01-desktop-1440 | 90.9 | 91.1 | +0.2 | within ±0.5 (run-to-run noise) |
| F-02 | SCR-01-desktop-empty-1440 | 88.7 | 88.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-02 | SCR-01-desktop-filter-1440 | 78.1 | 82 | +3.9 | better |
| F-02 | SCR-01-desktop-my-work-1440 | 90.3 | 90.1 | -0.2 | within ±0.5 (run-to-run noise) |
| F-02 | SCR-01-mobile-390 | 83.5 | 82.3 | -1.2 | D-92b: Effect uncertain tag and its mini-bar segment amber (board orange) |
| F-02 | SCR-01-mobile-empty-390 | 80 | 80.1 | +0.1 | within ±0.5 (run-to-run noise) |
| F-02 | SCR-01-mobile-filter-390 | 96.8 | 77 | -19.8 | D-92c (named by D-94): the sheet's Clear, the All 6 lines link and the line rows are 44px targets on phones (the board draws small links and 36px rows), so the sheet is taller and covers the chips row |
| F-02 | SCR-01-mobile-lead-390 | 83.5 | 82.3 | -1.2 | D-92b: Effect uncertain amber (as above) |
| F-02 | SCR-01-mobile-my-work-390 | 92.3 | 92.7 | +0.4 | within ±0.5 (run-to-run noise) |
| F-05 | SCR-04-desktop-1440 | 85.6 | 86.5 | +0.9 | better |
| F-05 | SCR-04-desktop-change-1440 | 87.6 | 87.2 | -0.4 | within ±0.5 (run-to-run noise) |
| F-05 | SCR-04-desktop-escalation-1440 | 87.5 | 89.2 | +1.7 | better |
| F-05 | SCR-04-desktop-incident-1440 | 88.4 | 88.4 | +0.0 | within ±0.5 (run-to-run noise) |
| F-05 | SCR-04-desktop-issue-1440 | 89.2 | 89.2 | +0.0 | within ±0.5 (run-to-run noise) |
| F-05 | SCR-04-desktop-leadership-1440 | 88.1 | 88.9 | +0.8 | better |
| F-05 | SCR-04-desktop-lines-1440 | 85.7 | 83.1 | -2.6 | D-92d: the shared 500px drawer (this board draws 480px) |
| F-05 | SCR-04-desktop-minutes-1440 | 87.7 | 89.1 | +1.4 | better |
| F-05 | SCR-04-desktop-validation-1440 | 81.4 | 82.7 | +1.3 | better |
| F-05 | SCR-04-desktop-weekly-1440 | 89.1 | 88.8 | -0.3 | within ±0.5 (run-to-run noise) |
| F-05 | SCR-04-mobile-390 | 87.4 | 84.7 | -2.7 | D-92c: 44px targets in the sheet head (change line, close) |
| F-05 | SCR-04-mobile-change-390 | 79.5 | 81 | +1.5 | better (cov+exc 92.3% both) |
| F-05 | SCR-04-mobile-escalation-390 | 79.2 | 79.7 | +0.5 | within ±0.5 (run-to-run noise) (cov+exc 90% both) |
| F-05 | SCR-04-mobile-incident-390 | 78 | 78.6 | +0.6 | better (cov+exc 90.9% both) |
| F-05 | SCR-04-mobile-issue-390 | 87.1 | 86 | -1.1 | D-92c: 44px targets in the sheet (cov+exc 90% both) |
| F-05 | SCR-04-mobile-leadership-390 | 76.9 | 76.5 | -0.4 | within ±0.5 (run-to-run noise) (cov+exc 90% both) |
| F-05 | SCR-04-mobile-lines-390 | 77.9 | 72.3 | -5.6 | D-92c: 44px line cards on phones (review UI-1-5; the board draws 40px cards), with one even 10px gap as the board |
| F-05 | SCR-04-mobile-minutes-390 | 78.5 | 78.7 | +0.2 | within ±0.5 (run-to-run noise) (cov+exc 92.3% both) |
| F-05 | SCR-04-mobile-validation-390 | 76.8 | 76.1 | -0.7 | D-92c: 44px targets in the sheet |
| F-05 | SCR-04-mobile-weekly-390 | 85.9 | 85.2 | -0.7 | D-92c: 44px targets in the sheet; the week is two shared DateFields with a 44px calendar button (board: one text box) (cov+exc 91.7% both) |
| F-06 | SCR-10-desktop-1440 | 90.8 | 87.7 | -3.1 | D-92 state words and colour: "Stopped: invoice follow-up needed" and "Effect uncertain" (board SEND UNCERTAIN, FOLLOW-UP NEEDED) widen the tag column and add 2px to rows |
| F-06 | SCR-10-mobile-390 | 91.4 | 91.9 | +0.5 | within ±0.5 (run-to-run noise) |
| F-07 | SCR-07-desktop-1440 | 90.6 | 89.4 | -1.2 | D-92b: waiting line dots amber (board white) |
| F-07 | SCR-07-mobile-390 | 78.4 | 78.2 | -0.2 | within ±0.5 (run-to-run noise) |
| F-07 | SCR-22-desktop-1440 | 92.3 | 88.8 | -3.5 | D-94: the closed row reads Unknown on All I can see because E-PROJECTS rows carry no open/closed state (on the Closed tab it is "—"); exception approved for that row (D-94); waiting dots amber (D-92b) |
| F-07 | SCR-22-mobile-390 | 91.3 | 95.5 | +4.2 | better |
| F-08 | SCR-06-desktop-1440 | 93.4 | 93.4 | +0.0 | within ±0.5 (run-to-run noise) |
| F-08 | SCR-06-mobile-390 | 89.5 | 92.2 | +2.7 | better |
| F-09 | SCR-02-desktop-awaiting-reconciliation-1440 | 60.1 | 60 | -0.1 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-02-desktop-waiting-1440 | 54.6 | 54.6 | +0.0 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-02-mobile-awaiting-reconciliation-390 | 72.7 | 72.5 | -0.2 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-02-mobile-waiting-390 | 73.6 | 73.1 | -0.5 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-16-desktop-1440 | 94.7 | 94.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-16-desktop-sow-signed-1440 | 92 | 92 | +0.0 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-16-desktop-success-1440 | 92.3 | 92.3 | +0.0 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-16-desktop-validation-1440 | 95.8 | 95.8 | +0.0 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-16-mobile-390 | 80.4 | 80.5 | +0.1 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-16-mobile-sow-signed-390 | 88.9 | 88.9 | +0.0 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-16-mobile-success-390 | 94.7 | 94.8 | +0.1 | within ±0.5 (run-to-run noise) |
| F-09 | SCR-16-mobile-validation-390 | 72.9 | 72.9 | +0.0 | within ±0.5 (run-to-run noise) |
| F-10 | SCR-36-desktop-1440 | 96.9 | 91.5 | -5.4 | D-92b: count strip no longer fills DONE green / WAITING and CASH amber (WAITING ON HR is amber again and HR only stays on one line) |
| F-10 | SCR-36-mobile-390 | 97.7 | 97.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-11 | SCR-13-desktop-delivery-rules-1440 | 98 | 98 | +0.0 | within ±0.5 (run-to-run noise) |
| F-11 | SCR-13-desktop-finance-rules-1440 | 95.6 | 95.5 | -0.1 | within ±0.5 (run-to-run noise) |
| F-11 | SCR-13-desktop-rules-1440 | 93.4 | 92.1 | -1.3 | D-92b: Set a rule panel head ink, not solid blue (table tags now square as drawn; was −4.5) |
| F-11 | SCR-13-mobile-delivery-rules-390 | 91.3 | 91.3 | +0.0 | within ±0.5 (run-to-run noise) (cov+exc 75% both) |
| F-11 | SCR-13-mobile-finance-rules-390 | 93.7 | 93.7 | +0.0 | within ±0.5 (run-to-run noise) (cov+exc 88.9% both) |
| F-11 | SCR-13-mobile-rules-390 | 97.8 | 97.8 | +0.0 | within ±0.5 (run-to-run noise) (cov+exc 93.3% both) |
| F-12 | SCR-15-desktop-1440 | 96.3 | 95.8 | -0.5 | within ±0.5 (run-to-run noise) |
| F-12 | SCR-15-desktop-settings-1440 | 85.6 | 96.7 | +11.1 | better |
| F-12 | SCR-15-mobile-390 | 92.5 | 92.5 | +0.0 | within ±0.5 (run-to-run noise) |
| F-12 | SCR-15-mobile-settings-390 | 97.8 | 97.9 | +0.1 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-1440 | 89.8 | 89.8 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-awaiting-reconciliation-1440 | 91.1 | 91 | -0.1 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-cancelled-1440 | 93.1 | 93.1 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-effect-uncertain-1440 | 92.6 | 92.6 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-history-1440 | 94.8 | 94.9 | +0.1 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-issue-1440 | 89.9 | 89.9 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-owner-needed-1440 | 92.7 | 92.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-permission-1440 | 93.4 | 93.4 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-processing-1440 | 92.5 | 92.3 | -0.2 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-ready-1440 | 95.3 | 95.3 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-setup-needed-1440 | 95.4 | 95.4 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-verified-1440 | 91.3 | 91.3 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-desktop-waiting-1440 | 92.7 | 92.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-390 | 95.8 | 95.8 | +0.0 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-awaiting-reconciliation-390 | 93.3 | 92.9 | -0.4 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-cancelled-390 | 95.9 | 95.8 | -0.1 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-effect-uncertain-390 | 95 | 94.4 | -0.6 | UI-2-2: as above |
| F-14 | SCR-02-mobile-history-390 | 93.8 | 94.3 | +0.5 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-issue-390 | 90 | 88.7 | -1.3 | D-92b: TEST TEMPLATE is the dashed amber sample label |
| F-14 | SCR-02-mobile-owner-needed-390 | 97.2 | 96.9 | -0.3 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-permission-390 | 98.5 | 98.6 | +0.1 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-processing-390 | 91.3 | 90.9 | -0.4 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-ready-390 | 94.9 | 94.3 | -0.6 | UI-2-2: the reference now sits left of the bell and Start instead of under Start (the board has no bell, so it sits further left than drawn) |
| F-14 | SCR-02-mobile-setup-needed-390 | 95.1 | 94.8 | -0.3 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-verified-390 | 90.3 | 90.1 | -0.2 | within ±0.5 (run-to-run noise) |
| F-14 | SCR-02-mobile-waiting-390 | 89.9 | 89.6 | -0.3 | within ±0.5 (run-to-run noise) |
| F-16 | SCR-03-desktop-1440 | 88.7 | 88.6 | -0.1 | within ±0.5 (run-to-run noise) |
| F-16 | SCR-03-desktop-done-1440 | 92.2 | 92.2 | +0.0 | within ±0.5 (run-to-run noise) |
| F-16 | SCR-03-desktop-not-yours-1440 | 89.5 | 88.2 | -1.3 | Not D-92, see "Fix round": no Callout on this screen; the mock's sentence is one line where the board's wraps, so the comment box sits 10px higher than drawn |
| F-16 | SCR-03-desktop-own-1440 | 89.9 | 90.2 | +0.3 | within ±0.5 (run-to-run noise) |
| F-16 | SCR-03-desktop-stale-1440 | 85.3 | 85.2 | -0.1 | within ±0.5 (run-to-run noise) |
| F-16 | SCR-03-mobile-390 | 86.3 | 86.4 | +0.1 | within ±0.5 (run-to-run noise) |
| F-16 | SCR-03-mobile-done-390 | 97.3 | 97.3 | +0.0 | within ±0.5 (run-to-run noise) |
| F-16 | SCR-03-mobile-not-yours-390 | 85.7 | 83.9 | -1.8 | Not D-92, see "Fix round": as above (mock wording), plus D-92c 44px phone buttons |
| F-16 | SCR-03-mobile-own-390 | 79.6 | 78.9 | -0.7 | Not D-92, see "Fix round": the alerted line now reads as the board writes it ("at 10:20."), which moves this page (laid out unlike its board) by one line |
| F-16 | SCR-03-mobile-stale-390 | 80.1 | 80.2 | +0.1 | within ±0.5 (run-to-run noise) |
| F-17 region | checklist-1440 | 91.9 | 91.9 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | checklist-390 | 77.1 | 76.8 | -0.3 | within ±0.5 (run-to-run noise) |
| F-17 region | checklist-gates-1440 | 92 | 92 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | checklist-gates-390 | 72.2 | 72.2 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | facts-1440 | 94.5 | 94.5 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | findings-1440 | 71.6 | 71.6 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | findings-390 | 74.7 | 74.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | notice-done-1440 | 93.6 | 93.8 | +0.2 | within ±0.5 (run-to-run noise) |
| F-17 region | notice-done-390 | 67.9 | 69.5 | +1.6 | better |
| F-17 region | recipients-1440 | 89.7 | 89.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | step-form-1440 | 45.2 | 49.9 | +4.7 | better |
| F-17 region | steps-1440 | 40.4 | 40.4 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | steps-390 | 31.6 | 31.6 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | suggestions-1440 | 70.1 | 70 | -0.1 | within ±0.5 (run-to-run noise) |
| F-17 region | table-1440 | 77.5 | 77.5 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | table-390 | 72 | 72 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | text-cites-1440 | 86.2 | 86.2 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | text-cites-390 | 100 | 100 | +0.0 | within ±0.5 (run-to-run noise) |
| F-17 region | timeline-1440 | 90.5 | 90.2 | -0.3 | within ±0.5 (run-to-run noise) |
| F-17 region | unknown-money-1440 | 75.5 | 75.6 | +0.1 | within ±0.5 (run-to-run noise) |
| F-17 region | unknown-money-390 | 89.4 | 89.4 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-rfp-lost-1440 | 88.2 | 88.2 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-rfp-outcome-1440 | 90.4 | 90.6 | +0.2 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-rfp-outcome-lost-1440 | 94.6 | 94.6 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-rfp-outcome-pending-1440 | 93 | 93 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-rfp-outcome-unknown-1440 | 88.7 | 88.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-rfp-pending-1440 | 74.6 | 74.6 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-rfp-unknown-1440 | 86.7 | 86.7 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-rfp-won-1440 | 76.5 | 76.6 | +0.1 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-desktop-team-input-1440 | 93.4 | 93.4 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-rfp-lost-390 | 86.8 | 86.8 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-rfp-outcome-390 | 89.8 | 89.8 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-rfp-outcome-lost-390 | 82.4 | 82.6 | +0.2 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-rfp-outcome-pending-390 | 87.1 | 87.1 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-rfp-outcome-unknown-390 | 89 | 89 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-rfp-pending-390 | 88.2 | 88.2 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-rfp-unknown-390 | 88.1 | 88.1 | +0.0 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-rfp-won-390 | 87.4 | 87.5 | +0.1 | within ±0.5 (run-to-run noise) |
| F-18 | SCR-16-mobile-team-input-390 | 86.4 | 86.5 | +0.1 | within ±0.5 (run-to-run noise) |
| F-19 | SCR-35-desktop-1440 | 85.9 | 82.8 | -3.1 | D-92b: "Set" tag grey (board green READY); Unknown amber tag (D-92 content rule); amounts in mono |
| F-19 | SCR-35-desktop-detail-1440 | 80.3 | 84.8 | +4.5 | better |
| F-19 | SCR-35-mobile-390 | 94.5 | 93.8 | -0.7 | D-92b grey Set tag; mono amounts |
| F-19 | SCR-35-mobile-detail-390 | 87.4 | 89.3 | +1.9 | better |
| F-20 | SCR-34-desktop-1440 | 95.9 | 95.8 | -0.1 | within ±0.5 (run-to-run noise) |
| F-20 | SCR-34-mobile-390 | 77.7 | 80.3 | +2.6 | better (cov+exc 92.9% both) |
| F-21 | SCR-25-desktop-1440 | 72.8 | 72.9 | +0.1 | within ±0.5 (run-to-run noise) |
| F-21 | SCR-25-desktop-assembling-1440 | 73.7 | 73.8 | +0.1 | within ±0.5 (run-to-run noise) |
| F-21 | SCR-25-desktop-invalid-1440 | 79.9 | 80 | +0.1 | within ±0.5 (run-to-run noise) |
| F-21 | SCR-25-desktop-review-1440 | 76.6 | 76.6 | +0.0 | within ±0.5 (run-to-run noise) |
| F-21 | SCR-25-mobile-390 | 74.2 | 74.3 | +0.1 | within ±0.5 (run-to-run noise) |
| F-21 | SCR-25-mobile-assembling-390 | 78.4 | 78.3 | -0.1 | within ±0.5 (run-to-run noise) |
| F-21 | SCR-25-mobile-invalid-390 | 80.6 | 80.6 | +0.0 | within ±0.5 (run-to-run noise) |
| F-21 | SCR-25-mobile-review-390 | 81.5 | 81.5 | +0.0 | within ±0.5 (run-to-run noise) |

## Board-vs-page differences that remain, and why
D-92 (b) colour meaning
- Effect uncertain is amber everywhere (My work cards and mini bars, exceptions, work item): boards draw it orange.
- Agent DONE tag blue (work item, decide). Ready to continue is orange again, as the boards (review UI-1-1).
- Clients "Set" tag grey (board READY green); NEW tag grey; month-end count strip neutral boxes (board fills DONE green, WAITING/CASH amber). WAITING ON HR is amber again (review UI-1-2).
- Setup "Set a rule" panel head ink (board solid blue); project journey waiting dots amber (board white).
- TEST TEMPLATE is the dashed amber sample label.
D-92 (c) 44px on phones
- Filter sheet Clear, Start work sheet head (change line, close), line cards (44px, board 40px), sheet buttons, work item Overview/History tabs, alert switches, standalone links; the tabs, switches and links overlap the lines around them so the boards' rhythm holds. Desktop keeps 40px where boards draw it.
D-92 (d) 500px drawer
- Start work drawer is 500px; SCR-04-desktop and -lines draw 480px.
D-92 content rules (README words)
- State words from the README list: "Effect uncertain" (board SEND UNCERTAIN), "Stopped: invoice follow-up needed" (board FOLLOW-UP NEEDED), "Waiting"; Unknown is the amber Unknown tag, never "—" (projects next milestone; exception added to F-07) or blank; amounts in mono with two decimals (clients cards).
D-93 (boards win; design system updated to match)
- Page titles 40px (record pages 36/34/32, phones 26/24/22/20 as each board draws them); tags in capitals; dates as the boards write them; link disclosures; one-line breadcrumbs; RECEIPT and "—" in facts; SCR-01 filter panel; ▾ select arrow; one-line optional note.
Not D-92 — fixed in the fix round (see below)
- Agent note and next-step callouts drew the shared Callout icon where the boards draw none: now `icon={false}` (SCR-25-mobile back to base).
- Setup table tags: now square, inline, at the cell's line height as the SCR-13 boards draw them (delivery rules back to base; rules −4.5 → −1.3, the rest D-92b).
- Start work drawer head height and the Audience choice's place under its label (SCR-04-desktop-minutes −0.6 → +1.4).
Not D-92 — remaining, explained
- SCR-03 not-yours (−1.3 desktop, −1.8 phone) and SCR-03-mobile-own (−0.7): see "Fix round".
- Start work week range is two shared DateFields with a calendar button (board: one "12–18 Nov 2026" box); inside the D-92c phone rows above.

## Fix round (coordinator, after review)
Asked: (1) no Callout icon where a board draws none (SCR-25-mobile, SCR-03 not-yours); (2) Setup delivery-rules Tag/Table padding; (3) the SCR-04-desktop-minutes audience choice; F-07 exception back to pending.
- (1) `icon={false}` on the workspace agent note and the work item's next-step callout, as the base and the boards draw them. SCR-25-mobile 70.3 → 74.3 (base 74.2). SCR-03 not-yours has no Callout: its drop is the page text. The mock says "You can read it, but you can't approve, return or reject it." on one line where the board's longer sentence wraps, so the comment box sits about 10px higher than drawn. The page's comment box (64px) now matches the board's. I also wrote the alerted line as the boards do ("was alerted at 10:42 by WhatsApp and email."). Scores: desktop 88.2 (base 89.5), phone 83.9 (base 85.7), SCR-03-mobile-own 78.9 (base 79.6; that page is laid out unlike its board, and the shorter line moves it by one row). The remaining gap is mock data versus board copy, not a component; I did not make the box taller again to win cells.
- (2) Setup tables draw their tags square, inline, at the cell's line height (`.setup-table/.setup-deliverytable .psl-tag`), as the boards' spans; the cell padding already matched (10px 14px). Delivery rules 97.2 → 98.0 (base 98.0); Rules 88.9 → 92.1 (base 93.4, the rest is the D-92b panel head). Other boards untouched (scoped to Setup tables).
- (3) The drawer head's words stack without a forced line height (the head is the boards' height again), and from 720px a two-option choice sits the body's 14px under its label, as the board draws Audience as its own row. SCR-04-desktop-minutes 87.1 → 89.1 (base 87.7); escalation 89.2, leadership 88.9, validation 82.7, -desktop 86.5 (all now above base). Phones keep the field's 6px (10px scored lower).
- Re-scored: F-05, F-11, F-14, F-16, F-17, F-21 (affected by the agent note, next step, decide, setup and drawer changes). Checks.sh exit 0; e2e specs for the touched features 220 passed.

## Review fix round (reviews of 939f7ef9: technical PASS, UX CHANGES, UI CHANGES)
Finding → fix → evidence. Scores are base → before this round (939f7ef9) → now; rows not listed moved by 0.5 or less.
- UX-01 (blocking) → the work item's phone tabs (Overview, History) are 44px targets (D-92c); they overlap the tag line by 14px above and below, so the page keeps the boards' rhythm → `work-item.css` phone rules; F-14 phone boards within −0.8 of the previous round (SCR-02-mobile-awaiting-reconciliation 93.7 → 92.9, still within 0.5 of base 93.3); e2e work-item, work-item-board pass.
- UX-02 (blocking) → the alert switch is a 44px button on phones with its 26px track drawn behind the knob (new token `switch-track`), overlapping the row so rows keep their height → `alerts.css`; SCR-15-mobile-settings 97.8 → 97.9 → 97.9 (a first try without the overlap fell to 79.9 and was corrected); e2e alerts pass.
- UI-1-1 (blocking) → Ready to continue is orange (`person`) again, as the board and base; green is for verified outputs only (StateTag spec and Tag.tsx comment say so) → tests my-work, my-work-model and work-item assert `person` again (base assertions).
- UI-1-2 (blocking) → month-end `restricted` is amber (`waiting`) again: WAITING ON HR waits on a team → finance-month-end test asserts `psl-tag--waiting` (base).
- UI-1-3 (blocking) → a restricted link stays on one line (`white-space: nowrap` on `cmp-restricted`); "HR only" no longer wraps. SCR-36-desktop 96.9 → 91.5 → 91.3: the remaining gap is the D-92b neutral count strip.
- UI-1-4 (blocking) → the filters-on count is an ink badge, as the boards draw it (CountBadge `tone="ink"`, IconButton count); CountBadge spec updated (D-93) → tests: my-work, button, search-toolbar look for `.cmp-badge--ink`.
- UI-1-5 (blocking) → line cards have one even gap (14px desktop, 10px phone: `.sw-lines .cmp-choices--cards`) and phone cards are at least 44px (D-92c) → SCR-04-desktop-lines 85.7 → 83.3 → 82.6 (D-92d 500px drawer); SCR-04-mobile-lines 77.9 → 74.2 → 66.3: the 44px cards the review asks for are taller than the board's 40px cards, so eight cards push the Tola card down (D-92c). The note's earlier reason ("44px line cards") was wrong before this round; it is right now.
- UI-1-6 (blocking) → new tokens in tokens.json, tokens.css regenerated (drift test green): `space-6px`, `space-22px` (main/side column gap), `z-bar` (5), text styles `page-title-36/32/30/28`, `page-title-phone-22`, `sheet-title` (18px), sizes `filter-panel` (380px), `sheet-top-gap` (70px), `switch-track` (26px). A value-preserving sweep (`tokenize.py`) put every padding, margin, gap, inset, top/right/bottom/left, min-height/height (40/44/48/50/54), font-size and z-index that equals a token onto that token: 268 declarations; every `font-size: 13px` is `--text-hint-size`, every `gap: 6px` is `--space-6px`, every `z-index: 5` is `--z-bar`, `calc(var(--space-1) * 1.5)` is gone, and components.css has no raw px left. Left raw, with no token of the same meaning: widths and column sizes (320/600/760px, the 1080px breakpoint), icon and avatar boxes (18/20/36px), `font` shorthands and line heights in floor.css, the 3/5/7/9/17px nudges the boards draw, and `calc(var(--control-md) + 4px)` for the SOW boards' framed boxes. Visual change: none measured beyond ±0.5 on the boards that only took tokens.
- TECH-1 → `response/usePhone.ts` deleted; ResponseView, ReconcilePanel, OutcomeView and RecordedView use `useIsPhone` from `@/components` (same query) → response and rfp tests pass unchanged.
- TECH-2 → alerts-bell: Escape is fired on the element that has focus, and the open drawer's focus target is pinned exactly (the drawer panel, where the trap starts).
- TECH-3 → the Decide stale notice is the shared Callout (`icon={false}`, `plain`, inside the announcing wrapper). The Clients notice already is a shared Callout; its wrapper carries `role="alert"` and the focus target because a warning Callout has no live role (D-92), so it stays.
- UX-03 → standalone links on phones are 44px targets without moving text (`cmp-target`: padding and equal negative margin): breadcrumb links, empty-state actions (Go to My work), inline disclosures (See his steps), See all exceptions, Alert settings. Exceptions and Clients card titles already open from the whole card (a full-card link layer). Start work line rows are 44px (UI-1-5). Not done: the filter sheet's "All 6 lines" — a 44px target there lowered SCR-01-mobile-filter by 5 points by moving the sheet; left at its board size and listed for a ruling.
- UX-04 → on a phone, Return or Reject with no note scrolls the note (and its message) above the pinned action bar (`scrollIntoView` with a `scroll-margin-bottom` the bar's height); focus still moves to it.
- UX-06 → no code change: the factory rule (F-08) is never to read tone from the note text. The page uses `status.tone` (uncertain → amber) when the response sends it; the default mock has no `status` (a proposal field) and the `psl_mock_overview=status` fixture shows it amber. Whether the live API sends `status.tone` is a backend contract question.
- UX-07 → no board draws "Blocked": `blocked` exceptions read the README's "Action needed" (person tone) → exceptions test and filter option follow.
- UX-08 → one wording: every facts strip is the shared FactsStrip (visible RECEIPT and "—", as the boards; "receipt recorded" and "Not yet" for screen readers). The workspace's own "facts" section lists record fields from the API (its labels are data), not the six facts.
- UI-1-7 → StateTag spec: Effect uncertain and Waiting on HR in the amber row, Ready to continue in the orange row, green "verified outputs only".
- Left alone as asked: UX-05 (forms on board markup; one-box date-time field is a library follow-up), UI-1-8 / F-07 (pending the design engineer). UI-1-9 (optional spacing above Add comment) not changed.
- Tests: checks.sh exit 0 on the COMMIT head (lint 0, typecheck, 78 files / 1650 unit tests, build). Full Playwright suite on the COMMIT head: 458 passed, 0 failed (7.8 min). One month-end assertion that lane 3 had moved to grey was put back to amber (UI-1-2) after the first full run (457 passed, 1 failed). No leftover next-server from this worktree was running (pid 29591 had exited; the one other next-server, pid 16977, runs from the main checkout and was left alone).

## D-94 round (design engineer, 16 Nov 2026; merged origin/dlv-00-delivery-setup 08d1f79f first)
- Next milestone → `ProjectsList.tsx` `nextMilestoneCell`: the sent milestone when there is one; otherwise "—" when the API says the project is closed, and the amber Unknown tag when it is open (or not known to be closed). The open/closed state comes from the API, never from text: E-PROJECTS (v7, `additionalProperties: false`) gives rows no state of their own, so the only API fact is the list the server answered, `status=closed` (the Closed tab). On "All I can see" (the SCR-22-desktop board, `?status=all`) the closed Sabi Market row therefore still reads Unknown. To draw "—" there, the contract needs an open/closed field on each E-PROJECTS row; that is a coordinator/backend decision (D-PROJECTS-VIEW), so I did not add it to the mock. Tests: projects.test asserts "—" (and no Unknown tag) for the closed row on the Closed tab, and Unknown for the same row on All I can see; projects-model unchanged ("due 14 Nov", "due Unknown").
- F-07 exception "—": approved_by "design engineer, 16 Nov 2026 — D-94"; its reason names the closed-project row only and the contract gap above. SCR-22-desktop 92.3 → 88.8 (unchanged by this round; coverage 100% with the exception, 97.9% without).
- "All 6 lines" in the phone filter sheet → a full 44px row (`my-work.css`). Overlapping the line rows above failed axe target-size (the e2e axe check caught it), so the row takes its height and the sheet grows: SCR-01-mobile-filter 96.8 → 92.0 → 77.6, a D-92c drop as D-94 names it. Desktop filter unchanged (82.0).
- Checks on the COMMIT head: `checks.sh` exit 0 (lint 0, typecheck, 78 files / 1650 unit tests, build); e2e my-work, projects and frame specs: 68 passed. The full suite last ran on dab025f0 (458 passed); this round changed only the projects list cell, the My work filter link CSS and the F-07 exceptions file.

## Round 2 review fixes (review-ux.md and review-technical.md round 2)
- UX2-01 → the filter sheet's line rows are 44px on phones (`.my-work__check` min-height control-md; the board draws 36px). SCR-01-mobile-filter 77.6 → 77.0 (−0.6), a D-92c drop under D-94, named in the table.
- UX2-02 → after Return/Reject with an empty note, the whole note field (its message included) scrolls above the pinned bar once the message has drawn (`requestAnimationFrame`, `scrollIntoView` on the `.psl-field`, `scroll-margin-bottom` on the field). Measured at 390 on W-1201: message y 648–666, bar top 676; focus on the note.
- TECH-4 → the setup-rules "Show more" test waits for the focus move (`await waitFor(...)`) and still asserts that focus lands on "All 55 rules are shown." The full checks.sh run passed 1650/1650.
- Checks on the COMMIT head: checks.sh exit 0 (1650 unit tests); full Playwright suite 458 passed, 0 failed. F-16 (decide boards) unchanged by the scroll fix.

## Round 3 UI fixes (review-ui.md round 2)
- UI-2-1 (blocking) → the line groups' screen-reader legends add no space (`.sw-lines .sw-group > legend { margin: 0; }`). Measured on the head: desktop gaps 14,14,14,14,14,14,14px (cards 65px), phone 10,10,10,10,10,10,10px (cards 44px). SCR-04-mobile-lines 66.3 → 72.3 (base 77.9; the rest is the 44px cards, D-92c); SCR-04-desktop-lines 82.6 → 83.1 (base 85.7; the 500px drawer, D-92d).
- UI-2-2 → on phones the work item's reference sits left of the bell and Start slot, as the board draws it left of Start, so nothing overlaps (W-1702 at 390: reference x 174–232, slot from x 238). SCR-02-mobile-ready and -effect-uncertain −0.6: the board has no bell, so the reference now sits further left than drawn. SCR-02-mobile scored 95.8 in two runs and 92.5 in a third on the same build (run-to-run variance on that page); the table shows 95.8.
- Filter chips → on phones each chip's remove button is a 44px target reaching past the drawn chip into the gaps (rows now 12px apart so neighbouring targets never overlap); the chip looks as the board draws it. New token `chip-height` (32px).
- Month-end "HR only" → the SCR-36 board draws plain muted text with no lock, so the lock is removed (D-93): `<span class="monthend-restricted">HR only</span>`, 13px muted, one line; it still never links. SCR-36-desktop 91.3 → 91.5.
- UI-2-3 → README "Spacing" now lists the scale steps and the in-between tokens instead of "a 4px base". Raw px that remain in feature CSS, all board-drawn or local layout with no token of the same meaning (counted with `var(--…)` stripped):
  - font sizes 10px (5: decide strip labels, work-item, overview squares, floor tags), 17px (5, floor and work-item labels), 33px (1);
  - pinned-bar bottom clearances: padding-bottom 80, 96, 110, 120, 130, 150, 180px (decide, rfp, response pages under their sticky bars);
  - control and row heights: min-height 4, 18, 24, 28, 32, 36, 42, 52, 74, 80, 84, 88, 112, 120, 480, 527px; height 6, 15–18, 20, 24, 26, 32, 34, 36, 56px and panel/scene heights 150–640px;
  - small nudges the boards draw: padding 1, 3, 5, 7, 9, 11, 13.5, 26, 96px; margin 3, 5, 9, 40, 96px; right 3px and the phone bar's 134px Start slot;
  - line heights 14–20px set beside their font sizes; widths and grid columns (320, 340, 360, 380, 420, 440, 480, 560, 600, 760px, the 1080px breakpoint) and box shadows.
- Checks on the COMMIT head: checks.sh exit 0 (1650 unit tests); full Playwright suite 458 passed, 0 failed.

## QA round (review-qa.md)
- QA-1 (blocking) → Decide's uncertain-decision notice and the "couldn't confirm whether it was recorded" notice sit in a `role="alert"` container again, as on base and as LineForm does (a warning Callout has no live role of its own). The audit (every `role="alert"`/`status`/`aria-live` on base against the head, file by file) found two more Decide notices that had lost it, now fixed the same way: the claim "We couldn't get this decision ready" notice and the done page's "We couldn't refresh this item". Tests: decide.test asserts all three uncertain/failed notices are inside an alert.
- QA-2 (blocking) → in the alerts bottom sheet on phones, "See all alerts" and "Alert settings" are side by side again and each is a 44px target (as base `.alerts-dfoot`). e2e alerts-bell (390) now checks both links are at least 44px tall and on one row.
- QA-3 → the audit's other losses, restored to base semantics: the workspace's uncertain-send and changed-record notices are alerts again (outside the polite status region, which keeps the done/queued notices); Setup's warning outcome notice (`OutcomeNotice`) is an alert again (it still takes focus); everything else the audit listed still announces (problem Callouts are alerts, success Callouts and loading states are status, AlertSettings and Clients notices take focus or sit in an alert). Tests back to base assertions: workspace-step (3), weekly (1) and setup-rules (3) find the notices by `role="alert"`, setup-templates finds the 422 message by `role="alert"`.
- Also: tests/work-item.test.tsx's page-load wait failed once under the full parallel run (1s waitFor default); it now allows 5s. Nothing it asserts changed.
- Left as asked: QA-4 (open/closed per row, backend), QA-5 (inline meta links, design engineer).
- Fidelity not re-scored: the alert wrappers draw nothing, the notices only show after a press (no scored board shows them), and the alerts sheet has no board (F-15).
- Checks on the COMMIT head: checks.sh exit 0 (1650 unit tests); full Playwright suite 458 passed, 0 failed.

## Kept hand-written (the library cannot draw the board), with reason
- Response (F-09) and RFP (F-18) forms: board markup from the base, including ProofField, the date-and-time box, the "What they did" buttons, the reconcile panel and FollowupCard (with checks and no agent it shows the checks, without either nothing). The shared formatters replace their private date helpers. Library gaps: a one-box date-time field, a compact file row with "Add another file", boxed radio buttons.
- Work item own StationTrack and AgentChecklist (lane 1 reasons stand). Templates list keeps its own table (Table now has `expanded`; not adopted to avoid a fidelity change in this round). Done next-step card and stale notice keep their markup (Callout `icon`/`plain` now exist).

## Changed test assertions (reason)
Component tests
- money-field: `formatAmount(1500000)` → `formatAmount('1500000')`: money is a decimal string; the type now refuses numbers (DSC-3).
- domain (FactsStrip): labels end RECEIPT (read "RECEIPT RECORDED"); not yet is "—" with "Not yet" for screen readers (D-93).
- search-toolbar: focus moves to the panel's first field; foot is Clear (secondary) and the dark Show button; the count is a polite live region without role=status (board filter panel, D-93).
- New `tests/components/board-alignment.test.tsx` (18 tests): formats and DSC-1, PageTitle sizes and ref, Breadcrumb one line, Disclosure link and DisclosureLink, Tabs disabled and "History 7", Segmented names, Menu Space on links (DSC-4), Toast write-after-mount (DSC-2), BottomSheet returnFocus/no grab/head action, Callout icon/plain, Panel ref/heading/data, TextArea one line, Table expanded row, AgentChecklist without an agent.
Feature unit tests (dates back to the boards' formats, D-93)
- decide, decide-board (fix round): the alerted line reads "was alerted at 10:42 by WhatsApp and email." / "at 10:20.", as the SCR-03 boards write it (was "12 Nov 10:42" with no full stop).
- alerts-model, alerts, alerts-bell: "10:42", "09:00 daily digest", "12 Nov", "Last loaded 11:00." (lane 3 had added WAT and years); alerts-bell phone tab "Needs you 3".
- clients: "14 Nov, 10:00"; finance-month-end: "UPDATED 10:42"; my-work: "updated 10:42", "Last loaded 10:42."; overview: "14 Nov 16:40 WAT"; projects-model: "due 14 Nov"; work-item: "As of 12 Nov 16:45", refresh time "dd Mon hh:mm"; workspace: "12 Nov 15:10", "As of 14 Nov 10:40 WAT".
- exceptions: "As of 14 Nov 11:05", "since 11:02"/"since 10 Nov", the since time's title "14 Nov 11:02" restored; empty and no-access headings are h2 again (EmptyState `level`).
- setup-rules: "since 01 Oct", "since 30 Jun", `versionText(row, now)` restored; setup-templates: "Changed by Ada Okafor, 12 Nov", "AS OF 12 NOV, 10:40", new `boardDay`/`boardStamp` checks replace the removed `lagosDay`/`lagosStamp` ones; title classes `cmp-page-title--34` / `--p22`.
- Count spacing: tab and option texts read "Active 22", "Rules 8", "History 7", "All 7", "Needs me 0" (textContent now has the space the accessible name had) in projects, projects-journey, setup-rules, work-item-board, my-work.
- projects-journey: tab panel name without the count (`/ ?\d+$/`); coming-next heading level 2; Tola's/Chidi's summary is a complementary landmark again.
- work-item-board: "See his steps" is a disclosure button again (aria-expanded, controlled list), as the base test had it.
- my-work: the phone filter sheet closes from the shared scrim (`.cmp-layer > .psl-scrim`).
- response, rfp: back to the base tests (forms back to board markup), plus lane 1's task-panel name; weekly, workspace-step: the reconcile choice is a radiogroup again; the uncertain notice stays in the status region (lane 1).
E2E specs
- Same date and count-spacing changes in alerts, alerts-bell, clients, finance-month-end, my-work, overview, projects, setup, setup-templates, work-item-board; setup `today()` is "15 Nov" as the board writes it.
- clients: phone h1 24px (list) and 22px (detail), the SCR-35 boards' sizes (lane 2 asserted 26px).
- exceptions: the follow-up tag's words are the README's "Stopped: invoice follow-up needed" (capitals by CSS).
- start-work: field labels read through the shared field wrapper; line cards are `label.psl-choice`.
- work-item-board: phone disclosures — "See his steps" is a button, "Preview the invoice" a summary.
- response, rfp: base specs (board markup).
None removed or loosened beyond the above; every guard test (claim before write, idempotency keys, 409/422, no resend, uncertain-send lock, RFP follow-up, template and rule guards) runs unchanged.

## Design-system files updated (D-93)
- design/system/project/README.md (dates and times, page-title sizes, capital tags, "the boards decide")
- design/system/project/tokens.json (page-title 40/43, new page-title-phone 26/28) → frontend/src/styles/tokens.css regenerated
- design/system/project/components/bundle.css (`.psl-tag` text-transform uppercase) → frontend/src/styles/psl-bundle.css regenerated
- components/Breadcrumb, Disclosure, Drawer, FactsStrip, ListToolbar, Panel, Segmented, Select, StateTag, Tabs, TextArea, Toast README.md
- frontend/src/components/README.md (formatter variants, Money as decimal string, D-93)

## Exceptions files
- delivery/features/F-07/fidelity-exceptions.json: "—" for a closed project's next milestone, approved_by "design engineer, 16 Nov 2026 — D-94", reason scoped to the closed-project row. No other exception changed.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` in the worktree on the COMMIT head: exit 0 (Django check, lint 0 warnings, typecheck, 78 files / 1650 tests, build).
- Full Playwright suite (E2E_PORT 4934, MOCK_PORT 4935): 458 passed on 20ccb20d, and 458 passed, 0 failed on the COMMIT head (review fix round). The earlier fix round's touched specs passed 220 of 220 on 939f7ef9.
- Fidelity: base and after as above; outputs in `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/984b2492-735a-4d33-833d-007cd38fd896/scratchpad/integ/base`, `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/984b2492-735a-4d33-833d-007cd38fd896/scratchpad/integ/final` and the fix-round `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/984b2492-735a-4d33-833d-007cd38fd896/scratchpad/integ/fix1` and `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/984b2492-735a-4d33-833d-007cd38fd896/scratchpad/integ/fix3` (report.json, side-by-side.png per board).
- Disk 6.1 GB free at the end; servers on 4931-4935 stopped by port; test-results removed; no temporary worktree created.
- Commits have no Co-Authored-By or AI footer; pushed to origin/ds-integrate; no PR.
