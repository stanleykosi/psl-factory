RECOMMENDATION: ESCALATE
COMMIT: 4f53c9f15d69264d048e8ea482fb80475d936481
APPROVER: approver

## Summary
- F-36 adds the "Assign accountable PM" panel (SCR-24, 2 boards). It opens over the My work Unassigned queue and runs on the contract mock only. It reuses F-30's AssignForm and useWorkspaceAssign and F-09's ProofField. G-24-1, G-24-2 and G-24-3 are mock overlays recorded for the backend in delivery/BACKEND-HANDOFF.md. SCR-23 is held as part 2 until F-47 merges.
- Gate PASS (round 3, attempt 1). Technical, security, UX, UI and QA all PASS on this head. QA-2-1, QA-2-3 and UX-1-1 are verified fixed. The builder reports 2540 vitest tests and 24 e2e tests passing. QA-2-2 is non-blocking and sits in the shared ValidationSummary, outside this lane.
- PMO acceptance had not been written when I finished (round-3/acceptance-pmo.md is missing).
- Fidelity: desktop 1440 is 94.1 visual, which passes. Phone 390 is 75.6 visual and depends on a D-83 waiver. Coverage is 100 on both boards once exceptions are counted. The waiver and all 18 entries in fidelity-exceptions.json are still marked "builder proposal, pending design engineer".
- Readiness sets risk to medium with the auth and contract-change surfaces and requires product acceptance. The diff changes 35 files against a policy cap of 15.

## Why
Criterion 15 (fidelity) is met only once the design engineer signs the phone waiver and the 18 exceptions, and none of them is signed yet. Merge policy keeps this from auto-merging on several counts: the risk is medium, auth and contract-change are always-human surfaces, product acceptance is required, and there are more than 15 changed files. The code is sound and stays inside readiness's scope.

## Acceptance criteria
1. Criteria 1 to 5 (opens over My work; candidates only from the response; no `assign`, no control; acting role from the response only; what happens next): met. Evidence is rfp-assign.test.tsx, the e2e spec, and the QA rounds 2 and 3. I spot-checked criterion 4 myself. In AssignPmDrawer.tsx:113-143, `roles` comes only from `assignRoles(shownAssign)` (the item response), and `acting_role` is sent only when the overlay returns roles. Nothing in features/rfp, my-work or workspace reads `useMe` or `/me`.
2. Criteria 6 to 11 (typed assign, no success before the re-read, overlay assign with proof, validation, stale, uncertain): met. Evidence is the component and mock tests and QA journeys. Criterion 9 now holds for all four named fields after round 3 (QA-2-1 verified on the real mock at 1440 and 390).
3. Criteria 12 and 13 (access 401, 403 and 404; Unknown, never 0): met. Evidence is the security and QA reviews and the component tests.
4. Criterion 14 (phone targets of at least 44px, including the chip's ×): met. Evidence is the e2e bounding-box checks reported by QA.
5. Criterion 15 (fidelity): not met until the design engineer signs. Desktop is 94.1. Phone is 75.6 under a pending D-83 waiver. All 18 exceptions are pending `approved_by`.
6. Criteria 16 and 17 (accessibility; tokens and components only): met. Axe is clean in e2e. A grep of the added CSS lines found no hex, rgb or hsl colours. The only px values appear in comments.
7. Criteria 18 and 19 (mock matches the contract; contract not extended): met. Nothing changed under frontend/src/api, apps, architecture, design, shell or start-work, or on any protected path (gate: "Protected paths: none changed"). The overlays are listed as proposals in delivery/BACKEND-HANDOFF.md.
8. Criterion 20 (existing behaviour green): met. The full checks.sh run passed, and the reviewers report that F-30 and F-31 assign behaviour is unchanged.

## For the human
I need three things from the design engineer:
1. Sign or refuse the D-83 visual waiver for SCR-24 mobile at 390 (visual 75.6, floor 70). The phone sheet shows the desktop's full content in one column (Conflicts 7), where the board draws only PM, role, note and a short next line.
2. Sign or refuse each of the 18 entries in fidelity-exceptions.json. These cover frame items, sample data, and the My work list behind the panel.
3. Give product acceptance (PRODUCT-ACCEPTANCE: required). This covers the new assign flow and its wording: "Assign accountable PM", "n people can prepare RFPs here", "<reference> is now with <name>.", the fixed "What happens next" sentence, and the board intro "Who may assign is set by PSL in Setup."

Also confirm you accept that "PMO Lead" and "CEO" as acting roles are mock overlay data (G-24-1), not granted authority. The backend still has to confirm G-24-1, G-24-2 and G-24-3.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-36/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-36/round-2/fidelity/SCR-24-mobile-390/report.html
- /Users/Hunchoo/psl-factory/delivery/features/F-36/round-3/review-qa.md
- /Users/Hunchoo/psl-factory/delivery/features/F-36/spec.md (Assumptions)
- /Users/Hunchoo/psl-factory/delivery/features/F-36/round-3/acceptance-pmo.md (once PMO has written it)
