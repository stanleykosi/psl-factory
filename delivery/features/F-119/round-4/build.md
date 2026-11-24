STATUS: READY
COMMIT: ca44c3775de717cd923cfa569ad85c68460bc85f
BUILDER: builder
LANE: full

## Summary
- UI-3-1, UI-3-2, UX-3-1: on phone (below 720px) Save is now a white bar fixed to the foot of the screen, edge to edge (left 0, right 0), 2px top rule, padding 12/16/18, button full width. It is the last element of the form, after Decisions, and it stays pinned at any scroll (it is fixed, not sticky). The page has 140px of bottom padding on phone so the bar never covers the last field or the 422 message. Desktop is unchanged: Save follows the notes file, then Decisions.

## Changes
- `retrospective.css`: phone `.retro__savebar` is `position: fixed` full width; `.retro__page` bottom padding on phone; desktop uses CSS `order` so Save (1) shows before Decisions (2).
- `RetroForm.tsx`: the Save row is now the last child of the form (after Decisions), still inside the same form, so the same submit handler runs. The Decisions block has class `retro__decisions`.
- `e2e/retrospective.spec.ts`: the phone test now checks the bar is the form's last element and follows the Decisions heading, its width equals 390 (+-1) and x is 0, it ends at the screen bottom (+-1) at scroll 0 and again after scrolling to the end, "Add a decision" is clear of it, and the 422 message is above it.

## Fixes
- UI-3-1 | ca44c3775de717cd923cfa569ad85c68460bc85f | edge-to-edge fixed bar at the screen foot, outside the panel's box
- UI-3-2 | ca44c3775de717cd923cfa569ad85c68460bc85f | bar after Decisions, never over it
- UX-3-1 | ca44c3775de717cd923cfa569ad85c68460bc85f | pinned at any scroll

## Notes
- A shared phone bottom-bar slot: there is none for forms (PhoneActionBar is the decide bar only); the clients and assistant forms use their own CSS, so this follows them.
- On desktop the Decisions block comes before Save in the DOM (tab order) but after it on screen, because of the board's order. Left as is.

## Validation
- Retrospective unit tests (3 files): 49 passed. eslint on my files clean. `tsc --noEmit`: no errors.
- `e2e/retrospective.spec.ts` full file on 4992/4993: 25 of 25 pass. Servers stopped by their own PIDs (dev server and mock; the mock's pid file was wrong, I found it with lsof and stopped that one, started by me); ports free. No build, full vitest or gate.
