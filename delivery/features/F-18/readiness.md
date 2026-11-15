DECISION: READY
RISK: high
SURFACES: ui, api, security, contract-change, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-18 is FE-M2B-RFP (F-09B). It covers team input and the RFP outcome inside the RFP frame, plus the drafted follow-up. Both dependencies, FE-M2B-RESPONSE (F-09) and FE-CONTRACT-V7 (F-13), are merged. The task has no gates (architecture/packages/v7/delivery.md:1776-1807).
- The contract is in v7. D-RFP-OUTCOME r2 (model.json:1155-1195) adds the RFP frame, `rfp_outcome`, lesson categories, the recorded block and the drafted follow-up. E-RFP-OUTCOME (openapi.json:12092) and E-RFP-FOLLOWUP (openapi.json:12447) are the two writes. Team input uses E-RESPONSE with the `team_input` variant.
- D-RFP-OUTCOME is still `proposed` at r2. It counts only under the design engineer's recorded exception (decisions-2026-11-14-v2.md (e)-(g), decisions-2026-11-15.md (h)(i)). The limits are the contract mock only, the backend developer may change or refuse any field, and nothing is released. That is why BLOCKING-DECISIONS is none.
- The 18 boards are inside the client approval of 13 Nov (design/review.json lists SCR-16, hash 9fad8d2d...). I cannot run `design.py check` from this role, so the coordinator must run it before the spec is written.
- Risk is high: the outcome is a sworn record of money-adjacent business fact, and the follow-up is an external email sent by a person. Under the overnight rules it is built and reviewed but not merged. It waits for the design engineer.

## Scope
Binding for the spec writer.

**Outcome (one):** the PM opens an RFP work item and sees the RFP frame. They record team input on its task. After submission they record the RFP outcome (won, lost, pending or unknown) with proof. For an unknown outcome they can review, edit and send the follow-up the agent drafted. The recorded state then shows as returned. All of this works at 390px and 1440px on the contract mock.

**Boards (all elements present, scored by the fidelity gate, 18 in total):**
- SCR-16-desktop-team-input and SCR-16-mobile-team-input.
- SCR-16-desktop-rfp-outcome and SCR-16-mobile-rfp-outcome, plus their -lost, -pending and -unknown variants (the form before recording).
- SCR-16-desktop-rfp-won, -rfp-lost, -rfp-pending and -rfp-unknown, plus the four mobile equivalents (the recorded state).
- The spec writer must open each board and confirm the list against `design/canvas/project/SCR-16-*`. Unlisted boards are out.

**In:**
1. **RFP frame**, drawn from the work item's RFP frame block only: reference, title, client, status tag with days left, PM, and the five tabs with counts. Absent counts are not shown. The tabs link only to routes that exist on the base. SCR-26, SCR-27 and SCR-40 are unbuilt (FE-RFP-RESPONSE and FE-RFP-SUBMIT depend on this task), so those tabs render as text or disabled. The spec must say which.
2. **Team input.** The `team_input` variant on the existing response route, reusing the F-09 form and the proof field exported from `src/features/response/index.ts`. Fields: `teams`, `blocking`, `team`, `estimate_person_days`, `what`. Options come only from the API. Add a `team_input` label to `RESPONSE_LABELS.entry`, as the F-09 technical review asked. Writes go through E-RESPONSE with CSRF and the existing claim, 409, 422 and uncertain-effect rules.
3. **RFP outcome form**, shown only when the work item returns an `rfp_outcome` block. Results, reasons, lesson categories and `record_as` come only from that block. Fields:
   - when it was learned;
   - the role recorded as;
   - proof;
   - a note;
   - reason and categorised lessons for lost;
   - awarded amount for won, where **unknown stays unknown and is never 0**;
   - expected decision date and reminder for pending.

   The write is E-RFP-OUTCOME with CSRF, `expected_revision` and `case_revision`. A person outside `record_as` sees no form. A 409 keeps what was entered and reloads. After an uncertain result, reload and never retry automatically.
4. **Recorded states.** won, lost, pending and unknown are drawn from the returned recorded rows, reminder holder and time, categorised lessons, debrief proof, archive reference and engagement (created and next lines). Leave out any element whose field is missing and substitute no board copy.
5. **Follow-up (unknown).** Show the draft the agent wrote: recipient as returned, body, version, checks, status, `can_send` and `can_edit`.
   - Copy: "It goes only if you send it".
   - Send and Edit are person actions. E-RFP-FOLLOWUP carries the expected revision, the draft version and an idempotency key generated once per attempt.
   - Disable the button while in flight. A double press makes one send.
   - `effect_uncertain` shows the uncertain state and offers no resend until the backend reconciles it (INV-RESEND). The frontend never resends on its own.
   - A stale draft version (409) reloads the draft.
   - An agent never sends.
6. **Mock.** Follow the F-09 pattern: `mock/rfp.mjs` (or an extension of `response.mjs`) validates against v7, answers 422, 409 and 403, and checks CSRF and `X-Mock-Scenario`. Follow-up scenarios: success, a repeat with the same key returning the same result, `effect_uncertain`, and a stale version. Fixtures cover the RFP states, a person without the grant, and one item with every r2 field absent. Keep them out of the base's v4-only checks if any still apply; F-13 has landed, so validate against the repointed contract and `OPENAPI_PATH`.
7. **Tests.**
   - Component tests: only returned options are shown; no form without the block; unknown amount stays unknown; double press makes one send; uncertain effect blocks resend; absent fields leave elements out; the 422, 409, 403 and 401 paths.
   - Mock contract test.
   - Playwright and axe at 390px and 1440px for each state.
   - Acceptance: A-RFP-OUTCOME and A-RFP-FOLLOWUP (frontend half), plus A-ACCESSIBILITY.

**Out:**
- The RFP response workspace (SCR-26/27, FE-RFP-RESPONSE) and RFP submission (SCR-40, FE-RFP-SUBMIT). Landing on SCR-41 after a win is also out.
- Backend work (T-RESPONSE) and the real API.
- Edits to `architecture/**` and the openapi file.
- Shell edits beyond what F-13 already provides.
- New npm dependencies.
- Email provider choice (D-ALERT-PROVIDERS stays open).
- Any rule on who may record or send. The backend decides, and the frontend shows only what it returns.

**Sizing note.** 18 boards, three writes and a frame is the upper bound for one PR. It stays one feature because the boards share the frame and the form. The spec should order the work in two commit slices: (A) frame, team input and outcome form; (B) recorded states and the follow-up send. If the build runs past one UI review round, the coordinator may split slice B into its own feature.

**Task IDs:** FE-M2B-RFP (R-RESPONSE). **Endpoints:** E-WORK-ITEM (read), E-EVIDENCE-UPLOAD, E-TASK-CLAIM, E-RESPONSE (team_input), E-RFP-OUTCOME, E-RFP-FOLLOWUP, all on the contract mock. **Decisions consumed:** D-RFP-OUTCOME r2 (proposed, exception-limited) and D-RESPONSE-VIEW r2.

## Risk
High. E-RFP-OUTCOME stores an uneditable business fact (won, lost, an awarded amount that can be unknown, lessons) that later creates an engagement. E-RFP-FOLLOWUP sends an external email to the client's procurement address, and a repeat or uncertain send is the main failure to guard against (INV-RESEND, INV-AGENT).

Surfaces:
- `ui` and `api`.
- `security`: CSRF on the writes, and showing the form and send only when the backend grants them.
- `external-messaging`: the follow-up.
- `contract-change`: the work runs on a proposed decision, D-RFP-OUTCOME r2, under the recorded exception.

`payments` is excluded because no money moves, and the awarded amount is only recorded as returned. Product acceptance is required: this is a new flow with new copy that the client must see.

Coordinator action before the spec: run `design.py check`, and confirm that the 18 boards still match the approved hash 9fad8d2d....
