STATUS: READY
COMMIT: 48221d25fe73354c183109e18cfaaa5c621ae4d1
BUILDER: builder
LANE: full

## Summary
- TECH-1-1: the phone e2e now Tabs through the whole form instead of five hand-picked controls. It starts at the first box (page scrolled to the top, focus with preventScroll), presses Tab, and loops over `document.activeElement` until focus leaves the form or reaches Save. After each Tab it waits (expect.poll) for the focused control's bottom to be at or above the bar's top (+1px; Save is in the bar and is not measured), then asserts `elementFromPoint` at its centre is that control (or its label).
- Two walks: an empty form (7 stops: boxes, participants, held-at, reference/notes, Add a decision, Save) and "Save new version" on case 2002 with a carried decision (text, file, Remove), which has more stops than the first.
- TECH-1-2: the focus handler keeps the requestAnimationFrame id, cancels it on the next focus and on unmount.
- TECH-1-3: the new test fails on the old code (below).

## Changes
- `frontend/src/features/retrospective/RetroForm.tsx`: `frame` ref, `cancelAnimationFrame` in the handler and in an unmount cleanup.
- `frontend/e2e/retrospective.spec.ts`: the old "a focused control is never hidden under the bar" test is replaced by "every control Tab reaches in the form ends above the bar, from the first box to Save".

## Fixes
- TECH-1-1 | 48221d25 | full Tab walk, first box to Save, on two forms
- TECH-1-2 | 48221d25 | RAF id kept and cancelled
- TECH-1-3 | 48221d25 | discrimination run recorded below

## Discrimination run (TECH-1-3)
Throwaway copy outside lane-d2: `git archive 53c24b19 frontend | tar -x` into the scratchpad, `cp -Rc` of lane-d2's node_modules, plus only the new `e2e/retrospective.spec.ts` and a local playwright config; symlinks to lane-d2's `architecture` and `contracts` for the mock; dev server on 4998 and mock on 4999. Old code (no focus handler, fixed 110px padding), the new test only:

```
1) e2e/retrospective.spec.ts:413:3 › phone 390 save bar › every control Tab reaches in the form ends above the bar, from the first box to Save
   Error: empty form step 1: {"inForm":true,"inBar":false,"bottom":775.25,"barTop":762,"hit":true,"name":"_r_c_-control"}
   expect(received).toBe(expected) // Object.is equality  Expected: true  Received: false
   Timeout 5000ms exceeded while waiting on the predicate
1 failed
```
Step 1 is the "Lessons for next projects" field: bottom 775 against a bar top of 762, so it ends under the bar. On the current code the same test passes. (My first version of the test passed on the old code too, because an earlier select click had scrolled the page; the scroll to the top and preventScroll focus fix that, so the test now discriminates.) The copy was deleted and the two processes started there (PIDs 70792 and 70576, cwd checked) stopped.

## Validation
- Full `e2e/retrospective.spec.ts` in lane-d2 on 4992/4993: 27 of 27 pass.
- Retrospective unit tests (3 files): 49 passed. `tsc --noEmit`: no errors. eslint clean on my files.
- Servers in lane-d2 stopped by PID (65984 dev, 65866 mock; cwd lane-d2 checked); all four ports free. No build, full vitest or gate.
