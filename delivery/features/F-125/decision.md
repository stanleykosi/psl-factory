RECOMMENDATION: AUTO_MERGE
COMMIT: 215361f5a3cf78d8fde907d7c12ec055c9e3dbf7
APPROVER: approver

## Summary
- Adds a guard in `fetchPage` (`MyWork.tsx`) and an `isV7Row` helper (`model.ts`). A response with any row whose `kind` is unknown now fails as a whole, and the page shows its existing error card instead of crashing.
- Against current main (8692cf87) the PR changes 3 files: `MyWork.tsx`, `model.ts` and `tests/my-work.test.tsx`. That is 50 insertions and 1 deletion. The larger base-to-head diff is merged main (F-86, F-72, CI), not F-125.
- No new copy, CSS, component, endpoint or data. No protected path changed. Risk is low and the only surface is ui.
- The technical, UX, UI and QA reviews all PASS and name 215361f5. QA ran it live: the card appeared, there were no console errors, and Try again returned to the card. The gate and PMO acceptance name a0eb6707, which is the pre-sync head. D-193 covers this, and the sync merged only unrelated main changes.

## Why
This is a contained guard that reuses existing states and stays inside readiness's Scope. It touches nothing on the merge policy's always-human lists, and no spec assumption is a product decision. The one gap is that the gate and PMO acceptance name the pre-sync head. Per your note, CI passed on 215361f5, and the diff against main is unchanged by the sync.

## Acceptance criteria
1. Live-shaped response shows the error card without throwing: met. The new vitest case exists, the technical reviewer re-ran the file (42 passed), and I read the guard in the diff.
2. Refresh and Show more are covered: met. Both go through `fetchPage`, and tests were added for them.
3. v7 mock behaviour unchanged: met for unit tests. The test diff only adds lines, and QA saw the mock page render rows. The Playwright e2e was not run (PMO-1-1, non-blocking).
4. No new design or words: met. The diff adds no string, CSS or component.
5. Live check: met. QA saw the error card against the live API with no console errors. The live row was work 4, not work 1, with the same shape.
6. Mixed list fails the whole response: met. `every(isV7Row)` enforces it, and a vitest case covers it.
