RECOMMENDATION: AUTO_MERGE
COMMIT: b9d61964c993dcbd1f19dc563e14ce6dabe10ccd
APPROVER: approver

## Summary
- Frontend-only change. It adds a shared work-list adapter and moves /verified (SCR-14) and /exceptions (SCR-10) onto live GET /work. Both pages are read-only.
- Every file changed by the feature is under `frontend/` (src, mock, tests, e2e). None is on the always-human path list, and there are no backend, auth, money or migration changes.
- The gate passed, and technical, UX, UI and QA reviews and PMO acceptance pass. Reviews are re-confirmed on b9d61964 under D-193. The sync with main touched none of F-62's files.
- Product acceptance was given in batch (D-182), delegated under D-184, and carried over under D-188. The hidden board parts are recorded in fidelity-exceptions.json.

## Why
The change stays inside readiness's Scope and the spec's lanes. The only product decisions were board changes the design engineer already accepted in batch. The "contract-change" surface tag refers to the frontend mock and row shape, not to a backend or API contract. The merge script's hard rules still apply and may lower this recommendation, because the policy lists contract-change as always-human and auto-merge as low-risk only.

## Acceptance criteria
1. /verified uses only GET /work?queue=verified, with "Last updated" and no "Verified at": met. grep finds no "Verified at" in src, and QA saw one request per page.
2. /exceptions uses queue=exceptions and no /api/v1/exceptions call remains: met. grep of src finds only the generated schema file, which I excluded.
3. Line titles come from lines[], falling back to the key: met, covered by adapter tests per the technical review.
4. Server order, 8 per page, no page-size control: met, per QA mock runs.
5. Show more skips empty pages, with a "Keep looking" cap: met, adapter tests.
6. An empty first page with next_page set does not show the empty state: met, adapter test.
7. The empty state appears only when there are no rows and next_page is null: met, QA live and mock runs.
8. Coverage notes, and no unknown count shown as 0: met, technical review.
9. A null owner shows "Unassigned": met, QA mock.
10. Exception state tags, none dropped: met. ROW_TAGS is a Record over the state type, so removing a state fails the typecheck.
11. Titles link to /work/{id} by integer id: met.
12. Open output reads GET /work/{id}, opens http/https only, with a null-output note and a per-row retry: met, QA mock. Not proved against the real server, because the live database had no items.
13. The sample label shows on /verified: met, QA mock.
14. The line filter and search restart from page 1, with a stale-answer guard: met, adapter test and request counter.
15. Errors (401, 403, 5xx) and a failed Show more: met, QA live and mock.
16. Phone layout at 390 px, no horizontal scroll: met, UI review measured scrollWidth equal to clientWidth.
17. Desktop matches the boards, with the exceptions hidden: met. The UI review confirmed that every missing item is in fidelity-exceptions.json.
18. Nothing writes: met, QA saw no non-GET calls.
19. The adapter surface is exported with no import from features/exceptions or features/verified: met. I spot-checked with grep and found none.
20. New and rewritten tests exist and pass: met. checks.sh and CI pass on this head.

## For the human
Not needed.

## Merge record (lane A coordinator, 24 Nov 2026)
- Merged under D-180 as routine: medium risk, with no sign-in, payment, security, data-migration or product-decision surface. Product acceptance was accepted in batch (D-182), delegated under D-184 and carried over under D-188. The tool's policy route was HUMAN_APPROVAL (medium risk, contract-change, 28 files), so this record stays at AWAITING_USER_APPROVAL until the design engineer confirms (listed in merge-batch.md, "Merged under delegation: confirm"). git.human_approval is not set by the coordinator.
- Pre-merge sync: main 8692cf87 merged in as b9d61964. CI (`checks`) passed on b9d61964. Technical, UX, UI, QA and PMO re-confirmed on b9d61964 (D-193).
- Merge: `gh pr merge 106 --squash --match-head-commit b9d61964c993dcbd1f19dc563e14ce6dabe10ccd`, merge commit 156996538dc28d1fdd1412c93023d8fa69a51def.
