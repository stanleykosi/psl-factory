RECOMMENDATION: AUTO_MERGE
COMMIT: 57d38e53b8c184ef7d1aec452a1649d714c4b2de
APPROVER: approver

## Summary
- F-22 adds the returned and received outcomes of the weekly report page (SCR-25, 4 boards) on the F-21 frame. It is frontend and mock fixtures W-2209..W-2214 only.
- Round 4 QA, security, technical, UI and UX reviews and PMO acceptance are all PASS. The reviews name a0be1442; the only later commits touch `delivery/` files, with no non-delivery diff (checked).
- No change in `frontend/src/api`, `apps`, `architecture`, `design`, `mock/workspace.mjs` or `mock/start-work.mjs`. The contract is not extended.
- Nothing is really sent. There is no resend control; uncertain and unknown recipients are never shown as delivered.
- Design decisions D-97 (conflicts) and D-99 (differences and waivers) are signed by the design engineer.
- Expect the merge-decision script to lower this: readiness lists the surfaces `contract-change` and `external-messaging`, and the diff has 18 non-delivery files against a 15-file cap. That is a policy limit, not a defect.

## Why
Every acceptance criterion has passing evidence, and the change stays inside the frontend lane and the readiness scope. I found no open product, pricing or copy decision. The "Time unknown" wording was the one open item, and D-97 and D-99 settled it. The external-messaging surface is the mock only, with no send path.

## Acceptance criteria
1. Four boards: met. Waivers were signed in D-99 and the round 4 UI review passes.
2. Exceptions limited and mapped: met. The UI review and D-99 cover them.
3. One fidelity run per round: met per build.md and the round folders.
4. Returned page from data: met. Component tests and QA pass.
5. Edit reuses the F-21 write path: met. The component test with a recording fetch and the e2e pass.
6. No edit without a step: met per the QA review.
7. Absent is not invented: met per the component test on a modified copy of W-2209.
8. Received with all confirmed: met. No button and no POST.
9. Nothing claimed without confirmation: met. W-2212, W-2213 and W-2214 have text assertions.
10. Reaching `received` is not proof: met per the W-2212 and W-2213 tests.
11. No resend while uncertain: met. Only ReconcilePanel is offered, mock only.
12. Unknown id and access: met per the component tests.
13. Recipients and time rules: met per the QA review.
14. Other boards unchanged: met. Existing tests pass in `checks.md`.
15. Accessibility and layout: met via `e2e/weekly-returned-received.spec.ts`.
16. Tokens only: met per the technical and UI reviews.
17. Weekly mock test updated, not weakened: met per the technical review.
18. Contract not extended: met. I checked the diff stat of the forbidden paths myself and it is empty.
19. No real send, no overclaim: met per build.md and the security review.
20. Existing behaviour not weakened: met. The round 4 checks pass.
21. build.md evidence: met.
