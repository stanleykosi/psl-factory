VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: d20fd9b2ccee7be267936cc2758358989ecdedbb
AUTHORITY: delivery security review

## Summary
- Scope: diff 9ebc7cbc..d20fd9b2 only. That covers `Workspace.tsx`, `InlineDecide.tsx`, `WorkItemOverview.tsx`, `workspace.css`, the W-27xx fixtures, the new W-2712 family and two test files. Everything outside this diff carries forward from my round-2 PASS on 9ebc7cbc. Impact assessment: the decide write path, claim, CSRF, `confirmed` gating and the reconcile flow in `useDecision` are untouched by this diff. That PASS therefore still holds for them.
- **No uncertain result shows as done, and no decision is sent twice.**
  - `onDeciding()` only clears two pieces of local display state: `flow.setNotice(null)` and `setDecided(null)`. It runs inside `send`, after the existing `!ready || busy || off` guard, so it adds no new way to submit.
  - The outcome notice still comes only from `onDecided`, with the round-2 `confirmed` gating. Clearing old notices first removes the stale "done" notice that could otherwise sit next to an uncertain result. This makes the uncertain case more honest.
  - No call to `review.decide` or the submit flow was added.
- **Controls still come only from `you_can_act`.** The availability check (`task.you_can_act === true && claim !== null`) is unchanged.
  - `bannerTone` now reads `item.stations[].status` on the income line. It sets a callout colour only and grants nothing.
  - `splitAsk` only moves the existing assistant link into the agent card.
- **No new write, link target or HTML rendering.**
  - The "Ask Chidi" link has a fixed `href="/assistant"`. Its label is server text drawn through React as escaped text. This link already existed through `WorkspaceLinks`, so there is no new route.
  - The `AgentCard` `foot` is a React node built by our own code.
  - The note label change is plain JSX.
  - Neither `dangerouslySetInnerHTML` nor `href` values from data appear in `src/features/workspace` or `src/features/work-item`. No fetch call, method or write endpoint was added.
- **The W-2712 fixture cannot be reached as real data.** Its files are under `frontend/mock/fixtures/work/`, which only the mock server serves. Nothing in `frontend/src` imports `mock/` (the only matches are comments). The only references to W-2712 are the four fixture files and two test files. The backend's `fixtures/` does not reference it. The fixture contains no tokens, emails or credentials, and its people (Bisi Ade, Ada Okafor) are the same sample names used across the W-27xx family. `you_can_act: true` in the base file is mock-only and grants nothing in the real backend.
- The new Reject `consequence` strings are static sample text from the backend. They are drawn as text.

## Findings
None.

## Verified
- TECH-2-1 | verified (security lens) | A decide clears the earlier step and decision notices before it sends. On W-2712, the result after a decide is "Schedule v1: result not confirmed", never an outcome. I did not re-run the tests: the brief says not to run the suite. The builder reports that the new tests fail on the round-2 source and pass now.

## Notes
- Carried forward and not blocking: E-TASK-DECIDE has no idempotency key. This is a backend item and is not changed here.
