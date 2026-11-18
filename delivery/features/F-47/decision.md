RECOMMENDATION: ESCALATE
COMMIT: 8d7da0c400b19e41356a0230e1328978452bc763
APPROVER: approver

## Summary
- F-47 adds proof upload to four Start work drawers (minutes, change, income schedule and ledger source) and covers 8 SCR-04 boards. It runs on the contract mock only. The file is uploaded first and its evidence id goes with the start. Nothing is released and no backend or OpenAPI change is made.
- Gate PASS (round 2, attempt 1). Technical, security, UX, UI and QA all PASS on this head. Every round-1 finding (TECH-1-1 to TECH-1-4, UX-1-1, UI-1-2) is verified. QA ran 124 browser checks, 77 of 77 e2e tests and 603 of 603 targeted vitest, with axe clean in 22 states. PMO acceptance (round-2/acceptance-pmo.md) did not exist when I wrote this.
- Fidelity: with-exceptions coverage is 100 on all 8 boards. Visual is at least 90 on the two Finance desktop boards. The other 6 (75.3 to 89.3) depend on D-83 waivers. All 6 waivers and all 30 exceptions in fidelity-exceptions.json still read "builder proposal, pending design engineer".
- Readiness sets risk to high, lists the security and contract-change surfaces and requires product acceptance. The diff changes 24 files (the policy cap is 15) and adds a section to delivery/BACKEND-HANDOFF.md. The spec conflicts are provisional under D-114.
- One spec assumption is a business rule: proof is required on schedules and ledger sources and optional on minutes and changes.

## Why
Criterion 17 is met only once the design engineer signs the D-83 waivers and exceptions, and none of them is signed. Merge policy also keeps this away from auto-merge: the risk is high, the security and contract-change surfaces are listed, product acceptance is required and more than 15 files changed. The code itself looks sound and stays inside its lanes.

## Acceptance criteria
1. Criteria 1 to 8 (drawers drawn from data, project first, Uploaded only after the backend confirms, revision chaining, one start per press that lands on the work item, Start held while proof is unsure, remove, project change clears proof): met. Evidence is QA's journeys at 1440 and 390, start-work-proof.test.tsx (36 tests) and the e2e request logs. For criterion 1 I ran the fixture-id grep (SCH-INC, QB-JE, MR-0044, income_detail_oct, weekly-sync-notes) on frontend/src myself. It returns nothing.
2. Criteria 9 to 15 (upload errors, uncertain upload, start 409 and uncertain start, wrong record, 401/403/404, plain text and no client limits, Unknown is never 0 and nothing read from /me): met. Evidence is QA's error journeys, the security review and start-work-proof-mock.test.ts (18 tests). I also spot-checked criteria 14 and 15 on the frontend/src diff. It adds no `accept=`, no size or type limit and no `useMe` or `/api/v1/me` read.
3. Criterion 16 (phone, 44 px controls): met. Evidence is the e2e at 390 and the QA journeys.
4. Criterion 17 (fidelity): not met until the waivers are signed. Coverage with exceptions is 100 everywhere. Visual is 89.3, 86.3, 95.8, 96.1, 78.6, 81, 75.3 and 84.9 (round-1/fidelity/scores.txt; the layout did not change in round 2, and UI-1-2 confirms the scores). The 6 D-83 waivers and 30 exceptions are unsigned.
5. Criteria 18 to 20 (accessibility, tokens only, mock matches the contract): met. Evidence is axe at both widths, my grep (no hex, rgb or hsl in the diff) and the mock-contract tests.
6. Criteria 21 to 23 (contract not extended, existing tests green, build.md evidence): met. The diff touches no file under src/api, components, shell, architecture, design, openapi or a protected path. src/features/response changes only by the one useEvidenceUpload.ts guard. checks.sh passes, and the BACKEND-HANDOFF.md edit is recorded (TECH-1-4).

## For the human
I need these decisions from the design engineer:
1. Sign or refuse the 6 D-83 visual waivers: minutes and change at 1440 (89.3, 86.3), and minutes, change, schedules and ledger at 390 (78.6, 81, 75.3, 84.9).
2. Sign or refuse each of the 30 entries in fidelity-exceptions.json, and confirm the provisional spec conflicts (D-114).
3. Accept the product (PRODUCT-ACCEPTANCE: required). That includes the spec's rule that proof is required on income schedules and ledger sources but optional on minutes and changes. It also includes the mock's choice of one Finance case per line (C-FIN-SCHEDULES, C-FIN-LEDGER), which stays open for the backend (gaps-e question 3).

Also read round-2/acceptance-pmo.md when it lands.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-47/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-47/round-1/fidelity/scores.txt
- /Users/Hunchoo/psl-factory/delivery/features/F-47/spec.md (Assumptions, Conflicts)
- /Users/Hunchoo/psl-factory/delivery/features/F-47/round-2/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-47/round-2/review-qa.md
