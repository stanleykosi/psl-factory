VERDICT: PASS
COMMIT: 10c7accc2889434032b1addd7d8fad42fe71b9ce
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- Contract mock (`frontend/mock/assistant.mjs`) validates request bodies and every reply against the v7 schemas, is wired into `M1_OPERATIONS`, and is covered by `mock-contract.test.ts` (skipped there only because `assistant-mock.test.ts` covers it). No idempotency key was added to the assistant bodies; the mock keeps a POST log to prove one POST per press.
- Click lock (`writing` ref), no auto-resend, and "re-read before Try again" in `useSend.ts` are sound. A created conversation is kept in `created` so a retry never makes a second one.
- Polling in `useConversation.ts` runs only while status is `working`, pauses while hidden, and its effect cleanup clears the timer and listener on unmount. The page is keyed by conversation id. Tests cover hidden, resume, stop and unmount.
- Start work changes are optional props (`prefill`, `onStarted`, `initialIntake`). No existing start-work test file was edited; the new tests are in `start-work-prefill.test.tsx`.
- Agent text goes through React text nodes only. There is no `dangerouslySetInnerHTML` and no speech API. `/me` is used only for `assistant_agents`. The shared components (ChatMessage, Composer, DraftCard, SourceTag, AgentChecklist `inline`) are general and have their own tests.

## Findings
- TECH-1-1 | non-blocking | low | frontend | frontend/src/features/assistant/useSend.ts:101 | After an uncertain send, "message is there" is decided by comparing the last person message text with the typed text. If the person had already sent identical text earlier in the thread, a lost send looks like a delivered one, and the text is cleared with no resend. Expected: compare the person-message count with the count before the send, or the last message's `at`. Actual: text equality only. Fix: record the number of person messages before the post and require a new one (do not resend automatically either way).
- TECH-1-2 | non-blocking | low | frontend | frontend/mock/assistant.mjs:243 | The draft's start reply (201 `{work_id, state}`) returns directly from `draftStart` and skips the v7 response-schema check that every other mock reply gets. Fix: run it through `ops['E-WORK-START'].replies['201']` (and the 409 reply) before returning.
- TECH-1-3 | non-blocking | low | frontend | frontend/src/features/start-work/useStartWork.ts:176 | The prefill search of record options is capped at `PREFILL_PAGES` (5) pages. A served value beyond that is shown as "no longer available". This is acceptable for the mock, and the note is honest. Fix: leave as is, and revisit when the real options endpoint supports lookup by id.

## Verified
None (round 1).
