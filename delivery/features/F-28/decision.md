RECOMMENDATION: ESCALATE
COMMIT: cc694876c715f0c927f3879491eb9ede706c4f31
APPROVER: approver

## Summary
- F-28 adds the 4 end-state boards of the minutes line (internal filed, published with per-person receipts) on the contract mock only. Nothing is sent or filed.
- Gate PASS on attempt 2. Technical, security, UX, UI, QA and PMO acceptance all PASS on this head. Round-1 blockers UI-1-1, UI-1-2 and UI-1-3 are verified. No blocking finding is open.
- Fidelity is below the 90 bar on 3 of 4 boards: desktop-internal 76.9, mobile-internal 89.0, desktop-published 81.5. Mobile-published passes at 92.1. Coverage is 100 after exceptions.
- The 3 D-83 visual waivers and every entry in fidelity-exceptions.json are still "builder proposal, pending design engineer".
- Readiness lists contract-change and external-messaging surfaces, and the diff adds a section to delivery/BACKEND-HANDOFF.md.

## Why
The readiness rule says the UI review passes only on fidelity of at least 90 after approved exceptions. Three boards miss that and the exceptions are not yet approved. Signing them is the design engineer's call, not mine. The code itself looks sound and stays inside scope.

## Acceptance criteria
1. Fidelity of the 4 boards, every element present after approved exceptions: not met until the exceptions are signed. Coverage is 100 with proposed exceptions.
2. Fidelity score of at least 90: met on mobile-published (92.1). Not met on the other three (76.9, 89.0, 81.5), which need waivers above the D-83 floor of 70.
3. Criteria 4 to 19 (per-person receipts, OWNER NEEDED, Unknown values, reconcile-only after uncertain send, links shown only when data supplies them, no new endpoints): met. QA ran 44 e2e and 404 component and mock tests on this head, and PMO accepted.
4. Criterion 22 (no overclaim of send, filing or duplicate-send protection): met. build.md and QA state that this is mock only.
5. Diff scope: met. Changes are only under frontend workspace, mock fixtures, tests, e2e and delivery/BACKEND-HANDOFF.md. Nothing under src/api, architecture, design or the shell.

## For the human
Decision needed from the design engineer: sign or refuse the 3 D-83 visual waivers (SCR-28-desktop-internal 76.9, SCR-28-mobile-internal 89.0, SCR-28-desktop-published 81.5) and the entries in fidelity-exceptions.json. These are the layout differences forced by D-111: the "Sent to" section, the 4-column actions table, the phone showing desktop wording, "Open actions" in the links row, the returned sentence in a white panel, Next in the side column, and the frame tab bar without counts.

Also keep the factory file fix for UI-1-3 with the merge record. PMO flagged it as uncommitted in the main folder.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-28/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-28/round-2/fidelity/scores.txt
- /Users/Hunchoo/psl-factory/delivery/features/F-28/round-2/review-ui.md
