DECISION: READY
RISK: high
SURFACES: ui, api, security, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- **Not done elsewhere.** F-17 and F-18 only list SCR-40 as out of scope (F-18 readiness.md:27,55; spec.md:166). `frontend/src/features/rfp/RfpFrame.tsx:3-4,21` renders the "Submission" tab as plain text because "the screens behind ... Submission are not built". delivery/screen-coverage.md:143 says "none yet". No code under frontend/src draws the pack, its checks, the reviewer decision or the submitted receipt.
- **One outcome, all 8 SCR-40 boards, which is the D-64 cap.** The PM sees the submission pack Tola assembled and sends it for review. The document reviewer approves, returns or rejects that exact version. The page then shows the submitted state and its receipt as the backend returns them. Contract mock only. Nothing reaches a client.
- **Gates.** FE-RFP-SUBMIT has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:1910-1942). It depends on FE-WORKSPACE-FRAME (F-17) and FE-M2B-RFP (F-18), and both are merged. SCR-40 is in the 13 Nov client approval (design/review.json:48, approved_at 2026-11-13T15:33:13Z). The M-5 milestone gate D-COSTING-RULE covers only SCR-27 ("SCR-27 passes once D-COSTING-RULE is decided", delivery.md:238). D-LINE-WORKSPACE r1 is `proposed`, and this work uses it under the same mock-only limits as F-21..F-33. D-RETURN r2 is `open`, but its text tells the frontend to build against it as a working assumption (model.json:859-863). I could not run `design.py check` because this role has no shell, so the coordinator runs it before the spec.
- **The price is never this screen's business.** The commercial proposal is one pack part, shown as the backend returns it: label, version and tag. No amount is drawn, computed or put in fixtures. A real submission cannot happen until D-COSTING-RULE is decided and a costing version is approved in order, because the backend's own check "Costing approved in order, same version as the proposal" holds the Approve step.
- **F-37 is not a hard dependency.** FE-RFP-SUBMIT does not depend on FE-RFP-RESPONSE. The two share `RfpFrame.tsx` tab links and the open tab-routing gap G-26-1. This feature links its tab only through `tab.work_id`, so it works whatever F-37 decides about the view parameter. Whichever of the two merges second keeps both tab links.

## Scope
Binding for the spec writer.

**Outcome (one):** an RFP's Submission tab opens the submission work item inside the F-18 RFP frame. The PM sees what goes to the client, the checks and Tola's assembly list. They can edit the cover letter if the backend offers it, and send the pack for review. The document reviewer decides on that exact pack version. After approval the page shows "Submitted" with what happened and the receipt, exactly as returned, plus "Record the outcome" (F-18). The page works at 390px and 1440px on the contract mock.

**Boards (8):** design/canvas/project/SCR-40-{desktop,mobile}-{draft,review,submitted,submitted-portal}.dc.html. The spec writer confirms every element against them.

**Task, acceptance, endpoints:**
- Task and acceptance: FE-RFP-SUBMIT (R-WORKITEM, R-DECIDE); A-WORKSPACE and A-RECONCILE (frontend half), plus A-ACCESSIBILITY.
- Reads:
  - E-WORK-ITEM (GET /api/v1/work/{work_id}): `rfp` frame and tabs, `workspace` (checklist, timeline and text sections, `steps`, `revision`, `version`), `tasks[].decision` (`version`, `recipient`, `chain`), `reconcile` and `allowed_actions`.
  - E-DOCUMENT (GET /api/v1/documents/{document_id}/versions/{version}) for "Open the full pack".
- Writes:
  - E-WORK-STEP (POST .../steps): `edit_cover_letter` and `send_for_review`.
  - E-TASK-CLAIM and E-TASK-DECIDE (POST /api/v1/tasks/{task_id}/decision): approve, return or reject.
  - E-WORK-ACTION (POST .../actions): reconcile.
- All of these exist in frontend/src/api/schema.d.ts (lines 54, 117, 201, 306, 715; `rfp.tabs[].key: "submission"` and `work_id` at 1684-1688; `reconcile` at 1544; `rfp_outcome.submission` at 1569).

**Reuse, not rebuild:**
- The F-18 RfpFrame. Its Submission tab links to `/work/{tab.work_id}` only when the tab carries `work_id`; otherwise it stays plain text.
- The F-17 Workspace sections, StepForm and useWorkspaceStep.
- The F-16 DecidePanel and useDecision, used in place as in F-33 (D-113).
- The ReconcilePanel (frontend/src/features/response/ReconcilePanel.tsx).
- The shared library in frontend/src/components (D-91).
- 44px phone targets (D-92c); phones show F-18's "← RFP" bar (D-60a).
- Fixtures W-3501..W-35xx and T-35xx (night log 06:16). Sample names come from the boards only.

**What is sent and what is held (external messaging):**
- *What this frontend sends:* only the person's own requests:
  - the cover-letter edit and "Send for review" steps (CSRF, `expected_revision`, `idempotency_key`);
  - the reviewer's verdict on the exact `decision.version` (CSRF, claim, `expected_revision`, a required note for Return);
  - a reconcile answer.
- *What the backend would send* (G-40-1, not this build): on Approve, the approved pack version's document, to the target the RFP recorded (`rfp.submission_plan`, G-23-4), the way the client asked (email or portal). The frontend never composes, addresses or triggers that send directly, and an agent never submits.
- *Held:* no real send exists.
  - No email provider has been chosen (D-ALERT-PROVIDERS is open), and there is no portal adapter (G-40-2).
  - The backend has not yet enforced the resend refusal and idempotency (BACKEND-HANDOFF priority 1).
  - No costing can be approved while D-COSTING-RULE is open.
  - So the mock only simulates submitted, receipt and `effect_uncertain`.
  - Merging waits for the design engineer, as for F-18.

**Binding rules:**
1. Controls (Edit cover letter, Send for review, Approve and submit, Return, Reject, reconcile) appear only when the response sends the step, the `you_can_act` flag or `allowed_actions`. No role, Setup row or agent text grants one. 403 and 404 look the same.
2. The Approve button carries the backend's consequence sentence and recipient as returned ("Approving lets the factory submit this exact pack"). The decision names `decision.version`. If the pack has changed (409), the page reloads and does not resubmit.
3. After `effect_uncertain` the page shows the uncertain state and the reconcile panel and offers no resubmit until the backend reconciles (INV-RESEND, F-17 QA-5-5 lock from `item.reconcile`). No board draws this state, so it reuses the shared panel and is listed as an exception.
4. Show the "Submitted" title, the receipt words and timeline rows only as returned. Do not hard-code "delivery confirmed" or "verified as sent" (G-40-3: a mail server accepting a message is not proof the client has it). "Verified" appears only from a returned verified status.
5. Pack parts, checks and tags (IN, DRAFT, TEST TEMPLATE) come from returned sections. The browser does not compute the 20 MB check, the "submit by" date or the approvals count. "all 4 approvals" is stale against D-APPROVAL-ORDER (three steps), so show the returned text and list it for the design engineer.
6. Prefill is not in v7, so "Edit cover letter" opens only if the step sends its current text (G-26-3). Otherwise it is drawn disabled with "Not available yet" (the F-29 precedent). "Ask Tola" follows the same rule (G-40-8).
7. Unknown values show "Unknown". Agent text is labelled as Tola's and is never a verified outcome.
8. Fidelity follows D-64/D-83: one run per round over the 8 boards, axe at 390 and 1440, and differences listed in the exceptions file for the design engineer.

**Contract proposals (mock overlay; record in build.md for the backend developer):**
- G-40-1: approve enqueues the send of the approved version only, plus a `sha256` on the version.
- G-40-2 and G-23-4: `rfp.submission_plan`, plus `record_manual_submission` for by-hand submissions.
- G-40-3: what `received` means.
- G-40-4: size and content type.
- G-40-9: the submission record is the one that `rfp_outcome.submission` (E-RFP-OUTCOME) reads.
- G-26-1: the Submission tab carries `work_id`.
- G-26-3: prefill.

**Questions for PSL** (product acceptance; they hold the real send, not this build):
- G-40-6: may a pack with a TEST TEMPLATE part be approved and sent?
- G-40-5: the "submit by" lead time.
- G-40-7 and D-RETURN: what Return and Reject do to the RFP.
- Is the configured publisher (`rfp.submit` in apps/policy/factory_rfp_validators.py:32) different from the document reviewer?

**Out:**
- SCR-26/27 (F-37 and FE-COSTING), and any price or amount.
- By-hand and not-stated submission boards (not drawn).
- The outcome form (F-18).
- Backend, OpenAPI, schema.d.ts regeneration, `architecture/**` and `src/shell/**`.
- New npm dependencies.

## Risk
High. Approving this pack is the step that releases a priced commercial proposal to a client by email or portal. The release cannot be undone, and its main failures are a double or uncertain send and sending a pack other than the approved version (INV-RESEND, G-40-1). SURFACES:
- `security`: CSRF, claim, and controls only from the response.
- `external-messaging`: the submission.
- `contract-change`: D-LINE-WORKSPACE `proposed` plus the G-40/G-26 proposals.
- `product-decision`: G-40-3/5/6 and D-RETURN, settled at product acceptance.

`payments` is excluded because no money moves and no amount is shown. Product acceptance is required because this is a new client-facing flow with new copy.

## Questions
None block the build. PSL's answers to the questions listed under Scope hold the real send only.
