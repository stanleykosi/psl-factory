RECOMMENDATION: ESCALATE
COMMIT: cdea4f987fb2e1d59cf051a8bdf96dd7197cf6e9
APPROVER: approver

## Summary
- The work item page now reads live GET /work/{id} and its history. It adds a shared per-line adapter and an evidence picker (case file upload). No page renders the picker yet.
- Round 2 on cdea4f98: the gate, technical, security, UX, UI, QA and PMO all passed. Product acceptance is recorded from the design engineer's words "Accept F-85 at cdea4f98". git.human_approval is recorded as approved.
- The diff against main (e6c24e70) is F-85's own 22 files, all under frontend/. It has no lockfile, migration, .github or architecture paths. The round 2 changes only updated the mock and tests to API 1.24.0 and merged main.
- The policy's always-human surfaces apply: security (file upload) and contract-change (adapter and command descriptor shapes). The risk is medium, and the policy auto-merges only low. The change has 22 files against a limit of 15. Under D-184 this is not a delegated merge.
- Live work reads and a live upload are not proved, because the shared test database is missing migrations (QA-2-1, PMO-2-1). Both are non-blocking.

## Why
The code and evidence look sound and I would not block on quality. Policy puts security, contract-change, medium risk and the file-count limit on the human list, and the design engineer's own approval is what authorises this merge. The PR is mergeable on that approval.

## Acceptance criteria
1. Mock page content, with no station track and no placeholders: met (e2e, QA browser walk on 4101 to 4108).
2. Live page matches GET /work/{id}: not proved live. The mock is checked against the contract.
3. No v7 mock-only types: met (technical review).
4. Polling rules: met (unit tests, QA counted the reads).
5. Poll failure and 401/403/404 handling: met (unit tests).
6. The same "unavailable" text for 404 and 403: met on the mock (4106 and 9999).
7. Decision links only when can_decide or can_claim, and the output link: met (e2e, QA on 4103 and 4101).
8. History filters and caption: met (QA).
9. No write controls, and the only POST is the upload: met (e2e and review).
10. Adapter, weekly report panel and picker contract, with distinct UploadId and EvidenceId types: met (50 unit tests pass in QA).
11. Live upload returning 200 with upload_id: not proved live. Mock scenarios 413, 415, 422, 429 and 404 are met.
12. The picker is not rendered by any page: met (technical review).
13. The gate and drift test pass: met (round-2/checks.md, attempt 2 PASS).

## For the human
Decision needed: do you merge PR #101 (F-85) at cdea4f98, given that the live work read and the live upload are untested? You have already recorded approval. If you still approve, merge. Otherwise wait until the shared test database has its migrations and QA can re-run live.
Files to look at:
- /Users/Hunchoo/psl-factory-main/frontend/src/features/workspace/evidence.ts
- /Users/Hunchoo/psl-factory-main/frontend/src/features/workspace/EvidencePicker.tsx
- /Users/Hunchoo/psl-factory-main/frontend/src/features/workspace/adapter.ts
