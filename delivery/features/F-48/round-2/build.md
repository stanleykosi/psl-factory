STATUS: READY
COMMIT: d28b8b98fe3f84c959c01d24d5f7aff07497916c
BUILDER: builder
LANE: full

## Summary
- TECH-1-1 was real: CV-2404's checklist step drew "Read: ACCESS · payroll (restricted)". The step now shows no record when its words match a restricted source.
- Added the missing CV-2404 component tests (wrong user, unknown id, restricted label absent at 1440 and 390, cannot_reason as text).
- Phone pose card image raised from 120 to 164px to match the board's card height (about 177px).
- fidelity-exceptions.json: Conflicts numbers added, restricted-label text corrected, 8 honest exceptions added for the phone/desktop differences UI listed. The file is edited in the main repo and left uncommitted for the coordinator.
- Contract mock only; nothing released; no real agent answered; no access request exists.

## Changes
- frontend/src/features/assistant/model.ts: stepsOf drops a step reference whose words equal a restricted source_details label or reference.
- frontend/src/features/assistant/assistant.css: .as__pose--inline img height 164px.
- frontend/tests/assistant.test.tsx: new CV-2404 tests; the "separate lines" test now asserts the reason sits in its own .cmp-chat__cannot element.
- delivery/features/F-48/fidelity-exceptions.json (main repo, uncommitted).
- No shared-file changes.

## Fixes
- TECH-1-1 | restricted label no longer drawn in the CV-2404 step | d28b8b98fe3f84c959c01d24d5f7aff07497916c
- TECH-1-2 | CV-2404 wrong-user, unknown-id and cannot_reason markup tests | d28b8b98fe3f84c959c01d24d5f7aff07497916c
- TECH-1-3 | Conflicts numbers on every exception; restricted-label wording corrected | uncommitted edit in main repo (coordinator commits)
- TECH-1-4 | reason asserted in its own .cmp-chat__cannot element | d28b8b98fe3f84c959c01d24d5f7aff07497916c
- UI-1 | phone pose image 164px | d28b8b98fe3f84c959c01d24d5f7aff07497916c
- UI-2 | exceptions for avatar, step card, reason line, Restricted chip, bell, composer, @ Mention, pose spacing | uncommitted edit in main repo
- UI-3 | exceptions for the red reason line and chip styling | uncommitted edit in main repo

## Acceptance criteria
1. [x] Desktop board: coverage 100 with exceptions, visual 91.8, PASS (round-2/fidelity/scores.txt).
2. [x] Phone board: coverage 100 with exceptions, visual 88.2; tool FAIL on its default 90 only, above the spec floor of 70. Waiver proposed for the design engineer.
3. [x] Every exception has a Conflicts number; the new ones are builder proposals pending design engineer.
10. [x] Restricted label absent from body text at 1440 and 390 (new test).
12. [x] finance_lead on CV-2404 and an unknown id see "We could not find that conversation." (new tests).
8. [x] cannot_reason with markup renders literally, no element (new test).
Others unchanged from round 1.

## Validation
- vitest tests/assistant.test.tsx: 59 passed.
- `bash delivery/checks.sh` in the f-48 worktree under the lock: EXIT 0 (an earlier run launched by mistake in the main checkout failed 1 of 3035 and is not evidence).
- e2e/assistant.spec.ts: 27 passed (ports 4774/4775).
- One fidelity run, production build with API_ORIGIN=127.0.0.1:4772; servers stopped after.
- Not done: I did not run the new tests against the old code to show they fail.
- Demo rebuilt and running: app 4925, mock 4924. Pushed to origin/fe-assistant-cant-state; worktree clean except the untracked root node_modules.
