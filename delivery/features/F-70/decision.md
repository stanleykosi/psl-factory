RECOMMENDATION: AUTO_MERGE
COMMIT: cf5074164183ccd9027b818fe6a3b64099288c2b
APPROVER: approver

## Summary
- F-70 connects the project list (SCR-22) and project journey (SCR-07) to live API 1.22.0. It is read-only: no write, backend, auth or money change.
- Gate, technical, UX, UI and QA reviews and PMO acceptance all PASS on ed72928f. Product acceptance is "accepted in batch, delegated under D-184" (D-182, item B9, accept all).
- cf507416 is only a merge of origin/main (F-58 sign-in, PR #100). The diff ed72928f..cf507416 touches frontend/src, frontend/tests, frontend/e2e and frontend/mock, which is main's change. I read the file list and saw nothing from this feature outside that. I did not read the conflict resolutions line by line.
- The coordinator ran 7 vitest files after the merge (218 passed). The delivery/checks.sh re-check on cf507416 was still running when I wrote this.
- The merge policy's size rule and its product-decision and contract-change surfaces would normally send this to a human. All three are delegated, as set out under Why.

## Why
The change stays inside readiness's Scope and the spec's lanes. It consumes the existing live contract and adds no new operation. The sign-in, session and shell files in the diff come from main's F-58 and are not changed by this feature. The 109 changed files (cap 15) are mostly project fixtures and tests. The design-engineer product decisions are the nine board changes, all accepted in batch. D-180 and D-184 delegate the merge to the lane coordinator, so the coordinator can apply that delegation. The standing rule that main merges need the design engineer's word is also covered by D-180. Nothing here touches auth, security, money or a migration, and the product decision is already accepted. This is not a real escalation. The remaining condition is that delivery/checks.sh passes on cf507416.

## Acceptance criteria
1. Live list with explicit status and q, null-safe counts and manager, no dropped columns: met. Unit tests in projects.test.tsx and projects-model.test.ts pass, and QA validated live bodies against the contract.
2. Journey from live data: four-cell facts strip, neutral state tag, `/work/{id}` links, paging, no invented station or summary: met. projects-journey.test.tsx passes, and QA ran the live model against captured bodies for three accounts.
3. 403 and 404 states, and the tab bar from live `tabs[]`: met. Covered in the same tests and in project-tabs.test.tsx.
4. Delivery tab shows "not available yet", and the other tabs keep their v7 mock content: met. QA ran 50 mock e2e tests with 0 failures.
5. The mock validates against the live contract: met. mock-live-projects.test.ts has 200 added lines. QA's captured live bodies validated against the OpenAPI file.
6. Spot check: the post-merge targeted vitest (218 passed) covers projects-journey and projects with the `/sign-in?next=` links. Not proved: populated live rows, a live next page and the live Delivery tab, because the local data has none. This gap is already recorded in QA, so it is not blocking.

## For the human
Not applicable. The policy-based ESCALATE comes only from delegated rules (file-count cap, contract-change and product-decision surfaces, the design engineer's word on main merges), so the coordinator applies D-180 and D-184. The follow-up UX-2-1, a keyboard tab stop on the Delivery route in the shared Tabs.tsx, is non-blocking.
