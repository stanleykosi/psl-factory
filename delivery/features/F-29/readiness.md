DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-29 is FE-DOCUMENT-REVIEW (SCR-08): 4 boards (default and returned, desktop and phone), inside the D-64 cap of about 8. One outcome, one PR: a reviewer reads a drafted client document, sees changes and checks, and approves or returns it. After a return, the PM sees the note.
- Gates are met. The task is in architecture v7 with `gate_ids: []` (architecture/packages/v7/delivery.md:2247-2276). Its dependencies are FE-M3-PROJECT-TABS (F-25, merged, PR #56) and FE-DECIDE (F-04, built). The screen is in the client-approved design set. I did not run `design.py check` (no shell in this role). The spec writer or builder runs it first and stops if it fails.
- The decision itself reuses the existing E-TASK-CLAIM and E-TASK-DECIDE writes from the built decide page. No new approver or rule is invented.
- Backend gaps G-SCR08-1..8 (gaps-a-project-setup.md:41-63) are additive contract proposals. They are built on the mock overlay only and the backend developer may change them. Nothing is released.
- Approving does not send the document to the client. The screen must not imply it does.

## Scope
**Outcome (one):** a person who may see a client document opens `/projects/[caseId]/documents/[documentId]?v=<version>` from the Documents tab. They read the numbered sections, see what changed since the previous version, the agent notes and the checks. The person whose task it is approves it or returns it with a note. On the mock only.

**Boards (4):** SCR-08 desktop, desktop-returned, mobile, mobile-returned (design/canvas main).

**Task and endpoints:** FE-DOCUMENT-REVIEW (R-PROJECT, R-DECIDE). Acceptance A-PROJECT-TABS and A-DECIDE, plus the existing tests staying green. Reads: E-DOCUMENT (GET /api/v1/documents/{document_id}/versions/{version}), E-PROJECT (title, pm, tab_counts), E-WORK-ITEM (tasks[].id, revision, you_can_act, cannot_act_reason, decision.changes, prepared_by, chain, workspace.agent_note). Writes: E-TASK-CLAIM and E-TASK-DECIDE (verdict approve or return, note needed for return, expected_revision, CSRF), the same as `/work/[id]/decide`.

**Reuse:** the F-25 project frame and tab bar, the F-04 decide controls and chain components, `frontend/src/components/` (D-91), and the mock plus `frontend/mock/proposals/*.json` overlay with the scenario cookies. Add the documents tab row link to this route if F-25 left it unlinked.

**Buildable on the mock:**
- Header: crumb, title, version, status, TEST TEMPLATE tag, audience.
- Sections with the changed marker, agent notes shown as agent text only, and the Checks panel.
- Default state: approve and return controls act on the task from E-WORK-ITEM, shown only when `you_can_act` is true. Otherwise show `cannot_act_reason` in plain words (including `prepared_by_you`).
- Returned state: who returned it, when, the quoted note, and "Approval on v2 is not carried over". The note is visible only where the backend sends it.
- Read states: loading, 401, 403/404 (look the same), error with retry. Absent values show "Unknown", never blank or 0 (INV-UNKNOWN).
- Phone: the back link and the "Tola flagged section 4" line as drawn.

**Held or out (do not build):**
- "Ask Tola to draft v3" and "Edit as v3" (G-SCR08-8). No operation exists. Render them disabled with a plain "not available yet" or leave them out, and list the choice in the exceptions file for the design engineer to sign. Do not call anything invented, and do not save a document from the browser.
- Sending the approved document to the client (a separate step and screen).
- CEO/CTO decision variants (D-DECISION-VARIANTS, not drawn here).
- Version compare beyond the changed-section marker (G-SCR08-4, nice-to-have).
- Backend, OpenAPI, schema.d.ts regeneration, `architecture/**`, `src/shell/**`. Record any gap as a contract proposal in build.md.

## Binding rules for the spec
1. No authority is invented. Controls follow `you_can_act` per task. Roles, personas and "PMO Lead" never grant a control. The "who reviews" label is shown only as the backend returns it.
2. Checks are shown as the backend returned them (done, held, blocked, unknown). The amount check says Unknown when costing is unknown and is never "matches" by default. The frontend computes no check and no section count itself.
3. Agent notes and drafted text are labelled as agent work and decide nothing. Approval and return are human acts and record the person's name and time as the backend returns them.
4. Return requires a note. The write sends `expected_revision` as read. A stale 409 shows the generic message, re-reads and does not auto-retry. A failed or timed-out write does not show "approved". Re-read before offering a retry.
5. Claim first when the task needs it, as on the decide page. Do not repeat the decide page's rules.
6. Mock names (Kemi Adebayo, Tola, Lagoon Health, SOW-0198, COST-0140) are fixtures only. The design examples supply no live policy.
7. Tokens and components only, 44px phone targets (D-92c), reduced-motion, labelled fields, errors announced. Section text is plain text, never injected HTML. `body_url` is a download link only.
8. Fidelity (D-64): UI review passes on the design-fidelity check of all 4 boards, every element present after approved exceptions, score of at least 90, one run per round. Axe at 390 and 1440.

## Contract proposals (build.md; mock overlay only)
- G-SCR08-1 `sections[]`, G-SCR08-2 `sections[].notes`, G-SCR08-3 `checks[]`, G-SCR08-5 `audience`, `review{work_id, task_id}`, `drafted_by`, G-SCR08-6 `case_id`, `project_title`, `reference`, G-SCR08-7 the return note (`chain.steps[].note` or `returned{}`). All additive. Until confirmed, the mock sends them and the page shows "Unknown" or hides the part when a field is absent. It never invents a value.
- G-SCR08-5: without `work_id` or `task_id` the page cannot reach its decision, so with them absent it shows read-only. It must not guess a task.
- G-SCR08-8 is held as above. G-SCR08-4 is not built.
- Backend questions already open and not blocking: whether the review is one task on the SOW work item, that the same person cannot approve what they prepared, body size and paging, and which step sends the approved document.

## Risk
Medium. Several behaviours (a document read, a decision write, a returned state) cross the layers on a contract that has seven proposed additive gaps, and one new route links the Documents tab to the decide writes. It is not high because there is no new authority, money, identity or migration. Decisions reuse the built E-TASK-DECIDE with its server-side checks, and the work is frontend and mock only (frontend/src/features, frontend/mock). SURFACES are ui, api and contract-change. PRODUCT-ACCEPTANCE is required: the document layout, the checks wording and the returned-state copy are new to the client. A product decision on the two draft-next-version buttons is needed from the design engineer as an exception, not as a block.

## Questions
None. The open items are backend contract confirmations and the exception for the held buttons. They do not hold this build.
