STATUS: READY
COMMIT: 48752f436c91d0f5f3ae640e7372a5cf7021095d
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes UI-1-1..UI-1-5 and UI-1-7, plus the cheap non-blocking notes (TECH-1-1..1-3, UX-1-1, UX-1-3, UX-1-4); UI-1-6 handled in the exceptions file.
- The review document and Documents tab now live on P-0101 ("Lagoon Health · patient app"), so the crumb, the project and the tab counts agree (board counts 6/4/6/9 are P-0101's). This moves the spec's P-0102 to P-0101 in fixtures, tests and e2e URLs; the spec's acceptance text says P-0102, flag for the coordinator.

## Changes
- `DocumentReview.tsx`: status tag now on its own line under the title row; phone flag line directly after the sections; disabled "Edit as v3" in the pinned phone bar (desktop: natural width in the page); after a return, if the re-read shows no `returned`, a warning with the document's own status and Try again replaces "Recording the return…".
- `DocumentParts.tsx`: agent strip is `Callout kind="info"` (avatar, bold name inline, backend lines, disabled "Ask Tola to draft v3" with "Not available yet"); `body_url` link only if `isLinkUrl`.
- `documentModel.ts`: `isLinkUrl` (https/http or relative; refuses javascript:, data:, `//host`, backslash forms, other schemes, empty); phone amounts tag reads "Amounts: Unknown/Held/Blocked" when not done.
- `document-review.css`: aside 333px, spacing and heading tokens (`--space-20px`, `--text-lead-size`), no raw px left.
- `ReviewControls.tsx`: no "0 / 2000" counter and a 3-row note. No rule requires the counter: the 2000 limit is still checked on press (`noteProblem`) with its error. The counter is a TextArea `limit` option, simply not used.
- `DocumentsTab.tsx`: comment on the type-required `VIEW`.
- Fixtures/tests: documents moved to P-0101 (6 rows, one with a work_id); model, component and e2e tests updated, plus new tests for the URL family and the unconfirmed-return state.
- `fidelity-exceptions.json`: dropped the "Tola" entry; re-worded the "Tola · PMO agent …" one to conflict 1 (B) only; waivers carry the round 2 scores.

## Fixes
- UI-1-1 | 48752f43 | tag moved out of the flex row, own line at every state
- UI-1-2 | 48752f43 | compact info strip like ws-agentnote
- UI-1-3 | 48752f43 | Edit as v3 natural width; pinned phone bar
- UI-1-4 | 48752f43 | flag directly under sections
- UI-1-5 | 48752f43 | aside 333px, no counter, 3-row note
- UI-1-6 | exceptions file | "Tola" dropped; the other re-cited
- UI-1-7 | 48752f43 | tokens
- TECH-1-1, TECH-1-2, TECH-1-3 (comment only), UX-1-1 (same disabled-button treatment kept as text button in the strip), UX-1-3, UX-1-4 | 48752f43
- Left: UX-1-2 (taste, needs a backend sentence).

## Acceptance criteria
As round 1 with P-0101 in place of P-0102; all [x] except 18 (fidelity, below). Criterion 1 crumb is "Lagoon Health / Documents / SOW-0198".

## Validation
- `bash delivery/checks.sh` under the lock: exit 0, 2173 tests.
- `playwright test document-review project-tabs` (4850/4851): 49 passed.
- Targeted vitest (model, component, mock, project-tabs): 134 passed.
- Fidelity, one run, production build, fonts loaded, all 4 boards: coverage 100% after exceptions on all four; visual desktop 72.0, desktop-returned 79.5, mobile 69.1, mobile-returned 74.0. None reaches 90; waivers are proposed in `fidelity-exceptions.json` ("builder proposal, pending design engineer"); mobile is below the 70 floor and asks the one-board exception. Reports in `round-2/fidelity/`.

## Blocked
None.
