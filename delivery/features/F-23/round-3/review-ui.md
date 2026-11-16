VERDICT: PASS
COMMIT: a3f43067bf20e8474e3a6bb54d273597154d6f28
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- UI-2-1 is fixed. Due is a date column again, it reads "13 Nov" / "15 Nov" as the board does, and the unknown due is `{unknown: true}` drawn as the design system's amber Unknown.
- The DRAFTED tags and the "Drafted" status are now the agent (blue) tag at 1440 and 390, as the boards draw them. I checked this on a rebuilt head.
- D-104's condition holds for SCR-28-desktop at 69.1. No gap F-23 can fix remains on that board; everything left is the approved shared frame or an open design-engineer choice.
- The DRAFTED change moves only the colour of two 70×23 tags on each drafted and review board. Size and layout are unchanged, so the round-2 scores stand.

## Findings
None.

## Verified
- UI-2-1 | verified | Round-3 SCR-28-desktop side-by-side shows Due "13 Nov", "15 Nov" and an amber Unknown pill (`psl-unknown`, waiting tint) on A-3. The fixture has `date` cells with `{unknown: true}`. `Sections.tsx` `DateText` shortens the date only when `columns[].date_format: "day_month"` is set and the date is known, so an unknown still reads Unknown (INV-UNKNOWN). Without the option, other lines keep the full date. Single-board rescore: desktop 69.1, phone 74.2. The phone row reads "13 Nov" and an amber Unknown.
- UI-2-2 | verified | Rebuilt head on 4769 with the mock on 4768, W-2303 and W-2304 at 1440 and 390. The row tag "DRAFTED" and the W-2303 status "Drafted" are `psl-tag psl-tag--agent`: background rgb(233, 238, 251), ink rgb(22, 56, 143), 70×23 / 71×23. That matches the boards' blue tag. `agent` is a contract tone, mapped through `labels.ts` TONE, so no hard-coded colour was added.
- UI-2-3 | carried | the phone row spacing is frame (Conflicts 10). It is non-blocking and unchanged.
- UI-1-6 | carried | the colour of Tola's third sentence is still the design engineer's choice. The spec puts it in `agent_note`.

## D-104 judgement (SCR-28-desktop at 69.1)
The only change since round 2 is the Due cell: "13 Nov" in place of "13 Nov 2026" and an amber pill in place of plain text. That accounts for the 0.1 move from 69.2. What still differs from the board, and why each is not a gap F-23 can fix:
- **Agent note:** a full-width band where the board has a side card. Frame.
- **Columns:** Meeting and Decisions swap columns. Conflicts 6, frame layout (D-62).
- **Confirm controls:**
  - The Decide panel's green button is followed by the opened confirm form (D-69, D-98 items 1 and 2).
  - Edit and Remove are buttons where the board has links.
  - The audience and owner are not inline (D-98 item 2).
- **Header:**
  - The fallback "ACTION NEEDED" tag.
  - The crumbs are plain text. This is a frame item, its exception is pending signature, and it is the same on F-21 and F-22.
- **Cites:** uppercase mono where the board has sans. This is the frame's `.ws-cite` style, listed in the reworded exceptions 5 to 8.
- **Tola's third sentence:** blue, where the board has amber (UI-1-6). The spec sets this. It is open for the design engineer and is not a builder gap.

So the "no fixable gap" condition holds, and the one-board exception can be signed. If the design engineer chooses amber for UI-1-6, that is a fixture-only change and will not lower the score.

## Waivers (one line per board)
| Board | Width | Visual | Waiver |
|---|---|---|---|
| SCR-28-desktop | 1440 | 69.1 | D-104 one-board exception to the 70 floor; condition met (no fixable gap); the waiver text carries 69.1. |
| SCR-28-desktop-suggesting | 1440 | 81.3 | Waiver OK (D-83); not touched this round. |
| SCR-28-desktop-drafted | 1440 | 85.4 | Waiver OK. Only the two DRAFTED tags' colour changed, now closer to the board. |
| SCR-28-desktop-review | 1440 | 78.7 | Waiver OK. Only the DRAFTED tag colour changed. |
| SCR-28-mobile | 390 | 74.2 | Waiver OK. |
| SCR-28-mobile-suggesting | 390 | 82 | Waiver OK. |
| SCR-28-mobile-drafted | 390 | 82.5 | Waiver OK. Only the tag colour changed. |
| SCR-28-mobile-review | 390 | 78.7 | Waiver OK. Only the tag colour changed. |

All waivers and 30 exceptions are still "builder proposal, pending design engineer" and need the design engineer's signature.

## Notes
- Code lens for round 3:
  - `columnDayMonth` is a typed proposal reader beside the others in `proposals.ts`, and it uses the shared `formatDayMonth` from `@/components`.
  - There is no new CSS and no hard-coded colour.
- The dlv-00 merge (7abfbcb9..a3f43067) has no frontend diff.
- Housekeeping: both servers on 4768/4769 were stopped by PID and port, and the test-results folder was removed. My screenshots are in the session scratchpad only.
