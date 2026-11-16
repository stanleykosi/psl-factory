DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-24 is FE-ASSISTANT part 1 (SCR-05): default, working, thread and draft-started, 4 states x desktop and phone = 8 boards, which meets the D-64 cap. The "can't" state (SCR-05-{desktop,mobile}-cant) is a later feature. "Speak your request" is out of this feature (FE-ASSISTANT-SPEECH, held by D-SPEECH-INPUT).
- Gates are met. FE-ASSISTANT has no unresolved gates (architecture/packages/v7/delivery.md:3075-3106). SCR-05 is in the client approval of 13 Nov 2026 (design/review.json:18, approved_at 2026-11-13T15:33:13Z; the only exception is the D-89 "+ Start" frame change). Dependencies FE-CONTRACT-V7 and FE-M2A are merged. D-96 lifted the pause and names F-24.
- The soft gates are D-ASSISTANT-VIEW and D-CONVERSATION-MODEL, both `proposed` (architecture/build_model.py:101, 854). They count only under the recorded exception used for F-17 and F-21 (contract mock only, the backend developer may change or refuse any field, nothing released). D-AGENT-PROVIDER is open and affects real answers only. Answers here come from fixtures.
- There is no contract mock for the assistant today. `frontend/mock/` has no assistant handler, and `frontend/tests/mock-contract.test.ts:172` shows E-CONVERSATIONS returning 501 not_mocked. `frontend/src/app/assistant/page.tsx` is only the empty `DestinationPage`. The schema types exist (`schema.d.ts` E-CONVERSATIONS, E-CONVERSATION, E-CONVERSATION-NEW, E-MESSAGE, E-MENTION-OPTIONS). So the mock must be added in this feature. Nothing outside it blocks the build.
- Two backend gaps (G-SCR05-1, G-SCR05-3) are marked blocking in the handoff for a real backend. They do not block a mock build, but the spec must carry them as contract proposals and the frontend must not paper over them.

## Scope
**Outcome (one):** a signed-in person opens the Assistant, picks an agent they may talk to, asks a question or for a draft, watches the agent work, reads the answer with its steps and sources, and, if the agent produced a draft, checks it and starts the normal work item from it. The agent never approves, sends or pays. A draft becomes a work item that a person owns, started through the line's normal E-WORK-START path (D-CONVERSATION-MODEL).

**Boards (8):** `design/canvas/project/SCR-05-{desktop,mobile}`, `-working`, `-thread`, `-draft-started` (default, working, thread, draft-started). `screens.md:28` lists the states and components (CMP-01, 09, 12, 13, 14, 15, 17, 18).
- default: the conversation list with status lines ("Drafted · ready to start", "Working · step 3 of 5") and the agent home with composer.
- working: the thread with a step list (done, now, next with record references) and "You can leave; you'll be alerted."
- thread: messages, hand-off note ("Tola passed this to Chidi"), sources with the restricted marker, the side panel (project, "Your access"), and the draft card (title, label/value rows, money, "Next", "Start this invoice").
- draft-started: "Started INV-0415." and "Open the work item", and the list entry after start.

**Out:**
- The `cant` boards (a later feature). The thread renderer may carry `cannot_reason` as a plain message element only if the thread board draws it. Do not tune anything to the cant boards and do not build the mobile cant buttons (G-SCR05-5).
- "Speak your request" (FE-ASSISTANT-SPEECH, D-SPEECH-INPUT open). See binding rule 1.
- Backend, OpenAPI, `schema.d.ts` regeneration and `architecture/**`. Where the boards need something the contract lacks, record a contract proposal in build.md and do not extend the contract locally.
- Real model answers. The mock supplies scripted conversations (synthetic provider, D-AGENT-PROVIDER open).
- Changes to `src/shell/**` beyond wiring the `/assistant` route, and to existing screens.

**Routes:** `/assistant` (list and home, `?agent=`) and `/assistant/[conversationId]` (thread). Replace the placeholder `app/assistant/page.tsx`.

**Endpoints (task FE-ASSISTANT, requirement R-ASSISTANT):**
- Reads: E-ME (`assistant_agents`), E-CONVERSATIONS, E-CONVERSATION, E-MENTION-OPTIONS.
- Writes: E-CONVERSATION-NEW, E-MESSAGE, and E-WORK-START (existing, for "Start this invoice").
- Acceptance: A-ASSISTANT and A-ASSISTANT-THREADS (frontend half), with the Start work tests (F-09, M2A) staying green.

**Contract mock (must be added, in this feature):** a new `frontend/mock/assistant.mjs` wired into `server.mjs` in the same way as `workspace.mjs`, `alerts.mjs` and `start-work.mjs`. It must:
- serve E-CONVERSATIONS, E-CONVERSATION, E-CONVERSATION-NEW, E-MESSAGE and E-MENTION-OPTIONS from fixtures that validate against `openapi.json`;
- script the four states: a `drafted` conversation, a `working` conversation that advances `step_details` (done, now, next) on each read so the 5 s poll is testable, an `answered` thread with `handoff` and `source_details` (one `restricted: true`), and a draft whose `draft.started` appears after E-WORK-START carrying a source;
- keep an idempotency map for the two new POSTs, as `workspace.mjs` does, and reject a second start of the same draft with 409;
- add the assistant operations to `me.*.json` `assistant_agents` per role (Tola for PMO, Chidi for Finance, Zainab for HR; the pm and finance_lead fixtures already name some);
- update `mock-contract.test.ts`, which currently expects 501 for E-CONVERSATIONS.

**Reuse (D-91 to D-96):** build on `frontend/src/components/` from the start. Use the shared AgentChecklist (it already mentions the assistant), Callout, Tag, Button, Drawer-free list rows, the Start work drawer (`features/start-work`) for the prefilled start, and `features/projects/ProjectTabs` only if a board draws it. Use tokens only, no hard-coded colour, no local re-implementation of a component the library has. If a board needs a part the library lacks (chat bubble, step list with record links, source chip), add it to the library as a general component with its test, not as a one-off in the feature.

**Tests and fidelity (D-64):** Sonnet builder. v7-typed fixtures and unit tests for list, working (polling and stop on terminal status), thread, draft card and start. Playwright with axe at 390 and 1440 for the four states. Mock contract tests for the five operations. One fidelity run per round on all 8 boards, every element present, score at least 90, or the D-83 style waiver signed per board by the design engineer for fields the API lacks. Only affected reviews re-run. `design.py check` must pass first (my role has no shell and I did not run it).

## Binding rules for the spec
1. **Speech.** The board draws the "Speak your request" microphone button (44px) in the composer on `SCR-05-desktop.dc.html:112` and the phone board. D-SPEECH-INPUT is open because browser speech recognition can send audio to a third party. F-24 must make no speech call and no `SpeechRecognition` or `getUserMedia` use. Decision for the spec: draw the button as the board shows it but disabled (`disabled`, tooltip and accessible name "Speak your request" plus a held note such as "Not available yet"), with no handler, recorded as a fidelity exception citing D-SPEECH-INPUT and D-96. Omitting it is the fallback if the fidelity run or the design engineer prefers; it is not "built". FE-ASSISTANT-SPEECH stays unbuilt.
2. **Not a generic chatbot.** Every agent reply is shown with its steps and its sources. The composer sends text and mentions only; it cannot send files (attachments are not proposed). The UI never offers an action the agent could take by itself (approve, send, pay). The agent's words are never rendered as HTML and never change what the person may do.
3. **Model output never grants authority.** The frontend shows the agent list from `E-ME.assistant_agents` only, the "Your access" list from `context.access`, and `restricted` sources as a restricted marker with no content. Nothing is derived from roles, from the message text or from `draft` text. A mention is a pointer that the backend re-checks (INV-ACCESS).
4. **A draft becomes a work item a person owns.** "Start this invoice" opens the normal Start work drawer prefilled from `draft.start` (line, case, revision, intake). The person reviews and confirms, so the work item is owned by the person who started it. Do not start it with one click and do not call any start path of the assistant's own. A 409 (case moved, or draft already started) shows the existing Start work messages. Real review and approval happen at the line's stations (the Finance Lead for the invoice).
5. **O01 coordinates scoped durable tasks.** The UI treats a working conversation as a durable task. A reload, a second tab or leaving the page does not lose or restart it: state is read from E-CONVERSATION. "You can leave; you'll be alerted" shows only when the data says `status = working`. Polling every 5 s (D-UPDATES) pauses when the page is hidden and stops on a terminal status.
6. **Unknown is not zero.** Draft money uses `money.unknown`; an unknown amount shows "Unknown" in amber, never 0 or blank (INV-UNKNOWN, D-94). Test-template or sample labels show only when the data says so.
7. **No double submit.** Disable send while a request is in flight and send one `idempotency_key` per attempt, kept across a retry (see proposal 2). Never retry a start after an uncertain result. Re-read the conversation instead.
8. **Words.** Use the boards' copy and plain business language. Agent copy (hello text, "I draft plans, SOWs…", composer placeholder) is frontend-owned for the mock and listed as G-SCR05-6 for the backend. It must not claim an ability the backend does not have, so keep the board copy and no more.
9. **Reduced motion.** The working indicator ("now" pulse) respects `prefers-reduced-motion`, as the board does.
10. Mention chips (`@Harmattan Bank`, `#Milestone 2`): render only kinds the contract has (project, work, document, person). The milestone and meeting chips need G-SCR05-4 and are a fidelity exception if the boards need them.

## Contract proposals the spec must carry (build.md, not applied locally)
1. **G-SCR05-1 (blocking for a real backend):** add optional `source:{conversation_id, message_id}` to the E-WORK-START request. The backend writes `draft.started{work_id, reference}` and rejects a second start from the same draft with 409. Add a stable `message_id` to `messages[]` on E-CONVERSATION. Until then the mock simulates it, and the frontend finds the started item from `draft.started` on re-read.
2. **G-SCR05-3 (blocking for a real backend):** add `idempotency_key` to E-CONVERSATION-NEW and E-MESSAGE (a repeat returns the first result). Drop `agent_run_id` from the frontend's needs unless a run read is added. The frontend sends the key anyway on the mock.
3. **Status after start:** `status` is `drafted` today. The list needs words for it ("Started INV-0415"). Propose a `started` value or derive from `draft.started`. Ask the backend.
4. G-SCR05-2: "Edit draft" on the desktop thread has no operation. Fidelity exception: the draft is edited in the Start work drawer; the button is left out. Needs a product answer later.
5. G-SCR05-4 (milestone and meeting mention kinds and `messages[].mentions` echo) and G-SCR05-6 (`assistant_agents` as objects with role label and hello) are nice-to-have. G-SCR05-7: confirm a notification is created when a working conversation ends, which the "you'll be alerted" line relies on (D-NOTIFY-MODEL).
6. Questions already in the handoff for the backend developer carry over: is a conversation private to its creator (the read has no `owner`), how restricted question text is retained (INV-RESTRICTED), and whether the working read is cheap to poll.

## Risk
Medium. The work adds a new route, a new mock and possibly new shared components, and it sits on a proposed contract (D-ASSISTANT-VIEW, D-CONVERSATION-MODEL) the backend may change. It has several behaviours (list, polling, send, mentions, start from a draft), and the start-from-draft step is a cross-layer contract with E-WORK-START. It is not high because everything runs on the mock, the start goes through the existing Start work drawer and idempotency path, speech is not built, and nothing reaches a client or a provider. SURFACES: ui (8 boards), api (five assistant operations plus the start), contract-change (the proposals above), product-decision (the disabled speech control under D-SPEECH-INPUT, and the missing "Edit draft"). PRODUCT-ACCEPTANCE is required: this is a new flow with agent copy and the rule that the agent drafts but a person starts, and the client must see it before release.

## Questions
None. D-SPEECH-INPUT and D-AGENT-PROVIDER stay with PSL and do not block this feature.
