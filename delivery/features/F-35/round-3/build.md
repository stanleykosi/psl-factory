STATUS: READY
COMMIT: eefaf6c5e7f37793673e3d57fce297a55358fad1
BUILDER: builder
LANE: full

## Summary
- Round 3 fixes QA-2-1: a decide refused as stale (409) after another reviewer decided keeps the sent state, the stale sentence and the unsent note on the page.
- InlineDecide reports the stale outcome and its note via onStale; Workspace shows a warning after the re-read closes the task.

## Changes
- frontend/src/features/workspace/InlineDecide.tsx, Workspace.tsx: onStale, noteNotSent text, staleDecide notice.
- frontend/tests/leadership-report.test.tsx: two unit tests (return with note, approve loses race).
- frontend/e2e/leadership-report.spec.ts: two-reviewer test at both viewports.

## Fixes
- QA-2-1 | a 409 decide keeps the stale notice and unsent note after the task closes | 971bf73adfb922d5edd856bb0ce5f051b5b91f1e

## Acceptance criteria
1. [x] QA-2-1 behaviour: unit and e2e tests assert the sent state, stale sentence, "Your note wasn't sent: ..." and a single decision write.
Not done (non-blocking, left): QA-2-2 History link 42x24 at 390 is the shared header (also F-33), to be fixed once with UI-2-1. "Received" fixture wording: no change needed in the mock. Green partial-delivery banner untouched.

## Validation
- New test failing without the fix: reasoned from the diff (noteNotSent, onStale and the page notice did not exist before), not re-run on old files.
- bash delivery/checks.sh under the shared lock: exit 0; lock released.
- Demo running: mock on 4986, production build (FRAME_FIXTURES=1) on 4987; /work/W-3202 returns 200.
- git status clean; branch pushed.
