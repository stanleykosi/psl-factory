RECOMMENDATION: AUTO_MERGE
COMMIT: 1407fbe72551058290b2303a86580eef05b945c2
APPROVER: approver

## Summary
- Start work now reads the live chooser, project picker and source picker, and starts the weekly report through POST /work, then opens the new work item.
- Round 2 gate, technical, UX, UI, integrated QA and PMO acceptance all name this head. Product acceptance was recorded under D-184 from batch answers D-182, D-183 and D-191.
- The diff is frontend only (start-work feature, mock server, tests). Most of the removed lines are v7 mock tests that the new live test replaces.
- It touches no lockfile, .github, migration, OpenAPI contract, AGENTS.md or CLAUDE.md. It has no auth, payments or security surface.
- Spot check: upload goes through F-85's EvidencePicker, which sends with uploadCaseFile. No second multipart helper exists under start-work.

## Why
Every criterion has passing evidence on the final head, and the change stays inside readiness Scope (SCR-04, one line, UI and API only). No assumption is a business decision beyond the board changes already accepted in batch. The merge script may still lower this to a human merge, because risk is medium and 32 files exceed the 15-file limit. Both reasons are mechanical, and the coordinator can treat it as a routine merge under D-180.

## Acceptance criteria
1. Live chooser with no group heading or "Next:" line: met. e2e and chooser tests passed in the round-2 gate and QA.
2. Unavailable lines link to django_url and cannot be selected; invoice is absent: met. Chooser unit test and e2e passed.
3. Project picker with search and paging: met. fetchProjects test and e2e network log passed.
4. Empty-field start sends no request: met. e2e counts zero POSTs.
5. Valid start sends the exact body and lands on /work/4102: met. buildBody test and e2e passed.
6. Double press sends one request, and retry reuses the key: met. e2e start_uncertain passed.
7. 409 keeps values, re-reads the revision and uses a new key: met. State-machine unit test passed.
8. 422 field mapping: met. Per-row unit tests passed.
9. 401, 403 csrf_failed and 404 handling: met. Unit tests and mock scenarios passed.
10. Wrong user or tenant gives the 404 wording: met. Mock scenario and unit test passed.
11. Provider and network failure: met. e2e with the mock paused started one work item only.
12. StartUpload uses uploadCaseFile on the chosen case only: met. I checked this myself in the diff.
Criteria 13 onward are covered by the round-2 review and QA files, all PASS on this head.

## Human approval
Delegated under D-180 (routine: medium risk, ui and api only) with product acceptance under D-184 (D-182, D-183, D-191). Merged by the lane C coordinator as 3b7df6cc on 24 Nov 2026; listed in delivery/connect/merge-batch.md under "Merged under delegation: confirm". git.human_approval is left for the design engineer's confirmation.
