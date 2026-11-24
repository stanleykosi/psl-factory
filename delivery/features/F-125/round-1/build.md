STATUS: READY
COMMIT: a0eb67073f7a675f3a1436fbd62b855b8a44161d
BUILDER: builder
LANE: frontend

## Summary
- /my-work no longer throws on live GET /work rows; a response with any row whose `kind` is not a v7 kind fails as a whole and shows the existing error card.
- One shared guard in `fetchPage` covers load, refresh and Show more, so refresh and Show more use their existing failure paths and keep the rows on screen.
- No new words, CSS or components. `WorkRows.tsx` is untouched.
- Four new vitest cases; no existing assertion edited.
- `npm run build` was not run by me (see Validation); the gate will run it.

## Changes
- `frontend/src/features/my-work/model.ts`: new pure `isV7Row(item)` (kind is an own key of `KINDS`).
- `frontend/src/features/my-work/MyWork.tsx`: `fetchPage` throws `networkError()` when any item fails `isV7Row`. Imports `isV7Row`.
- `frontend/tests/my-work.test.tsx`: new `live rows (F-125)` block: load, mixed list, Show more, refresh.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Live-shaped response shows the error card, no throw: vitest case asserts role=alert "We couldn’t load your queue".
2. [x] Refresh and Show more: two vitest cases, rows stay (10), "Couldn’t refresh" / "We couldn’t load more" shown.
3. [x] v7 unchanged: full vitest run 161 files / 3874 tests passed; existing tests unedited. Playwright e2e/my-work.spec.ts not run by me.
4. [x] No new strings, CSS or components: diff is the three files above.
5. [x] Live check: Django 8008 on 55433, Next dev 4972, signed in as qa-seed, GET /api/v1/work returned 200 (2225 bytes) and /my-work showed "We couldn’t load your queue ... Reference network_error", nav stayed up, zero page or console errors. Screenshot: `/Users/Hunchoo/psl-factory-main/delivery/features/F-125/round-1/live-my-work.png` (taken at the first sign-in, before the final run; it shows the loading state, so the error text above comes from the final run's DOM output, not the image). Whether lane C's work 1 was in the 2225-byte body was not inspected.
6. [x] Mixed list (v7 row plus live row) fails whole response: vitest case.

## Validation
- `npx vitest run tests/my-work.test.tsx tests/my-work-model.test.ts`: 75 passed.
- New tests against old src (stashed): 4 failed as expected.
- `npm run lint`, `npm run typecheck`: clean.
- Full `npx vitest run` via heavy lock: 161 files, 3874 tests passed.
- `npm run build`: queued on the heavy lock but not completed; my attempt to stop a stuck waiting process was refused, so it did not run. Gate runs it.
- Servers on 4972 and 8008 stopped by PID.

## Blocked
Not blocked.

## Coordinator merge of main 3b7df6cc
- Merged as a0eb6707 with no conflicts; `npx tsc --noEmit` reports 0 errors.
