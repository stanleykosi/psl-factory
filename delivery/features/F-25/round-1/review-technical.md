VERDICT: PASS
COMMIT: 4686abdab3e88ab0d1a4a6c8f093f7b389dbae2c
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The three tabs are read-only: the only calls are E-PROJECT-TAB GETs, with no write, no form and no completion control. Nothing new is read from /me. Nothing under src/api, model.ts, architecture or design changed.
- Unknown is never 0. Amounts go through `amountText`, which returns undefined and so draws the Unknown tag. Nothing is added: the change amount sits beside the contract amount as "+ the change · change amount X". Completion, invoice and paid are three separate cells, and none is derived from another.
- 403 and 404 on a tab show one shared "No access" panel and no row text. P-0099 makes no tab request. A 401 goes to sign-in with the path and query kept.
- The shared-file footprint is small and matches the spec, apart from two small extras: the `caseId` prop and the `PATH_VALUES` entry. Both are non-blocking.
- The F-26 merge will need two follow-up test edits (TECH-1-1, TECH-1-2). Neither breaks this branch.
- I did not run the checks. checks.md shows GATE PASS on this head, and I read the code.

## Findings
- TECH-1-1 | non-blocking | frontend/tests/mock-project-tabs.test.ts:70 | `GET /projects/P-0101/money` is asserted to be 501 through the full mock server. F-26 routes money to `money.mjs` before the M1 check (its server.mjs line ahead of `if (!M1_OPERATIONS...)`), so this assertion fails after the second merge. | Whoever merges second drops `money` from this assertion and keeps `documents`. Do not restore the 501 in `projectTab()`.
- TECH-1-2 | non-blocking | frontend/tests/project-tabs.test.tsx:426 | The test title says "documents and money keep their coming-next panel" but it only opens `documents`, so the name over-claims. It is not wrong today. After the F-26 merge, money is no longer coming-next. | Rename to "documents keeps its coming-next panel" in this round or at merge. This also affects the `projects-journey.test.tsx` row (see the merge list below).
- TECH-1-3 | non-blocking | frontend/src/features/projects/ProjectJourney.tsx:187 | `ProjectView` and `ProjectPage` gain a `caseId` prop. The spec says "one import and one branch, nothing else changes", and `journey.case_id` is already available (F-26 uses it for `MoneyTab`). The extra prop widens the diff in a file both features touch and makes the second merge conflict more likely. | Pass `journey.case_id` to `ProjectTabContent` and revert the signature change. Optional, because the result is the same.
- TECH-1-4 | non-blocking | frontend/src/features/projects/ProjectTabContent.tsx:21 | On a tab 403/404 the `PmRoute` line ("PM <name> · Route ...") still draws above the panel that says "Nothing from it is shown here". The name comes from E-PROJECT, which the person may already read, so this is not a leak. It is a mixed message, and the PM name appears on the one state where the spec asked for no names. | Either hide `PmRoute` while the tab state is an access error, or accept it and confirm with the security reviewer. The tab state lives inside each tab, so hiding it needs the state lifted or a small context. Likely accept.
- TECH-1-5 | non-blocking | frontend/src/features/projects/tabsModel.ts:`invoiceWord` and MilestonesTab.tsx:`InvoiceCell` | An invoice whose `state` is absent or not in `STATE_TAGS` shows only its reference. That reads as "no status" and not as Unknown. It is a fact the data could not supply, so the amber Unknown the spec uses elsewhere would be more honest. | Draw `<Unknown />` in place of the word when the state is missing or unrecognised. Small change plus one test.
- TECH-1-6 | non-blocking | frontend/tests/mock-contract.test.ts:39 | `tab: 'milestones'` was added to `PATH_VALUES`. The spec does not list this file, but without it the generic persona and schema loop cannot call E-PROJECT-TAB. The addition is additive, loosens nothing, and is flagged in build.md. | Accept. When F-26 merges, keep this entry. F-26 edits other lines in this file (E-REPORT becomes E-PAYROLL-MATCH), so a conflict is unlikely.

## Checked, no finding
- Contract: `isTabResponse` checks each row. The mock slices fixtures and never computes a value. Every fixture is validated against the generated 200 schema. `useProjectTab` makes one request per view, with a sequence guard, no polling and no automatic retry. A 401, 403 or 404 on "Show more" replaces the panel, and other errors keep the rows with a "Try again".
- ListToolbar: Filter is optional, defaults are 0 and false, existing callers are unchanged, and there is a test for both modes. Phone search needs no Filter.
- Tests: existing assertions were changed only as the spec lists (mock-projects 501 case moves to `documents`; journey row `milestones` becomes `documents`; projects e2e). The `projects-journey.test.tsx` type union keeps `'money'`, so nothing is weakened. No test is skipped.
- server.mjs: `E-PROJECT-TAB` is in `M1_OPERATIONS` and excluded from the per-operation fixture loader. One dispatch line sits after the persona and scenario handling. Money and documents answer 501 from `projectTab()`.

## What the second merge must keep (F-25 and F-26)
- server.mjs: F-26's `isMoneyRequest` dispatch stays where it is, before the `M1_OPERATIONS` check, so money never reaches F-25's `projectTab()`. Keep F-25's `E-PROJECT-TAB` entry in `M1_OPERATIONS`, its loader exclusion, the `projectTab` import and its dispatch line. Do not drop either side's import.
- ProjectJourney.tsx: one chain, `journey ? JourneyTab : hasTabContent(tab) ? ProjectTabContent : tab === 'money' ? MoneyTab : ComingNext`. Keep F-25's imports and `hasTabContent`, and keep `ComingNext` for Documents. If TECH-1-3 is not taken, keep `caseId` on `ProjectView`.
- projects-journey.test.tsx: the F-25 and F-26 edits are the same row change in the same case. The merged result has `documents` only, with `'milestones' | 'documents'` in the type union. F-26 drops `money` there. Keep F-25's `'documents'` row at index 2.
- mock-projects.test.ts: the 501 case uses `documents`, which both features reach. Do not merge back to `milestones` or `money`.
- mock-project-tabs.test.ts:70 and project-tabs.test.tsx:426: edit as in TECH-1-1 and TECH-1-2.
- After the merge, rerun `delivery/checks.sh` and both features' e2e at 390.
