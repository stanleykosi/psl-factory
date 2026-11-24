VERDICT: PASS
COMMIT: ca44c3775de717cd923cfa569ad85c68460bc85f
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- The phone bar CSS is scoped to `.retro__savebar`, `.retro__page` and `.retro__decisions`, which are used only in `RetroForm.tsx`. Desktop, the follow-up form and the other boards are not affected, and no ancestor of the retro page sets `transform`, `filter`, `contain` or `will-change`, so `position: fixed` holds.
- Save is still a `type="submit"` button inside the same `<form>`, so the same `onSubmit` handler runs. Only its DOM position changed.
- The desktop `order` trick works (the form is a flex column). It gives the right screen order, but changes keyboard focus order: Decisions now comes before Save in Tab order. Non-blocking, see TECH-4-1.
- The tightened e2e assertions are stronger than the round 3 ones (width, x, bottom edge at scroll 0 and at end, last field and message clearance). None is weakened. The builder's local run is the only e2e evidence; the GitHub gate does not run e2e.

## Findings
- TECH-4-1 | non-blocking | medium | frontend | Desktop Tab order now differs from screen order. The Decisions block is before the Save row in the DOM (`RetroForm.tsx:154` and `:193`), but on desktop Save is shown above Decisions (`retrospective.css:61-62`). A keyboard user going from Notes file reaches Decision 1 and Add a decision before Save, though Save is visually directly under the notes file. Nothing is unreachable or trapped, so this is a WCAG 2.4.3 watch item, not a blocking breach. Any DOM order fixes one viewport and breaks the other, because the phone bar is last in DOM. Product/UX should decide whether the board's desktop order or the Tab order wins; the builder's note records the same trade-off.
- TECH-4-2 | non-blocking | low | frontend | `.retro__page { padding-bottom: 140px }` (`retrospective.css:51`) is a fixed allowance, not measured against the bar. When Save is disabled, `.psl-reason` (`Button.tsx:119-120`) sits inside the bar. The longest retro reason is about 90 characters, which wraps to two lines at 390px. That keeps the bar near 130-136px, just inside 140px. A longer reason would let the bar cover the last field at scroll end. Consider 160px or a measured spacer.

## Verified
- UI-3-1 | verified | Technical side. Read the CSS: `position: fixed; left: 0; right: 0; bottom: 0; margin: 0` only in the `max-width: 719.98px` query. Desktop is unchanged (`order` only, which is inert for a non-flex element). No other shared class is touched. Full-width fixed bars match the existing pattern (`work-phonebar`, `alerts-footer`, `rfp-pin`).
- UX-3-1 | verified | Pinned at any scroll: the bar is viewport-fixed and the e2e test checks its bottom edge at scroll 0 and at scroll end. Read, not run.
- UI-3-2 | verified | The bar is the last child of the form on phone, after the Decisions block (DOM check in `e2e/retrospective.spec.ts:374-375`). Padding and the 140px allowance keep the last field and the 422 message clear (`e2e/retrospective.spec.ts:386-397`).

## Notes
- The e2e assertions are real. The old assertions (bottom within 80px, width above 300) were loose. The new ones use +-1px tolerances against a 390x844 viewport set in `test.use`, and the final message check is a top-edge check after scroll. The `form:has(.retro__savebar)` selector matches only the retro form.
- I did not run any test, server or build (single-file, no-server rule). Evidence used: the builder's local run (25 of 25, `build.md`), the GitHub frontend gate on this head (`checks.md`: PASS, run 45416986512), and reading the code.
- I did not look at the `DemoBar` fixed position (bottom right, same z-index) on phone. It is a demo control, not part of this round's change.
