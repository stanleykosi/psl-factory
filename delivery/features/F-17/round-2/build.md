STATUS: READY
COMMIT: a5e803ab09ccd3122a4c252be8658a9138314be0
BUILDER: builder
LANE: full

## Summary
- D-62 built: the frame now draws the shared line layouts, chosen by section kind and step type (never by line or work id). Desktop: a main column plus a side column (`.ws-cols`, as the boards' 600px/340-440px split). The side column holds `suggestions` sections (blue head) and a "Decide" panel for the workspace-scope steps (orange head, full-width buttons, green primary). An open step form is a card with a blue head. Phone: no panel border, white sections, the Decide panel sticks to the bottom (head hidden, 2px top rule), checklist marks hidden and status words as tinted pills.
- UX-1-1 fixed: a 422 message for a field the form does not show now appears in the top alert (test fails on the old code). TECH-1-1/2/3 and UX-1-2/3/4/5 fixed too (see Fixes).
- Region check re-run (same driver and regions.json; two page roots changed, see below). Coverage is 100% after exceptions in all 26 runs. Visual >= 85 in 9 of 26 runs, all at 1440. Several regions still cannot reach 85; the measured gap and cause for each are below. These are not claimed as passing.
- D-LINE-WORKSPACE limits unchanged: contract mock only; nothing real is sent; the idempotency promise is not verified.

## Changes
- `Workspace.tsx`: splits sections into main and side (`suggestions` go side), wraps the workspace steps in a "Decide" panel (`psl-panel--decide`, `STEP_TEXT.decide` is a frame word), renders step forms under it. Step forms stay outside the pinned panel. Failed and done notices name the step; a "Confirm what happened first." line shows by the buttons after an uncertain effect.
- `Steps.tsx`: `StepRow` takes an optional `hint`.
- `workspace.css`: the layout above, tokens only.
- `Sections.tsx`: one "More rows aren't available yet." line per section, both controls point at it by `aria-describedby`; blank or whitespace `value` reads Unknown (TECH-1-3).
- `StepForm.tsx`: unmatched 422 field messages join the top alert.
- `usePageReload.ts`: state resets when `id` changes (TECH-1-1). `useWorkspaceStep.ts`: stale notice without a version when the re-read failed (TECH-1-2); done and failed notices carry the step label.
- Tests: 11 new tests in `tests/workspace.test.tsx` and `tests/workspace-step.test.tsx`; no existing assertion changed. Run against the round-1 source, 8 of the new tests fail (422 top message, blank value, one line per section, label beside message, failed names step, confirm-first hint, 409 no version, id reset).
- Factory: `delivery/features/F-17/regions.json` (steps page root `.ws-steps` / `.ws-steps__buttons` -> `.ws-decide`, because the board region is the whole decide panel), `round-2/fidelity/` (driver copy, `region-scores.txt`, report.json and side-by-side.png only).

## Fixes
- FID-1-1 | a5e803a | shared layouts per D-62 (partial: see gaps below)
- UX-1-1 | a5e803a | unmatched 422 messages shown at the top; new test
- TECH-1-1 | a5e803a | hook state reset on id change; test
- TECH-1-2 | a5e803a | no "version unknown"; test
- TECH-1-3 | a5e803a | blank value reads Unknown; test
- UX-1-2 | a5e803a | "Confirm what happened first." beside the off buttons; test
- UX-1-3 | a5e803a | the more-rows line once per section; test
- UX-1-4 | a5e803a | failed notice names the step; test
- UX-1-5 | a5e803a | a returned message not naming the step gets the step label; test
- Left: TECH-1-4 (retry sends the reloaded revision; needs a backend answer on the idempotency promise before a real-API cutover).

## Acceptance criteria
1-24, 26-29: unchanged from round 1 and still met. The affected e2e and component tests pass. Criterion 9 now shows the "more rows" line once per section (spec text unchanged). Criterion 21 now also covers a named field the form lacks.
25. [~] Region check, `round-2/fidelity/region-scores.txt`. Coverage 100% after exceptions in 26 of 26. Visual >= 85: text-cites 86.3, recipients 89.7, timeline 90.2, checklist 91.5, checklist-gates 91.3, facts 94.5, notice-done 93.6 (all 1440). Below 85 and why:
   - steps 1440 40.4 / 390 36.9: the board panel holds a Note field and sits in a 360px frame the page does not have (no field, drawn by the line's decide step); the Decide panel itself matches in colour, head, buttons.
   - recipients 390 25, timeline 390 27.3: the phone board region is a single green summary line ("Delivered to 2 client contacts. Verified."), each line's own one-line summary (D-62 exception).
   - suggestions 1440 46.9 / 390 41.5: the board splits one suggestion into reference, requirement, answer box and source, with a Status radio group and Edit/Write my own pair; the frame draws the returned item rows with one step set per item (no Status field, no "Write my own" in the data).
   - step-form 1440 48.1 / 390 66: board heading is the section title and the answer is prefilled in place; frame shows the step label and an empty field.
   - table 1440 76.3 / 390 74.3: board bold requirement with source beneath and tag in capitals; frame draws the source as a cite beside it.
   - findings 1440 71.6, unknown-money 1440 65.8 (board SCR-56 forecast has chart-like composition): the measured gap is content composition from that line's own board.
   - text-cites, checklist, checklist-gates, findings, facts 390 (40.9 to 59.9): the phone boards for these use one list region across the whole board (status pills, no sub-lines); the frame shows owner and held-by lines the board omits.
   - notice-done 390 67.9, unknown-money 390 81.2.
   The remaining gaps are for each line's own task, or for design engineer decisions on the exceptions in `fidelity-exceptions.json` (still provisional).

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 (after fixing a lint error, refs read in render).
- `E2E_PORT=4701 MOCK_PORT=4702 npx playwright test` for workspace, work-item, work-item-board, decide, decide-board, response, start-work: 160 passed (axe clean, no sideways scroll, 44px at 1440 and 390 on the new layout).
- Region check on a production build (`API_ORIGIN=http://127.0.0.1:4702 next build`, `next start -p 4701`), same driver; servers stopped; temporary files deleted.

## Notes for the next round
- DOM order: on a page with a `suggestions` section, it now comes after the other sections (side column). Relative order of the other sections is unchanged. On phones the side sections and Decide panel flow after the main sections.
- The Decide panel head reads "Decide" (the contract has no deciding role: boards say "Decide - PMO Lead"). Listed under contract proposals.
- The phone pinned bar uses `position: sticky` inside the workspace, not fixed.
