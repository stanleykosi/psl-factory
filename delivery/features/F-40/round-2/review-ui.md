VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 1457df1c1d4ad44327640da4efcce7d5d85dc9cd
AUTHORITY: delivery UI review

## Findings
- UI-2-1 | blocking | low | frontend | The "Support replied" field is still not the board's single box. Desktop and 390 record boards draw one text line ("Femi Ojo · Support lead · 10 Apr 2027, 11:00"); the page draws a name/role input plus a separate native date-time picker (beside it at 1440, on its own row at 390). No exception covers the picker, and the round-2 waivers say the field "now follows the boards". Add an honest exception (a structured date-time is needed by the contract) and correct the waiver text, or merge into one field.
- UI-2-2 | non-blocking | low | frontend | The Proof card shows a remove "×" the board does not draw. Mention it under the F-18 Proof exception wording.

## Verified
- UI-1-1 | verified | Ready and Published chips are amber at 1440 (desktop and record side-by-sides) and at 390 (mobile-record), matching the boards.
- UI-1-2 | verified | Handover rows at 1440: label left, mono caps value right (NO · BELOW THE RULE'S THRESHOLD, ATTACHED), row rules; DRAFT is a chip as on the board.
- UI-1-3 | partial | The Record reply button is inside the card at 1440, and the hint and Proof label are hidden. The date-time split remains: see UI-2-1. The confirm tick is excepted (Conflicts 5).
- UI-1-4 | verified | At 390 the headings read "Support's reply" and the card is gone on the record screen.
- Remaining differences (crumbs, project tabs, Next panel, Tola section, intro footnote, gaps lines, Open question banner, Tamarind/Lagoon) each have their own exception. The eight visual waivers are pending the design engineer and do not block.
- Not run: fidelity tool (per instruction); I read the round-2 side-by-sides only.
