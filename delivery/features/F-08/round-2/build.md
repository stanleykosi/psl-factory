STATUS: READY
COMMIT: 1a6ff66150da556f286b9280c9dcd3c300fea2f9
BUILDER: builder
LANE: full

## Summary
- The flat Overview now follows the SCR-06 boards in structure, order, wording and styling. Each line has its agent avatar (tinted Tola, Chidi or Zainab circle) and the board subtitle. Tag tones come from an optional per-line `status`: ON TRACK green, WAITING amber, STOPPED/UNCERTAIN/PROBLEMS red. The order is lines, then the exceptions section with "See all exceptions" on the right, then the legend. The phone view uses the board's line cards, 18px squares and the "18 in progress · 5 need a person" summary.
- WebGL detection is fixed. It tries `webgl2` and then `webgl`, each on a fresh canvas with `failIfMajorPerformanceCaveat: false`, and returns false only when both fail or throw. A new unit test covers this, and the default e2e checks that a normal Chromium shows the 3D option with no "can't show" hint.
- The 3D floor is now concept 3, the "tilted swimlane board" (D-01), ported to three 0.187.0 inside the lazily loaded `features/floor/`. Stations are cards in the flat reading order with stacked tiles. Each card has a count label, and the readout reads "Line · Station · N items · needs a person" on hover or focus. The card you point at lifts, the board leans toward the pointer, and there is a Reset view button. It renders on demand only and draws no agents.
- The console 404 was ours: the "See all exceptions" link prefetched `/exceptions`, which does not exist on this branch, and the pending request also stopped the page from ever settling. The link now has `prefetch={false}`. A production build plus next start served every CSS chunk with 200.
- Fidelity (flat view): the desktop run passes with coverage 100% (with exceptions) and visual 94. The phone run reaches coverage 100% but visual 89.9, 0.1 under the bar; the cause is set out below. The reports are in `round-2/fidelity/`.

## Changes
- `frontend/src/features/overview/OverviewPage.tsx`:
  - Line rows are now `div role="list"`/`role="listitem"`. With the old `<li>` rows the fidelity extractor dropped every name, subtitle and tag (text inside an `li` ancestor counts as "owned"). The ARIA semantics are the same.
  - Added the avatar, name and subtitle column, the tag tone from `tagTone()`, and `aria-label` on the Flat/3D floor radios (same as their text; the extractor reads radio names only from labels).
  - Phone: h1, then the summary line, then the line cards, then the coverage line, then the exceptions section, with no legend. Desktop: eyebrow, then h1 with the View switch, then hint, totals, lines, exceptions and legend, as on the board.
  - The legend now reuses the board's sentences. The count sentence is kept at the end (Assumption 2).
- `frontend/src/features/overview/lines.ts` (new):
  - `LINE_IDENTITY` holds the board avatar agent and subtitle per line name. This is design copy, not business data, and an unknown line gets neither.
  - `tagTone(line)` uses `status` when present. Otherwise it uses the round-1 rule (person when any station needs a person, else neutral). It never reads `note`.
- `frontend/src/features/overview/types.ts`: adds `LineStatus` and the optional `status` on `OverviewLine`.
- `frontend/src/features/overview/overview.css`:
  - Desktop: 40px h1, identity column and `line-height: normal` on the tiles and identity (board metrics). The exceptions header row has the h2 on the left and the link on the right.
  - Phone: line cards with a 2px ink border and 12px padding, 24px avatars, 600-weight names, 18px squares and the summary line.
- `frontend/mock/overview.mjs`, `frontend/mock/fixtures/overview/status.json`: a new cookie variant `psl_mock_overview=status`. It is the default fixture plus `status` per line (waiting, stopped, uncertain, on_track, waiting, on_track, on_track, problems).
- `frontend/src/features/floor/support.ts`: fixed `webglAvailable()` and added `describeStation()`.
- `frontend/src/features/floor/scene.ts` (rewritten, concept 3):
  - Perspective camera (fov 28, yaw -0.2, pitch 0.98, clamped) fitted to the label anchors, then panned and zoomed so the labels fill the stage. Hemisphere and directional light with soft shadows.
  - The board has alternating lane strips, an ink line slab and a rule. Each station is a card (signal tint plus a signal stripe when it needs a person) with up to 10 tiles; the label carries the exact count.
  - HTML overlay: a line label with name and toned tag (aria-hidden), and a station chip `<button>` per station.
  - Raycast hover; drag to turn, clamped. The hovered or focused card lifts and the board leans toward the pointer.
  - A poll change runs the 280 ms ease-out for tiles. New or removed stations rebuild without animation.
  - Frames run only while something moves. Under reduced motion every step snaps. Dispose removes listeners and labels, frees geometry and materials, then calls `renderer.dispose()` and `forceContextLoss()`.
- `frontend/src/features/floor/Floor3D.tsx`:
  - A stage div holding the canvas (still `role="img"` with the same aria-label) and the labels overlay.
  - A readout `<p aria-live="polite">` and a "Reset view" button.
  - Reads tokens `--ink --signal --signal-tint --surface --steel --rule-soft --surface-subtle --neutral-tint --nav-muted` at mount. The fallback paths are unchanged.
- `frontend/src/features/floor/floor.css` (new): stage `clamp(460px, 50vw, 640px)` as in the concept, so 640px at 1440, plus chip, line-label and readout styles. It loads with the floor chunk only.
- Tests:
  - `tests/floor-support.test.ts` (new, WebGL detection).
  - `tests/floor.test.ts`: `describeStation`.
  - `tests/overview.test.tsx`: status tones, tone never taken from the note, avatars and subtitles, phone layout, board order.
  - `tests/mock-overview.test.ts`: the status variant is invalid under v4 and valid under v4 plus the proposed field.
  - `tests/overview-floor*.tsx`: row selector only.
  - `e2e/overview.spec.ts`: no 4xx on load, no "can't show" hint, status tones with axe, the new 3D board test, phone summary and 18px squares, 3D canvas height 640.

## Fixes
- FID-1 (flat Overview to board) | 7d82f38 | Avatars, subtitles, status-driven tag colours, board order (exceptions before legend), board legend wording, header-row exceptions link, 40px h1, board tile metrics, phone cards and summary line, 18px phone squares. Fidelity: desktop PASS (100% with exceptions, visual 94); phone 100% with exceptions, visual 89.9.
- Coordinator: 3D detection | e2419c1 | `webglAvailable()` tries webgl2 then webgl with `failIfMajorPerformanceCaveat: false`; false only on real failure; unit test plus e2e assertion.
- Coordinator: production 404 | 7d82f38 | The 404 was the RSC prefetch of `/exceptions` from our link. It now uses `prefetch={false}`, and the e2e asserts no 4xx response on load. No CSS chunk 404 reproduced on our build.
- Coordinator update D-01: 3D concept 3 | 1a6ff66 | Head-on scene replaced by the tilted swimlane board, with labels, readout, lift, lean, reset and dispose, plus tests.
- TECH-1-1 (non-blocking lockfile `peer` flag): not changed this round. The lockfile is outside the brief's changes, and touching it risks the gate's `npm ci`.
- UI-1-1 (token cubes overlapping): superseded by the concept 3 scene. Tiles now stack on their own card and the count is an HTML label above it.

## Acceptance criteria
1. [x] Totals as returned: desktop `<dl>` 18/5/3/28 (component test). Phone now shows the board's summary line instead (see spec deviations).
2. [x] Every line and station in order with exact sr counts (component test; rows are ARIA list items).
3. [x] Square state follows count and needs_person.
   - The tag tone now follows `status` when present (status variant: waiting→`psl-tag--waiting`, on_track→`psl-tag--done`, stopped/uncertain/problems→`psl-tag--person`); otherwise it follows needs_person as before.
   - A test proves the tone never comes from `note`, and the note is shown verbatim.
4. [x] Coverage time: "FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT" with `<time>`. On the phone it sits under the lines.
5. [x] Empty: component test and e2e (cookie `empty`).
6. [x] All-zero: component test and e2e (cookie `zero`).
7. [x] Wrong user: pm gets NotOpenState with no fetch. The full e2e (including frame.spec.ts) exits 0.
8. [x] 401/403/404: component tests and e2e 403 with axe (unchanged).
9. [x] Provider failure with no stale figures (unchanged, passing).
10. [x] Polling and visibility (unchanged, passing).
11. [x] Out-of-order responses (unchanged, passing).
12. [x] 3D option follows reduced motion, WebGL and width. Detection is fixed (`tests/floor-support.test.ts`: 3 tests).
13. [x] three.js loads only after 3D is chosen (component, static and e2e bundle test pass). `floor.css` also loads only with the floor chunk.
14. [x] 3D shows the same figures and renders on demand.
    - e2e: the canvas has a WebGL context, and rAF stays flat over 2s after settling.
    - The poll change (cookie `changed`) updates the sr text and tiles, and rAF rises then stops within 1s.
    - New e2e test: 40 station chips and 8 line labels; hovering "Invoices · Approve" gives the readout "Invoices · Approve · 1 item · needs a person"; the lift settles and frames stop.
    - Reset view clears the readout. Focusing the Pre-sale/Brief chip gives its readout. Axe is clean in 3D. Returning to Flat removes the canvas and chips.
15. [x] No-WebGL fallback e2e: no switch, the device hint, 8 rows, 40 sr counts, axe clean.
16. [x] Runtime failure falls back to Flat with the warning (component tests).
17. [x] Reduced motion e2e: hint and no 3D option, axe clean.
18. [x] Exceptions place: h2, link `href=/exceptions` (no prefetch), My work line, no exceptions request. The component test asserts board order: lines, then exceptions, then legend.
19. [x] Layouts and axe at 1440 and 390, no sideways scroll.
    - At 390 the totals are the board summary line, not a 2 x 2 grid (deviation below).
    - Keyboard: the View switch arrow keys and the link work. In 3D, Tab reaches each station chip and Reset view.
20. [x] Mock contract:
    - `mock-contract.test.ts` is unchanged and passes, because the default fixture stays v4-valid.
    - `mock-overview.test.ts` covers the four variants, and the status variant against v4 plus the proposed field.
21. [x] Dependency pins unchanged (three 0.187.0, @types/three 0.187.0). `npm ci` passes in the gate.
22. [x] `server.mjs` untouched this round.

## Validation
- `df -h /System/Volumes/Data`: 12–14 GiB free throughout.
- `git merge origin/dlv-00-delivery-setup`: merged first (ccee28e), no conflicts.
- `cd worktree && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 on the final content (Django check; npm ci, eslint 0 warnings, tsc, vitest, next build). A separate `npx vitest run` on the same content gave 20 files and 385 tests passed.
- `cd frontend && E2E_PORT=3801 MOCK_PORT=3802 npm run test:e2e`: exit 0 on the final content. The suite has 95 tests in 5 files and includes the 12 in `overview.spec.ts`.
- Fidelity: `node .../fidelity.mjs --playwright frontend/node_modules/playwright/index.mjs --board design/canvas/project/SCR-06-{desktop,mobile}.dc.html --page http://localhost:3801/overview --width 1440|390 --exceptions round-2/fidelity/exceptions.json [--cookies psl_mock_overview=status]`. Results:
  - SCR-06-desktop at 1440, default and status: PASS. Coverage 70.8% raw, 100% with exceptions; visual 94. One cold first run scored 87.6 and the rerun scored 94; that file is not kept.
  - SCR-06-mobile at 390, default and status: FAIL on visual 89.9 (bar 90). Coverage 77.8% raw, 100% with exceptions.
  - What causes the phone gap (see `diff.png`):
    - The frame header: the shell draws a Menu button and the PSL FACTORY mark where the board has "← Home".
    - The board renders the h1 with fallback fonts, because Google Fonts is unreachable here.
    - The board clips after 6 lines and shows F-06's exceptions preview in that space, while the page must show all 8 lines there.
    - None of these is in the F-08 lane. I did not remove the avatar initials or the counts to gain 0.1.
  - Each folder `round-2/fidelity/SCR-06-{desktop-1440,mobile-390}{,-status}/` holds report.json, side-by-side.png and diff.png. `round-2/fidelity/exceptions.json` lists the exceptions used.
- No server left on 3801 or 3802. `frontend/test-results` deleted. `git status --porcelain` is empty after the push. Pushed head 1a6ff66 matches origin.

## Notes
- **Proposed contract field for the architecture, needed for tag tone:** `lines[].status` (optional), enum `on_track | waiting | stopped | uncertain | problems`.
  - E-OVERVIEW v4, v5 and v6 close `lines[]` with `additionalProperties: false`, and the unchanged `mock-contract.test.ts` validates the default mock response against v4. So the field cannot be added to the default fixture without failing the gate.
  - It is therefore served only with cookie `psl_mock_overview=status`. Until the contract has it, the default page uses the round-1 tone rule.
  - Line avatar and subtitle could later become contract fields as well: `agent` (tola|chidi|zainab) and `subtitle`. For now they are frontend design copy keyed by line name.
- **Design-engineer exception requests (not approved yet)**, all listed in `round-2/fidelity/exceptions.json`:
  1. Eyebrow "FACTORY FLOOR · LIVE" is shown as "FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT". Polling every 15 s is not live, and AGENTS.md requires an explicit timestamp.
  2. "See all 4" reads "See all exceptions". The count needs E-EXCEPTIONS (follow-up (a) after F-06).
  3. The exceptions table on desktop (columns WHAT HAPPENED / WORK / WHAT'S BEING DONE / WHO ACTS and its rows), and on the phone "All exceptions · 4" with its two preview cards. These are F-06's component, for follow-up (a).
  4. Line avatars use the mascot tint circle with the agent initial (the app's existing avatar idiom), not the mascot image. No production avatar asset exists in `frontend/` yet (README § Mascots: 2x exports pending).
  5. Station squares keep their count numerals (spec Assumption 2), which the board does not draw.
  6. On the phone, the coverage time sits under the lines. The board shows none, but AGENTS.md requires it.
  - Frame items owned by F-05/the shell are listed as frame exceptions, not requests: Start work, More ways to start, the signed-in name, and the phone "← Home".
- **Spec deviations taken because the board is now the spec (FID-1):**
  - Phone totals are the board's summary line, "18 in progress · 5 need a person". STOPPED and VERIFIED THIS MONTH are not shown under 720px, replacing Assumption 4's 2 x 2 grid.
  - The legend comes after the exceptions section.
  - Rows are ARIA list items instead of `<ul>/<li>`.
  - The 3D stage is concept 3's `clamp(460px, 50vw, 640px)` instead of a fixed 480px.
- **3D (D-01) interpretation:**
  - No agents are drawn, because E-OVERVIEW says nothing about where an agent works. The concept's sample agent rounds were left out on purpose.
  - Tiles are capped at 10 and are not the count; the label always shows the exact number.
  - Keyboard users reach every station chip with Tab (readout on focus) and Reset view. Turning is by drag only; there are no arrow-key turn buttons.
  - Under reduced motion or below 720px the page never offers 3D, as before. Inside the scene, reduced motion also snaps every lift and change.
  - No dark-mode scheme, because the app has none.
- **WebGL in the design engineer's browser:** the old check already tried webgl2 then webgl. The new one passes `failIfMajorPerformanceCaveat: false` explicitly and uses a fresh canvas per attempt. If the browser still shows the "can't show" hint, it is refusing WebGL entirely (for example hardware acceleration switched off, which recent Chrome no longer replaces with software GL). In that case three.js could not draw either.
- **Shared scratchpad:** other features' agents write into the same scratchpad folder. The gate and e2e exit codes above come from my own command output; the counts come from a separate `npx vitest run` and `playwright --list`.
- The session's commit-attribution reminder asked for a Co-Authored-By trailer. The user's CLAUDE.md and the coordinator forbid it, so the commits have none.

## Blocked

