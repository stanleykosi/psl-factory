RECOMMENDATION: ESCALATE
COMMIT: 6a09ff21cf6f75f7466743fcb3609bf3b8f54195
APPROVER: approver

## Summary
- The work item page now reads live GET /work/{id} and history. It adds a shared per-line adapter and an evidence picker (case file upload). The picker is not rendered by any page yet.
- Technical, security, UX and UI reviews, integrated QA, PMO acceptance and product acceptance all passed on 35189b45. Head 6a09ff21 only adds a merge of main (F-58 sign-in) with one resolved conflict in frontend/mock/server.mjs. Targeted tests passed (242), and checks.sh passed on the merged head.
- Criteria 2, 19 and the live half of 22 are proved on the mock only. The live half is still pending (PMO-1-1).
- The diff touches 72 files, which is over the 15-file limit. It also has a security surface (file upload) and a contract-change surface (adapter and command descriptor shapes). Under D-184 this merge is not delegated.

## Why
The code and evidence look sound, and I would not block the merge on quality. Policy puts security, contract-change and the file-count limit on the human list, and the live upload has never run against real Django. That is a person's call.

## Acceptance criteria
1. 4102 page content, no station track or placeholders: met (e2e, QA browser walk).
2. Live page matches GET /work/{id}: not verified live. The mock is checked against contract 1.22.0. Live is pending.
3. No v7 mock-only types: met (technical review).
4. Polling rules: met (unit tests, QA counted 3 reads in 11 s on 4102, 1 on 4101).
5. Failed poll and 401/403/404 handling: met (unit tests).
6. 404 and 403 show the same "unavailable" text: met on the mock. Not checked live signed in.
7. csrf_failed handled apart from no-access: met (unit test and mock scenario).
8. 401 shows the signed-out state with a next link: met. Browser sign-in link not proved on QA's base, and the merge with F-58 only touched the mock server guard.
9. Decision links only when can_decide or can_claim: met (e2e, QA).
10. Output link equals output_url: met.
11. Null revisions not shown as 0: met.
12. History tabs, kinds and caption: met.
13. Unknown station and status shown raw: met.
14. History empty and error states: met.
15. No write buttons, only the upload POST: met (grep and e2e).
16. Adapter exports and test: met.
17. Null tokens and keyless lines: met.
18. Weekly report panel via the adapter: met on the mock.
19. Live weekly report panel: not verified live. Pending.
20. Unknown panel key is harmless: met.
21. correct descriptor is disabled and has no button: met.
22. Picker upload: met against the mock. Live upload is not proved, because file storage was not running.
23. Pre-send refusal of .exe and files over 10 MB: met.
24. Upload error mapping and no auto-retry: met.
25. csrf_failed during upload: met.
26. UploadId and EvidenceId stay distinct: met.
27. fileToEvidence is labelled as a proposal: met.
28. Picker is not rendered by any page: met.
29. Picker uploads only to the loaded item's case_id: met.
30. Viewport check at 1440 and 390: met (UX, UI and QA). The fidelity tool fails because of the hidden parts, and the UI review recommends adding a fidelity-exceptions file for F-85.
31. Lint, typecheck, tests and drift: met. Full checks.sh passed on 6a09ff21 (3887 tests).

## For the human
Decision needed: merge PR #101 (F-85) as is, with the live halves of criteria 2, 19 and 22 still unproven? The merge also adds a case file upload component that no page uses yet.
Files to look at:
- frontend/src/features/workspace/evidence* (the upload and the fileToEvidence proposal)
- frontend/src/features/workspace/adapter.ts (the contract shape lane A and B build on)
- frontend/mock/server.mjs (the merge conflict resolution)
- delivery/features/F-85/round-1/review-security.md
Also add a fidelity-exceptions.json listing the hidden station track, facts strip and agent steps, as the UI review asked.
