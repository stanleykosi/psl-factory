STATUS: READY
COMMIT: 5dea11efbc33d8f40c3f9c3beb40934067bb7fba
BUILDER: builder
LANE: full

## Summary
- Round 4 fixes only UI-3-1: table money cells are left-aligned in the body sans, the amber note has the warning icon.
- unknown-money 1440 went 72.3 to 75.6 (coverage 100%); table 1440 stays 77.5 (forced, unchanged). Neither reaches 85.
- The board has no "As of ... reconciled" line, so that is an exception, not a move.

## Changes
- `frontend/src/features/workspace/workspace.css`: `.ws-table td.num` uses the sans face; `.ws-table .num` is `text-align: left` (header cells too, header stays mono). Money stays the full amount (D-63).
- `frontend/src/features/workspace/Sections.tsx`: the section note draws `WarningIcon` (the shell icon) before its text.
- `delivery/features/F-17/fidelity-exceptions.json`: new exception for the note's typographic apostrophe (fixture data); the unknown-money entry now also names the as-of line and the Unknown chip.
- `round-4/fidelity/`: report.json and side-by-side.png for unknown-money-1440 and table-1440, plus region-scores.txt.

## Fixes
- UI-3-1 | 5dea11e | left sans money, warning icon on the note. Table inset: the panel body already pads 14px, the same as the board (`padding: 14px`), so nothing changed. As-of line: the board has none; recorded as an exception.

## Acceptance criteria
1. [x] Money cells left, sans: side-by-side shows left-aligned amounts in sans.
2. [x] Warning icon on the amber note: visible in the side-by-side.
3. [~] unknown-money 1440 near 85: 75.6. Remaining gap: full amounts against the board's compact figures (D-63), the amber Unknown chip, the as-of line, and a frame 327px high against 279px.

## Validation
- `bash delivery/checks.sh`: exit 0.
- `E2E_PORT=4701 MOCK_PORT=4702 npx playwright test e2e/workspace.spec.ts`: 31 passed.
- Region check, production build, 1440 only, unknown-money and table: table 100% coverage / visual 77.5; unknown-money 100% (24/24, 13 by exception) / visual 75.6. My two servers were stopped by PID.

## Blocked
Not blocked. The exceptions are proposals pending the design engineer.
