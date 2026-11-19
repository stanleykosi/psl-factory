RECOMMENDATION: ESCALATE
COMMIT: 4dba97ab6ee7dd7c97f33f51a63d28750636cb58
APPROVER: approver

## Summary
- F-45 draws a ledger source (LED-0052) in four states from the contract mock: investigation, observer records what they found with proof, an independent reviewer approves or rejects, and verified only after the re-read.
- Gate, technical, security, UX, UI, QA and PMO acceptance all PASS on this head, with no blocking finding.
- Risk is high (Finance approval write, append-only proof upload, contract-change, product-decision surfaces), above the policy's low-only auto-merge level.
- Open items are the design engineer's: unsigned waivers and exceptions, a ledger-only behaviour that differs from F-33, and product acceptance.
- Pre-merge: resolve Workspace.tsx against F-35/F-39 as described in TECH-1-1.

## Why
The work is sound and evidenced, but the merge policy allows AUTO_MERGE for low risk only, and this is an authority-bearing Finance flow the client has not yet seen working. Visual waivers, exceptions and a behaviour difference from F-33 are decisions a person must make.

## Acceptance criteria
1. Four states from data (AC 1): met, component tests and QA at 1440 and 390; no board string in src.
2. No amount, unknown never 0, sample-marked (AC 2 to 4): met, tests on every fixture; QA saw no amount on any page.
3. Reviewer-not-set and Unknown holds, controls only from you_can_act (AC 5 to 8, 16): met; zero POSTs on every read-only fixture.
4. Verified only after the re-read (AC 9): met on the ledger line, and differs from F-33's income line (see below).
5. Observation with proof, upload failures, reject needs a note (AC 10 to 15): met; QA exercised them in a real browser.
6. Backend refusals, uncertain decide and observation (AC 17 to 19): met; the W-4213 500 re-reads first and shows no early success. No Try again is offered, which the spec allows.
7. Access, phone, accessibility, tokens, mock matches contract (AC 20, 21, 23 to 25): met.
8. Fidelity (AC 22): not met until the waivers and exceptions are signed. Coverage is 100 after exceptions on all 8 boards.
9. Contract not extended (AC 26): met, with one accepted deviation (`start-work.mjs`, 2 lines, authorised by spec.md:223).
10. Existing tests green, evidence (AC 27, 28): met; checks.sh passed on this head.

## For the human
Please sign:
1. The 7 D-83 visual waivers (76.4 to 91; desktop investigating at 91 passes without one), in fidelity-exceptions.json `visual_waivers`.
2. The 27 exceptions (all "builder proposal, pending design engineer"), including the desktop-verified side-note exception: keep the re-check sentence in the main column, or Option B, where the backend sends it as `workspace.next` (the UI review prefers Option B). Also the missing exception line for the two extra mobile-verified facts (UI-4).
3. The ledger-only "approved after re-read" behaviour: on the ledger page the notice reads "result not confirmed" until the re-read moves on, while F-33's income line still says "<label> is approved". Accept the difference, or ask for F-33 to match.
4. Product acceptance (required): the three ledger policy values that are NOT SET, three-person separation, what Unknown or More than one does, and the verdict set (approve and reject only).

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-45/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-45/round-1/build.md (Fidelity, Pending)
- /Users/Hunchoo/psl-factory/delivery/features/F-45/round-1/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-45/round-1/acceptance-pmo.md

Before the PR, the coordinator should set `operation_ids` to E-WORK-ITEM, E-WORK-STEP, E-EVIDENCE-UPLOAD, E-TASK-CLAIM, E-TASK-DECIDE (PMO-1-1) and resolve the merge with F-35/F-39 per TECH-1-1.
