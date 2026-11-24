VERDICT: CHANGES
COMMIT: 06d07376b02424f191502441b6f29635848c88d5
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer

## Summary
- UI-2-1 (phone Save as a bottom bar) is not closed. The bar is sticky and white with the 2px top rule, but it sits inside the form's 2px bordered Panel, so the panel frame wraps it. It spans the panel's inner width (about 354px of the 390px screen by the CSS; the builder's 322px estimate is lower), not the screen. The board's bar is edge to edge.
- The gap is fixable in frontend code. It is not a close-enough case: the bar is the element UI-2-1 asks for, and the board draws it as the screen's foot.
- A second issue comes from the same CSS. The bar is placed before the Decisions block inside the form, so while the user scrolls the form the sticky bar covers the Decisions fields. The builder's note that the bar sits "at the end of the form" is not accurate.
- UI-2-2 is closed by D-202: fidelity-exceptions.json holds 28 exceptions and 2 visual waivers, all approved by the design engineer. The fidelity tool was not re-run.
- Desktop placement is unchanged (the save rule outside the 719.98px media query is untouched). No phone server was started, and no PIDs were recorded.

## Findings
- UI-3-1 | blocking | medium | frontend | Phone Save bar is inside the Panel frame and is not screen-width. Expected (SCR-33-mobile.dc.html, bottom element of the 390 screen): a white bar, edge to edge, 2px top rule, padding 12/16/18, with Save full width at the foot of the screen. Actual: `RetroForm.tsx:153` puts `.retro__savebar` inside the form, and the form sits in `Panel` (`RetrospectiveView.tsx:142`, `.psl-panel` 2px border, `.psl-panel__body` padding 14px). The bar's negative margin of 14px (`retrospective.css:49`) only reaches the panel's inner edge, so the panel border frames the bar and the bar is about 354px wide, not 390px. Fix: on phone, make the bar span the screen (for example a margin of -32px to the screen edges, with the panel's border and the body padding not wrapping it, or take Save out of the Panel on phone), and move the `retro__savebar` row after the Decisions block (`RetroForm.tsx:159-196`) so the bar is the last thing in the form and does not cover Decisions while scrolling. The e2e assertion (width > 300) does not catch the width; add a check that the bar's width is about the viewport width and that its left edge is at 0.
- UI-3-2 | non-blocking | low | frontend | The builder's note says the bar "never hides the last field" because it "sits in the flow at the end of the form". Decisions follow it in the DOM (`RetroForm.tsx:159`), so the sticky bar overlays Decisions fields while they are scrolled past. The same fix as UI-3-1 (move the row after Decisions) removes this; if it is kept, add scroll-padding so a focused field is not left under the bar.

## Verified
- UI-2-1 | reopen | The bar is sticky, white, with a 2px top rule and the board's padding and gap (retrospective.css:49), but it is inside the framed Panel and is not screen width (see UI-3-1). The builder's test only asserts `width > 300` and bottom-of-screen placement (frontend/e2e/retrospective.spec.ts, phone 390 save bar), so it does not catch the frame or the width.
- UI-2-2 | verified | fidelity-exceptions.json holds 28 `exceptions` and 2 `visual_waivers`, every entry approved_by "design engineer (hunchoweb)" under D-202 (visual waivers D-83 at 1440 and 390). Closed for this round; the tool was not re-run.
- Checks: checks.md GATE PASS on 06d07376 (GitHub frontend-checks run 45413135825, incl. lint, typecheck, unit tests and build). This is a CSS-only lens check; the phone render was not captured.

## Notes
- The builder's 322px width estimate and the CSS arithmetic (about 354px) disagree. Either way the bar does not reach the screen edges, so the finding stands; a rendered measurement at 390 would settle the exact number.
- Taste only: the bar's sticky behaviour overlaps the form's content when the form is taller than the screen, which is the intent of a bottom bar; after UI-3-1 it should only overlay Decisions if they stay above the bar.
