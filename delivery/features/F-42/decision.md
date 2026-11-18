RECOMMENDATION: ESCALATE
COMMIT: 8779c5f30c05ed760fc1cbfe3a2dddf790daca1e
APPROVER: approver

## Summary
- F-42 is part 1 of the fixed asset schedule (SCR-55, 8 boards). Chidi checks the October register. A PPE reviewer approves the register changes and then the explained in-service dates, in place. After that the item goes to calculation, or it is held when Calculation rules (F07) are not set. It runs on the contract mock only: there is no new endpoint, no figure is computed and nothing is released.
- Gate PASS (round 2, attempt 2). Technical, security, UI, UX and QA all PASS on this head, and every blocking round-1 finding (UI-1-1, UX-1-1, UX-1-2, TECH-1-1) is verified. QA ran a production build against the mock at 1440 and 390, with axe clean. PMO acceptance (round-2/acceptance-pmo.md) had not been written when I finished.
- Fidelity is below 90 on all 8 boards (74.6 to 89.1). Coverage with exceptions is 100. All 8 D-83 waivers and all 24 exceptions in fidelity-exceptions.json are still "builder proposal, pending design engineer".
- Readiness sets risk to high, requires product acceptance, and lists the security, contract-change and product-decision surfaces. The diff changes 31 files (the policy cap is 15) and adds a section to delivery/BACKEND-HANDOFF.md.
- Product questions are still open. One is who explains the 3 unclear dates and attaches the proof (G-55-1, no board, not built). Others are the wording of the "Depreciation starts from these dates." basis, which depends on F07 (NOT SET), and the return and reject wording (D-RETURN, open).

## Why
Criterion 18 passes only once the design engineer signs the D-83 waivers for each board. None is signed yet. Merge policy also keeps this away from auto-merge: the risk is high, the surfaces include security, contract-change and product-decision, product acceptance is required, and the diff has more than 15 files. The code looks sound and stays in its lanes: frontend workspace and work-item features, fixtures, tests, e2e and the backend handoff.

## Acceptance criteria
1. Four states from data: met. QA journey 1 checked this at both widths. I ran the criterion's grep myself on frontend/src at 8779c5f3, and none of the board strings appears there.
2. Costs as returned: met. QA confirmed the costs digit for digit at both widths, and asset-schedule.test.tsx covers them.
3. The page computes nothing: met. Technical review found no arithmetic in the diff.
4. Unknown is never 0: met. The W-3910 component test checks it, and `receipt_recorded` stays `unknown` in every fixture.
5. Sample-marked: met. The component test checks it. QA notes that the tag is off in the production build by design (NEXT_PUBLIC_SHOW_SAMPLE_LABEL).
6. Each unset key is a hold with no controls (W-3907, W-3908, W-3909): met. Evidence is QA plus the UX-1-1 test, so the holds also draw no exceptions button.
7. Decide controls only from `you_can_act` and the steps: met. Evidence is QA claim counts and the security review.
8. Agent work is not a decision: met. Evidence is QA journey 1 (W-3901 sends no claim or decision).
9. Approved and calculating only from the response: met. Evidence is QA journey 2 re-reads.
10. Approve: met. W-3902 and W-3903 each send one claim and one decision, with CSRF and `expected_revision: 1`. A double press sends one decision.
11. Return and reject need a note: met. Evidence is QA and the component tests.
12. No write when the person cannot act: met. QA counted zero claims on W-3901, W-3904 to W-3909 and W-3912.
13. Backend refusals and 14. uncertain decide: met. QA forced 401, 403, 409, 422, 5xx and network failures through the mock.
15. Access, 16. phone, 19. accessibility: met. Evidence is the QA and security reviews, with axe returning [] at 1440 and 390.
17. Other lines unchanged: met. The income-schedule tests pass, and W-2706 keeps its exceptions button.
18. Fidelity: not met until the waivers are signed. Visual scores are 84.1, 75.0, 74.9, 74.6, 82.4, 84.4, 87.1 and 89.1 (round-2/fidelity/scores.txt). All 8 are above the 70 floor.
20. Tokens and components only: met. I grepped the CSS in the diff and found no hex, rgb( or hsl( literal.
21. Mock matches the contract and 22. contract not extended: met. Evidence is asset-schedule-mock.test.ts and mock-contract.test.ts. No change touches src/api, migrations, architecture or policy files.
23. Existing tests green: met. checks.sh passed. Reviewers ran the vitest files one at a time and all passed. Only a combined run under heavy machine load timed out.
24. build.md evidence: met.

## For the human
I need two decisions from the design engineer:
1. Sign or refuse the 8 D-83 visual waivers for SCR-55: investigating, register review, date review and calculating, each at 1440 and 390. Scores run from 74.6 to 89.1. The gaps left are the shared frame, the AgentCard head, the full tables shown in place of the phone summaries, the Proof section, and the StationTrack tone, including Calculate shown as amber "Waiting" (UI-1-2, UI-1-3).
2. Sign or refuse each of the 24 entries in fidelity-exceptions.json.

Also confirm that you accept the product for part 1 (PRODUCT-ACCEPTANCE: required), knowing these questions are still open:
- G-55-1: who explains the 3 unclear dates and attaches the proof. The step is not built. After "Approve register" the item only waits.
- The basis "Approve the explained dates. Depreciation starts from these dates." is sample wording, and F07 is NOT SET.
- Return and reject show only the re-read (D-RETURN is open).

"PPE reviewer" is sample fixture wording, not a granted authority.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-42/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-42/round-2/fidelity/scores.txt
- /Users/Hunchoo/psl-factory/delivery/features/F-42/round-2/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-42/spec.md (Conflicts 2, 3, 6 and 7)
- /Users/Hunchoo/psl-factory/delivery/features/F-42/round-2/acceptance-pmo.md (when PMO finishes)
