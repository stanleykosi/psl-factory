STATUS: READY
COMMIT: 8a9755d4f598464231786ff2100fd420a93b31a4
BUILDER: builder
LANE: full

## Summary
- `poseFor` returns `cant` for `cannot_answer`; the side panel shows `/agents/<agent>-cant.png` with "<Name> can't do that with your access."
- The phone thread shows an inline pose card (agent tint, alt "<Name>, can't do this") only for `cannot_answer`.
- `text` and `cannot_reason` stay separate plain lines (D-116). The two phone buttons are not drawn (G-SCR05-5).
- Contract mock only; nothing released; no real agent answered; the refusal text is the mock's sample; no access request exists.
- The mobile board is below the tool's default visual 90 (87.8) but above the spec's floor of 70. Everything below marked "builder proposal" is pending the design engineer.

## Changes
- frontend/src/features/assistant/SidePanel.tsx: `Pose` gains `cant`; `poseFor` maps it.
- frontend/src/features/assistant/Thread.tsx: the phone-only pose card above the first agent message when status is `cannot_answer`.
- frontend/src/features/assistant/assistant.css: `.as__pose--inline` (tokens only).
- frontend/public/agents/{tola,chidi,zainab}-cant.png: copied from design/mascots/revised-poses and web-sized with `sips -Z 380` (1024x1536 to 253x380, the idle poses' height). Not drawn or edited.
- frontend/tests/assistant.test.tsx: 3 tests (side-panel pose and no phone card at 1440; phone card on CV-2404 only, none on CV-2401/2403; poseFor map). frontend/e2e/assistant.spec.ts: CV-2404 added to the axe/scroll/44px matrix, plus a 1440/390 test with reduced motion, zero writes and axe.
- delivery/features/F-48/fidelity-exceptions.json: F-24's carried over plus builder proposals (pending design engineer) for the two phone buttons (Conflicts 6, G-SCR05-5), "Payroll" (5), the one-paragraph wording (3), the restricted-source label (spec criterion 10) and the conversation-list pattern match.

## Acceptance criteria
1. [x] Desktop board at 1440: coverage 100 with exceptions, visual 90.8, tool PASS.
2. [x] Phone board at 390: coverage 100 with exceptions, visual 87.8, above the spec floor of 70. The tool reports FAIL only on its default 90; a D-83 waiver is the design engineer's.
3. [x] Exceptions each have role, name, category, reason, approved_by and a Conflicts number; none covers data the API supplies. The restricted-label and list-pattern entries have no Conflicts number (builder proposals, pending design engineer).
4-6, 9-11: [x] vitest tests/assistant.test.tsx, 55 passed. The side panel is `/agents/zainab-cant.png`; the phone card appears only for 2404.
7, 8, 12, 13: [x] covered by F-24's existing thread, markup-as-text, wrong-user and error tests, which stay green. I added no CV-2404 wrong-user or cannot_reason-markup case.
14, 15: [x] e2e: axe, no sideways scroll and a still image at 390 for CV-2404; the 44px check is F-24's matrix, which now includes CV-2404.
16: [x] CSS has no colour literals.
17: [x] no change under src/api, apps, architecture, design, mock/assistant.mjs or src/shell.
18: [x] checks.sh exit 0; 27 of 27 e2e passed.
19, 20: [x] this file.
- G-SCR05-5 proposal: a typed `suggestions[]` on the message; who receives an access request is an unproposed business decision.

## Validation
- `bash delivery/checks.sh` under the shared lock: EXIT 0 (lint, typecheck, unit tests, production build).
- `E2E_PORT=4774 MOCK_PORT=4775 playwright test e2e/assistant.spec.ts`: 27 passed. test-results deleted.
- Fidelity: production build with API_ORIGIN=127.0.0.1:4772, app on 4773, shared tool unmodified, output in round-1/fidelity/ (scores.txt). Desktop 1440: coverage 78.1 (100 with exceptions), visual 90.8, PASS. Phone 390: coverage 28.6 (100 with exceptions), visual 87.8, tool FAIL on its default 90 only.
- My servers on 4772/4773 stopped by PID.

## Coordinator note (19 Nov)
Merged dlv-00 into the branch (2900167babb52fd0ae639672099c398e287ad1a5) to pick up the flaky-test fix (PR #65) and the merged features; there were no conflicts. The first gate failed on a 10 s hook timeout from the old base.
- Merged dlv-00 again (8a9755d4f598464231786ff2100fd420a93b31a4) to pick up the flaky-test fix (#75); base_sha moved to a9bfa180bbb86754f4d9739419127e596b94b8b2.
