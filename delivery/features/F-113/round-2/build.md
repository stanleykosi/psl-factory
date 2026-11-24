STATUS: READY
COMMIT: 2b2936217bdaf5319c6f464ba7e129bd4ea26e6e
BUILDER: builder
LANE: full

## Summary
- Root cause of UX-1-1, UI-1-1 and UI-1-2: my row classes (`delivery__row`, `delivery__title` and so on) collided with older, unused rules of the same names in `project-tabs.css`, which overrode my grid and padding. The tab now uses its own `dlvov__*` classes in the new `dlvov.css` (old `delivery.css` removed).
- Row layout now follows the board: number box, title with reference beneath, tag with "Updated <date>" beneath it on the right, inside the panel's 14px inset. Phone: one compact line (title, tag) with reference and date beneath; number box hidden as on the mobile board.
- The row title is now the link to `/work/{work_id}` (the API supplies the target). The separate "Open" link is removed, so spec AC3 ("click Open") is met by clicking the title; spec line 80-ish still says "Open" and should be reworded by the coordinator. The panel head is the board's "The six delivery lines, in order"; the spec does not word it differently.
- `fidelity-exceptions.json` written (proposal, pending design engineer). Fidelity re-run done once on the production build (after the heavy-lock build finished); results under Validation.

## Changes
- `frontend/src/features/projects/DeliveryTab.tsx`, new `dlvov.css` (replaces `delivery.css`), `frontend/tests/delivery-tab.test.tsx`.
- `delivery/features/F-113/fidelity-exceptions.json`: 28 exceptions in F-14's format, each with `approved_by: "builder proposal, pending design engineer"` and a spec reason: the 3 OF 6 DONE tag and DLV-0052 (DC-3, D-182), Tola card and its texts, NEXT card, the Release to Closure sub-nav strip (Question 3 a, D-187), "Open the handover", the not-started Closure link, and frame items (breadcrumb with fixture project name, shell persona, PM tag, Planning tab from live tabs[]). `visual_waivers` has the two D-83 waivers (75.4 and 78.7), also pending the design engineer.

## Fixes
- UX-1-1 | tag and date no longer overlap; own class names | 6636f0eb
- UI-1-1 | same | 6636f0eb
- UI-1-2 | rows sit inside the panel body inset | 6636f0eb
- UI-1-3 | compact phone row (title and tag on one line) | 6636f0eb
- UI-1-4 | title is the link; board head wording | 6636f0eb
- UX-1-2 | closure reasons read "Title – finding" | 6636f0eb
- UX-1-3 | phone rows tightened (same change as UI-1-3) | 6636f0eb
- UI-1-5 | exceptions file written, pending design engineer | not a code commit

## Acceptance criteria
Unchanged from round 1 except AC3: the started row's title link goes to `/work/2501` (test updated). Targeted tests pass.

## Validation
- `npx vitest run tests/delivery-model.test.ts tests/delivery-tab.test.tsx tests/projects-journey.test.tsx tests/projects-model.test.ts`: 86 pass. `eslint` on the changed folders: clean.
- Full gate, full vitest: not run by me (coordinator queues the gate).
- Fidelity (one run, production build, Next 4990 / mock 4991, with the exceptions file; reports and side-by-side images in `round-2/fidelity/`):
  - SCR-43 desktop 1440: coverage 100% after exceptions (54.2% raw), visual 75.4, moved 3, extra 7. Under 90, so it relies on the proposed D-83 waiver (visual >= 70).
  - SCR-43 mobile 390: coverage 100% after exceptions (50% raw), visual 78.7, moved 1, extra 9. Same waiver.
  - Side-by-sides read: rows are aligned, tag and date no longer overlap, rows sit inside the panel inset, phone rows are one compact line with reference and date beneath. The side-panel exception needed the empty name `""` (the tool's key), fixed in the file; the desktop figure above is from the re-run after that.
  - The remaining gap is the hidden Tola and NEXT cards, sub-nav strip, per-row gate sentences, handover/archive swap, and the frame header (all in the exceptions or waiver reasons).
- Servers I started on 4990 and 4991 are stopped.

## Blocked
None. Open for the design engineer: sign the proposed exceptions and the two D-83 visual waivers in `delivery/features/F-113/fidelity-exceptions.json`.

## Coordinator: D-193 sync with main
Merged origin/main (ae0525fb: F-86, F-72) once before merge, as merge commit 2b293621. The one conflict was in `frontend/mock/server.mjs`: both sides kept, F-113's `deliveryRead` route and import plus F-72's live document-review route and its wider `documents.mjs` import. F-113's own code is unchanged. `delivery-tab` and `delivery-model` tests: 47 pass.
