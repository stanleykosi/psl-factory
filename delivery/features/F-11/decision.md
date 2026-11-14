RECOMMENDATION: ESCALATE
COMMIT: 604e1b0a0f8fb3ac2cee49124f70370b1343e6de
APPROVER: approver

## Summary
- F-11 (Setup frame and Rules, PR #20) passed the gate, technical, UX, UI (all six SCR-13 boards 93.4 to 99.8), security, integrated QA and PMO acceptance on this exact head.
- Readiness rated it high risk, with surfaces security, auth, contract-change and product-decision. The merge policy only allows auto-merge at low risk, so a person must decide.
- The save form changes who holds authority (who may assign an RFP, who reviews client documents, Finance reviewers and publishers).
- Product acceptance is provisional, recorded by the coordinator overnight (D-36), not by the design engineer. Several exceptions (D-22, D-30, D-33) are also provisional.
- The contract proposal fields exist only in the mock, with no backend yet. PMO-3-1 is also open: the branch must merge dlv-00 (which carries PR #19, merged as e09827a) so its own diff drops the shell `note` change.

## Why
The code appears sound and well tested, but this is a change to authority-bearing rules. The human has already asked that high-risk features be built and reviewed but not merged without them. The accepted exceptions and the contract proposal are product and contract calls that only the design engineer can confirm.

## Acceptance criteria
1. Lead or Admin sees the Setup frame and the Rules, Finance and Delivery views: met, per round 3 UX, UI, QA and PMO on this head (17 e2e tests pass).
2. Role-list rule save with version, 409 reload-and-clear, 422 field mapping, and no edit controls for read-only users: met, per QA and the component tests. I did not re-run them.
3. Fidelity for the six boards at 390 and 1440: met, with approved exceptions (provisional).
4. Shell diff empty (spec AC 26): not met on this head, because of the phone-bar `note`. It is resolved only after merging dlv-00 per PMO-3-1, and that sync is not yet verified.
5. Product acceptance: provisional only.

## For the human
Decide whether to merge PR #20 after reading these. First, the Set a rule panel and its wording, since it edits who holds authority. Second, the provisional exceptions D-22, D-30 and D-33, and the page-level outcome callout. Third, the contract proposal for backend confirmation. Before merge, F-11 must merge dlv-00 and show no `src/shell/**` change in its diff.

Files to look at:
- delivery/features/F-11/round-3/acceptance-product.md
- delivery/features/F-11/round-3/acceptance-pmo.md
- delivery/OVERNIGHT-DECISIONS.md (D-22, D-30, D-33 to D-36)
- frontend/src/features/setup/**
- frontend/mock/proposals/setup.json
