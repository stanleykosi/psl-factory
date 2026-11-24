STATUS: READY
COMMIT: 06d07376b02424f191502441b6f29635848c88d5
BUILDER: builder
LANE: full

## Summary
- UI-2-1: on phone (below 720px) the retrospective form's Save is now a sticky bottom bar with the shared action-bar look (surface, 2px top rule, 12/16/18 padding), full width; desktop placement unchanged.
- It sticks only while the form is on screen and sits in the flow at the end of the form, so it never hides the last field or the form-level 422 message (that message is above it in the flow).
- UI-2-2 (visual under 90) left for the design engineer (LD-Q5).

## Changes
- `frontend/src/features/retrospective/retrospective.css`: phone `.retro__savebar` sticky bar (same pattern as clients.css and assistant.css sticky bars).
- `RetroForm.tsx`: the Save row carries `retro__savebar`. The follow-up action form and "Save new version" button are not sticky.
- `e2e/retrospective.spec.ts`: new phone test (bar at bottom of screen, form message above it); the phone order test now compares document order, because a sticky Save no longer sits at its flow position at scroll 0.

## Fixes
- UI-2-1 | 06d07376b02424f191502441b6f29635848c88d5 | Save is a bottom bar on phone

## Validation
- Unit: tests/retrospective-failure, -model, -summary: 49 passed. eslint clean on my files.
- Dev server 4992 + mock 4993, e2e/retrospective.spec.ts: 25 tests; the 23 unrelated passed on the first run, the two phone tests (one new, one adjusted as above) pass after the adjustments. Servers stopped by PID, ports free. No build, full vitest or gate.
- Note: the Save bar's width is the form's width (about 322px of the 358px panel on 390), since the form sits inside the panel; the board's bar spans the screen.
