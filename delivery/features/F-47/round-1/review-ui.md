VERDICT: PASS
REVIEWER: reviewer-ui
COMMIT: 438c350fe7fe79233604f2293b6812d10df6c1ee
AUTHORITY: delivery UI review

## Summary
- The local fidelity driver is a fair copy of the shared tool. The only real change is F-05's actions hook, which runs after the page loads and before the font wait and screenshot. Everything else is the shared code: absolute imports of the same `dc-template`, `extract`, `compare`, `visual`, `report` and `assets` modules. The run is valid evidence. The shared tool can't open the drawer, so I could not do a clean run with it myself.
- The added "Done 28" exception is correct, and the recomputation is honest. It is the My work tab under the scrim (Conflicts 8, F-05's rule, the same as the "Unassigned 1" entry). Exceptions only affect coverage, never the visual score. The tool's own formula on the saved reports gives schedules (33+5)/38 = 100% and ledger (32+6)/38 = 100%.
- Side by side, all 8 drawers match their boards in fields, order, words, card, help placement and footer. On both Finance desktop boards the visual score is at least 90 (95.8 and 96.1). Minutes desktop (89.3), change desktop (86.3) and the four phone boards (75.3 to 84.9) can be waived under D-83. Every gap is either the page under the scrim, F-05's signed bottom-sheet frame and shared TextArea height, or the "×" from Conflicts 2. All scores are at least 70, and I found no gap the builder could fix.
- I checked the live build on 4945. On the phone the file card's "×" is 44×44 and "Choose a file" is 358×44, and nothing overflows at 390 px. On desktop the "×" is F-09's 24×24, which meets WCAG 2.5.8; the spec asks for 44 only on phones. The new CSS uses tokens only (`--control-md` = 44px) and only in `.sw-prooffield`. ProofField and useEvidenceUpload are reused from F-09, not copied.
- Before merge, the design engineer must sign every exception and visual waiver. They are all still "builder proposal, pending design engineer" (D-114 is provisional).

## Findings
1. UI-1-1 | non-blocking | low | design engineer | Signature needed. All 30 exceptions and the 6 D-83 visual waivers in `delivery/features/F-47/fidelity-exceptions.json` read `approved_by: "builder proposal, pending design engineer"`. Under D-114 this round accepts them provisionally. D-83 needs a waiver signed per board before the feature can merge. The items to sign are the waivers for minutes desktop (89.3), change desktop (86.3) and the four phone boards, plus Conflicts 2, 7, 9 and 11.
2. UI-1-2 | non-blocking | low | frontend | The saved scores are out of date. `round-1/fidelity/scores.txt` and the two Finance desktop `report.json` files still show 97.4% / pass False, because the "Done 28" exception was added after the run. The recomputation is correct, but the next scored run (a fix round, or the merge run) should regenerate them so the files on record match build.md.
3. UI-1-3 | non-blocking | low | frontend | Two boards were drawn with fallback fonts. On `SCR-04-desktop-change-1440` and `SCR-04-mobile-schedules-390` the tool warned that Google Fonts could not be reached. The board side was drawn in fallback fonts (the "PSL FACTORY" wordmark and the phone title are visibly different), so those two visual scores (86.3, 75.3) are somewhat pessimistic. Both are still above the D-83 floor of 70, so nothing changes. If those two boards are re-run, it should be with network access.

## Per board (coverage as run / with exceptions, visual, D-83)
- SCR-04-desktop-minutes 1440: coverage 73.7 / 100, visual 89.3. Missing (all excepted): the scrim table, its column headers and ages (Conflicts 8), and the two select values, which are matched by their control. Moved: the top-bar name and the drawer title (small shifts). Extra: the bell, the "records you can see" line, and the card's "Remove …" button (Conflicts 2). The drawer is identical to the board. Waivable.
- SCR-04-desktop-change 1440: coverage 71.1 / 100, visual 86.3. Missing (all excepted): the scrim table, the project select value, the textarea label and value (matched by control). Extra: the bell, the records line, the combobox, the textbox and the Remove button. The request box is about 20 px shorter than the board's (the shared TextArea, F-05 as signed). The help line sits under the card as drawn. Waivable.
- SCR-04-desktop-schedules 1440: coverage 86.8 / 97.4 as run, 100 with "Done 28". Visual 95.8, which passes. Missing (all excepted): "Tunde Bello · PMO" (Conflicts 7), "Done 28", and the text-field label and values (matched by control). Moved: the scrim rows. Extra: the Finance persona's own My work page (Overview and Setup links, search, filter, Unassigned tab). The drawer matches.
- SCR-04-desktop-ledger 1440: coverage 84.2 / 97.4 as run, 100 with "Done 28". Visual 96.1, which passes. Same pattern, plus "Continues (optional)" (Conflicts 9). The drawer matches.
- SCR-04-mobile-minutes 390: coverage 69.2 / 100, visual 78.6. Missing (all excepted): "← My work" and "START" (bottom sheet), and the select values. Every drawer item is moved down about 100 px by the phone bar, the strip of My work and the sheet head (F-05 frame). Waivable.
- SCR-04-mobile-change 390: coverage 61.5 / 100, visual 81.0. Same frame shift, plus the shared TextArea's height. The card and the moved help match. Waivable.
- SCR-04-mobile-schedules 390: coverage 61.5 / 100, visual 75.3. Same frame shift. The title wraps to two lines at 390 px. The board was drawn with fallback fonts (UI-1-3). In the full-page capture, the Finance list below the fixed scrim makes the page taller, but the visual score uses the board's height, so this does not count against it. Waivable.
- SCR-04-mobile-ledger 390: coverage 53.8 / 100, visual 84.9. Same frame shift, plus "Continues (optional)". Waivable.

## Notes
- Live checks on http://localhost:4945, all 4 lines at 390 and 1440, choosing a file only and never pressing Start:
  - Minutes and change show the disabled dashed box "Choose the project first." until a project is chosen.
  - Schedules and ledger show "Choose a file" straight away.
  - A long file name wraps inside the card, and the "×" keeps its 44 px column.
  - The "×" is named "Remove <file name>".
  - I could not reach the uploading, failed and "Proof removed" states without mock scenarios, so I did not view them. QA and UX cover them.
- The empty "Choose a file" button is solid-bordered on desktop. No board draws it (Conflicts 3), so it is not scored.
- `.sw-prooffield .resp-label { font-weight: 600 }` is a literal value, but the tokens file has no weight token, and the rule matches the drawer's other labels.
