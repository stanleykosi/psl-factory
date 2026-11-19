STATUS: READY
COMMIT: 644c8aafaff61edb86748e73808886fdcaf014dd
BUILDER: builder
LANE: full

## Summary
- The branch still builds the F-39 escalation line (W-3601 to W-3609): four states, escalate / don't escalate in place, Send for review and its hold. The round-2 rule that hides a decided task is unchanged.
- This round fixes QA-3-1. A second reviewer whose decide gets a 409 because the first reviewer already decided now sees the current state from the re-read. They also see a lasting alert: "This review changed while you were reading it, so nothing was recorded." When they typed a note, a second line says "Your note wasn’t sent: “<note>”". This works at 1440 and 390, Drawer included.
- The fix is F-35's commit 971bf73a (fe-leadership-report-drafting-review-tuesday) applied as-is to the shared InlineDecide.tsx and Workspace.tsx. It is a shared fix, kept byte-identical to F-35's lines so the two branches merge cleanly. The only conflict was the labels import line, resolved to this branch's imports.

## Changes
- `frontend/src/features/workspace/InlineDecide.tsx`: new `onStale(note)` prop, called when a decide answers 409, with the trimmed note it carried ('' for escalate/approve). It also adds `DECIDE_TEXT.noteNotSent`.
- `frontend/src/features/workspace/Workspace.tsx`: keeps `staleDecide`. When the re-read removes that task's decide panel, it shows a warning callout with `role="alert"`: the stale sentence plus the unsent note. The next decide or step clears it. While the panel is still drawn, InlineDecide's own stale view leads, as before.
- `frontend/tests/escalation.test.tsx`: new "QA-3-1: another reviewer decided first" block. The 409 handler sets the served item to the decided fixture before it answers, so the task really closes. It covers desktop don't escalate, phone Drawer don't escalate, and a lost-race escalate that names no note.
- `frontend/e2e/escalation.spec.ts`: new two-page test through the live mock at 1440 and 390. Page A escalates, then page B's don't escalate gets the mock's real 409. B shows MESSAGE DRAFTED, the stale sentence and the unsent note, still visible after 1.5 s. One decision POST is sent, and axe is clean.

## Fixes
- QA-3-1 | the stale notice and the unsent note stay on the page after a 409 whose re-read removes the decide panel (shared InlineDecide `onStale` plus a Workspace alert, the same as F-35's 971bf73a) | 45ae7b660519ea32d5a7d5f08eff2817230ec33a

## Acceptance criteria
11. [x] Backend refusals are shown, including a real two-reviewer stale. Evidence:
    - The 3 new component tests pass. With the two source files reverted to c706d6a7, all 3 fail (`Tests 3 failed | 29 passed`).
    - The new e2e passes at desktop 1440 and phone 390. On the old code both fail at "stale sentence toBeVisible": element not found.
    - The existing scenario-cookie 409 test (the stale view, "Review the latest" brings the note back) still passes.
- Every other criterion has the same evidence as round 2/3. The full escalation e2e (with income-schedule): 60 passed.

## Other lines (shared component)
- In this branch, only income_schedules (F-33, W-27xx) also decides in place through InlineDecide. It had the same bug: the panel goes after a stale re-read that closes the task, with no notice. With this shared fix it now gets the same alert. All of F-33's existing unit tests and e2e still pass. Follow-up: add an F-33 two-reviewer test.
- F-35 (leadership report) has this exact fix on its own branch. F-42 and other merged lines that use only the link or decide page are not affected by this path. Their own decide pages (F-16 useDecision views) were not re-checked for this race. That is a follow-up for QA.

## Validation
- Gate: `bash delivery/checks.sh` under the shared lock (lock released). rc=0. Django check: no issues. Lint and typecheck: clean. Vitest: 109 files and 2486 tests passed. `next build`: compiled successfully.
- `E2E_PORT=4937 MOCK_PORT=4936 npx playwright test e2e/escalation.spec.ts e2e/income-schedule.spec.ts`: 60 passed. Run on the old code (`--grep QA-3-1`): 2 failed.
- Fidelity: not re-run. No board's page changes. The new alert shows only after a stale 409 in a two-reviewer race, which is not a board state.
- Demo rebuilt and running: mock on 4936, `next start` on 4937 (W-3602 returns 200).
