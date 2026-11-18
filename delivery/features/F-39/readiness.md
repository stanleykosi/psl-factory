DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- FE-EMERGENCY-ESCALATION has 22 boards (SCR-50: 10, SCR-51: 12), which is too many for one PR under D-64. Part 1 (this feature) is the escalation up to the PMO Lead's decision: SCR-51 investigating, decide, not-escalated and draft, desktop and phone, 8 boards. The other 14 boards are split into parts 2 to 4 below.
- Gates are met. The task has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2146-2177). SCR-50 and SCR-51 are in the client-approved list (design/review.json:58-59, 13 Nov, with only the D-89 "+ Start" frame exception). Both dependencies are merged: FE-WORKSPACE-FRAME is F-17 and FE-M2A is F-05, both DONE and merged.
- How this relates to F-30: F-30's overdue issue (W-2412) draws "Raise an escalation". That button opens the Start work drawer on the `escalation` line, prefilled with the project and issue (`mock/fixtures/start-work/lines.pm.json:225`, F-30 spec AC 10). Nothing is sent until the person presses the drawer's own start. Start goes through E-WORK-START (F-05) and returns a `work_id`. This feature is the `/work/{work_id}` page that work item opens. Part 1 changes neither the issue page nor the drawer, and the issue stays open (board: "The issue stays open with its owner").
- How this relates to FE-DECIDE-VARIANTS: the CTO's emergency pre-authorisation (SCR-03 cto-emergency) belongs to FE-DECIDE-VARIANTS, which is gated on D-DECISION-VARIANTS (open: "Not designed", model.json:1017-1030). Part 1 does not touch it. SCR-50 parts 3 and 4 only read the authorisation record. They never decide it and never type it.
- Part 1 builds on the contract mock only, like F-21 to F-33. D-LINE-WORKSPACE and D-TASK-DECISION-VIEW are still proposals. Nothing goes to the client in part 1: the client message is only drafted and sent for internal review. I did not run `design.py check` (this role has no shell), so the spec writer runs it first and stops if it fails.

## Scope
**Outcome (one):** after a PM raises an escalation from an overdue issue, the escalation page shows what Tola is checking. The PMO Lead then decides "Escalate to the client" or "Don't escalate" (with a note). A refusal ends as NOT ESCALATED with the note quoted. An escalation goes on to Tola's draft "Message v1", which the PM sends for review. Contract mock only.

**Boards (8):** design/canvas/project/SCR-51-{desktop,mobile}-{investigating,decide,not-escalated,draft}.dc.html.
- Investigating: status "INVESTIGATING", with facts Raised by, From issue and Asked for ("ESCALATE TO THE CLIENT"). Tola's checklist ("step 3 of 4", WORKING) shows each item's `detail` as returned ("ACT-0420 · OVERDUE 15 DAYS", "MILESTONE 3 · GO-LIVE 4 DEC"), plus "Started 13 Nov 11:00" and Ask Tola.
- Decide: status "YOUR DECISION", the "What Tola found" findings with `cites`, and the "Decide · PMO Lead" panel with its consequence sentence. The note is labelled "(needed to return or refuse)". The buttons are "Escalate to the client" (`approve`) and "Don't escalate" (`reject`).
- Not-escalated: status "NOT ESCALATED", the refusal note as returned text, the Next line, and "Back to the issue".
- Draft: status "MESSAGE DRAFTED", "Message v1" as text with the "FACTS AND DATES ONLY" tag, and Tola's done list ("Used the PMO Lead's decision · ESCALATE · 13 NOV", "Listed the recipients · SPONSOR · PROJECT CONTACT"). Then the Next line and the `send_for_review` step ("Send for review").

**Task and endpoints:** FE-EMERGENCY-ESCALATION (R-WORKITEM, R-DECIDE), acceptance A-WORKSPACE.
- Reads: E-WORK-ITEM `GET /api/v1/work/{work_id}`, which carries the workspace block, `tasks[]` with `you_can_act`, `required_role`, `cannot_act_reason` and `decision` (frontend/src/api/schema.d.ts:54, 1359-1427).
- Writes: E-TASK-CLAIM `POST /api/v1/tasks/{task_id}/claim` (:96), E-TASK-DECIDE `POST /api/v1/tasks/{task_id}/decision` (:117) and E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (:715).
- Fixture ids: W-36xx and T-36xx (night log 06:16).

**Authority:** the decide controls show only when the task returns `you_can_act: true`. The panel's role words come from `required_role`, and a person who cannot act sees `cannot_act_reason` and `asked` as returned. No role, name or board label grants a control, and neither does "PMO Lead". A missing reviewer or an unset policy is a hold that shows the returned `disabled_reason`, never a default. guide/10-POLICY-CONFIGURATION.md and contracts/policy-slots.json have no escalation slot. Slot D01 (emergency, UNCONFIGURED) applies to SCR-50 only.

**Reuse:** the F-17 workspace frame and its section, step and field renderers, the line layout frame (D-73, D-81) and the F-16 decide-in-place pattern (`frontend/src/features/decide/useDecision.ts`), as F-33 used it. Components come from `frontend/src/components/` (D-91). Phones use one column with 44px targets (D-92c), and the note form opens in the shared Drawer (as decided for F-30 in D-111).

**Contract proposals (mock overlay only; record in build.md for the backend developer; delivery/backend-handoff/gaps-c-client-lines.md:112-130):**
- G-SCR51-2 (X-VERDICTS): add `tasks[].decision.verdicts[]` with label, consequence and `note_required`. "Don't escalate" is `reject` and closes the escalation as NOT ESCALATED. Until the backend confirms this, the button words come from the overlay and the backend is asked.
- G-SCR51-4: the crumb "REGISTERS / ESCALATIONS / ESC-0012" has no `escalations` register enum. Show it as plain text built from returned ids, or list it as a frame exception.
- G-SCR51-5: `cites` for `action_id` and `issue`. Counts and dates show only as returned.
- G-SCR51-6: "Back to the issue" uses X-LINKS. Until the backend confirms it, the link is built only from ids in the response; without such an id it is not drawn.
- G-SCR51-1: which internal notes skip review. Part 1 shows only the steps that are returned and does not default the rule.

**Out (named parts):**
- **Part 2: SCR-51 review and received, 4 boards.** The PMO Lead approves the exact message ("Approve and send" or "Return with a note"), and the page shows each recipient's receipt. It is a client send (external-messaging). It waits on G-SCR51-3 (every recipient taken from contact records, with approval bound to the version and the recipient list), G-SCR51-1, D-RETURN for "Return", and the backend's refusal to resend while delivery is uncertain.
- **Part 3: SCR-50 record, refused, review and retro, 8 boards.** It waits on G-SCR50-1 (the `record_outcome` step is held until an authorisation record exists, and the record is read from FE-DECIDE-VARIANTS' decision), G-SCR50-2 (outcome fields, with an unknown customer count shown as "Unknown", never 0), G-SCR50-3 (outcome reviewer role unnamed) and G-SCR50-4 (which Lead decides the retrospective, recorded by the PM). D01 is UNCONFIGURED. Expect NEEDS-INFO until the backend answers those questions.
- **Part 4: SCR-50 report, 2 boards.** Tola's client and leadership report with per-person receipts. It waits on G-SCR50-6 (X-CLIENT-SEND, a review task before the send).
- **Also out of part 1:** the CTO pre-authorisation decision (FE-DECIDE-VARIANTS), any change to the issue page or the Start work drawer, creating the escalation or changing the issue's state (backend), and editing the draft message (an open backend question). Backend work, OpenAPI, schema.d.ts regeneration, `architecture/**` and `src/shell/**` are also out.

## Risk
Medium. Part 1 has several behaviours on the shared workspace block (F-17): an agent checklist, a claim-and-decide with a required note on refusal, and a step write. It also adds additive contract proposals (X-VERDICTS, the escalations enum, cites, links), so SURFACES are ui, api and contract-change. It is not high and has no external-messaging surface, because nothing reaches the client in part 1. The decision only allows a draft that still faces review in part 2. Authority is never decided in the browser, only rendered from `you_can_act` and `required_role` (schema.d.ts:1364-1365), so the auth surface is not ticked. PRODUCT-ACCEPTANCE is required because the escalate and don't-escalate decision, its wording and the drafted client message are new flows the client must see.

## Questions
None for part 1. The open items are backend confirmations and design notes. They hold the real write or later parts, not this build:
- Does "Don't escalate" notify the person who raised it?
- May the PMO Lead edit the draft?
- The phone decide board has no note field (gaps-c-client-lines.md:128-130).
