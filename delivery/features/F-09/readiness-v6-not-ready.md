DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: D-RESPONSE-VIEW, D-WORK-ACTIONS-VIEW, D-RFP-OUTCOME
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- Architecture v6 closes most of the gaps I raised in delivery/features/F-06/readiness-full-not-ready.md (PMO-0-1 to PMO-0-5). E-WORK-ITEM now carries `case_id`, `case_revision`, `tasks[].response`, `allowed_actions`, `reconcile` and `rfp_outcome`, and there is a new E-RFP-OUTCOME (packages/v6/model.json:2699-2846, 2976-3195, 9958-10095). FE-M2B-RESPONSE has no unresolved gates and depends only on FE-WORKITEM, which is merged (delivery.md:1232-1264, validation.json:178). The client approved SCR-16 and SCR-02 on 13 Nov (design/review.json). The three proposals are r1 `proposed`, and they count under the design engineer's recorded exception (decisions-2026-11-13-v3.md item 1, decisions-2026-11-14-v2.md (f)(g)), with the same limits as F-05.
- **Too big for one PR.** In scope are 28 boards (26 for SCR-16, 2 for SCR-02), three forms, five writes (E-EVIDENCE-UPLOAD, E-TASK-CLAIM, E-RESPONSE, E-WORK-ACTION, E-RFP-OUTCOME) and an RFP workspace frame. All of it is high risk. Proposed split: **F-09, Record a response and reconcile** (10 boards) and **F-09B, Team input and RFP outcome** (18 boards).
- **The standing rule cannot be met on v6.** The rule is "nothing on a board may be omitted; missing API data uses mock data from the proposal". But several elements drawn on the boards have no field in any v6 proposal, and the mock validates every fixture against openapi with `additionalProperties: false`. That leaves the builder no legal place to put the data (PMO-0-1, PMO-0-2). To fix this, D-RESPONSE-VIEW, D-WORK-ACTIONS-VIEW and D-RFP-OUTCOME each need an r2 in a v7 package. For F-09 alone, an explicit fidelity exception would also work.
- **F-09B has more than copy missing.** The rfp-unknown board has a **Send follow-up** email to the client's procurement address, and no endpoint exists for it (external messaging). The RFP tabs link to SCR-26, SCR-27 and SCR-40, which nobody has built, and the won board links to SCR-41.
- **Dependency.** The v4-to-v6 contract repoint belongs to F-05. F-05 is high risk, so under the overnight rules it will not merge. F-09 cannot type `tasks[].response` until a repoint is on the base (PMO-0-4).

## Findings
- PMO-0-1 | blocking | high | backend | F-09's boards (record a response and reconcile) show elements that no v6 field carries. The fixtures cannot hold these elements, because E-WORK-ITEM and E-RESPONSE are `additionalProperties: false`. Each element below is listed with the board line where it appears:
  - the intro sentence ("Lagoon Health's client contact doesn't log in… The release waits for this.", SCR-16-desktop.dc.html:20);
  - the proof hint ("Signed PDF, e-signature record, or the client's email saved as PDF", :34);
  - Tola's aside ("I'll check the PDF names build 2.4.0 and is signed by Dr Obi…", :46-47);
  - the success summary: "received by email", recorded by, recorded at, "1 proof file" (SCR-16-desktop-success.dc.html:17). E-RESPONSE's 200 returns only `task_id` and `work_state`, and the form has no channel field;
  - "What happens next" after recording (success, :17; SOW, SCR-16-desktop-sow-signed.dc.html:17, "the SOW's 4 stages become the project's milestones…");
  - the project crumb on the SOW board ("PROJECTS / TAMARIND LOANS / DOCUMENTS / SOW-0207");
  - on reconcile, the unknown option's "Keep it held and remind me tomorrow" and "A resend reuses the same invoice number" (SCR-02-desktop-awaiting-reconciliation.dc.html:17). Only `resend` is carried.

  Expected, either of these:
  - (a) D-RESPONSE-VIEW r2 adds optional `intro`, `proof_hint`, `agent_note {agent, lines[]}` and `next[]` to `tasks[].response`, plus a `recorded {by, at, received_via, proof_count}` block. D-WORK-ACTIONS-VIEW r2 adds `reconcile.unknown_note` and `reconcile.resend_note`. These go in v7, and the coordinator repoints the mock to v7.
  - (b) The design engineer records a fidelity exception in `delivery/features/F-09/fidelity-exceptions.json`. It approves static per-variant board copy, filled in only from returned fields, and names the sentences that cannot be filled (channel, "4 stages", the remind-tomorrow rule).

  Actual: a builder would have to hard-code record-specific text, or put fields in fixtures that fail `tests/mock-contract.test.ts`.
- PMO-0-2 | blocking | high | backend | The F-09B boards (team input and RFP outcome) need data that D-RFP-OUTCOME r1 does not carry:
  - **RFP workspace frame**, on every RFP board and on team input (SCR-16-desktop-team-input.dc.html:17, -rfp-outcome.dc.html:17): the status tag ("DEADLINE 28 NOV · 16 DAYS", "SUBMITTED 26 NOV", "WON · 04 DEC"), the "PM TUNDE BELLO" tag, and the five tabs with counts ("Requirements 64", "Team input 2/4"). The tabs link to SCR-26, SCR-27 and SCR-40, which are not built.
  - **The result boards:**
    - "What's recorded" rows;
    - the reminder holder and time ("Reminder for Tunde Bello · 10 DEC 09:00");
    - lessons as a categorised list with PRICE, TIMELINE and STRENGTH tags. The contract has `lessons` as one string and `recorded` as `{result, at, by}` only;
    - the archive reference ARC-0117;
    - the "Debrief notes (proof)" link;
    - "Engagement EN-0042 created", with "Open engagement EN-0042" linking to SCR-41;
    - per-result "What happens next" text.
  - **A write with no endpoint.** rfp-unknown has a follow-up email drafted by Tola, with **Send follow-up** and **Edit**. It goes to an external address (procurement@…).

  Expected: D-RFP-OUTCOME r2, plus an RFP frame proposal, in v7. The follow-up send needs its own proposed endpoint with idempotency and uncertain-effect handling (INV-RESEND). Until then F-09B stays NOT-READY.
- PMO-0-3 | blocking | medium | pmo | This is too big for one reviewable PR: 28 boards, five CSRF writes, three distinct forms and an unbuilt frame. Expected: split into F-09 (10 boards, Scope below) and F-09B (18 boards, listed below), and create F-09B as its own feature. Team input goes with F-09B because its board sits inside the RFP frame. FE-M2A-PROOF depends on FE-M2B-RESPONSE (delivery.md:1215-1218), most likely for the proof upload. F-09 should therefore export the proof field for reuse.
- PMO-0-4 | blocking | medium | integration | The contract repoint is not on the base. The base still runs on v4:
  - `frontend/mock/server.mjs:22`;
  - `package.json:12`;
  - `tests/api-schema-drift.test.ts:16`;
  - `src/api/client.ts:1`.

  F-05 owns the v6 repoint (F-05/readiness.md PMO-0-4), but F-05 is high risk and will not merge overnight. Expected: the coordinator lands a single repoint commit on the base before F-09 starts, to v7 if PMO-0-1 (a) is taken, or else F-05's five-file v6 commit on its own. F-05 and F-09 then rebase onto it. F-09 must not make its own repoint.
- PMO-0-5 | non-blocking | medium | backend | E-EVIDENCE-UPLOAD returns the new `case_revision` and says "send it as case_revision on the start, response or action that follows" (model.json:4580-4583). But E-WORK-ACTION's request has no `case_revision` (model.json:5021-5053, `additionalProperties: false`). Expected for the mock: reconcile sends the work `revision` as `expected_revision`, and sends `evidence_id` from an upload made with the work item's `case_revision`. Record this in build.md as a question for the backend developer.
- PMO-0-6 | non-blocking | low | frontend | The SCR-02 awaiting-reconciliation boards are whole work-item pages, and F-09 owns only the "Confirm what happened" panel. Expected: the UI reviewer scores both SCR-02 boards for the whole page. Any differences outside the panel (facts, track, header) are raised against F-03's files, not F-09's.
- PMO-0-7 | non-blocking | low | frontend | The entry point on SCR-02-desktop-waiting and SCR-02-mobile-waiting is a "Record the client's response" button inside the task panel. Today `TaskPanels` (WorkItemOverview.tsx:147-162) says "Only a {role} can decide" and "Open the decision" for every task. "Change the reminder" on the same board has no endpoint, so it stays out and is listed in build.md.
- PMO-0-8 | non-blocking | low | pmo | I could not run `design.py check`, because my role has no shell. A comment in the code says the board was changed on 14 Nov (WorkItemOverview.tsx:78, "design owner, 14 Nov 2026"), and the approval dates from 13 Nov. Expected: the coordinator runs the check and confirms the 28 boards still match the approved `design_sha256` before the spec is written.

## Scope
**Binding for the spec writer, once PMO-0-1 and PMO-0-4 are closed and the coordinator accepts the split: F-09 only.**

**Outcome (one, observable):** in the work item, the PM sees "Record the client's response" on a task with a `response` block. That opens `/work/<id>/respond?task=<task_id>`. There they pick who responded, when, what they did and which version, upload proof, confirm it is genuine and press Record. The success page follows. A Lead with `reconcile` in `allowed_actions` confirms what happened to an uncertain send from the work item. This works at 390px and 1440px on the contract mock.

**Boards in scope (10). Every element must be present, scored by the fidelity gate:**
- SCR-16-desktop.dc.html, SCR-16-mobile.dc.html
- SCR-16-desktop-validation.dc.html, SCR-16-mobile-validation.dc.html
- SCR-16-desktop-success.dc.html, SCR-16-mobile-success.dc.html
- SCR-16-desktop-sow-signed.dc.html, SCR-16-mobile-sow-signed.dc.html
- SCR-02-desktop-awaiting-reconciliation.dc.html, SCR-02-mobile-awaiting-reconciliation.dc.html (the panel, per PMO-0-6)
- Entry button only: SCR-02-desktop-waiting.dc.html, SCR-02-mobile-waiting.dc.html

**In:**
1. **Route.** `frontend/src/app/work/[id]/respond/page.tsx` takes `?task=`. It is a page, as drawn, not a drawer. Like `decide/page.tsx`, its title never names the item.
2. **Form** (`variant` `client_response` or `sow_signature`):
   - Fill it only from `tasks[].response`. The pickers are `responders` (name · role, organisation), `actions` (label from the API, e.g. "Declined" for `rejected`) and `versions` (label and note). Offer nothing the API did not return, and derive nothing from roles.
   - Proof goes up first through E-EVIDENCE-UPLOAD on `case_id` with `case_revision`, using `evidence_kind`. "Add another file" adds to `evidence_ids`.
   - When `claim_required` is true, call E-TASK-CLAIM before E-RESPONSE.
   - Submit E-RESPONSE with CSRF, `expected_revision` (the task revision), `case_revision` (from the last upload), `who`, `action`, `responded_at`, `evidence_id`, `attested`, `version_id` and an optional `note` of up to 2000 characters.
   - Record stays disabled until proof is added and the attestation is ticked, with the validation board's alert.
   - A 422 shows inline. A 409 keeps what was entered and reloads the work item. A 403 or 404 goes through `ApiError`, and a 401 through `SignedOutState`.
   - A double press never records twice: disable while a request is in flight. E-RESPONSE has no idempotency key, so the builder must not retry automatically after an uncertain result. Instead, reload the work item and show the recorded state if the task is already done.
3. **Success.** Shown after a 200, filled from the refetched work item and the PMO-0-1 fields, with "Back to the work item".
4. **Reconcile panel.** `ReconcilePanel` is shown only when `reconcile` is present and `allowed_actions` includes `reconcile`.
   - The outcomes come from `reconcile.outcomes`, the check sentence from `checks`, and the resend line from `resend`.
   - "It arrived" requires an upload of `evidence_kind`.
   - Submit E-WORK-ACTION `{expected_revision, action: "reconcile", outcome, evidence_id?}` with CSRF, then refetch.
   - No resend is ever triggered from the frontend.
5. **Entry from the work item. These are the only F-03 edits, each listed in build.md:**
   - In `TaskPanels` (WorkItemOverview.tsx:147-162), one branch. When `task.response && task.you_can_act`, show the response-variant wording and a button to `/work/<id>/respond?task=<task_id>` in place of "Open the decision". Put the variant labels in `src/features/response/labels.ts`.
   - In `WorkItemOverview` (line 184), one conditional mount of `ReconcilePanel` in the task column.
   - Do not touch `NextStep`: F-06 edits it for "See all exceptions".
6. **Reuse.** Export the proof field and the upload hook from `src/features/response/index.ts` for FE-M2A-PROOF.
7. **Mock.**
   - Handlers go in `frontend/mock/response.mjs` for E-EVIDENCE-UPLOAD, E-RESPONSE and E-WORK-ACTION. Each validates its body against the openapi schema with the existing ajv and answers 422 without proof or attestation, 409 on a stale revision, and 403 for a persona without the grant. A success swaps the work item through the existing override map.
   - E-TASK-CLAIM reuses F-04's handler.
   - Fixtures are W-1601 to W-1649: UAT response, SOW signature, awaiting reconciliation with `allowed_actions: ["reconcile"]`, the same item without the grant, and a `claim_required` task. Put the post-record variants in `fixtures/response/**`. All must be schema-valid.
8. **Tests.**
   - Component tests: only returned options are shown, the claim comes before the response, the disabled and alert state, the 422, 409, 403 and 401 paths, one record on a double press, the upload revision is carried into the response, and reconcile is hidden without the grant.
   - Mock-contract tests in `frontend/tests/response-mock.test.ts`.
   - Playwright and axe at 390px and 1440px for the default, validation, success, SOW and reconcile states.
   - Acceptance: A-RESPONSE and A-RECONCILE (frontend half), plus A-ACCESSIBILITY.

**Out:**
- Everything for F-09B.
- "Change the reminder".
- Resume and cancel buttons. `allowed_actions` carries them, but no board in scope draws them.
- Backend work (T-RESPONSE, T-EXCEPTIONS) and the real API.
- Edits to `architecture/**`, `openapi.json`, `src/api/**` and `src/shell/**`.
- New npm dependencies.
- A visible SAMPLE DATA tag (NEXT_PUBLIC_SHOW_SAMPLE_LABEL rule).

**Ownership (disjoint from F-02, F-05, F-06, F-07 and F-08):**
- Owns:
  - `frontend/src/app/work/[id]/respond/**`
  - `frontend/src/features/response/**`
  - `frontend/mock/response.mjs`
  - `frontend/mock/fixtures/response/**`
  - `frontend/mock/fixtures/work/W-16[0-4]x*.json`
  - `frontend/tests/response*.test.ts(x)`
  - `frontend/e2e/response.spec.ts`
- Shared, additive only, listed in build.md:
  - one `M1_OPERATIONS` entry and one dispatch line in `server.mjs`;
  - the two edits in `WorkItemOverview.tsx` (item 5).
- Does not touch:
  - `NextStep` and the exceptions files (F-06);
  - the start-work files (F-05);
  - the projects files (F-07);
  - the overview files (F-08);
  - `decide/**` and `my-work/**`;
  - the existing W-10xx, W-12xx, W-14xx and W-15xx fixtures.
- Rebase onto whichever lane touches `WorkItemOverview.tsx` or `server.mjs` first.

**F-09B, Team input and RFP outcome (NOT-READY until PMO-0-2 is closed).** It has 18 boards:
- SCR-16-desktop-team-input, SCR-16-mobile-team-input
- SCR-16-desktop-rfp-outcome, SCR-16-mobile-rfp-outcome
- SCR-16-desktop-rfp-outcome-lost, SCR-16-mobile-rfp-outcome-lost
- SCR-16-desktop-rfp-outcome-pending, SCR-16-mobile-rfp-outcome-pending
- SCR-16-desktop-rfp-outcome-unknown, SCR-16-mobile-rfp-outcome-unknown
- SCR-16-desktop-rfp-won, SCR-16-mobile-rfp-won
- SCR-16-desktop-rfp-lost, SCR-16-mobile-rfp-lost
- SCR-16-desktop-rfp-pending, SCR-16-mobile-rfp-pending
- SCR-16-desktop-rfp-unknown, SCR-16-mobile-rfp-unknown

It uses E-RESPONSE (`team_input`) and E-RFP-OUTCOME, and covers A-RFP-OUTCOME. Fixtures are W-1650 to W-1699. It reuses F-09's proof field and owns `src/features/rfp-outcome/**`.

**Task IDs:** FE-M2B-RESPONSE (R-RESPONSE, R-EXCEPTION). F-09 takes the response and reconcile part; F-09B takes team input and the RFP outcome. **Endpoints (F-09):** E-WORK-ITEM (read), E-EVIDENCE-UPLOAD, E-TASK-CLAIM, E-RESPONSE and E-WORK-ACTION, all on the contract mock.

## Risk
The rating is high:
- E-RESPONSE stores a sworn record: a staff member vouches for an outside party's UAT approval or SOW signature with proof. The record "can't be edited later" (SCR-16-desktop.dc.html:40, INV-AUDIT, REC-EVIDENCE).
- Reconcile can authorise a resend of an invoice to a client (E-WORK-ACTION, INV-RESEND).
- Both are CSRF writes with revisions. E-RESPONSE has no idempotency key, so a double submit is a real risk.

The surfaces:
- `security`: attestation, CSRF on four writes, and offering only actions the API grants (`allowed_actions`, `responders`, `actions`).
- `external-messaging`: the resend in F-09, and the follow-up email in F-09B.
- `contract-change`: three proposals, an r2 needed for each, and the repoint.
- `product-decision`: the RFP frame tabs that link to unbuilt screens, and the board copy that needs either fields or a fidelity exception.

`payments` is excluded: the awarded amount (F-09B) is recorded as stated in the letter and moves no money. Product acceptance is required, because this is a new flow and new copy for the client.

## Notes
- If the coordinator accepts the split and closes PMO-0-1 by route (a) or (b), and lands the repoint (PMO-0-4), re-run readiness for F-09. I expect READY, high, with `ui, api, security, contract-change, external-messaging`.
- The 13 Nov decision stands: Engineering Lead and Support do not log in, and the PM records their part. The responder list must come from `responders`, never from a hard-coded role list.

## Questions
None. The blockers are contract work (the r2 proposals, the follow-up endpoint), a split and a repoint. None of them is a client business rule.
