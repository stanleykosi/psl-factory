VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: ea9718cd5eeb3fd267df59ebb13d7373165cd43e
AUTHORITY: delivery security review

## Summary
- The send guard in the shared `useWorkspaceStep.ts` still holds. `writing.current` is set synchronously and is cleared only in `finally`, after the re-read. So moving the done notice after the re-read leaves the in-flight window closed. A second press, or another step, returns `kept` without a POST.
- The INV-RESEND lock is unchanged. `effect_uncertain` sets `pressLocked` before the re-read. 5xx, network failure and abort on a sending step lock that step and drop its key. `awaitingReconcile` keeps the lock after a reload. Nothing retries by itself. A failed re-read sets `refreshFailed`, which keeps every step off.
- The TECH-1-3 change to the search submit sends `q` only through the shared list read, the same way typing does. No new sink or URL is built.
- The merge brings in F-31, F-32 and F-33 unchanged. F-41 changes against dlv-00 are the reviewed round-1 code plus the two round-2 fixes. There are no new dependencies, secrets, `dangerouslySetInnerHTML` or links.
- Ran the 13 related vitest files (payments, reminder, workspace-step, workspace, weekly, minutes, issue, engagement, income, release): 449 passed.

## Findings
None.

## Verified
- SEC (round-1 note, mock accepts a second send while uncertain) | verified | This is still true of the contract mock (`workspace.mjs` `handle` checks only the step key) and is unchanged by this round. The browser lock above holds, and round-2 `build.md` (TECH-1-2 record) names the backend's resend refusal and key idempotency as the real guard before any live provider (BACKEND-HANDOFF F-41, priority 1). It stays non-blocking for a mock-only feature.
- TECH-1-1 (security reading) | verified | Delaying the notice opens no new path to a send: `useWorkspaceStep.ts:102-118` and the `finally` at 163-166 hold the write guard across the re-read. The new `payment-reminder.test.tsx` case confirms one POST and no success text before the re-read lands.
