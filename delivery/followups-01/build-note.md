STATUS: READY
COMMIT: 1a7e4c9de8d61230a4b5b667982212ba18008918
BRANCH: fu-01-small-followups (pushed, no PR opened)
BUILDER: builder
LANE: frontend

## Summary
- Seven of the nine follow-ups are fixed. Item 7 (F-09 proof box wording) is skipped, and part of items 4 and 8 is left, for the reasons below.
- No behaviour, money, permission or contract change. Only wording, layout, focus, mock fixtures and tests changed.

## Changes (by item)
1. F-16 UI-2-1: `DecideStates.tsx`. On the phone done view, the card text now stops before the "Paid is tracked separately..." sentence, so the separate line says it once. Desktop is unchanged. New test in `tests/decide-board.test.tsx` fails on the old code (confirmed by stashing the source).
2. F-07 UX-3-1 / QA-3-1: `ProjectsList.tsx` says "1 PROJECT" when the total is 1. Changed assertions: `tests/projects.test.tsx` lines 174 and 275 ("1 PROJECTS" to "1 PROJECT"), and `e2e/projects.spec.ts` line 253. The e2e failure showed up in my own browser run, so the e2e assertion was a real dependency.
3. F-07 TECH-3-1: removed `contractBody` and `PROPOSED_FIELDS` and the old "v6" comments from `mock/projects.mjs`. Removed the E-PROJECTS and E-PROJECT stripping in `tests/mock-contract.test.ts` and `tests/mock-projects.test.ts`. The bodies now validate in full against v7 (the loaded contract). No field had to be kept stripped: all passed. Changed assertions: the `PROPOSED_FIELDS.row` equality in mock-projects.test.ts is removed (the list no longer exists; the row-field values are still asserted on the line above it). The test titles and messages that mentioned "v6 / PROPOSAL fields" are reworded.
4. F-15 TECH-2-1: `AppShell.tsx` `leaveAlerts(href)` sets the focus flag only when the target path differs from the current path. `AlertsDrawer.tsx` passes the alert's work link or the footer link's href. New test in `tests/alerts-bell.test.tsx` fails on the old code. Wordmark below 380px: NOT changed. The UI review calls it taste. A 15px wordmark would not keep the 8px gap to the bell at 360 to 379 (about 6px spare after the gap, and 15px adds about 18px of width), so it would need a design call.
5. F-14 UI-4-1: `WorkItemOverview.tsx` renders the "See all exceptions" button after the panel's own links, so owner-needed and setup-needed show the primary action first. Effect-uncertain has no panel links, so its board position (between the facts and the small print) is unchanged. F-14 QA-4-1: `W-1711.json` gets `case_id` C-1711 and `case_revision` 5. New sidecars `mock/fixtures/response/W-1711.{delivered,not_delivered,unknown}.json`, same shape as W-1603's (schema-valid, no `presentation` since the contract does not allow it on the response items). New test in `tests/response-mock.test.ts` walks W-1711 to each answer.
6. F-12 QA-1-1 / D-27: `alerts.css` adds `--alerts-footer: 86px` (footspace and callout `scroll-margin-bottom`). `AlertSettingsPage.tsx` scrolls the "problem" callout into view (stale and invalid already focus it). e2e at 390: a new "failed save" test and a bar-clearance assertion in the stale and invalid tests. Confirmed they fail without the fix (callout bottom 779, bar top 758).
7. F-09 UX-3-2 (proof box says "Add another file" next to "Proof can't be uploaded"): SKIPPED. The button is already disabled in that case. The text "Add another file" is what the SCR-16-desktop-validation board draws, even next to "No proof added yet". Changing it departs from a board, so it is a design-engineer decision.
8. F-11 round 3:
   - TECH-3-1 fixed: `RulesView.tsx` clears the closed-panel notice when an editable rule is back. I did not write a dedicated test; the path the reviewers described is not reachable in the mock, and the existing "Show more brings the panel back" test still passes.
   - QA-3-1 fixed: `SetupFrame.tsx` `ShowMore` moves focus to a visually hidden "All N rules are shown." line after the last page loads. `setup-rules.test.tsx` has a new focus assertion.
   - UX-3-1 NOT fixed (needs a product decision): the phone "← Setup" goes to the reserved Roles page until a phone Setup home exists.
9. D-21: `public/agents/tola-done.png` (from `design/mascots/transparent/pmo-done.png`, resized to 268x380 like the other poses). `CaughtUp.tsx` and `my-work.css` use it on the My work "Nothing needs you" panel: 170px high on desktop, 150px on phone, as SCR-01-desktop-empty and SCR-01-mobile-empty draw it. Alt text is now the board's "Tola, the PMO agent, giving a thumbs up". Changed assertion: `tests/my-work.test.tsx` (the image name and the src, `tola.png` to `tola-done.png`). Other empty-state boards do not draw Tola poses, so nothing else was changed.

## Tests run
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit=0 (lint, typecheck, vitest 44 files and 1169 tests passed, build).
- Playwright (E2E_PORT=4521 MOCK_PORT=4522): my-work, work-item-board, setup, alerts-bell, decide-board and projects specs: 163 passed, 1 failed (projects "1 PROJECTS", fixed in e2e and re-run: passed). alerts.spec.ts at 390: 9 passed. I did not run the other e2e specs (decide, exceptions, finance-month-end, overview, response, start-work, work-item, frame).
- Not done: the design-fidelity tool on the My work empty boards (item 9) and on the decide done phone board (item 1). The changes are small, but a fidelity score has not been re-measured.
- Ports 4521 and 4522 are free; test-results was deleted; `git status --porcelain` is empty.

## Round 2

Head: 290a212a2441e67190e21fc61c940a77a670f4ce (was 1a7e4c9).

Fixed UI-1-1 only. The state panel has a new presentation flag `note_first` (type, mock-contract schema, `StatePanel` in WorkItemOverview.tsx). When true, the note renders before the panel links; otherwise it stays after them. W-1709's desktop panel sets it, so setup-needed now reads body, note, "Open Setup", "See all exceptions", as the board draws. Owner-needed and effect-uncertain do not set it and are unchanged. No check on the work id.

Design-fidelity, production build, 1440, FRAME_FIXTURES=1, ports 4811/4812, pm cookie, F-14 exceptions, wait 500 ms (reports in fidelity/<board>-1440/):
- SCR-02-desktop-setup-needed (W-1709): visual 95.4 (was 89.8), coverage 96.7 raw, 100 with exceptions. PASS.
- SCR-02-desktop-owner-needed (W-1708): visual 92.7 (was 92.7), coverage 100 with exceptions. PASS. One run scored 88 because Google Fonts could not be reached; two reruns gave 92.7.

Checks: lint and typecheck clean, production build clean, and every test file passes. The machine load was above 200 while I ran the full suite, so each full `delivery/checks.sh` run failed 1 to 4 different timing-sensitive tests (ECONNRESET or loading-state timeouts in mock-contract, work-item-board, work-item, decide, setup-rules, start-work, response). Each of those files passes when run alone (459 of 459 in the last six-file run; 134 of 134 for response and work-item-board). Re-run the gate on a quiet machine to confirm.
