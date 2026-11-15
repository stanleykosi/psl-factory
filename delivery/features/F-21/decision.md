RECOMMENDATION: ESCALATE
COMMIT: a3b587107fba754884bfd399d9a4dc25d32c7ab1
APPROVER: approver

## Summary
- F-21 builds the weekly client report line on the contract mock: PM writes four cited parts, Tola assembles, PMO Lead approves or returns. The work is 8 boards (default, invalid, assembling, review at desktop and phone). Returned and received are left to F-21b.
- Round 3 UX, UI, security, integrated QA and PMO acceptance all PASS on this head. Technical review PASS names 31f0d25e, not this head.
- The head is the merge of dlv-00-delivery-setup into F-21 (a3b58710). Since the technical review, the diff is mostly the F-19 Clients merge. QA's synced run (1556 tests) covers that merge, but the technical review does not.
- The change surfaces include contract-change (the proposed v7 D-LINE-WORKSPACE block) and external-messaging ("Approve and send" to a client). Both are on the merge policy's always-human list.
- Nothing is sent for real. The send and idempotency exist only on the mock, and the backend does not yet enforce the resend refusal, idempotency or cite scoping (BACKEND-HANDOFF.md priority 1).

## Why
The merge policy requires a human for contract-change and external-messaging, and the merge-decision script would lower AUTO_MERGE anyway. The design engineer already gave that decision on 15 Nov ("Merge", D-87 in delivery/OVERNIGHT-DECISIONS.md). So this needs only the human's go-ahead to be applied, not a new review. I found nothing in the diff outside Scope. Files outside the frontend and delivery areas that the policy protects (.github, architecture, migrations, lockfiles, env) are not touched.

## Acceptance criteria
1. Desktop and phone fidelity of the 8 boards, score 90 or more (spec criteria 1-5): met. The UI review passes this head, and the exceptions were approved in D-85. I did not rerun the fidelity tool.
2. Default and form states: the saved parts and cites come from data, with no generate control (spec 6-9): met. The component and mock tests cover the exact write request, with nothing judged client-side. QA PASS.
3. The 422 per part, send to assembling, and the quiet assembling state (spec 10-12): met per the UX and QA reviews on this head.
4. Review state, Approve with one send and no automatic retry, and Return needing a note (spec 13-15): met per the QA and PMO acceptance reviews. I read the spec's tests but did not rerun them myself.
5. Stays inside scope: met. No returned or received pages, no backend or `architecture/**` changes, and the contract gaps are recorded in build.md as proposals.

## For the human
Decision: confirm the merge of PR #39 (F-21) into dlv-00-delivery-setup. D-87 already records your "Merge" on 15 Nov, so this is the formal go-ahead the policy requires. It rests on these points:
- The change is mock-only and nothing is sent to a client.
- The proposed D-LINE-WORKSPACE contract may still change in the backend.
- The technical review covers 31f0d25e. The later merge commit a3b58710 is covered by QA's synced run, not by a technical re-review.

Files to look at:
- delivery/features/F-21/round-3/review-technical.md
- delivery/features/F-21/round-3/review-qa.md
- delivery/features/F-21/round-3/build.md
- frontend/src/features/workspace/**
- frontend/mock/fixtures/**, W-2201 to W-2204
