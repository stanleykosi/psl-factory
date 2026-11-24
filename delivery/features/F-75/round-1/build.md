STATUS: READY
COMMIT: bfcad616bcb0a7d43a339ba6f4ba1ba67681eeb9
BUILDER: builder
LANE: full

## Summary
- Registers (SCR-11) and Actions (SCR-29) now read `GET /api/v1/projects/{case_id}/registers|actions` through `liveApi` (live 1.24.0 sections), not the v7 typed arrays.
- Sections are matched by `key` (`issues`, `changes`, `emergencies`, `rfp`; Actions `meetings`); Escalations and unknown keys are never drawn. Counts (register badges, Actions header) come from `total` and `counts` only.
- Built as the boards draw: count badges, AGE column, "From <meeting> · <date>", Critical as a neutral tag, `Owner needed`, amber `Unknown` due. Hidden because live has no data: owner role/marks, Overdue row tag, page-size choice, row links.
- Paging: one shared `page`, 25 a section, "Show more" uses the selected register's `has_more` via `MoreFooter`; a failed more keeps rows with Retry.
- Mock moved to the live shape (fixtures plus handler) and validated with Ajv against the 1.24.0 200 schema.

## Changes
- `src/features/projects/sectionsModel.ts` (new): pure model: `isSectionsBody`, `availableRegisters`, `selectedRegister`, `parseSectionView`, `sectionSearch`, `buildSectionQuery`, `mergePage`, `stateTone`, `knownPriority`, `ageText`, `dueText`, `fromText`, `registerCountText`, `actionsHeaderText`.
- `src/features/projects/useProjectSections.ts` (new): one read per (case, tab, q), sequence guard, `showMore` merges the next page.
- `RegistersTab.tsx`, `ActionsTab.tsx`: rewritten on the hook and model.
- `TabParts.tsx`: `tabStateView` takes the structural `{loading}|{ready}|{error, error}` state; `OwnerValue` removed (no user left). `RowLink`, `NONE`, `useTabPaging`, `AmountValue` kept (Milestones/Documents use them).
- `tabsModel.ts`: removed register/action remnants (`REGISTERS`, `registerOf`, `parseTabView`, `tabSearch`, `ownerText`, `ageText`, `dueText`, `fromText`, `actionsSummaryText`, `registerCount*`, `Owner`). Kept `RegisterRow`/`ActionRow`/`ROW_CHECKS` registers+actions entries and `useProjectTab.ts` untouched: `ListTab`/`TabRows` still span four tabs until F-71 narrows them (F-71 introduces `ReadTab`); delete them in the merge.
- `mock/project-tabs.mjs`: new `sectionsTab` branch for registers and actions (25 a section, shared `page` with clamp, `q` filter, Actions `counts`, 422 `invalid_filter`); v7 code for milestones/documents untouched. Persona `pmo_lead` is the scripted "no issue.read" persona (no Issues/Escalations sections).
- `mock/fixtures/projects/tabs/P-0101|0102|0106.{registers,actions}.json`: live shape, all rows per section (P-0102 Issues 30 rows).
- Tests: new `mock-live-project-sections.test.ts`, `project-sections-model.test.ts`, `project-sections.test.tsx`; v7 registers/actions cases removed from `mock-project-tabs.test.ts`, `project-tabs-model.test.ts`, `project-tabs.test.tsx`, `demo-mock.test.ts`; `e2e/project-tabs.spec.ts` registers/actions tests updated (not run); `next-config.test.ts` allow-list gets only the six fixtures and the model test (they carry the contract's required `django_url`).
- Not touched: `src/shell`, `src/api`, `src/features/workspace`, `ProjectTabContent.tsx`, `useProjectTab.ts`, Money/Milestones code.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Live read, no limit/register/cursor/filters; tabs Issues, Changes, Emergencies, RFPs: `project-sections.test.tsx` (request search is `''`, tab names). 1440/390 e2e updated, not run.
2. [x] Matched by key: renamed title and unknown key tests in `project-sections.test.tsx` and `project-sections-model.test.ts`.
3. [x] Badges = `total` (P-0102 Issues 30 with 25 rows); badges/line never from rows (rows.length is used only for emptiness and focus).
4. [x] Issue row text, Critical neutral tag, `age_days` null "—", 0 "0d", no links: render test and model test.
5. [x] Changes/RFPs dashes, null owner "Owner needed" on Issues only, no role text: render test.
6. [x] No-issue persona (`pmo_lead`) and `?register=issues` fallback; `sections: []` shows No access.
7. [x] Escalation text (ISS-0240, Awaiting decision) asserted absent.
8. [x] P-0102 paging `?page=2`, 30 rows, button goes, Changes shown once; focus kept.
9. [x] Switching register makes no read; search change reads from page 1 with server counts.
10. [x] Failed more (503 on page 2) keeps rows, Retry works.
11. [x] Actions header "9 ACTIONS · 2 OVERDUE · 1 WITHOUT OWNER"; absent on null counts; "N actions match “q”" with search.
12. [x] From line, Unknown tag, Owner needed, tones by state code, no OVERDUE row tag.
13. [x] `dueText('2026-11-13T00:00:00Z')` is "13 Nov" (unit test); e2e checks "13 Nov" under Africa/Lagos (not run).
14. [x] P-0099/outside persona/P-0103/401/422/503: render tests and mock tests.
15. [x] Wrong tab or malformed section/row shows the error card (unit and render test).
16. [x] Search no-match with Clear search and the empty sentence (P-0106).
17. [x] `mock-live-project-sections.test.ts`: all fixtures and served bodies validate (Ajv strict + formats), UUID case_id, page 3 clamp, counts only on Actions, `page=0|x|` and `q=` give 422.
18. [x] Unit tests for all listed functions incl. clamp and duplicate cases.
19. [x] grep: no `api.GET`, `E-PROJECT-TAB` or `useProjectTab` in the two tabs or hook.
20. [ ] Not done: no Django 8010 / dev server run in this round (instructed not to start servers). To do by the coordinator or reviewers on the shared server.
21. [~] axe, no horizontal scroll, keyboard: arrow/Home/End covered in jsdom; axe, 390/1440 scroll and focus-after-more in `e2e/project-tabs.spec.ts` are updated but not run. Focus after "Show more" uses `useFocusAfterMore` (moves to the table frame, not the first new row, since rows have no links; phone cards get no focus move).

## Validation
- `npx tsc --noEmit`: clean. `npx eslint . --max-warnings 0`: clean.
- `npx vitest run` on: project-sections.test.tsx (25), project-sections-model (19), mock-live-project-sections (12), mock-project-tabs (12), project-tabs.test.tsx (15), project-tabs-model (9), next-config (7), demo-mock (30), mock-contract, projects-journey, frame-fixtures: all pass.
- Not run: full suite, e2e, `checks.sh` (the gate runs on Actions), design-fidelity tool (needs a production build and server; not started).

## Open
- Design fidelity not run: both boards need the tool at 1440 and 390 on a production build.
- Merge with F-71 (`fe-connect-1-money-milestones-tabs`) will conflict, small: `tabsModel.ts` (they add `ReadTab`, narrow `ListTab`), `TabParts.tsx` (`tabStateView` signature, `OwnerValue` removed here), `mock/project-tabs.mjs` (add the `sectionsTab` branch beside their milestones branch), `tests/demo-mock.test.ts`, `mock-project-tabs.test.ts`, `project-tabs*.test.*`, `next-config.test.ts` allow-list. Keep both sides; after merge `RegisterRow`/`ActionRow`/registers+actions `ROW_CHECKS` entries are dead and can go with `ReadTab = 'documents'`.
- Shared-code note: `useFocusAfterMore` focuses the table frame, not the first new row, when rows have no links (same for any link-less list).

## Edits to other lanes' tests
- `tests/issue-assign-mock.test.ts` (lane C, F-30): only the test "the register row for ISS-0233 opens W-2411" is reworked, commit bfcad616bcb0a7d43a339ba6f4ba1ba67681eeb9. Reason: live register rows have no `work_id` and are plain text (F-75 spec conflict 4, accepted under D-182). It now asserts the live P-0101 fixture carries ISS-0233 (by `reference`) with no `work_id`, and keeps `not.toContain('W-1002')`. No other test in the file changed.
