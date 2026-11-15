STATUS: READY
COMMIT: d9cd1d2e011106564b113229ce15100497d81ca7
BUILDER: builder
LANE: full

## Summary
- UI-2-1 to UI-2-7 fixed with the D-63 answers: phone sections are 2px ink boxes with a 14px inset; the Decide bar is a fixed full-width bar with the consequence sentence, and the page keeps its height clear below it; a section `note` is an amber warning box under the section; money is the full amount in the row's size; the desktop checklist has no marks.
- Small notes: TECH-2-1 (a late reload for an old id is ignored), UX-2-2 (a failure notice is scrolled into view), UX-2-1 (bar measured, see below).
- regions.json re-anchored (findings and facts at 390) or narrowed with `widths` (recipients, timeline, suggestions, step-form, facts at 390); list (b) gaps recorded as `visual_exceptions` in fidelity-exceptions.json, "pending design engineer".
- Region check: coverage 100% after exceptions in 21 of 21 runs; visual >= 85 in 9 of 21 (text-cites 390 now 100). The gate is still not met for 12 runs; the causes are content from each line's own board (below). Not claimed as passing.

## Changes
- `Sections.tsx`: no `.psl-amount` on money; the note is drawn after the section as `psl-callout psl-callout--warning`; checklist marks removed; suggestion = mono reference line, answer in a tinted box, detail beneath, agent line dropped when the tag names it, cites dropped when the label already names them.
- `StepForm.tsx`: submit button is always primary (red for danger).
- `Workspace.tsx`: measures the pinned bar into `--ws-bar-h` (ResizeObserver); scrolls a failed, problem or uncertain notice into view (`block: nearest`); notices wrapped in `.ws-notices`.
- `usePageReload.ts`: a read that lands after an id change is ignored.
- `workspace.css`: phone box rules, fixed bar (16px side padding, 44px buttons in rows), page padding-bottom and `html` scroll-padding-bottom equal to the bar, `.ws-row__main { flex: 1 1 0 }`, table nowrap and min-width 560px, cite as a 12px muted line under the words, uppercase tags, footer on one row, sans 600 status pills, suggestion card, text rows without padding on phones.
- Tests: `workspace.test.tsx` (marks gone, suggestion card, note callout and no `.psl-amount`; suggestions text assertion changed because "Suggested by Tola" and "RFP p.6" now show once, a deliberate UI-2-6 change); `workspace-step.test.tsx` (late reload ignored; fails on the old code, passes on the new).
- Factory: `delivery/features/F-17/regions.json`, `fidelity-exceptions.json`, `round-3/fidelity/` (driver copy with a `widths` option, region-scores.txt, report.json and side-by-side.png only).

## Fixes
- UI-2-1 | d9cd1d2 | phone sections bordered white boxes
- UI-2-2 | d9cd1d2 | row end values stay right
- UI-2-3 | d9cd1d2 | fixed full-width bar, page padding equals its height, scroll-padding for Tab
- UI-2-4 | d9cd1d2 | reference cells nowrap, table min-width, scrolls
- UI-2-5 | d9cd1d2 | cite line, uppercase tags, footer on one row
- UI-2-6 | d9cd1d2 | suggestion card
- UI-2-7 | d9cd1d2 | pill font, money size, submit primary
- UI-2-8 | d9cd1d2 | desktop checklist marks removed (D-63)
- TECH-2-1 | d9cd1d2 | late reload ignored; test
- UX-2-2 | d9cd1d2 | the notice is scrolled into view (not tested in a browser: no e2e asserts scroll)
- UX-2-1 | d9cd1d2 | measured on 375x667: W-2001 bar 192px (29% of the height; three buttons share rows), W-2008 97px; no sideways scroll. Kept compact, not reduced to the primary button only.

## Acceptance criteria
1-24, 26-29: unchanged and met (e2e below). One spec line changed by the design engineer: criterion naming the checklist "mark" now has no mark (D-63); the spec text is the coordinator's to update.
25. [~] Region check (`round-3/fidelity/region-scores.txt`), coverage 100% in 21 of 21. Scores (1440 / 390):

| region | 1440 | 390 |
|---|---|---|
| text-cites | 86.2 pass | 100 pass |
| steps | 40.4 | 31.6 |
| recipients | 89.7 pass | dropped |
| timeline | 90.2 pass | dropped |
| table | 77.5 | 72 |
| suggestions | 70.1 | dropped |
| checklist | 91.9 pass | 76.8 |
| checklist-gates | 92 pass | 72.2 |
| findings | 71.6 | 74.7 |
| facts | 94.6 pass | dropped |
| unknown-money | 72.3 | 89.3 pass |
| step-form | 45.2 | dropped |
| notice-done | 93.6 pass | 67.9 |

Region changes: findings 390 now compares SCR-25 mobile's "Risks" row (has a cite) with one findings row (was a SCR-49 checklist, 50.5). Facts 390 dropped: the only phone board rows with label and value (SCR-44 decision) use status pills, and the rows scored 64.2. Recipients, timeline, suggestions and step-form 390 dropped: the phone boards draw a one-line summary, a full-screen swipe card or a full-screen edit page, not the frame pattern (reason stored in `dropped_390`). Left at 390 with a known gap: table (SCR-26 phone is a swipe card), checklist and gates (board omits owner/held-by/due and head), findings, steps (the bar keeps the sentence and shares rows), notice-done (board shows a short summary line).
Still under 85 at 1440: steps (Note field and role in head not in contract), table (44px checkbox targets make rows taller than the board's), suggestions (Status radio, Write my own, requirement title not in the item), findings (no board draws findings), unknown-money (compact amounts are a line task), step-form (no prefill/submit label).

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 (a lint error on a ref written in render was fixed first).
- vitest `tests/workspace*`: 86 passed. New TECH-2-1 test fails on the old `usePageReload.ts`.
- `E2E_PORT=4701 MOCK_PORT=4702 npx playwright test` for workspace, work-item, work-item-board, decide, decide-board, response, start-work: 160 passed.
- Region check on a production build (`next build`, `next start -p 4701`, mock on 4702, FRAME_FIXTURES=1); I stopped only those two by PID.
- Bar size on 375x667 by a small Playwright script.

## Notes
- The phone bar uses `position: fixed`; the page padding and `scroll-padding-bottom` are set from the measured height.
- Questions still open for the design engineer: all `visual_exceptions` entries are proposals pending approval.
