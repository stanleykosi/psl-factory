STATUS: READY
COMMIT: d9f900c2122f048e73d85ec1b4e3daac63125900
BUILDER: builder
LANE: frontend

## Summary
- Round 3 fixes the one blocking finding: the "What happens next" panel head is white on the blue band.

## Changes
- `frontend/src/features/projects/milestone-complete.css`: the rule is now `.cmp-panelbox.psl-panel--agent.mscomplete__next > .psl-panel__head` (specificity 0,4,0), which outranks the shared `components.css` rule `.cmp-panelbox.psl-panel--agent > .psl-panel__head { color: var(--action-ink) }` (0,3,0). It sets `color: var(--on-strong)` (white), `background: var(--action)`. The shared rule is unchanged.
- `frontend/tests/milestone-complete.test.tsx`: one test that the panel carries the agent classes and that the CSS file holds the rule with white text (jsdom does not apply the stylesheet, so the rule is read from the file).

## Fixes
- UI-2-1 / UX-2-1 | d9f900c2122f048e73d85ec1b4e3daac63125900 | white heading inside this panel only

## Validation
- `npx tsc --noEmit -p .`: clean.
- `npx vitest run tests/milestone-complete.test.tsx tests/cash-forecast.test.tsx`: 2 files, 88 tests passed.
- eslint was run on the test file only (no output); fidelity and a browser check were not re-run, so the rendered contrast is not measured.
