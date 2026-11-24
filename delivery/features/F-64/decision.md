RECOMMENDATION: ESCALATE
COMMIT: 7108be9d709378a1d14333db432515028e087aa0
APPROVER: approver

## Summary
- F-64 connects the SCR-03 Decision desk (default, done, not-yours and stale boards) to live API 1.22.0. It is frontend only, 41 files, and mostly under frontend/src/features/decide, with some F-113 delivery-tab files that came in through the main merge.
- The gate, technical, UI, UX and QA reviews and PMO acceptance all name 7108be9d. Product acceptance is carried over under D-188, from D-182 and D-202.
- The change writes business decisions (approve, return and reject) through a changed contract: required evidence, no revoke, and reshaped task reads.
- The live decision paths have not been run against real data. Approve, return, the evidence picker on a real task, a live not-yours read and a live stale 409 are proved on the mock only (PMO-2-1). The coordinator's psl_demo run is still pending.
- Readiness marks the surfaces contract-change and product-decision, and the risk as medium. Both surfaces are on the merge policy's always-human list. The change also touches 41 files against a limit of 15.

## Why
The rules for this push (D-180, D-184, D-188) cover routine merges. This change records approvals on a contract the mock has never been checked against, and the one proof that would close that gap has not run. I would not merge it without that run, so the merge script would lower an AUTO_MERGE anyway.

## Acceptance criteria
1. Live task, its evidence and what is asked are readable on SCR-03: met on the mock (e2e 8 of 8, vitest). Live evidence covers only the negative cases (signed-out, 404, non-numeric id, not-open, 401).
2. Approve, return and reject are recorded through the live API with an evidence pick and a note: met on the mock only. Not proved live.
3. Stale revision conflicts reload with the note kept: met on the mock only.
4. Not-yours read-only board with comment: met on the mock only.
5. No revoke, no invented approvers or authority, and the unsupported design parts hidden: met. QA's grep of the decide feature for revoke and for direct api calls returned nothing. I did not run the code myself.

## For the human
Decide whether to merge now and treat the coordinator's psl_demo run as a follow-up, or to hold the merge until that run proves live approve, return, evidence pick and the stale 409. My recommendation is to hold until the run. Files to look at: delivery/features/F-64/round-2/acceptance-pmo.md (PMO-2-1), delivery/features/F-64/round-2/review-qa.md, and frontend/src/features/decide/useLiveDecision.ts.
