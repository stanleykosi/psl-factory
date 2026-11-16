STATUS: READY
COMMIT: 10c7accc2889434032b1addd7d8fad42fe71b9ce
BUILDER: builder
LANE: full

## Summary
- `/assistant` and `/assistant/[conversationId]` replace the placeholder: list, agent home, thread, side panel, composer, mentions, polling, and "Start this invoice" opening the normal Start work drawer prefilled from `draft.start`. Contract mock only; no agent runs.
- New shared components (with tests and README rows): `ChatMessage`, `Composer` (held mic, no attach), `SourceTag`, `DraftCard`, `AgentChecklist` `inline`, `AGENTS.team`.
- New contract mock `frontend/mock/assistant.mjs` + fixtures (CV-2401..2406, 2411, mentions), wired into `server.mjs`; `me.*.json` gain `assistant_agents`.
- Start work gets additive optional props only (`prefill`, `onStarted`, `initialIntake`); all existing tests pass unchanged.
- Fidelity: coverage after exceptions is 100 on all 8 boards; visual is 76.5 to 84.5 (none at 90), so a visual waiver is requested for the design engineer to sign (below).

## Changes
- `frontend/src/app/assistant/{layout,page}.tsx`, `[conversationId]/page.tsx`: routes; layout keeps the list across conversations.
- `frontend/src/features/assistant/**`: AssistantFrame, AssistantHome, ThreadPage, Thread, SidePanel, ConversationList, ComposerBar, MentionPicker, DraftStart, Chrome (Talk to, "N earlier"), hooks `useConversation` (5 s poll, pauses hidden, stops on terminal), `useConversationList`, `useSend` (sync lock, no key, no auto retry, re-read after uncertain), api/labels/model/types, assistant.css (tokens only).
- `frontend/src/components/`: ChatMessage, Composer, SourceTag, DraftCard, AgentChecklist `inline` (and `source` may be a node), Avatar `team`, components.css, index.ts, README.
- `frontend/src/features/start-work/` (additive): `StartWorkDrawer` `prefill`/`onStarted`, `LineForm` `initialIntake`, `useStartForm` `initialIntake` + `prefilling` (read-only and start disabled while record values are looked up; unserved value left empty with the existing note).
- `frontend/mock/assistant.mjs`, `fixtures/assistant/**`, `server.mjs`, `me.*.json`; `public/agents/{tola-idle,tola-working,chidi-idle,zainab-idle,zainab-working,zainab-done}.png` (new; existing tola-done, chidi-done, chidi-working kept).
- Tests: `tests/assistant.test.tsx`, `assistant-mock.test.ts`, `assistant-bridge.ts`, `start-work-prefill.test.tsx`, `components/assistant-components.test.tsx`, `mock-contract.test.ts` (501 case now uses E-REPORT; assistant ops covered by assistant-mock), `e2e/assistant.spec.ts`.
- Factory: `delivery/features/F-24/fidelity-exceptions.json`, `round-1/fidelity/{run.sh,drive-states.mjs,serve-frozen.mjs,scores.txt,per-board folders,frozen/}`.
- No change in `src/api/**`, `architecture/**`, `design/**`, `apps/**`, protected paths.

## Fixes
None (round 1).

## Acceptance criteria
1. [~] Desktop boards: coverage with exceptions 100 on all four; visual 83.8, 84.5, 81.2, 80.3 (not 90): waiver requested.
2. [~] Phone boards: coverage 100 with exceptions; visual 76.5, 79.5, 77.3, 76.7: waiver requested.
3. [x] Driven states are the real UI: `round-1/fidelity/drive-states.mjs` resets the mock, presses the real button, confirms in the real drawer, waits for the re-read, freezes (`frozen/draft-started-{1440,390}.html`).
4. [x] Exceptions each have role, name, category, reason, Conflicts number, `approved_by` "builder proposal, pending design engineer"; none covers a value the data can supply (Conflicts 2, 3, 4, 5, 6, 7, 8/9, 11, 14).
5. [x] Agents only from E-ME (assistant.test.tsx: pm 3, finance_lead 1 + `?agent=tola`, admin and no-field none, no composer); `grep roles` in the feature: nothing.
6. [x] Default state (component test; e2e).
7. [x] Start a conversation: one NEW `{agent}` + one MESSAGE `{text}` with CSRF; double click/Enter one each; Shift+Enter; blank; 4,001 chars message; "+ New request" posts nothing.
8. [x] Errors: [422], [409], [500] and network error (60 s fake timers: POST count 1, one re-read, Try again), 403 on NEW.
9. [x] Working/polling with fake timers (5 s, hidden pauses, stops after answer, list re-read once); phone card "Started 14:02".
10. [x] Durable reload: e2e reads the mock log (no writes).
11. [x] Thread order and content; no Edit draft, attach, Approve, Send, Pay.
12. [x] Agent text is text (component and page tests; no innerHTML in the feature or components).
13. [x] Restricted source: lock and "Restricted" only, label absent from DOM; unknown amount "Unknown" amber.
14. [x] Start opens the prefilled drawer; nothing sent until the drawer's button; one POST /api/v1/work with the typed body and CSRF.
15. [x] Started: drawer closes, re-read, "Started INV-0415." + "Open the work item" `/work/W-1401`, focus on it, button gone, list "Started · INV-0415", reload keeps.
16. [x] Second tab gets the 409 (the drawer's existing "changed since you opened" notice), then shows the started line; uncertain start shows Start work's own notice and the assistant sends nothing.
17. [x] CV-2402 has no button; CV-2411 as finance_lead opens "You can’t start this here." with no form (curly apostrophe, as Start work's existing text).
18. [x] Mentions: no request for empty q; one GET `?q=harm`; chip; body `mentions:[{kind:"project",id:"P-0102"}]`; remove.
19. [x] Wrong user, CV-2499, 401 (component and e2e).
20. [x] Held mic: 44px, aria-disabled, tooltip "Not available yet", no handler; no SpeechRecognition/getUserMedia in `src`.
21. [x] Reduced motion (e2e at 1440 and 390, plus a control that pulses without it).
22. [x] Mock: `assistant-mock.test.ts` (31 tests); `mock-contract.test.ts` no longer expects 501 for E-CONVERSATIONS.
23. [x] No contract extension: no diff in `src/api/**`, `apps/**`, `architecture/**`, `design/**`; `tsc` clean; writes carry only typed fields.
24. [x] e2e axe (wcag2a/aa/21/22, with colour contrast), one h1, no sideways scroll, 44px on phones at 1440 and 390 for `/assistant`, CV-2401 (before and after start), CV-2403, CV-2405.
25. [x] Library first, tokens only (no hex/rgb in the diff; styles-drift test passes).
26. [x] Existing suites unchanged and green (82 files, 1775 tests); e2e `start-work.spec.ts` green.
27. [x] Every e2e request goes to the mock; limits below stated.
28. [x] This file.

## Validation
- `bash delivery/checks.sh`: exit 0 (Django check, lint, tsc, vitest 82 files / 1775 tests, `next build`).
- `E2E_PORT=4770 MOCK_PORT=4771 npx playwright test e2e/assistant.spec.ts e2e/start-work.spec.ts`: 31 passed.
- Fidelity (one run, 8 boards, `--assets canvas-assets.json`, production build on 4770, mock 4771); `round-1/fidelity/scores.txt`:
  - SCR-05-desktop 1440: coverage 83.9, with exceptions 100, visual 83.8
  - SCR-05-desktop-working 1440: 83.9 / 100 / 84.5
  - SCR-05-desktop-thread 1440: 80.9 / 100 / 81.2
  - SCR-05-desktop-draft-started 1440: 79.6 / 100 / 80.3
  - SCR-05-mobile 390: 66.7 / 100 / 76.5
  - SCR-05-mobile-working 390: 60 / 100 / 79.5
  - SCR-05-mobile-thread 390: 71.4 / 100 / 77.3
  - SCR-05-mobile-draft-started 390: 40 / 100 / 76.7
  Pass rule needs visual 90: all 8 fail it; all are 70 or more, so a waiver per board is requested (listed under `visual_waivers` in `fidelity-exceptions.json`, "builder proposal, pending design engineer"). Remaining gaps are fields the API lacks, the frame (top bar, phone bar), the grey disabled Send, and the extra draft rows on phones. I did not tune further under D-64.
- The later polish commit changed the fidelity-measured page; scores above are from that build.

## Exceptions (Conflicts items built as recommended)
1 mic drawn held (no coverage exception; D-SPEECH-INPUT, D-96); 2 Edit draft left out; 3 attach left out; 4 shortcuts left out; 5 start button hidden once started, side sentence "answered"; 6 "Started INV-0415." + "Open the work item"; 7 no mention echo chips on load; 8 inline steps (desktop and done lists), card for phone working with title as task; 9 "← Assistant" via the frame's `usePhoneBack` with the title as note, hidden h1 on both widths (the phone bar's note is not an h1: deviation from the spec's "visible header is the h1"), no "← Home"; 10 "N earlier" button opens a BottomSheet; 11 one copy per agent; 12 hidden h1; 13 pose images copied; 14 same draft rows at both widths; 15 list status "Started · INV-0415"; 16 frame items.
- Other board-vs-spec notes: phones show no side panel (the phone boards draw none), so the "You can leave; you'll be alerted" sentence is desktop only; phone thread has no Talk to row; Composer send is grey (aria-disabled) while blank; mention chips use neutral colour (the boards' orange/blue chips would break D-92 colour meaning); a second tab's 409 uses Start work's existing stale notice.
- Greps: `approve|send for|pay` in the feature matches only the static agents-cannot sentence and Zainab's "payroll" copy.

## Start work and library changes (reasons)
- `prefill`/`onStarted`/`initialIntake`/`prefilling`: open the invoice drawer filled from the draft without a new start path; defaults unchanged.
- `AgentChecklist` `inline` and node `source`; `AGENTS.team`: board header line and linked step records; additive.

## Contract proposals and limits (not applied locally)
- G-SCR05-1 (`source` on E-WORK-START, `messages[].message_id`, 409 on second start), G-SCR05-3 (`idempotency_key` on both writes, blocking for a real backend), `started` status or derived wording, G-SCR05-2 (Edit draft), G-SCR05-4 (mention kinds and echo), G-SCR05-6 (agents as objects with hello, ability, suggestions), G-SCR05-7 (notification when a working conversation ends), `draft.started.note`; open questions: conversation privacy (no `owner`), retention of restricted question text, polling cost. Backend lane: all five assistant operations are unimplemented.
- Limits: D-ASSISTANT-VIEW and D-CONVERSATION-MODEL are `proposed`; contract mock only; every answer is fixture or labelled sample text; the draft-to-work link, the 409 on a second start and the double-send protection are mock simulations; the assistant writes carry no idempotency key (Conflicts 17). Nothing is released.

## Blocked
Not blocked. Needs the design engineer: sign the exceptions and the visual waivers.
