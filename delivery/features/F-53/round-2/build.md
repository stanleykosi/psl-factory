STATUS: READY
COMMIT: 2dd0f23ff3e91b66d5396c50580da203afee81e2
BUILDER: builder
LANE: frontend

## Summary
- At 390 the proof chip "×", "Choose a file" and the search-box "Clear search" button are now 44x44 targets; desktop sizes and glyphs are unchanged.
- The assistant @-mention picker follows the Menu pattern: Down and Up move between the search box and options, Enter picks, Escape closes.
- Round 2 touches only these two points from round-1 QA; no spec or contract change.

## Changes
- frontend/src/features/response/response.css: phone-only rules for `.resp-chip__remove` (44px, negative margin so the chip keeps its size) and `.resp-filebtn` (44px).
- frontend/src/components/components.css: phone rule making the shared SearchField `.psl-search__clear` 44x44 (My work, Projects, Payments).
- frontend/src/features/assistant/MentionPicker.tsx: arrow, Enter keys on the popover.
- frontend/tests/assistant.test.tsx: unit test for the keys. frontend/e2e/conformance.spec.ts: new e2e measuring the three targets at 390.

## Fixes
- QA-1-1 | chip "×", "Choose a file" and "Clear search" are 44px at 390, e2e added | 2dd0f23ff3e91b66d5396c50580da203afee81e2
- QA-1-2 | mention picker Up/Down/Enter/Escape, unit test added | 2dd0f23ff3e91b66d5396c50580da203afee81e2
- COORD-1-1 | same fix: the 44px targets in the shared components at 390 and the picker keys | 2dd0f23ff3e91b66d5396c50580da203afee81e2

## Acceptance criteria
4. [x] Phone targets at least 44x44: new e2e in conformance.spec.ts measures the three at 390 and passes.

## Validation
- delivery/checks.sh under the lock: passed.
- Playwright on 4931/4932 (conformance, assistant, response, rfp, my-work, projects, payments): 151 passed.
- Demo rebuilt and running on 4925 (mock 4924). Worktree clean and pushed; 4931/4932 stopped.
- Note: "Clear search" is the shared SearchField icon button (the link-style Button was already 44px at phone), so the fix is in SearchField's phone CSS.
