STATUS: READY
COMMIT: 3a2884d4707522db814305db68b78dc6e4fc682a
BUILDER: builder
LANE: full

## Summary
- Round 3 fixes QA-2-1 (blocking), QA-2-2 and QA-2-3. Layout, exceptions and waivers unchanged; no fidelity re-run.
- The full `delivery/checks.sh` did NOT pass cleanly: two runs under the lock each failed on a different unrelated test (see Validation). Both pass when run alone.

## Changes
- `frontend/src/features/workspace/StepForm.tsx` (shared F-17 form): focus goes to the first focusable control inside an invalid field (the old selector hit the non-focusable wrapper of the Update type choice). New opt-in `summary` prop draws a top "N things to fix" ValidationSummary linked to the fields' first controls; only Workspace.tsx passes it, for line `issue_followup`, so weekly, minutes and other lines are unchanged.
- `frontend/src/features/workspace/Workspace.tsx`: passes `summary` on the issue line.
- `frontend/src/features/workspace/AssignForm.tsx`: the kind word ("Team", "Outside party") is dropped when it equals the backend `role`.
- `frontend/e2e/issue-detail.spec.ts`: the unknown-id test is replaced by 403 and 404 tests that send `x-mock-scenario` on the item read only (W-2411), asserting the same "You can’t open this work item" view, no title or ISS id, and axe, at 1440 and 390.
- `frontend/tests/issue-detail.test.tsx`: new test for an empty submit on Post update (summary "2 things to fix", focus on the first radio) and Record a reply (summary "1 thing to fix", focus on the textarea); the kind-word assertion now checks no repeat; two existing assertions use getAllByText because the summary repeats a message.

## Fixes
- QA-2-1 | 3a2884d4 | focus on first focusable control + summary on the issue line's step forms
- QA-2-2 | 3a2884d4 | kind word not repeated when equal to role
- QA-2-3 | 3a2884d4 | e2e uses the 403/404 scenario header on the item read

## Validation
- `npx vitest run` on issue-detail, workspace-step, weekly, minutes: 148 passed. `npm run lint` and `tsc --noEmit` clean.
- e2e `issue-detail`, `workspace`, `weekly`, `minutes` specs: first run 109 passed, 4 failed (my new 403/404 tests, wrong apostrophe in the expected text). After the fix, `issue-detail -g "item read"`: 4 passed. The full four-file set was not re-run after that fix.
- Full `bash delivery/checks.sh`, two runs under the shared lock:
  - Run 1: exit 1, `frontend/tests/setup-rules.test.tsx` "403 that leaves no editable row..." failed. Re-run alone: 42 passed.
  - Run 2: exit 1, `frontend/tests/rfp.test.tsx` "after Send the stale line is gone and focus moves to the status line" failed. Re-run alone twice: 53 passed each time.
  - Neither file is touched by this branch; both look like timing failures under machine load. I did not do a third full run.

## Not run
- A third full `checks.sh` run; the full e2e set after the apostrophe fix; fidelity (no layout change); e2e for the other lines beyond workspace, weekly and minutes.
