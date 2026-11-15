VERDICT: CHANGES
COMMIT: ab641e93900ddddcaeaa19d323f33fa9045ef9d0
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (round 2, design-fidelity gate)

## Summary
- The fidelity gate passes on three boards: SCR-22-desktop (All tab), SCR-22-mobile and SCR-07-desktop. SCR-07-mobile has 100% coverage and a visual score of 68. D-08 accepts that score, because the page carries its own back link below the bar.
- From reading the side-by-side images, the list and project page now follow the boards. That covers the tabs with counts, search and Filter, the six columns, the phone cards with the red attention line, the breadcrumb, the six-tab bar, the facts strip, the journey box with status squares and tags, and Tola's panel.
- One blocking difference: on phones the Filter icon button draws a 4px frame where the board has 2px. The bundle's inset ring and the page's own border are both applied (`projects.css:97`).
- No horizontal scroll at 390 or 1440 on 14 captured states. The projects CSS has no hard-coded colours.
- The other differences are covered by approved exceptions or decisions (D-08, D-09, D-10, the frame items), or are spec-required additions (paging footer, "What is next").

## Findings
- UI-2-1 | blocking | low | frontend | The phone Filter icon button on SCR-22-mobile has a doubled frame. Expected (board): a 44px white button with a 2px ink frame, the same weight as the search box beside it. Actual: `psl-iconbtn` already draws a 2px ink ring (`box-shadow: inset 0 0 0 2px`), and `.projects__iconbtn` adds `border: 2px solid var(--ink)`. The frame reads as 4px and heavier than the search box. Computed at 390: `border: 2px solid rgb(31,36,39)` plus `box-shadow: rgb(31,36,39) 0 0 0 2px inset`. Fix: drop the border from `.projects__iconbtn`, and use the bundle class's ring as it is. `frontend/src/features/projects/projects.css:97`; see fidelity-review/SCR-22-mobile-390/side-by-side.png.
- UI-2-2 | non-blocking | low | frontend | The SCR-22 desktop title "Projects" is 36px; the board draws it at 40px (the tool flags "text size 40px on the board, 36px on the page"). The cause is the frame-wide `.shell-title` (36px, `frontend/src/styles/shell.css:33`). My work (SCR-01, also 40px on its board) has had the same gap since F-02, so this is a frame follow-up, not this lane's work. Boards vary from 28 to 40px, so the frame needs a size option instead of a per-page override.

## Verified
- FID-1 | verified | The gate was re-run at head ab641e9 against the shared production build on :3711, with the mock on :3712, persona pm and `--exceptions fidelity-exceptions.json`:
  - SCR-22-desktop on `/projects?status=all` at 1440: coverage 95.7% (100% with exceptions), visual 92.1. PASS.
  - SCR-22-desktop on `/projects` (Active) at 1440: coverage 91.5% with exceptions, visual 89.1. FAIL, but only because the closed Sabi Market row is missing, which D-09 approves. It is kept for the record.
  - SCR-22-mobile on `/projects` at 390: coverage 88.9% (100% with exceptions), visual 91.6. PASS.
  - SCR-07-desktop on `/projects/P-0101` at 1440, with the cookie scoped to `/`: coverage 95.7% (100% with exceptions), visual 91.1. PASS.
  - SCR-07-desktop with the tool's default cookie path: visual 84.3. The page renders as Ada Okafor with Overview and Setup in the bar, so this is a tool artefact. It is kept as `-pathcookie`.
  - SCR-07-mobile at 390: coverage 100%, visual 68. FAIL, accepted by D-08 only. The whole page sits about 56px lower because of the in-page "← Projects" link. The only style difference the tool reports is that link's colour and underline, which follows from the same decision.
  - Missing items after exceptions: none. Moved items: the breadcrumb (+1 to 2px) and "Plan a project" (+10px, from row height). Both are sub-visual.

## Notes
- Approved differences seen in the side-by-sides, and not findings:
  - Start work and More ways to start are missing from the bar (frame, F-05).
  - "← Home" and "← Projects" are not in the phone bar (D-08).
  - Active shows 4 rows and "4 PROJECTS" (D-09).
  - Invoice · Milestone 2 reads WAITING with a white square instead of "AWAITING FINANCE DECISION" with a red square (D-10).
  - There are no visible tags on the phone journey (D-10).
  - The rows-per-page footer and the "What is next" row are additions the spec requires.
- Taste:
  - Tola's avatar is the shared initial-letter avatar (`avatarClass`, as on the work item page). The board has a portrait image whose blob does not resolve in the render. The initial avatar is consistent with the neighbouring screen.
  - The list tabs are about 6px wider each than on the board. This is not visible at a glance.
  - `projects.css` uses literal px for some font sizes and gaps (12/13/15px, 14px, 20px, 22px) where the boards give those values. It has no hard-coded colours. Every colour is a `var(--…)` token.
- At 390 and 1440, document width equals viewport width on 14 captured states: list, Closed, no results, journey, Milestones tab, empty P-0105, and no-access P-0104.

## Method (not part of the verdict)
- Fidelity: `node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs` with the worktree's Playwright, `--cookies psl_mock_persona=pm` and `--exceptions /Users/Hunchoo/psl-factory/delivery/features/F-07/fidelity-exceptions.json`.
- For the root-path cookie, a scratchpad Playwright shim rewrote the URL-scoped cookie to `path=/`. The tool itself was not changed.
- Evidence (report.json and side-by-side.png) is in `delivery/features/F-07/round-2/fidelity-review/<board>-<width>[-variant]/`.
- I used the shared servers on :3711 and :3712 for viewing only. I did not start or stop any server and did not run a dev server (disk rule). Computed styles were read with Playwright.
- Scratch screenshots are left in the session scratchpad only.
