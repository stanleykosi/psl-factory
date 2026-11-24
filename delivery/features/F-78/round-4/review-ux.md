VERDICT: PASS
COMMIT: 86e1a6cfc20e7f6d999d4472374f7a8298fcd29a
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Round 4 changes behaviour only in the Milestones tab's completions list. An empty list used to show an error ("We couldn't load the recorded completions"); it now shows "No completions recorded yet." under "Recorded completions". That is the right journey state and the wording is plain.
- UX-1-1 (the same hold rule as UI-1-4) verified: under `name_in_use`, `norole` and `baseline_required` the proof radios, upload zone and Mark complete control are absent, and `proof_required` keeps only the PDF zone. Checked by the cited tests in `milestone-complete.test.tsx`; the hold path is unchanged in round 4.
- No new UX finding. The round-2 and round-3 items that stand are carried, not re-walked.
- Live: "Mark complete" is hidden for every staff role until backend LB-2 is fixed. This is recorded as a backend open item, not a frontend failure.
- The empty completions line's visual look is raised by the UI lens as UI-4-1 (non-blocking); the UX lens does not object to the wording.

## Findings
None.

## Verified
- UX-1-1 | verified | `npx vitest run tests/milestone-complete.test.tsx -t "UI-1-4"` on 86e1a6cf: 3 passed; `-t "proof_required"`: 2 passed. The hold cases show the hold line only, with no radios, no upload zone and no Mark complete. The round-2 browser walk (1440 and 390, `norole`, `inuse`, `baseline`, `proofreq`) still stands because the render gating is unchanged.
- QA-3-2 | verified | UX judgement of the empty state: "No completions recorded yet." under the "Recorded completions" heading (`frontend/src/features/projects/MilestonesTab.tsx:217`). The behaviour is verified by QA; the wording is accepted. The look is raised as UI-4-1 (non-blocking).
- UX-2-1 | carried | verified in round 3 (heading white on blue, 6.04:1). No CSS change since d9f900c2 in F-78's own files.
- UX-1-2 | carried | non-blocking, unchanged. The norole hold still reads only "You can't mark this milestone complete." It waits on LB-2 to name who can complete.
- UX-2-2 | carried | non-blocking, unchanged. The PNG refusal wording is the picker's own text, not the spec's "Only a PDF can be attached as proof." Not touched in round 4.

## Notes
- Impact assessment of round 4 for the journey: the completion POST, re-read, uncertain and Check again paths are in `milestoneCompleteModel`/`useMilestoneComplete`, which round 4 does not change. The round-4 change to `useMilestones` only reads the completions list (`sections` of zero or one), so the Mark complete entry on the tab and its options read are unaffected.
- Mock limits: the QA-3-2 empty state comes from `sections: []` in the mock and tests, not from a live record. Live check for LB-2 remains open.
- No browser walk this round. No server started; no PIDs to record.
