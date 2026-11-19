VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 9b8df3bbb9a306ec4b5f1050a5f0bbf2436ee83c
AUTHORITY: delivery UI review

## Summary
- Tool not re-run (as instructed). I read the saved report and side-by-sides and drove the live build at 1440 and 390 (pmo_lead), screenshots in the session scratchpad ui/ folder.
- Phone 67.9 is mostly a capture artefact: the live sheet opens at the top with "Client or prospect" first and Log RFP pinned; the tool captured the sheet scrolled to the last field, so six labels read as missing and the visual score is distorted. It cannot be called a pass or a waiver until re-measured.
- One real phone difference: the submission method is a 2x2 grid; the board draws four across.
- Six "scroll-capture" exceptions hide drawable labels and must be removed, not signed. The other 24 exceptions are honest and map to spec conflicts.
- No overflow at 390 (scrollWidth equals viewport), 44px targets, tokens and fonts match neighbouring drawers.

## Findings
- UI-1-1 | blocking | high | builder | Phone gate not passed: visual 67.9 is under the 70 floor and coverage 34.8 with no valid exceptions. The capture scrolled the sheet (side-by-side shows the sheet starting at "Received"), so the number cannot be trusted. Fix the driver (round-1/fidelity/_driver/act.mjs: scroll the sheet body to the top before capture, or capture at a height that shows the whole form) and re-run once; a score under 70 after that is a design-engineer decision, not a waiver by builder.
- UI-1-2 | blocking | high | builder | The six "scroll-capture" exceptions (Client or prospect, RFP reference, Received, Submit to, Deadline, Note) in fidelity-exceptions.json are labels the page draws from data; the gate rule forbids excepting a value the data can supply, and a driver limit is not a board difference. Remove them and fix the capture (UI-1-1). Verified live: all six labels render at both widths.
- UI-1-3 | blocking | medium | builder | Phone submission method is a 2x2 grid (Email / Client portal over By hand / Not stated); the SCR-23-mobile board draws one row of four (Email, Portal, By hand, Not stated) with the Deadline choice in one row of three. Restyled and not in the exceptions. Use a single row of four at 390 (labels fit at the board's width) or have the design engineer approve the grid as an exception with conflict number. Evidence: side-by-side.png phone, m-3top.png.
- UI-1-4 | blocking | medium | design engineer | Desktop visual 74.2 is under 90 and needs a board-level D-83 waiver signed by the design engineer; none is signed (builder only proposes). Real contributors seen: taller drawer (help lines and "(optional)" under fields), no info banner (conflict 2), no "New client" sentence (conflict 1), native date-time control text format (11/12/2026, 09:40 am) in place of "12 Nov 2026, 09:40 WAT" (conflict 6), the page behind the scrim shows the empty My work state not the board's list (frame, conflict 8).
- UI-1-5 | low | medium | builder | Note for later: phone sheet shows "Step 2 of 2 · change line" and the native date control; both accepted by spec (conflicts 2, 6). The disabled state in the uncertain panel drops the selected fill on Email, so the chosen method is no longer visible; grey the segment instead of removing the selection.

## Verified
- Exceptions 1-9 (frame, table, headers, "2h", "1d", close x): honest, conflict 8, F-05/F-47 precedent.
- Claim exceptions (intro sentence, New client sentence, Submit-to and Deadline board help, phone "Opens a new pre-engagement workspace"): honest, conflicts 1-4; each is text no data supplies and the page draws the line's own help instead (verified live).
- Sample-data and "Submit by" word exceptions (conflicts 5, 6, 11): honest; they cover typed values and date-time control text, not labels or options; no data value or drawable element hidden.
- Picker lists Tamarind Loans Ltd, Harmattan Bank, Kora Logistics, with search; "New client" row appears only with psl_mock_rfp=new_client.
- Desktop at 1440: drawer, eyebrow "START WORK · PRE-SALE", Cancel plus Log RFP footer, error states (403, uncertain, duplicate) use the same banner styles as other lines; no horizontal overflow.
- Phone at 390: bottom sheet, pinned Log RFP, no overflow, file row and fields in desktop order (D-111).
- Evidence copied: fidelity folders already under round-1/fidelity/ (report.json, side-by-side.png).
