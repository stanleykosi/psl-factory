RECOMMENDATION: AUTO_MERGE
COMMIT: 81a9bb9f021d125b3c0f55234434deb93977ec7e
APPROVER: approver

## Summary
- F-72 connects document review (SCR-08) to the live document-review API. It reads the preview by integer id and records one write, the approve or return decision. It moves no money and touches no sign-in or security surface.
- Technical, UX, UI, QA and PMO acceptance all PASS on 81a9bb9f. Product acceptance is "accepted in batch, delegated under D-184" (D-182 for B7 and B8, D-183 for B12), carried over under D-188 from 7c649b84.
- 81a9bb9f only merges main commit 3b7df6cc (F-86, PR #103) into 7c649b84. The one conflict was the django_url allow-list in next-config.test.ts, resolved as a union. The reviewers report that no document or document-review file changed in that merge.
- The full delivery/checks.sh on 81a9bb9f passed (158 test files, 3751 tests, build OK), as the coordinator and the PMO file report. I did not re-run it. Gate attempt 4 PASS is on 7c649b84.
- I ran the three document suites myself on this head: 3 files, 71 tests pass. Live end to end (criterion 19) is held because no document version is seeded in the live database.
- The policy would send this to a human on three counts: the contract-change and product-decision surfaces, and 18 changed frontend files (cap 15). D-180 and D-184 delegate all three to the lane coordinator, as in F-70.

## Why
The change stays inside readiness's Scope and the spec's lanes. It consumes the existing live contract with one write guarded by `expected_revision`, and it adds no operation and no backend change. The product decisions (dropped parts, note required, phone Approve opens the note sheet) were accepted in batch. The diff outside `frontend/` is empty, and it touches no lockfile, migration, `.github` or AGENTS/CLAUDE path. The remaining risk is that the live write has never run against a real document version. The contract-validated mock, 409/422/403/5xx tests and the single-POST guard cover that, and the write is a reversible review decision.

## Acceptance criteria
1. Live preview by integer id, sections as plain text: met. document-review.test.tsx passes, and the mock e2e and the UX walk covered it.
2. Invalid id sends no request and shows "You can't open this document": met. Tests assert no fetch, and QA saw `abc` and `0` send nothing.
3. 403 and 404 look identical: met. QA saw the live wrong-user and wrong-tenant reads answer 404 with the same screen as a missing version.
4. Controls follow `decisions[]` only, with no Reject: met. Tests cover it, and the technical review confirms only approve and return are drawn.
5. Approve sends exactly the four contract keys and nothing to /tasks, /work or claim endpoints: met. The body test passes, and QA saw the phone POST body.
6. Note required before any request, 4000-character limit: met. The model and page tests pass, and QA saw the phone sheet refuse a blank note.
7. After a 200 the page re-reads and shows the live result: met. The toast fires only after a successful re-read.
8. 409 keeps the note and sends the new revision: met. QA's phone walk showed bodies with revision 7 then 8.
9. 422 `action_unavailable` message and refreshed controls, note field errors: met. Tested.
10. 403 and CSRF failure on the write record nothing and say so: met. Tested in the mock scenarios.
11. Network or 5xx shows the uncertain notice, and Try again only re-reads: met. QA saw exactly 1 POST after 3 seconds and still 1 after Try again.
12. Double press sends one write: met. The in-flight ref guard is tested.
13. A failed publication read does not break the page: met. Tested.
14. Dropped parts gone, no `django_url` in documents: met. Tests assert it, and the next-config allow-list holds.
15. Crumb is the project title and "Documents", no reference: met. The UI review checked 1440 and 390.
16. "Not the current version" and unparsed `review_status`: met. Tested.
17. Documents-tab row links only for the exact case path: met. 19 refused forms are tested in project-tabs.test.tsx.
18. Mock validates against the live contract: met. mock-live-document-review.test.ts passes (I ran it).
19. Live end to end: not met, held. No document version is seeded in the live database. The spec allows this if it is recorded and not faked, and it is recorded in build.md and review-qa.md.
20. Mock e2e at 1440 and 390: met. QA ran 11 of 11, axe included.

## For the human
Not applicable. The policy-based ESCALATE comes only from delegated rules (file cap, contract-change and product-decision surfaces), which D-180 and D-184 give to the lane coordinator. After the merge, run criterion 19 when backend seeds a document version. That live approve or return is the one thing not yet proved.
