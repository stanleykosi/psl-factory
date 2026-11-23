DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Connect the already-built SCR-05 Assistant (F-24, F-48) to live API 1.22.0 under FE-CONNECT-1. Five boards (default, thread, draft-started, cant, working), inside the 8-board limit, so one PR.
- Readiness rests on the D-180 two-day push exception (delivery/connect/LANES.md): build on the best reading of A-28 to A-32 and flag each. This is not a client-approved answer. The exception covers only this connection work.
- No new design. The boards stay as approved. Parts the live API cannot fill are dropped or degraded and listed for the client, so acceptance is required.
- I did not re-run design.py check or re-verify architecture approval for this check. The builder must run the design gate before building.
- The live shapes are reshaped, not matched, so this is medium risk. The work touches no money, identity or data migration.

## Scope
Outcome: a signed-in person sees the conversation list, opens a conversation, asks a question, sees the answer, drafted or cannot-answer state from live data, and starts a new conversation.

In (routes /assistant and /assistant/[conversationId], files src/features/assistant/*):
- `GET /assistant/conversations` shows scope (project or department), agent and updated_at.
- `POST /assistant/conversations` sends `{agent, case_id, idempotency_key, scope?}`.
- `GET /assistant/conversations/{id}` renders one question and answer per message, with sources, `started_work_id`, `draft_url` and `transfer_url`.
- `POST …/messages` sends `{text, idempotency_key, source_keys[]}` and gets 202. The screen then polls the conversation until `status` settles.
- The source picker uses `available_sources` and `question_options`. It replaces the @mention picker.
- `POST /assistant/turns/{turn_id}/transfer` passes the answer to another agent.
- `GET/POST …/draft`, `GET …/draft-options` and `POST …/start` run the save-then-start flow. Only the exact saved `draft_version` can be started.
- `GET /projects/{case_id}/intake-sources`.
- Agents come from `/me` `assistant_agents`.

Best reading for the open questions (flag each in the PR):
- A-28: the list has no title, status or status_line. Derive the row label from scope, agent and updated_at, and show no status badge. Do not invent one.
- A-29: with no project picked, send `scope: department` and the case_id from the department project picker. That picker returns only sample projects until a real provider path is approved, so flag it.
- A-30: map known `status` values (queued or working, answered, drafted) and treat any other text as the cannot-answer card. Show the backend text as the reason. If it is empty, show a plain "I can't answer this" with no invented reason.
- A-31: with no progress field, show a working card from the message `at` time. Poll every 3 seconds, back off to 10 seconds, and stop on a final status or when the person leaves.
- A-32: remove image attach from the UI, because the live API has no upload. Record this as a design deviation for client sign-off.

Rules the spec writer must follow:
- Every POST sends an idempotency_key (uuid), reused on retry.
- Model or agent text is rendered as plain text and grants nothing. Start work only through the saved draft and `…/start`, with the server's permission checks. Agent output never enables a button.
- An unknown value is not zero. Missing fields render as "Not provided", never as 0 or blank.
- Restricted (403) and stale-draft (409) responses show a reload state, not a retry loop.

Out: thread titles, step-by-step "what I did" lines, @mention kinds, message edit, image attachments and any backend change. Also out: SCR-04 Start work forms, SCR-02 Work item and the other lines' panels.

## Risk
Medium. This is a cross-layer contract change: the conversation, message and draft shapes change, and messages go async (202 plus polling). It sends agent-drafted text onward to start work, which is external-messaging and needs authority checks. No money, identity or migration is involved. Parts of the design are dropped (image attach, titles and status badges), so the client must see the result.

## Questions
None blocking. A-28 to A-32 stay open for the backend and are flagged for the PR description.
