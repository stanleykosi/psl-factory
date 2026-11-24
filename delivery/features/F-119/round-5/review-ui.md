VERDICT: PASS
COMMIT: 53c24b19059ece9c6d4e8a9bf3eb086a7cba1405
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (round 5, static review of the diff, CSS and components; no server started, fidelity not re-run under D-202)

## Summary
- Desktop Save sits where SCR-33-desktop draws it: `RetroForm.tsx:204` renders `saveBar` after the notes file select and its warning Callout, before the Decisions block. The `order` rules are gone and the desktop DOM order matches the board.
- Desktop Save is the board's 300 by 50 blue button: `.retro__actions .retro__save { width: 100%; max-width: 300px }` (`retrospective.css:41`), `psl-btn` primary on `--action` (#2459D6, `tokens.css:17`), `size="lg"` with `--control-lg` 50px.
- Phone bar matches SCR-33-mobile: `.retro__savebar` (`retrospective.css:52`) is fixed, left 0, right 0, bottom 0, white `--surface`, 2px `--rule-strong` top rule in `--ink`, padding `--space-3 --space-4 --space-18px` (12/16/18), gap 8px, full-width Save. The board uses the same values (`padding: 12px 16px 18px`, `border-top: 2px solid #1F2427`, `gap: 8px`).
- Phone and desktop switch at the same breakpoint: `usePhone()` uses `(max-width: 719.98px)` (`components/internal.ts`), the CSS media query is `max-width: 719.98px`. No band where the DOM order and the CSS disagree.
- Round 5's `html:has(.retro__savebar) { scroll-padding-bottom: 110px }` is inside the phone media block only and sits above the 82px bar height (2px border, 12px, 50px button, 18px).

## Findings
None.

## Verified
- UX-4-1 | not in UI lens | Scroll padding is phone-only and scoped by `:has`; no visual change to the board's layout. Noted only.
- UX-4-2 | verified | Save is rendered once: `RetroForm.tsx:204` is `phone ? <>{decisions}{saveBar}</> : <>{saveBar}{decisions}</>`. Desktop Save precedes Decisions, phone Save follows Decisions as the fixed bar. Tokens and class names checked against the board values above.

## Notes
- Hydration order: the app is Next.js 16 and `useIsPhone()` returns false on the server. Before hydration a phone browser holds the desktop DOM order (Save before Decisions), then reorders after hydration. The bar is fixed, so the visible result is the same, but the tab order changes once. Non-blocking.
- Crossing 720px while a control has focus re-mounts the swapped subtrees because the two branches are unkeyed fragments. Focus can be lost on a rotate or resize, and typed values are kept because the draft lives in `RetroForm` state. Non-blocking; a keyed render or a single DOM order with CSS placement would avoid it.
- Board's desktop "Save draft" is not rendered. This is the approved exception in `fidelity-exceptions.json` (D-8, no draft exists), so it is not a finding.
- Fixed-bar edge to edge depends on no transform, filter, contain or will-change on ancestors. Round 5 does not change ancestors, and the round 3 check still holds.
