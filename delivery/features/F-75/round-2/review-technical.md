VERDICT: PASS
COMMIT: 286b41057cb2df45c6d577f7d2f4a203d8dd7fa5
REVIEWER: technical-reviewer
AUTHORITY: technical reviewer (lead)

## Summary
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
