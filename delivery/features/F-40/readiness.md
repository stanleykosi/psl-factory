DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- FE-DELIVERY-CLOSURE has 20 boards. That is more than one PR under D-64, so I split it into three parts. **Part 1 is SCR-48, handover to Support: 8 boards** (default, record, gaps, received, each on desktop and phone). Its one outcome: Tola drafts the handover, the PM publishes it, and the PM records Support's reply with proof. A reply with gaps goes back to Tola for v2. "Acknowledged" shows only when the backend verifies it.
- The only gate that fails is a dependency, as for F-34. Every SCR-48 board is drawn inside F-32's Delivery tab: the crumb is "PROJECTS / … / DELIVERY / HND-0048", and the boards draw the delivery sub-nav (Overview … Handover, Closure). They also need a `work_id` on the Handover row (HND-0048) of F-32's P-0101 `delivery[]` fixture. F-32 (branch fe-delivery-release-delivery-tab-and-release-gate) is not merged: the approver said ESCALATE, and it is waiting for the design engineer's waivers and "merge". Once F-32 is in dlv-00, part 1 becomes READY with no other change. The spec can be written now against F-32's branch head. Nothing is built until F-32 merges.
- The other gates pass:
  - FE-DELIVERY-CLOSURE has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2350-2382). Its declared dependency FE-WORKSPACE-FRAME (F-17) is merged. The M-6 gates (D-LINE-WORKSPACE, D-CHANGE-DECIDERS, D-DECISION-VARIANTS) do not list this task.
  - SCR-33, SCR-48 and SCR-49 are in the 13 Nov client approval (design/review.json:45, 56, 57; approved 2026-11-13T15:33:13Z, with the D-89 frame-only exception).
  - D-LINE-WORKSPACE and D-RESPONSE-VIEW are `proposed`. They count only under the recorded contract-mock exception (architecture/sources/decisions-2026-11-15.md (g), (i)), as for F-30, F-32 and F-34.
  - Flow-audit conflict C is closed: Support has no login, and the PM records the reply with proof (architecture/sources/flow-audit.md:125; 13 Nov decision).
- Authority and money, stated plainly:
  - **Part 1 has no human decision and touches no money.** A handover review exists only if the Setup rule `delivery.handover_review` requires one. That rule is Not set (frontend/mock/fixtures/setup/delivery.desktop.json:52-63), so the page shows the hold. It never shows the board's "NO · BELOW THE RULE'S THRESHOLD" as a real value.
  - **Closure (part 3) is the PMO Lead's decision** under D-ROLE-PMO, revision 1, approved (architecture/model.json:753-778). The page takes authority only from `tasks[].required_role` and `you_can_act`. It names no approver.
  - Unpaid invoices on the closure boards (INV-0533 OWED) belong to Finance. They are shown as returned, never changed, and closing does not erase debt.
- I did not run `design.py check`, because this role has no shell. The spec writer runs it first and stops if it fails.

## Scope
**Outcome, part 1:** on a project's Delivery tab, a person opens the Handover row and reaches the handover work item (`/work/{work_id}`, line key `delivery_handover`, HND-0048). There:
- The PM sees Tola's draft (Support handover v1, the runbook and escalation contacts, TEST TEMPLATE) and can "Publish to Support".
- The PM records Support's reply: who replied, when, Received or Gaps found, the gaps, and the proof file.
- With gaps, the PM sees them listed as OPEN and can "Ask Tola to draft v2".
- With no gaps, the PM sees the acknowledged, verified banner.

All of it runs on the contract mock.

**Boards (8):** `design/canvas/project/SCR-48-desktop*.dc.html` and `SCR-48-mobile*.dc.html`:
- **Default ("HANDOVER · READY TO PUBLISH"):** the handover facts, "Review needed?", Tola's three steps, Next, and step `publish` (`sends: true`) with its consequence sentence as returned.
- **Record ("Record Support's reply"):** the shared response form from `src/features/response/`, variant `support_handover` (already in `contract.ts:7`). It reuses the F-18 form in the shared Drawer, as F-31 did. Fields: `who` from `responders[]` (Femi Ojo · Support lead), `responded_at`, the actions from `response.actions[].label` (Received, Gaps found), gaps, proof through E-EVIDENCE-UPLOAD, `attested`, and "What happens next" from `response.next`.
- **Gaps ("GAPS · 2"):** the gaps `checklist` with OPEN items, the returned banner sentence, Next, and step `draft_v2`.
- **Received:** the verified banner, "Recorded by Tunde Bello with Support's reply as proof", Next, and "See what closure needs" as a `work` link. That link is drawn only if it is returned. Closure is not built, so the link points to a plain work item or is left out.

**What F-40 needs from F-32 (merge F-32 first):**
- the Delivery project tab (`PROJECT_TABS` `delivery`), with D-113 conflict 5 applied: the sub-nav sits on the Delivery tab only and is a frame exception on line items and on phones;
- the `workspace.links[]` kind `work` and the "links only from data" rule (G-44-2);
- the frame rule that a decision step follows its task's `you_can_act`. Part 1 does not need it, but a handover review task would, and part 3 depends on it;
- the P-0101 `delivery[]` rows and the move of the boards' Tamarind Loans to Lagoon Health (P-0101) as sample data.

F-40 adds a `work_id` to the Handover row (HND-0048) as an additive edit. F-34 adds one to the Hypercare row of the same fixture, so whichever merges second keeps both. Fixture ids are W-37xx and T-37xx (night log).

**Task and endpoints:** FE-DELIVERY-CLOSURE (R-WORKITEM, R-RESPONSE), acceptance A-WORKSPACE and A-RESPONSE. All of the following are in frontend/src/api/schema.d.ts, so no new endpoint is needed:
- E-WORK-ITEM `GET /api/v1/work/{work_id}` (:54)
- E-WORK-STEP `POST /api/v1/work/{work_id}/steps` for `publish` and `draft_v2` (:715)
- E-TASK-CLAIM, only when `claim_required` (:96)
- E-RESPONSE `POST /api/v1/tasks/{task_id}/response` (:180; `action` enum at :2455)
- E-EVIDENCE-UPLOAD (:159)
- E-WORK-ACTION `reconcile` (:201)
- E-PROJECT (:264)

**Contract proposals (mock overlay only; record each in build.md for the backend developer; from delivery/backend-handoff/gaps-d-delivery.md:135-150):**
- **G-48-1 (blocking for the real write):** Received maps to `approved` and Gaps found to `changes_requested`, with labels from `actions[].label`. A `gaps: string[]` field is required with `changes_requested`, and each gap is returned as a checklist item with an id.
- **G-48-2 (blocking for the real send):** no Support recipient or channel exists in integrations.csv. "Publish" is a mock step. A send whose result is unknown shows `receipt: uncertain` and offers `reconcile`, never a resend.
- **G-48-3:** `unknown` on plain items. While `delivery.handover_review` is Not set, a fixture shows "Review needed? Unknown", and Publish carries the returned `disabled_reason`. The board's "NO · BELOW THE RULE'S THRESHOLD" appears only in a fixture marked sample.
- The board's "Open question for PSL: Support doesn't log in…" note is not drawn, because conflict C is closed. It is listed as an exception, as D-113 did for F-31.

**Later parts (12 boards):**
- **Part 2, 4 boards: SCR-33 retrospective (desktop, phone) and SCR-49 blocked (desktop, phone).**
  - This needs the backend to choose G-33-1 / G-49-1. Recommended is option A: the factory opens the closure work item when go-live is verified, so the retrospective steps `save_retrospective` and `save_draft` and the prerequisites checklist live in its workspace.
  - The mock can follow option A.
  - The "Finance confirmation" row reads Unknown (G-49-2).
  - The browser never decides that closure can start.
- **Part 3, 8 boards: SCR-49 default, decision, returned and closed (desktop, phone).** Expect NEEDS-INFO and high risk:
  - Every one of these states assumes Finance has confirmed. Where that confirmation comes from, and who gives it, is undefined: G-49-2, flow-audit 5.4, and the Setup rule `delivery.closure_finance_confirmer` is Not set (delivery.desktop.json:36-50). PSL must answer before these states can be specified.
  - The returned board depends on D-RETURN, which is `open` (model.json:833-852).
  - What a closed project refuses (G-49-3, `project_closed`) needs a backend answer. The Finance follow-up of open invoices stays allowed, and invoices, receipts and allocations are never changed.
  - The PMO Lead decides through the F-16 page, with controls only from `you_can_act`.

**Out of part 1:** SCR-33 and all of SCR-49. Setting or editing any Setup rule. Any real send to Support. Any review decision. Any closure, read-only lock or invoice effect. Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**` and `src/shell/**`.

## Binding rules for the spec
1. **Controls and authority from the response only (INV-ACCESS).** `publish`, `draft_v2` and the record form show only when the response sends them. No role or persona grants a control, and 403 and 404 look the same.
2. **Writes guarded.** Writes send CSRF and `expected_revision` as read. Steps also send an `idempotency_key`. The proof is uploaded before E-RESPONSE. A failed, stale or timed-out write never shows "published" or "recorded". The page re-reads before offering a retry. After `effect_uncertain`, it offers no resend until a reconcile.
3. **Verified only from the backend (INV-AGENT).**
   - "Acknowledged" and the green banner come only from the returned `state` and status tone `verified`.
   - Tola's steps and "draft v2" text are shown as returned and are never a verified outcome.
   - "Recorded by" shows the recording person; Support is never shown as having logged in.
4. **Unknown, not zero; no rule in the browser.**
   - The review threshold, the gap count ("GAPS · 2") and the "closure needs" sentence are drawn only from returned values.
   - No rule wording goes in `src/`.
   - A missing value reads "Unknown".
5. **Design system, fidelity and builder.**
   - Tokens and `@/components` only (D-91). Labels on every field. 44px phone targets (D-92c). Reduced motion respected. Axe at 390 and 1440.
   - One fidelity run per round over the 8 boards (D-64). Boards below 90 follow the D-83 waiver route, signed by the design engineer.
   - Sonnet builder.

## Risk
Medium for part 1. The page has four states, two step writes (one of them a send), a recorded response with proof and a proposed gaps field, all on the shared F-17 frame and the F-18 response form. That makes it a cross-layer contract with additive proposals (G-48-1 to -3; contract-change).

`external-messaging` is ticked because "Publish to Support" is a send with no defined channel (G-48-2). On the mock, nothing is sent, and the existing uncertain and reconcile path covers an unknown result. `product-decision` is ticked because `delivery.handover_review` is a PSL rule that is still Not set; the page only shows the hold.

Part 1 has no money, identity, migration or decision authority, so `auth` and `payments` are not ticked. Part 3 will be high risk with `auth` and `payments`: the PMO Lead's closure, the read-only lock, and Finance's open invoices shown next to it.

PRODUCT-ACCEPTANCE is required because the handover flow and its wording are new to the client.

## Questions
None for part 1. The block is F-32's merge. Backend confirmations hold the real write, not the mock build: the G-48-1 mapping and gaps field, the G-48-2 Support channel, and what closes a gap (gaps-d-delivery.md:147-150).

For part 3, PSL will need to answer: where "Finance confirmation" before closure comes from and who gives it (G-49-2, `delivery.closure_finance_confirmer`), and what "return" does on closure (D-RETURN).
