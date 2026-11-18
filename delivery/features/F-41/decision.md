RECOMMENDATION: ESCALATE
COMMIT: 2e9e42e3313d5a5318aa01fc8b585c2d47c5bcb4
APPROVER: approver

## Summary
- F-41 (FE-PAYMENTS) adds the read-only Payments and follow-up list (SCR-20) and the Payment reminder work item W-3801 (SCR-32) on 4 boards. It runs on the contract mock only: no email goes out, no money record is written, and recording a payment stays held (D-RECEIPT-ALLOCATION, D14 UNCONFIGURED).
- Gate PASS (round 2, attempt 1). Technical, security, UX, UI and QA all PASS on this head, and every round-2 fix (UI-2-1, UI-2-2, UX-2-1, UX-2-3) is verified. QA ran 307 e2e tests and 822 targeted vitest tests on a production build with 0 failures. checks.sh passed 2552 tests on its second run; the first run hit one unrelated flaky start-work test. When I finished, round-2/acceptance-pmo.md did not exist yet, so PMO acceptance is not on record for this head.
- Fidelity is below 90 on all 4 boards: SCR-20 desktop 84.5, SCR-20 phone 71.1, SCR-32 desktop 76.7, SCR-32 phone 79.2. Coverage with exceptions is 100. All 4 D-83 waivers and all 39 entries in fidelity-exceptions.json still say "builder proposal, pending design engineer". The 17 spec Conflicts are provisional under D-115.
- Readiness sets risk to high, requires product acceptance, and lists the contract-change, external-messaging, product-decision and security surfaces. The diff changes 58 files (the policy cap is 15) and adds contract proposals (`overdue`, `totals_detail`, `agent_note`, `attachment`, `steps[].submit_label`, step-keyed mock nexts).
- QA proved the no-resend rule on the mock only. A reload during a hung send turns Send back on unless the backend has already marked the item uncertain. So the guarantee against a second send to the client has to come from the backend (BACKEND-HANDOFF priority 1). The frontend cannot give it.

## Why
Merge policy rules out auto-merge on several counts: the risk is high, the surfaces include external-messaging, contract-change and product-decision, and the change has 58 files. Criterion 23 (fidelity) is met only once the design engineer signs the D-83 waivers and the exceptions, and none is signed. The code looks sound and stays inside scope. The open questions are design and product decisions, plus one rule the backend has to enforce.

## Acceptance criteria
1. Criteria 1 to 11 (rows from data, exact decimal amounts, Unknown never 0, nothing computed, "+ Unknown" only as returned, overdue from the backend, invoices, receipts and allocations kept separate, server-side search and paging, Chidi's note, sample label, empty and error): met. Evidence is QA's list journeys at 1440 and 390 and payments.test.tsx. I spot-checked criterion 4 myself: the lines the diff adds under frontend/src/features/finance/payments contain no `parseFloat`, `.reduce(`, `compactAmount` or `Date.now`.
2. Criteria 12 to 14 (the draft from data, Unknown facts, agent work is not a send): met. Evidence is QA's W-3801 and W-3810 journeys and payment-reminder.test.tsx.
3. Criteria 15 to 19 (one send per press, no resend after an uncertain send, edit makes a new version, stale, not now): met on the mock. Evidence is QA's request logs and the workspace log. Not proved: the backend refusing a second send, its idempotency, and draft versioning. There is no browser timeout, so the 60 s case is TECH-1-2's recorded deviation.
4. Criteria 20 to 22 (controls only from the response, 401/403/404, phone at 44px with no sideways scroll): met. Evidence is QA, security review, and the 151.6x44 note link.
5. Criterion 23 (fidelity): not met until the waivers are signed. Coverage is 100 on every board, but visual is 84.5, 71.1, 76.7 and 79.2, and every waiver and exception is still a builder proposal.
6. Criteria 24 to 26 (axe, tokens only, mock matches the contract): met. Evidence is the QA axe run, the UI review and payments-mock/mock-contract tests.
7. Criterion 27 (contract not extended): met. I checked the diff names myself: nothing under frontend/src/api, shell, components, work-item or decide; nothing under apps, architecture, design or migrations; no lock files.
8. Criteria 28 and 29 (existing tests green, build.md evidence): met. Evidence is checks.md (GATE: PASS) and round-2/build.md.

## For the human
I need three decisions from the design engineer:
1. Sign or refuse the 4 D-83 visual waivers: SCR-20 desktop 84.5, SCR-20 phone 71.1, SCR-32 desktop 76.7 and SCR-32 phone 79.2. The UI reviewer waived SCR-20 phone only on the condition that you confirm Conflicts 12 (the full strip, the PAID card and the full note on the phone). Option B would recover most of that score.
2. Sign or refuse the 39 entries in fidelity-exceptions.json. The provisional D-115 answers to spec Conflicts 1 to 11 also need your confirmation, especially these:
   - 1: Record a payment is not drawn.
   - 6: no "7 days" follow-up line.
   - 7: Edit makes Draft v2.
   - 10: the page opens with no filter.
   - 11: the sent and set-aside states.
3. Confirm whether you accept the product (PRODUCT-ACCEPTANCE: required) on these terms:
   - On a reload during a hung send, only the backend can stop the reminder going to the client twice. QA could not prove that on the mock.
   - Recording a payment, short payments, the reminder interval and who may send all stay held.

Also check round-2/acceptance-pmo.md once PMO has written it.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-41/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-41/round-2/fidelity/scores.txt
- /Users/Hunchoo/psl-factory/delivery/features/F-41/round-2/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-41/round-2/review-qa.md
- /Users/Hunchoo/psl-factory/delivery/features/F-41/spec.md (sections "What is sent" and "Conflicts with the boards")
