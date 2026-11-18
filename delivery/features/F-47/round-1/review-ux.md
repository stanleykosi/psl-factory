VERDICT: CHANGES
REVIEWER: reviewer-ux
COMMIT: 438c350fe7fe79233604f2293b6812d10df6c1ee
AUTHORITY: delivery UX review

## Summary
- Walked minutes and change as `pm` and the income schedule and ledger lines as `finance_lead`, at 1440 and 390, against the running build (4945/4944). One Start per line reached its work item (W-1403, W-1405, W-4401, W-4402); mock reset afterwards.
- The proof card reads clearly: "Choose the project first." then "Choose a file", then "Uploading… · 38 KB", then "Uploaded · 38 KB" with a named "Remove <file>" ×, and "Not uploaded · 1 KB" with the backend's 422 sentence.
- Start is off while uploading and while a file is failed. It comes back on after removing the file. The project select is disabled while uploading. Changing project drops the card and shows "Proof removed: it was added to the other project. Add it again.", and typed text is kept.
- Start sends one upload per file, then one start with the proof id. The button reads "Starting…" until the response, and nothing says "started". A start refused with 422 (required fields) keeps every entry and the uploaded card.
- Phone: bottom sheet, no sideways scroll. The × is 44x44 and the selects, segments, Close and Start are at least 44 high. One blocking gap: upload failures are not announced to assistive tech.

## Findings
- UX-1-1 | blocking | medium | frontend | Upload failures are not announced. Spec criterion 18 requires "Upload problems ... are announced (`role="status"` or `alert`)". With a `.exe` upload (422) the sentence "EXE files can't be used as proof." sits in plain spans (SPAN < SPAN < DIV group < FIELDSET), with no `role` or `aria-live`. The only live region that exists at that moment is an empty `alert`. The project-changed line is announced correctly (`role="status"`). A screen-reader user is not told the upload failed. Expected: a live region (the card's reason text or the shared ProofField error) so the failure is read when it appears. Seen on the minutes (pm) and ledger (finance_lead) drawers at 1440. Code: `frontend/src/features/start-work/StartProof.tsx:78` (ProofField is shared from F-09, so the fix may need a start-work wrapper rather than an edit to `features/response`).
- UX-1-2 | non-blocking | low | frontend | The disabled Start gives no reason. While a file is uploading or failed, the button is simply greyed out and nothing near it says "remove it or try again first". The card's "Not uploaded" text carries the cause, so this is a clarity issue only. Consider a short line above Start.
- UX-1-3 | non-blocking | low | frontend | On desktop the × is 24x24 px. The spec asks for 44 px on phones only, and the phone × is 44x44, so this meets the spec. It is small for pointer and touch laptops.
- UX-1-4 | non-blocking | low | frontend | The file input has no accessible name that I could read from `aria-label` or `<label>`. It may be named through `aria-labelledby` on the group; I did not run axe, so criterion 18's "file input is named" is unconfirmed. QA's axe run should settle it.

## Notes
- Tried states not available in this mock: Try again (only 5xx or network errors show it; a 422 correctly shows none), 401, and the uncertain-start "Check again" cookie. I did not drive them.
- Desktop single-file card hides the picker once a file is chosen, so replacing a file needs × first. That matches the board and is clear.
