# RFP submission: the PM sends Tola's submission pack for review, the document reviewer decides on that exact pack, and the Submission tab shows "Submitted" and the receipt only as the backend returns them (contract mock only)

> Tasks: FE-RFP-SUBMIT (R-WORKITEM, R-DECIDE; acceptance A-WORKSPACE and A-RECONCILE frontend halves, A-ACCESSIBILITY, with the F-16, F-17, F-18, F-28 and F-33 tests kept green). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; FE-RFP-SUBMIT at `architecture/packages/v7/delivery.md:1910-1942`, `gate_ids: []`, "Unresolved gates: none"; depends on FE-WORKSPACE-FRAME (F-17) and FE-M2B-RFP (F-18), both merged. Endpoints typed in `frontend/src/api/schema.d.ts`: E-WORK-ITEM `:54` (`tasks[].decision` `:1368`, `allowed_actions` and `reconcile` `:1541-1566`, `rfp_outcome.submission` `:1569`, `rfp` and `rfp.tabs[].work_id` `:1663-1690`, `workspace` `:1693-1904`), E-TASK-CLAIM `:96`, E-TASK-DECIDE `:117` (`work_state` `:2157`), E-WORK-ACTION `:201`, E-DOCUMENT `:306`, E-WORK-STEP `:715`. This feature changes no generated type. Decisions consumed: D-LINE-WORKSPACE (`proposed`, used under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)); D-RFP-OUTCOME r2 (`proposed`, as F-18); D-RETURN (open, revision 2, "the frontend builds against it as a working assumption", `architecture/model.json:859-869`); D-64, D-83, D-89, D-91, D-92c, D-111, D-112, D-113. Open and held: D-ALERT-PROVIDERS, D-COSTING-RULE, G-40-1 to G-40-9 (`delivery/backend-handoff/gaps-b-rfp-planning.md:109-130`), G-23-4, G-26-1, G-26-3. Design: client-approved canvas version 1794581312-b166 (13 Nov 2026, `design/review.json:48`), republished with "+ Start" as 1794762832-cab1 (D-89, D-90); `design.py check --project .` run for this spec on 18 Nov: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`). Screen: SCR-40, all 8 artboards in `design/canvas/project/`: `SCR-40-{desktop,mobile}-draft`, `-review`, `-submitted`, `-submitted-portal`. Models: `delivery/features/F-28/spec.md` (receipts, shape), `F-33/spec.md` (decide in place), `F-18/spec.md` (RFP frame, outcome).

## What is sent, and what stays held (read first)

- **On the contract mock, nothing reaches a client.** There is no email, no portal, no real recipient, no real company form and no real submission record. Every "Submitted", "Emailed", "Sent", "Delivered", "confirmed" and "receipt" word on these boards is text a fixture returns, as a backend would return it. The PR and `build.md` must say so and must not claim a working submission, delivery, receipt check or duplicate-send protection.
- **What this page sends (to the local mock only), and nothing else:** the person's own steps.
  - The PM's cover-letter edit (E-WORK-STEP `edit_cover_letter`) and "Send for review" (E-WORK-STEP `send_for_review`). Each carries CSRF, `expected_revision` = `workspace.revision` and a UUID `idempotency_key`.
  - The document reviewer's claim and verdict on the exact pack version the task names (E-TASK-CLAIM, then E-TASK-DECIDE `approve`, `return` or `reject`, with CSRF and `expected_revision` = the task revision; a note is required for return and reject).
  - A reconcile answer after an uncertain send (E-WORK-ACTION `reconcile`, one POST per press).
- **What the backend would send (G-40-1, not built anywhere):** on Approve, the approved pack version (`decision.version.document_id`) and only that version, to the target the RFP recorded (`rfp.submission_plan`, G-23-4), the way the client asked (email or portal). The frontend never composes, addresses, triggers or retries that send. An agent never submits.
- **Held, because a product or backend decision is open:**
  1. the real send: no email provider (D-ALERT-PROVIDERS) and no portal adapter (G-40-2);
  2. the server-side resend refusal and idempotency (BACKEND-HANDOFF priority 1; E-TASK-DECIDE also has no idempotency key, F-33 PMO-3-1);
  3. any real approval: the backend's check "Costing approved in order, same version as the proposal" cannot pass while D-COSTING-RULE is open;
  4. what Return and Reject do to the RFP (D-RETURN, G-40-7);
  5. whether a pack with a test-template part may be sent (G-40-6);
  6. the "submit by" lead time (G-40-5);
  7. what counts as "delivered" (G-40-3).
  The page shows whatever the re-read work item says and adds no rule. Merging waits for the design engineer, as for F-18.
- **Held on the page itself:** "Submitted", a receipt and "Record the outcome" appear only when the re-read item returns them. After an uncertain send (`effect_uncertain`, or a `reconcile` block), the only action is the reconcile panel. There is no "Send again" and no resend, and no step or decide control is live until the backend reconciles (INV-RESEND, the F-17 lock from `item.reconcile`). No price, amount or approver name is shown unless the response returns it, and this feature's fixtures return no amount.

## Conflicts with the boards (for the design engineer, before the build)

"Recommend" is what this spec builds if no answer comes. Each difference becomes an entry in `delivery/features/F-38/fidelity-exceptions.json` with `approved_by: "builder proposal, pending design engineer"` until signed. "Proposal" means a field or reading used on the mock only; the backend developer may change or refuse it.

### Need an answer

1. **The review board is a decision page with no RFP frame.** `SCR-40-desktop-review` draws the crumbs "DECISION · TL-RFP-2026-014 · SUBMISSION", the title "Review the submission pack · v1" and no tab bar. The phone board goes back "← My work".
   - **Recommend:** decide in place on the same work item (`/work/W-3502`), as F-33 (D-113). The review fixture returns no `rfp` block, so the page draws the line header from `workspace.context.crumbs`, `title` and `subtitle` exactly as the board does. The RFP frame stays "drawn when returned". Whether the backend omits `rfp` for the reviewer goes to the backend developer as a proposal.
   - **Option B:** the review fixture carries `rfp`, and the frame and tabs are drawn above the review. The title, crumbs and tab bar then differ from the board (listed as exceptions).
2. **The Approve button should say where the pack goes.** Readiness rule 2: Approve carries the consequence and the recipient as returned. The board names the address only in the Checks row.
   - **Recommend:** the Decide panel shows one extra line, "Goes to procurement@tamarindloans.example", from `tasks[].decision.recipient`, and only when it is returned. It is added to F-33's `InlineDecide` and is absent for every F-33 fixture, because none carries a recipient. Listed as an extra element (`safety`).
   - **Option B:** no extra line. The Checks row is the only place the address appears.
3. **The submitted boards give one overall delivery claim, not a receipt per person.** F-28's rule is that "Sent", "Delivered" and "Received" show only from a returned `receipt`.
   - **Recommend:** the submitted fixtures carry a `recipients` section titled "Sent to" with one item: the address or "Client's procurement portal", the channel, `receipt` and `at`. The word comes from `RECEIPT_WORDS`. This is an extra element (`safety`), as F-28 Conflicts 1.
   - **Option B:** timeline rows only, with the receipt shown as returned row text. Not recommended: it cannot show an uncertain receipt as such.
4. **"Delivery confirmed" and "verified as sent" may say more than a mail server's acceptance proves (G-40-3).**
   - **Recommend:** the fixtures return the board's words as sample text, and the page composes none of them. The real words are the backend's, settled with PSL at product acceptance (question 13). No "Verified" or "confirmed" string is in `src/`.
   - **Option B:** the fixtures use weaker words now ("Accepted by their mail server"). These differ from the board and are listed.
5. **No board draws an uncertain submission.**
   - **Recommend:** fixture W-3505 is served after an approve that answers `work_state: effect_uncertain`. Its re-read shows:
     - the backend's status (`uncertain` tone);
     - the "What happened" timeline with no receipt row;
     - "Sent to" with `receipt: uncertain`;
     - the shared `ReconcilePanel` from `item.reconcile`, with no `resend` or `resend_note` text;
     - no "Record the outcome".
     This state has no board and is not in the fidelity run. The panel's placement is listed (`no board`).
   - **Option B:** the design engineer draws `SCR-40-*-uncertain` first. The uncertain half then waits.
6. **"Costing v2, all 4 approvals" is stale.** D-APPROVAL-ORDER (approved 13 Nov) has three steps.
   - **Recommend:** the fixtures say "costing v2, all 3 approvals", and Tola's source tag says "COSTING V2 · 3 APPROVALS". This is a listed text difference until the design engineer corrects the boards.
   - **Option B:** keep the board's "4" in sample data.
7. **The submitted boards end with a design note:** "If delivery hadn't been confirmed … this would show 'Effect uncertain' …".
   - **Recommend:** not drawn, and not in the fixtures, because it describes a state the page is not in (F-33 Conflicts 6 precedent). Listed as a difference.
   - **Option B:** draw it only if the backend returns it as the timeline section's `note`, word for word.
8. **"Edit cover letter" needs the letter's current text (G-26-3).**
   - **Recommend:** the step's `cover_letter` long_text field carries `value`. `StepForm` already opens a long_text with it (`StepForm.tsx:180-181`). The form opens on press (D-98), in the `Drawer` on phones.
   - When the backend cannot send the text, it returns the step with `disabled_reason: "Not available yet"`. The frame draws that as it already does (fixture W-3507), never as an empty editor.
   - The phone draft board draws no "Edit cover letter" or "Ask Tola". Both are extras on the phone.
   - **Option B:** hide "Edit cover letter" until the backend supports prefill.
9. **The note label says "(needed to return)", but the decide rule also needs a note to reject** (`mock/server.mjs` `NOTE_REQUIRED`, F-16).
   - **Recommend:** use F-33's composed label "Note (needed to return or reject)". This is a wording difference, checked at product acceptance.
   - **Option B:** the board's words, which are then wrong for Reject.
10. **A pack with a TEST TEMPLATE part can be approved on the board (G-40-6).**
    - **Recommend:** the page shows only what the backend offers. The board fixture (W-3502) offers Approve, because it is sample data.
    - W-3508 shows the backend holding Approve: the step is sent with `disabled_reason: "A part still uses a test template."`, and Return and Reject stay live.
    - The real rule is PSL's (question 11).

**Questions for PSL** (they hold the real send, not this build):

11. May a pack that still has a test-template part be approved and sent to a client? (G-40-6)
12. How many days before the client's deadline must we submit? The board's "submit by 26 Nov" assumes 2. (G-40-5)
13. What may the page call "delivered": the client's mail server accepting it, or only a receipt from the client? (G-40-3)
14. When the reviewer returns or rejects a pack, what happens to the RFP? (D-RETURN, G-40-7)
15. Is the person allowed to submit for PSL (the "publisher") the same as the document reviewer? (`rfp.submit`, `apps/policy/factory_rfp_validators.py:32`)

### Layout

16. **Desktop RFP frame on a line workspace.** The draft and submitted boards draw the F-18 frame above the workspace: "PRE-SALE / RFP · TL-RFP-2026-014", "Tamarind Loans · loan origination RFP", the status tag, "PM TUNDE BELLO" and five tabs.
    - **Recommend:** `LineHeader` (`features/work-item/WorkItemView.tsx:145`) draws the existing `RfpFrame` when `item.rfp` is returned on desktop. It replaces the crumbs and h1, and `item.title` becomes the workspace's h2 ("Submission pack · v1", "Submitted · delivery confirmed").
    - With the frame drawn, a line status tag is drawn only from a returned `workspace.status`, with no state-tag fallback.
    - Spacing differences are listed (`frame layout`).
17. **The Submission tab.** `RfpFrame`'s `Tab` gains one additive branch: `submission` links to `/work/{tab.work_id}` only when the tab carries `work_id`; otherwise it stays plain text, as today. The current tab is drawn as now.
    - F-37 edits the same function for Requirements. Whichever merges second keeps both branches.
    - This feature does not read a `view` parameter (G-26-1).
18. **Columns.** On desktop, the main column holds "What goes to the client", "Checks" and, on the submitted boards, the banner, "What happened" and "Sent to". The side column holds the agent card ("Submission pack v1 · Tola · PMO agent · done"), "Ask Tola", Next, "Send for review", "Edit cover letter", the Decide panel and "Record the outcome".
    - The side column follows the F-17 frame (`ws-side`) and the work item aside (`RfpOutcomeLink`, `ReconcilePanel`).
    - Any placement difference is listed (`frame layout`).
19. **Phones.** The phone boards are sparse: they drop the agent card, Next, Checks (on review), the timeline headings and "Edit cover letter".
    - **Recommend (D-111, F-28 Conflicts 4):** the same sections, words and values as desktop, in one column. There is no frame on the phone (F-18).
    - The phone back link is "← RFP" to the first returned tab that carries `work_id` and is not current. With none (the review fixture), it is the existing "Queue" back to My work, where the board draws "← My work" (`phone wording`).
    - The Decide buttons sit in F-33's pinned bar. Return and Reject open the `Drawer` with the note.
    - Extras are listed (`phone composition`).
20. **Phone titles and bar tags.** The phone boards draw "Submission pack" with the bar tag "v1", "Review submission · v1" with "REVIEW", and "Submitted" with "DONE". The contract has one `title` and one status.
    - **Recommend:** `item.title` at both widths, with the status tag in the meta line only when `workspace.status` is returned. The bar tags are not drawn (`phone wording`, `frame item`), as F-28 Conflicts 5.
21. **Frame items.** The top bar, "Tunde Bello · PMO" and "Kemi Adebayo · PMO Lead" (from `/me`), the PMO Lead's extra nav items (Overview, Setup) and "+ Start" belong to the shell. All fixtures are opened with the mock persona `pm`, and no persona is added (`sample data`, `frame item`).

### Exceptions to sign

22. **Every board string is data:**
    - the pack parts and their detail;
    - the tags IN, DRAFT and TEST TEMPLATE;
    - the check sentences and "FROM THE RFP, P.2";
    - Tola's steps and source tags, and "Drafted 22 Nov 10:15";
    - the Next sentence and the consequence sentence;
    - the timeline rows and times;
    - "TL-SUB-0091";
    - "SUBMITTED 26 NOV" (`rfp.status.label`) and "DEADLINE 28 NOV · 6 DAYS" (`rfp.status.label`).
    The browser checks no 20 MB limit, works out no "submit by" date or days left, and counts no approvals. The `When` and `Tag` formats come from the library (`component`).
23. **The green banner.** The boards draw a green band headed "Submitted · delivery confirmed" or "Submitted · portal receipt confirmed". The frame draws `item.title` as the heading and a returned untitled `text` item carrying the sentence and a `tag` ("Receipt confirmed", tone `verified`), as F-28 Conflicts 7 and F-21's W-2211. The tag is an extra (`no field`). The verified tone comes only from the returned tag tone.
24. **"Open the full pack (PDF, 6.1 MB)"** is a `workspace.links[]` `document` entry, and the label is returned text. E-DOCUMENT has no size or content type (G-40-4), so the browser adds none.
25. **Tones.** The tones are IN `verified`, DRAFT `person`, TEST TEMPLATE `uncertain`, and DONE `agent` on the agent card. Each comes from the fixture's tag tone, never from the word. Colours the design system lacks are listed, not hard-coded.
26. **Visual waivers.** A board scoring under 90 is waived board by board in `fidelity-exceptions.json` citing D-83, after the design engineer signs. A board under the 70 floor needs its own one-board floor exception (as D-112).

## Boards

| Board | File (`design/canvas/project/`) | Page | Width | Mock |
|---|---|---|---|---|
| draft | `SCR-40-desktop-draft.dc.html` / `SCR-40-mobile-draft.dc.html` | `/work/W-3501` | 1440 / 390 | persona `pm` |
| review | `SCR-40-desktop-review.dc.html` / `SCR-40-mobile-review.dc.html` | `/work/W-3502` | 1440 / 390 | persona `pm` |
| submitted (email) | `SCR-40-desktop-submitted.dc.html` / `SCR-40-mobile-submitted.dc.html` | `/work/W-3503` | 1440 / 390 | persona `pm` |
| submitted-portal | `SCR-40-desktop-submitted-portal.dc.html` / `SCR-40-mobile-submitted-portal.dc.html` | `/work/W-3504` | 1440 / 390 | persona `pm` |

All 8 are live URLs, so no driver is needed. Each fidelity run starts with `POST /__mock/reset`, so W-3501 and W-3502 are not served from a step or decide override.

## Summary
- The RFP's Submission tab opens the submission work item inside the F-18 RFP frame. The PM sees what goes to the client (response, commercial proposal, cover letter, company forms, each with a returned tag), the returned checks and Tola's assembly list. They can edit the cover letter when the step sends its text, and send the pack for review.
- The document reviewer approves ("Approve and submit"), returns or rejects that exact pack version in place, through F-33's `InlineDecide` over F-16's `useDecision`. The controls come only from the task's `you_can_act` and the steps sent. The panel names `decision.version` and the returned recipient.
- After approval the page shows "Submitted", "What happened", "Sent to" with the returned receipt, and "Record the outcome" (F-18). All of it appears only after the re-read item returns it. An uncertain send shows only the reconcile panel, with no send again.
- Unknown reads "Unknown", never 0. Nothing is read from `/me`. No price or amount is drawn.
- New:
  - one additive tab branch in `RfpFrame`;
  - the frame in `LineHeader`;
  - the recipient line in `InlineDecide`;
  - 9 fixtures (W-3501 to W-3509) with sidecars, and a document fixture.
  Contract mock only; no mock server change.

## Context
- **RFP frame:** `frontend/src/features/rfp/RfpFrame.tsx`. `Tab` (`:19-45`) links `team_input`, and `outcome` when the item carries `rfp_outcome`; Submission is plain text (`:3-4`). It is used today only by `features/response/ResponseView.tsx:282` and `features/rfp/OutcomeView.tsx:89`, not by line workspaces. The F-18 phone back is "RFP" (`OutcomeView.tsx:109`, `ResponseView.tsx:205-211`). `RfpOutcomeLink` (`features/rfp/RfpOutcomeLink.tsx`) is drawn in the work item aside (`features/work-item/WorkItemOverview.tsx:733`) when `rfp_outcome` is returned. The outcome route is `/work/[id]/outcome` (`OutcomeView`).
- **Line page:** `features/work-item/WorkItemView.tsx`. `LineHeader` (`:145-216`) draws crumbs, title, `ProjectBar` and the status tag, falling back to `STATE_TAGS`. `usePhoneBack` is at `:243`. `WorkItemOverview.tsx:720-740` draws `ReconcilePanel`, task panels (skipped for tasks the workspace steps name), `RfpOutcomeLink`, then `Workspace`.
- **Workspace frame:** `features/workspace/`:
  - `Workspace.tsx`: `useWorkspaceStep` with `awaitingReconcile` from `item.reconcile` or `effect_uncertain` (`:114`); the all-locked rule (`:133-166`).
  - `Sections.tsx`: `checklist`, `timeline`, `text`, `recipients` with `RECEIPT_WORDS` from `labels.ts:45`.
  - `StepForm.tsx`: a long_text opens with the field's `value` (`:180-181`).
  - `Steps.tsx`, `Links.tsx`, and `proposals.ts` (`workspaceLinks`: `assistant`, `document`, `project_tab`).
- **Decide in place: F-33's `features/workspace/InlineDecide.tsx` and `proposals.ts` `stepVerdict`.** These are on branch `fe-fin-schedules-income-detail-review` (F-33, READY_FOR_ACCEPTANCE, not merged yet). This feature builds on a base that contains F-33. Decide flow: `features/decide/useDecision.ts`, `DecideStates.tsx` (`cannotActCopy`, `UncertainNotice`), `format.ts` (`NOTE_MAX`).
- **Reconcile:** `features/response/ReconcilePanel.tsx`, shown only with `reconcile` and `allowed_actions` including `reconcile`; one E-WORK-ACTION per press. The mock (`mock/response.mjs:186-202`) swaps in `fixtures/response/<work_id>.<outcome>.json`. A `delivered` answer needs evidence issued on the item's `case_id`.
- **Mock:**
  - `mock/server.mjs:148-183` `taskResponse`: claim and decide, the note rule, `expected_revision` (409) before `you_can_act` (403), then the swap to `<id>.<verdict>.json` and `work_state` = the sidecar's `state`. **A `<id>.next.json` makes the first decide answer 409.**
  - `mock/workspace.mjs:177-196` E-WORK-STEP: `<id>.steps.json` scripts per step key (`next: false` keeps the content and bumps the revision); `<id>.next.json` on a 200.
  - Document reads come from `mock/fixtures/E-DOCUMENT.json` and `mock/fixtures/documents/`.
- **Ids:** W-35xx and T-35xx are free (`grep -r "W-35\|T-35\d" frontend/mock` finds only the unrelated template id "T-35"). The RFP's case is the F-18 one, `C-2102` (`mock/fixtures/response/work/W-2102.json`), reused read-only. The team input tab links to the existing `W-2101`.
- **Tests that must stay green:**
  - unit: `tests/rfp.test.tsx`, `tests/rfp-mock.test.ts`, `tests/response.test.tsx`, `tests/response-mock.test.ts`, `tests/workspace.test.tsx`, `tests/workspace-step.test.tsx`, `tests/workspace-mock.test.ts`, `tests/decide.test.tsx`, `tests/decide-board.test.tsx`, `tests/mock-decide.test.ts`, `tests/mock-contract.test.ts`, and F-33's `tests/income-schedule*.test.*` and F-28's `tests/minutes-end*.test.*`;
  - e2e: `e2e/rfp.spec.ts`, `e2e/response.spec.ts`, `e2e/workspace.spec.ts`.

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (read; unchanged)
Read by `useWorkItem` and `useWorkspacePage`. The page draws `workspace` in the returned order for `line_key: "rfp_submission"` and branches on nothing else.
- **401:** the signed-out state with `next=/work/<id>`.
- **403 and 404 look the same:** `NoAccessState`, with no title, client, reference, address or pack part, and no further call.
- **5xx:** `WorkErrorCard` with Retry.
- **Loading:** `LoadingState`.
- After any write, the page re-reads (`usePageReload`). A 200 body never produces an optimistic state.
- INV-UNKNOWN, INV-RESTRICTED and INV-SAMPLE apply, as F-17. Times are WAT.

### Fixtures (`frontend/mock/fixtures/work/`; all `sample: true`, `reference: "TL-RFP-2026-014"`, `line: "Pre-sale / RFP"`, `case_id: "C-2102"`, `workspace.line_key: "rfp_submission"`, `screen: "SCR-40"`)

Common to the framed fixtures (W-3501, W-3503 to W-3509; W-3502 has none, Conflicts 1): `rfp` = reference, title "loan origination RFP", client "Tamarind Loans", `pm` Tunde Bello, and `tabs`:
- Requirements (count 64, plain);
- Team input (count 4, of 4, `work_id: "W-2101"`);
- Pricing (plain);
- Submission (`work_id` = the fixture's own id, `current: true`);
- Outcome.

The sections:
- **Pack** (`checklist`, key `pack`; titled "What goes to the client", or "Pack" on review), four items:
  - "Response document", detail "64 requirements, v3 approved 18 Nov", tag IN `verified`;
  - "Commercial proposal", detail "costing v2, all 3 approvals", tag IN `verified`;
  - "Cover letter", detail "drafted by Tola", tag DRAFT `person`;
  - "Company forms", detail "from the template", tag TEST TEMPLATE `uncertain`.
  No amount appears anywhere.
- **Checks** (`checklist`, key `checks`), five items with `status: done`:
  - "Every requirement answered or marked";
  - "Costing approved in order, same version as the proposal";
  - "Client's format: one PDF, under 20 MB";
  - "Send to: email · procurement@tamarindloans.example", `cite_label` "FROM THE RFP, P.2";
  - "Deadline 28 Nov · submit by 26 Nov leaves 2 days".

| Id | `state`; `rfp.status`; `workspace.status` | Content | Tasks and steps |
|---|---|---|---|
| W-3501 draft | `action_needed`; `deadline` "DEADLINE 28 NOV · 6 DAYS"; none | `title` "Submission pack · v1"; `workspace.version` {label "Submission pack v1", number 1, document_id "D-3501"}; Pack; Checks. `item.agent` Tola, `done`, 4 steps with sources ("RESPONSE V3 · APPROVED 18 NOV", "COSTING V2 · 3 APPROVALS", none, "TEST TEMPLATE · UNTIL PSL SUPPLIES THE REAL ONE"), finished 22 Nov 10:15 Lagos. `links`: `assistant` "Ask Tola". `next`: ["A document reviewer checks the pack. After that it's sent the way the RFP asks: here, by email to procurement@tamarindloans.example."] | no tasks. Steps: `send_for_review` (primary, `applies_to: workspace`, no fields); `edit_cover_letter` (secondary, field `cover_letter` `long_text`, required, `value` = the letter text). `W-3501.steps.json`: `edit_cover_letter` 200 `{outcome: "done", message: "Cover letter saved."}` with `next: false`; `send_for_review` 200 done. `W-3501.next.json` = in review as the PM sees it: status "IN REVIEW" `person`, task `T-3501` `you_can_act: false`, `cannot_act_reason: "prepared_by_you"`, the three verdict steps sent, no PM steps |
| W-3502 review (reviewer can act) | `action_needed`; **no `rfp`**; "IN REVIEW" `person` | crumbs Decision / TL-RFP-2026-014 / Submission; `title` "Review the submission pack · v1"; `subtitle` "Tamarind Loans · loan origination RFP · submit by 28 Nov"; Pack; `links`: `document` "Open the full pack (PDF, 6.1 MB)" (D-3501 v1); Checks | `T-3502` `kind: decide`, `required_role: "document reviewer"`, `you_can_act: true`, `revision: 1`. `decision`: `version` {label "Submission pack v1", number 1, document_id "D-3501"}, `recipient` "procurement@tamarindloans.example", `chain` one step (role "document reviewer", `current`, `is_you: true`, no person), `step_count: 1`, no amount. Steps, all `task_id: T-3502`: `approve_submission` "Approve and submit" (primary, `verdict: approve`, `sends: true`, consequence "Approving lets the factory submit this exact pack. If anything in it changes, it comes back to you."); `return_submission` "Return" (secondary, `verdict: return`); `reject_submission` "Reject" (danger, `verdict: reject`). Sidecars: `W-3502.approve.json` = W-3503's content under id W-3502; `W-3502.return.json` = "RETURNED TO PM" `person`, read-only, the reviewer's note as an untitled `text` item; `W-3502.reject.json` = "REJECTED" `stopped`, read-only. Each sidecar is one revision higher, with the task `you_can_act: false` and `cannot_act_reason: already_decided`. **No `W-3502.next.json`** |
| W-3503 submitted (email) | `verified`; `submitted` "SUBMITTED 26 NOV"; none | `title` "Submitted · delivery confirmed"; untitled `text` item "Emailed to procurement@tamarindloans.example, the address the RFP gives on p.2. Their mail server accepted it (ref TL-SUB-0091), so the response is verified as sent." with tag "Receipt confirmed" `verified`. `timeline` "What happened": "Approved by document reviewer · Kemi Adebayo" 26 Nov 14:58; "Emailed to procurement@tamarindloans.example" 15:42; "Delivery confirmed by their mail server · ref TL-SUB-0091" 15:43. `recipients` "Sent to": one item, `text` "procurement@tamarindloans.example", `channel` "Email", `receipt: received`, `at` 15:43. `next`: ["When the client announces the result, record it here: won, lost or still pending."]. `rfp_outcome`: `submission` {id "TL-SUB-0091", label "Submission pack v1", sent_at, delivery "Delivery confirmed by their mail server"}, `results` [won, lost, pending, unknown], `record_as` and `evidence_kind` as F-18's W-2104 | no tasks to act on; no steps |
| W-3504 submitted (portal) | as W-3503 | `title` "Submitted · portal receipt confirmed"; the sentence "The client's portal confirmed it received this exact pack (receipt TL-SUB-0091). The response is verified as submitted."; timeline "Sent to the client's procurement portal" and "Portal receipt TL-SUB-0091 matched"; "Sent to": "Client's procurement portal", channel "Portal", `received`; the same `next` and `rfp_outcome` | as W-3503 |
| W-3505 approve answers uncertain | before: as W-3502 (with `rfp`, `T-3505`). `W-3505.approve.json`: `effect_uncertain`; `deadline` (not submitted); "Effect uncertain" `uncertain` | after: `title` "Submission pack v1 · delivery not confirmed"; timeline: the approval row and "Emailed to procurement@tamarindloans.example" 15:42 only; "Sent to" `receipt: uncertain`, no `at`. `reconcile` {what "Submission pack v1 to procurement@tamarindloans.example", sent_at, checks {count 2, agent tola}, outcomes [delivered, not_delivered, unknown], evidence_kind, unknown_note}, with **no `resend` and no `resend_note`**; `allowed_actions: ["reconcile"]`; no `rfp_outcome` | after: task `already_decided`; no steps. Reconcile sidecars in `fixtures/response/`: `W-3505.delivered.json` (the W-3503 content, id W-3505), `W-3505.not_delivered.json` (`action_needed`, status "Not delivered" `stopped`, `next` ["Someone checks with Tamarind Loans before anything is sent again."], no steps), `W-3505.unknown.json` (still `effect_uncertain` with `reconcile`) |
| W-3506 the pack changed | as W-3502 (with `rfp`, `T-3506`, Submission pack v1) | `W-3506.next.json` = Submission pack **v2**, the cover letter's detail "edited by Tunde Bello", task `T-3506` at revision 2 and `decision.version` number 2 | as W-3502. The first decide answers 409 (mock rule); the page re-reads and shows v2 with nothing sent again |
| W-3507 no prefill | as W-3501 | as W-3501 | `edit_cover_letter` sent with no field `value` and `disabled_reason: "Not available yet"`; `send_for_review` live |
| W-3508 test template held | as W-3502 (with `rfp`, `T-3508`) | as W-3502 | `approve_submission` sent with `disabled_reason: "A part still uses a test template."`; Return and Reject live |
| W-3509 not your role / unknown | as W-3502 (with `rfp`, `T-3509`) | as W-3502, but the "Deadline" check `status: unknown` and the pack's "Company forms" detail absent | `T-3509` `you_can_act: false`, `cannot_act_reason: not_your_role`; the three verdict steps sent |

Also new: `mock/fixtures/documents/D-3501.1.json`, the E-DOCUMENT read: title "Submission pack · Tamarind Loans", version 1, status as returned, `test_template: true`. It follows the shape of `documents/D-2901.1.json`.

Once the overlay is stripped, every fixture and sidecar validates against the generated E-WORK-ITEM 200 schema.

### Overlay proposals (mock only; each recorded in `build.md` for the backend developer)
- `workspace.steps[].verdict` (F-33, G-C-1), reused unchanged.
- `workspace.links[]` `document` and `assistant` (X-LINKS), reused.
- Omitting `rfp` on the reviewer's read (Conflicts 1).
- `steps[].fields[].value` as the initial value of a long_text field (G-26-3), already read by `StepForm`.
- `rfp.tabs[].work_id` on the Submission tab (G-26-1).
- `rfp.submission_plan` (G-23-4, G-40-2): recorded, not read. The address appears only in returned text.
- G-40-1: the approved version's `sha256` and that approve enqueues only that version.
- G-40-3: what `received` means.
- G-40-4: size and content type.
- G-40-9: the submission record is the one E-RFP-OUTCOME reads.
- PMO-3-1 (F-33): E-TASK-DECIDE has no idempotency key.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (PM: `edit_cover_letter`, `send_for_review`)
- **Request:** `{expected_revision: workspace.revision, step, inputs, idempotency_key: <UUID, new per press, reused on a manual retry of the same press>}`, header `X-CSRFToken`, sent through the existing `useWorkspaceStep`. For `edit_cover_letter`, `inputs` is `{cover_letter: <text>}`. For `send_for_review`, `inputs` is `{}`.
- **200 `done`:** re-read. After Send for review, the re-read shows the review as the PM sees it (`W-3501.next.json`). After an edit, the item shows its re-read revision. The notice is the response `message` or the F-17 default.
- **Errors:**
  - 409: re-read and show the stale sentence; typed text is kept.
  - 422: shown under the named field.
  - 5xx, network or timeout: "Not recorded" after a re-read; Try again uses the same key.
  - `outcome: uncertain`: the existing reconcile panel; never "sent for review".
  - 401: signed-out state. 403: re-read, then read-only.
- **Permission and tenant:** the backend decides per record and step. The page draws only the steps returned, and a step with `disabled_reason` is drawn disabled with its reason.

### E-TASK-CLAIM and E-TASK-DECIDE (reviewer), through F-33's `InlineDecide` over `useDecision(work_id, task_id)` only
- **Buttons:** one per step with `task_id` and a valid `verdict`, under "Decide · document reviewer" (`required_role` as returned), labelled with the step's `label`. They exist only when that task's `you_can_act` is true. Otherwise `cannotActCopy(cannot_act_reason, task)` is shown, with no button and no claim.
- **What the panel shows:** the version label (`decision.version.label`), the step's `consequence`, and, when returned, "Goes to {decision.recipient}" (Conflicts 2).
- **Claim:** sent once per task revision, only when `you_can_act` is true.
- **Decide request:** `{verdict, note?, expected_revision: <task revision>}` with CSRF and no extra keys. The note is required for `return` and `reject`, at most `NOTE_MAX`, and checked before any request. Approve sends no note.
- **200:** re-read. "Submitted", "Returned" or "Rejected" appear only from the re-read item. If the decide answers `work_state: effect_uncertain`, or the re-read item is `effect_uncertain` or has `reconcile`, it is never shown as approved or submitted.
- **Errors:**
  - 409 (the pack changed, W-3506): re-read, show the new version, keep the note; nothing is sent again until a new deliberate press on the new task revision.
  - 403: the read-only view.
  - 422: the message under the note.
  - 5xx, network or timeout: re-read first, then `UncertainNotice`; no automatic second decide.
- **Rules:** no role, person or `prepared_by` rule in the page, and `/me` is not read.

### E-WORK-ACTION `POST /api/v1/work/{work_id}/actions` (reconcile)
- Through the existing `ReconcilePanel`, unchanged: one POST per press with the outcome (and the evidence for `delivered`), then a re-read.
- While `reconcile` is present, every step and decide control is `aria-disabled`. There is no POST to `/steps`, `/claim` or `/decision`, no "Send again" and no new key, and the same holds after a reload.
- A 5xx on the reconcile itself shows the panel's existing uncertain state, with no automatic retry.

### E-DOCUMENT `GET /api/v1/documents/{document_id}/versions/{version}`
"Open the full pack (PDF, 6.1 MB)" uses the existing `WorkspaceLinks` document panel unchanged:
- one GET `/api/v1/documents/D-3501/versions/1`;
- the title, the version, and a "Test template" tag when `test_template: true`;
- 403 and 404: "You can't open this document.", with no title;
- 5xx or network: a manual retry of the read only.

### Screen states
- **Loading, error, signed out, no access:** as above.
- **Success:** the four board states (W-3501 to W-3504), plus in review for the PM (W-3501.next), returned and rejected (sidecars), uncertain (W-3505.approve), not delivered (W-3505.not_delivered), the pack changed (W-3506), no prefill (W-3507), test template held (W-3508), and not your role with unknowns (W-3509).
- **Empty:** a section with `items: []` reads "Nothing here yet."
- **Unknown:** a check with `status: unknown` reads "Unknown", and a missing detail draws nothing (never "0" or "-"). A received or uncertain recipient without `at` reads "Time unknown".
- **Restricted:** the label only.
- **Motion:** `prefers-reduced-motion` respected.

## Lanes
- **Frontend lane.** The builder is Opus for the first build (high risk, client release, D-64), then Sonnet for fix rounds. It owns:
  - `features/rfp/RfpFrame.tsx`: the additive `submission` branch in `Tab`.
  - `features/work-item/WorkItemView.tsx`: `LineHeader` draws `RfpFrame` on desktop when `item.rfp` is returned (with no state-tag fallback while framed); `usePhoneBack` "RFP" from the tabs (Conflicts 19).
  - `features/workspace/InlineDecide.tsx`: the additive recipient line.
  - Additive rules in `work-item.css`, `rfp.css` and `workspace.css`, tokens only.
  - Fixtures W-3501 to W-3509 and their sidecars as listed, `fixtures/response/W-3505.{delivered,not_delivered,unknown}.json`, and `fixtures/documents/D-3501.1.json`.
  - Tests: `tests/rfp-submission.test.tsx`, `tests/rfp-submission-mock.test.ts`, `tests/mock-contract.test.ts` (new fixtures only, with the overlay stripped), `e2e/rfp-submission.spec.ts`.
  - Factory files: `delivery/features/F-38/fidelity-exceptions.json` and `round-<N>/**`.
  - Each frame change is listed in `build.md` with its reason. No submission-specific component, route or copy goes in `src/`.
- **Shared, read only:**
  - `features/decide/**`, `features/response/**` (import `ReconcilePanel`), `features/documents/**`, the rest of `features/rfp/**`, `features/workspace/**` other than the line above, `src/components/**`, `src/shell/**`, `src/api/**` (including `schema.d.ts`), `src/styles/**`;
  - `mock/server.mjs`, `mock/workspace.mjs`, `mock/response.mjs`, every existing fixture;
  - `package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`;
  - `architecture/**`, `design/**`, `apps/**`;
  - the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Record in `build.md`: G-40-1 to G-40-9, G-23-4, G-26-1, G-26-3, PMO-3-1, Conflicts 1 (the `rfp` on the reviewer's read), D-RETURN, and questions 11 to 15.
- **Integration owner:** the coordinator.
  - **Base must contain F-33** (`InlineDecide`, `stepVerdict`); the build starts after F-33 merges into dlv-00.
  - F-37 also edits `RfpFrame.Tab` and likely `LineHeader` for the Requirements workspace. Whichever merges second keeps both tab branches and one frame-in-header path, then reruns `delivery/checks.sh` and the e2e below.
- **Ports:** app 4951, mock 4952 (not in any spec, `playwright.config.ts` or `delivery/config.json`; the builder greps first).
  - Command: `cd frontend && E2E_PORT=4951 MOCK_PORT=4952 npx playwright test e2e/rfp-submission.spec.ts e2e/rfp.spec.ts e2e/response.spec.ts e2e/workspace.spec.ts`, with `timezoneId: 'Africa/Lagos'`.
  - Fidelity runs on a production build, once per round over all 8 boards (D-64).
  - Before starting, `df -h /System/Volumes/Data` (stop under 3 GB). Delete `frontend/test-results` after.
  - e2e is not in `checks.sh`, so paste its output in `build.md`.
- **Review routing (high risk):** technical (Sonnet), UI (Opus first review, fidelity gate on 8 boards), UX (Sonnet), QA (Opus), security (Opus: a release to a client, the resend lock, CSRF and claim), PMO. Product acceptance is required. It merges only on the design engineer's "merge".
- **Size:** about 1,200 to 1,600 lines, two thirds fixtures and tests. One PR.

## Acceptance criteria
Fidelity command per board (swap `--board`, `--page`, `--width` and `--out`; cookie `psl_mock_persona=pm`; `POST http://localhost:4952/__mock/reset` first):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-40-desktop-draft.dc.html \
  --page "http://localhost:4951/work/W-3501" --width 1440 \
  --cookies psl_mock_persona=pm \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-38/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-38/round-<N>/fidelity/SCR-40-desktop-draft-1440
```

### Fidelity (8 boards, D-64, D-83)
1. **Coverage and visual.** Each of the 8 boards (table under Boards) is checked at its width on a production build.
   - `scores.coverageWithExceptions` is 100.
   - `scores.visual` is at least 90, or between 70 and 90 with a D-83 visual waiver signed for that board in `fidelity-exceptions.json`. Below 70 needs a signed one-board floor exception.
   - The UI reviewer's side-by-side reading finds no fixable gap.
   - — verify: the command per board exits 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass and waiver.
2. **Exceptions limited.**
   - Each entry has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number.
   - None covers a value the data supplies (a name, an address, a date, a tag, a count, a receipt, a sentence).
   - One fidelity run per round (D-64).
   - — verify: `fidelity-exceptions.json` content; `build.md`.

### Page
3. **Draft from data.** `/work/W-3501` at 1440 shows:
   - the RFP frame with Submission current and not a link, Team input linking to `/work/W-2101`, and Requirements and Pricing as plain text;
   - "Submission pack · v1", the four pack parts with their returned tags, and the five checks with "FROM THE RFP, P.2";
   - Tola's card ("done", the 4 steps and sources), "Ask Tola" to `/assistant`, the Next sentence, "Send for review" and "Edit cover letter".
   No board string is in `src` (`grep -rnE "TEST TEMPLATE|procurement@|submit by|TL-SUB|all [34] approvals|Approve and submit" frontend/src` returns nothing).
   — verify: `cd frontend && npx vitest run tests/rfp-submission.test.tsx`; the page at 1440 and 390.
4. **Submission tab link is additive.**
   - A frame whose Submission tab carries `work_id` links to `/work/{work_id}`; without `work_id` it stays plain text, as today.
   - The Team input and Outcome behaviour is unchanged, and F-18's pages (W-2101 to W-2114) render exactly as before.
   - A line workspace item without `rfp` (every F-17 to F-33 fixture) draws no frame and the same header as before.
   - — verify: component tests on `RfpFrame` and `LineHeader`; `tests/rfp.test.tsx` and `e2e/rfp.spec.ts` unchanged and green.
5. **The page computes nothing.**
   - Changing a fixture's check text ("under 20 MB", "submit by 26 Nov leaves 2 days"), `rfp.status.label` ("6 DAYS") or the approvals text changes only that text. The page never shows a computed date, day count, size or approvals count.
   - The diff adds no date arithmetic (`differenceIn`, `getTime() -`, `Date.now() -`) and no size check under `frontend/src/features`.
   - — verify: component tests on modified copies; `git diff -U0 frontend/src | grep -nE "getTime\(\) *-|Date\.now\(\) *-|20 ?MB|MB'"` returns nothing.
6. **Unknown is never 0.** On W-3509, the deadline check reads "Unknown" and the forms part with no detail shows no "0", blank cell, "-" or "—" in its place. No page in this feature contains "₦" or an amount.
   — verify: component test on W-3509; `document.body.textContent` checked for `₦` and `/\b0\.00\b/` (absent).
7. **Agent work is not a decision or an outcome.** Tola's card and its steps render in the agent style. No agent text appears as a check result, a decision or a "Submitted" state. The page offers no control that lets Tola submit.
   — verify: component test on W-3501.

### Controls and writes
8. **Controls only from `you_can_act` and the steps sent.**
   - W-3502 shows "Approve and submit", "Return" and "Reject" under "Decide · document reviewer", with "Submission pack v1", the consequence sentence and "Goes to procurement@tamarindloans.example".
   - On W-3501.next (the PM in review), W-3509 (not your role) and every submitted fixture, there is no decide button and no claim is sent; W-3501.next shows the `prepared_by_you` copy and W-3509 the `not_your_role` copy.
   - W-3508 draws "Approve and submit" disabled with "A part still uses a test template." and Return and Reject live.
   - W-3507 draws "Edit cover letter" disabled with "Not available yet" and opens no editor.
   - W-3503 and W-3504 draw no step at all.
   - Personas `pm`, `ceo` and `finance_lead` see the same controls for the same fixture, and the diff adds no `/me` or `useMe` read under `features/rfp`, `features/work-item` or `features/workspace`.
   - — verify: component tests across three personas with a recording `fetch`; `git diff -U0 frontend/src | grep -nE "useMe|/api/v1/me"` returns nothing.
9. **Send for review.** On W-3501, one press of "Send for review" sends exactly one POST `/api/v1/work/W-3501/steps` with CSRF, `expected_revision` = `workspace.revision`, `step: "send_for_review"`, `inputs: {}` and a UUID `idempotency_key`; a double press still sends one.
   - The page says nothing like "sent for review" until the re-read shows the in-review state.
   - A 500 shows "Not recorded" after a re-read, and Try again reuses the same key.
   - A 409 re-reads and shows the stale sentence.
   - — verify: component tests; e2e request log.
10. **Edit cover letter.** On W-3501, "Edit cover letter" opens the step form (the `Drawer` at 390) with the current letter text already in the field.
    - Saving sends one POST with `step: "edit_cover_letter"`, `inputs.cover_letter` = the edited text, CSRF, `expected_revision` and a UUID key.
    - A blank letter is refused before sending, with the message under the field and focus there.
    - A 422 lands under the field and keeps the text.
    - — verify: component tests; e2e at 390 for the Drawer.
11. **Approve sends one decision on the exact version.** On W-3502:
    - one claim to `/api/v1/tasks/T-3502/claim`;
    - pressing "Approve and submit" sends exactly one POST `/api/v1/tasks/T-3502/decision` with CSRF and `{verdict: "approve", expected_revision: 1}`. It validates against the generated request schema, with no note and no extra keys. A double press sends one.
    - "Submitted · delivery confirmed", "What happened", "Sent to" and "Record the outcome" appear only after the re-read serves `W-3502.approve.json`. A test double answering 200 while the re-read still serves the review shows none of them.
    - — verify: component tests with a recording `fetch`; e2e request log.
12. **Return and Reject need a note.**
    - Return or Reject with an empty or blank note sends nothing; the message shows under "Note (needed to return or reject)", is announced, and focus moves to the note. A note over 2000 characters is refused before sending.
    - With a note, one POST with `verdict: "return"` (or `"reject"`) and the trimmed note.
    - The re-read shows "RETURNED TO PM" (or "REJECTED") and no "Submitted".
    - — verify: component tests; the e2e log shows no decision POST without a note.
13. **The pack changed (409).** On W-3506, the first "Approve and submit" answers 409. The page re-reads, shows "Submission pack v2" with its new detail, keeps no stale "approved" text, and sends no second decision. Only a new press on the v2 task sends one, with `expected_revision: 2`.
    — verify: component test; `tests/rfp-submission-mock.test.ts`.
14. **Uncertain paths, each with its own fixture, never a success before the re-read.**
    - (a) **Decide answers `effect_uncertain`:** approving on W-3505 re-reads `W-3505.approve.json`. The page shows "Effect uncertain", "Sent to" with "Uncertain", the `ReconcilePanel` and `UncertainNotice`. It never shows "Submitted", "Delivered", "Received" or "Record the outcome".
    - (b) **Decide network failure, timeout or 500** on W-3502: the item is re-read first, then `UncertainNotice`, with no "approved" or "submitted" from the click. One POST after 60 s with fake timers.
    - (c) **Step `outcome: uncertain`** (a scripted `W-3501.steps.json` variant in a test copy): the reconcile path, never "sent for review".
    - (d) **Reconcile answers:**
      - `delivered` (with evidence) re-reads to the submitted content;
      - `not_delivered` re-reads to "Not delivered" with the backend's `next` and no button;
      - `unknown` keeps the lock;
      - a 5xx on the reconcile itself shows the panel's uncertain state, with no retry.
    - (e) **The lock:** while `reconcile` is present, every step and decide control is `aria-disabled`, and one reconcile press sends one POST to `/actions` and none to `/steps`, `/claim` or `/decision`; the same after a reload. The page contains no "Send again", "Resend" or "Submit again" (`grep -rniE "send again|resend|submit again" frontend/src/features` finds nothing new).
    - — verify: component tests per path with a recording `fetch`; e2e with a routed abort at 1440 and 390.
15. **Receipts only as returned.**
    - On W-3503 and W-3504, "Sent to" reads "Received" with its time only because `receipt: received`.
    - For a test copy with each of `not_yet`, `uncertain`, `failed`, `unknown` and an absent `receipt`, the row reads Not yet, Uncertain, Failed or Unknown, never Received, Sent or Delivered.
    - The banner's verified styling comes only from the returned tag tone.
    - No "Delivered", "delivery confirmed", "verified as sent" or "Verified" string is composed in `src/` (fixtures only).
    - — verify: component tests over all five receipt values; `grep -rnE "Delivered|delivery confirmed|verified as sent" frontend/src` returns nothing.
16. **Record the outcome (F-18).** "Record the outcome" appears only on items that return `rfp_outcome` (W-3503, W-3504, W-3505.delivered). It links to `/work/W-3503/outcome`, where the F-18 outcome form opens showing "Submission pack v1" and the returned delivery. It is absent on W-3501, W-3502, W-3505.approve and W-3505.not_delivered.
    — verify: component test; e2e click-through.
17. **Open the full pack.** On W-3502, "Open the full pack (PDF, 6.1 MB)" sends exactly one GET `/api/v1/documents/D-3501/versions/1` and shows the title, the version and "Test template". A 404 shows "You can't open this document." with no title.
    — verify: component test with a recording `fetch`.
18. **Access: 401, 403 and 404.**
    - A 401 on read or write shows the signed-out state with `next=/work/<id>`.
    - With `X-Mock-Scenario` 403 or 404, `/work/W-3502` and `/work/W-3503` show the same `NoAccessState`, and `document.body.textContent` contains no "Tamarind", "TL-RFP-2026-014", "procurement@" or "Submission pack".
    - A 403 on decide shows the read-only view and no "approved".
    - Persona `none` gets the not-open view with no further call.
    - — verify: component tests with a recording `fetch`.
19. **Nothing on load or on a timer.** Loading any W-35xx page sends only GETs. Advancing fake timers 60 s sends no POST. Every e2e request goes to port 4952.
    — verify: recording `fetch`; the e2e request log.

### Quality
20. **Phone.** At 390, each state is one column with the same sections, words and values as desktop.
    - There is no RFP frame. The back link is "← RFP" to `/work/W-2101` on the framed fixtures and "Queue" on W-3502.
    - The Decide bar is pinned with the three labels; Return and Reject open the full-height `Drawer` with the note; Escape and Cancel close it and return focus.
    - No sideways scroll.
    - Every button, link, tab and segment is at least 44 by 44 px (D-92c; links inside sentences are exempt, D-95).
    - — verify: e2e at 390 measuring bounding boxes.
21. **Accessibility.** No axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 and 390 on:
    - W-3501 to W-3509;
    - the open Drawer, the note error, the uncertain notice with the reconcile panel, and the not-open view.
    Also:
    - the RFP nav keeps `aria-current="page"` on Submission;
    - the receipt and tags are text, not colour only;
    - the reconcile result is in a live region;
    - focus is visible;
    - nothing animates under `reducedMotion: 'reduce'`.
    — verify: `e2e/rfp-submission.spec.ts`.
22. **Tokens and components only.** The diff adds no `#hex`, `rgb(`, `hsl(` or raw px outside tokens in any CSS file, and no local copy of a component `@/components` exports (`Button`, `Drawer`, `TextArea`, `Callout`, `Panel`, `Tag`, `Segmented`). New UI imports from `@/components`.
    — verify: `git diff -U0 -- '*.css' | grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\("` returns nothing; diff read.
23. **Mock matches the contract.** `tests/rfp-submission-mock.test.ts` checks:
    - every new fixture and sidecar validates against the generated E-WORK-ITEM schema with `steps[].verdict` stripped;
    - claim then approve on W-3502 serves `W-3502.approve.json`;
    - approve on W-3505 answers `work_state: effect_uncertain`;
    - the first decide on W-3506 is 409;
    - Return without a note is 422; W-3509's decide is 403;
    - the W-3501 steps follow their scripts, and a repeated step key returns the stored reply with no second effect;
    - each W-3505 reconcile outcome serves its sidecar;
    - reset clears.
    — verify: `cd frontend && npx vitest run tests/rfp-submission.test.tsx tests/rfp-submission-mock.test.ts tests/mock-contract.test.ts`.
24. **Contract not extended.**
    - `git diff --stat` shows no change in `frontend/src/api/**`, `frontend/src/features/decide/**`, `frontend/src/features/response/**`, `frontend/src/shell/**`, `frontend/mock/*.mjs`, any existing fixture, `apps/**`, `architecture/**`, `design/**` or the protected paths.
    - The only overlay reads are those under "Overlay proposals", each listed in `build.md`.
    - Every fixture validates with no stripping beyond `steps[].verdict`.
    - — verify: `git diff --stat`; `tests/mock-contract.test.ts`; `build.md`.
25. **Existing tests green.** `delivery/checks.sh` passes, and every test listed under Context passes with no assertion removed or loosened. This includes F-18's `tests/rfp*.test.*` and `e2e/rfp.spec.ts`, F-33's inline decide tests (unchanged with no `decision.recipient`) and F-28's receipt tests. The F-18, F-28 and F-33 fidelity scores do not drop.
    — verify: `delivery/checks.sh`; the e2e command under Lanes pasted in `build.md`; `git diff` on tests.
26. **No overclaim, and the `build.md` evidence.**
    - `build.md` and the PR state the "What is sent" section: contract mock only; nothing submitted, emailed or delivered; the company forms are a test template; D-LINE-WORKSPACE and D-RFP-OUTCOME limits.
    - `build.md` also lists the commands and results, the 8 scores and waivers, every exception with its Conflicts number, every frame change with its reason, every proposal and backend item, and questions 11 to 15.
    - — verify: file content.

## Out of scope
- **Not built:**
  - a real submission, email or portal send; a "Send again", resend, "mark delivered" or "submit by hand" control;
  - choosing or editing where the pack goes (`rfp.submission_plan` is read by nobody here);
  - the by-hand and not-stated submission boards (not drawn), and `record_manual_submission`.
- **Never computed or drawn:**
  - any price, amount, rate or costing figure;
  - the 20 MB check, the "submit by" date, days left or the approvals count, worked out in the browser;
  - SCR-26 and SCR-27 (F-37, FE-COSTING) and the Requirements and Pricing tab links.
- **Not added to the page:**
  - the outcome form itself (F-18, reused as is);
  - a separate decision page for the submission, or changes to the F-16 decision page, `useDecision`, `ReconcilePanel` or the mocks' rules;
  - separation-of-duties or role logic, or reading `/me` to show a control;
  - an undrawn uncertain board (Conflicts 5 B), or a phone-only title or status field;
  - an agent submitting, sending or deciding.
- **Not this feature's work:** backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, and new npm dependencies.

## Assumptions
- **Option A for Conflicts 1 to 10 unless answered.** Reason: each keeps everything the data holds visible on the one frame. Every difference is a signed exception, not a hidden change.
- **Line key `rfp_submission`, step keys `send_for_review` and `edit_cover_letter`** (as `gaps-b-rfp-planning.md:114`), and verdict step keys `approve_submission`, `return_submission` and `reject_submission`. Reason: v7 names no submission line key, and the frame branches on none.
- **The submission is its own work item, reached through `rfp.tabs[].work_id`.** Reason: readiness binds the link to `tab.work_id`, and G-26-1 leaves one workspace per work item.
- **One document id outside the W/T ranges: `D-3501`, in the same 35xx block.** Reason: readiness requires E-DOCUMENT for "Open the full pack", and no existing document is an RFP pack. If the coordinator refuses it, the link and criterion 17 are dropped and the board element is listed as an exception.
- **The RFP's case is the F-18 `C-2102`, and Team input links to `W-2101`, both read-only.** Reason: they are the same sample RFP (TL-RFP-2026-014), so the evidence upload for a `delivered` reconcile has a case.
- **D-RETURN working assumption.** A return shows the reviewer's note on the item, and what the PM can do next is whatever the backend sends. No fixture invents a PM rework step beyond the read-only returned view. Reason: D-RETURN r2 says build against it, but it names no step.
- **The uncertain item's `rfp.status` stays the deadline, not "SUBMITTED".** Reason: a submission is not proven until reconciled (INV-RESEND, G-40-3).
- **`decision.chain` has one step, "document reviewer", with no person.** Reason: the board draws one reviewer, and the reviewer is a Setup rule (`documents.client_reviewer`); "Kemi Adebayo" appears only in returned timeline text.
- **The mock persona is `pm` for every board.** Reason: the frame derives nothing from role, and the mock has no PMO Lead persona (as F-28).
- **Ports 4951 and 4952.** Reason: unused in any spec or config.
- **"Edit cover letter" uses the existing long_text `value` prefill, with a returned `disabled_reason` when it is missing, rather than a frontend rule keyed on the step name.** Reason: this is the smallest change that meets readiness rule 6 without a submission-specific branch in the shared frame.
