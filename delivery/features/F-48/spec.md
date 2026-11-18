# The Assistant "can't" state: a person asks for something their access does not allow and sees that the agent cannot do it, why, and what it checked (contract mock only)

> Tasks: FE-ASSISTANT, part 2 (R-ASSISTANT; acceptance A-ASSISTANT and A-ASSISTANT-THREADS, frontend half). Architecture: package `architecture/packages/v7` (same manifest as F-24, digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; `status: "cannot_answer"` and `messages[].cannot_reason` are already typed in `frontend/src/api/schema.d.ts`; no generated type changes). FE-ASSISTANT is at `architecture/packages/v7/delivery.md:3075`, no unresolved gates. Design: approved canvas version 1794581312-b166. `design.py check --project .` was run for this spec and returned `EXCEPTION`, `passes: true` (D-89 "+ Start" frame change only). Screens: SCR-05, 2 artboards: `SCR-05-desktop-cant` and `SCR-05-mobile-cant` (`design/canvas/project/`). Decisions consumed: D-ASSISTANT-VIEW and D-CONVERSATION-MODEL, both `proposed` (contract mock only, as F-24). Builds on `delivery/features/F-24/spec.md` (merged, #48). Readiness: `delivery/features/F-48/readiness.md` (READY, low, PRODUCT-ACCEPTANCE not required).

## Summary
- `poseFor` returns a new `cant` pose when `status === 'cannot_answer'`, so the side panel shows the "can't" pose and the sentence "Zainab can't do that with your access." (already in `labels.ts`).
- The phone thread shows the board's inline pose card in the agent tint, only for a `cannot_answer` conversation.
- The refusal reason is `cannot_reason` shown as plain text, exactly as returned, through the existing `ChatMessage` `cannot` line. Nothing is merged or rewritten.
- No control appears or changes: no draft card, no start button, no "request access". The phone buttons "Show staff-cost totals" and "Ask HR Lead for access" are not drawn (G-SCR05-5).
- Reads only. Reuses fixture CV-2404. No backend, no schema change, speech stays held.

## Context
- Pose today: `frontend/src/features/assistant/SidePanel.tsx:11-16` (`Pose = 'idle' | 'working' | 'done'`; `poseFor` maps `cannot_answer` to `idle`). The image is `/agents/${agent}-${pose}.png` (line ~25), alt `"<Name> pose"`.
- `frontend/public/agents/` has `{tola,chidi,zainab}-{idle,working,done}.png` and no `*-cant.png`.
- The design asset exists: `design/mascots/revised-poses/{tola,chidi,zainab}-cant.png`; the boards' blobs are `cant` in `design/mascots/canvas-assets.json` (pmo `11781bdc...`, finance `3e917463...`, hr `6b7cc480...`).
- Thread: `frontend/src/features/assistant/Thread.tsx:45` passes `cannot={message.cannot_reason}` to `ChatMessage`; `ThreadPage.tsx` and `AssistantFrame.tsx` lay out the thread and side panel; labels in `labels.ts` (`sideSentence`, `statusLine`, `CANNOT_NOTE`).
- Fixture: `frontend/mock/fixtures/assistant/CV-2404.json` (pm, Zainab, `cannot_answer`, list line "Can't share"), served by `frontend/mock/assistant.mjs`.
- Tests: `frontend/src/features/assistant/assistant.test.tsx`, `assistant-mock.test.ts`, `frontend/e2e/assistant.spec.ts`; fidelity files `delivery/features/F-24/fidelity-exceptions.json`.

## Contract
Reads only. The frontend sends no new request and adds no field. No new endpoint.

### E-CONVERSATION `GET /api/v1/assistant/conversations/{id}` (CV-2404)
| Field | Shown as |
|---|---|
| `status = cannot_answer` | pose `cant`; side sentence "<Name> can't do that with your access."; phone pose card. Only this field decides the state, never the agent's words |
| `messages[].cannot_reason` | one plain-text line under the agent answer (and sources), as returned, line breaks kept |
| `messages[].text` | the agent's answer as plain text |
| `step_details[]` | `AgentChecklist` (inline), for example "Checked your access to payroll records", "1 STEPS · DONE" as F-24 renders it |
| `source_details[]` with `restricted: true` | `SourceTag restricted` only: lock and "Restricted", no label, reference or link in the DOM |
| `context.project.title`, `context.access[]` | side panel "Project" and "Your access" as returned |
- No `draft`, so no draft card and no start button. No other control changes. The composer on this thread is the existing E-MESSAGE path, unchanged.
- Errors, 401, 403/404 and polling are F-24's (terminal status: no polling).
- Strings are React text: no `dangerouslySetInnerHTML`, `innerHTML` or markdown.

### E-CONVERSATIONS (list)
- Row for CV-2404 reads `status_line` "Can't share" (F-24 `statusLine`; without it, "Can't answer"). Unchanged.

### Screen states for the two boards
- **Loading / error / signed out / no access:** F-24's.
- **Success (cannot_answer), desktop 1440:** list row, thread (ask, "Zainab · HR agent", steps, answer, `cannot_reason`, restricted source tag), side panel with the `cant` pose, sentence, Project, Your access, agents-cannot note.
- **Success, phone 390:** "← Assistant" header with the conversation title, the ask, the inline pose card in the agent tint (cant pose image, alt "<Name>, can't do this"), "Zainab · HR agent", the answer and `cannot_reason`. The card appears only for `cannot_answer`; on every other status the phone thread is as F-24.
- **Reduced motion:** the pose is a still image; nothing animates.

### Fixture (existing, unchanged unless a test needs more)
CV-2404: pm, Zainab, "A staff member's salary", `cannot_answer`, restricted source, `context.access ["PMO · no payroll access"]` if not already set. If a test needs a second case (for example a non-HR agent), add it as `CV-4501` using ids from the W-4501..W-4599 block only (`W-4501` for a work reference). No other new ids.

## Lanes
- **Frontend lane (builder)** owns: `frontend/src/features/assistant/SidePanel.tsx` (`Pose` gains `'cant'`, `poseFor`), `Thread.tsx`/`ThreadPage.tsx`/`AssistantFrame.tsx` (phone pose card), `assistant.css` (tokens only), `labels.ts` only if the sentence is not already `cannot_answer`-aware, `frontend/public/agents/{tola,chidi,zainab}-cant.png` (new), tests in `assistant.test.tsx` and `e2e/assistant.spec.ts`, and factory files `delivery/features/F-48/fidelity-exceptions.json`, `round-<N>/fidelity/**`, `round-<N>/build.md`.
- **Backend lane:** none. Record in build.md: G-SCR05-5 (phone suggestion buttons need a typed field) and that "who receives an access request" is an unproposed business decision.
- **Shared, read only:** `frontend/src/components/**` (reuse `ChatMessage`, `SourceTag`, `AgentChecklist`, `Avatar`), `src/api/**`, `src/shell/**`, `src/styles/**`, `package.json`, `architecture/**`, `design/**`, `apps/**`, and protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`. `frontend/mock/**` is read only unless a test needs a new fixture (then only the fixture and nothing in `assistant.mjs`).
- **Integration owner:** the coordinator; the feature touches only F-24's folder.
- **Ports:** app 4770 and mock 4771 are in the F-24 range; use app **4772**, mock **4773** (4770 to 4779 is the assistant block). `cd frontend && E2E_PORT=4772 MOCK_PORT=4773 npx playwright test e2e/assistant.spec.ts`, `timezoneId: 'Africa/Lagos'`. Check `df` first (stop under 3 GB); delete `frontend/test-results` after.
- **Review routing:** technical, UI (fidelity), UX, QA, security (agent text as text, restricted marker). One fidelity run per round (D-64); only affected reviews re-run. Low risk, 2 boards, well under the D-64 cap.

## Conflicts with the boards (for the design engineer, before the build)

### Need an answer
1. **The "can't" pose image.** The boards show a cant pose (blobs in `canvas-assets.json`); the code has none. The pose is a design asset and the builder must not draw or generate it. **Recommend:** copy `design/mascots/revised-poses/{tola,chidi,zainab}-cant.png` (they exist, same source as the blobs; confirm each matches its board blob on the fidelity run; resizing for the web is allowed) to `frontend/public/agents/`. If a file does not match the board or is missing, keep the idle pose for that agent and record an `asset` exception for the design engineer to supply the image.

### Layout
2. **Phone inline pose card.** Board draws the pose in the agent tint above "Zainab · HR agent". **Recommend:** build it as drawn, shown only when `status === 'cannot_answer'`, using agent tint tokens and the shared `Avatar`/image styles; decorative alt text is the board's "<Name>, can't do this".
3. **One paragraph versus answer plus reason.** The phone board draws a single paragraph ("I can't share an individual's pay with you; that is restricted to HR roles. I can show staff-cost totals...") while the contract has `text` and `cannot_reason` separately. **Recommend:** show `text` and then `cannot_reason` as separate plain-text lines, never joined or rewritten. Exception `wording` where the board's one paragraph differs.
4. **Desktop board's thread chrome.** The desktop board is built from the same home/thread layout as F-24 and still draws the "Edit draft", start and "Started" lines (hidden template blocks), the mic, attach, shortcuts and mention chips. **Recommend:** nothing is added; the F-24 exceptions (D-100) apply unchanged. No draft card appears on a `cannot_answer` thread.
5. **Phone header.** Board shows "← Assistant", "Payroll", and a "Start" button. **Recommend:** the conversation title is the header and the "Start" button is the existing frame "+ Start" (D-89), as F-24. Exception `wording` for "Payroll" versus the title.

### Exceptions to confirm
6. **"Show staff-cost totals" and "Ask HR Lead for access" (phone).** No field carries them (G-SCR05-5); a request-access path needs a business decision on who receives it. **Recommend:** not drawn. Exceptions `no field` (both buttons), `approved_by` "builder proposal, pending design engineer". The composer is never prefilled from agent text.
7. **Speech.** The held microphone stays as F-24 built it. No change.

## Acceptance criteria
Fidelity command per board (swap `--board`, `--page "http://localhost:4772/assistant/CV-2404"`, `--width`, `--out`; cookie `psl_mock_persona=pm`; `POST /__mock/reset` first):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-05-desktop-cant.dc.html \
  --page "http://localhost:4772/assistant/CV-2404" --width 1440 \
  --cookies psl_mock_persona=pm \
  --assets /Users/Hunchoo/psl-factory/design/mascots/canvas-assets.json \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-48/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-48/round-<N>/fidelity/SCR-05-desktop-cant-1440
```

### Fidelity (2 boards)
1. **Desktop board at 1440.** `SCR-05-desktop-cant` reports `pass: true`, `scores.coverageWithExceptions` = 100 and `scores.visual` >= 70 (the D-64/D-83 floor), or a D-83 waiver signed per board by the design engineer where the gap is a field the API lacks. — verify: the command exits 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass.
2. **Phone board at 390.** `SCR-05-mobile-cant` passes at `--width 390` with the same thresholds. — verify: same, a row in `scores.txt`.
3. **Exceptions are limited and explained.** Each entry in `delivery/features/F-48/fidelity-exceptions.json` has `role`, `name`, `category`, `reason`, `approved_by` ("builder proposal, pending design engineer" until signed) and a Conflicts number; F-24's approved entries are carried over unchanged. None covers a value the data can supply. The two phone buttons cite G-SCR05-5. — verify: file content and the build.md mapping.

### Page behaviour
4. **Pose by status.** Unit tests: `poseFor` returns `cant` for `cannot_answer`, `working` for `working`, `done` for `drafted`, `idle` for `answered`. The side panel image for CV-2404 is `/agents/zainab-cant.png`; for `answered` it stays `-idle.png`. — verify: `assistant.test.tsx`.
5. **Pose assets.** `frontend/public/agents/{tola,chidi,zainab}-cant.png` exist, are copies of (or web-sized versions of) `design/mascots/revised-poses/*-cant.png`, and were not drawn or generated; if Conflicts 1's fallback applies, the missing agent keeps `-idle.png` and an `asset` exception is listed. — verify: `ls frontend/public/agents`; `cmp` or image dimensions against the source; build.md.
6. **Side panel text.** For CV-2404 the panel reads "Zainab can't do that with your access.", Project "October payroll" (as the fixture returns), "Your access" "PMO · no payroll access" (as `context.access` returns), and the agents-cannot note. The sentence comes from `status`, not from message text: a fixture whose agent text says "I can't" but has `status: answered` reads the answered sentence. — verify: component tests.
7. **Thread content.** `/assistant/CV-2404` shows, in order: the ask in the person bubble; "Zainab · HR agent"; the checklist step "Checked your access to payroll records" with "1 STEPS · DONE"; the answer; the `cannot_reason`; one restricted source tag. The list row reads "A staff member's salary" with "Can't share". — verify: component test; page at 1440.
8. **Reason is text.** A fixture whose `cannot_reason` contains `<img src=x onerror=alert(1)>` and `**bold**` renders those characters literally, creates no element, and is not edited, trimmed of words or joined with `text`. — verify: component test; `grep -rn "dangerouslySetInnerHTML\|innerHTML" frontend/src/features/assistant` is empty.
9. **No new controls.** On a `cannot_answer` thread there is no draft card, no start button, no "Edit draft", no "Show staff-cost totals", no "Ask HR Lead for access", no request-access link or button, and the composer is empty (not prefilled). No new request is sent by opening or reloading the thread (mock log shows zero POSTs). — verify: component tests; `grep -rn "staff-cost\|Ask HR" frontend/src` is empty; e2e reading `GET /__mock/assistant-log`.
10. **Restricted source.** The restricted tag shows the lock and "Restricted" only; the fixture's label and reference are not in `document.body.textContent`, and it is not a link. — verify: component test.
11. **Phone pose card.** At 390, CV-2404 shows the inline pose card with the `zainab-cant.png` image, alt "Zainab, can't do this", in the agent tint. CV-2401 (drafted), CV-2403 (answered) and CV-2405 (working) at 390 show no such card. At 1440 the card is not shown (the side panel carries the pose). — verify: component tests with `useIsPhone` both ways; e2e at 390.
12. **Wrong user, unknown id, signed out.** `finance_lead` opening `/assistant/CV-2404` and anyone opening `/assistant/CV-2499` see "We could not find that conversation." with no title, agent or reason. 401 shows the signed-out callout with `next` = this URL. — verify: component tests (F-24's remain green; add CV-2404 to the wrong-user case).
13. **Provider or read failure.** A failed E-CONVERSATION read for CV-2404 shows F-24's `ErrorState` with "Try again", with no pose card and no stale refusal text. — verify: component test.

### Quality
14. **Accessibility.** `/assistant/CV-2404` at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), no sideways scroll, visible focus, one h1, the pose image has the alt above (the side-panel image keeps a meaningful alt, not empty), 44px touch targets on the phone. — verify: `e2e/assistant.spec.ts` with axe and a bounding-box check of every phone control.
15. **Reduced motion.** With `reducedMotion: 'reduce'` the `cant` pose has no running animation or transition. — verify: e2e computed-style check.
16. **Library first, tokens only.** The pose card reuses shared components and styles; `features/assistant/**` adds no local copy of a library component. `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" ` on the diff of `assistant.css` and any new CSS returns nothing. — verify: the command.
17. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**`, `frontend/mock/assistant.mjs` or `src/shell/**`. Writes send only typed fields. — verify: `git diff --stat`; `npx tsc --noEmit`.
18. **F-24 not weakened.** All F-24 assistant tests (`assistant.test.tsx`, `assistant-mock.test.ts`, `e2e/assistant.spec.ts`), the Start work suites and every other suite in `delivery/checks.sh` pass; no assertion removed or loosened; the only edit to an F-24 test is the added CV-2404 cases. — verify: `delivery/checks.sh`; `git diff` on tests.
19. **No overclaim.** build.md and the PR state: contract mock only, nothing released, no real agent answered, the refusal text is the mock's sample text, and no access request exists. — verify: build.md.
20. **build.md evidence.** Commands and results, the 2 scores, every exception with its Conflicts number, the asset source for each `-cant.png`, and the G-SCR05-5 proposal. — verify: file content.

## Out of scope
- The phone suggestion buttons (G-SCR05-5) and any "request access" path or recipient; prefilling the composer from agent text.
- Speech (FE-ASSISTANT-SPEECH, D-SPEECH-INPUT); "Edit draft", attach, shortcuts and mention chips (D-100).
- Drawing, generating or editing a pose image.
- Rewriting, merging, translating or classifying the backend's refusal text; inferring "can't" from words.
- New endpoints, mock behaviour, `schema.d.ts` regeneration, OpenAPI, backend, `architecture/**`, `design/**`, `src/shell/**`, other screens, new npm dependencies.
- Changing the F-24 side sentences, list words or other poses.

## Assumptions
- The `revised-poses/*-cant.png` files are the intended board images. Reason: same folder and naming as F-24's pose source, and `canvas-assets.json` names a `cant` blob for each agent; confirmed by fidelity.
- Phone pose card sits above the agent name, as the board draws. Reason: only the board shows it.
- Alt "<Name>, can't do this" for the phone card and the page-wide "<Name> pose" kept for the side panel. Reason: the board's alt; the side panel's existing alt is already tested.
- Ports 4772/4773. Reason: free inside the assistant block 4770 to 4779.
- The fidelity floor is 70 (D-64/D-83), lower than F-24's 90 target. Reason: the caller's instruction; a waiver covers fields the API lacks.
- Fixture ids, if any: `CV-4501`, `W-4501`. Reason: W-4501..W-4599 is this feature's id block.
- CV-2404's access line and project text are used as the fixture has them. Reason: readiness names "October payroll" and "PMO · no payroll access", and the screen only shows `context` as returned.
