VERDICT: PASS
COMMIT: ba04923c108e0180ffdbd49404afc42fceeb191d
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The merge with F-26 keeps both features' code and follows my second-merge list. I checked each of the six points in the code.
- The round-3 changes are small: the ellipsis rule is removed, the route line height is unitless, `TabEmpty` is an h2, and a 1024px e2e case is added. The wrapped cells show every fact in full.
- The only test file edited in the merge is F-26's `mock-money.test.ts`. That edit is correct and weakens nothing.
- I did not run the checks. build.md reports `delivery/checks.sh` passing on this head and 71 e2e tests passing on the merge commit.

## Findings
- TECH-3-1 | non-blocking | frontend/mock/project-tabs.mjs:1-5 | The header comment still says "Documents and Money are not mocked here (501)". Money is now answered by `money.mjs` before this handler, and `OTHER_TABS` was correctly cut to `['documents']`. | Change the comment to "Documents is not mocked here (501); money goes to money.mjs". Comment only.

## Verified
- ProjectJourney chain | verified | `ProjectJourney.tsx` is `journey` then `hasTabContent(tab)` (`ProjectTabContent` with `journey.case_id`) then `tab === 'money'` (`MoneyTab`) then `ComingNext`. Both features' imports are kept, and `ProjectView` has no extra prop.
- server.mjs ordering | verified | F-26's `isMoneyRequest` dispatch (line 263) comes before the `M1_OPERATIONS` check (264), so money never reaches F-25. `E-PROJECT-TAB` is in `M1_OPERATIONS` once and excluded from the fixture loader (222). The `projectTab` import (26) and dispatch (281) are kept.
- projects-journey.test.tsx | verified | The `page` and `open` unions are `'milestones' | 'documents'`. The coming-next `it.each` has one row, `documents` at index 2. The `Money` tab-bar row at line 105 is a separate F-07 case about the tab bar and is untouched.
- 501 cases | verified | `mock-projects.test.ts` stays on `documents`. `mock-project-tabs.test.ts` asserts only `documents` as 501. `mock-contract.test.ts` still asserts 501 for E-PAYROLL-MATCH and keeps `tab: 'milestones'` in `PATH_VALUES`. A search of tests and e2e finds no remaining expectation that milestones, registers or actions return 501, and none that Milestones or Money "comes next".
- mock-money.test.ts | verified | The 501 loop now lists only `P-0101/documents` and `P-0109/money`. Both still answer exactly 501, and the tabs F-25 now serves are no longer expected to. The assertion has the same strength, with fewer wrong paths, and nothing is skipped.
- project-tabs.mjs | verified | `OTHER_TABS = ['documents']`. An unknown tab is 404 and the 403, 404 and query rules are unchanged.
- Round-3 diff | verified | The ellipsis rule is deleted, with the fixed column widths kept. The route line height is `1.3`. There are no changes to the contract, the hook or the model. This closes TECH-2-1, because wrapped cells show every fact in full, and the 1024px e2e covers it. TECH-2-2 stays accepted.

## Carried forward
- TECH-1-4, TECH-1-6 and TECH-2-2 stay accepted. Nothing in the merge changes their impact.
