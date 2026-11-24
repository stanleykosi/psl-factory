STATUS: READY
COMMIT: 286b41057cb2df45c6d577f7d2f4a203d8dd7fa5
BUILDER: builder
LANE: full

## Summary
- Merged origin/main (f355d339, includes F-71 and the checks.sh fix) into the branch; the 8 conflicting files are resolved (below) and Money/Milestones behaviour is intact.
- UI-1-1: Registers desktop columns are ISSUE, WHAT, SEVERITY, OWNER, STATE, AGE, AGE right-aligned last.
- UX-1-1: after "Show more" removes its button, focus lands on the first new row (desktop) or first new card (phone).
- UX-1-2: the Severity note shows only on the Issues register.
- fidelity-exceptions.json written for UI-1-2 to UI-1-5, with no sign-off invented.

## Changes
- `RegistersTab.tsx`: STATE before AGE, AGE `num` (right-aligned); the note only when Issues is selected.
- `useFocusAfterMore.ts` (shared with Milestones/Documents, behaviour unchanged where rows have links): when the first new row has no link it gets tabindex -1 and takes focus, instead of the table frame.
- Merge resolutions:
  - `TabParts.tsx`: took main's file; `tabStateView` keeps the structural `{loading}|{ready}|{error, error}` signature; `AmountValue`, `OwnerValue`, `RowLink`, `Link`/`Unknown` imports removed (nothing uses them after main removed `amountText`).
  - `tabsModel.ts`: `ReadTab` is now `documents` only; `registers`/`actions` removed from `ROW_CHECKS`, `TabRows`, `RegisterRow`, `ActionRow`, `TabSummary`, `Owner`, `Register`, `REGISTERS`, `registerOf`, `parseTabView`, `tabSearch`, `ownerText`, `ageText`, `dueText`, `fromText`, `actionsSummaryText`, `registerCount*`, `workHref`. `TabView` is `{q?}` and `buildTabQuery(view, cursor, limit)`; `useProjectTab.ts` and `DocumentsTab.tsx` adjusted to match (register dropped).
  - `mock/project-tabs.mjs`: both `milestonesTab` (F-71) and `sectionsTab` (F-75) kept; `sectionsTab` no longer takes `cookies` and calls `fixtureFor(caseId, tab)`. An unreadable `page` on Milestones now answers 422 `invalid_filter` (as Registers and Actions); a page past the last stays 404.
  - Tests: took main's `project-tabs.test.tsx`, `project-tabs-model.test.ts`, `mock-project-tabs.test.ts` and removed the v7 registers/actions cases again; `demo-mock.test.ts` keeps F-71's milestones/money lines and F-75's live registers/actions check; `next-config.test.ts` takes main's line plus `project-sections-model.test.ts` (main's regex already allows the tab fixtures).
- Edit to F-71's test (`tests/mock-live-money.test.ts`): `?page=0` and `?page=x` on milestones now expect 422; `?page=3` stays 404.
- `tests/project-sections.test.tsx`: new column order, note only on Issues, focus on the first new row (desktop and phone).
- `delivery/features/F-75/fidelity-exceptions.json`: 18 exceptions plus 5 extras. (a) spec hides: approved_by "hide accepted by the design engineer, 23 Nov 2026, D-182; exception entry pending sign-off (questions-batch B35)". (c) frame items `REGISTERS · LAGOON HEALTH`, `← Project`, `← Projects` reuse F-25's entries with their original approved_by; frame items with no F-25 match (`Tunde Bello · PMO`, tab `Registers`) and (b) sample values and both Filter and the "Changing an owner..." sentence carry "pending design engineer (questions-batch B35)".

## Fixes
- UI-1-1 | Registers columns in board order, AGE right-aligned | 286b4105
- UX-1-1 | focus on the first new row or card after Show more | 286b4105
- UX-1-2 | Severity note on Issues only | 286b4105
- TECH-1-1 | merge with F-71 resolved at the three named spots | 286b4105
- Left: UX-1-3 (Owner needed on a closed issue stays, spec display rule), TECH-1-2 (timeout flake; not changed), TECH-1-3 (null owner reads Owner needed, low), UI-1-6 (taste, for the design engineer), UI-1-2 to UI-1-5 (exceptions file, sign-off pending).

## Acceptance criteria
As round 1; criterion 21 focus now covered by render tests at both widths. Criterion 20 (live backend) and axe/e2e remain unrun here.

## Validation
- `npx tsc --noEmit` clean. `npx eslint . --max-warnings 0` clean after removing two unused helpers in `project-tabs.test.tsx`.
- vitest, 15 files, 263 tests pass: project-sections, project-sections-model, mock-live-project-sections, mock-project-tabs, project-tabs, project-tabs-model, next-config, demo-mock, issue-assign-mock, money, milestones, mock-live-money, mock-money, milestones-model, money-model.
- `git diff --name-only $(git merge-base HEAD origin/main) HEAD | grep -E '^delivery/|^\.github/'` printed nothing.
- Not run: full suite, e2e, fidelity re-run, servers.
- Note: the merge and the three fixes are in one commit (286b4105) because the merge files were already mixed with the fixes.
