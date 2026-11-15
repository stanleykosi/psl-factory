STATUS: READY
COMMIT: 777d9a3f11f10544e6d43ffa7d52a86f7202df99
BUILDER: builder
LANE: full

## Summary
- Desktop: the "N versions · Changed by X, date" line moved out of the action column to one muted line under the name in the Document cell, so read-only rows show it too (UI-1-2, D-79). Version and kind stay inline after the name, "Version 3" wording kept.
- Phone: the "AS OF" line is back directly under the note, before the cards (UI-1-3, D-78).
- Tests: a component test with history on every row (read-only fixture, line sits in the Document cell, no Upload control) and one for the as-of position (UI-1-4). Fixtures unchanged.
- Phone visual is 78.8 (was 83.3), waived under D-78 / the SCR-34-mobile exception already in fidelity-exceptions.json (not touched). Desktop 95.9.

## Changes
- `frontend/src/features/setup/TemplatesView.tsx`: history line rendered as a block `setup-docname__history` under the name; removed from the action cell; phone as-of paragraph moved after the note callout.
- `frontend/src/features/setup/setup.css`: added `.setup-docname__history` (block, no left margin); removed the now-unused `.setup-actioncell` flex rules (kept the nowrap rule for the link).
- `frontend/tests/setup-templates.test.tsx`: two new tests (42 total).

## Fixes
- UI-1-2 | 777d9a3f | history line moved to the Document cell
- UI-1-3 | 777d9a3f | phone as-of under the note
- UI-1-4 | 777d9a3f | test coverage with history on every row (fixture kept as is)
- UI-1-1 / UX-1-1 | not builder-owned | settled by D-78 (waiver)
- UX-1-2, UX-1-3, UX-1-4 | 777d9a3f | resolved by D-79 and the as-of move (version wording already "Version 3")
- UX-1-5 | left: no action needed per the review.
- UI notes (44px hit areas overlapping by ~7px, count-line gap instead of "·") | left: not defects, taste.

## Acceptance criteria
1. [x] Desktop SCR-34 @1440: coverage 100% with exceptions, visual 95.9, PASS (`round-2/fidelity/SCR-34-desktop-1440`).
2. [ ] Phone SCR-34 @390: coverage 100% with exceptions, visual 78.8 < 90; waived by D-78 (`round-2/fidelity/SCR-34-mobile-390`, `scores.txt`). Down from 83.3 because as-of now sits above the cards, as the design engineer chose.
3. [x] History line in the Document cell for all rows, read-only included: new component test.
4. [x] Phone as-of under the note: new component test.
5. [x] Other round 1 criteria unchanged: e2e below passes.

## Validation
- `bash delivery/checks.sh` in the worktree: exit 0 (1443 tests).
- `E2E_PORT=4641 MOCK_PORT=4642 npx playwright test e2e/setup-templates.spec.ts e2e/setup.spec.ts`: 11 passed, 28 passed.
- Fidelity once, production build on 4641 with mock on 4642, FRAME_FIXTURES=1, cookie psl_mock_persona=admin.
- Servers stopped by PID, `frontend/test-results` deleted, git status clean, pushed.

## Blocked
None.
