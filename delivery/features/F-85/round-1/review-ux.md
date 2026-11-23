VERDICT: PASS
COMMIT: 1817c34ee2d7bf6386c9ade3231304b9dbe3a7e4
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer (lighter panel, D-180)

## Summary
- Walked /work/4101 to 4106 and /work/4102 and /work/4103 history at 1440 and 390 width against the mock. Every page matches the spec table and D-182. There is no station track, facts strip or agent steps, and no placeholder where they were.
- 4106 shows one "This record is unavailable." with a way back to the queue. 4104 shows "Why it is stuck" and the next step. 4103 offers "Open decision" only on the decidable task. 4101 links to the output. 4102 draws the weekly report panel read only.
- History shows an unknown station and status as raw text, and gives the "Showing all changes. As of ..." caption. Phone layout puts the tabs under the title with no overflow.
- Only low, non-blocking polish items remain.

- Merge delta (F-58 sign-in and account menu, F-70 project list): re-walked /work/4102, /work/4103 and /work/4103/history at 1440 and 390 against the mock, signed in and after sign-out. Pages, copy and states are unchanged, with no overflow. After sign-out at 1440 the item and history routes show "You're signed out." with a Sign in link. The F-85 journeys are not altered by main.

## Findings
- UX-1-1 | non-blocking | low | frontend | The breadcrumb shows the raw line key ("WEEKLY_REPORT", "INVOICE"). Use a plain business label when the line is known. LiveWorkItemView.tsx Header.
- UX-1-2 | non-blocking | low | frontend | Decision rows show raw lowercase words ("review · PMO Lead · open"). The second row ("approval · Finance Lead") has no link and no reason, so it reads like a dead end. Capitalise the words and say who it is waiting on. LiveWorkItemView.tsx Overview.
- UX-1-3 | non-blocking | low | frontend | The history row shows "Evidence 11" as plain text. The spec says a link when evidence_id is set. Link it when an evidence route exists, otherwise record the gap.
- UX-1-4 | non-blocking | low | frontend | While a line panel loads, it draws nothing (PanelView returns null). Add a small loading line so the page does not seem to finish early.

## Verified
None.
