VERDICT: PASS
COMMIT: a24195b3bd085eb5730a9155bce08b2e22fc9e92
REVIEWER: technical-reviewer
AUTHORITY: technical reviewer (lead)

## D-193 re-check (a24195b3)
- Ran `git diff d5c20396 a24195b3 --` over every file F-75 changed under frontend/src (including RegistersTab.tsx, ActionsTab.tsx, useProjectSections.ts, sectionsModel.ts and tabsModel.ts). The diff is empty, so the sync left F-75's code untouched.
- Main's sync brought in F-111 and F-87: issue follow-up, work-item controls, and workspace command and write-lock hooks. Neither tab imports from workspace, work-item or issue-followup (grep found none).
- mock/server.mjs now routes issues.mjs first, but ISSUES_PATH only matches work/51xx and projects/{case}/issues/{id}(/messages). It does not match the register or action list reads, so those fall through unchanged.
- next-config.test.ts keeps both allow-list lines, as the brief says.
- No behaviour on the Registers or Actions tabs changes. GitHub frontend-checks passed on a24195b3.

## Summary
- D-193 pre-merge re-check of the main sync (eb100065 merged into 286b4105, giving d5c20396). The earlier evidence below was gathered on 286b4105 and still stands.
- RegistersTab.tsx and ActionsTab.tsx are unchanged between 286b4105 and d5c20396 (empty diff). F-75 changed no screen code in the sync.
- Only two files are shared by F-75 and main: next-config.test.ts (main's one-per-line list kept, with F-75's 'project-sections-model.test.ts' added as its own line) and demo-mock.test.ts (auto-merged, alerts assertions only). Neither covers the Registers or Actions tabs. Main's other changes (alerts, received-bid, AppShell bell) do not touch the project tabs or the shared hook. CI ci-mode checks passed on d5c20396 (GitHub Actions, success).
- The merge with F-71 is sound. AmountValue is gone, the stale cookies argument is dropped, and a bad page answers 422. The money, milestones, mock-live-money, project-sections, project-tabs and mock-project-tabs tests pass (123 tests, run here).
- UI-1-1 (column order, AGE right-aligned) and UX-1-2 (Severity note on Issues only) are correct, and tests cover them.
- UX-1-1: focus lands on the first new row or card after Show more. Documents is covered by the hook's existing tests. Milestones does not use the hook.
- The F-71 test edit is right. 422 `invalid_filter` for an unreadable page is the live contract.

## Findings
None.

## Verified
- TECH-1-1 | verified | `git diff origin/main 286b4105 -- frontend/src/features/projects frontend/mock` touches no F-71 money or milestones logic beyond the three named spots. money.test.tsx, milestones.test.tsx and mock-live-money.test.ts pass.
- TECH-1-2 | verified | Left unchanged by the builder, as declared in round-2/build.md. It was a timeout flake and is not a defect in this diff.
- TECH-1-3 | verified | Left as low by design (a null owner reads "Owner needed"), as declared in round-2/build.md. It is not blocking.

## Notes
- The contract has no per-page-value text for 422, but the backend decides it. `page_number` in apps/core/factory_api/work.py:158 raises 422 `invalid_filter` for a non-numeric page, 0, or a page above 10000. workspaces.py:176 uses it for the project tabs. So `?page=0` and `?page=x` on Milestones should be 422. The mock's 422 for those and its 404 for a page past the last match the F-71 test.
- A page past the last is still 404 in the mock. That was F-71's choice, and I did not check whether the live Django paginator does the same. It is outside F-75 and not blocking.
- build.md says useFocusAfterMore is shared with Milestones. It is not: only Registers, Actions and Documents use it. MilestonesTab has its own focus code. The hook change is therefore not a regression risk for Milestones, and the project-tabs Documents tests pass.
- The hook change is small and safe. A row with no link gets tabindex -1 and takes focus. Rows with links behave as before.
- Not run (out of scope for this review): the full suite, e2e, and criterion 20 against the live backend.
