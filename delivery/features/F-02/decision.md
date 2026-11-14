RECOMMENDATION: AUTO_MERGE
COMMIT: eab6dffa85a3636cea84a414ea5ca4b55ab90534
APPROVER: approver

## Summary
- F-02 builds the My work page (`/my-work`, SCR-01) against the contract mock. It has queue tabs with counts, a table on desktop and cards on phones, search, Line and State filters, Show more with a 10/20/50 rows-per-page choice, URL state and a 15 s refresh. It reads only E-WORK-LIST. The mock gets a small `work-list.mjs` handler.
- Compared with the PR base (`dlv-00-delivery-setup`), the PR changes 15 files: `frontend/src/features/my-work/**`, `frontend/src/app/my-work/page.tsx`, the E-WORK-LIST row fixture, `frontend/mock/work-list.mjs`, a 3-line hook-up in `frontend/mock/server.mjs`, and tests. No openapi, `src/api`, `src/shell`, architecture, migration, lockfile, dependency, CI or env file changes. No always-human path or surface is touched.
- Round 2 passed on 55e8194: gate, technical, UX, UI and QA reviews, and the design engineer's product acceptance. Both blocking findings, UI-1-1 and TECH-1-2, are verified closed. The head eab6dff only merges the base (F-03, already merged as 2c3a09b) into the branch. PMO acceptance names eab6dff, and the coordinator's integration run on that head passed: checks.sh, vitest 245 and Playwright 62.
- My spot-check on eab6dff: I re-ran `tests/my-work.test.tsx`, `tests/my-work-model.test.ts`, `tests/mock-work-list.test.ts` and `tests/mock-contract.test.ts`, and all 159 tests passed. I also read the merged `server.mjs`. F-02's E-WORK-LIST branch and F-03's E-WORK-ITEM/E-WORK-HISTORY handlers sit side by side and do not overlap. `model.ts` trims `q` and drops it when empty.
- Policy note: readiness rated this medium risk, but the merge policy auto-merges low risk only. `merge-decision.py` will lower this to human approval, as it did for F-03. My recommendation is about the change's merits.

## Why
This is read-only UI against a mock. It sends no writes and touches no money, identity, data or contract. Every acceptance criterion has test or QA evidence. The two choices not drawn on the boards were the rows-per-page control and dropping the Project and Waiting-on filters. The design engineer approved both on the running page. The spec's assumptions are UI mechanics: where line options come from, a radio group instead of checkboxes, and a native select. None of them is a pricing, policy, free-versus-paid or public-copy decision.

On head naming: the gate and the four reviews name 55e8194, not eab6dff. The only difference between the two is the base merge, which is already-merged F-03 work plus the `server.mjs` conflict resolution. The integration run and my own re-run on eab6dff cover that.

## Acceptance criteria
1. Queue tabs and counts (24/12/6/2, in order, in badges): met. Component test, plus QA in the browser.
2. Unassigned only when present: met. Component test. QA saw pm with 3 tabs and an e2e test checks the tablist scrolls sideways at 390.
3. Each tab requests its queue, and keyboard works: met. Component test. QA checked the arrow, Home and End keys.
4. Kinds come from the API (Needs me shows only decide, do and fix; STARTED is not derived from state): met. Mock test and component test, which I re-ran and which pass.
5. State words and colours for all 11 states: met. Table-driven unit test, which I re-ran.
6. Station bar and age formatting: met. Unit tests, which I re-ran.
7. Sample labels: met. Component test. QA counted 22 labels.
8. Row links to `/work/{id}`: met. Component test. On eab6dff the links now open the F-03 page, and W-1001 to W-1006 resolve (PMO impact assessment).
9. Search (debounced, never an empty `q`, no-results state): met. Fake-timer test and QA. I read the trim in `model.ts`.
10. Filters (Line and State only, chips, Esc, Clear all): met. Component test, e2e, and QA.
11. Paging (limit 20 by default, Show more by cursor, 10/20/50, survives reload): met. Component test, e2e, and QA.
12. URL restore and invalid-value fallback, with no browser storage used: met. Component test. QA checked that storage stays at 0.
13. Polling every 15 s that pauses while the tab is hidden: met. Fake-timer test. QA saw the 15 s poll.
14. A refresh keeps loaded rows and focus: met. Component test.
15. A failed refresh keeps the screen, and 401 shows signed out: met. Component tests. QA forced a 500.
16. Empty Needs me for pm: met. e2e and QA.
17. Wrong role (pm opening unassigned gets 403): met. e2e, mock test and QA.
18. Load failures show the error card and Try again recovers: met. Component tests and QA.
19. Loading skeleton, with a late stale response ignored: met. Component test that resolves two responses out of order.
20. The mock honours the query and stays on contract: met. `mock-work-list.test.ts` and `mock-contract.test.ts`, which I re-ran on eab6dff. QA covered 21 paging combinations.
21. Accessibility (axe at 390 and 1440, focus rings, reduced motion): met. The e2e suite passed, 39 tests on 55e8194 and 62 on eab6dff.
22. Product acceptance items are visible: met. build.md lists them, and the design engineer approved them in round-2/acceptance-product.md.

Open and non-blocking: QA-2-1 (the mock accepts an empty `q=`), TECH-1-3 (two navigations in one tick), and PMO-2-5 (`feature.json` `operation_ids` is empty). Removing the SAMPLE DATA tag is a separate follow-up the design engineer asked for.

## For the human
Not applicable (AUTO_MERGE).

## Merge (14 Nov 2026)
The design engineer merged PR #5 themselves on GitHub as e78038f318c0c50e15e08baf23606a39a1b7f40d, while the post-merge re-reviews of the combined head eab6dff were running. Those re-reviews: technical, UX and UI passed; QA found QA-2-2 (rows W-1004..W-1006 opened different sample invoices). QA-2-2 was fixed in PR #8 (mock data only, with a guard test) and merged under the standing delegation. The factory record stays at PR_OPEN because its merge route needs QA to pass on eab6dff, which it cannot do retroactively; the merged code and the fix are both on dlv-00-delivery-setup.
