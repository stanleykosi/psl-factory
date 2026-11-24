VERDICT: CHANGES
COMMIT: bdeee6852cdfbefbe883a6a5cd8f23b8d7faa3b1
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (lighter panel, D-180)

## Summary
- Fidelity tool not re-run (builder's SCR-24 run reused: 1440 coverage 52.4% / visual 89.8; 390 coverage 43.8% / visual 71.2). I read the gaps against the boards and the running build (mock, ports 4982/4983, lane-c2, 1440 and 390).
- SCR-24 gaps are mostly accepted: sample values, Note replaced by Reason, proof required, role hint and "alerted" line dropped (LC-Q7, LC-Q9, D-182), tick-box (LC-Q17, D-187), and the list behind the drawer (the board's work table is replaced by the received-RFP list). Two board elements are still missing without an exception (UI-1-1, UI-1-2).
- SCR-23 Log RFP differs from the board in several labels and one control with no recorded exception (UI-1-3). SCR-23 was not run through the tool (drawer has no URL), so these come from my side-by-side with the F-49 board capture.
- Both drawers: no horizontal overflow at 1440 or 390, sheet/drawer layout and tokens match neighbouring screens, 24px targets met except one shared link (note). Validation, upload proof and list states look right.

## Findings
- UI-1-1 | blocking | medium | frontend | SCR-24 board draws a blue info callout at the top of the drawer ("Only people allowed to prepare RFPs for this workspace are listed. Who may assign is set by PSL in Setup.") and a helper line under Accountable PM ("3 people can prepare RFPs here"). Neither is built; neither is listed in the spec's accepted changes (only role/hint and "alerted" are). The callout is static copy and the count is `nominees.length`, so "the API has no field" does not apply. Build both, or have the design engineer add them to fidelity-exceptions.json. frontend/src/features/rfp/AssignPmDrawer.tsx.
- UI-1-2 | blocking | low | frontend | SCR-24 board keeps "Proof" as a labelled block and an assignment summary; the built drawer has no helper text under "You are assigning as" ("One of the roles PSL allows to assign RFPs"). Role hint is accepted as dropped, but this line is static copy, not served data. Build it or list it as an exception. AssignPmDrawer.tsx.
- UI-1-3 | blocking | medium | frontend | SCR-23 Log RFP vs board, no exception recorded: (a) the blue info callout "Logging an RFP opens a new pre-engagement workspace for it. The RFP reference can't be changed later." is missing; (b) eyebrow reads "START WORK" without "PRE-SALE"; (c) labels renamed: "Client or prospect" -> "Client", "Received" -> "Actually received", "Submit to" -> "Where to submit", "Submission deadline" -> "Deadline"; "Deadline" options "Unknown / Stated / Not stated" -> "Not known / A date is stated / Not stated"; (d) "How the client wants it submitted" is a four-way segmented control on the board (Email, Client portal, By hand, Not stated) and a select ("Submission method", "Choose...") in the build; (e) the board's hint lines under RFP reference ("As written on their document"), Received ("When it actually arrived, not when you log it") and Submit to are missing. The client-name pair is accepted by LC-Q8; the rest are not. Restore the board wording, control and hints, or get them approved as exceptions. frontend/src/features/start-work/lines/receivedBid.tsx.

## Verified
(Round 1: none.)

## Notes
- Fidelity artefacts were not copied: I did not run the tool (instructed not to), so there is no report.json or side-by-side.png for this round. SCR-23 still has no tool run (no URL); the design engineer may want a harness URL or a manual check.
- Fidelity score 390 / 71.2 is mostly the sheet versus the board's list plus the same missing items; after UI-1-1 to UI-1-3 are closed, ask for one tool run on SCR-24 and judge the remainder against the accepted list.
- "change line" link in the Log RFP header is 67x16 px, below the 24px target. It is the shared F-86 drawer shell, not new in F-88; raise separately.
- Mock data: the Unassigned tab badge shows 2 while the list shows 12+ rows. Mock only.
- Review run: servers on 4982/4983 were already serving lane-c2; I reused them and started and stopped nothing.
