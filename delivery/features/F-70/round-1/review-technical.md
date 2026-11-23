VERDICT: PASS
COMMIT: 020724df7e55a58ab2e00d32d4bdde5b273f088a
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel D-180

## Summary
- List and journey use `liveApi` and the generated live types (`operations['workspaces_projects']`, `['workspaces_project']`). Query (status always sent, q trimmed to 120, cursor, page) matches the contract.
- Unknown is never 0: `factText`, `Count` and `countOf` give "Not available" or Unknown for null finance, reviews and exceptions. Counts come from `facts.total`, `waiting` and `stopped`. No invented rules: state tags are neutral and carry the live words, and there is no NEXT MILESTONE column, badges or summary.
- Shared commit 6a58dc2b is one line in `DocumentReview.tsx` (`counts` to `tabs`) and matches the new `ProjectTabs` prop. It also removes superseded tests.
- The mock still serves the other tabs. `server.mjs` normalises UUID and P-nnnn ids, and `project-tabs.mjs` and `documents.mjs` look up by `r.id`. Targeted run of 6 files (mock-live-projects, projects-model, projects-journey, projects, project-tabs, money) passed, 165 tests.
- The mock is validated against the live contract by the new `mock-live-projects.test.ts`, which has negative cases. Playwright e2e and live-browser checks were not run (builder stated this).

## Findings
None.

## Verified
