VERDICT: PASS
COMMIT: 1407fbe72551058290b2303a86580eef05b945c2
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Re-walked the weekly start on the mock (persona pm) at 1440 and 390: the form, a valid week (16 to 22 Nov) and the two refusals. A valid week starts and lands on /work/4102 at both widths.
- Picking today as the last day (18 to 24 Nov) is refused with "Selected reporting period must have ended; future progress is unknown". It shows as a callout above the form, with the values kept and the button back to "Start report".
- A period of 13 days (10 to 22 Nov) is refused with "Select a positive weekly reporting window of at most eight days; this is not a configured publication cadence". Same place, same behaviour. Phone shows a sheet with no horizontal break.
- The words are server text and understandable to a PMO person. Only "this is not a configured publication cadence" is jargon, and it is low. The end-day and timezone choice is LC-Q32, not a finding.
- Earlier lows kept open.

## Findings
- UX-2-1 | non-blocking | low | frontend | The two period refusals show the server's sentence unchanged. The 8-day one ends "this is not a configured publication cadence", which means little to a PMO person. A shorter line such as "Pick a week of at most 8 days" would do. Neither message is tied to the Week field. frontend/src/features/start-work/useStart.ts (notice for action_unavailable).
- UX-1-1 | non-blocking | low | frontend | Carried forward, not rechecked this round: the 403 callout repeats the app sentence and the server sentence. frontend/src/features/start-work/LineForm.tsx.
- UX-1-2 | non-blocking | low | frontend | Carried forward: unavailable cards all say the same "Not available here yet." until the backend gives a reason per line (LC-Q3). frontend/src/features/start-work/LineChooser.tsx.

## Verified
- QA-1-1 | verified | UX view: valid week start accepted at 1440 and 390 and opened /work/4102; date-only is not reachable from the form.
