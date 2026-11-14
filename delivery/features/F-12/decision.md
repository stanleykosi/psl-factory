RECOMMENDATION: ESCALATE
COMMIT: 831b17164ca8b1200e9ff84d2d486ea0d7dc7dc5
APPROVER: approver

## Summary
- F-12 (FE-ALERTS) adds `/notifications` and `/settings/alerts` on the contract mock. All 33 changed paths are inside the spec lanes, and no `src/shell`, `src/api`, `package.json` or `architecture` files changed.
- Gate, technical, UX, UI, security, QA and PMO all PASS on this head. They show no blocking findings and three open non-blocking ones.
- The change is built on v7 proposal fields that are still `proposed`. They count only under the design engineer's recorded exception.
- Product acceptance is provisional, from the coordinator's overnight instruction and not the design engineer.
- The merge must wait for F-13 (PR #13, held for the design engineer). F-12 must then be rebased onto it with the local overlay and types removed.

## Why
The code looks sound, but the feature's declared surfaces include `security` and `contract-change`, both on the merge policy's always-human list. The proposal contract, the phone settings layout and the product acceptance all need the design engineer. `scripts/merge-decision.py` does not exist in this repo, so I could not run it. I applied the policy by hand, and it gives the same answer.

## Acceptance criteria
1. Overlay is verbatim v7 and the base contract is not drifted: met. Checks and the technical review cover it, and `src/api` is untouched.
2. Own records only, and CSRF on both writes: met on the mock only. QA confirmed 404 on another person's id and 403 on a wrong or missing token. Not proved on a real API.
3. List and settings match the boards at 1440 and 390: met. Fidelity scores are 97.8, 96.4, 92.9 and 95.8, with 100% coverage after exceptions D-24.
4. Open an alert marks it read and goes to its work: met. UX and QA checked it, and the security review checked the link encoding.
5. Save sends the exact body and gets a new revision, 409/422/401/failure handling: met. QA ran 24 journeys against the mock and unit tests assert the body.
6. Absent proposal fields are never invented: met. The `bare` scenario and unit tests cover it.
7. Accessibility: met. axe found 0 violations in 19 states.
8. Suite and build: met. Gate PASS with 414 unit tests.
9. Merge preconditions: not met yet. F-13 has not merged and F-12 has not been rebased.
Spot-check: I confirmed the head SHA and the 33-file diffstat against the lanes, and the round-1 files all name this head.

## For the human
Decide three things.
1. Do you accept the v7 proposal fields (D-NOTIFY-MODEL r3, D-ALERT-PREFS-VIEW r1) as the contract for this feature? Confirm the security and contract-change surfaces for the mock-only masking, CSRF and own-record behaviour.
2. Do you accept the phone settings layout (PMO-0-5), the phone back link beside the heading (D-24, E-4), and QA-1-1 as a follow-up (D-27)?
3. Merge only after F-13 (PR #13) has merged and F-12 has been rebased with the overlay removed.

Files to look at:
- `delivery/OVERNIGHT-DECISIONS.md` (D-24, D-27, D-29)
- `delivery/features/F-12/round-1/acceptance-product.md`
- `frontend/src/features/alerts/contract-proposal.ts`
- `frontend/mock/proposals/alerts.json`
- `frontend/src/features/alerts/AlertSettingsPage.tsx`
