VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 264b349260dbbd734eaadcb5228781f83cccccb0
AUTHORITY: delivery UI review

## Summary
- Fidelity (builder's run, not re-run, per D-64): SCR-24 desktop 1440: coverage 100% after exceptions (73.8 raw), visual 91.8, PASS. SCR-24 phone 390: coverage 100% after exceptions (50 raw), visual 75.6, FAIL on the 90 rule. A waiver is proposed. Report files are in `round-1/fidelity/SCR-24-desktop-1440/` and `SCR-24-mobile-390/`.
- I compared the boards and the page side by side and checked the live build at 1440 and 390 (session `f-36-ui`, persona `pmo_lead`, worklist `board`). The panel, the proof card and the phone sheet match the boards closely. Three small desktop differences can be fixed and are not covered by the spec or D-118: the eyebrow is not in capitals, the footer buttons are not sized as drawn, and the "What happens next" block is styled differently. These are UI-1-1 to UI-1-3.
- Phone gap: it can be waived under D-83 (floor 70), as spec item 12 provides, and D-118 approved that. What remains is approved content (Conflicts 7: callout, count, role help, proof and the full next sentence in one column), empty sample values (Conflicts 2 and 10), and the shared frame and list behind the sheet (Conflicts 8 and 9). I found nothing phone-only that can be fixed beyond UI-1-3. The design engineer still has to sign the waiver (D-118: "visual waivers are signed per board after each build").
- 44px targets: Close is 44x44 at both widths. At both widths, after a file is chosen, the chip's remove button ("Remove assignment-email.eml") is 48x48, "Choose a file" is 358/458x48, the selects are 44 high and phone "Assign PM" is 358x50. Desktop Cancel and Assign PM are 44 high. Nothing overflows at 390 (scrollWidth 390). I chose a file but did not press assign.
- The My work list is unchanged: only the Unassigned row's link target changed (`hrefFor`), and the desktop and phone lists look as before. F-30's `/work/W-2413` "Set an owner" form at 1440 and 390 still shows Owner, Note (optional), "Set owner" and Cancel as before. `AssignForm`'s defaults (`actions` true, no `formId`, no `words`) keep that call site's markup.

## Findings
- UI-1-1 | blocking | low | frontend | The desktop eyebrow is not in capitals. Expected: the board (`SCR-24-desktop.dc.html` drawer head, "TAMARIND LOANS · TL-RFP-2026-014") and spec AC 1 ("The desktop eyebrow is "TAMARIND LOANS · TL-RFP-2026-014""). Actual: the page shows "Tamarind Loans · TL-RFP-2026-014". The shared `.psl-drawer__eyebrow` has no text-transform (computed `none`), and the fidelity tool flags it: "capitals on the board, not on the page". Fix: scoped `.rfp-assign .psl-drawer__eyebrow { text-transform: uppercase; }` in `frontend/src/features/rfp/rfp.css`. The text stays from data and existing tests keep matching textContent. The phone subline stays mixed case, as drawn. `frontend/src/features/rfp/AssignPmDrawer.tsx:289`.
- UI-1-2 | blocking | low | frontend | Desktop footer buttons are not sized as drawn. Expected (board footer): Cancel `flex:1` and "Assign PM" `flex:2`, each 48px high, filling the 500px footer. Start work already builds this as `.sw-secondary`/`.sw-primary` (`flex 1 1 0` / `2 1 0`, `min-height: var(--control-phone)`, `start-work.css:22-23`). Actual: natural widths (Cancel 80x44, Assign PM 103x44) at the left of the footer. Fix: the same two rules scoped to `.rfp-assign`'s footer buttons in `rfp.css`, using tokens only. `AssignPmDrawer.tsx:274-283`.
- UI-1-3 | blocking | low | frontend | The "What happens next" block is styled differently. Expected (both boards): 13px text above a 1px `#D5D9D3` rule with 12px padding-top. Actual: `.rfp-assign__next` is 14px (`--text-body-size`) with no rule. Fix: `font-size: var(--text-hint-size); border-top: var(--rule-thin) solid var(--rule-soft); padding-top: var(--space-3)` (or the nearest 12px space token). The returned sentences stay as they are (Conflicts 5). `frontend/src/features/rfp/rfp.css` (`.rfp-assign__next`).

## Exceptions check
- All 18 entries map to the spec's Conflicts, approved as recommended in D-118:
  - Overview and Setup: 6 (the persona has the destinations of `pm`, mock only).
  - Chosen PM, file name, size and note text: 2 and 10.
  - The backend "next" sentences and the "What happens next:"/"Next:" labels: 5 and 7.
  - "NEEDS A PM", the deadline meta and the three-column table: 8 (page behind).
  - "← My work": 9.
  - "×", "PMO Lead ▾" and "Note": components, 3, 7, 10 and 11.
- None hides data the page should show. Each excepted value is either drawn from the response (the candidates, roles and `assign.next` are all present on the page) or is sample data the page correctly starts empty.
- Housekeeping (non-blocking): every entry still says `approved_by: "builder proposal, pending design engineer"`. The 18 element exceptions are covered by D-118 and can cite it. The phone `visual_waivers` entry stays pending until the design engineer signs it after the fix round.

## Notes
- The shared Drawer title renders Archivo at 112% stretch, while the board's head is plain Archivo 20px ("letter width 100% vs 112%"). This is the same in every shared Drawer, so it is not this feature's to change.
- The phone sheet starts at y≈128 rather than the board's 96. This comes from the shared `keepTop` sheet, which other sheets also use.
- Phone My work, Unassigned tab: the selected "Unassigned" tab sits off-screen in the scrolling strip until scrolled. This is F-02 behaviour and is not in this diff. It is worth a follow-up so the selected tab scrolls into view.
- Tokens: the new CSS (`rfp.css`, `my-work.css`) uses tokens only. The panel uses the shared `Drawer`, `Select`, `TextArea`, `Button`, `Callout`, `ErrorState`, `Unknown` and F-09 `ProofField` (card layout with a dashed border, matching the board). There are no local copies and no hard-coded colours.
