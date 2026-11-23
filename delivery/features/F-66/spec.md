# Assistant conversations on the live API

> Tasks: FE-CONNECT-1 (SCR-05). Architecture: package v9, live API 1.22.0 (`contracts/psl-factory.openapi.json`, client types `src/api/live-schema.d.ts`). Design: approved canvas as in `design/review.json`, with the D-180 two-day-push exception (not a client approval); screens: SCR-05 (`SCR-05-desktop`, `-mobile`, `-desktop-thread`, `-mobile-thread`, `-desktop-draft-started`, `-mobile-draft-started`, `-desktop-cant`, `-mobile-cant`, `-desktop-working`, `-mobile-working`).

## Summary
- `/assistant` lists the person's live conversations (`GET /assistant/conversations`); `/assistant/[conversationId]` shows one question and answer per message from `GET /assistant/conversations/{id}`.
- Asking sends `POST …/messages` (202), then the thread polls until the message status settles, showing the working, answered, drafted or cannot-answer card.
- "New conversation" sends `POST /assistant/conversations` with the agent, a project (or department scope) and an idempotency key.
- The source picker (`available_sources`, `question_options`) replaces the @mention picker. A saved draft is the only way to start work, through `…/draft` then `…/start` with the exact `draft_version`.
- Parts the live API cannot fill are removed or degraded, never faked (image attach, titles, status badges, step lines). They are listed under "Questions for the design engineer".

## Context
Built today against the v7 mock contract, in the lane-a frontend (`/Users/Hunchoo/psl-factory-worktrees/lane-a/frontend`, from origin/main):
- `src/features/assistant/api.ts`: `fetchConversations`, `fetchConversation`, `fetchMentions`, `createConversation`, `postMessage`, `uploadImage` and the `write()` helper returning `ok | refused | unsure` outcomes (an `unsure` write is never resent silently).
- `types.ts` reads from `@/api/schema` (v7). Other files: `useConversationList.ts`, `useConversation.ts`, `useSend.ts`, `pending.ts`, `model.ts`, `labels.ts`, `AssistantHome.tsx`, `ConversationList.tsx`, `ThreadPage.tsx`, `Thread.tsx`, `ComposerBar.tsx`, `MentionPicker.tsx`, `DraftStart.tsx`, `SidePanel.tsx`, `AssistantContext.tsx`, `AssistantFrame.tsx`.
- Live client: `src/api/client.ts` exports `liveApi` (typed by `live-schema.d.ts`) and `call()`; `api` and `liveApi` share one CSRF token. Use `liveApi` for every call here and move `types.ts` to `@/api/live-schema`.
- Tests and mock: `tests/assistant*.test.ts(x)`, `tests/assistant-bridge.ts`, `mock/assistant.mjs`. The v7 mock stays only as test fixtures; the screen no longer depends on it.
- Agents: `/me` `assistant_agents` (`tola | chidi | zainab`), unchanged.

## Contract

All calls use `liveApi` + `call()`. Errors map: 401 signed-out state; 403 "restricted" reload state; 404 "not found" state; 409 stale reload state; 422 field message; 429, 5xx and network failure show the error state with a Retry that does not resend a write that may have landed (keep the `unsure` rule).

Every POST carries a `idempotency_key` (uuid v4) created when the person submits, stored with the pending action and reused unchanged on any retry of that same action; a new action gets a new key.

### GET /api/v1/assistant/conversations
- 200 `{ items: [{conversation_id, case_id, scope: "project"|"department", agent, updated_at, django_url}], as_of }`, at most 25, no paging, no title, no status.
- Row: agent avatar and name, scope word ("Project" or "Department"), and "Updated <time in WAT>". No title, no status badge, no status line (A-28). The row opens `/assistant/<conversation_id>`; `django_url` is never linked.
- Coverage line "As of <as_of in WAT>" and "<n> conversations loaded". The screen never claims a total; the server gives none.
- Empty: the board's empty state with the New conversation button. A body without an `items` array is a load error, never "no conversations".

### POST /api/v1/assistant/conversations
- Request `{ agent, case_id, idempotency_key, scope? }`. 200 returns the conversation row; navigate to `/assistant/<conversation_id>`.
- With a project chosen (from `GET /api/v1/projects` or the project's own entry point): `scope: "project"`, that `case_id`. With none chosen: `scope: "department"` and the `case_id` of the project picker's first choice offered for department chat (A-29); the picker's choices come from the backend and may be sample projects only; show them as the server returns them.
- Errors: 403 "You can't use this assistant here"; 422 shows the server message; a second submit with the same key returns the same conversation.
- Fixture: `{"agent":"tola","case_id":"7f1c0f3e-2b64-4f0e-9a3b-0d1c5e6f7a88","idempotency_key":"3b9f1f0e-5c1a-4f4c-8f0b-2f6d8a1c9e11","scope":"project"}`.

### GET /api/v1/assistant/conversations/{conversation_id}
- 200 `{ conversation_id, case_id, scope, agent, updated_at, django_url, messages[≤30], available_sources[{key,label,django_url}], question_options[string] }`; message `{id, question, status, answer|null, sources[{label,django_url}], at, started_work_id|null, draft_url|null, transfer_url|null}`.
- Each message renders as the question bubble (person) then the answer bubble (agent), both as plain text, never HTML or markdown links. Sources render as chips from `sources[].label`; a source chip is a link only when `django_url` is a same-origin path the shared helper in `model.ts` can map to a frontend route; otherwise it is a plain label.
- Status mapping (A-30, one function `messageState(status, answer)` in `model.ts`, case-insensitive): `queued|working|pending|running` give `working`; `answered|complete|completed` with a non-empty `answer` give `answered`; `drafted|draft` give `drafted`; every other value, or an answered status with an empty answer, gives `cant` and shows the backend `status` text as the reason; if the text is not a human sentence (empty or one token) show only "I can't answer this." No reason is invented.
- `working` card: "Working on it" with "Asked at <at in WAT>"; no step lines, no progress bar (A-31). Polling: while any message is `working`, re-read the conversation every 3 s for 5 reads, then every 10 s; stop when no message is working, on unmount, when the tab is hidden (resume on visible), and on any 401, 403, 404. After 5 minutes of polling stop and show "Still working. Reload to check again." with a Reload button.
- Unknown is not zero: a missing `at`, `answer` or label shows "Not provided".
- Fixture (cant): `{"id":"a1…","question":"What did we bill Ojo Foods?","status":"cannot answer: no billing source selected","answer":null,"sources":[],"at":"2026-11-23T09:10:00Z","started_work_id":null,"draft_url":null,"transfer_url":null}`.

### POST /api/v1/assistant/conversations/{conversation_id}/messages
- Request `{ text (1 to 4000), idempotency_key, source_keys[≤5] }`; 202 `{ message_id, status }`. No attachments, no mentions.
- The composer shows the person's text at once as "Sending…" and the working card after the 202, then polls. Empty or whitespace text is not sent; over 4000 characters is blocked with a count. A 6th source is blocked ("Up to 5 sources").
- Source picker: opens from the composer's source control, lists `available_sources` (label only, key never shown), multi-select to 5, selected sources show as chips above the composer and are sent as `source_keys`. `question_options` show as suggestion chips that fill the composer text when tapped; they never send by themselves.
- Errors: 403 restricted card and composer disabled; 409/422 show the server message and keep the typed text; 429 "Too many questions. Wait a moment."; `unsure` shows "We couldn't confirm it was sent. Check the thread before asking again." and re-reads the conversation (no automatic resend).

### POST /api/v1/assistant/turns/{turn_id}/transfer
- Request `{ agent }`; 200 returns a conversation row (the target agent's conversation). Offered on a message with non-null `transfer_url`, as "Pass to <agent>" with only the agents in `/me` `assistant_agents` other than the current one. On success navigate to the returned conversation. 403 shows "You can't pass this to that assistant." `turn_id` is the message `id` (assumption 2).

### Draft: GET and POST /api/v1/assistant/turns/{turn_id}/draft, GET …/draft-options, POST …/start
- Shown only on a message with non-null `draft_url`. Read `GET …/draft` → `{line: "planning/v1"|"pmo-finance/v1", case_id, case_revision, draft_version|null, draft|null, started_work_id|null, django_url}`.
  - `planning/v1` fields: `reference` (text, ≤100), `packet` (source id). `pmo-finance/v1` fields: `reference`, `handoff`, `coverage`, `preparation`, `invoice` (source ids or null), `mode` (`completion` | `existing-preparation/v1`), `due_date` (date or null). Any other `line` shows "This draft can't be edited here" and a link-less note; no start button.
  - Source-id fields use `GET …/draft-options` (`fields[{key,label}]`, `items[{id,label}]`, `next_before` for "Show more"); the person picks by label, the id is never shown. Null shows "Not provided".
- "Save draft": `POST …/draft` with `{line, case_revision, draft_version, draft, background?}`; the response replaces the local draft, including the new `draft_version`.
- "Start work": enabled only when the draft has been saved and the form is unchanged since the save (`draft_version` not null and equal to the last saved version); sends `POST …/start` with the same body. 200 `{work_id, state, revision}` shows the "draft-started" board state with a link to `/work/<work_id>`. `started_work_id` non-null on load shows the started state and no Start button.
- 409 (stale `case_revision` or `draft_version`): the form is locked with "This draft is out of date. Reload to see the latest." and a Reload button; no retry loop, no auto-resave. 403: "You can't start this work."; 422: server message by field.
- Authority: no assistant text, source label or `draft_url` content enables, fills or starts anything. Draft values come only from what the person typed or picked, or from the saved server draft.

### GET /api/v1/projects/{case_id}/intake-sources
- Used by the draft form only if `draft-options` has `source_options_url` null and the form needs project sources; same response shape (`case_revision, fields, field, items, next_before`). If not needed it is not called.

## Lanes
- Frontend lane owns everything under `src/features/assistant/*`, `src/app/assistant/**`, `tests/assistant*`, `e2e/assistant*`, the assistant mock `mock/assistant.mjs`, and the assistant typing in `src/api/*` only for imports (no hand-edits to `live-schema.d.ts`).
- Backend lane: no change. Out of scope; A-28 to A-32 stay open for it.
- Integration owner: owns shared files `src/api/client.ts`, `src/api/errors.ts`, `src/shell/*` and the `/me` hook; the builder changes none of them. If a change is needed, ask.

## Acceptance criteria
1. `/assistant` lists live conversations as scope, agent, "Updated <WAT time>", with "As of" and "<n> loaded" and no title or status badge — verify: mock or dev server returns 3 items; page shows 3 rows, no badge, no title.
2. An empty list shows the board's empty state; a body with no `items` shows the load error with Retry, not the empty state — verify: component test for both bodies.
3. New conversation sends `{agent, case_id, idempotency_key, scope}` once; submitting twice quickly sends one request; a retry after a network error reuses the same key — verify: test asserts request bodies and key equality.
4. With no project chosen the request has `scope: "department"` — verify: test on the request body.
5. Sending a question posts `{text, idempotency_key, source_keys}` and gets 202; the thread shows "Sending…" then the working card with "Asked at <time>" — verify: `tests/assistant-send.test.tsx`.
6. While a message is working the thread re-reads at 3 s, then 10 s, stops when status settles, when the person leaves the page, and on 403 — verify: fake-timer test counting calls.
7. Status mapping: working, answered, drafted and an unknown status each render the matching card; an unknown status shows its text as the reason; an empty reason shows only "I can't answer this." — verify: table test on `messageState`.
8. Answer text containing `<script>`, markdown links or "approve and send" renders as plain text and enables no control — verify: test with that answer; DOM has no script or anchor from the text.
9. Source picker lists `available_sources` labels, allows 5, blocks a 6th, sends keys never labels; question options fill the composer and do not send — verify: test.
10. Composer blocks empty text and text over 4000 characters, keeping the typed text — verify: test.
11. 403 on a conversation or send shows the restricted state, with composer disabled and no retry loop; 404 shows not found — verify: test counts calls after 403 (no repeats).
12. Draft: Start is disabled until saved; the start body carries the exact saved `draft_version`; editing after a save disables Start again — verify: test.
13. A 409 on save or start locks the form with Reload, makes no second request — verify: test.
14. Start 200 shows the started state with a link to `/work/<work_id>`; a message with `started_work_id` loads as started without a Start button — verify: test.
15. Unknown draft `line` shows no Start button; null fields show "Not provided", never 0 or blank — verify: test.
16. Pass to another agent offers only `/me` `assistant_agents` other than the current one, and navigates to the returned conversation — verify: test.
17. No image attach control, upload call or `/assistant/mentions` call exists in the assistant code — verify: `grep -rn "uploads\|mentions" src/features/assistant` returns nothing.
18. No hand-written pixel or colour values are added; the existing assistant tokens and CSS classes are reused — verify: diff of `assistant.css` adds no new literal colours.
19. Agent or source `django_url` is never rendered as an absolute or `//` link — verify: helper test with `https://x`, `//x`, `javascript:` and `/work/1/`.

## Out of scope
- Backend changes, answers to A-28 to A-32, image attachments, thread titles, status badges, step-by-step lines, @mention kinds, message edit, per-line panels, SCR-04 Start work forms, SCR-02 Work item.
- Other draft lines than `planning/v1` and `pmo-finance/v1`.
- A real provider path for the department project picker.
- Speech input stays as built (on-device typing only, F-48).

## Questions for the design engineer
1. Image attach (board shows it on the composer). The live API has no upload. Options: (a) remove the control entirely and record a deviation (recommended); (b) keep it disabled with "Not available yet"; (c) keep it and send nothing, which would drop the person's image silently, so not advised.
2. Thread titles and status badges in the list (boards show a title and a Working / Answered / Can't / Drafted tag). Live rows have neither. Options: (a) show "<Agent> · Project|Department · Updated <time>" and no badge (recommended); (b) keep a badge slot that fills only after opening the thread; (c) fetch every thread to derive a badge, which is up to 25 extra reads per list view.
3. "What I did" step lines under an answer (boards draw them). No live field. Options: (a) hide them (recommended); (b) show the sources as the only evidence line; (c) wait for the backend.
4. Polling and the working card (board "working" shows run start and progress). Options: (a) working card with "Asked at <time>" and polling at 3 s then 10 s (recommended); (b) manual "Check again" button only; (c) polling with no card text beyond a spinner.
5. @mention picker (project, work, document, person). Replaced by the source picker (labels only). Options: (a) replace as built (recommended); (b) keep a text-only "#" shortcut that opens the same source list; (c) hide the control until sources are richer.
6. Cannot-answer card (board shows a reason and buttons). Live gives status text only. Options: (a) show the text as the reason, with a "Ask a different question" focus button only (recommended); (b) drop the reason line; (c) keep the board's suggestion buttons using `question_options`.
7. Separate person and agent bubbles with edit (board). Live has one object per question. Options: (a) two bubbles per message, no edit (recommended); (b) one card with question above answer; (c) keep edit disabled with a tooltip.
8. Conversation list paging (board shows page size). Live has none, max 25. Options: (a) remove the size control and show "<n> loaded" (recommended); (b) keep a size control that cuts the client list; (c) show "Latest 25" as a fixed label.

## Conflicts with the boards
Places where this spec adds, moves or removes something a board draws (same as the questions above, with the recommendation first):
- Remove: image attach on the composer, titles and status badges in the list, "what I did" lines, the @mention picker, edit on messages, list size control.
- Replace: @mention picker with a source picker; per-bubble run card with a "working" card showing only the asked time; cannot-answer buttons with one focus button.
- Add: scope word ("Project" or "Department"); "Pass to <agent>" on an answer; draft save-then-start with "Show more" source lists; "Reload" states for 403/409 and after 5 minutes of polling.
Recommendation: the design engineer decides all of these once before the build starts.

## Assumptions
1. Department scope sends the first case offered by the department project picker (A-29), because the sources do not say otherwise.
2. `turn_id` for transfer, draft and start is the message `id` (the spec names no other field); if `draft_url` or `transfer_url` ends with a different id, use that id and keep the message `id` as the fallback.
3. "Final" statuses are the lists in the status mapping; anything else is shown as cannot-answer, per readiness.
4. Poll cap of 5 minutes and 5 fast reads are a judgement call; no backend rate limit is documented.
5. Times display in WAT, matching F-61.
6. Draft form fields follow the live schema only; no per-line field copy exists in the boards, so labels use `draft-options` `fields[].label` where given and the key words otherwise.
7. The project chooser for a new conversation uses the existing `GET /api/v1/projects` list; if the person is on a project page, that project is preselected.
