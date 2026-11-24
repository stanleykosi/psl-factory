VERDICT: PASS
COMMIT: bfcad616bcb0a7d43a339ba6f4ba1ba67681eeb9
REVIEWER: technical reviewer
AUTHORITY: technical reviewer (lead)

## Summary
- Registers and Actions read `GET /api/v1/projects/{case_id}/{tab}` through `liveApi` with generated types. Sections are matched by `key`, Escalations are never drawn, and only `q` and `page` are sent. Matches `src/api/live-schema.d.ts` and the spec.
- Unknown values are never 0. The age is "—" when null (0 reads "0d"), the due date is the amber Unknown, the severity is "—", and every count comes from the server's `total` and `counts`. `isSectionsBody` rejects a malformed body, and 401, 403, 404 and 5xx each have a state. The failed-more path keeps the rows.
- The ISS-0233 test edit in `tests/issue-assign-mock.test.ts` reflects D-182 (plain row, no `work_id`). It still asserts the row exists by `reference` and that `W-1002` is absent. Nothing else in that file changed.
- The F-71 merge will conflict in eight files, all in the project-tab files (see TECH-1-1), but the conflicts are mechanical.
- Tests: 65 of 66 passed in the four files I ran. The one failure passed when run alone, so it is a timeout under load.

## Findings
- TECH-1-1 | non-blocking | medium | integration | `git merge-tree` of bfcad616 against current main (4fd055ce) reports text conflicts in `frontend/mock/project-tabs.mjs`, `TabParts.tsx`, `tabsModel.ts`, `tests/demo-mock.test.ts`, `mock-project-tabs.test.ts`, `next-config.test.ts`, `project-tabs-model.test.ts` and `project-tabs.test.tsx`. Resolve with these specifics. (a) `TabParts.tsx`: main deleted `AmountValue` and its `amountText` and `Unknown` imports, while F-75 kept them. Delete them, or the build breaks on the removed `amountText` in `tabsModel.ts`. F-75 deleted `OwnerValue`, which main kept; nothing uses it once the F-75 tabs land, so delete it and `ownerText` and `Owner`. Main's `tabStateView(TabState<ReadTab>)` accepts the structural state F-75 passes, so keep F-75's wider signature. (b) `tabsModel.ts`: after the merge `ReadTab` should shrink to `documents`, and `registers` and `actions` should leave `ROW_CHECKS`, `TabRows`, `RegisterRow` and `ActionRow`. (c) `mock/project-tabs.mjs`: main dropped the `cookies` parameter and the `fixtureFor(caseId, tab, cookies)` argument, but F-75's `sectionsTab` still passes `cookies`. Drop it, or `fixtureFor` gets an extra argument. Main's milestones branch answers 404 `invalid_query` on a bad `page`, F-75's answers 422 `invalid_filter`. Both are mocks of one live operation, so pick one on merge (422 matches the live contract). (d) Keep both sides of the tests. Main's `next-config` allow-list and F-75's both extend the same line, so union them.
- TECH-1-2 | non-blocking | low | frontend | `tests/project-sections.test.tsx:241` ("a failed Show more keeps every row..., Retry loads page 2") timed out in my four-file parallel run, which took 125s with 4 isolated workers. It passed alone in 20s. Under load the `until` helper's budget is tight. It is a flake risk, not a logic fault; consider a longer `until` timeout for that case.
- TECH-1-3 | non-blocking | low | frontend | `ActionsTab.tsx` `ActionOwner` shows "Owner needed" when `detail` is null as well as when the server says so. The contract says `detail` is the owner name or "Owner needed", so null should not occur. If it did, an unknown owner would read as "unassigned". Low risk; render "—" or Unknown for null if the contract ever allows it.

## Verified
None.

## Notes
- Not run, as instructed: full suite, e2e, servers. Design fidelity and the 390/1440 axe and scroll checks (AC 20 and 21) are still open per `build.md`.
- Tests that ran: `project-sections.test.tsx`, `project-sections-model.test.ts`, `mock-live-project-sections.test.ts` and `issue-assign-mock.test.ts`. 65 of 66 passed, with the one timeout above.
- The simplicity cost is small. `useProjectSections` (76 lines) sits beside `useProjectTab`, which stays until F-71 narrows it. A pure `mergePage` handles the shared page and duplicate rows.
