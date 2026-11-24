VERDICT: CHANGES
COMMIT: 3b782e399d96666f02e5efbaf52ff86a8f590e0a
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer

## Summary
- Fidelity tool on a production build (API origin 127.0.0.1:4999 confirmed in routes-manifest), case 2001 with dossier 5001, no exceptions file: SCR-33 desktop 1440 FAIL, coverage 36% (18/50), visual 79.7; SCR-33 mobile 390 FAIL, coverage 27.3% (3/11), visual 78.1.
- Most of the 32 + 8 "missing" items are spec-accepted or hidden parts (listed as UI-1-x for the design engineer's fidelity-exceptions.json). Four differences are not covered by the spec and block.
- Not reviewed in browser beyond the empty form (case 2001): saved, historical and action-form states were not screenshotted; the builder's e2e covers them.
- Phone: no horizontal overflow, one column, targets look at least 44px. Contrast is readable. Persona "Ada Okafor" and SAMPLE DATA label are mock/shell, not findings.
- Reports and side-by-side images: scratchpad fidelity/SCR-33-1440 and fidelity/SCR-33-390 (report.json, side-by-side.png).

## Findings
- UI-1-1 | blocking | medium | frontend | Save button size and place differ from the boards. Desktop board: "Save retrospective" is 300x50, directly after the notes file inside the panel. Built: 157px wide, below the extra fields (y 1129 vs 824), with the reason text beside it. Phone board: full-width (358px) button in a bottom bar; built is a 157px inline button (y 1129 vs 776). Make it the board's size (full width on phone) and place it as the board does.
- UI-1-2 | blocking | medium | frontend | An extra title bar "RECORD THE RETROSPECTIVE" is drawn on the form panel (desktop and phone); the boards' panel has no header. Remove it (the tool lists it as an extra heading).
- UI-1-3 | blocking | medium | frontend | Checklist status chips restyled. Board: DONE green, NOW red, UNKNOWN amber. Built: UNKNOWN is grey, "NOT YET" (the screen's own row) is amber instead of the board's red NOW chip. The words are spec-approved; the colours should follow the board (held = red, unknown = amber) via existing status tokens. The row is also bold with a "this screen" suffix and a sub-line the board lacks (the suffix and sub-line are an accepted spec addition, see UI-1-9).
- UI-1-4 | blocking | low | frontend | Phone: the three boxes are plain labelled textareas in a panel; the phone board draws each as its own bordered card with the label inside and 18px "Retrospective" title (built 26px "Project retrospective", tool: 22px vs 26px). Match the card treatment and title size, or list it as an exception for the design engineer. Textareas also show a resize grip the board does not have (both widths).
- UI-1-5 | exception candidate | low | design engineer | "Cites:" chips under each box are not drawn (D-182, no live source). Fidelity: missing x5 on desktop.
- UI-1-6 | exception candidate | low | design engineer | "Save draft" not drawn (D-8, no draft exists). Missing x1.
- UI-1-7 | exception candidate | low | design engineer | Tola panel (avatar, "Tola · PMO agent ...") not drawn (DC-3, no live source). Missing x2; this also moves the checklist panel up (misplaced).
- UI-1-8 | exception candidate | low | design engineer | Board sample content is not UI: box text, "Tunde Bello (PM), Lagoon Health ... (recorded)", "retrospective-notes-sabi.docx Uploaded · 36 KB". Built uses a checkbox list of project people (outside parties not offered, spec conflict 4) and a "Notes file" select of recorded proofs (spec conflict 3, DC-4), where the board has one bordered line and a dashed upload chip. Also the mobile board's "← Sabi Market" back link and subtitle (the shell shows the breadcrumb on phone).
- UI-1-9 | exception candidate | low | design engineer | Added required fields and read-only data not on the boards (spec conflict 5): When it was held, Reference, Decisions block and "Add a decision", Write-in-one-box hint, Saved retrospectives list, version label, follow-up actions, "checklist used version n" line, "this screen" row marker. Checklist words are the API's (Closed/Recorded/Not yet/Unknown and titles such as "Hypercare finished", "Handover to Support") instead of DONE/NOW and the board titles; context and report checks omitted (spec conflict 7).
- UI-1-10 | exception candidate | low | design engineer | The tool counts "What went well", "What didn't", "Lessons for next projects" as missing text (they are form labels on the page) and the board's box sample text as missing (page boxes are empty on case 2001). Needs a pattern or exception entry, not a code change.

## Verified
None (round 1).

## Notes
- Verdict stays CHANGES even after the exceptions above: coverage cannot reach 100% without the design engineer's file, and visual must reach 90 (now 79.7 and 78.1). UI-1-1 to UI-1-4 will lift the score; the rest depends on the exceptions.
- The build, mock and server I started were stopped by PID and the copy was deleted.
