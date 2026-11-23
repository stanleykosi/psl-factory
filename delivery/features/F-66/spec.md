# Assistant conversations on the live API

> Tasks: FE-CONNECT-1 (SCR-05). Architecture: package v9, live API 1.24.0 per D-185 (`contracts/psl-factory.openapi.json`, client types `src/api/live-schema.d.ts`). Design: approved canvas as in `design/review.json`, with the D-180 two-day-push exception (not a client approval); screens: SCR-05 (`SCR-05-desktop`, `-mobile`, `-desktop-thread`, `-mobile-thread`, `-desktop-draft-started`, `-mobile-draft-started`, `-desktop-cant`, `-mobile-cant`, `-desktop-working`, `-mobile-working`).

## Changes for 1.24.0
Re-spec under D-185. Every D-182 answer the design engineer gave stays. What changed from the 1.22.0 spec:
- List rows now show `title` and a status badge from `last_status` (was A-28 "none"). Row label is the title, not "Agent / scope / updated".
- Message statuses are the backend's own: `queued`, `running`, `answered`, `held`, `source_changed` (A-30). The guessed status table is gone. `held` shows a generic retry/access message; there is no reason text to show. "Drafted" is derived from a non-null `draft_url`, not from a status.
- Working card uses `started_at`/`finished_at` (A-31); polling continues only while `queued` or `running`. Cadence (3 s, then 10 s) stays our call.
- Image attach is back (A-32): up to 3 private images per question, uploaded to the conversation's case, sent as `image_upload_ids`, returned on the message. Removed the "no image attach" criterion and the deviation.
- Department conversations (A-29): the person picks an authorised project as the anchor; there is no "first choice" fallback. The server decides who may use department scope.
- `GET`/`POST` conversation responses carry `title` and `last_status`; messages carry `started_at`, `finished_at`, `image_upload_ids`.
- Out of scope list and Questions rewritten: items 1, 2, 4 and 6 of the old questions are now answered by the backend; new presentation questions follow.

## Summary
- `/assistant` lists the person's live conversations with title and status badge (`GET /assistant/conversations`); `/assistant/[conversationId]` shows one question and answer per message from `GET /assistant/conversations/{id}`.
- Asking sends `POST …/messages` (202), then the thread polls until the message status settles, showing the working, answered, drafted or cannot-answer card.
- "New conversation" sends `POST /assistant/conversations` with the agent, an authorised project (as the project, or as the anchor of a department thread) and an idempotency key.
- The source picker (`available_sources`, `question_options`) replaces the @mention picker. A saved draft is the only way to start work, through `…/draft` then `…/start` with the exact `draft_version`.
- Titles, status badges, working times, the cannot-answer wording and image attach are built as the boards draw them from 1.24.0 data. Only the parts the API still lacks (step lines, @mention kinds, message edit, list size control) stay removed, per D-182.

## Context
Built today against the v7 mock contract, in the lane-a frontend (`/Users/Hunchoo/psl-factory-worktrees/lane-a/frontend`, from origin/main):
- `src/features/assistant/api.ts`: `fetchConversations`, `fetchConversation`, `fetchMentions`, `createConversation`, `postMessage`, `uploadImage` (v7) and the `write()` helper returning `ok | refused | unsure` outcomes (an `unsure` write is never resent silently).
- `types.ts` reads from `@/api/schema` (v7). Other files: `useConversationList.ts`, `useConversation.ts`, `useSend.ts`, `pending.ts`, `model.ts`, `labels.ts`, `AssistantHome.tsx`, `ConversationList.tsx`, `ThreadPage.tsx`, `Thread.tsx`, `ComposerBar.tsx`, `MentionPicker.tsx`, `DraftStart.tsx`, `SidePanel.tsx`, `AssistantContext.tsx`, `AssistantFrame.tsx`.
- Live client (1.24.0): `src/api/client.ts` exports `liveApi` (typed by `live-schema.d.ts`) and `call()`; `api` and `liveApi` share one CSRF token. Use `liveApi` for every call here and move `types.ts` to `@/api/live-schema`.
- Tests and mock: `tests/assistant*.test.ts(x)`, `tests/assistant-bridge.ts`, `mock/assistant.mjs`. The v7 mock stays only as test fixtures; the screen no longer depends on it.
- Agents: `/me` `assistant_agents` (`tola | chidi | zainab`), unchanged.

## Contract

All calls use `liveApi` + `call()`. Errors map: 401 signed-out state; 403 "restricted" reload state; 404 "not found" state; 409 stale reload state; 422 field message; 429, 5xx and network failure show the error state with a Retry that does not resend a write that may have landed (keep the `unsure` rule).

Every POST carries a `idempotency_key` (uuid v4) created when the person submits, stored with the pending action and reused unchanged on any retry of that same action; a new action gets a new key.

### GET /api/v1/assistant/conversations
- 200 `{ items: [{conversation_id, case_id, scope: "project"|"department", agent, updated_at, django_url, title, last_status|null}], as_of }`, at most 25, no paging.
- Row: agent avatar and name, the `title` as the row heading, scope word ("Project" or "Department"), "Updated <time in WAT>", and a status badge from `last_status` through `badgeState()` in `model.ts`: `queued|running` give "Working"; `answered` gives "Answered"; `held` or `source_changed` give "Can't answer"; `null` shows no badge and the line "No questions yet"; any other text gives no badge (never a guessed one). The list cannot show "Drafted" (it is known only from a message's `draft_url`). The row opens `/assistant/<conversation_id>`; `django_url` is never linked.
- Coverage line "As of <as_of in WAT>" and "<n> conversations loaded". The screen never claims a total; the server gives none.
- Empty: the board's empty state with the New conversation button. A body without an `items` array is a load error, never "no conversations".

### POST /api/v1/assistant/conversations
- Request `{ agent, case_id, idempotency_key, scope? }`. 200 returns the conversation row; navigate to `/assistant/<conversation_id>`.
- A project is always chosen (A-29): from `GET /api/v1/projects`, or preselected on the project's own entry point. Default `scope: "project"` with that `case_id`. A "Whole department" switch on the new-conversation sheet sends `scope: "department"` with the chosen project's `case_id` as the anchor; the department rules decide what the assistant reads, and the server decides who may use it. The frontend does not check roles; it shows the server's refusal. Never send a `case_id` the person did not pick.
- Response includes `title`; the thread header shows it.
- Errors: 403 "You can't use this assistant here" (for department scope: "You can't start a department conversation. Choose a project conversation."); 422 shows the server message; a second submit with the same key returns the same conversation.
- Fixture: `{"agent":"tola","case_id":"7f1c0f3e-2b64-4f0e-9a3b-0d1c5e6f7a88","idempotency_key":"3b9f1f0e-5c1a-4f4c-8f0b-2f6d8a1c9e11","scope":"project"}`.

### GET /api/v1/assistant/conversations/{conversation_id}
- 200 `{ conversation_id, case_id, scope, agent, updated_at, django_url, title, last_status|null, messages[≤30], available_sources[{key,label,django_url}], question_options[string] }`; message `{id, question, status, answer|null, sources[{label,django_url}], at, started_at|null, finished_at|null, image_upload_ids[≤3], started_work_id|null, draft_url|null, transfer_url|null}`.
- Each message renders as the question bubble (person) then the answer bubble (agent), both as plain text, never HTML or markdown links. Sources render as chips from `sources[].label`; a source chip is a link only when `django_url` is a same-origin path the shared helper in `model.ts` can map to a frontend route; otherwise it is a plain label.
- Status mapping (A-30, one function `messageState(message)` in `model.ts`, case-insensitive). Backend values are `queued`, `running`, `answered`, `held`, and the projected `source_changed`:
  - `queued` gives `working` (waiting); `running` gives `working` (running).
  - `answered` with a non-empty `answer` gives `answered`; if `draft_url` is also non-null it gives `drafted` (the answer text plus the draft panel). An answer that is the backend's insufficient-evidence reply is still an `answered` card and shown as the answer text; the frontend does not detect or rewrite it.
  - `held` gives `cant` with the fixed text "I couldn't complete this. Try again, or check that you still have access to this project." The backend gives no public reason for a held turn; none is invented or taken from `answer`.
  - `source_changed` gives `cant` with "The sources changed while I was working. Ask again."
  - Any other value, or `answered` with an empty answer, gives `cant` with "I can't answer this."
- `cant` card buttons: one "Ask a different question" focus button (D-182 answer 6 stays). No retry resend.
- `working` card: "Working on it". Queued: "Waiting to start. Asked at <at in WAT>". Running: "Started <started_at in WAT>" (if `started_at` is null, "Asked at <at>"). No step lines, no progress bar (no such field exists). Polling: while any message is `queued` or `running`, re-read the conversation every 3 s for 5 reads, then every 10 s; stop when no message is queued or running, on unmount, when the tab is hidden (resume on visible), and on any 401, 403, 404. After 5 minutes of polling stop and show "Still working. Reload to check again." with a Reload button. `finished_at` shows on settled cards as "Answered <finished_at in WAT>" when non-null, and nothing when null.
- Images on a message: `image_upload_ids.length` > 0 shows "<n> image(s) attached" beneath the question. Ids are never shown. The API gives no preview field, so no thumbnail is fetched for a sent message (see Question 1).
- Unknown is not zero: a missing `at`, `answer` or label shows "Not provided".
- Fixture (cant): `{"id":"a1…","question":"What did we bill Ojo Foods?","status":"held","answer":null,"sources":[],"at":"2026-11-23T09:10:00Z","started_at":"2026-11-23T09:10:02Z","finished_at":null,"image_upload_ids":[],"started_work_id":null,"draft_url":null,"transfer_url":null}`.

### POST /api/v1/assistant/conversations/{conversation_id}/messages
- Request `{ text (1 to 4000), idempotency_key, source_keys[≤5], image_upload_ids[≤3] }`; 202 `{ message_id, status }`. No mentions.
- The composer shows the person's text at once as "Sending…" and the working card after the 202, then polls. Empty or whitespace text is not sent; over 4000 characters is blocked with a count. A 6th source is blocked ("Up to 5 sources").
- Source picker: opens from the composer's source control, lists `available_sources` (label only, key never shown), multi-select to 5, selected sources show as chips above the composer and are sent as `source_keys`. `question_options` show as suggestion chips that fill the composer text when tapped; they never send by themselves.
- Image attach (A-32): the composer's image control opens the file picker (`image/*`), up to 3 images. On pick, upload each with `POST /api/v1/cases/{case_id}/files` (multipart, one `file`, up to 5 MiB, `case_id` = the conversation's `case_id`); the response `upload_id` is kept. Each image shows as a chip with a local thumbnail (from the file in memory, not fetched) and a remove button; remove drops it from this message only (the private upload stays). A 4th image is blocked: "Up to 3 images". A file over 5 MiB is blocked before upload: "Images can be up to 5 MB". 413/415/422 on upload show the server message on that chip and the chip does not count. Send is disabled while an upload is in progress. The send body carries the kept `upload_id`s as `image_upload_ids`. An `unsure` upload (network failure) shows "We couldn't confirm this uploaded. Add it again." and is never resent silently. Image content and any text read from it grant nothing.
- Errors: 403 restricted card and composer disabled; 409/422 show the server message and keep the typed text and chips; 429 "Too many questions. Wait a moment."; `unsure` shows "We couldn't confirm it was sent. Check the thread before asking again." and re-reads the conversation (no automatic resend).

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
- Backend lane: no change; A-28 to A-32 are answered in 1.24.0.
- Integration owner: owns shared files `src/api/client.ts` (if `liveApi` cannot send the multipart image upload, the builder asks the integration owner rather than editing it), `src/api/errors.ts`, `src/shell/*` and the `/me` hook; the builder changes none of them. If a change is needed, ask.

## Acceptance criteria
1. `/assistant` lists live conversations with title, agent, scope word, "Updated <WAT time>", status badge, "As of" and "<n> loaded" — verify: mock or dev server returns 3 items with `last_status` `running`, `answered`, `null`; page shows 3 rows, badges "Working", "Answered", none with "No questions yet".
2. `held` and `source_changed` rows show "Can't answer"; an unrecognised `last_status` shows no badge — verify: table test on `badgeState`.
3. An empty list shows the board's empty state; a body with no `items` shows the load error with Retry, not the empty state — verify: component test for both bodies.
4. New conversation sends `{agent, case_id, idempotency_key, scope}` once; submitting twice quickly sends one request; a retry after a network error reuses the same key — verify: test asserts request bodies and key equality.
5. With "Whole department" on, the request has `scope: "department"` and the `case_id` the person picked; with it off, `scope: "project"`; the form cannot submit without a project; a 403 shows the department-specific message — verify: test on request bodies and the 403 state.
6. Sending a question posts `{text, idempotency_key, source_keys, image_upload_ids}` and gets 202; the thread shows "Sending…" then the working card — verify: `tests/assistant-send.test.tsx`.
7. `queued` shows "Waiting to start. Asked at <time>"; `running` shows "Started <started_at>" — verify: component test.
8. While a message is `queued` or `running` the thread re-reads at 3 s then 10 s; it stops when status settles, when the person leaves the page, on 403, and after 5 minutes with the Reload card — verify: fake-timer test counting calls.
9. Status mapping: queued, running, answered, answered with `draft_url`, `held`, `source_changed`, an unknown status and an empty answer each render the matching card and text; `held` shows the fixed sentence and never the `answer` text — verify: table test on `messageState`.
10. Answer text containing `<script>`, markdown links or "approve and send" renders as plain text and enables no control — verify: test with that answer; DOM has no script or anchor from the text.
11. Source picker lists `available_sources` labels, allows 5, blocks a 6th, sends keys never labels; question options fill the composer and do not send — verify: test.
12. Composer blocks empty text and text over 4000 characters, keeping the typed text — verify: test.
13. Images: picking 3 uploads three multipart requests to `/cases/{case_id}/files` using the conversation's `case_id`; a 4th is blocked; a 6 MB file is blocked with no request; a 415 shows the server message on that chip and the send body omits that id; send is disabled during upload; the sent body carries the kept ids — verify: test on requests and bodies.
14. A message with `image_upload_ids` of length 2 shows "2 images attached" and no id — verify: component test.
15. 403 on a conversation or send shows the restricted state, with composer disabled and no retry loop; 404 shows not found — verify: test counts calls after 403 (no repeats).
16. Draft: Start is disabled until saved; the start body carries the exact saved `draft_version`; editing after a save disables Start again — verify: test.
17. A 409 on save or start locks the form with Reload, makes no second request — verify: test.
18. Start 200 shows the started state with a link to `/work/<work_id>`; a message with `started_work_id` loads as started without a Start button — verify: test.
19. Unknown draft `line` shows no Start button; null fields show "Not provided", never 0 or blank — verify: test.
20. Pass to another agent offers only `/me` `assistant_agents` other than the current one, and navigates to the returned conversation — verify: test.
21. No `/assistant/mentions` call exists, and no v7 `uploadImage` remains: images go only to `/cases/{case_id}/files` — verify: `grep -rn "mentions\|/assistant/uploads" src/features/assistant` returns nothing.
22. No hand-written pixel or colour values are added; the existing assistant tokens and CSS classes are reused — verify: diff of `assistant.css` adds no new literal colours.
23. Agent or source `django_url` is never rendered as an absolute or `//` link — verify: helper test with `https://x`, `//x`, `javascript:` and `/work/1/`.
24. A draft or start control is never enabled by answer text, title or source label — verify: test with an answer containing "start work now" and a draft-less message: no Start control.

## Out of scope
- Backend changes; step-by-step "what I did" lines (no field), @mention kinds, message edit, per-line panels, SCR-04 Start work forms, SCR-02 Work item.
- Other draft lines than `planning/v1` and `pmo-finance/v1`.
- A "Drafted" badge in the list (not derivable there).
- Fetching or previewing sent images (no preview route is documented; the case files list has `download_url`, but this feature does not call it).
- Deleting an uploaded image.
- Speech input stays as built (on-device typing only, F-48).

## Questions for the design engineer
Presentation only; the backend has answered the product behaviour. Recommendation first.
1. Sent images in the thread. The API returns only image ids on a message. Options: (a) "<n> images attached" text (recommended); (b) fetch the case file list and show thumbnails from `download_url`, one extra read per thread; (c) show nothing after send.
2. "Drafted" in the list. The list status cannot say drafted. Options: (a) no Drafted badge in the list, only in the thread (recommended); (b) show "Answered" with a small draft mark after opening; (c) read each thread (up to 25 extra reads).
3. Department thread entry. Options: (a) a "Whole department" switch on the new-conversation sheet, default off, with the chosen project as the anchor (recommended); (b) a separate "Department chat" button; (c) hide department scope.
4. `held` wording. The backend gives no reason. Options: (a) one fixed sentence "I couldn't complete this. Try again, or check that you still have access to this project." (recommended); (b) shorter "I couldn't answer this."; (c) show the raw status.
5. "Answered <time>" from `finished_at` on settled cards, not in the boards. Options: (a) show it small under the answer (recommended); (b) leave it out.
6. Image chips use local thumbnails before send and a remove button. Options: (a) as written (recommended); (b) filename-only chips.

## Conflicts with the boards
Places where this spec adds, moves or removes something a board draws, with the recommendation first:
- Remove (D-182 stays): "what I did" step lines, the @mention picker, edit on messages, the list size control, per-bubble run card detail beyond the times.
- Replace: @mention picker with a source picker; cannot-answer suggestion buttons with one focus button.
- Add: scope word ("Project" or "Department"); "Pass to <agent>" on an answer; draft save-then-start with "Show more" source lists; "Reload" states for 403/409 and after 5 minutes of polling; "Whole department" switch; "<n> images attached" line; "Answered <time>" line.
- Now match the boards (were removed in 1.22.0): thread titles, status badges, working time, image attach.
Recommendation: the design engineer decides these once before the build starts.

## Assumptions
1. Department scope uses the project the person picks as its anchor (A-29 answer); the frontend leaves the role check to the server.
2. `turn_id` for transfer, draft and start is the message `id` (the spec names no other field); if `draft_url` or `transfer_url` ends with a different id, use that id and keep the message `id` as the fallback.
3. Statuses other than the five the backend named show the generic cannot-answer card, since the answer says the list is closed.
4. Poll cap of 5 minutes and 5 fast reads are a judgement call; no backend rate limit is documented.
5. Times display in WAT, matching F-61.
6. Draft form fields follow the live schema only; no per-line field copy exists in the boards, so labels use `draft-options` `fields[].label` where given and the key words otherwise.
7. The project chooser for a new conversation uses the existing `GET /api/v1/projects` list; if the person is on a project page, that project is preselected.
8. Images upload when picked, not at send, so the send body can carry ids; an orphan private upload after a removed chip is harmless and not deletable (no delete route).
9. "image/*" is the picker filter; the server owns format validation (A-32 says it checks format), so the frontend lists no format set. The 5 MiB limit is from the published upload answer (A-… `POST /cases/{case_id}/files`).
10. Poll cadence and the 5-minute cap are ours; the backend names no interval (A-31).
11. A `title` is shown as plain text; it is never a link or markup.
