VERDICT: PASS
COMMIT: 568c0a407f78b39a3cb7cf33f0030cc3b0a6028c
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design system and approved SCR-06 artboards)

## Summary
- The fidelity gate passes on SCR-06-desktop at 1440, with and without the `status` cookie: coverage 100% after exceptions (70.8% raw) and visual 94.1. SCR-06-mobile at 390 has coverage 100% after exceptions (77.8% raw) but visual 89.8, with or without the cookie. That is 0.2 under the bar. D-18 (provisional, counted as approved) accepts this score, because the gap comes from the frame header and the missing F-06 preview.
- Reading the side-by-sides, the Overview's own content matches the boards: avatars (now the real mascots), subtitles, 40px h1, tile metrics, row grid, station track, tag tones under `status`, board order (lines, then exceptions, then legend), and the phone line cards with 18px squares and the summary line. Every remaining difference is an approved exception (D-08, D-14, D-18).
- The 3D floor follows concept 3 (D-01) almost frame for frame. It shows the same lean, card deck, line slabs with tags, chips with counts, and PERSON chips in the signal colour. Labels are readable at 1x and no label sits outside the stage. The pointed card lifts with a focus outline. Dragging turns the board, and Reset view puts it back exactly and clears the readout. Tab focus fills the readout.
- Both round-1 findings are resolved (see Verified). Three low, non-blocking items remain.

## Findings
- UI-2-1 | non-blocking | low | frontend | 3D floor: in the Invoices lane the "1 Approve PERSON" chip overlaps its neighbours "1 Check" and "0 Send" by a few pixels in the default view. These are the only 2 of the 1128 label pairs that overlap. Concept 3 shows the same tightness, and all three chips stay legible. Expected: chips sit clear of each other. Actual: overlapping boxes at 1440 (see `round-2/fidelity-review/floor-3d/f08-3d-full.png`). The chips are placed in `frontend/src/features/floor/scene.ts`, and `.floor__chip` is in `floor.css:9`.
- UI-2-2 | non-blocking | low | frontend | The legend says "The 3D floor shows the same lines with work moving between stations". The 3D floor draws no agents and nothing moves between stations, by design (build.md Notes, D-01 interpretation). Only tiles rise or fade when a count changes. Expected: wording that matches what is shown, for example "...shows the same lines and counts as a tilted board." Actual: `frontend/src/features/overview/OverviewPage.tsx:292`. This is copy, so the UX lens may own the final wording.
- UI-2-3 | non-blocking | low | product | With the default fixture (no `status` field, so the contract as it is today), tag tones fall back to the round-1 rule. WAITING tags show in red (person tint) instead of the board's amber, and ON TRACK shows grey instead of green. Only the `status` cookie variant matches the board. D-18 accepts this until the backend confirms `lines[].status`. Once the field is in E-OVERVIEW, the default page will match without any frontend change.

## Verified
- UI-1-1 | verified | Superseded by the concept 3 rebuild. Tiles stack on their own card, and the count is an HTML chip above it. At 1440 no tile runs into a chip or into a neighbouring card (`round-2/fidelity-review/floor-3d/f08-3d-full.png`).
- UI-1-2 | verified | Avatars (mascot images, D-14) and board subtitles are shown on every row at both widths. Tag tones follow the board when `status` is present (fidelity `-status` runs). The default fallback is covered by D-18 (see UI-2-3).

## Notes
- **Gate runs.** All ran against the shared build at http://localhost:3811/overview with `--exceptions delivery/features/F-08/fidelity-exceptions.json`. Board mascots were loaded from `design/mascots/canvas-assets.json` (19 mapped), so the board side no longer shows broken images.
  - SCR-06-desktop 1440: PASS. Coverage 70.8 / 100, visual 94.1. 19 board items are missing, all excepted: frame Start work, More ways to start, signed-in name, "LIVE" eyebrow, "See all 4" and the F-06 exceptions table (header and rows). 3 items are extra: the persona name, the UPDATED eyebrow and "See all exceptions". 4 items are listed as moved, all by 3px vertically, because the eyebrow line box is 18px where the board's is 15px.
  - SCR-06-desktop 1440 with `psl_mock_overview=status`: PASS. The figures are the same as the default run.
  - SCR-06-mobile 390: FAIL, visual 89.8 (allCells 92.3). Coverage is 77.8 raw and 100 after exceptions, with 0 unexcepted items. 4 items are missing: "← Home" (D-08) and the F-06 "All exceptions · 4" preview with its two cards (D-18). 6 items are extra: the shell's Menu and mark, the UPDATED line under the lines, and the exceptions heading, link and note. Nothing is moved and there are no look differences.
  - SCR-06-mobile 390 with the status cookie: the same result as the default phone run.
  - Evidence (report.json and side-by-side.png for each run) is in `delivery/features/F-08/round-2/fidelity-review/SCR-06-*/`. The 3D captures (build default, hover lift before/after, turned, reset, and concept 3 at the same size) are in `round-2/fidelity-review/floor-3d/`.
- **Seg control look difference.** The tool reports a dark bar under the Flat and 3D floor options on the page and none on the board. In the side-by-side the control reads the same as the board: it is the shared `psl-seg` border, not an F-08 style. Taste only.
- **3D, compared with concept 3.**
  - Camera, lean, colours and labels match.
  - The concept's agent chips (Tola, Chidi, Zainab) are left out on purpose, because the contract has no field for where an agent works.
  - At the default view, the front edge of the Payroll slab touches the bottom of the stage, as it does in the concept. Nothing that carries text is cut off.
  - When the board is turned, cards that leave the stage hide their labels instead of spilling past it.
  - No console errors and no 4xx responses while 3D was in use. No sideways scroll at 1440.
- **Tokens.**
  - `overview.css` and `floor.css` use token variables only.
  - `scene.ts` reads its colours from CSS custom properties. The only literals are the white light colours.
  - Pixel sizes follow the board's metrics (40px h1, 26px and 18px squares, 210/150px columns). Spacing on the phone uses `--space-3`.
- **Not re-run by this reviewer:** axe, keyboard order across the full page, and the 768px width. The builder's e2e run (95 passed) covers axe and keyboard.
- This review read the shared build and mock without changing them. My own headless Chromium sessions are closed. No server was started or stopped.
