RECOMMENDATION: AUTO_MERGE
COMMIT: d5c203969d05cdde59c15127792da33cc30d3580
APPROVER: approver

## Summary
- F-75 moves the Registers (SCR-11) and Actions (SCR-29) tabs to the live sectioned project-tab read. It is read-only, with no write, sign-in, money, security or database surface.
- Technical, UX, UI, QA and PMO all PASS on d5c20396. Product acceptance is "accepted in batch, delegated under D-184" (D-182), with fidelity sign-offs approved under D-207 (B35: 15 exceptions, 4 visual waivers), carried over under D-188/D-193 from 286b4105.
- d5c20396 is the one pre-merge sync with main eb100065. The sync shares only next-config.test.ts and demo-mock.test.ts with F-75's diff, and RegistersTab.tsx and ActionsTab.tsx are unchanged by it. Ci-mode checks passed on d5c20396. The round-2 gate passed on 286b4105.
- The diff is 27 files, all under frontend/ plus F-75 records. No lockfile, migration, .github, AGENTS/CLAUDE or other protected path is touched (D-200). Two other lanes' tests are edited (issue-assign-mock per D-182 conflict 4, mock-live-money because 422 is the live contract), and build.md gives the reasons.
- The merge-decision script will probably lower this to a human on the contract-change surface and on file count (27, cap 15). D-180 and D-184 delegate those to the lane coordinator, as in F-71. Main is under a merge freeze for F-87, so the coordinator merges after it lifts.

## Why
The change stays inside readiness's Scope and the spec's lanes. Unknown values stay Unknown and are never shown as 0, and sections are matched by stable key, not title text. The product choices were accepted in batch by the design engineer. The remaining risk is that populated live rows have not been rendered, because the live project is empty. The contract-validated mock covers rows, and the change is read-only.

## Acceptance criteria
1. Registers render the returned sections, selected by key, with per-register counts and a shared-page-safe Show more using the selected section's has_more: met. I ran project-sections-model.test.ts and project-sections.test.tsx on this head, and 45 tests pass. QA walked the mock at 1440 and 390.
2. Actions show owner (or "Owner needed"), due (or Unknown) and state as given, with the header counts coming from the server only: met (same tests, QA walk).
3. Loading, empty, error, forbidden, not-found and as-of states: met (QA forced 401/403/404/422/500/503).
4. No write request from either tab: met (read-only GET, per technical review and QA).
5. Design fidelity: met. Coverage is 100% after exceptions, with the 15 exceptions and 4 visual waivers signed under D-207.
6. Live smoke: partly met. The live bodies validate against the 1.24.0 schema, and only the empty state is proved live. Live rows, live counts and live Show more are proved only on the mock. PMO-2-1 to PMO-2-3 are open and non-blocking.

## For the human
Not applicable. After merge, check a populated live project when the backend seeds register and action data. The 4 "exactly one request" e2e checks fail under `next dev` because of the StrictMode double effect, and they are not proved under a production build.
