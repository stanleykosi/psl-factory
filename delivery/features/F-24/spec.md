# The Assistant: pick an agent, ask, watch it work, read the answer with its steps and sources, and start the normal work item from its draft (contract mock only)

> Tasks: FE-ASSISTANT, part 1 (R-ASSISTANT; acceptance A-ASSISTANT and A-ASSISTANT-THREADS, frontend half, with the Start work tests of F-09 and M2A kept green). Architecture: package `architecture/packages/v7` (manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; E-ME, E-CONVERSATIONS, E-CONVERSATION, E-CONVERSATION-NEW, E-MESSAGE, E-MENTION-OPTIONS and E-WORK-START are typed in `frontend/src/api/schema.d.ts`, and this feature changes no generated type). FE-ASSISTANT is at `architecture/packages/v7/delivery.md:3075` with no unresolved gates. Design: approved canvas version 1794581312-b166. `design.py check --project .` was run for this spec and returned `EXCEPTION`, `passes: true` (D-89 "+ Start" frame change only). Screens: SCR-05, 8 artboards: `SCR-05-{desktop,mobile}`, `-working`, `-thread`, `-draft-started` (files in `design/canvas/project/`). Decisions consumed: D-ASSISTANT-VIEW and D-CONVERSATION-MODEL, both `proposed` (contract mock only, see "Limits"). Shape modelled on `delivery/features/F-21/spec.md`. Readiness: `delivery/features/F-24/readiness.md` (READY, PRODUCT-ACCEPTANCE required).

## Outcome
A signed-in person opens the Assistant and picks an agent they may talk to (only from `E-ME.assistant_agents`). They ask a question or ask for a draft. They see the agent's steps as it works (done, now, next, with the record each step used), then the answer with its sources. If the agent drafted something, they press the draft's start button ("Start this invoice"). That opens the **normal Start work drawer, prefilled** from `draft.start`; the person checks it and confirms, so the work item is theirs. The agent never approves, sends or pays. Nothing reaches a provider, a client or a real backend.

## Boards (8)

| Board | State | Page | How it is reached |
|---|---|---|---|
| `SCR-05-desktop` (1440) | default: conversation list, Talk to Tola/Chidi/Zainab, Tola's home with composer, side panel "Tola is ready." | `/assistant` (persona `pm`) | live URL |
| `SCR-05-mobile` (390) | default on a phone: agent row, Tola's home, composer | `/assistant` | live URL |
| `SCR-05-desktop-working` | thread CV-2405 "Planning packet · Tamarind Loans", WORKING · STEP 3 OF 5 | `/assistant/CV-2405` | live URL, first read after a mock reset |
| `SCR-05-mobile-working` | the same on a phone | `/assistant/CV-2405` | same |
| `SCR-05-desktop-thread` | thread CV-2401 "Invoice · Harmattan Bank M2": ask, hand-off note, 3 STEPS · DONE, answer, sources, draft card | `/assistant/CV-2401` | live URL |
| `SCR-05-mobile-thread` | the same on a phone | `/assistant/CV-2401` | same |
| `SCR-05-desktop-draft-started` | CV-2401 after the start: "Started INV-0415." and "Open the work item" | `/assistant/CV-2401` | driver: press "Start this invoice", confirm in the Start work drawer, wait for the re-read, freeze |
| `SCR-05-mobile-draft-started` | the same on a phone | `/assistant/CV-2401` | same driver at 390 |

The `cant` boards (`SCR-05-{desktop,mobile}-cant`) are a later feature. Nothing is tuned to them.

## Conflicts with the boards (for the design engineer, before the build)

"Recommend" is what this spec builds if no answer comes. Every exception's `approved_by` is `"builder proposal, pending design engineer"` until the design engineer signs it. Items 1 to 6 change what the page offers and need an answer. The rest are exceptions to confirm.

### Controls the boards draw that this feature does not make live
1. **"Speak your request" microphone (desktop composer only; the phone boards do not draw it, contrary to readiness).** D-SPEECH-INPUT is open. Recommend: draw the 44px button as the desktop board does, but with `aria-disabled="true"` (still focusable, so the reason can be read). Its accessible name is "Speak your request", and a `Tooltip` reads "Not available yet". It has no click handler. There is no `SpeechRecognition`, `webkitSpeechRecognition` or `getUserMedia` anywhere in `src/`. Exception category `held decision`, citing D-SPEECH-INPUT and D-96. **Builder proposal, pending design engineer.** Fallback: leave it out. FE-ASSISTANT-SPEECH stays unbuilt.
2. **"Edit draft" (desktop thread and draft-started).** No operation exists (G-SCR05-2). Recommend: **leave it out**. The person edits the draft's values in the Start work drawer it opens. Exception `no field`. **Builder proposal, pending design engineer.** This needs a product answer later.
3. **"+" Attach a file (desktop and phone composers).** Readiness binding rule 2 says the composer sends text and mentions only, and E-MESSAGE has no file field. Recommend: **leave it out**. Exception `no field`. **Builder proposal, pending design engineer.**
4. **Shortcut prompts** ("Create an invoice", "Draft a SOW", "Ask about a project", "Ask about pay" on desktop; the first three on the phone). On the board they open a fixed thread and switch agent ("Create an invoice" picks Chidi). No field carries them. Hard-coding them would put agent routing in the frontend and claim abilities the backend has not confirmed (readiness rule 8). Recommend: **leave them out**, exception `no field`. Contract proposal: `assistant_agents` as objects with `suggestions[]` (extends G-SCR05-6). **Builder proposal, pending design engineer.** Option B for the design engineer: each prompt only puts its label into the composer, with no agent switch and no send.
5. **The start button after the start (desktop draft-started).** The board still shows "Start this invoice" and "Edit draft" above the green "Started" line. Recommend: once `draft.started` exists, **hide the start button** (a second start is a 409 anyway) and show the started line. Exception `missing on page`. The side panel's "Chidi has a draft ready for you to check." also stays on that board. Recommend: after the start, the side panel reads "Chidi answered from records you can see." (the board's own sentence for an answered thread). Exception `wording`.
6. **The started line.** Desktop: "Started INV-0415 · now at its first review station. Open the work item". Phone: "Started INV-0415. It's now at Finance review. Nothing goes to the client until a Finance Lead approves it. Chidi will tell you if Finance returns it." and "Open INV-0415". Only `draft.started{work_id, reference}` exists, and the rest are claims about the line that the frontend cannot check. Recommend: **"Started INV-0415." and the link "Open the work item"** (to `/work/{work_id}`) at both widths. Everything else is exception `no field`. Contract proposal: `draft.started.note` (backend-composed).

### Board vs contract and frame
7. **Mention chips on the thread** ("@Harmattan Bank", "#Milestone 2" in the composer). E-CONVERSATION has no `mentions` echo, and `milestone`/`meeting` kinds do not exist (G-SCR05-4). Recommend: the thread composer starts empty. Chips show only for mentions the person picks in this composer, from E-MENTION-OPTIONS, using the four contract kinds (prefix "@" for project and person, "#" for work and document). Exception `no field` for the drawn chips.
8. **Step list.** The desktop boards draw a light box with a mono header ("3 STEPS · DONE", "WORKING · STEP 3 OF 5"). The phone working board draws the full agent card ("Building the planning packet", "Tola · PMO agent · step 3 of 5", WORKING, "Started 14:02"). Recommend: add an `inline` variant to the shared `AgentChecklist` (header line only, no avatar head). Use it for every agent message on desktop and for done step lists on the phone. A `working` message on the phone uses the existing card head: task = conversation `title`, foot "Started <clock of the person's message `at`>". The phone task words ("Building the planning packet") differ from the title ("Planning packet · Tamarind Loans"): exception `no field`. "WORKING" is the component's existing tag word.
9. **Phone headers.** The phone boards show "← Home" (default), "← Assistant" plus "Harmattan Bank" (thread) or "TOLA" (working). Recommend: "← Assistant" back link (frame item, as F-14/F-16) and the conversation `title` as the phone header. "← Home" on the phone default is a frame item. Exceptions `frame item` and `wording`.
10. **Phone default "3 earlier".** On the board this is plain text. Recommend: a button "N earlier" (N = items on the first E-CONVERSATIONS page, "20+ earlier" when `next_cursor` is present). It opens the conversation list as a `BottomSheet`, because the phone board has no other way to reach the list. Exception `extra control`.
11. **Agent copy differs by width.** The phone Tola text omits "chase sign-offs" and uses a shorter placeholder. Recommend: one text per agent at both widths (the desktop board's copy). Exception `wording`. Agent hello, ability text and placeholders are frontend-owned copy for the mock and listed as G-SCR05-6 (backend-owned is safer).
12. **One `h1` per page.** The home h1 is the agent hello (board). The desktop thread boards draw no h1. Recommend: a visually hidden h1 with the conversation `title` on desktop; on phones the visible header is the h1. Exception `extra element` (hidden).
13. **Pose images.** The boards use `/_blob/` poses. Recommend: copy `design/mascots/transparent/{pmo,finance,hr}-{idle,working,done}.png` to `frontend/public/agents/{tola,chidi,zainab}-{idle,working,done}.png` (new files; existing ones untouched; resizing for the web is allowed). Run fidelity with `--assets /Users/Hunchoo/psl-factory/design/mascots/canvas-assets.json`. Exception `asset` only if a scored image still differs.
14. **Draft card wording.** The phone thread board shows "Amount ₦6,800,000.00" and "Next · Finance review by a Finance Lead" only; the desktop board shows four rows. Recommend: the same rows at both widths, from data. The extra phone rows are exceptions `extra element`. "Next: " is a desktop prefix and a "Next" label on phones (frontend words, the value is `draft.next`).
15. **Conversation list after a start.** The desktop draft-started board keeps "Drafted · ready to start". The mock changes that entry's `status_line` to "Started · INV-0415", because that is what the data would say (readiness, proposal 3). Exception `data newer than board`.
16. **Frame items** (top bar, signed-in name and role, Start work, main nav) are exceptions as in F-14 to F-21. The desktop "TODAY" list label comes from `updated_at` (Africa/Lagos day: "TODAY", "YESTERDAY", else "12 NOV").

### A conflict with readiness (not the boards)
17. **Idempotency key on the two assistant writes (readiness rule 7, proposal 2).** E-CONVERSATION-NEW and E-MESSAGE bodies are `additionalProperties: false`, with no `idempotency_key`. Sending one would break the typed client and the schema-validating mock, which would be a local contract extension that readiness forbids. Recommend: **do not send a key** until G-SCR05-3 lands. A double send is prevented on the client by a synchronous in-flight lock. There is no automatic retry. After a network error or 5xx, the page re-reads E-CONVERSATION (or E-CONVERSATIONS for a new conversation) before offering "Try again". If the last person message already has the same text, the page shows it and does not resend. G-SCR05-3 stays blocking for a real backend.

## Summary
- New routes `/assistant` (list, agent home, `?agent=`) and `/assistant/[conversationId]` (thread) replace the placeholder `DestinationPage`. They are built from the shared library, with new general components `ChatMessage`, `Composer`, `SourceTag` and `DraftCard` plus an `inline` variant of `AgentChecklist`.
- Agents come from `E-ME.assistant_agents`, access from `context.access`, and restricted sources show as a marker with no content. Nothing comes from roles or text. Agent text renders as plain text only.
- A working conversation is a durable task. The page polls E-CONVERSATION every 5 s while `status = working`, pauses when the tab is hidden, stops on a terminal status, and keeps the state across a reload.
- "Start this invoice" opens the existing Start work drawer prefilled from `draft.start`. The person confirms. After the 201 the thread re-reads and shows "Started INV-0415." with "Open the work item".
- A new contract mock `frontend/mock/assistant.mjs` serves the five assistant operations from v7-valid fixtures and links a start to its draft on the mock only.

## Context
- Placeholder page: `frontend/src/app/assistant/page.tsx` (renders `DestinationPage destination="assistant"`). There is no `src/features/assistant/`.
- Shared library (D-91): `frontend/src/components/` (README lists `SourceTag`, `DraftCard` and `ChatMessage` as "not built yet, the assistant page is a stub"; specs in `design/system/project/components/{ChatMessage,DraftCard,SourceTag}/README.md`). Reused: `AgentChecklist.tsx` (CMP-09, steps done/now/next with `source`, reduced motion), `Avatar.tsx` (`AGENTS`, `AgentAvatar`, `AgentChip`), `Button`, `IconButton`, `Tooltip`, `Callout`, `Tag`, `TextArea`, `SearchField`, `Menu`, `BottomSheet`, `Loading`/`EmptyState`/`ErrorState`, `Money`/`Unknown`/`When` (`Values.tsx`), `VisuallyHidden`, `useIsPhone`.
- Start work: `frontend/src/features/start-work/StartWorkDrawer.tsx` (props `entry`, `onClose`; on 201 it `router.push`es to `/work/{id}`), `LineForm.tsx`, `useStartWork.ts` (`useStartForm(line, onStarted)` keeps values from empty, one key per attempt, 409/422/uncertain notices), `intake.ts` (`resolveCase` takes `case_id`/`case_revision` from the chosen option), and `RecordPicker.tsx`/`fetchOptions`. It cannot be prefilled today.
- Mock: `frontend/mock/server.mjs` (routes from v7 openapi, persona cookie `psl_mock_persona`, scenario cookie, CSRF on writes, `POST /__mock/reset`), `workspace.mjs` (pattern: Ajv request and reply validation, idempotency map, log endpoint), `start-work.mjs` (E-WORK-START: invoice answers `W-1401`. P-0102 Harmattan Bank, case C-0102 revision 3, milestone M-0202 answers a scripted 422 `billing_contact`, pinned by `tests/start-work-mock.test.ts:270`). `frontend/mock/fixtures/me.*.json` carry no `assistant_agents` today. `frontend/tests/mock-contract.test.ts:172` expects 501 for E-CONVERSATIONS.
- Assets: `frontend/public/agents/` has avatars and four poses. Full pose sets are in `design/mascots/transparent/`, mapped to the boards' blobs in `design/mascots/canvas-assets.json`.

## Contract

All operations are v7 as typed. The frontend sends exactly the typed bodies, plus CSRF on writes (`X-CSRFToken` from E-ME). It never adds a field.

### E-ME `GET /api/v1/me` (read; `assistant_agents`)
- The "Talk to" chips and the phone agent row list `assistant_agents` in returned order, with avatar, name and team (`AGENTS`, plus a new `team` field "PMO", "Finance", "HR" added to `Avatar.tsx`'s `AGENTS`, additive).
- `?agent=` selects that agent only if it is in the list. Otherwise the first listed agent is selected.
- Absent or empty list: the page shows `EmptyState` "No agents are available to you." with no composer, and sends no assistant write.
- Mock fixtures (assumption, not a rule): `me.pm.json` `["tola","chidi","zainab"]` (the board's Tunde Bello), `me.finance_lead.json` `["chidi"]`, `me.ceo.json` `["tola","chidi","zainab"]`, `me.admin.json` `[]`, `me.none.json` no field.

### E-CONVERSATIONS `GET /api/v1/assistant/conversations?limit=&cursor=`
- 200: list rows (avatar of `agent`, `title`, `status_line`), grouped by the `updated_at` day. Rows are links to `/assistant/{conversation_id}`; the open one is marked `aria-current="page"`. `ShowMore` appears when `next_cursor` is present.
- A row with no `status_line` shows the status in words ("Working", "Answered", "Can't answer", "Drafted").
- Empty: "No conversations yet." Loading: `Skeleton` rows. Error: `ErrorState` with "Try again". 401: the signed-out callout with `next=/assistant`.
- Own conversations only (backend rule). The mock serves each persona's own set.

### E-CONVERSATION `GET /api/v1/assistant/conversations/{id}` (read; polled while working)
| Field | Shown as |
|---|---|
| `agent`, `title` | thread header (phone), hidden h1 (desktop), side panel pose and name |
| `status` | side panel sentence: `working` "<Name> is working on it. You can leave; you'll be alerted." (only when `status = working`); `answered` "<Name> answered from records you can see."; `drafted` with no `draft.started` "<Name> has a draft ready for you to check."; `drafted` with `started`, the answered sentence; `cannot_answer` "<Name> can't do that with your access." |
| `context.project.title`, `context.access[]` | side panel "Project" and "Your access" lines. Absent: "Pick a project with @" / "Records you can see" (board home copy) |
| `messages[]` `role: person` | `ChatMessage` person bubble (ink, right). `text` is plain text with line breaks kept |
| `messages[]` `role: agent` | `ChatMessage` agent message: avatar, "Name · Team agent", `handoff.note` (muted line), steps, `text`, sources, then `cannot_reason` as a plain line if present, then `DraftCard` if `draft` |
| `step_details[]` | `AgentChecklist` (`inline` on desktop): `state` done/now/next, `text`, `reference.label` (or `reference.reference`) as the step's record; a link only when `reference.work_id` is present (`/work/{id}`). If `step_details` is absent, the `steps[]` strings are shown as done steps |
| `source_details[]` (else `sources[]`) | `SourceTag` per source: mono `label` (else `kind · reference`). Link when `link.work_id` (`/work/{id}`) or `link.case_id` (`/projects/{case_id}`) is present, otherwise plain. `restricted: true`: dashed tag with a lock and the word "Restricted", with **no label, reference or link** in the DOM |
| `draft` | `DraftCard`: `title`, `status_label` (tag), `rows[]` as label/value (a row with `money` shows `Money`, then `value` if present; `money.unknown` shows the amber "Unknown", never 0 or blank), `draft.next`, the start button labelled `draft.start.label` when `start` is present and `started` is absent, and the started line when `started` is present |

- Polling: every 5 s while `status = working` (D-UPDATES). The timer pauses on `visibilitychange` hidden and resumes on visible. It stops on any other status. The list re-reads once when a polled thread reaches a terminal status. A failed poll keeps the last good data and shows a quiet "Couldn't refresh. Retrying." line; there is no error page.
- Reload, a second tab or leaving and coming back all read the current state. Nothing restarts a run.
- 401: signed-out callout with `next` = this URL. 403/404 (wrong user, wrong tenant, unknown id): `NoAccessState`-style message "We could not find that conversation." with **no title, agent or text** of the conversation.
- Agent text and every string from the API are rendered as React text. `dangerouslySetInnerHTML`, `innerHTML` and markdown rendering are not allowed in `features/assistant/**` or the new components.

### E-CONVERSATION-NEW `POST /api/v1/assistant/conversations` body `{agent}`; E-MESSAGE `POST .../{id}/messages` body `{text, mentions?}`
- From the home: the first Send posts E-CONVERSATION-NEW `{agent}`, then E-MESSAGE, then `router.replace('/assistant/{id}')`. Pressing "+ New request" only returns to the home. It posts nothing (no empty conversations).
- In a thread: Send posts E-MESSAGE to that conversation.
- `text` is required (Send stays off while the text is blank after trim) and at most 4000 characters (the contract's stated limit). Over the limit, the page shows "Keep it under 4,000 characters." and sends nothing. `mentions` is `[{kind, id}]` from picked chips only.
- Enter sends and Shift+Enter adds a line (ChatMessage spec). Send is busy and ignores presses while a request is in flight (synchronous lock). There is no automatic retry. Conflicts 17 covers uncertain results.
- 200 `{message_id, agent_run_id, status}`: re-read E-CONVERSATION and start polling if `working`. `agent_run_id` is not used.
- 409: re-read, "This conversation changed. Showing the latest.", text kept. 422: the returned `message` under the composer, text kept. 403: the returned `message` (for example the agent is not allowed), text kept. 401: signed-out callout. 5xx or network: Conflicts 17.
- Permission and tenant: the backend checks that the agent serves the person and the conversation is theirs. The frontend shows only agents from E-ME and never decides access.

### E-MENTION-OPTIONS `GET /api/v1/assistant/mentions?q=&kind=&limit=`
- "@ Mention a project or record" opens a `SearchField` popover. No request is sent until `q` is at least 1 character (and the `SEARCH_PAUSE_MS` pause has passed). The list shows `label`, `hint` and `SampleLabel` when `sample` is true. Choosing an item adds a chip with a "×" remove button (accessible name "Remove <label>"). Empty: "Nothing you can mention matches." Error: "Couldn't load. Try again."
- Only returned items can be chosen. A mention is a pointer the backend re-checks (INV-ACCESS).

### E-WORK-START (existing) through the prefilled Start work drawer
- The draft's start button opens `StartWorkDrawer` with two new optional props (additive; existing callers unchanged):
  - `prefill?: {line_key, intake}` opens that line's `LineForm` directly. `useStartForm` gains an optional `initialIntake`. Text values are copied. `record`/`records` values are resolved to options through `fetchOptions` (with the parent for dependants) and matched by `value`. A value not served is left empty with `NO_LONGER_AVAILABLE`. The case and revision come from the chosen option, as today (`resolveCase`). If the line is not in E-LINES for this person, the drawer shows the existing "You can't start this here." problem and no form.
  - `onStarted?(workId)` replaces the default navigation. The assistant closes the drawer, re-reads E-CONVERSATION, shows the started line and moves focus to it (polite live region).
- The person reviews the values and presses the drawer's own start button. There is no one-click start and no assistant start path. The key and the 409/422/uncertain behaviour are Start work's own (unchanged). An uncertain start is never retried by the assistant. After the drawer closes, the thread re-reads.

### Screen states
- **Loading:** list skeleton, `Loading` in the main column. **Empty:** no conversations; no agents (E-ME). **Error:** `ErrorState` with retry per read. **Signed out:** callout with `next`. **No access:** the conversation message above.
- **default:** home of the selected agent (pose image, h1 hello, ability line, composer, side panel "<Name> is ready.").
- **working:** steps with the `now` pulse (stops under `prefers-reduced-motion: reduce`; the state is also written in words), the agent text, and the side sentence with "You can leave; you'll be alerted."
- **thread:** the CV-2401 elements in the order of the board. **draft-started:** Conflicts 5 and 6.

### Fixtures (`frontend/mock/fixtures/assistant/`, new; all validate against the v7 200 schemas; wording copied from the boards' data)
| Id | Owner persona | Shows |
|---|---|---|
| CV-2401 | pm | `drafted`, Chidi, "Invoice · Harmattan Bank M2", list `status_line` "Drafted · ready to start"; person ask; agent message with `handoff.note` "Invoices are prepared by Chidi, the Finance agent, so Tola passed this to him.", three done `step_details` with references, the answer, `source_details` (MILESTONE · HB-M2, SIGNED SOW v2 · stage 2, CLIENT · Harmattan Bank), and `draft` {title "Invoice draft · Harmattan Bank · Milestone 2", `status_label` "DRAFTED · NOT REVIEWED", rows Amount (`money` {"6800000.00","NGN",unknown:false}, value "(contract stage 2 of 3)"), To, Due terms, Template "Invoice · TEST TEMPLATE"; `next` "Finance review by a Finance Lead"; `start` {line_key "invoice", case_id "C-0102", case_revision 3, intake {project "P-0102", milestone "M-0202"}, label "Start this invoice"}}; `context` {project C-0102 "Harmattan Bank · mobile onboarding", access ["PMO on this project"]} |
| CV-2402 | pm | `drafted`, Tola, "SOW · Kora Logistics phase 2", "Drafted · 3 open questions"; draft with rows and `next` but **no `start`** (no start button) |
| CV-2403 | pm | `answered`, Chidi, "Can we bill Harmattan stage 3?", "Answered"; board answer; one `source_details` entry with `restricted: true` (label text that must not appear in the DOM) |
| CV-2404 | pm | `cannot_answer`, Zainab, "A staff member's salary", "Can't share" (list entry; the thread renders through the generic renderer, not tuned to the cant boards) |
| CV-2405 | pm | `working`, Tola, "Planning packet · Tamarind Loans", "Working · step 3 of 5"; the five `step_details` of the board (done, done, now, next, next) with references; person message `at` 14:02 WAT |
| CV-2406 | pm | `drafted`, a draft row with `money.unknown: true` (no amount); not in the list, reachable by URL |
| CV-2411 | finance_lead | `drafted`, Chidi: the finance_lead's own list (the wrong-user case); its draft's `start.line_key` is `weekly_report`, a line `finance_lead` cannot start (criterion 17) |
| CV-2499 | – | reserved no-access id: 404 for everyone |

Mentions: `fixtures/assistant/mentions.json` (project P-0102 "Harmattan Bank · mobile onboarding", P-0101, a work item, a document, a person; `_personas` per row, stripped before serving).

### Mock `frontend/mock/assistant.mjs` (new; wired into `server.mjs` like `workspace.mjs`)
- `ASSISTANT_OPERATIONS` = E-CONVERSATIONS, E-CONVERSATION, E-CONVERSATION-NEW, E-MESSAGE, E-MENTION-OPTIONS. The order of checks is as in `workspace.mjs`: scenario, CSRF on writes, then the request body validated with Ajv against the v7 schema (422 naming the fields), then ownership (404 for another persona's or an unknown conversation), then the script. Every reply is validated against its v7 schema (500 `mock_invalid_reply` otherwise).
- **Working advances on reads:** each GET of CV-2405 after the first moves one step (step 4 now, then step 5 now). The fourth read returns `answered` with a fixture answer marked as sample text ("Sample answer from the contract mock. No agent ran.") and the `list` status_line "Answered". `POST /__mock/reset` restores it.
- **New conversations:** E-CONVERSATION-NEW creates `CV-N<n>` for the persona (403 if `agent` is not in that persona's `assistant_agents`). E-MESSAGE appends the person message and a scripted agent message ("Sample answer from the contract mock. No agent ran.", one done step, no sources) with `status: answered`. A message whose text contains `[working]` answers `working` and advances on reads like CV-2405. A message containing `[409]`, `[422]` or `[500]` answers that status once (test hooks; mock only).
- **Mock-only idempotency for the two POSTs:** the contract has no key (Conflicts 17), so the mock logs every POST (`GET /__mock/assistant-log`: operation, conversation, text, status). Tests use the log to prove one POST per press.
- **Start from a draft (simulates G-SCR05-1):** E-WORK-START is routed to `assistant.mjs` first. A request is treated as the draft's start only when (a) the draft's conversation was read by this persona since the last reset, and (b) `line`, `case_id`, `intake.project` and `intake.milestone` equal that draft's `start`. In that case: the schema and CSRF checks run as in `start-work.mjs`; a repeat of the same key and body returns the stored 201; if `draft.started` is already set, the reply is 409 `{code:"draft_already_started", message:"This draft was already started."}`; otherwise the reply is 201 `{work_id:"W-1401", state:"processing"}` and the mock sets `draft.started = {work_id:"W-1401", reference:"INV-0415"}` and the list `status_line` "Started · INV-0415". Every other start goes to `start-work.mjs` unchanged, so the pinned billing-contact 422 (`tests/start-work-mock.test.ts:270`) still answers when no draft was read.
- Reset clears every override, read mark, log and created conversation.

## Lanes
- **Frontend lane (builder, Sonnet; D-64)** owns:
  - `frontend/src/app/assistant/page.tsx` (replaced), `frontend/src/app/assistant/[conversationId]/page.tsx` (new).
  - `frontend/src/features/assistant/**` (new): page layout (list, main, side panel), `AgentHome`, `Thread`, `SidePanel`, `ConversationList`, `useConversation` (read and poll), `useSend`, `labels.ts`, `assistant.css` (tokens only).
  - Shared library additions (general, each with a test in `frontend/tests/components/` covering render, states, keyboard and axe, plus a README table row): `ChatMessage.tsx` (person bubble, agent message), `Composer.tsx` (text, mentions, send, held mic), `SourceTag.tsx` (default, link, restricted), `DraftCard.tsx` (drafted, started; no Approve/Send/Pay), `AgentChecklist` `inline` variant, `AGENTS.team`. Exports in `index.ts`.
  - Start work, **additive only**: `StartWorkDrawer` `prefill` and `onStarted` props, `useStartForm`/`LineForm` `initialIntake`, with new tests `frontend/tests/start-work-prefill.test.tsx`. Existing behaviour and tests unchanged.
  - Mock: `frontend/mock/assistant.mjs`, `fixtures/assistant/**`, `server.mjs` wiring (import, reset, log path, E-WORK-START pre-route), `assistant_agents` added to `me.*.json`; `frontend/public/agents/*-{idle,working,done}.png` (new).
  - Tests: `frontend/tests/assistant.test.tsx`, `assistant-mock.test.ts`, `mock-contract.test.ts` (E-CONVERSATIONS 501 expectation replaced by the five operations), `frontend/e2e/assistant.spec.ts`.
  - Factory files: `delivery/features/F-24/fidelity-exceptions.json`, `round-<N>/fidelity/**` (`drive-states.mjs`, `scores.txt`, per-board folders), `round-<N>/build.md`.
- **Shared, read only:** `src/shell/**` (the `/assistant` nav entry already exists from `destinations`; touch it only if the route does not render, and list the change), `src/api/**` including `schema.d.ts`, `src/styles/**`, other `features/**`, `package.json` and the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`, existing fixtures other than `me.*.json`, and the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Record in build.md (not blocking for the mock): all five assistant operations are unimplemented, and the contract proposals G-SCR05-1 (`source` on E-WORK-START, `messages[].message_id`, 409 on a second start), G-SCR05-3 (`idempotency_key` on both writes), the `started` status or derived wording, G-SCR05-2 (Edit draft), G-SCR05-4 (mention kinds and echo), G-SCR05-6 (agents as objects with hello, ability text and suggestions), G-SCR05-7 (notification when a working conversation ends), `draft.started.note`, plus the open questions: privacy of a conversation (no `owner`), retention of restricted question text (INV-RESTRICTED), and cost of polling the read.
- **Integration owner:** the coordinator. `features/start-work/**` is shared with F-09 and M2A, and `src/components/**` with every feature. Whichever merges second merges the current base and reruns `delivery/checks.sh` and the start-work e2e.
- **Ports:** app **4770**, mock **4771** (range 4770 to 4779; no spec or Playwright file uses it; F-21 uses 4741/4742 and F-22 4750/4751). `cd frontend && E2E_PORT=4770 MOCK_PORT=4771 npx playwright test e2e/assistant.spec.ts`, `timezoneId: 'Africa/Lagos'`. Score on a production build (`next build`, `next start -p 4770`, mock on 4771). Check `df` first (stop under 3 GB) and delete `frontend/test-results` after.
- **Review routing:** technical (sonnet), security (opus: agent text rendering, access markers, a start from model output), UI (opus, fidelity gate on 8 boards), UX (sonnet), QA (opus). **Product acceptance required.** Medium risk. One fidelity run per round (D-64); only affected reviews re-run.
- **Size:** estimated 1,800 to 2,500 lines including fixtures and tests. One PR. If it overruns, move the four phone boards to a follow-on first.

## Acceptance criteria
Fidelity command for one board (swap `--board`, `--page`, `--width`, `--out`; cookie `psl_mock_persona=pm`; `POST /__mock/reset` before each board):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-05-desktop-thread.dc.html \
  --page "http://localhost:4770/assistant/CV-2401" --width 1440 \
  --cookies psl_mock_persona=pm \
  --assets /Users/Hunchoo/psl-factory/design/mascots/canvas-assets.json \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-24/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-24/round-<N>/fidelity/SCR-05-desktop-thread-1440
```

### Fidelity (8 boards)
1. **Desktop boards at 1440.** The four `SCR-05-desktop*` boards each report `pass: true`, `scores.coverageWithExceptions` = 100 and `scores.visual` >= 90, or a D-83-style visual waiver signed per board by the design engineer where the gap is a field the API lacks. — verify: the command per board exits 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual and pass.
2. **Phone boards at 390.** The four `SCR-05-mobile*` boards pass at `--width 390` with the same thresholds. — verify: same, rows in `scores.txt`.
3. **Driven states are the real UI.** `drive-states.mjs` resets the mock, opens CV-2401, presses "Start this invoice", confirms in the real Start work drawer against the real mock, waits for the re-read and freezes. The only DOM edits are for freezing. — verify: the script and `frozen/*.html`.
4. **Exceptions are limited and explained.** Each entry has `role`, `name`, `category`, `reason`, `approved_by` (`"builder proposal, pending design engineer"` until signed) and a Conflicts number. None covers a value the data can supply. The mic and "Edit draft" entries cite D-SPEECH-INPUT/D-96 and G-SCR05-2. — verify: file content and the build.md mapping.

### Page behaviour
5. **Agents only from E-ME.** Persona `pm` sees Tola, Chidi and Zainab. `finance_lead` sees only Chidi, and `/assistant?agent=tola` selects Chidi. `admin` (empty list) sees "No agents are available to you." with no composer. No code reads `roles` to choose agents. — verify: `tests/assistant.test.tsx`; `grep -n "roles" frontend/src/features/assistant` shows nothing.
6. **Default state.** `/assistant` (pm) shows the five conversation rows with their `status_line`s under "TODAY", the pressed Tola chip, the h1 "Hi Tunde, I'm Tola. What should we get moving?", the ability line, the composer with the Tola placeholder, and the side panel "Tola is ready." with the two context lines and the agents-cannot box. — verify: component test; page at 1440 and 390.
7. **Start a conversation.** Typing on the home and pressing Send (or Enter) sends exactly one E-CONVERSATION-NEW `{agent:"tola"}` and then one E-MESSAGE `{text}` with CSRF, with no extra field, and lands on `/assistant/CV-N1`. A double click or a double Enter sends one of each. Shift+Enter adds a line. Blank text cannot be sent. 4,001 characters shows "Keep it under 4,000 characters." and sends nothing. "+ New request" posts nothing. — verify: component test with a recording `fetch`; `assistant-mock.test.ts` and `GET /__mock/assistant-log`.
8. **Errors keep the text.** `[422]`: the returned message under the composer, text kept. `[409]`: one re-read and "This conversation changed. Showing the latest." `[500]` and a network error: no automatic resend (fake timers advanced 60 s, POST count stays 1), one re-read, and "Try again" only if the person message is not on the re-read. 403 on E-CONVERSATION-NEW (an agent not allowed for the persona) shows the returned message. — verify: component tests.
9. **Working and polling.** `/assistant/CV-2405` shows "WORKING · STEP 3 OF 5" (desktop) and the card "Tola · PMO agent · step 3 of 5", WORKING and "Started 14:02" (phone). The five steps show their words for screen readers and their references. The side panel reads "Tola is working on it. You can leave; you'll be alerted." The page re-reads every 5 s (fake timers). It does not read while `document.visibilityState` is `hidden` and resumes when visible. It stops after the `answered` read (no further GET in 30 s), the sentence "You can leave…" disappears, and the list re-reads once. — verify: component tests with fake timers.
10. **Durable across reload.** Reloading `/assistant/CV-2405` after two polls shows the advanced step (step 5 now), not step 3. A second tab shows the same. No write is sent by opening or reloading a thread. — verify: e2e reading the mock log (zero POSTs).
11. **Thread.** `/assistant/CV-2401` shows, in order: the person's ask; "Chidi · Finance agent"; the hand-off note; "3 STEPS · DONE" with three steps and references; the answer; three source tags; the draft card with "DRAFTED · NOT REVIEWED", Amount "₦6,800,000.00 (contract stage 2 of 3)", To, Due terms, Template "Invoice · TEST TEMPLATE", "Next: Finance review by a Finance Lead" and "Start this invoice". It has no "Edit draft", no attach button and no Approve, Send or Pay control. The side panel shows the project, "PMO on this project" and "Chidi has a draft ready for you to check." — verify: component test; `grep -niE "approve|send for|pay" frontend/src/features/assistant` shows only the static agents-cannot sentence.
12. **Agent text is text.** A fixture message containing `<img src=x onerror=alert(1)>` and `**bold**` renders those characters literally. No element is created from it. — verify: component test; `grep -rn "dangerouslySetInnerHTML\|innerHTML" frontend/src/features/assistant frontend/src/components/{ChatMessage,Composer,SourceTag,DraftCard}.tsx` is empty.
13. **Restricted and unknown.** On CV-2403 the restricted source shows the lock and "Restricted" only. Its fixture label and reference are not in `document.body.textContent`, and it is not a link. On CV-2406 the unknown amount reads "Unknown" (amber tag), never "₦0", "0", "-" or blank. — verify: component tests.
14. **Start opens the normal drawer, prefilled.** "Start this invoice" opens the Start work drawer on the invoice line with Project "Harmattan Bank · mobile onboarding" and Completed milestone "Milestone 2 · beta signed 30 Oct" chosen. Nothing is sent until the person presses the drawer's start button. Then exactly one POST `/api/v1/work` with `{line:"invoice", case_id:"C-0102", case_revision:3, intake:{project:"P-0102", milestone:"M-0202"}, idempotency_key}` and CSRF. — verify: component test and e2e (request recorded).
15. **Started.** After the 201 the drawer closes, the page stays on the thread, E-CONVERSATION is re-read, and the draft card shows "Started INV-0415." with "Open the work item" linking to `/work/W-1401`, announced politely with focus on it. The start button is gone. The list row reads "Started · INV-0415". Reloading keeps it. — verify: component test and e2e.
16. **No second start.** A second tab that still shows the button, opened before the start, gets the mock's 409 through the drawer's existing message. After the drawer closes the thread re-reads and shows the started line. Only one 201 exists in the mock. An uncertain start (network error) shows Start work's own uncertain notice, and the assistant sends nothing itself. — verify: e2e with two pages; component test for the uncertain path.
17. **A draft with no start or a line the person can't start.** CV-2402 shows no start button. A draft whose `start.line_key` is not in E-LINES for the persona (`finance_lead` on CV-2411, whose draft names `weekly_report`) opens the drawer with "You can't start this here." and no form. — verify: component tests.
18. **Mentions.** "@ Mention a project or record" sends no request for an empty query. Typing "harm" sends one GET `/api/v1/assistant/mentions?q=harm` (after the pause), and the list shows only returned items with their sample labels. Choosing one adds the chip "@Harmattan Bank · mobile onboarding" with a remove button. Send carries `mentions:[{kind:"project", id:"P-0102"}]`. Removing the chip removes it from the body. — verify: component test.
19. **Wrong user, unknown id, signed out.** `finance_lead` opening `/assistant/CV-2401` and anyone opening `/assistant/CV-2499` see "We could not find that conversation." with no title, agent or message text. 401 on any read shows the signed-out callout with `next` = this URL. — verify: component tests; e2e at 1440.
20. **Held mic.** The desktop composer has a 44px "Speak your request" button with `aria-disabled="true"` and the tooltip "Not available yet". Pressing it, by click or keyboard, sends nothing and changes nothing. `grep -rn "SpeechRecognition\|getUserMedia\|webkitSpeech" frontend/src` is empty. — verify: component test and the command.
21. **Reduced motion.** With `reducedMotion: 'reduce'` the `now` step box and the working avatar ring have no running animation. — verify: e2e.

### Mock and contract
22. **Mock matches the contract.** `assistant-mock.test.ts` covers the five operations: every fixture and reply validates against v7 (no stripping); a bad body is 422 naming the field; a missing CSRF is 403; another persona's conversation is 404; CV-2405 advances and ends; `[409]`/`[422]`/`[500]` answer once; the draft start rules above (armed only after a read; matching body 201 and `draft.started`; repeat key replay; second start 409; unarmed start falls through to the pinned billing-contact 422); reset restores everything. `mock-contract.test.ts` no longer expects 501 for E-CONVERSATIONS. — verify: the tests.
23. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**` or `design/**`. The assistant writes send only typed fields (no `idempotency_key`, no `source`). Every wanted field is a contract proposal in build.md. — verify: `git diff --stat`; build.md; a typecheck (`npx tsc --noEmit`).

### Quality
24. **Accessibility and layout.** For `/assistant`, CV-2401 (before and after start), CV-2403 and CV-2405 at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), no sideways scroll, visible focus, 44px targets on phones, one h1, the composer label "Message <Name>", Talk to chips with `aria-pressed`, errors in `role="alert"`, live region for started and refresh notes, and focus back to the draft button when the drawer closes without a start. — verify: `e2e/assistant.spec.ts`.
25. **Library first, tokens only.** The new components live in `src/components/` with tests and README rows. `features/assistant/**` imports no local re-implementation of a library component. `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" ` on the feature and component CSS in the diff returns nothing. — verify: the command; the README diff.
26. **Existing behaviour not weakened.** `tests/start-work*.test.*`, `tests/components/**`, `shell.test.tsx`, `mock-contract.test.ts` (other operations), `e2e/start-work.spec.ts`, `e2e/workspace.spec.ts` and every other suite in `delivery/checks.sh` pass. No assertion is removed or loosened, and the only existing fixtures edited are `me.*.json` (the field added). — verify: `delivery/checks.sh`; `git diff` on tests and fixtures.
27. **No real call, no overclaim.** Every request in the e2e run goes to the mock (4771). build.md and the PR state the limits below and do not claim a real agent, idempotent writes, a backend link from draft to work item, or a working assistant. — verify: build.md; recorded requests.
28. **build.md evidence.** It lists the commands run and their results, the 8 scores, every exception with its Conflicts number, every Start work and library change with its reason, the contract proposals, and the limits. — verify: file content.

### Product acceptance (required, at the end, by the design engineer with PSL)
Product acceptance must check, on the running app with the mock:
- The agent drafts but a person starts: "Start this invoice" opens the normal drawer, nothing starts without the person's press, and the started item is shown as theirs at the line's first station. The agent offers no approve, send or pay.
- The agent copy (hello, ability lines, placeholders, "Agents use only records you can see…", "Agents draft, read and explain. They cannot approve, send, pay or change a record.") is acceptable and claims nothing the backend will not do (G-SCR05-6).
- The held mic (disabled, "Not available yet") versus leaving it out (D-SPEECH-INPUT stays with PSL).
- "Edit draft", attach and the shortcut prompts left out (Conflicts 2 to 4), and the shortened started line (Conflicts 6).
- The working wording "You can leave; you'll be alerted.", which depends on G-SCR05-7 being built before release.
- The restricted marker reads clearly as "the record exists but you can't open it".

## Limits (binding on the PR description and build.md)
- D-ASSISTANT-VIEW and D-CONVERSATION-MODEL are `proposed`. F-24 consumes them only under the recorded exception used for F-17 and F-21: **contract mock only**. The backend developer may change or refuse any field. **Nothing is released.**
- D-AGENT-PROVIDER is open: every answer is a fixture or labelled mock sample text. No model or provider is called.
- The link from a draft to its work item, the 409 on a second start and the protection against a double send are **mock simulations** (G-SCR05-1, G-SCR05-3 are blocking for a real backend).

## Out of scope
- The `cant` boards and their phone buttons (G-SCR05-5); "Speak your request" (FE-ASSISTANT-SPEECH).
- File attachments, "Edit draft", shortcut prompts, milestone and meeting mention kinds, mention echo on reload.
- Any assistant-owned start, approve, send or pay path; starting with one click; editing a draft outside the Start work drawer.
- "Ask Tola" links from other screens (F-21 proposal), the report "Ask me" link (G-SCR12-2), notifications for finished conversations.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, new npm dependencies, `src/shell/**` beyond wiring if needed, and changes to existing screens other than the additive Start work props.
- Real model answers, real recipients, any claim of idempotency.

## Assumptions
- Persona `pm` (Tunde Bello) talks to all three agents and `finance_lead` only to Chidi in the mock. Reason: the board draws all three for Tunde; who may talk to whom is the backend's rule, not set here.
- The draft's start uses P-0102/M-0202 (case C-0102, revision 3). Reason: it is the Harmattan Bank milestone 2 the mock already serves to `pm`; the linking is armed by a conversation read so the pinned billing-contact 422 stays.
- The started reference is "INV-0415" and the work item `W-1401`. Reason: the board's reference and the invoice item the start mock already returns.
- No `idempotency_key` on the assistant writes (Conflicts 17). Reason: the v7 bodies forbid extra fields and readiness forbids local extensions.
- A conversation is created on the first send, not on "+ New request". Reason: it avoids empty conversations and an extra write; the contract allows either.
- The 4,000-character limit is enforced before sending. Reason: the contract states it; the backend's 422 still applies.
- Mention chips use "@" for project and person and "#" for work and document. Reason: the boards use "@" for a project and "#" for a record.
- The restricted source shows "Restricted" without its label. Reason: readiness rule 3 ("restricted marker with no content"), the safest reading of INV-RESTRICTED.
- The list day labels are "TODAY", "YESTERDAY", then "12 NOV", in Africa/Lagos time. Reason: the board draws "TODAY" only.
- Frontend-owned neutral sentences ("No conversations yet.", "Couldn't refresh. Retrying.", "This conversation changed. Showing the latest.", "We could not find that conversation.", "Keep it under 4,000 characters.", "No agents are available to you.", "Nothing you can mention matches.", "Not available yet") are not business rules. The approver may escalate any wording.
- Ports 4770/4771 and conversation ids CV-24xx. Reason: free in `frontend/` and `delivery/`.
