STATUS: READY
COMMIT: 436e9de26df0289e533d4f986de29cc9ae9400b4
BUILDER: builder
LANE: full

## Summary
- Fixes MAIN-1-1: F-85's live mock and tests now match API 1.24.0. No UI added, no src change was needed (the live types in src/api/types.ts derive from the regenerated schema, and the history mapper reads only fields that still exist).
- 1.24.0 changes met: history rows require `actor_kind` and `entry_id` and the response has `next_before`; the work item has new required fields (reference, started_at, verified_at, queue_output_url, exception_*, action_kind, station, agent, tracking_url, proofs_url); each panel has `contract_path`; the weekly report has `return_note`, `preview`, `review_notes`. Case files, tasks and the weekly report core are unchanged.

## Changes
- frontend/mock/work-live.mjs: fixtures carry the new required fields (null or fixed sample values); history rows have actor_kind and entry_id; history answers carry next_before: null; panels have contract_path: null; weekly report has return_note, preview, review_notes.
- frontend/tests/live-work-item.test.tsx: history rows built with actor_kind and entry_id, empty history with next_before.

## Fixes
- MAIN-1-1 | typecheck of tests/live-work-item.test.tsx and mock-work-live contract test | 436e9de26df0289e533d4f986de29cc9ae9400b4

## Acceptance criteria
1. [x] Round 1 criteria unchanged; the mock is validated against contract 1.24.0 in tests/mock-work-live.test.ts (green).

## Validation
- tsc --noEmit: only tests/shell-live.test.tsx (3 errors, lane A's file, not touched). eslint on the changed files: clean.
- vitest: tests/mock-work-live, live-work-item, line-adapter, evidence, cash-forecast: 103 pass.
- Full vitest before the last mock fix: 46 failures in 5 files; 8 were mock-work-live (fixed above). The other 38 are outside F-85: tests/mock-contract.test.ts (E-ME), mock-live-me.test.ts, mock-live-projects.test.ts and demo-mock.test.ts fail because the /me and /projects mocks lack 1.24.0 fields (positions, next_milestone, totals). Those mocks belong to lane A / the frame; not touched.
- Not run: playwright (no UI change), live Django.

## Blocked
None.
