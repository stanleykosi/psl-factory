STATUS: READY
COMMIT: 7ea09ba55efec2f90b009e55042ff1d54c9c80ab
BUILDER: builder
LANE: full

## Summary
- UX-2-4 fixed in the mock, not the Delivery tab: `mock/work-live.mjs` now serves live work items 2501 to 2505, so the delivery row titles on the mock reach a live work item instead of a 404.
- Browser walk done (see Validation). Everything is pushed.

## Changes
- `frontend/mock/work-live.mjs` (lane C's file, additive only, for lane C to know): a small `delivery()` helper over `item()` and five entries 2501 to 2505. Each carries the overview row's line key, title, state, reference and updated_at (2501 to 2503 verified, 2504 action_needed, 2505 ready), with the case id of P-0101. No route, frame or other fixture changed.
- `frontend/tests/mock-work-live.test.ts`: new test that every work_id the delivery mock serves for P-0101 answers 200, validates against the 1.26 work item schema, and matches the row's line, state and reference.

## Fixes
- UX-2-4 | row titles on the mock now reach a live work item (2501 to 2505 answer 200) | df2e09f4551626e0e97153c73d924118ceb5546c

## Validation
- `npx vitest run tests/mock-work-live.test.ts tests/delivery-tab.test.tsx`: 28 pass. eslint on the two changed files: clean.
- No full vitest, build or gate (GitHub runs the gate, D-199).

## Walk
`next dev -p 4990` (API_ORIGIN 4991) and the mock on 4991, both started by me and stopped by PID. On /projects/00000000-0000-4000-8000-000000000101/delivery I clicked the row title "Release gates" at 1280px and at 390px. Both reached `/work/2501`, the live work item view with the heading "Release gates for Lagoon Health", and no /api/v1/work request answered 4xx. No 404 view. Rows 2502 to 2505 are covered by the mock test (all answer 200).

## Blocked
None. Note: after the dev server ran, free disk read 3.0 GB (the .next dev cache in lane-d/frontend).

## Coordinator: D-193 sync with main before merge
Merged origin/main 8573a7a1 (#105 F-125, #106 F-62, #108 ledger test wait) as 7ea09ba5. It merged cleanly, and no F-113 file is touched (`git diff --name-only df2e09f4 7ea09ba5` against the F-113 paths is empty). D-200: base_sha 8573a7a1, no protected path.
