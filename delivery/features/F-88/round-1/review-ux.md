VERDICT: PASS
COMMIT: bdeee6852cdfbefbe883a6a5cd8f23b8d7faa3b1
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux (lighter panel, D-180)

## Summary
- Walked SCR-23 (Log a received RFP from Start work) and SCR-24 (Assign PM from My work, Unassigned) on the mock as the PMO Lead persona at 1440 and 390; no horizontal overflow at either width, no dead ends.
- SCR-23: client picker, reference, file, received time, deadline, optional submission details and Note, optional LC-Q17 tick-box (appears only once a client name or submission detail is filled). Success shows "RFP logged." with reference, time, file and "Open Unassigned"; focus moves to the status. Required-field summary, 403, 422 field message and the 503 "Not confirmed. Check before trying again." with "Check again" all read plainly.
- SCR-24: nominee, role, proof (recorded or upload with "I checked this file is the right proof."), required reason, "What happens next". Empty submit lists 4 fixes with links and inline errors; success shows "PM assigned: Amara Okoye." only after the re-reads. Already assigned, setup required, no nominees, lost reply, 422 and 409 states all say something useful.
- Deviations from the boards are the ones the spec records and D-182/D-187 settled (Reason for Note, required proof, no role/hint, receipt link). Two small non-blocking observations below.

## Findings
- UX-1-1 | non-blocking | low | frontend | Start work chooser shows a second "Lines you can start" heading above "Log a received RFP" after the group of F-86 lines, so the heading repeats; the received RFP is also listed separately from its siblings. Expected one list. Actual two same-named groups (`frontend/src/features/start-work/LineChooser.tsx`, `withOwnLines`).
- UX-1-2 | non-blocking | low | frontend | On the mock the Unassigned tab badge and the "6 records you can see" line (from `/work` counts) disagree with the 13 rows the received-bids list serves. Live `/work` has no `counts`, so the tab is hidden there until My work is connected (build.md notes this); worth a follow-up so the number and list come from one source (`frontend/src/features/my-work/MyWork.tsx`).

## Verified
None. Round 1, no earlier findings.
