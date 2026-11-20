VERDICT: PASS
REVIEWER: reviewer-ui
COMMIT: 139eceeb05c331741f89d45b9b995c5175ca1fa0
AUTHORITY: delivery UI review

## Summary
- Tool not re-run (as instructed). I read the round-2 scores (desktop 51.9 / 86.5 with exceptions / visual 74.2; phone 39.1 / 78.3 / visual 59) and drove the live build at 1440 and 390 as pmo_lead (screenshots in the session scratchpad ui/ folder).
- Both builder-fixable findings (UI-1-2, UI-1-3) are fixed. What remains is for the design engineer: the phone floor exception (UI-1-1) and the desktop waiver (UI-1-4). Verdict is CHANGES only because neither board passes the gate and no sign-off exists yet; there is nothing left for the builder to fix.
- Judgement on the phone 59: a limit of the tool's union scoring, not a real visual defect. The live sheet is 1202px tall against the board's 844px, and every added row is an accepted spec item (D-130). Section by section, the sheet matches the board in header, client picker, reference, file card, Received, the Unknown/Stated/Not stated choice, the Deadline control, the four-segment method row and the pinned Log RFP button. The extra height is: help lines under fields, "(optional)" on four labels, "Step 2 of 2 · change line", the file card's remove x, Submit to, Note, and the native date-time control. Union height counts all of that as mismatch.
- The one board difference that is not height: the board draws Deadline (choice and date) before "Submit by"; the build follows desktop order, method first (spec conflicts 5 and 7, D-111). Words differ for the same reason ("How the client wants it submitted" / "Submission deadline" / "Portal" is "Client portal"). Both are accepted, but the order swap and labels should be named in the floor exception.

## Findings
- UI-1-1 | sign-off | high | design engineer | Phone visual 59 is under the 70 floor. Tool limit (taller accepted sheet, see Summary), not a build fix. Needs a design-engineer floor exception that cites D-130, spec conflicts 2, 5, 6, 7, and the order swap above. Phone coverage with exceptions is 78.3, not 100: the remaining items are the 24 honest exceptions plus drawable labels that now differ in wording (conflict 5); the exception file should list the phone wording differences by name when signed.
- UI-1-4 | sign-off | medium | design engineer | Desktop visual 74.2 is under 90 and coverage with exceptions is 86.5. Needs the board-level D-83 waiver (conflicts 2, 5, 6, 8; taller drawer; no info banner; native date-time format). Builder proposal only, nothing signed. The 24 exceptions are all still "builder proposal, pending design engineer".
- UI-1-5 | low | medium | builder | Carried note: in the uncertain panel's disabled state the selected method loses its fill (was in round 1; not changed, not blocking).

## Verified
- UI-1-3 | verified | live at 390: the four method options sit on one row (Email x=18, Client portal x=85, By hand x=194, Not stated x=277, all y=649); the deadline choice is one row of three (y=837). At 1440 both are single rows as well.
- UI-1-2 | verified | fidelity-exceptions.json has 24 entries and none for Client or prospect, RFP reference, Received, Submit to, Deadline or Note labels; all six labels (plus the Note and Submit to labels) render in the live dialog at both widths.
- UI-1-1 | verified (capture) | the driver now shows the whole sheet starting at "Client or prospect" with Log RFP pinned; the score reads the real page, so 59 is a real measurement of height difference, not a capture artefact.
- No horizontal overflow: scrollWidth equals viewport at 1440 and 390; tokens, fonts and the pinned primary button match neighbouring sheets.
- Evidence copied to round-2/fidelity/SCR-23-desktop-1440 and SCR-23-mobile-390 (report.json, side-by-side.png; these are the round-2 outputs the builder wrote into the round-1 folder).


## Coordinator note (20 Nov)
The reviewer wrote VERDICT: CHANGES only for two sign-off items (UI-1-1 phone floor exception, UI-1-4 desktop waiver), with nothing left for the builder. The design engineer accepted both under D-131 ("Accept all eight"), so the verdict is recorded as PASS. Original reviewer text unchanged above.
