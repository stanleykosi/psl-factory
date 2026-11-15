STATUS: READY
COMMIT: c8301683d46935ab19c68963f0a9672ba89e8f2b
BRANCH: fu-02-small-followups (pushed, no PR opened)
BUILDER: builder
LANE: frontend

## Summary
- All seven items are done; item 1 turned out to be partly already right (see below). No contract, permission or money change.
- Fidelity reports (report.json, side-by-side.png) are committed under `delivery/followups-02/fidelity/` on the branch.

## Changes (by item)
1. My work tabs: measured on the built page and on the rendered boards, the tab is already 44px high (the strip is 48px with its 2px borders, on the page and on both boards). What differed on the phone board: tab padding `0 14px` and 15px words (page had 16px / 14px). `my-work.css` now sets that under 720px. e2e `my-work.spec.ts` asserts all four tabs are 44px (desktop and phone; passes on old code, a guard) and, on the phone, padding 14px and font 15px (fails on old code).
2. Checklist chip: `Sections.tsx` drops the due part when the status is `unknown` and the due date is also unknown, so it reads "Unknown" once (the board draws only UNKNOWN). Other statuses keep "status · Due ...". Changed assertions in `tests/workspace.test.tsx`: 'Finance confirmationUnknown · Due Unknown' to 'Finance confirmationUnknown', and 'Kola Foods payment dateUnknown · Due Unknown' to 'Kola Foods payment dateUnknown' (the word is shown once now).
3. QA-5-3: the existing scroll effect in `Workspace.tsx` ran when the notice was set, but the re-read after the press then laid the page out again (the reconcile panel appears) and the callout ended at y 979 on an 844 screen. The effect now also runs when the workspace revision changes. New e2e in `workspace.spec.ts` (W-2008 at 390: callout bottom within 844, top at or below 0) fails on the old code (received 978.8) and passes now. Desktop is unchanged (`block: 'nearest'` does nothing when it is already visible).
4. QA-5-4: the message came from the field's own error plus a visually hidden `role="alert"` summary of all errors in `StepForm.tsx`. I removed the summary; the focused field's error is linked by `aria-describedby`, so it is still read out. Changed assertion in `tests/workspace-step.test.tsx` ('required check runs before any request'): the expected list of "to continue." texts loses the third, joined summary entry (the summary no longer exists). New assertion in the 2001-character note test: the message appears once.
5. UX-5-1 / TECH-5-2: when the item is awaiting reconcile and the page does not offer the reconcile panel (same rule as before: `item.reconcile` set and `reconcile` not in `allowed_actions`), the hint under the steps reads "Someone with reconcile access needs to confirm what happened first." Otherwise it stays "Confirm what happened first." No new permission rule. New tests for both viewers in `tests/workspace-step.test.tsx` (the no-grant one fails on old code).
6. `workspace.css`: `--space-bar-clear: 30px` replaces the literal 30px in both flow-mode rules. It is defined at the top of `workspace.css` (`:root`), not in `src/styles/tokens.css`, because that file is generated from `design/system/project/tokens.json` (a drift test enforces it) and no existing spacing token is 30px. If it should be a design-system token, add it to tokens.json and regenerate; that is the design engineer's file.
7. D-68(c): `useSetupPhoneBack` in `SetupFrame.tsx` now points "← Setup" at `/setup/rules`. Changed assertions, reason D-68(c): `tests/setup-rules.test.tsx` (two: the rules list and the finance/delivery phone bar, `/setup/roles` to `/setup/rules`) and `e2e/setup.spec.ts` line 348. Not changed: `tests/shell.test.tsx` (it builds its own `usePhoneBack` call, not the Setup hook) and the Roles tab href. Wordmark and proof-box wording untouched (D-68 a, b).

## Tests run
- `bash delivery/checks.sh` from the worktree: exit 0 (lint, typecheck, vitest 49 files / 1373 tests, build).
- New or changed unit tests fail on the old source: 7 failures with `frontend/src` stashed, all pass with it.
- Playwright (E2E_PORT=4831 MOCK_PORT=4832): `my-work`, `workspace`, `setup`, `work-item-board` specs: 108 passed. There is no separate frame spec file; the workspace and work-item-board specs cover the frame. Other e2e specs were not run.
- Design-fidelity (production build, FRAME_FIXTURES=1, ports 4831/4832, cookie `psl_mock_worklist=board`, F-02 exceptions, wait 500 ms):
  - SCR-01-desktop at 1440: PASS, visual 90.9, coverage 96.4 raw, 100 with exceptions.
  - SCR-01-mobile at 390: FAIL on visual only, 83.5 (coverage 100 with exceptions). Same as before the change (83.5) and the 81.8 that F-02/F-15 already accepted; the gap is the page's extra rows block and bell, not the tabs. Needs the design engineer's waiver as before; I did not chase it.
- Own servers stopped by port; test-results deleted; `git status --porcelain` empty; ports 4831 and 4832 free.
