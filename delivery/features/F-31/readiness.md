DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-31 is part 1 of FE-ENGAGEMENT-PLANNING, with 8 boards: SCR-41 default and register, plus SCR-42 default and record, each on desktop and phone. That is the D-64 cap. It covers one outcome: a won RFP becomes a registered engagement, its planning page shows what each department owes, and the PM records what a department sent. It ships as one PR.
- I chose SCR-42 record over the suggested SCR-42 held. Record is the planning page's only human write in part 1, and it reuses the F-18 team-input form (`frontend/src/features/response/TeamInputForm.tsx`, E-RESPONSE `team_input`). Held is a read-only status. Its one action, "Open Setup › Rules", has no link target (G-42-4), and the default board already shows the OWNER NEEDED row. Held belongs with readiness and ready, which together finish planning.
- Gates are met. FE-ENGAGEMENT-PLANNING has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:1981-2012). It depends only on FE-WORKSPACE-FRAME (F-17, merged). F-18 (team input, `engagement_work_id`) is also merged. SCR-41 and SCR-42 are in the 13 Nov client-approved list (design/review.json:49-50, approved 2026-11-13). The D-89 "+ Start" exception does not affect them. M-5's D-COSTING-RULE gate applies to SCR-27 only.
- All the endpoints this part needs are in frontend/src/api/schema.d.ts: E-WORK-ITEM (:54), E-WORK-STEP (:715), E-WORK-ASSIGN (:736), E-RESPONSE (:180), E-EVIDENCE-UPLOAD (:159), E-PROJECT (:264) and E-RFP-OUTCOME `engagement_work_id` (:5053). The backend gaps are in delivery/backend-handoff/gaps-b-rfp-planning.md:134-178. The three SCR-41 blocking gaps (G-41-1, -4, -5) block the real write, not this screen, so they are built on the contract mock only, as in F-30. The SCR-42 blocking gaps (G-42-3, -5, -6) block readiness, hand-off and automatic repricing, which are part 2 or held.
- I did not run `design.py check` because this role has no shell. The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** when an RFP is won, the PMO Lead opens the engagement and sees Tola's planning packet, with unknowns kept as Unknown. The PMO Lead confirms the PM, who is prefilled from the RFP. The PM registers the engagement with plan evidence, start date and client project contact. The PM then opens the planning work item, sees what each department was asked for and where it stands, and records what one department sent, with proof, under their own name. Contract mock only.

**Boards (8):**
- SCR-41-desktop and SCR-41-mobile (default): the reference EN-0042 and "Route A · from won RFP" subtitle; the Planning packet table (PART / FROM / STATUS, with IN / UNKNOWN / NOT YET tags and a money cell); Tola's packet checklist; "Unknowns stay Unknown…"; and the "PM for this engagement" confirm step.
- SCR-41-desktop-register and SCR-41-mobile-register: the "Register the engagement" step. It has plan evidence (upload), start date (date, with the `date.unknown` form), client project contact (text), the "What registering does" consequence lines, and "Register engagement".
- SCR-42-desktop and SCR-42-mobile (default): the status "PLANNING · 2 OF 5 IN" and the PM fact; the "What each department must give" table (DEPARTMENT / WHAT WE ASKED FOR / STATUS / ESTIMATE / Proof, with "Record input" per waiting row and "Who receives this?" on OWNER NEEDED); the line "Departments don't log in…"; the estimate-changed finding; Tola's checklist; and the Readiness panel, where "Prepare readiness" shows disabled with its `disabled_reason` as returned.
- SCR-42-desktop-record and SCR-42-mobile-record: "Record department input". The department picker lists only waiting departments, with fields for what they gave, estimate in person-days, proof, received, and the attestation line "records their input under your name". This is the F-18 team-input form. On phones it opens in the full-height Drawer (D-92d), as F-30 does.

**Task and endpoints:** FE-ENGAGEMENT-PLANNING (R-WORKITEM, R-RESPONSE), acceptance A-WORKSPACE and A-RESPONSE.
- Reads: E-WORK-ITEM on `/work/{engagement_work_id}` (line `engagement`) and `/work/{planning work_id}` (line `planning`), and E-PROJECT for the project tab bar and `lines[]`.
- Writes: E-WORK-STEP (`register_engagement`, and `confirm_pm` if G-41-1 resolves to a step), E-WORK-ASSIGN (if G-41-1 resolves to assign), E-EVIDENCE-UPLOAD (plan evidence and department proof) and E-RESPONSE (`team_input`).

**Reuse, not rebuild:** the F-17 workspace frame and its line layouts (D-62, D-63, D-73, D-81), with its section, step and field renderers; the F-18 team-input form and response flow; `frontend/src/components/` (D-91); the F-25 project tab bar; and the `frontend/mock` workspace scenarios, plus an overlay in `frontend/mock/proposals/` for the items below. Add only the engagement scenarios (default, register) and the planning scenarios (default, record, recorded-then-reread). Use new fixture ids that don't clash with W-21xx, W-29xx or W-30xx.

**Contract proposals (mock overlay only; record them in build.md and the backend-handoff section):**
- G-41-1 (blocking for the real write): confirming the PM. Proposed: E-WORK-ASSIGN with an additive `assign.default_person_id`, so the PM picker shows the RFP's PM preselected and offers only `assign.candidates[]`. Until confirmed, nothing outside the candidates may be sent, and the page does not say a PM is confirmed until the re-read says so.
- G-41-2 (open PSL question, no decision id): build the confirm step as drawn, keep it removable, and check its wording at product acceptance.
- G-41-3: if the awarded amount and the costing total differ, show both, each labelled by its source. They are never merged, and the browser computes nothing.
- G-41-4 (blocking for the real write): plan evidence is uploaded before the project exists. On the mock, upload to the engagement's existing `case_id`/`case_revision` from the response. On a 409, re-read before any retry. The staging or own-case question (G-23-5) stays with the backend.
- G-41-5 (blocking for the hand-off link): registering returns only `{work_id, state, revision, outcome, message}`. Proposed: an optional `created[] {kind, case_id?, work_id?, reference, line?}`, plus `queued` / `effect_uncertain` with a reconcile path. Until confirmed, the page shows the backend's message, then re-reads. It links to the new project and planning item only from ids that are returned. It never claims all three effects happened, and it never re-sends while the result is uncertain (one `idempotency_key` per attempt).
- G-41-6: the client project contact is a plain text step input. Whether it is required, and where it is stored, is a backend question; there is no front-end rule.
- G-42-1: the ESTIMATE cell needs a `quantity {value?, unit, unknown}` cell. Until confirmed, show the backend's text as returned ("230 person-days", "Unknown", "No effort"). The browser does not total the estimates or count them.
- G-42-2: `teams[].disabled_reason` / `asked_at`. The record form lists only the teams the response offers as recordable, and the browser does not decide which departments are waiting.
- G-42-3 (product question, not a front-end blocker): Tola's "Sent requests … EMAIL · 08 DEC" is shown only as a returned checklist item, never as a verified send. Whether the factory may send department requests needs a PSL decision, which belongs on the backend list.
- G-42-5: the estimate-changed finding is shown as returned, with its cites. "Open costing" shows only if the response sends a link; SCR-27 is held by D-COSTING-RULE. Nothing starts costing v3.
- G-42-7: "Planning" in the tab bar is a link to the planning work item from E-PROJECT `lines[]`. It is not a new tab.

**Part 2 (later feature, 6 boards):** SCR-42-desktop-held, SCR-42-mobile-held, SCR-42-desktop-readiness, SCR-42-mobile-readiness, SCR-42-desktop-ready and SCR-42-mobile-ready. Part 2 is held on G-42-6, which asks who accepts readiness and what makes planning verified; that needs a PSL rule and has no decision id. G-42-4 (the Setup rule for department receivers, and a link target) and D-ALERT-PROVIDERS ("the PMO Lead has been alerted") also apply. Part 2's readiness should go back through the PMO.

**Out:** pressing "Prepare readiness" and anything after it; the held, readiness and ready states; Setup rules for department receivers; costing v3 and SCR-27; sending any department request; the SOW (SCR-16); backend, OpenAPI, schema.d.ts regeneration, `architecture/**` and `src/shell/**`.

## Binding rules for the spec
1. Every control (confirm PM, register, record input, "Who receives this?", "Prepare readiness") shows only when the response sends it. Roles never grant a control (INV-ACCESS). 403 and 404 look the same.
2. Writes send CSRF, `expected_revision` as read, and `case_revision` where a record or evidence field is used. Steps also send an `idempotency_key`, kept across a retry of the same attempt. If a write fails, times out or has an uncertain effect, the page does not show "registered" or "recorded"; it re-reads before offering a retry.
3. Department input is recorded under the PM's name, with the attestation the F-18 form already enforces. The page must not suggest the department logged in. The received time is sent as entered; the backend validates it.
4. Unknown values show "Unknown", never blank or zero. "No effort" (not applicable) stays separate from 0 and from Unknown, exactly as returned. The browser computes no totals, counts ("2 of 5"), price differences or overdue status. Status and tone come from the backend.
5. Agent text (Tola's packet work, sent requests, the estimate finding, "Ask Tola") is shown as returned and labelled as Tola's. It is never a verified outcome. "Ask Tola" shows only if a link is returned (as in F-29 and F-30).
6. Use tokens and shared components only: labels on every field, errors announced, reduced motion respected, 44px targets on phones (D-92c, D-95), one Drawer component (D-92d).
7. Fidelity (D-64): run the design-fidelity tool once per round over all 8 boards, and run axe at 390 and 1440. Line-screen standard (D-83): 100% coverage after exceptions, no fixable gap in the UI side-by-side reading, and visual >= 70, with a waiver signed per board. Put the differences in the exceptions file for the design engineer.

## Risk
Medium. Part 1 has several behaviours across two line workspaces (four writes: confirm PM, evidence upload, register, record input) on the shared F-17 frame, and it adds additive contract proposals (G-41-1, -4, -5, G-42-1, -2), so it touches a cross-layer contract. Registering creates the project and starts planning. That effect happens in the backend and is hard to undo, but here it runs on the contract mock only. The front end's part is limited to an idempotent single step that re-reads and doesn't retry while the result is uncertain, which keeps it below high. The backend task for G-41-5 should be rated high. SURFACES are ui, api and contract-change, plus product-decision because the boards draw two open PSL questions (G-41-2 re-asking for the PM, and G-42-3 agent-sent department requests) that are shown here but not decided. auth is not ticked: no new authority rule is added, and the PM can be chosen only from the candidates the backend returns. external-messaging is not ticked: this part sends nothing outside. PRODUCT-ACCEPTANCE is required because the engagement registration and the "record department input" flows, and their wording, are new to the client.

## Questions
None for this part. The open items are backend confirmations (the proposals above and the questions in delivery/backend-handoff/gaps-b-rfp-planning.md:150-153 and 174-178). The PSL questions (G-41-2, G-42-3, G-42-5, G-42-6) hold part 2 or the real behaviour, not this build.
