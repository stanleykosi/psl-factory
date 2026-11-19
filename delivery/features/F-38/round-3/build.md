STATUS: READY
COMMIT: 48da4d86526113ca1b12b051907896059068af66
BUILDER: builder
LANE: full

## Summary
- TECH-2-1: the four submitted fixtures have `rfp.status.kind: "submitted"` again (spec table, F-18 tone rule). The amber SUBMITTED tag is dropped: it was only possible by changing the kind, and F-18's frame draws `submitted` neutral. The tag colour is a remaining visual difference for the design engineer (in the waivers). The "review pending" wording (UX-1-1) was fixed in round 2 by fixture timeline and next_step data, not by the kind, so it is unaffected (test at tests/rfp-submission.test.tsx still passes).
- UI-1-8: at 390 the draft already draws Send for review and Edit cover letter in the pinned bottom bar (the Next panel is position: fixed, bottom 0, same pattern as other lines). The round-2 full-page capture only made it look in-flow. No code change; a phone e2e now asserts it.
- Shared History link size left as is (shared header).

## Changes
- frontend/mock/fixtures/work/W-3502.approve.json, W-3503.json, W-3504.json, response/W-3505.delivered.json: status kind back to `submitted`.
- frontend/tests/rfp-submission.test.tsx: new test that all four fixtures keep kind submitted and a SUBMITTED label (fails on the old fixtures, checked).
- frontend/e2e/rfp-submission.spec.ts: phone-only test that the draft's bar is fixed and ends at the viewport bottom at scroll 0 and at the end (passes before and after: no code defect found).

## Fixes
- TECH-2-1 | fixtures' rfp.status.kind restored to submitted; new test | 48da4d86526113ca1b12b051907896059068af66
- UI-1-8 | verified already pinned at 390 (fixed bar holds both buttons); phone e2e added; no code change | 48da4d86526113ca1b12b051907896059068af66

## Acceptance criteria
1. [x] AC 1 to 20 unchanged from round 2: vitest 3249 passed, rfp e2e 126 passed.

## Validation
- delivery/checks.sh under the lock: first run failed one start-work.test.tsx test (10 s timeout under load, unrelated); second run exit 0, 3249 passed.
- e2e E2E_PORT=4951 MOCK_PORT=4952 npx playwright test e2e/rfp-submission.spec.ts e2e/rfp.spec.ts e2e/response.spec.ts e2e/workspace.spec.ts: 126 passed.
- Fidelity (one run, phone draft only, production build, round-3/fidelity/scores.txt): SCR-40-mobile-draft-390 coverage 85.7, with exceptions 100, visual 78.4 (unchanged; existing unsigned waiver stands). Other boards not re-run.
- Remaining differences on that board: consequence sentence above the buttons (board draws the button only), Edit cover letter is not drawn on the board, agent card below.
- Demo rebuilt and left running: app 4985, mock 4984 (API_ORIGIN 127.0.0.1:4984).
- UI-2-1 (unsigned waivers) is for the design engineer.
