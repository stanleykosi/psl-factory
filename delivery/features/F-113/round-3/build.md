STATUS: IN_PROGRESS
COMMIT: df2e09f4551626e0e97153c73d924118ceb5546c
BUILDER: builder
LANE: full

## Summary
- UX-2-4 fixed in the mock, not the Delivery tab: `mock/work-live.mjs` now serves live work items 2501 to 2505, so the delivery row titles on the mock reach a live work item instead of a 404.
- Paused by the coordinator before the browser walk. Everything else is done and pushed.

## Changes
- `frontend/mock/work-live.mjs` (lane C's file, additive only, for lane C to know): a small `delivery()` helper over `item()` and five entries 2501 to 2505. Each carries the overview row's line key, title, state, reference and updated_at (2501 to 2503 verified, 2504 action_needed, 2505 ready), with the case id of P-0101. No route, frame or other fixture changed.
- `frontend/tests/mock-work-live.test.ts`: new test that every work_id the delivery mock serves for P-0101 answers 200, validates against the 1.26 work item schema, and matches the row's line, state and reference.

## Fixes
- UX-2-4 | row titles on the mock now reach a live work item (2501 to 2505 answer 200) | df2e09f4551626e0e97153c73d924118ceb5546c

## Validation
- `npx vitest run tests/mock-work-live.test.ts tests/delivery-tab.test.tsx`: 28 pass. eslint on the two changed files: clean.
- No full vitest, build or gate (GitHub runs the gate, D-199).

## Blocked
Left: the browser walk of one row title at 1280 and 390 on `next dev` 4990 with the mock on 4991, checking it reaches the live view. Not started (paused). I started no processes this round, so nothing is running.
