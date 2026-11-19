STATUS: READY
COMMIT: 8d59b2422e06f960853993435c2935b7b9805046
BUILDER: builder
LANE: full

## Summary
- **Proof row (UI-1-1):** on the fixed_assets line it now shows the file name as returned ("asset-dates-explanation.pdf", body text, not capitals or grey mono), with "Uploaded · 64 KB" under it, as the board draws it.
- **Holds and uncertain states (UX-1-1):** these no longer draw the "See all exceptions" button, so the phone station bar is clear. Every other line still draws it.
- **Waiting state after "Approve register" (UX-1-2):** it now says what is still missing ("Waiting for someone to explain the 3 unclear in-service dates and attach the proof…"), and station 3 reads "Waiting" instead of "Needs a person".
- **Lifecycle facts (TECH-1-1):** they no longer go back to "not yet" after both reviews.
- **Claims:** both specs say the panel claims when the page loads, not on press, so InlineDecide is unchanged (see the claim question below).

## Changes
- `frontend/src/features/work-item/WorkItemOverview.tsx`: the existing F-30 rule that hides the "See all exceptions" button above the workspace now also covers `line_key: "fixed_assets"`. The app shell is not changed, and other lines are unchanged (a test confirms F-33's W-2706 still shows the button).
- `frontend/src/features/workspace/workspace.css`: three additive rules scoped to `.ws[data-line="fixed_assets"] .ws-rows--text`. They put the row's cite first, in sans body size, ink colour, weight 600 and its own case, with the detail under it. Tokens only.
- Fixtures:
  - `W-3902.approve.json`: new `next` and `next_step` wording, and station 3 set to `waiting`.
  - `W-3903.approve.json`, `W-3904.json`, `W-3909.json`: facts `drafted` and `reviewed` set to `earned`.
  - These were regenerated with the same scratch generator; no other fixture changed.
- `frontend/tests/asset-schedule.test.tsx`: new tests for:
  - the proof row order and case, and the scoped CSS rule;
  - no exceptions button on W-3907, W-3908, W-3909 and W-3911.approve, while W-2706 keeps it;
  - the lifecycle facts after both reviews;
  - the waiting wording, including that "dates are explained" is absent.
- Factory files:
  - `fidelity-exceptions.json`: no exception added in round 2. I rewrote the reasons on the two existing proof exceptions as a tool limitation, and updated the date-review waiver to 74.9; the other waivers keep their measured values.
  - `round-2/fidelity/` holds `run.sh`, the 8 reports and `scores.txt`.

## Fixes
- UI-1-1 | 8779c5f3 | Proof row on the fixed_assets line: the cite label in its returned case and body text, with the detail line under it (scoped CSS, so F-33 and other lines are unchanged).
- UX-1-1 | 8779c5f3 | No "See all exceptions" button on the fixed_assets line, so the holds have no button and the phone station bar is clear. The shell is unchanged; the button sits in WorkItemOverview's line branch, next to the existing issue-line rule.
- UX-1-2 | 8779c5f3 | `W-3902.approve.json` now says "Waiting for someone to explain the 3 unclear in-service dates and attach the proof. The date review starts after that.", and station 3 is `waiting`. The explain step itself stays with the design engineer (G-55-1).
- TECH-1-1 | 8779c5f3 | Lifecycle facts `drafted` and `reviewed` are `earned` on W-3903.approve, W-3904 and W-3909.

Not fixed, and why:
- UI-1-2 (the values note drawn as the amber callout): this is the shared Sections facts `note`, as the spec chose. It is for the design engineer when signing the waiver.
- UI-1-3 (Calculate shown amber "Waiting"): this needs a backend station status for a factory step (backend handoff P-4).
- UX-1-3 (where the consequence is drawn): owned by product, and D-RETURN is open.
- UX-1-4: partly fixed by TECH-1-1. "Receipt recorded: Unknown" is the generic facts strip shared by every line.
- UX-1-5: the uncertain notices are shared InlineDecide and useWorkspaceStep code that this feature must not change.
- UX-1-6: "F07" is sample backend text (conflict 5).

## Claim question: on load or on press?
Both specs say the claim is sent when the panel loads, before any press. So viewing a decidable task claims it, and I did not change the shared InlineDecide.
- F-42 `spec.md:145`: "The claim is sent once per task revision, only while that task's `you_can_act` is true. No claim is sent for a task that is `already_decided`. Until the claim answers, the buttons are off and the existing "Getting this review ready…" line shows."
- F-42 acceptance criterion 10 (`spec.md:247`): "On W-3902 the page sends one E-TASK-CLAIM to `/api/v1/tasks/T-3902/claim`. Pressing "Approve register" then sends exactly one POST…"
- F-33 `spec.md:96`: "The claim is sent once per task revision, only when the task's `you_can_act` is true; until it answers, the buttons are off with the existing "getting this review ready" line."
- F-33 criterion 10 (`spec.md:133`): "On W-2702, the page sends one E-TASK-CLAIM to `/api/v1/tasks/T-2702/claim`, then pressing "Approve schedule" sends exactly one POST…"
- Evidence in the tests:
  - Component tests check `posts('/api/v1/tasks/T-3902/claim')` has length 1 before any press, and that W-3903 claims only T-3903.
  - The e2e request logs show claim then decision.
  - No claim is sent where `you_can_act` is false (W-3905, W-3906, W-3912, and the holds).

Whether viewing should claim at all is a product question for F-16's flow, not this feature's.

## Acceptance criteria
Round 1's evidence stands for criteria 1–17 and 19–24, and the round-2 tests above cover the fixes.
- 6: the holds now have no button at all.
- 18 (fidelity): this round's run gives 100% coverage after exceptions on all 8 boards. Every board has a D-83 waiver, and every visual score is at least 70.

## Validation
- `npx vitest run tests/asset-schedule.test.tsx tests/asset-schedule-mock.test.ts tests/income-schedule.test.tsx`: 92 passed. `eslint` on the changed files: clean.
- e2e: `E2E_PORT=4970 MOCK_PORT=4971 npx playwright test e2e/asset-schedule.spec.ts e2e/income-schedule.spec.ts` gave 60 passed (3.1 min). `frontend/test-results` was deleted.
- `bash delivery/checks.sh` under the shared lock, entered at 14:33 with load 12.97:
  - Django check: clean.
  - Lint and typecheck: passed.
  - Vitest: 108 of 109 files and 2494 of 2495 tests passed.
  - The one failure was `tests/work-item-board.test.tsx` "W-1701: crumb, title…", which saw the loading span still on screen. The load average rose to about 150 during the run. This file is not touched by F-42 (the WorkItemOverview change only applies to `fixed_assets`). Re-run alone, it passed 81 of 81.
  - The build step did not run, because checks stops at the test failure. The e2e production build of the same head succeeded.
  - The lock was released.
- Fidelity: one run with the shared tool unmodified, `round-2/fidelity/run.sh`. It used the e2e production build of 8779c5f3 (`API_ORIGIN=http://127.0.0.1:4971 FRAME_FIXTURES=1`), the app on 4969, the mock on 4971 reset before each board, and persona finance_lead.

| Board | Width | Coverage | With exceptions | Visual |
|---|---|---|---|---|
| SCR-55-desktop-investigating | 1440 | 84.8 | 100 | 84.1 |
| SCR-55-desktop-register-review | 1440 | 86.3 | 100 | 75.0 |
| SCR-55-desktop-date-review | 1440 | 90.4 | 100 | 74.9 |
| SCR-55-desktop-calculating | 1440 | 89.7 | 100 | 74.6 |
| SCR-55-mobile-investigating | 390 | 77.8 | 100 | 82.4 |
| SCR-55-mobile-register-review | 390 | 75 | 100 | 84.4 |
| SCR-55-mobile-date-review | 390 | 75 | 100 | 87.1 |
| SCR-55-mobile-calculating | 390 | 80 | 100 | 89.1 |

- The 3 costs and the 2 proof lines are still counted as exceptions, because the check does not read a span inside a `td` or a list row. The proof text now matches the board exactly (round-2 screenshot). These exceptions were in the file before this run. No exception was added after the run; only their reason text was rewritten.
- All exceptions and waivers are "builder proposal, pending design engineer".

## Blocked
None.

## Merge with dlv-00 (F-47, F-41, #65)
- Merged `origin/dlv-00-delivery-setup` at 6a46d178 (PR #67, which includes F-47 #66 and #65) into the branch head c972854d.
- New head: 8d59b2422e06f960853993435c2935b7b9805046, pushed. It is a merge commit and carries no AI trailer.
- Conflicts and how I resolved them:
  - `frontend/src/features/workspace/Workspace.tsx`:
    - F-41's `REMINDER_LINE` is kept.
    - F-33's `INCOME_LINE` stays replaced by F-42's `scheduleLine()`, which covers both income_schedules and fixed_assets.
    - The phone Drawer list is now `ISSUE_LINE || ENGAGEMENT_LINE || scheduleLine(...) || REMINDER_LINE`.
    - No `INCOME_LINE` or `incomeLine` reference is left.
  - `delivery/BACKEND-HANDOFF.md`: both sections are kept, in merge order F-47, F-41, F-42, after F-33's.
- These merged on their own, and I checked them:
  - `Sections.tsx` and `workspace.css`: F-41's `Attachment` and `.ws-attachment` draw only for an item that carries `attachment`. F-42's proof row is a `cites` item styled by `.ws[data-line="fixed_assets"] .ws-rows--text` rules, so the two stay separate.
  - `mock-contract.test.ts`: F-41's lists and F-42's W-39xx block and links entry are both present.
  - `proposals.ts`, `useWorkspaceStep.ts` and `workspace.mjs` are F-41's as merged. F-42 has no step scripts, and its decide sidecars are untouched.
  - `income-schedule-mock.test.ts` still allows `W-(27|39)`.
- Results on the merge head:
  - `tsc --noEmit`: clean.
  - `vitest` for asset-schedule, asset-schedule-mock, income-schedule, income-schedule-mock and mock-contract: 406 passed.
  - `bash delivery/checks.sh`, under the shared lock entered at 1-minute load 12.72: exit 0. The Django check was clean, lint and typecheck passed, Vitest passed 114/114 files and 2655/2655 tests, and the build succeeded. The lock was released.
  - e2e with `E2E_PORT=4970 MOCK_PORT=4971 npx playwright test e2e/asset-schedule.spec.ts e2e/income-schedule.spec.ts e2e/payments.spec.ts e2e/start-work-proof.spec.ts e2e/workspace.spec.ts`: 142 passed (8.8 min). `frontend/test-results` was deleted.
  - No layout change in F-42, so there was no fidelity run, and the round-2 scores stand.
