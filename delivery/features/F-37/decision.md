RECOMMENDATION: ESCALATE
COMMIT: 36db1217cc448105529fc82e2e2ec5087be13606
APPROVER: approver

## Summary
- F-37 builds the RFP requirements page (SCR-26) inside the RFP frame on the contract mock: the PM accepts, accepts selected, edits and accepts, or writes their own answer to each of Tola's suggestions, and adds a requirement. Record team input links to the shared drawer.
- Gate, technical, UI, QA and PMO acceptance PASS on this head (UX carried forward with impact notes); all seven earlier blocking findings are closed.
- Risk is medium with the `contract-change` surface, above the policy's low-only auto-merge level. The change is 24 files, all under frontend/, with no change to the generated API types, apps, architecture or design.
- Open items are the design engineer's: eight unsigned visual waivers, 48 unsigned exceptions, the earlier layout-rework decision, and product acceptance.
- Pre-merge: add an F-37 section to BACKEND-HANDOFF.md, set `operation_ids`, and merge the current base for F-38's shared RfpFrame tab links.

## Why
The work is sound and evidenced, but the merge policy allows AUTO_MERGE for low risk only, and the page's flows and wording are new to the client. Fidelity sits at 70.5 to 74.7 under D-83 waivers that a person must sign.

## Acceptance criteria
1. Frame from `rfp`, tabs, 390 header (AC 1): met; component tests and QA at 1440 and 390.
2. Rows, progress and Tola from data (AC 2): met; no board string in src.
3. Unknown never 0, no price (AC 3): met; tests on modified copies, QA saw no amount.
4. Send for review only as returned (AC 4): met; disabled with the backend's reason.
5. Record links to the team-input form (AC 5): met; link and drawer verified. Completing the record cannot run on the mock (QA-3-1, 501 not_mocked), which is out of scope for part 1.
6. Add a requirement (AC 6): met; QA ran real 409 and 422 paths.
7. Accept one, accept selected, edit and accept, write my own (AC 7 to 10): met; QA log shows one POST per action with the right `item_ids` and step.
8. Failures never say accepted (AC 11): met; 409 by cookie and real revision, 500 by route injection (frontend only; the mock cannot script a 500 for E-WORK-STEP, QA-3-2).
9. Uncertain step (AC 12): met; one `accept`, every step off after reload.
10. Agent text only displayed, 401/403/404, nothing from `/me` (AC 13 to 15): met; persona none, pm, finance_lead and ceo checked.
11. Phone (AC 16): met; no sideways scroll, 44px targets.
12. Fidelity (AC 17): not met until the waivers and exceptions are signed. Coverage 100 after exceptions on all 8 boards; fidelity was not re-run in round 3.
13. Accessibility, tokens, mock matches contract, contract not extended, existing tests green (AC 18 to 22): met; checks.sh rc=0 on this head.

## For the human
Please sign:
1. The 8 D-83 visual waivers (70.5 to 74.7: SCR-26 desktop 74.7, mobile 70.7, desktop-review 70.5, desktop-edit 70.7, desktop-reject 71.2, mobile-review 73.4, mobile-edit 73.4, mobile-reject 72.0), in fidelity-exceptions.json `visual_waivers`. None reaches 80.
2. The 48 exceptions (all "builder proposal, pending design engineer"). Confirm that none hides a data-supplied value (the Your answer and Status labels in particular), and note the 3 Harmattan exceptions were removed in round 3 without a fidelity re-score.
3. The earlier coordinator decision to rework the layout before review (round 1: Progress, Before review and Tola's note moved to the right column, the team-input task panel hidden on desktop, the title at 32px). It raised visual from 67.9 to 75.7 up to 70.5 to 76.8 and was never at the 90 bar.
4. Product acceptance (required by readiness): the accept, edit and write-own flows and their wording, "Suggested by Tola", the past-answer line including "that bid was won", which comes from mock data and must come from a real record, and that the PM's accept is recorded under their name.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-37/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-37/round-1/build.md (layout pass, Fidelity)
- /Users/Hunchoo/psl-factory/delivery/features/F-37/round-3/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-37/round-3/acceptance-pmo.md

Before the PR, the coordinator should set `operation_ids` (PMO-3-1), add the F-37 section to BACKEND-HANDOFF.md (PMO-3-2), and merge the current base for F-38's RfpFrame tab links.
