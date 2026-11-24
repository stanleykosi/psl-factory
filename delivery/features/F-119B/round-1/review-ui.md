VERDICT: PASS
COMMIT: 9d9b149c0eee33789567d9006229314f1224d6d0
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (F-119B round 1; static review of the diff since 53c24b19, CSS and components; no server started, fidelity tool not re-run under D-202 per the brief)

## Summary
- The only change since the F-119 round 5 pass (53c24b19) is 9d9b149c: a phone-only `onFocus` handler on the form, a `ResizeObserver` that writes the bar's measured height into `--retro-bar`, and the scroll and padding values that read it. No colour, type, radius, surface or bar box rule changed.
- Phone bar still matches SCR-33-mobile: `.retro__savebar` (`retrospective.css:52`) is fixed to the viewport edges, `--surface` white, 2px `--rule-strong` top rule in `--ink`, padding `--space-3 --space-4 --space-18px` (12/16/18), gap `--space-2`, full-width primary Save.
- Desktop Save still matches SCR-33-desktop: `.retro__actions .retro__save { width: 100%; max-width: 300px }` (`retrospective.css:46`), `size="lg"`, rendered once before Decisions (`RetroForm.tsx:230`, `phone ? decisions+saveBar : saveBar+decisions`).
- The new `--retro-bar` variable is set only while the phone bar is mounted and removed on cleanup. Its fallback (110px) applies only before the first measure. Desktop never sets it, and the `.retro__page` and `html:has(...)` rules sit inside the 719.98px media block, so desktop layout is unchanged.
- No new hard-coded colours or one-off tokens. The new values reuse existing spacing and z tokens, and the `calc()` only adds 32px and 16px of clearance to the measured height.

## Findings
None.

## Verified
- Round 1 of F-119B: no prior UI findings in this feature's lens to retest. UI-1-1 to UI-3-x and UX-4-x were verified in F-119 rounds 2 to 6; the UX-5-1 fix (criterion 24) is a focus-scroll behaviour and is covered by the phone focus test, which is a functional check outside this UI lens.

## Notes
- Carried from F-119 round 5, still non-blocking: before hydration `useIsPhone()` is false, so a phone browser briefly holds the desktop DOM order (Save before Decisions) and then reorders. The fixed bar hides the visible effect, but the tab order changes once.
- Carried, TECH-5-3 (open, non-blocking): crossing 720px while a control has focus remounts the unkeyed phone and desktop fragments (`RetroForm.tsx:230`). Focus can be lost on rotate or resize; typed values survive in `draft`. A keyed render or one DOM order with CSS placement would remove it.
- Fidelity: the 28 exceptions and 2 D-83 waivers for SCR-33 (desktop 78.8, phone 76.6) are signed under D-202 and copied to `delivery/features/F-119B/fidelity-exceptions.json`. The desktop "Save draft" absence is one of those approved exceptions, not a finding.
