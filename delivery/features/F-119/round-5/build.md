STATUS: READY
COMMIT: 53c24b19059ece9c6d4e8a9bf3eb086a7cba1405
BUILDER: builder
LANE: full

## Summary
- UX-4-1: below 720px a focused control scrolls clear of the fixed Save bar: `html:has(.retro__savebar) { scroll-padding-bottom: 110px }` (the page scrolls on html; scoped to this page by :has and to phone by the media query).
- UX-4-2: the CSS `order` rules are gone. `RetroForm` renders Save once, chosen with `useIsPhone()`: desktop right after the notes file (and the form messages), before Decisions; phone as the last element after Decisions (the fixed bar). Only one Save is in the DOM at a time.

## Changes
- `RetroForm.tsx`: Decisions and the Save row are consts; `phone ? decisions then bar : bar then decisions`.
- `retrospective.css`: `order` rules removed; phone `scroll-padding-bottom`.
- `e2e/retrospective.spec.ts`: desktop test (Tab from the notes file lands on Save; Add a decision follows Save in the DOM) and phone test (focus the last checkbox and the Lessons field; `elementFromPoint` at the centre is the control, and the control ends above the bar).

## Fixes
- UX-4-1 | 53c24b19059ece9c6d4e8a9bf3eb086a7cba1405 | scroll-padding-bottom for the fixed bar, with an e2e check
- UX-4-2 | 53c24b19059ece9c6d4e8a9bf3eb086a7cba1405 | Save in one DOM place by useIsPhone, no CSS order, with an e2e check

## Validation
- Retrospective unit tests (3 files): 49 passed. `tsc --noEmit`: no errors. eslint clean on my files.
- Full `e2e/retrospective.spec.ts` on 4992/4993: 27 of 27 pass. I stopped only the two processes I started (PIDs 6029 dev server and 5973 mock; both had cwd lane-d2, checked before killing); ports free. No build, full vitest or gate.
