VERDICT: PASS
REVIEWER: reviewer-ui
COMMIT: 48752f436c91d0f5f3ae640e7372a5cf7021095d
AUTHORITY: UI design reviewer (design-fidelity gate, D-83)

## Summary
- UI-1-1 to UI-1-5 and UI-1-7 are fixed; UI-1-6 is handled honestly in `fidelity-exceptions.json`. I read the builder's round-2 side-by-sides for all 4 boards and checked the phone flag order live at 390 on app 4853.
- Builder scores (72.0 / 79.5 / 69.1 / 74.0) match the reports and the side-by-sides; I did not re-run the tool. Coverage is 100% after exceptions on all four. None reaches 90.
- The remaining gaps are forced by approved decisions (D-111 conflicts 1, 4, 5, 7, 9, 10, 11, 13; D-99/D-110 frame; fixture counts). They need the design engineer's waivers. Mobile 69.1 is below the 70 floor and needs the one-board exception (F-23 SCR-28 precedent, 69.2). Both are correctly marked "pending design engineer" in the file.
- Document now on P-0101: crumb "Lagoon Health / Documents / SOW-0198", project bar "Lagoon Health", tab counts 4/6/6/9 agree with the board (6 documents).
- No sideways scroll at 390 (scrollWidth 390).

## Findings
None.

## Verified
- UI-1-1 | verified | The status tag is now outside the flex row (`DocumentReview.tsx`, `.docrev__status { align-self: flex-start }`). It sits on its own line under the title at the same place as the boards on desktop (default and returned) and on phone.
- UI-1-2 | verified | The returned agent note is `Callout kind="info"`: avatar, bold name inline, the backend's lines, the disabled "Ask Tola to draft v3" with "Not available yet". It is now a compact strip, not a headed panel. See Notes for two small styling differences (no 2px blue border, avatar centred on the strip) that match the shared work-item strip, so I do not block.
- UI-1-3 | verified | Desktop: the disabled "Edit as v3" is at natural width (about 88px, `align-self: flex-start`), with its reason beside it. Phone: it is in the pinned `psl-actionbar` at full width with "Not available yet" under it, as the board pins it. The grey look is the approved conflict 1 B.
- UI-1-4 | verified | Live at 390: the flag line is at y 826, the Checks panel at y 888. The flag is directly after the sections and before Checks. The inline note inside section 4 stays (the spec reads either way).
- UI-1-5 | verified | The aside is 333px (the board's width). The "TEST TEMPLATE v1 …" tag stays on one line. The "0 / 2000" counter is gone and the note is 3 rows. "YOUR REVIEW · PMO LEAD" begins about 40px lower than the board only because the page's Changes text wraps the header block lower; the review panel's own spacing matches. The 2000 limit is still checked on press.
- UI-1-6 | verified | The "Tola" frame exception is dropped. The "Tola · PMO agent I can draft v3 …" entry now cites conflict 1 (B) only (the backend's sentence and the disabled buttons). The other 9 entries are unchanged and each cites its approving conflict.
- UI-1-7 | verified | `document-review.css` uses `--space-20px` and `--text-lead-size`. No raw px, hex or inline style remain.
- UI-1-8 | verified | The `visual_waivers` reasons are updated to the round-2 measured scores (72.0 / 79.5 / 69.1 / 74.0) with the forced causes; mobile asks for the one-board floor exception. All four are marked "builder proposal, pending design engineer": these need the design engineer's signature before merge and are not a code change.

## Fidelity per board (builder's round-2 run, head 48752f43; copies in `round-2/fidelity/<board>-<width>/`)
| Board | Width | Coverage | With exceptions | Visual | Missing (all excepted) | Remaining differences (all forced) |
|---|---|---|---|---|---|---|
| SCR-08-desktop | 1440 | 86.4 | 100 | 72.0 | Overview, Setup, persona, Compare with v1, Drafted-by count sentence, "Sending to the client…" | shared frame (Alerts bell, PM persona; D-99, conflict 9), backend Changes text (5), Minutes cite (data), page ~100px taller |
| SCR-08-desktop-returned | 1440 | 96.4 | 100 | 79.5 | Compare v1 and v2 | sections below the banner (4), grey disabled held buttons (1), "17 Nov 14:20" (10), shared frame |
| SCR-08-mobile | 390 | 91.7 | 100 | 69.1 | ← Lagoon Health (accessible name), AMOUNTS MATCH COSTING | two-row tab bar (D-110), full title (8), Drafted-by line and Checks/Audience (7). Below the 70 floor: needs the one-board exception |
| SCR-08-mobile-returned | 390 | 81.8 | 100 | 74.0 | ← Lagoon Health, Tola's board sentence | sections below the banner (4), two-row tab bar, disabled Ask Tola in grey (1), shared phone bar |

No table/row pattern differences reported.

## Notes
- The info strip has no 2px blue border (the board draws one) and the avatar is vertically centred while the text is left-aligned beside the "Ask Tola" button text. This is the shared `Callout`/work-item strip. If the design engineer wants it closer, it is a shared-component change, not a F-29 one.
- Taste: the "Ask Tola to draft v3" text button is slightly indented from the strip's text.
