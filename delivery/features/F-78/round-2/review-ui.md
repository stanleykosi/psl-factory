VERDICT: CHANGES
COMMIT: ca4abee2fb0b22e6aca06c61e643eba2ae8fb02f
REVIEWER: ui-reviewer
AUTHORITY: UI design reviewer

## Summary
- UI-1-1 to UI-1-4 are fixed: dark card header, Project and Milestone as bordered read-only fields, a flat phone page with a 22px milestone heading, no breadcrumb and no bar overlap, and no proof controls under holds. No horizontal scroll at 1440 or 390 in the five states tried (ok, inuse, baseline, proofreq, norole).
- Fidelity with the exceptions file: desktop 1440 coverage 53.6% raw, 100% with exceptions, visual 78.3 (fail, needs >= 90); phone 390 coverage 41.7% raw, 100% with exceptions, visual 77.0 (fail). Run once per board and width, after warming the compile.
- One new blocking defect: the "WHAT HAPPENS NEXT" header text is dark blue (#16388F) on the blue (#2459D6) band, so it is barely readable; the board has white text (UI-2-1).
- Visual is below 90 on both boards. A visual waiver is needed unless the design engineer wants more changes. Most of the gap is excepted content (invoice text, evidence row, dates) and the grey disabled "Mark complete" against the board's filled blue state. Please fix UI-2-1 first and let the score be re-read.
- Entries still "pending design engineer (questions-batch B36)" count as unexcepted until signed; they are listed below with exact role and name.

## Findings
- UI-2-1 | blocking | medium | frontend | "WHAT HAPPENS NEXT" header text colour. Board SCR-19-desktop: white text on the blue #2459D6 header. Built: #16388F text on the #2459D6 band (fidelity look "text colour #FFFFFF on the board, #16388F on the page"; seen in side-by-side.png). `.mscomplete__next > .psl-panel__head` in frontend/src/features/projects/milestone-complete.css:9 sets the colour on the head, but the heading inside the agent Panel keeps its own colour. Set the heading colour to white (--on-strong) too. Contrast is below readable.
- UI-2-2 | non-blocking | low | frontend | The phone and desktop Mark complete controls match the board only when ready (blue, ticked). In the default state the grey disabled button is the state difference already listed as a not-gating extra; no change asked.

## Verified
- UI-1-1 | verified | 1440 screenshots: the card header is the dark #1F2427 band with white capitals ("MILESTONE"; the stage number is excepted under conflict 4). The "What happens next" panel has the blue header band as drawn, but its heading text is unreadable; tracked as UI-2-1.
- UI-1-2 | verified | 1440 ok and hold states: bordered read-only "Project: Lagoon Health · patient app" and bordered "Milestone: Go-live" fields. Project is now a fidelity match (the tool lists it as moved, not missing).
- UI-1-3 | verified | 390: h1 is the milestone name at 22px, a grey project line under it, no breadcrumb, no card borders, bordered-free flat layout, short next text, scrollWidth 390, 'Mark complete' in a bottom bar with the content ending above it. The dev "N" badge overlaps the bar only in dev mode.
- UI-1-4 | verified | cookies psl_mock_complete=inuse, baseline, proofreq, norole at 1440 and 390: 0 radios, 0 file inputs, no Mark complete button. With ok: 2 radios, the PDF zone and the button show at both widths. Under proofreq the mock has can_attach_pdf false, so no PDF zone is correct.

## Notes
Fidelity, per board and width (report.json and side-by-side.png copied to round-2/fidelity/SCR-19-desktop and SCR-19-mobile):
- SCR-19-desktop 1440: coverage 15/28, 53.6% raw; 100% with exceptions; visual 78.3; pass false (visual below 90). Misplaced (not gating): "MILESTONE 2" (built "MILESTONE" in the dark band) and the Project field. Extras (shell/frame): nav "Overview" and "Setup", "Alerts, 1 unread", "Account menu: Ada Okafor · Finance Lead", the breadcrumb navigation and links, "Demo controls" and "Demo".
- SCR-19-mobile 390: coverage 5/12, 41.7% raw; 100% with exceptions; visual 77.0; pass false (visual below 90). Extras: "Back to Projects", "Alerts, 1 unread", project line, "Evidence", "Or upload a private PDF", "Take a photo or choose a file", "PDF · up to 10 MB", "Choose the proof. Tick the confirmation.", the changed "What happens next" paragraph, "Demo controls".
- Table/row styling: the SCR-19 boards have no tables.
- Persona note: the tool run used the default mock persona (shell shows "Ada Okafor · Finance Lead"); the board shows "Tunde Bello · PMO", which is excepted.

Unexcepted entries, sorted:
- (a) Accepted spec changes (conflicts 1 to 4): signed under B32 / D-195 / D-202; nothing outstanding.
- (b) Board sample values: "Tunde Bello · PMO" is signed (D-202). "HB-M2" (Text, mobile case reference chip) is pending design engineer (questions-batch B36), unexcepted until signed.
- (c) Frame and shell, all pending design engineer (questions-batch B36), unexcepted until signed: Text "LAGOON HEALTH / MILESTONES" (desktop breadcrumb, style); Link "← Lagoon Health" (mobile back link, built "← Projects"); the not-gating extras (desktop shell extras, phone shell extras, the disabled grey "Mark complete" state).
- (d) Real build gaps that block the frontend: UI-2-1 only. Everything pending B36 is (b) or (c) and does not block.

Visual waiver: yes, needed for both boards unless the score reaches 90 after UI-2-1. I do not propose one for UI-2-1 itself; fix it. The design engineer decides the waiver; visual_waivers in fidelity-exceptions.json is empty. Scratch copies: /private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/fid78r2 and .../shots78r2.
