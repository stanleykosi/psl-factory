VERDICT: PASS
COMMIT: b9c62eb095afab1a2df87f562ffef833678e021c
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- All four findings I was asked to verify (TECH-1-1, 1-2, 1-3, 1-5) are fixed. I read the diff 4686abda..b9c62eb0.
- The diff is 8 files: 5 under `src/features/projects`, 2 test files, and `project-tabs.css`. Nothing changed in the contract, the mock, `server.mjs`, `ListToolbar` or `model.ts`.
- No test is weakened. The round also adds an invoice-state test and a once-only empty-sentence assertion.
- I did not run the checks. build.md reports `delivery/checks.sh` and the 58 e2e tests passing on this head.

## Findings
- TECH-2-1 | non-blocking | frontend/src/features/projects/project-tabs.css:`.ptabs__ms td:not(:nth-child(2))` | Milestone cells other than CONTRACT AMOUNT are now one line with an ellipsis. A long completion text, invoice word or change title is cut on screen, so the full fact is no longer visible. The text stays in the DOM and is read by screen readers, but a sighted user cannot read it. This trades fidelity for completeness. | Accept for this round. Give the cells a `title` attribute (or let the cell wrap at phone width), and note it for the UI round.
- TECH-2-2 | non-blocking | frontend/src/features/projects/TabParts.tsx:`TabEmpty` | `TabEmpty` hard-codes the `psl-empty` markup and an `h3` in place of the shared `EmptyState`. This avoids the repeated sentence the UX review asked to remove. It copies the shared component's markup, and the page's heading levels for the empty state are unchecked. | Accept. Better still, give `EmptyState` an optional title-only mode later and use it here.

## Verified
- TECH-1-1 | verified | `mock-project-tabs.test.ts` no longer asserts that money returns 501; the case is now "documents answers 501; unknown tab 404", and the test name matches. The assertion is safe against the F-26 merge, and the `projectTab()` handler is unchanged.
- TECH-1-2 | verified | `project-tabs.test.tsx` is renamed "documents keeps its coming-next panel", and the body still opens `documents`.
- TECH-1-3 | verified | The `caseId` prop is gone from `ProjectView` and `ProjectPage`; `ProjectTabContent` gets `journey.case_id`. The `ProjectJourney.tsx` diff against the base is now one import, one `hasTabContent` branch and that prop, which is the same shape F-26 uses.
- TECH-1-5 | verified | `InvoiceCell` draws `' · '` and then the state word or `<Unknown />`, so a missing or unlisted state reads Unknown. The new test covers both an absent state and `state: 'surprise'`, expecting `INV-0398 · Unknown` and `INV-0412 · Unknown`.

## Carried forward
- TECH-1-4 and TECH-1-6 are accepted and unchanged; there is no new impact.
- The second-merge list from round 1 still applies. Only one point changes: `ProjectJourney.tsx` now takes nothing extra from F-25 beyond the import and the branch.
