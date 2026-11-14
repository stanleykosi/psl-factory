RECOMMENDATION: ESCALATE
COMMIT: 3c93fe030ff5ac81da343dc7a0917820c8803d7b
APPROVER: approver

## Summary
- F-04 adds the decision page: approve, return or reject one exact version, plus the stale, not-yours, own-work, already-decided and not-your-turn views. It runs on the contract mock only.
- The round-2 gate, all five reviews (technical, security, UX, UI, QA), PMO acceptance and the design engineer's product acceptance ("approved", 14 Nov 2026) all PASS and all name head 3c93fe0.
- Against the PR base (dlv-00-delivery-setup), the PR changes 30 files, all under frontend/. It does not touch architecture/, lockfiles, migrations or .github.
- I spot-checked it myself. `grep -rn "v2-reviewed" frontend` prints nothing, the architecture diff is empty, and `vitest run` on the drift, mock-contract and decide tests passed 99 of 99.
- I am escalating on the merge policy, not on quality. Readiness rated the risk high and listed the always-human surfaces security, payments and contract-change. The PR also changes 30 files, over the 15-file auto-merge cap.

## Why
I would be comfortable merging the change itself. Every criterion has evidence, the scope matches readiness, and the spec's Assumptions are UI and mock conventions, not pricing or policy. The policy still requires a person here. Auto-merge is allowed only for low risk, and this is the one-tap screen for approving invoices. It sends CSRF-bound writes that carry revisions, and it is the first code to use the backend's still-proposed decision fields (D-TASK-DECISION-VIEW). The design engineer's product acceptance covered how the page looks and behaves. It did not cover merging.

## Acceptance criteria
1. Contract is v4 everywhere: met. I re-ran the grep and found no matches, the architecture diff is empty, and the drift and mock-contract tests pass.
2. Default view (W-1201): met. Component tests and e2e at 390 and 1440 (review-qa.md, acceptance-pmo.md).
3. Unknown is never zero: met. The decide.test.tsx cases for W-1202 and the crafted unknown-with-amount case pass in my run.
4. Absent fields are omitted (W-1208): met. Component test passes in my run.
5. Claim on open with the right revision: met. Component test checks method, URL, body `{"expected_revision":2}` and the CSRF header, under StrictMode.
6. Approve: met. Component and mock tests, and the e2e done flow.
7. Note rules: met. Component tests, plus the mock rejects a missing or over-2000-character note with 422 (mock-decide.test.ts).
8. One write, no retry: met. Double-click test. Round-2 fix: the controls stay off when an uncertain decide cannot be checked.
9. Stale (A-STALE): met. The 409 reloads the item and shows the side-by-side view with no second write. Tested in component tests and e2e.
10. 409 on claim: met. Component test.
11. Cannot act, controls absent (W-1203 to W-1206): met. Component tests.
12. Cannot-act copy per reason: met. Copy for already_decided and not_your_turn was drafted and approved at product acceptance.
13. Eligibility not taken from /me: met. Component test with swapped personas.
14. Errors (401, 403, 404, 422, 5xx): met. Component tests (review-qa.md).
15. Mock claim and decide validation: met. mock-decide.test.ts.
16. Mock stale and done flows: met. Sidecar fixtures, /__mock/reset, and e2e.
17. Fixtures are valid and labelled: met. Strict Ajv over every W-12xx file, all `sample: true`.
18. Layout and accessibility: met. axe at 390x844 and 1440x900, no violations (round-2 checks.log, review-qa.md).
19. Gate: met. round-2/checks.md shows GATE: PASS at 3c93fe0.

## For the human
Decision needed: should PR #9 (https://github.com/stanleykosi/psl-factory/pull/9) be merged into dlv-00-delivery-setup as it stands? Merging accepts three things:
(a) The invoice decision screen is built on the backend's still-proposed decision fields (D-TASK-DECISION-VIEW and D-WORKITEM-DETAIL, under your 13 Nov exception), so it may need rework if the backend changes their shape.
(b) The non-blocking QA items QA-2-1, QA-2-2 and QA-2-3 stay open.
(c) The PR goes past the policy's limits: high risk, the security, payments and contract-change surfaces, and 30 files against a cap of 15.

Files to look at:
- frontend/src/features/decide/useDecision.ts: claim and decide, revision handling, and no-retry on an uncertain result
- frontend/src/features/decide/DecisionContent.tsx: amount display, including unknown
- frontend/src/features/decide/DecideStates.tsx: the cannot-act, stale and done views
- frontend/mock/server.mjs: claim and decide validation
- frontend/src/api/schema.d.ts: the v4 types
- delivery/features/F-04/round-2/review-qa.md: QA-2-1 to QA-2-3
