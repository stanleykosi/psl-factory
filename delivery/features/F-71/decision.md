RECOMMENDATION: AUTO_MERGE
COMMIT: f29087ed4c453d75e2766dfa992956fcc94d9aab
APPROVER: approver

## Summary
- F-71 connects the Money (SCR-12) and Milestones (SCR-38) tabs to the live API. It is read-only: no write, sign-in, money-moving, security or migration surface.
- Technical, UX, UI, QA and PMO all PASS on f29087ed. Product acceptance is "accepted in batch, delegated under D-184" (D-182, D-185, D-202 "Sign all"), carried over under D-188/D-193 from cfc3c462.
- f29087ed is the one pre-merge sync with main 4a88c26b. F-71's own diff and the sync diff share only frontend/mock/server.mjs, where both routes are kept. The ci-mode checks passed on f29087ed. The round-2 gate passed on cfc3c462.
- Diff against 4a88c26b touches only files under frontend/ and F-71 records. It touches no lockfile, migration, .github, AGENTS/CLAUDE or other protected path.
- The policy would send this to a human on the contract-change and product-decision surfaces and on file count (47 changed files, cap 15). D-180 and D-184 delegate those to the lane coordinator, as in F-72.

## Why
The change stays inside readiness's Scope: two read tabs on the live /money, /milestones contract, with no write. Unknown money stays Unknown, is never shown as 0 and is never summed. Paid status shows as given and is never inferred. The product choices (hides, NGN for the currency symbol, 46 signed fidelity exceptions and 6 visual waivers) were accepted in batch by the design engineer. The remaining risk is that a populated live body has never been rendered (TECH-1-4). The contract-validated mock and empty live bodies cover that, and the change is read-only.

## Acceptance criteria
1. Money rows per stage, Unknown for null amount, paid or owed, never 0 or summed: met. I ran money.test.tsx, milestones.test.tsx and money-model.test.ts on this head: 3 files, 96 tests pass. QA's walk found no 0.00 and no total.
2. Per-invoice status as given, paid and owed as given: met (tests above, technical review).
3. Drill-down through ?figure= with as_of and the limited warning: met (tests, QA mock walk at 1440 and 390).
4. Milestones from /money items plus recorded completions, null additional_amount shown as Unknown: met (milestones tests).
5. No finance.read: completions only, a plain note, no figures: met (QA walk on P-0107/P-0108).
6. No non-GET request from either tab: met (QA).
7. Design fidelity: met. Coverage 100% on six runs, with signed exceptions under D-202.
8. Live smoke: held. The live project is empty (0 items, 0 completions), and a populated live body is unproved. The spec allows this fallback and the reviews record it.

## For the human
Not applicable. After merge, check a populated live project when the backend seeds money data (TECH-1-4). QA-2-1 and QA-2-2/TECH-2-1 are routed to F-78.
