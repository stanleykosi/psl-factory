RECOMMENDATION: AUTO_MERGE
COMMIT: 698c74e87d6b51a3b85829a455e34a1a883a3453
APPROVER: approver

## Summary
- Head moved from 30143e1a to 698c74e8: a merge of origin/main 90748de3 (#115 checks.sh, #112 F-61 alerts) that resolved PR #116's conflict on the shared next-config allowlist (both sides kept). No F-111 file changed since 30143e1a.
- The net F-111 diff against main is still the same nine files: issue-followup adapter, model, mock fixtures, one-line import in LiveWorkItemView.tsx, and e2e and unit tests. No protected path, migration, lock file, contract or workflow file is touched.
- Technical, UX, UI and QA PASS name 698c74e8. Product acceptance is carried over under D-184, D-187, D-202 and D-203, and the 57 fidelity exceptions and eight waivers are signed. CI `frontend-checks` PASS on 698c74e8 (run 45431101897, `round-2/checks-sync.log`).
- Spot-check: overdue comes only from `timing.reminder_overdue` and `escalation_overdue` (model.ts:83), and no-owner from `team.assignment_id === null` (model.ts:50). Nothing in the feature calls `liveApi.POST`.
- `round-2/checks.md` still names 8a5c09fe as the gate head. The head's own CI result is in `checks-sync.log`, which is the D-193 sync re-check the PMO file relies on.

## Why
Read-only screen inside readiness's Scope (risk low, surfaces ui and api, no always-human surface). The only change since my last recommendation is a main-side merge that does not touch F-111 behaviour. The known gaps are either accepted under named authority or are verification follow-ups, not product decisions. The one criterion not met (live comparison, AC17) cannot cause a write, and the owner accepted it for this read-only line.

## Acceptance criteria
1. AC1 (Open `/work/5101`, the header, facts and Blocks): met on the mock, per QA round 2 (fixtures 5101 to 5108, both widths, GET only). Blocks is plain text, not a link (TECH-1-3, accepted under D-202).
2. AC2 (timeline rows exactly as sent): met. Mapper and unit tests in `tests/issue-followup.test.tsx`, per QA.
3. AC3 (overdue banner from flags only): met. Unit test flips both flags to false with past dates and the banner goes (`tests/issue-followup.test.tsx`, around line 106). I read the logic at model.ts:83.
4. AC4 (no-owner state, no 0 days, no timing rows): met per QA e2e and mapper test. I read the no-owner logic at model.ts:50.
5. AC5 (verified state, no "Closed" while Resolved): met per QA e2e.
6. AC6 (Blocks fact left out when both are null): met per mapper unit test.
7. AC7 (banned strings absent): met. QA e2e checks the strings are absent on all four states.
8. AC8 (GET only, no write control enabled): met. No `liveApi.POST` or POST method in the feature's code (grep). QA recorded GET requests only.
9. AC9 (flagged controls drawn disabled or hidden): partly met by design. Nothing is drawn for writes. Accepted under D-202 and D-187, and UX-2-1 asks for the spec text to be corrected.
10. AC10 (messages 403 keeps the page): met per QA e2e (`/work/5105`).
11. AC11 (detail 503, per-section Try again): partly met. The failure shows a reload message with no per-section Try again. Accepted under D-202, and per-section retry belongs with F-87 and F-95.
12. AC12 (404 and unseen record show "This record is unavailable."): met per QA.
13. AC13 (401 and 403 csrf handling): met per QA scenarios and unit tests.
14. AC14 (adapter uses only the work item's case_id): met per unit test on the request URLs.
15. AC15 (polling with fake timers): not covered here. Polling is `PanelView`'s job (F-85), tracked as TECH-1-6, non-blocking.
16. AC16 (registration and `commands() = []`, generic fallback): met per unit test.
17. AC17 (live Django comparison): not met. The local database has no project issue (QA-2-4, PMO-2-1). Accepted as a demo-readiness step: the page is read-only, and unknown values show as "Not recorded", not as zero.
18. AC18 (viewport check at 1440 and 390 against SCR-30): met per UI round 2, with the exceptions in `fidelity-exceptions.json` signed under D-203.
19. AC19 (lint, typecheck, unit tests, live-schema drift): met. CI `frontend-checks` PASS on 698c74e8, and the Ajv contract test (12 of 12) passes.

## For the human
None needed for the merge. Follow-ups, none blocking:
- Before the demo, the integration owner seeds one project issue, starts its follow-up work item, and compares the page with the live reads (PMO-2-1, AC17). Record the result in `BUILD-TESTS.md`.
- The design engineer checks the merged screen on port 3000 after merge, as D-184 says. Anything they dislike becomes a fix.
- Open non-blocking findings go to their owners: QA-2-1 (a 404 on one read replaces the whole panel) belongs with F-95.
