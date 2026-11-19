RECOMMENDATION: ESCALATE
COMMIT: ee9dc46dca9ff40d39148cc4ba1f76572bb35aa7
APPROVER: approver

## Summary
- F-48 adds the Assistant "can't" state (SCR-05): `cant` pose by status, phone inline pose card, restricted source shown as lock only, restricted step label hidden. Frontend only, contract mock only, nothing released.
- Gate, technical, UX, UI and QA all PASS on this head; blockers TECH-1-1 to 1-3 verified closed. Diff is 9 files under frontend/assistant, within the policy's 15-file cap, no always-human path or surface.
- Risk is low, so policy would allow AUTO_MERGE, but the phone board scores 88.2 (tool floor 90) and 41 exceptions are still "builder proposal, pending design engineer".
- PMO acceptance is CHANGES: `operation_ids` empty, and the backend handoff lacks the restricted-reference note. Product acceptance is not required.

## Why
The code is sound and I would merge it, but the design gate is EXCEPTION status with unsigned waiver and exceptions, which are the design engineer's calls, and the PMO record fixes are not done. No product or money decision is involved.

## Acceptance criteria
1. Desktop board 1440: met, coverage 100 with exceptions, visual 91.8, tool PASS.
2. Phone board 390: met against the spec floor of 70 (88.2, coverage 100); the tool default 90 fails, so a waiver is needed.
3. Exceptions limited and explained: met as proposals (41 entries, all with Conflicts numbers, none covers data the API supplies); unsigned.
4. Pose by status: met, unit tests (59 passed in assistant.test.tsx).
5. Thread content, reason as text, no new controls, restricted source: met; QA saw no leak at 1440, 390 or after reload; zero writes.
6. Phone pose card, wrong user, unknown id, read failure: met, component tests and QA.
7. Accessibility, reduced motion: met, e2e 27 passed (axe, no sideways scroll, 44px).
8. Tokens, contract not extended, F-24 not weakened: met, no change under src/api, apps, architecture, design; checks.sh exit 0 on this head.
9. No overclaim, build.md evidence: met.

## For the human
Design engineer, please sign in `fidelity-exceptions.json`:
1. A D-83 waiver for SCR-05-mobile-cant at 390, visual 88.2 (tool default 90, spec floor 70). Add it to `visual_waivers`; desktop-cant 91.8 passes without one.
2. The 41 exceptions marked "builder proposal, pending design engineer" (the two phone buttons per G-SCR05-5, the restricted-source label shown as lock only, one-paragraph wording, and the avatar, step card, red reason line, Restricted chip, bell, composer, @ Mention and spacing differences).
Product acceptance is not required.

Before merge, the coordinator should: set `operation_ids` to E-CONVERSATION and E-CONVERSATIONS (PMO-2-1); add the restricted step-reference note to delivery/backend-handoff/gaps-a-project-setup.md (PMO-2-2). Then the PMO pass can go to PASS.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-48/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-48/round-2/fidelity/scores.txt
- /Users/Hunchoo/psl-factory/delivery/features/F-48/round-2/acceptance-pmo.md
