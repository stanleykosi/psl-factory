RECOMMENDATION: ESCALATE
COMMIT: f296a554242b27ef690d2ec359765ff2669b5377
APPROVER: approver

## Summary
- Work-item controls on the live API: "Check what happened" (reconcile), Resume/Cancel, Pause/Continue background, via the shared adapter (`useWorkCommand`, `useWriteLock`, `workItemCommands`).
- On this head the CI checks, technical (Opus), UX, UI, QA, PMO and product acceptance all pass, and each file names f296a554.
- The change is high risk and touches the contract-change and product-decision surfaces. It changes 19 files, over the 15-file auto-merge cap.
- PMO-3-1 (no live proof of Check what happened, Resume or Cancel) is ACCEPTED_RISK, recorded by the design engineer under D-203. Pause and Continue are live-proved.

## Why
The code and evidence look sound, and I would not block it. Merge policy puts contract-change and product-decision on the always-human list, and the risk is high, so AUTO_MERGE is not available. Cancel is hard to undo and reconcile follows an uncertain send. Under D-207 the main coordinator merges high-risk work after the design engineer's recorded "Accept and merge" (D-203).

## Acceptance criteria
1. Controls shown only when listed, with no empty row: met. The mock e2e and unit tests pass (QA/UI/UX PASS).
2. Reconcile sends one body `{action, expected_revision}`: met. Unit and e2e request capture.
3. State shown after a 202 re-read, with no outcome panel or proof upload: met in the mock.
4. Re-read failure message: met. Unit test.
5. Resume sends the expected body: met in the mock. Not live-proved (accepted risk).
6. Cancel dialog, with the request only on confirm: met in the mock. Not live-proved (accepted risk).
7. Background pause and continue bodies: met, and live-proved at 202.
8. `adopt_profile` and `release_invoice` never drawn or sent: met. Unit test.
9. Double-click, lock and poll safety: met. Fake-timer tests.
10. Null revision holds the write: met.
11. 409 stale_version reload with no repeat: met.
12. 403 and csrf handling: met.
13. 422 message shown: met.
14. 429 and 503 send nothing further: met.
15. Uncertain lock after a 5xx or dropped connection on Resume, Cancel and background: met. Unit and e2e.
16. Reconcile stays enabled after an uncertain failure: met.
17. 404 and 401 handling: met.
18. No write on load, poll or navigation: met.
19. v7 path unchanged: met per QA and the CI checks.
20. Unit tests for the command table: met.
21. Live Django check for Check what happened and for a person with no controls: partly met. Live proof exists for Pause/Continue only. The gap is ACCEPTED_RISK under D-203.
22. Viewport check at 1440 and 390: met per UI/UX PASS.
23. Lint, typecheck, test and drift test: met. `premerge-checks-f296a554.log` shows ci PASS.

## For the human
The design engineer's "Accept and merge" (D-203) is already on record, so I need no new decision. Under D-207 the main coordinator performs the merge of PR #113 (MERGEABLE, GitHub checks SUCCESS) after a final sync check. Look at `delivery/features/F-87/round-3/acceptance-pmo.md` for the accepted-risk scope. It covers Check what happened and Resume as live-unproven, and it needs a new decision if a later feature carries the same gap.
