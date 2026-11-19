VERDICT: PASS
COMMIT: cfd8a916060e08c73e7217af956fe4d3b98f41a1
REVIEWER: pmo-acceptance
AUTHORITY: delivery PMO acceptance

## Summary
- Delivery acceptance only. F-47 (FE-M2A-PROOF part 1 of 3) is in scope and complete on this head: the Proof box is live in the Start work drawer for minutes, change, income schedules and ledger sources, 8 boards, contract mock only. Client/product acceptance, merge and release keep their own authorities. Nothing is released.
- Evidence: gate PASS (checks.sh, no protected paths changed); technical, security, UX, UI and integrated QA all PASS on this head. Build ran 102 files / 2322 tests passed and e2e 77/77. QA re-ran the same suite (77/77 e2e, 603/603 targeted vitest, one load flake that passed on rerun) and drove the real production build at 1440 and 390. All 23 criteria are covered in round-1/build.md and round-2/build.md (criteria 18 and 20 changed this round). Fidelity: 8 boards, 100.0 with exceptions. Two boards pass on raw visual (95.8, 96.1) and six rest on D-83 waivers (75.3 to 89.3).
- Task coverage: only FE-M2A-PROOF is in scope. The operation IDs are E-LINES, E-LINE-OPTIONS, E-EVIDENCE-UPLOAD and E-WORK-START, and feature.json lists `operation_ids: []`. The changed paths stay within the lane. The only files outside it are the three allowed edits (the `server.mjs` branch, `me.finance_lead.json`, the `useEvidenceUpload.ts` guard) and `delivery/BACKEND-HANDOFF.md`. TECH-1-4 asked for that last one to be recorded, and round-2/build.md now records it. No `src/api`, `components`, `shell`, `architecture`, `design` or `openapi` change.
- Backend handoff: the "Added during F-47" section exists (BACKEND-HANDOFF.md:250-264) and matches the spec. It covers write order, the Finance fixed cases C-FIN-SCHEDULES (3) and C-FIN-LEDGER (2), the proposed kinds `schedule_source` and `ledger_source`, upload limits as 422, one revision per case, evidence ownership on the start, 403/404 equality, `next` (G-SCR04P-9), who may start the Finance lines, and the mock-only cookie `psl_mock_start_work` and ids. Backend items still open and not yet answered: gaps-e question 3, the case and revision source, and QA-2-1 (413/415 should be 422 with a message).
- Parent status stops at this slice. This is part 1 of 3, and D-START-INTAKE r1 is still `proposed`, so the work is not real-backend verified. FE-M2A-PROOF stays open at package level until F-47B and F-47C land.
- Not proved on this head: the real backend and its upload limits; F-31's record-input and upload tests, because F-31 (c5d25156) is not an ancestor of the head. Merge must first sync the base, re-run `delivery/checks.sh` and the e2e (spec Lanes: integration owner, `server.mjs`, `useEvidenceUpload.ts`, `mock-contract.test.ts`) and rerun F-31's engagement-planning tests.
- Fidelity note: the fidelity run used a local driver copy (round-1/fidelity/_driver). The UI reviewer judged it faithful to F-05's driver. This is not a separate finding.

### Human items (design engineer / product)
1. Confirm or change the 14 spec conflicts taken PROVISIONALLY under D-114 (delivery/OVERNIGHT-DECISIONS.md), taken as recommended while the design engineer slept. The seven that need an answer are: (1) file box, F-09 card with no browser limits; (2) the "×" on an uploaded file; (3) empty and waiting states; (4) project change clears proof; (5) failed upload holds Start; (6) no `next` on the Finance lines; (7) Finance lines served only to the Finance persona (CEO and CTO keep the 8 lines, and the top-bar name differs from the board).
2. Sign the 30 exceptions in `fidelity-exceptions.json`. All read "builder proposal, pending design engineer" (UI-1-1).
3. Sign the 6 D-83 visual waivers: minutes desktop 89.3, change desktop 86.3, and the four phone boards at 78.6, 81, 75.3 and 84.9. All are above the 70 floor, so no floor exception is needed. The change desktop and schedules phone scores (86.3, 75.3) were drawn with fallback fonts and are somewhat pessimistic (UI-1-3).
4. Product acceptance (required in readiness): the two new Finance back-office drawers and proof upload at start. The client has not seen them.
5. Merge, on the design engineer's "merge" only, after the base sync above.

### Backlog (named, not part of this acceptance)
- **F-47B**: fixed assets and cash forecast drawers, 4 boards. Ready once F-47 merges.
- **F-47C**: management accounts and the `money` kind, 2 boards, plus `finance_import` lines. Waits for the backend developer to choose E-WORK-START or E-IMPORT and to add the missing fields (G-SCR04P-1, -3).
- **Held**: payroll and business-unit drawers, 4 boards. Blocked by D-PAYROLL-VISIBILITY (PSL), the PSL payroll hold, SCR-13 "Who may read inputs" and G-SCR04P-5 to -7.
- **Unblocked by F-47: FE-MILESTONE-COMPLETE** (SCR-19, the invoice line started with proof), once F-47 merges. **FE-FIN-ACCOUNTS-INTAKE** (SCR-53) still waits on F-47C. The workspaces these starts open (FE-FIN-SCHEDULES, FE-FIN-LEDGER) are separate tasks.

## Findings
- PMO-2-1 | non-blocking | low | pmo | Open non-blocking items to carry. They stay OPEN in feature.json and none is an acceptance gate. UX-1-2 (no reason line beside a held Start), UX-1-3 (desktop "×" is 24 px, and the spec asks for 44 px on phones only), UX-1-4 (file input named through the group; QA axe was clean at both widths, so this is likely closable), UI-1-1 (signatures, human item 2 and 3), UI-1-3 (fallback fonts on two boards), QA-2-1 (413/415 message lost; backend must confirm limits answer 422), QA-2-2 (403/404 on the start show the backend message; backend should keep record and file names out of it).
- PMO-2-2 | non-blocking | low | integration | F-31 is not on this head. Criterion 22 names F-31's engagement-planning tests "when on the base". They were not run here, so evidence for them is missing, not failing. Re-run them after the base sync before merge.

## Verified
- TECH-1-1, TECH-1-2, TECH-1-3, TECH-1-4, UX-1-1, UI-1-2 | verified | State VERIFIED in feature.json by their lens reviewers on this head. QA independently re-checked them in the browser or by test (review-qa.md Verified). UX-1-1 was the only blocking finding of round 1, and no blocking finding remains.
- Accepted risks: none claimed. The D-114 provisional acceptance of the spec conflicts is a named authority (design engineer, via the coordinator's bedtime instruction), and it is listed above for confirmation.

## Update for head cfd8a916 (diff 8d7da0c4..cfd8a916)

- None of F-47's files (start-work intake, ProofField, useEvidenceUpload, server.mjs, me.finance_lead.json) changed in 8d7da0c4..cfd8a916; the only F-47 file touched is tests/mock-contract.test.ts, which gained F-31, F-32 and F-33 proposal checks.
- Re-run on the worktree: start-work, response and mock-contract tests, 9 files, 571 passed. checks.sh passed (2552) and e2e passed (99) per build.md.
- F-31 response Drawer and F-33 lines are untouched by F-47 and their tests pass.

Verdict unchanged.
