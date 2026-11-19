VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: b051cfa790dc4984060e6e236649aefb5c83e764
AUTHORITY: delivery UI review

## Summary
- Builder scores (not re-run): coverage 100% with exceptions, visual 74.2 to 87.7, all eight below 90. The eight waivers and 23 exceptions are pending the design engineer, which alone does not block.
- Frame, crumbs, Next panel and Tola section differences are honestly excepted (Conflicts 3, 6, 7, 8, 9, 11, 12).
- Several drawable differences are covered by no exception and the waiver text does not name them. They are fixable.

## Findings
- UI-1-1 | blocking | medium | frontend | State chip colour restyled. The boards draw "HANDOVER · READY TO PUBLISH" and "HANDOVER · PUBLISHED 08 APR" as an amber/yellow chip; the page draws them red (desktop and 390 side-by-sides, W-3701 and record). Use the board's chip token, or add an honest exception.
- UI-1-2 | blocking | medium | frontend | Handover section rows restyled. Board rows are plain label left, value right-aligned mono caps with row rules (Review needed? / NO · BELOW THE RULE'S THRESHOLD / ATTACHED / DRAFT). The page puts each value in a grey chip inline after the label. No exception covers table/row styling; match the board or record one.
- UI-1-3 | blocking | medium | frontend | Reply form field structure. Board has one "Support replied" field (name, role and date-time together), with the Record reply button inside the card at desktop. The page splits it into "Support replied" and "When they replied", adds a "One gap per line" hint, a "Proof" label, and a "I confirm this response is genuine" checkbox, and puts the intro as a footnote. Only the intro position (Conflicts 3) and gap lines (Conflicts 4) are excepted. Either match the board or add exceptions for the split field, the hint and the confirm checkbox (the checkbox may be spec-required; say so).
- UI-1-4 | blocking | medium | frontend | Phone screens drop the board's screen heading. The 390 boards title the screen "Handover acknowledged" and "Support's reply" (flagged only as a 20px vs 22px heading mismatch in the fidelity report); the page shows the project name as the heading, plus a wrapping card with its own "RECORD SUPPORT'S REPLY" caption on mobile-record where the board has no card. No exception covers this.
- UI-1-5 | non-blocking | low | frontend | The waiver text says the gap is "the shared frame" and "form position". It should also name findings 1 to 4 if they stay, so the design engineer signs what is actually different.

## Verified
- Exceptions contain no data value a mock could supply (names, dates, references are shown as returned); the Tamarind/Lagoon swap is covered by Conflicts 13.
- No horizontal overflow at 390 in the side-by-sides; Record reply sits in the pinned bar as specified.
- Colours, type and spacing of the frame match neighbouring F-22 screens. Contrast is readable.
- Not run: fidelity tool (per instruction), my own screenshots (relied on the builder's side-by-sides).
