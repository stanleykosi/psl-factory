STATUS: READY
COMMIT: 122c9d294658aa736a277d5dcac185021233891a
BUILDER: builder
LANE: frontend

## Summary
- Round 4 lean fixes only: e2e assertion, empty live completions list, UI-1-4 confirmed.

## Fixes
- QA-3-1 | 122c9d29 | `e2e/project-tabs.spec.ts`: Milestones test now asserts one "Mark complete" link per "Not completed" stage; new test with cookie `psl_mock_complete=norole` asserts zero links.
- QA-3-2 | 122c9d29 | `isCompletions` accepts `sections: []` (and one section); `useMilestones` reads it as no rows, so the existing "No completions recorded yet." shows. Tests: `milestones-model.test.ts` (`tab([])` true) and `milestones.test.tsx` (QA-3-2 renders empty state, no error).
- UI-1-4 | no change | Already hidden: `MilestoneComplete.tsx` showProofs requires `can_complete`; showPdf requires `can_complete` or the spec's proof_required exception. Proved by `tests/milestone-complete.test.tsx` "UI-1-4: under %s there are no proof radios and no upload zone" (name_in_use, norole, baseline_required) and "proof_required keeps only the PDF zone".

## Validation
- vitest: milestones-model, milestones, milestone-complete: all pass (95, then milestones 37). tsc and eslint clean.
- Playwright project-tabs + money on mock, ports 4970/4971 (PIDs 40791, 40577): 49 passed, desktop and phone. Servers exited with the run; no listener left.
