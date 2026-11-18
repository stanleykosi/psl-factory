DECISION: READY
RISK: low
SURFACES: ui
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-48 is FE-ASSISTANT part 2: the SCR-05 "can't" state, 2 boards (`SCR-05-desktop-cant`, `SCR-05-mobile-cant`). F-24 built and merged the other 8 non-speech boards (default, working, thread, draft-started, desktop and phone; D-100 waivers, D-101 acceptance). This leaves only "can't", well under the D-64 cap. It is not DONE-ELSEWHERE: the data and the text line exist, but the "can't" pose, the phone layout and a fidelity run on these boards were never built or checked.
- Gates are met. FE-ASSISTANT has `gate_ids: []` and "Unresolved gates: none", and its title names the "cant" state (architecture/packages/v7/delivery.md:3075-3106). SCR-05 is in the client approval (design/review.json:18). Dependencies FE-CONTRACT-V7 and FE-M2A are merged, and so is F-24 (#48). D-ASSISTANT-VIEW and D-CONVERSATION-MODEL are still `proposed` (architecture/model.json:657, 1493). They count under the same recorded exception F-24 used: contract mock only, nothing released.
- The contract already covers this state: `status: "cannot_answer"` and `messages[].cannot_reason` (frontend/src/api/schema.d.ts:4443, 4746). The backend handoff says "can't share" reason is "covered by v7 as is" (delivery/backend-handoff/gaps-a-project-setup.md:23). The mock has the fixture `frontend/mock/fixtures/assistant/CV-2404.json` (Zainab, payroll, restricted source).
- What is still missing in the code: `poseFor` maps `cannot_answer` to `idle` (frontend/src/features/assistant/SidePanel.tsx:13-16), and `frontend/public/agents/` has no `*-cant.png`. The phone thread does not draw the board's inline pose card. The phone buttons "Show staff-cost totals" and "Ask HR Lead for access" have no contract (G-SCR05-5), so they are left out by fidelity exception.
- Speech (FE-ASSISTANT-SPEECH, D-SPEECH-INPUT) is out. The held microphone from F-24 stays as it is.

## Scope
**Outcome (one):** a person who asks an agent for something their access does not allow opens that conversation and sees that the agent cannot do it, the reason the backend returned, and what the agent checked. Nothing in the reply grants access or offers a way round it. Contract mock only.

**Boards (2):** `design/canvas/project/SCR-05-desktop-cant.dc.html` and `SCR-05-mobile-cant.dc.html`.
- Desktop: the thread (the ask in the ink box, Zainab · HR agent, the step "Checked your access to payroll records" under "1 STEPS · DONE", the answer, the restricted source tag), the conversation list row "A staff member's salary · Can't share", and the side panel with the **cant pose**, "Zainab can't do that with your access.", Project "October payroll" and Your access "PMO · no payroll access".
- Phone: "← Assistant" header with the project label, the ask, the **inline cant pose in the agent tint**, "Zainab · HR agent" and the answer.

**Task, endpoints, acceptance:** FE-ASSISTANT (R-ASSISTANT). Reads only: E-CONVERSATION (`status`, `cannot_reason`, `step_details`, `source_details`, `context`) and E-CONVERSATIONS (`status`, `status_line`). No new writes. The composer on a "can't" thread is the existing E-MESSAGE path, unchanged. Acceptance: A-ASSISTANT and A-ASSISTANT-THREADS (frontend half). All F-24 assistant tests stay green.

**In:**
- Add a `cant` pose: `poseFor` returns `cant` for `status === 'cannot_answer'`. Add `{tola,chidi,zainab}-cant.png` to `frontend/public/agents/` from the same source as F-24's poses (candidates are under `design/mascots/revised-poses/`; confirm against the board blobs). Alt text as the board shows it ("Zainab, can't do this").
- Add the phone "can't" layout: the inline pose card in the agent tint, shown only when `status === 'cannot_answer'`.
- Show the refusal reason from `cannot_reason` exactly as returned, as plain text through the existing `ChatMessage cannot` line. If the board's single paragraph and the separate reason line differ, record it as a fidelity difference. Do not merge or rewrite the backend's text.
- Mock: reuse CV-2404. Add more "can't" fixtures (for example a non-HR agent) only if a test needs them, using the F-48 id block W-45xx/T-45xx.
- Tests: unit tests for pose and side sentence by status, the reason rendered as text (no HTML), no draft card and no start control on a "can't" thread, and the phone card. Playwright with axe at 390 and 1440 on CV-2404. One fidelity run per round over the 2 boards, score at least 90 or a D-83 waiver.

**Out:**
- The phone suggestion buttons (G-SCR05-5): leave them out, recorded as a fidelity exception for the design engineer. Do not prefill the composer from the agent text. Do not build any "request access" path: who receives an access request is a business decision that is not proposed.
- Speech, "Edit draft", attach, shortcuts and mention chips (as in D-100), backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**` and `src/shell/**`.

## Binding rules for the spec
1. "Can't" comes only from `status === 'cannot_answer'` and the returned `cannot_reason`. Never infer it from the agent's words, and never infer "answered" or "done" from them. The side sentence and list words stay as F-24 wrote them (`labels.ts` `sideSentence`, `statusLine`).
2. Agent text and the reason are rendered as text, never HTML. They change no control: no draft card, no start, and no "request access" control appears unless the response sends a typed field for it.
3. A restricted source shows only the restricted marker (`SourceTag restricted`). Nothing of the record is shown, and the source gives no link. "Your access" comes from `context.access` as returned.
4. Tokens and shared components only. 44px targets on the phone. The pose image respects reduced motion (no animation).

## Risk
Low. This is a read-only state on screens F-24 already built, over an existing contract field and an existing fixture. The change is a pose mapping, assets, one phone layout element and tests in `frontend/src/features/assistant/` (SidePanel.tsx, Thread.tsx, ThreadPage.tsx). There is no write, money or migration, and no new authority rule: the restricted payroll content is never in the response, and the screen only shows the backend's refusal. SURFACES is ui only, because the one contract gap (G-SCR05-5) is dropped by exception and not proposed. PRODUCT-ACCEPTANCE is not-required: the work matches the client-approved board, and the left-out phone buttons go to the design engineer as a fidelity difference, as in D-100.

## Questions
None.
