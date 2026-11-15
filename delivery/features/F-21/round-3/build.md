STATUS: READY
COMMIT: 31f0d25efa8bb8e90da50b0d43c4e71b4bf3fb0d
BUILDER: builder
LANE: frontend

## Summary
- The unconfirmed cite hint is replaced with the UX-accepted wording, shown once per form as the `help` of the first records field, carried in W-2201's data.
- The shared frame (StepForm.tsx) is back as in round 2 and holds no weekly wording.

## Changes
- frontend/mock/fixtures/work/W-2201.json: the eight per-field helps removed; the new sentence set once on the first records field of each step (Send, Save draft).
- frontend/tests/weekly.test.tsx: hint test expects "Saved records are not shown here. Choose at least one record for this part before you send." once in the Save draft form.
- frontend/src/features/workspace/StepForm.tsx: no net change from round 2.

## Fixes
- UX-2-1 | 31f0d25efa8bb8e90da50b0d43c4e71b4bf3fb0d | wording replaced, once per form

## Acceptance criteria
1. [x] Hint wording per UX-2-1: weekly.test.tsx asserts the exact sentence once.

## Validation
- bash delivery/checks.sh: exit 0.
- vitest weekly: 25 passed.
- Playwright weekly + workspace (ports 4741/4742, FRAME_FIXTURES=1): 62 passed; servers exited with the run.
- Fidelity not re-run: the hint sits under the first cite field (one line instead of four); no other layout change.
