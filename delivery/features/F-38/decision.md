RECOMMENDATION: ESCALATE
COMMIT: 4b70abcdc0d7a345e6f66a90324b6f92411878c3
APPROVER: approver

## Summary
- F-38 draws the RFP submission item (SCR-40, W-3501..W-3509) from the contract mock: the PM sends Tola's pack for review, the document reviewer approves, returns or rejects that exact version, and Submitted and the receipt show only after the re-read.
- Gate, technical, UI, UX, security, QA and PMO acceptance all PASS on this head. Earlier blockers (stale approved text, uncertain states, submitted status kind, pinned bar) are closed.
- Risk is high (external messaging, security, contract-change, product-decision surfaces). The merge policy allows AUTO_MERGE for low risk only. Nothing is really sent: no provider, portal adapter or costing exists.
- Open items are the design engineer's: 8 visual waivers, 25 exceptions and product acceptance.
- Pre-merge: the branch is behind dlv-00 and touches shared files, so sync and re-run checks.sh.

## Why
The work is sound and evidenced, but this is the step that would release a priced proposal to a client, and four product questions about it are unanswered. Waivers, exceptions and product acceptance are a person's decisions.

## Acceptance criteria
1. Fidelity and exceptions (AC 1, 2): not met until signed. Coverage is 100 after exceptions on all 8 boards. Visual is 76.7 to 89, below 90 everywhere. Only the phone draft was re-measured in round 3.
2. Draft, tab link, nothing computed, Unknown never 0, no amounts (AC 3 to 6): met. Component tests, mock tests and QA at 1440 and 390 on W-3501 and W-3509.
3. Agent work is not a decision, controls only from the response (AC 7, 8): met. Security review and tests on W-3501, W-3509 and the submitted items.
4. Send for review, edit cover letter, approve, return and reject, 409 (AC 9 to 13): met. One POST with CSRF, revision and UUID key; QA saw one decision, Submitted only after the re-read, and W-3506 shows v2 with no second decision.
5. Uncertain paths and receipts only as returned (AC 14, 15): met. W-3505 shows "delivery not confirmed" with no resend; reconcile "It didn't arrive" works. The "It arrived" path was not run by QA.
6. Record the outcome, open the full pack, access, nothing on load (AC 16 to 19): met. I spot-checked the TECH-2-1 fix in round 3: the four submitted fixtures keep kind submitted, with a test that fails on the old ones.
7. Phone, accessibility, tokens (AC 20 to 22): met. Phone pinned bar measured live by UI round 3.
8. Mock matches the contract, contract not extended (AC 23, 24): met. One mock-only change outside the lane (frontend/mock/documents.mjs, 4 lines), declared in the handoff.
9. Existing tests green, no overclaim (AC 25, 26): met. checks.sh PASS on this head (3249 vitest passed; 126 rfp e2e passed).

## For the human
Please sign, in /Users/Hunchoo/psl-factory/delivery/features/F-38/fidelity-exceptions.json:
1. The 8 visual waivers (desktop draft 89, review 76.7, submitted 84.7, portal 79.5; phone draft 78.4, review 79.3, submitted 83.6, portal 81.3). You accepted them under D-131; please confirm.
2. The 25 exceptions (all "builder proposal, pending design engineer"), including the shared-frame items you accepted in D-131: tab bar roles and names and the Submission chip fill (UI-1-4), h2 title under the frame's h1 (UI-1-5), colour and style differences (UI-1-6, UI-1-7), and the top bar with no PMO Lead persona (UI-1-9). Also the facts strip and stepper (UX-1-4), and the "invoiced twice" wording on the shared reconcile panel (UX-1-3).
3. Product acceptance (required):
   - may a pack with a TEST TEMPLATE part be approved and sent (G-40-6);
   - the "submit by" lead time (G-40-5);
   - what Return and Reject do to the RFP (G-40-7, D-RETURN);
   - is the person who may submit (rfp.submit) different from the document reviewer.
   The board's "all 4 approvals" is stale against D-APPROVAL-ORDER (three steps); the page shows the backend's text.

Before the PR, the coordinator should set operation_ids to E-WORK-ITEM, E-WORK-STEP, E-TASK-CLAIM, E-TASK-DECIDE, E-WORK-ACTION, E-DOCUMENT (PMO-3-1), sync with dlv-00 and re-run checks.sh (PMO-3-3).

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-38/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-38/round-3/build.md
- /Users/Hunchoo/psl-factory/delivery/features/F-38/round-3/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-38/round-3/review-qa.md
- /Users/Hunchoo/psl-factory/delivery/features/F-38/round-3/acceptance-pmo.md
