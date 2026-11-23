VERDICT: PASS
COMMIT: 7d7d6cc313cb158e9d765a2593d154f06e430d16
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked the Start work drawer on the mock (persona pm) at 1440 and 390 width: chooser, project picker, weekly form, start, and the error states. All match the spec and SCR-04.
- Chooser lists live lines with no groups and no "Next:" line. Three lines show as unavailable, each with "Open in the full form" linking to its django_url (/lines/pmo-minutes/, /lines/finance-payroll/, /lines/pmo-issues/). Next stays disabled until the weekly report is chosen. No invoice line.
- Weekly form has Project, Week and Reference only (no Template line, no file field). Empty start makes a summary of 3 problems plus inline errors. A valid start lands on /work/4102.
- Error states read plainly: 409 keeps the values and says the project changed, 503 locks the form with "Not confirmed. Check before trying again." and "Check again", 403 and 404 show their wording, a failed lines load shows "We couldn't load your lines. Nothing was started." with Try again. Phone layout is a sheet with Step 2 of 2 and no horizontal break.

## Findings
- UX-1-1 | non-blocking | low | frontend | On a 403 start the callout reads "Your role doesn't let you start this line. Your role does not allow this." The server message repeats the app's own sentence. Show only one. frontend/src/features/start-work/LineForm.tsx (notice kind problem) and useStart.ts.
- UX-1-2 | non-blocking | low | frontend | Unavailable cards all say the same "Not available here yet. Open it in the full form." The contract gives no reason per line (LC-Q3 option 1), so this is acceptable now. Revisit if the backend adds one. frontend/src/features/start-work/LineChooser.tsx.

## Verified
