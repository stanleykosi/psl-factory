STATUS: READY
COMMIT: 9ac9d703289113821b42cbaa66f241535ed2a9bb
BUILDER: builder
LANE: full

## Summary
- Main (merged to API 1.26.0) now passes typecheck, lint, full vitest (157 files, 3810 tests) and the production build.
- Test and mock fixtures moved to the 1.26.0 shapes; no assertion weakened, no product code changed.

## Changes
- frontend/tests/destinations.ts, tests/shell-live.test.tsx: /me fixture gains positions (empty), destinations gain url and available.
- frontend/mock/fixtures/me.*.json: destinations url (= key) and available; positions copied from role-dashboard.<persona>.json.
- frontend/mock/fixtures/projects/list.json, mock/demo-projects.mjs: next_milestone null (unknown, not invented).
- frontend/mock/projects.mjs: list body carries totals {all, active, closed} counted from the persona's visible rows.
- frontend/tests/mock-live-projects.test.ts: the hand-built list body adds totals; the key-list assertion now includes totals and its title says "no limit" (shape changed, not weakened).

## Fixes
- F-68 | /me and /projects fixtures to 1.24.0 then 1.26.0 | 03e7165e, 22e9439c

## Acceptance criteria
1. [x] tsc clean, lint clean, npm test green, build passes on 1.26.0.

## Validation
npx tsc --noEmit: 0 errors. npm run lint: clean. npx vitest run: 157 files, 3810 tests passed. npm run build: success. Earlier failures in assistant, cash-forecast were timeouts under heavy machine load; they pass alone and in the full run. package-lock.json unchanged by the merge.

## Coordinator merge of main (after the builder's 22e9439c)
- Main moved to e6c24e70 ("Resolve Railway code review findings"), where the backend developer had fixed the same /me and project fixtures and tests (11 files). The coordinator merged it as a2f752fb and took main's version of every conflicted file: the 7 me.*.json fixtures, mock/projects.mjs, tests/destinations.ts, tests/mock-live-projects.test.ts and tests/shell-live.test.tsx. F-68's other fixes (mock-contract, cash-forecast, the remaining mock-live and single-test files) are kept.
- Re-checked on a2f752fb: `npx tsc --noEmit` 0 errors; `npx vitest run` 157 files, 3810 tests passed. package-lock.json unchanged.

## Superseded (coordinator, 23 Nov 2026)
- After merging main e6c24e70 the branch tree is identical to origin/main (`git diff origin/main HEAD` is empty): the backend developer's commit made the same fixture and test changes. Nothing is left to merge, so no PR was opened.
- Main e6c24e70 checked on that tree: `npx tsc --noEmit` 0 errors, `npx vitest run` 157 files / 3810 tests passed. The checks.sh gate timed out at 30 minutes in lint while the machine ran seven test suites at once (load about 450), so lint and build on main are not confirmed by this feature.
- The temporary worktree lane-a-hot is removed. F-68 stays open in the records as superseded; it needs no review or merge.

- Brought to main e2f44656 as 9ac9d703 (tree identical to origin/main) so the confirmation gate checks current main.
