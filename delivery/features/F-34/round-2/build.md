STATUS: READY
COMMIT: e3928527335e9963daedccf798e736ff53e1ee8b
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the two blocking UI findings and the UX notes that were cheap. Contract mock only; nothing is deployed, evaluated or qualified (the round 1 "What is sent, and what stays held" section still holds).
- The fixtures no longer carry a result word beside the returned "Met" tag, W-3104's stage strip no longer says an agent is working, and the proof message goes once a file is uploaded.
- Three tone exceptions for the missing `waiting` tone are added and the gap is in BACKEND-HANDOFF.
- A fidelity re-run is needed: the criteria rows lose one tag and W-3104's strip changes, so the layout moved a little. Please run run.sh (frozen, then live). I did not run it.

## Changes
- `frontend/mock/fixtures/work/W-3101`, `.next`, `W-3109`, `W-3111`, `W-3112`, `.next`, `W-3104`: criteria items keep only the returned tag (no `status: "done"`); W-3104 `stations` Hypercare is `done`.
- `src/features/workspace/StepForm.tsx`: an evidence field's message is cleared when a file is uploaded (shared, same behaviour as the other fields).
- `tests/hypercare.test.tsx`: three new tests.
- `delivery/BACKEND-HANDOFF.md`: missing `waiting` tone (D-46) and the Setup link for a PM.
- `delivery/features/F-34/fidelity-exceptions.json`: 3 tone exceptions, the Setup needed tag colour, and MET placement. All are "builder proposal, pending design engineer".

## Fixes
- UI-1-1 | e3928527 | removed the second result word from the criteria fixtures; test checks no "Done" in the Met rows; MET placement listed as an exception
- UI-1-2 | e3928527 | tone exceptions for the running status, the record status and "Open · owner set" (and Setup needed), citing the missing `waiting` tone (D-46); gap added to BACKEND-HANDOFF; no frontend tone mapping
- UX-1-1 | e3928527 | W-3104 strip has Hypercare done; test checks no current_agent and no "Agent working"
- UX-1-2 | e3928527 | the proof message clears when a file is uploaded; test added
- UX-1-4 | e3928527 | recorded in BACKEND-HANDOFF (send the Setup link only to people who may open Setup)

Left, not cheap or shared frame: UX-1-3 (field message wording), UX-1-5 (frame Next strip text), UX-1-6 (a returned row would show what was recorded; backend data), UX-1-7 (phone bar is the F-22 frame).

## Validation
- `checks.sh` under the lock: lint, typecheck, Django check and build step reached. Under a load spike (71) 12 test files failed on 10 s hook timeouts and one assertion in `setup-proposal`; none of the failures is a code change. All 12 files were re-run alone with load under 14: 12 files, 161 tests passed.
- e2e hypercare + delivery-release (E2E_PORT=4962 MOCK_PORT=4963): 43 passed. `frontend/test-results` deleted.
- `hypercare.test.tsx`, `delivery-hypercare-mock.test.ts`, `workspace-step.test.tsx`, `engagement-planning.test.tsx`: 161 passed.

## Scores
Not re-run (see Summary). Round 1 scores stand until the coordinator's re-run.

## Coordinator: scored fidelity run, round 2 (19 Nov)
As arranged (the builder doesn't run it; the design engineer approved the coordinator running run.sh for F-34), the coordinator copied round-1's run.sh, serve-frozen.mjs and drive-states.mjs unmodified into round-2/fidelity (only the output path changed), rebuilt e3928527 for production (mock 4960, app 4961), scored the live boards, re-froze the two record boards from this build with drive-states.mjs, and scored them. scores.txt: 100 with exceptions on all 8; visual desktop 92.1 (pass) / setup-needed 77.1 / qualified 80.5 / record 82.7; phone 84.5 / 80.0 / 82.9 / 77.5.
