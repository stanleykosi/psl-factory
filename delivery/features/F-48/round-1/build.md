STATUS: BLOCKED
COMMIT: 0a7196f6eaf9b82b7193ea7139b2e0b72cb9aeb9
BUILDER: builder
LANE: full

## Summary
- Code done and committed and pushed: `poseFor` returns `cant` for `cannot_answer`; phone shows an inline pose card (alt "<Name>, can't do this") only for `cannot_answer`; `zainab/tola/chidi-cant.png` copied from design/mascots/revised-poses and web-sized with sips (1024x1536 to 253x380, same height as the idle poses; not drawn or edited).
- Not done: full checks.sh, production build, fidelity run (both boards) and e2e. The coordinator paused heavy work for the F-32/F-33 merges; before that, the shared lock and load never allowed a run.
- `fidelity-exceptions.json` written (F-24's carried over + 4 new, all "builder proposal, pending design engineer": the two phone buttons (Conflicts 6, G-SCR05-5), "Payroll" header (5), one-paragraph wording (3)).
- Contract mock only; nothing released; no real agent answered; no access request exists.

## Changes
- frontend/src/features/assistant/SidePanel.tsx: `Pose` gains `cant`, `poseFor` mapping.
- frontend/src/features/assistant/Thread.tsx: phone-only pose card above the first agent message when status is `cannot_answer`.
- frontend/src/features/assistant/assistant.css: `.as__pose--inline` (tokens only).
- frontend/public/agents/{tola,chidi,zainab}-cant.png: from design/mascots/revised-poses.
- frontend/tests/assistant.test.tsx (3 tests: side-panel pose, phone card on 2404 only, poseFor map), frontend/e2e/assistant.spec.ts (CV-2404 in axe matrix, plus a 1440/390 reduced-motion and zero-write test; not run).

## Acceptance criteria
4, 6, 7, 9 (component part), 10, 11 (component), 12 partly: [x] by vitest tests/assistant.test.tsx, 55 passed. 1, 2, 14, 15, 18 (full gate), 16 grep, 17: [ ] not run. 3: [x] file written.

## Validation
- `vitest run tests/assistant.test.tsx`: 55 passed. `tsc --noEmit` clean; eslint on features/assistant clean.
- A first checks.sh failed only on a lint warning, since fixed.
- Scores: none (fidelity not run).

## Blocked
Heavy work paused by the coordinator. Needed: push (network), checks.sh under the lock, production build, fidelity at 1440 and 390 for SCR-05-desktop-cant and SCR-05-mobile-cant, e2e on ports 4774/4775. I stopped my own queued checks waiter (PID 18741).
