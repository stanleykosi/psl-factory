DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- This is not delivered elsewhere. F-18 built the RFP frame (`frontend/src/features/rfp/RfpFrame.tsx`), team input and the outcome on the SCR-16 boards. In that frame the Requirements, Pricing and Submission tabs are still plain text (RfpFrame.tsx:1-4, 30-36). F-18 also chose concept 1 of `SCR-26-team-input-concepts`. F-17 used SCR-26 review and edit only as region anchors for the generic frame (delivery/features/F-17/readiness.md:32-34, regions.json:112-312, test fixtures W-2002 and W-2006). Nothing under `frontend/src` renders the RFP requirements line.
- **Part 1 (this feature, 8 boards, D-64):** the PM works through the requirements. The boards are SCR-26 default, review, edit and reject, each desktop and mobile. The PM accepts one or several of Tola's suggested answers, edits and accepts one, or writes their own answer with a reason. The page shows the "Before review" team checklist and a "Send for review" button that stays disabled, with the reason as the backend returns it.
- **Part 2 (later feature, 4 boards):** SCR-26 accepted and response-review, desktop and mobile. Accepted needs G-26-4 (the `undo` step and `next_item_id`). Response-review needs the open Engineering Lead review rule (G-26-9, no decision id). Its Return and Reject buttons also need D-RETURN (r2 `open`, model.json:833-871).
- **Gates.** FE-RFP-RESPONSE has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:1877-1908). Its dependencies FE-WORKSPACE-FRAME (F-17, PR #30) and FE-M2B-RFP (F-18, PR #29) are merged. SCR-26 is in the 13 Nov client approval (design/review.json:39). The phone boards changed only under the recorded D-89 "+ Start" exception. D-LINE-WORKSPACE is still r1 `proposed` (model.json:1291-1319, also an M-5 gate). It counts only under the recorded exception that F-17, F-21 and F-30 used: contract mock only, the backend may change or refuse any field, nothing is released.
- I did not run `design.py check` (this role has no shell). The spec writer runs it first and stops if it fails. Pricing stays with FE-COSTING, which is gated by D-COSTING-RULE. The Pricing tab stays plain text, and this feature shows no amount, rate or approver.

## Scope
**Outcome (one):** a PM opens an RFP work item and lands on its Requirements workspace inside the F-18 RFP frame. They see the requirement rows, each with its RFP page, answer and status, plus progress counts and Tola's note. For each suggestion they can do one of three things:
- accept it (one row, or the ticked rows with "Accept selected");
- edit it and accept ("Save and accept");
- reject it and write their own answer with an internal reason. Tola's suggestion then shows read-only as "not used".

The team-input checklist links to the F-18 Record form. "Send for review" shows only as returned, disabled with the backend's reason. All of this runs on the contract mock at 390 and 1440.

**Boards (8):** `design/canvas/project/SCR-26-{desktop,mobile}`, `-{desktop,mobile}-review`, `-{desktop,mobile}-edit` and `-{desktop,mobile}-reject` (`.dc.html`).

**Task, endpoints, decisions:**
- Task: FE-RFP-RESPONSE (R-WORKITEM, R-DECIDE), acceptance A-WORKSPACE (frontend half).
- Endpoints: E-WORK-ITEM (`rfp`, `workspace`, `tasks[].response`), E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (backend-named steps such as `accept`, `accept_selected`, `edit_accept`, `write_own`; `add_requirement` only if returned), and the existing E-RESPONSE team input link. Both paths are typed in frontend/src/api/schema.d.ts:54 and :715.
- Decision consumed: D-LINE-WORKSPACE r1, under the recorded exception.

**Reuse, not rebuild:**
- The F-17 workspace renderer (`features/workspace/` Sections, Steps, StepForm, useWorkspaceStep).
- The F-18 `RfpFrame`, which gets a small edit to link the Requirements tab.
- The existing `itemValues` proposal (`features/workspace/proposals.ts:38-43`, F-23), so the edit form opens with the current answer. This covers G-26-3 on the mock.
- The shared `frontend/src/components/` (D-91).
- Fixtures and task ids come from the W-34xx and T-34xx blocks (NIGHT-LOG-2026-11-18.md:32).

**Contract gaps: build on the mock, record in build.md for the backend (delivery/backend-handoff/gaps-b-rfp-planning.md:56-78):**
- **G-26-1 (tabs and views).** The spec settles which tab is current on `/work/{id}` and where Team input links. Until `rfp.tabs[].work_id` or a `?view=` query is confirmed, Pricing and Submission stay plain text.
- **G-26-2 (section paging, search, filter and "all matching").** No section read exists in schema.d.ts. Until one exists:
  - filters and search render as F-17 renders them;
  - select-all covers only the rows that are shown;
  - bulk accept sends `item_ids`, never a server-resolved scope.
- **G-26-3 (prefill).** Use the `itemValues` overlay only.
- **G-26-5 and G-24-4 (rows and past answers).** The requirement rows and past-answer cites are fixture content marked "Suggested by Tola". Cites follow the per-record `restricted` rule. Nothing claims a past bid's result unless a field returns it.
- **G-26-7 and G-26-8.** Answer history and the clarification send are left out unless returned. The "4 OPEN" clarification count comes only from returned data.

**Binding rules for the spec:**
1. Controls show only for returned steps. Roles never grant one (INV-ACCESS). 403 and 404 look the same.
2. Bulk accept still records each answer under the PM's name, as the backend returns it.
3. Every write follows the F-17 rules: CSRF, `expected_revision` = `workspace.revision`, one `idempotency_key` per attempt, and no automatic retry.
   - A 409 keeps the typed answer and reloads.
   - A 422 maps the error to its field.
4. Agent text is shown as returned and is never a verified outcome. "Unknown" is never blank or 0.
5. The phone follows the precedent: a single column, 44px targets (D-92c), and the edit and write-own forms in the shared full-height Drawer (D-111, D-113). The mobile-review "swipe for the next" card is a spec conflict for the design engineer, because F-17 dropped that pattern.
6. Fidelity follows D-64 and D-83: one run per round over the 8 boards, axe at 390 and 1440, and exceptions in `delivery/features/F-37/fidelity-exceptions.json`.

**Out:**
- SCR-26 accepted and response-review (part 2).
- "Send for review" as a working write, the PMO Lead decision, and recording the Engineering Lead review.
- Pricing and costing (FE-COSTING, D-COSTING-RULE), submission (F-38, SCR-40), and the clarification send.
- Undo and "next: R-08", "Compare with v2", and the response PDF.
- Tola's requirement-extraction job (backend).
- Backend, OpenAPI, schema.d.ts regeneration, `architecture/**` and `src/shell/**`.

## Risk
Medium. The page has several behaviours: three per-row writes plus a bulk write on the shared F-17 step path, edits to the shared F-18 `RfpFrame`, and fields that are proposals only (G-26-1, -2 and -3 are additive), hence `contract-change`. It is not high because this part moves no money, sends nothing outside, changes no authority and runs on the mock only. The answers are internal until review, and each accept is recorded under the PM's name. PRODUCT-ACCEPTANCE is required because the accept, edit and write-own flows and their wording are new to the client.

## Questions
None for the client in part 1. The open items are backend confirmations: G-26-1, -2 and -3 and the three questions at gaps-b-rfp-planning.md:75-78. Part 2 waits on PSL for the Engineering Lead review rule (G-26-9, no decision id) and for D-RETURN.
