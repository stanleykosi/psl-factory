VERDICT: CHANGES
REVIEWER: reviewer-ux
COMMIT: c4bd4510133c0c807bf0ae1d2068f8b7a14b6ff8
AUTHORITY: delivery UX review

## Summary
- Flows follow the spec from the builder's e2e/component evidence and a short live check: Finance sees the two new lines; fixed assets has Proof, optional Prior schedule and Accounting note; forecast has no file.
- Not exercised live by me: upload failed/removed, refusals, uncertain, landing (my scripted file upload did not find the input; relied on the builder's 22 + 24 tests and 9x2 e2e).
- Open UX decision: Start is not disabled while required fields are empty (build.md criterion 3).
- Accounting note has four placeholder options "Sample note A-D" where the spec says two.

## Findings
- UX-1-1 | blocking | medium | product | Start stays enabled with empty required fields; the server then answers "<Label> is required." under each field (F-05 behaviour, build.md criterion 3 marked partial). The boards draw an enabled "Start schedule/forecast", so this may be fine, but build.md asks for a decision and the spec criterion says "nothing computed or defaulted". Needs an explicit decision before PASS.
- UX-1-2 | blocking | low | frontend | Accounting note shows "Sample note A" to "D" (four placeholder choices, spec said two). Visible placeholder copy in a Finance drawer must be flagged as sample; the line cannot carry `sample: true`. Confirm with the design engineer or reduce to the spec's two options.
- UX-1-3 | non-blocking | low | frontend | Phone sheet shows "Step 2 of 2" and a drag handle that the boards omit, and the sheet is taller than the board. Acceptable usability (44 px targets, Escape returns focus per e2e) but record as a difference.
- UX-1-4 | non-blocking | low | backend | Wrong-record uploads are refused (4xx) but not a guaranteed 404 (criterion 8 partial). Mock only; already in BACKEND-HANDOFF.md.

## Verified
- Finance persona: Start work menu lists 5 lines; "Fixed asset schedule" and "Cash forecast" appear under "Finance back office" at 390 and the 1440 drawer opens.
- Builder evidence accepted but not re-run: upload states "Uploading…" / "Uploaded · 96 KB" / failed with Try again, remove sends nothing, start held while uploading; Audience from data with none preselected; start, landing on W-3901 / W-4001, hold W-4006 "SETUP NEEDED" without a Decide button, uncertain retry with same key, 401/403/404/409 wording; axe clean at both widths.
- Not verified by me: any of the above in the live browser beyond opening the drawer.
