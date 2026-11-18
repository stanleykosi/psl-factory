STATUS: READY
COMMIT: 83747e368e5af5b4680839ede43bd485d8744414
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the UI-1-1 to UI-1-9 blocking findings, TECH-1-1, UX-1-1 and the cheap non-blocking ones (UI-1-11, UI-1-12, UI-1-13). UI-1-10 (status tag tone) is left for the design engineer. Contract mock only, as in round 1.
- Fidelity (one run, round-2/fidelity/, after all fixes, frozen only after uploads finished): coverage 100% after exceptions on all 8; visual 72.2 to 85.5, all at or above the 70 floor, so no floor exception is asked.
- Exceptions file: 45 exceptions (count in round 1 build.md said 44), 8 per-board waivers naming each board's own gaps.

## Fixes
- UI-1-1 | 83747e3 | `workspace.css`: the green Decide-panel button rule now has `:not([aria-disabled="true"])`, so a disabled primary ("Prepare readiness", F-29's "Ask Tola") keeps the grey disabled look.
- UI-1-2 | 83747e3 | phone: `.ws-form--bare` has no border or padding (Confirm PM sits in the panel's own padding).
- UI-1-3 | 83747e3 | `Sections.tsx`: text plus amount is one string ("Costing v2 · ₦40,951,000.00"; "· Unknown" when the amount is unknown), so the stacked cell does not split. Unit test kept ("Costing v2 · Unknown").
- UI-1-4 | 83747e3 | `ResponseDrawer.tsx` and CSS: F-18's form is drawn in its one-column variant, no page box, its Record bar pinned at the bottom of the Drawer (sticky on desktop, F-18's fixed bar on a phone); Cancel is in the shared Drawer `footer` slot on desktop (existing slot, no change to Drawer). On a phone Cancel is dropped (the sheet has Close and Escape), as the board draws one button.
- UI-1-5 | 83747e3 | Drawer segments and file button are `--control-phone` high.
- UI-1-6 | 83747e3 | CSS only, scoped to Drawers and the engagement line: a form in a Drawer has no second box, its heading is visually hidden (still names the form), actions sit at the bottom of the sheet; on desktop the Decide panel is hidden while the Register form is open, so the consequence and button show once. SCR-41-mobile-register is now 77.7 (was 69.8); no floor exception.
- UI-1-7 | 83747e3 | `round-2/fidelity/drive-states.mjs` waits for the upload to finish before freezing; the 4 frozen boards are re-driven.
- UI-1-8 | 83747e3 | the Drawer eyebrow is `workspace.context.project.title` from the response; exception 43 is now a `sample data` entry for the project name only; entry 24 (phone finding sentence) is category `frame`. Count fixed to 45.
- TECH-1-1 | 83747e3 | `Workspace.tsx`: the "Recorded under your name" notice is set only after the re-read returns an item. Test: a failed re-read leaves no such text.
- UX-1-1 | 83747e3 | `ResponseDrawer.tsx`: when a re-read no longer lists the team the person chose, the Drawer closes and the page says "<Team> is no longer waiting. We've reloaded this item so you can see whether it was recorded." Test: lost reply with the team gone.
- UI-1-9 | 83747e3 | planning line CSS: estimate cells do not wrap, department names are bold. The row actions stay the shared outlined item-step Button (D-91) and are named in the SCR-42 waivers for the design engineer.
- UI-1-11 | 83747e3 | the shared-renderer differences are named in each waiver.
- UI-1-12 | 83747e3 | one waiver per board with that board's own gaps and its round-2 score.
- UI-1-13 | 83747e3 | on a phone the engagement line's cited links are 48px tall targets.
- Not changed: UI-1-10 (tag tone is the fixture's, design engineer to choose); TECH-1-2 to TECH-1-4 and UX-1-2..1-5 non-blocking, UX-1-2 is fixed by UI-1-1.

## Changes
Files: `frontend/src/features/workspace/{ResponseDrawer.tsx,Workspace.tsx,Sections.tsx,workspace.css}`, `frontend/tests/engagement-planning.test.tsx` (47 tests; 3 added), `frontend/e2e/engagement-planning.spec.ts` (phone closes the Drawer with Close). Shared files: only the CSS rule `:not([aria-disabled])`, the phone `.ws-form--bare` rule, the Sections text-plus-amount string and Drawer-scoped form CSS; every other line identical. Fidelity files and `fidelity-exceptions.json` in the main project folder.

## Fidelity (production build, app 4861, mock 4860; frozen boards served on 4860 after the mock was stopped)
| board | width | coverage | with exceptions | visual |
|---|---|---|---|---|
| SCR-41-desktop | 1440 | 77.3 | 100 | 81.9 |
| SCR-41-mobile | 390 | 60 | 100 | 79.2 |
| SCR-42-desktop | 1440 | 73.2 | 100 | 74.3 |
| SCR-42-mobile | 390 | 42.9 | 100 | 79.5 |
| SCR-41-desktop-register | 1440 | 81.5 | 100 | 80.1 |
| SCR-41-mobile-register | 390 | 66.7 | 100 | 77.7 |
| SCR-42-desktop-record | 1440 | 70.3 | 100 | 85.5 |
| SCR-42-mobile-record | 390 | 64.7 | 100 | 72.2 |
Before this scored run I ran the tool on the boards three times to size the fixes (discovery, logs in the same folder were overwritten); `scores.txt` is the final run. All 8 are under 90, so 8 waivers stay proposed for the design engineer (D-83).

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` under the lock (load below 14): exit 0 (lint, typecheck, tests, production build).
- Targeted vitest (workspace, work-item, minutes, issue-detail, weekly, response, rfp, mock-contract, engagement, projects, project-tabs, decide): 1162 passed before the last CSS-only edits; `engagement-planning.test.tsx` 47 passed after.
- e2e: `E2E_PORT=4861 MOCK_PORT=4860 npx playwright test` over engagement-planning, workspace, work-item, issue-detail, project-tabs, response, rfp, minutes, weekly: 235 passed.
- Servers stopped by PID; `frontend/test-results` deleted.
