DECISION: READY
RISK: medium
SURFACES: ui, api, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Not built anywhere yet. F-05 (FE-M2A) lists SCR-23 as out of scope (delivery/features/F-05/readiness.md:90, spec.md:334). F-18 has no SCR-23 or SCR-24 work, and nothing in frontend/src handles `rfp_intake` or an RFP assign panel. The pieces are there to reuse: the Unassigned queue in My work (F-02, `features/my-work/model.ts:27`), `AssignForm` and `useWorkspaceAssign` (F-30), and the mock's E-WORK-ASSIGN handler (`frontend/mock/workspace.mjs`).
- Gates are met. FE-RFP-INTAKE has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:1843-1875). Its dependencies FE-M2A (F-05), FE-MYWORK (F-02) and FE-CONTRACT-V7 (F-13) are merged. The client approved SCR-23 and SCR-24 on 13 Nov (design/review.json:36-37). D-RFP-INTAKE r1 is `proposed` and owned by the backend developer. It is built on the contract mock only, the same way F-30 built E-WORK-ASSIGN.
- The task has 4 boards, but SCR-23 is not buildable yet. Its core input, "The RFP document", is an evidence intake field. In Start work that is FE-M2A-PROOF (F-47), which has no readiness yet: `start-work/intake.ts:11` says so, and `IntakeField.tsx:209` draws "Proof upload comes next". Building it here would collide with F-47 in `intake.ts` and `IntakeField.tsx`.
- **First outcome (2 boards): SCR-24, Assign the accountable PM.** **Part 2 (2 boards): SCR-23, Log a received RFP.** Part 2 starts after F-47 merges evidence intake.
- I did not run `design.py check` (no shell in this role). The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a PMO Lead (or whoever the backend lets assign) opens an RFP from the My work Unassigned queue. They see which client and RFP it is, choose the accountable PM from the people the backend lists, and see the role they are assigning in. They can add a note and optional proof, then press assign. The RFP leaves Unassigned and the page shows who it is now assigned to. Contract mock only; nothing is released.

**Boards (2):** design/canvas/project/SCR-24-desktop.dc.html (panel over the work item) and SCR-24-mobile.dc.html (full screen, back link "My work").
- Header "Tamarind Loans · TL-RFP-2026-014" from `rfp.client` and `rfp.reference`.
- "Accountable PM" list showing name, role and load hint (`assign.candidates[]`), and "n people can prepare RFPs here" from the length of the list.
- "You are assigning as".
- "Proof (optional)".
- Note (`note_required`).
- "What happens next".
- Cancel and assign.

**Task and endpoints:** FE-RFP-INTAKE (R-START), acceptance A-ASSIGN, and the Unassigned part of A-START-INTAKE (the logged RFP shows as Unassigned). Endpoints:
- E-WORK-LIST `?queue=unassigned`
- E-WORK-ITEM (`assign`, `rfp`, `revision`)
- E-WORK-ASSIGN, POST /api/v1/work/{work_id}/assignment, body `expected_revision, person_id, note`; 200 returns `assigned_to`
- E-EVIDENCE-UPLOAD, only through the proof proposal below

All of these are in frontend/src/api/schema.d.ts (assign block at line 1900, E-WORK-ASSIGN at line 5329).

**Reuse, not rebuild:**
- `features/workspace/AssignForm.tsx` and `useWorkspaceAssign.ts`, lifted so they also work on a work item that has no line workspace. Do not fork them.
- `features/response/ProofField.tsx` and `useEvidenceUpload.ts` (F-09) for the proof.
- The My work Unassigned tab.
- `frontend/src/components/` (D-91).
- The mock's E-WORK-ASSIGN handler, extended by scenario. Fixtures use the W-33xx block (NIGHT-LOG-2026-11-18.md:32).

**Contract proposals (mock overlay only; record each one in build.md for the backend developer, delivery/backend-handoff/gaps-b-rfp-planning.md:36-52):**
- **G-24-1 (`assign.roles[]` and request `acting_role`).** Until it is confirmed, show the single `assign.role` as read-only text. Show a role select only when the overlay returns more than one role, and offer only the roles returned. Never take a role from `/me`.
- **G-24-2 (`evidence_id` on assign, `assign.evidence_kind`).** Until it is confirmed, the proof field appears only in overlay mode. A failed or uncertain upload is never sent as attached.
- **G-24-3 (`assign.next {summary, agent, channels[]}`).** Show only the channels and agent text the backend returns. Without the overlay, the block is static board copy that names no channel. Do not claim "Tola investigates" happened: that needs G-24-4, a job the backend has not defined.

**Part 2, F-36B, SCR-23 Log a received RFP (2 boards), held until F-47 merges.** This is the `rfp_intake` line on the existing Start work drawer: client picker, RFP reference, RFP document upload, received time, submission method and target, deadline (unknown, stated or not stated), and note. Its mock overlays are G-23-1 (new client, blocking for the real write), G-23-2 (`show_when`), G-23-3 (deadline state) and G-23-5 (the shared fixed intake case and its 409 contention, blocking for the real write). Its readiness is re-checked once F-47 is merged.

**Out:**
- Reassigning an RFP after the first assignment (no board; a question for the backend).
- The RFP response workspace (SCR-26, F-37).
- The analysis job JOB-RFP-ANALYSE (G-24-4).
- The real alert sending (I-ALERTS).
- SCR-23.
- Any backend, OpenAPI or schema.d.ts regeneration, `architecture/**`, `src/shell/**`, or `features/start-work/**`.

## Binding rules for the spec
1. **Authority comes from the response.** The panel shows only when `assign` is returned and has candidates. The person is chosen only from `assign.candidates[]`: nothing is preselected and no owner can be typed. The acting role is chosen only from the roles returned. Nothing is derived from `/me` roles (INV-ACCESS). 403 and 404 look the same.
2. **Who may assign is a policy the backend holds.** It is a PSL Setup rule, `presale.rfp_assigner`, which exists only in SCR-13 mock fixtures. It is not in model.json or guide/10-POLICY-CONFIGURATION.md. If the backend sends no `assign`, the page shows no assign control and invents no fallback assigner. The mock's candidates are board sample people, not real approvers.
3. **Writes.** Each write sends CSRF and `expected_revision` as read. Only one write runs at a time. A 409 keeps what was chosen, reloads the item, and offers assign again only if the item still returns `assign`. A failed or timed-out write never shows "assigned": re-read first, and show the result only from `assigned_to` and `state` as returned.
4. **Display.** Unknown values show "Unknown". Labels on every field, errors announced, reduced motion respected, 44px targets on the phone (D-92c), and tokens and components only.
5. **Fidelity (D-64).** One design-fidelity run per round over both boards, scoring at least 90. Axe at 390 and 1440. Any difference goes in the exceptions file for the design engineer.

## Risk
Medium. Assigning the accountable PM changes who is responsible for a client bid. It is also the first write that records an acting role as the authority in the audit (G-24-1), so `auth` is ticked. The surface is small, though: one existing write (E-WORK-ASSIGN, already exercised by F-30), the candidates and roles are limited to what the backend returns, and there is no money, migration or client sending. SURFACES are ui, api, auth and contract-change (G-24-1, -2 and -3 are additive proposals). PRODUCT-ACCEPTANCE is required because the assign flow, its wording and the "What happens next" copy are new to the client.

## Questions
None for PSL. The open items are backend confirmations, and they hold the real write, not this build:
- G-24-1, -2 and -3, and the three questions at delivery/backend-handoff/gaps-b-rfp-planning.md:49-52.
- For part 2: G-23-1 and G-23-5, and the questions at lines 28-32 of the same file.
