RECOMMENDATION: ESCALATE
COMMIT: 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b
APPROVER: approver

## Summary
- F-32 adds the project Delivery tab (SCR-43) and the release gates item in its waiting, decision and ready states (SCR-44). It covers 8 boards and runs on the contract mock only. There is no new endpoint, no write from the work page, and nothing is released.
- Gate PASS (round 2, attempt 1). Technical, security, UX, UI, QA and PMO acceptance all PASS on this head. Every blocking round-1 finding (UI-1-1 to UI-1-9) is verified. QA ran 874 vitest and 238 e2e tests on a production build, with 0 failures.
- Fidelity is below 90 on all 8 boards (76.7 to 84.9). Coverage with exceptions is 100. All 8 D-83 waivers and all 51 entries in fidelity-exceptions.json are still "builder proposal, pending design engineer".
- Readiness sets risk to medium, requires product acceptance, and lists the auth, contract-change and product-decision surfaces. The diff changes 34 files (the policy cap is 15) and adds a section to delivery/BACKEND-HANDOFF.md.
- Three PSL product questions are still open (PMO-2-2): is the gate a "Planning decision" or a "Release decision", who holds release authority, and whether Reject applies.

## Why
Spec criterion 1 passes only with D-83 waivers signed for each board. None is signed, and signing them is the design engineer's call. Merge policy also keeps this away from auto-merge: the risk is medium, the surfaces include auth, contract-change and product-decision, and the change has more than 15 files. The code itself looks sound and stays inside scope.

## Acceptance criteria
1. Scores (coverageWithExceptions 100, visual of at least 90, or a signed D-83 waiver from 70 up): not met until the waivers are signed. Coverage is 100 on every board. Visual is 77.5, 78.1, 84.9, 77.3, 76.7, 80.9, 77.5 and 82.1 (round-2/fidelity/scores.txt).
2. Exceptions are limited and mapped to Conflicts numbers: proposed in full. Each entry still needs approved_by from the design engineer.
3. Criteria 3 to 8 (tab everywhere, rows from data, nothing counted in the browser, Tola card and Next, sub-nav, Empty and Unknown): met. Evidence is QA journey 1 plus the component tests in delivery-overview.test.tsx.
4. Criteria 9 to 16 (three states from data, decision controls only from you_can_act, no write from the work page, ready only through the response, return needs a note, INV-AGENT, Unknown not zero, links only from data): met. Evidence is QA journeys 2 onward, release-gates.test.tsx and the delivery-release e2e. I spot-checked criterion 10 myself: the diff adds no `/me` read, `fetch` or POST under features/workspace or DeliveryTab.tsx.
5. Criteria 17 to 21 (access, phone, accessibility, tokens only, mock matches the contract): met. Evidence is the QA and security reviews. I also grepped the diff under frontend/src and found no raw colour literals.
6. Diff scope: met. The changes touch the frontend projects and workspace features, mock fixtures and proposals, tests, e2e and delivery/BACKEND-HANDOFF.md. Nothing is under architecture, migrations or the policy files.

## For the human
I need two decisions from the design engineer:
1. Sign or refuse the 8 D-83 visual waivers: SCR-43 desktop and mobile, and SCR-44 default, decision and ready at 1440 and 390. Scores run from 76.7 to 84.9. The gaps left are the shared frame (amber gates note, plain facts values, grey readiness tags, side-by-side buttons at 390) and the approved Conflicts.
2. Sign or refuse each of the 51 entries in fidelity-exceptions.json.

Also confirm that you accept the product for part 1 (PRODUCT-ACCEPTANCE: required), knowing the three PSL questions in PMO-2-2 are still open. That covers the gate's name, who holds release authority, and whether Reject applies. The fixtures show "PMO Lead" as the decider, but that is mock wording, not a granted authority.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-32/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-32/round-2/fidelity/scores.txt
- /Users/Hunchoo/psl-factory/delivery/features/F-32/round-2/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-32/round-2/acceptance-pmo.md
