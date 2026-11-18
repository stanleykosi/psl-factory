RECOMMENDATION: ESCALATE
COMMIT: 9b73aacf87069a93f583f69053dacf3151e3ae68
APPROVER: approver

## Summary
- F-31 is part 1 of engagement planning (SCR-41 default and register, SCR-42 default and record, 8 boards). A won RFP becomes a registered engagement, the PMO Lead confirms the PM, and the PM records what a department sent under their own name. It runs on the contract mock only and sends nothing real.
- On this head: gate PASS (round 3, attempt 1). Technical, UX, UI, QA and PMO acceptance all PASS. QA-2-1, the only blocking finding left from round 2, is verified. QA-3-1 (the PM wording on `uncertain_written`) and the PMO-3-x notes are non-blocking.
- Fidelity is below 90 on all 8 boards. Visual runs from 72.2 to 85.5 and coverage with exceptions is 100 (round-2/fidelity/scores.txt; round 3 made no layout change). All 45 entries in fidelity-exceptions.json, including the per-board D-83 waivers, still read "builder proposal, pending design engineer".
- Under merge policy this cannot auto-merge. Readiness sets risk to medium, lists the contract-change and product-decision surfaces, and requires product acceptance. The diff changes 29 files (the cap is 15) and adds contract proposals to delivery/BACKEND-HANDOFF.md.
- There is one disclosed scope deviation. `frontend/src/features/response/useResponse.ts` adds an optional `forbidden` flag to the `problem` notice, but spec criterion 20 says nothing under `src/features/response/**` changes. The change is additive and F-18's tests are unchanged and green (PMO-3-1).

## Why
Criterion 16 passes only once the design engineer signs the D-83 waivers and the 45 exceptions, and nothing is signed yet. Product acceptance is required, and spec Conflicts items 1 to 6 are product and design choices only a person can confirm: the sample sits on Ojo Foods, the PM form is pre-filled, and "Who receives this?" is shown disabled. Policy also blocks auto-merge on risk, surfaces and file count. The code itself looks sound, stays in the frontend lane and the mock, and is well tested.

## Acceptance criteria
1. Criteria 1 and 2 (packet from data; money and Unknown): met. Evidence is QA round-2 journeys, re-run on this head (round-3 J10), and engagement-planning.test.tsx.
2. Criteria 3 to 5 (Confirm PM pre-filled only from the response; register; no blind repeat on an uncertain result): met. Evidence is QA J5, the round-2 journeys and the e2e engagement-planning spec (63/63 on this head). QA-3-1 is a wording gap only. Nothing claims "confirmed" and nothing is resent.
3. Criteria 6 to 12 (departments from data, controls only from the response, record drawer, recorded under the PM's name, failures never say recorded, agent text only displayed, reached from the project): met. Evidence is QA J8 and J9 for QA-2-5 and the round-2 journeys.
4. Criteria 13 and 14 (401/403/404; nothing from `/me`): met. I spot-checked criterion 14 myself: the added lines under frontend/src contain no `useMe` or `/api/v1/me`.
5. Criterion 15 (phone): met, apart from a non-blocking gap. The 44px Remove button is verified (QA-2-1). The record Drawer has no Cancel on a phone, though Close and Escape work (TECH-2-1, UX-2-1). Either the spec is amended or the design engineer confirms.
6. Criterion 16 (fidelity): not met until the waivers and exceptions are signed. Visual scores are 81.9, 74.3, 79.2, 79.5, 80.1, 85.5, 77.7 and 72.2, all above the floor of 70.
7. Criteria 17 to 19 (axe, tokens only, mock matches the contract): met. Evidence is QA axe runs at 1440 and 390 and engagement-planning-mock.test.ts. I grepped the added lines under frontend/src and found no hex, rgb or hsl colour literals.
8. Criterion 20 (contract not extended): met except for the one additive field in `features/response/useResponse.ts` (PMO-3-1). Nothing is under `src/api`, `apps`, `architecture`, `design`, `src/shell`, migrations or lock files.
9. Criterion 21 (existing tests kept green): met. checks.sh passes. The two `mock-contract.test.ts` edits only admit the new W-26xx fixtures and strip the F-31 overlay keys before the schema check. The technical review found they do not loosen any existing check.

## For the human
I need three things from the design engineer:
1. Sign or refuse the 45 entries in fidelity-exceptions.json, including the 8 per-board D-83 visual waivers (72.2 to 85.5).
2. Confirm spec Conflicts items 1 to 6 as built. These cover the sample on Ojo Foods and Sola Martins, Confirm PM drawn open and pre-filled from `default_person_id`, the register form opening on press, record input in a Drawer, "Who receives this?" disabled with "Not available yet", and the PSL designer notes left out. Also choose the tag tone in UI-1-10.
3. Accept the product for part 1 (PRODUCT-ACCEPTANCE: required). Say whether you accept the additive `useResponse.ts` change against criterion 20, and the phone Drawer having no Cancel button.

These PSL questions are still open and belong to part 2 and the backend: G-41-2, G-42-3, G-42-5 and G-42-6.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-31/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-31/round-2/fidelity/scores.txt
- /Users/Hunchoo/psl-factory/delivery/features/F-31/spec.md (Conflicts 1 to 15, criteria 16 and 20)
- /Users/Hunchoo/psl-factory/delivery/features/F-31/round-3/acceptance-pmo.md
- /Users/Hunchoo/psl-factory/delivery/features/F-31/round-3/review-qa.md
