STATUS: READY
COMMIT: 9d9b149c0eee33789567d9006229314f1224d6d0
BUILDER: builder
LANE: full

## Summary
- UX-5-1: on phone a `focusin` handler on the form (React `onFocus`) scrolls the page with `window.scrollBy` so any focused control inside the form ends at least 8px above the fixed Save bar. It runs in a requestAnimationFrame after focus, skips controls inside the bar itself, and the `scroll-padding-bottom` rule is kept for the cases the browser handles.
- TECH-5-1: the bar's real height is measured (ResizeObserver, phone only) into `--retro-bar` on `html`; `scroll-padding-bottom` is `--retro-bar + 16px` and the page's bottom padding is `--retro-bar + 32px` (fallback 110px). It follows a wrapped reason line.
- TECH-5-2: the e2e no longer uses a fixed wait and now Tabs (not focus()) from "What didn't" into "Lessons", then through the participants, and focuses "Add a decision".

## Changes
- `RetroForm.tsx`: bar ref, height measurement effect, `clearOfBar` focus handler (phone only).
- `retrospective.css`: padding values from `--retro-bar`.
- `e2e/retrospective.spec.ts`: the focus test: after each Tab or focus it waits (expect.poll) for the control's bottom to be at or above the bar top (+1px), then asserts `elementFromPoint` at its centre is the control.

## Fixes
- UX-5-1 | 9d9b149c0eee33789567d9006229314f1224d6d0 | focused control scrolled fully clear of the bar
- TECH-5-1 | 9d9b149c0eee33789567d9006229314f1224d6d0 | padding derived from the bar's real height
- TECH-5-2 | 9d9b149c0eee33789567d9006229314f1224d6d0 | e2e Tabs into Lessons, covers below-the-fold controls, no fixed wait

## Left
- TECH-5-3 (blocks remount when the viewport crosses 720px): accepted trade-off, values live in draft.

## Validation
- Retrospective unit tests (3 files): 49 passed. tsc: no errors. eslint clean on my files.
- Full `e2e/retrospective.spec.ts` on 4992/4993: 27 of 27 pass. I stopped only PIDs 47436 (dev server) and 47325 (mock), both with cwd lane-d2, checked before killing; ports free. No build, full vitest or gate.
