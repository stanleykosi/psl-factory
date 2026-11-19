VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 8a9755d4f598464231786ff2100fd420a93b31a4
AUTHORITY: delivery UI review

## Findings
Method: builder's fidelity output read (not re-run): desktop 1440 coverage 100 with exceptions, visual 90.8; phone 390 coverage 100 with exceptions, visual 87.8 (above the spec floor of 70). Side-by-side images read for both widths.

- UI-1 (blocking, phone 390): the pose card is drawn smaller than the board. Board card is about 177 px high with the figure filling it; built card is about 133 px with a figure about 25% smaller. Fix the size to match the board, or record an exception that gives a real reason.
- UI-2 (blocking, phone 390): differences from the board with no exception of their own. The board draws none of these, the page does: the "Zainab" avatar beside the name, the "1 STEP · DONE" checklist card, the separate red `cannot_reason` line, the "Restricted" chip, the bell, the "Message Zainab" composer with "@ Mention", and the tighter pose-to-name spacing. The spec keeps the checklist, reason and chip, but the exceptions file has no entry for any of them. Add one honest exception each (name the spec line) or match the board.
- UI-3 (blocking, desktop 1440): the board's source tag is "ACCESS · payroll (restricted)". The page shows a dashed lock "Restricted" chip and a red reason line, which the board does not draw. The label exception covers only the missing label, not the extra red line or the chip styling. Add an entry for each, or match the board.
- UI-4 (note): the builder proposals still pending the design engineer (Payroll header, two phone buttons, one-paragraph wording, restricted label, list pattern) do not block. The phone tool result is FAIL on its default 90 (87.8). The spec floor is 70, and a waiver is the design engineer's.
- UI-5 (note): the desktop 1440 side panel and the cant pose match the board (pose, sentence, Project, Your access, agents note). The desktop "Attach", shortcut and header differences are covered by D-100 exceptions.

## Verified
- Desktop side panel and "can't" pose at 1440 match the board.
- No draft card, start button or suggestion buttons on the thread.
- Not done: no live browser session was run, and the tool was not re-run, as instructed.
