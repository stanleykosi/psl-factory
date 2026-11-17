VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 521bbf184e45598b765b3c59c8625e20cd335980
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
- I re-ran the fidelity tool against the running head (app :4794, mock :4793) for all 4 boards. Element coverage is 100% after exceptions on 3 boards. Desktop-published is 96.3%, but only because of the shared mock's signed-in person (see Notes). Visual: desktop-internal 76.5, phone-internal 85.8, desktop-published 81.2, phone-published 89.9. That matches the builder (76.9 / 85.8 / 81.5 / 89.9).
- All 4 boards are under 90 and above D-83's 70 floor. Most of the remaining gap comes from D-111 (Conflicts 1, 3 to 8 and 11) and goes to the design engineer as visual waivers.
- Two gaps can be fixed in this lane and block under D-83 ("the side-by-side reading finds no fixable gap"):
  - UI-1-1: "Open actions" is drawn as a plain underlined link. The board draws an outlined button, and so does the "Open the minutes" button next to it.
  - UI-1-2: at 390 the actions table scrolls sideways inside its panel, so DUE and STATE (including OWNER NEEDED) and part of OWNER are cut off.
- The diff adds no CSS, no colour literals and no one-off components. The Sent to list, the Unknown receipt and the Unknown due tag use the existing frame styling.

## Findings
- UI-1-1 | blocking | low | frontend | "Open actions" is a plain blue underlined link (weight 400, #2459D6, no border). The board draws an outlined, full-width, weight-600 ink button (tool "looks": weight 600 vs 400, colour #1F2427 vs #2459D6, outlined vs none, underline). On W-2312 it sits beside "Open the minutes", which is an outlined button, so the same links row mixes two styles. Conflicts 6 (D-111) only excuses the placement and size (links row instead of the Next panel), not the button style. Expected: draw the `project_tab` link with the existing button-link classes the app already uses for navigation (`<Link className="psl-btn psl-btn--secondary">`, as in `src/features/rfp/RfpOutcomeLink.tsx:9` and `src/features/response/ResponseView.tsx:118`). It stays a link for a11y. The `assistant` link stays as it is. Actual: `frontend/src/features/workspace/Links.tsx:94-97` routes `project_tab` through the assistant branch's plain `<Link>`.
- UI-1-2 | blocking | medium | frontend | At 390 the actions table (W-2310, W-2311, W-2312, W-2314) has `scrollWidth` 560 inside a 322px box (`.ws-table { min-width: 560px }`, `workspace.css:105`). The first view at phone width shows only ACTION and part of OWNER: "Tunde Bello" and "Ada Okoye · Lagoon Health" are cut at the panel edge, and DUE ("Unknown") and STATE (OPEN / OWNER NEEDED) are out of view, with nothing on screen to show the table scrolls. D-111 approved Conflicts 4 Option A because "everything the backend returns is visible … including OWNER NEEDED". As built, the key fact on this screen is hidden on phones. W-2313 already gets the stacked phone layout through the `:has(.ws-table__steps)` rule (`workspace.css:153-159`), so the frame can do this. Expected: at phone width the 4-column actions table shows every cell without sideways scrolling. Either stack it like the W-2313 rows, keeping a visible column label for DUE and STATE so a lone "Unknown" is not ambiguous, or apply an equivalent rule limited to this table. The F-23 tables must not change, or must be re-proved in the a11y e2e. Actual: see `/private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/shots/W-2311-390.png` and `delivery/features/F-28/round-1/fidelity/SCR-28-mobile-internal-390/side-by-side.reviewer-ui.png`.
- UI-1-3 | non-blocking | low | frontend | `fidelity-exceptions.json` has no entry for the gaps the tool reports as "moved" or restyled under signed conflicts: "Open actions" in the links row (Conflicts 6), the green band drawn as a white panel with a tag (Conflicts 7), Next order and side column (Conflicts 8), and the project tab with no current tab and Projects not marked current in the nav (Conflicts 11). These are outside the pass rule, but the design engineer signs the waivers from this list. Add them with their Conflicts number so the waiver records the whole visible difference.

## Fidelity per board (reviewer run, head 521bbf18)
| board | width | coverage (with exceptions) | visual | missing (all excepted unless noted) | moved | notable look differences |
|---|---|---|---|---|---|---|
| SCR-28-desktop-internal | 1440 | 63 (100) | 76.5 | crumbs + 2 crumb links, project tablist + 5 counted tabs (C11); banner sentence (C2/C7, read inside the panel) | Open actions right→left (C6); Next/main order (C8); Journey tab | Open actions style (UI-1-1); heading 35px vs 32px; Projects nav not current |
| SCR-28-mobile-internal | 390 | 40 (100) | 85.8 | ← Project, FILED bar tag, short sentence (C5/C4) | none | title 22 vs 20px; table cut at 390 (UI-1-2) |
| SCR-28-desktop-published | 1440 | 59.3 (96.3) | 81.2 | as desktop-internal, plus "Tunde Bello · PMO", which is not excepted. That is the shared mock's persona (Ada Okafor · Finance Lead), not the build; the builder's run had 100 | as desktop-internal | as desktop-internal |
| SCR-28-mobile-published | 390 | 40 (100) | 89.9 | ← Project, DONE, short sentence (C5/C4) | none | table cut at 390 (UI-1-2) |

Extras, all expected under D-111: "Sent to" (C1); OWNER and DUE columns (C3); the full stacked desktop sections on the phone (C4); the frame's nav (Overview, Setup, alerts), History, the subtitle "Formal minutes and action handoff · MIN-0141" and the phone "← Queue" (C11 frame items).

Gap split for the design engineer:
- Forced by D-111, so it becomes a waiver:
  - the returned sentence in the frame panel with a tag instead of the green band (C7)
  - the 4-column table instead of rows of title and tag (C3)
  - "Sent to" (C1)
  - "Open actions" in the links row under the main column (C6)
  - Next in the side column after main (C8)
  - phone showing the desktop wording and every section (C4, C5)
  - frame tab bar with no counts and no current tab, and frame nav (C11)
- Fixable in this lane: UI-1-1 and UI-1-2. Neither will lift the scores to 90. After the fix, all four boards still need a signed D-83 visual waiver (`approved_by` is still "builder proposal, pending design engineer").

Reviewer evidence copied as `report.reviewer-ui.json` and `side-by-side.reviewer-ui.png` into each `delivery/features/F-28/round-1/fidelity/<board>-<width>/`. I did not overwrite the builder's files.

## Verified
None (round 1).

## Notes
- Environment: the shared mock at :4793 serves the persona "Ada Okafor · Finance Lead" to fresh browser contexts during this run (probably a parallel reviewer's persona switch), so "Tunde Bello · PMO" reads as missing on desktop-published. This is not a build defect. My first desktop-published run returned a half-loaded page (coverage 11%); the rerun is the one reported.
- W-2312 at 1440 and 390: there is a large empty area left of or below the "Confirm what happened" panel, and "See all exceptions" sits flush against the sentence panel. This is the same as merged F-21 (W-2212), so it predates this branch and I have not raised it against F-28.
- Heading 35px vs the board's 32px, and the status tag top-aligned rather than centred on the heading line, are frame-wide and the same on F-21/F-23 pages.
- The W-2313 stacked phone rows show "Unknown" and the state tag without column labels (existing F-23 pattern). Worth fixing together with UI-1-2.
