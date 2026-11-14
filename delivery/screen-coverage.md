# Screen coverage: approved screens and the frontend tasks that build them

Audit date: 14 Nov 2026. This is a read-only audit; nothing else was changed.

Sources:
- `design/screens.md` (59 screens). All 59 are in the client approval in `design/review.json` (canvas 1794581312-b166, 13 Nov 2026).
- Board files in `design/canvas/project/` (442 files) and `design/canvas/finance/project/` (143 files). Every file is listed in its canvas.json, and every canvas.json entry has a file.
- Frontend tasks (`owner_role` "frontend developer") and endpoints in `architecture/packages/v6/model.json` and `openapi.json`.
- `delivery/features/F-*/feature.json`, plus `readiness.md` and `spec.md` for F-01 to F-08.
- The readiness drafts for F-10, F-11 and F-12. These appeared, uncommitted, while this audit was running.
  - F-10 is narrowed to SCR-36 and proposes slices F-10B to F-10J.
  - F-11 is narrowed to Setup rules and proposes F-11B to F-11F.
  - F-12 is NOT-READY and proposes F-12A, F-12A2 and F-12B.
  - F-09 has no readiness yet.

Status key:
- **built**: the feature is DONE and its code is on `dlv-00-delivery-setup`.
- **building**: the feature is IMPLEMENTING.
- **planned (F-xx)**: a v6 task and a feature record exist; readiness is not done yet.
- **planned (task only)**: a v6 frontend task exists, but no feature record has been made for it yet. "Proposed slice" means a readiness draft has proposed a sub-feature that does not exist yet.
- **UNASSIGNED**: no v6 frontend task and no feature covers the screen.
- **reference-only**: a concept, flow, line map, storyboard or design-system board. It is not a platform screen.

"Partial" means the screen is assigned but some approved states are left out by every task. Those states are named in the Notes column.

## Counts

| | Screens | Board files |
|---|---|---|
| Covered (built 2, building 7, planned 23) | 32 | 313 |
| UNASSIGNED | 27 | 210 |
| Reference-only boards (not screens) | — | 62 (53 main, 9 Finance) |
| **Total** | **59** | **585** |

Assigned screens with approved states that no task covers: SCR-03 (three decision variants, task parked), SCR-04 (seven Finance drawers, task only), SCR-15 (account menu and sign-out), SCR-21 (invite and deactivate), SCR-34 (versioned upload), SCR-08 (the review page is not named in any task). The Finance and Setup screens marked "proposed slice" are inside a v6 task's requirement, but they have no endpoints and no feature yet.

## Screen table

Board column: canvas folder, file count, then the state suffixes. Each state has a `-desktop` and a `-mobile` file, for example `SCR-25-desktop-review.dc.html` and `SCR-25-mobile-review.dc.html`. "default" means `SCR-nn-desktop.dc.html` and `SCR-nn-mobile.dc.html`. main = `design/canvas/project/`; fin = `design/canvas/finance/project/`.

| Screen | Title | Boards | Task / feature | Status | Notes |
|---|---|---|---|---|---|
| SCR-01 | My work (work queue) | main 9 (+2 concept): default, my-work, empty, filter, lead | FE-MYWORK / F-02 | building | First version merged. Reopened for a fidelity round on `fe-mywork-fidelity`. Loading and error states use the STATES boards. Elements missing from the contract are listed as out of scope in the F-02 spec. |
| SCR-02 | Work item | main 26: default, ready, processing, waiting, setup-needed, awaiting-reconciliation, cancelled, owner-needed, effect-uncertain, verified, permission, issue, history; fin 6: evidence-asked, evidence-supplied, returned | FE-WORKITEM / F-03; actions in FE-M2B-RESPONSE / F-09 | built (display and history); action states planned (F-09) | F-03 shows every state as read-only. The reconcile, resume and supply-evidence actions belong to F-09 (E-WORK-ACTION, E-RESPONSE, E-EVIDENCE-UPLOAD). |
| SCR-03 | Decision | main 14: default, done, not-yours, stale, payment-exception, ceo-costing, cto-emergency; fin 2: own | FE-DECIDE / F-04; FE-DECIDE-VARIANTS | built (standard); variants planned (task only, parked) | **Partial.** payment-exception, ceo-costing and cto-emergency wait on D-DECISION-VARIANTS, which is open: PSL has not set the rule. `revoke` (withdraw approval) is also not built. |
| SCR-04 | Start work | main 34 (+2 concept): default, lines, validation, weekly, minutes, issue, change, incident, escalation, leadership, accounts, schedules, ppe, forecast, bu, ledger, payroll | FE-M2A / F-05; FE-M2A-PROOF | core building; Finance drawers and proof planned (task only) | **Partial.** F-05 builds the core drawers without proof fields. accounts, schedules, ppe, forecast, bu, ledger and payroll belong to FE-M2A-PROOF, which has no feature yet. |
| SCR-05 | Assistant | main 10: default, thread, draft-started, cant, working | FE-M4 / F-12 | planned (F-12, NOT-READY) | Proposed slice F-12B, blocked on D-CONVERSATION-MODEL. Open question: the speech input. |
| SCR-06 | Overview: factory floor | main 2 (+1 concept): default (reduced-motion uses the flat view) | FE-M3-OVERVIEW / F-08 | building | The embedded exceptions list is follow-up (a) after F-06. |
| SCR-07 | Project journey | main 2: default | FE-M3-PROJECTS / F-07 | building | "empty" uses the STATES pattern. The board elements with no contract field are listed in the F-07 spec. |
| SCR-08 | Document review | main 4: default, returned | FE-M3-PROJECT-TABS (implied) | planned (task only) | **Check.** E-DOCUMENT exists under R-PROJECT. F-03, F-04 and F-07 all exclude SCR-08, and no task names the review page itself. Name it in FE-M3-PROJECT-TABS readiness. |
| SCR-09 | Import and reconcile | fin 4: default, error | FE-M3-FINANCE | planned (task only) | F-10 readiness moves this to proposed slice F-10B. E-IMPORT. |
| SCR-10 | All exceptions | main 2: default | FE-M2B / F-06 | building | Read-only. Fixing an exception from this list belongs to F-09. |
| SCR-11 | Registers (issues, changes, RFPs) | main 2: default | FE-M3-PROJECT-TABS | planned (task only) | E-PROJECT-TAB `registers`. Row shapes come from D-PROJECT-TAB-ROWS. |
| SCR-12 | Report with drill-down | main 2: default | FE-M3-REPORT | planned (task only) | E-REPORT. F-08 excludes it. Where a person opens a report from still needs a product answer. |
| SCR-13 | Setup: roles, rules, delegation | main 16: default, validation, permission, fields, rules, delegation, delivery-rules, finance-rules | FE-M3-SETUP / F-11 | planned (F-11, readiness READY in draft for the rules tabs) | F-11 takes the rule tabs (E-SETUP-RULES, E-SETUP-RULE-SAVE). Proposed slices: delegation is F-11B (E-DELEGATION is PUT only, with no list); roles and validation are F-11C; fields (payroll field visibility) is F-11E, which has no endpoint. |
| SCR-14 | Verified outputs | main 2: default | FE-MYWORK / F-02 | building | Since 13 Nov this is the My work "Done" queue with a Verified filter. The board's facts, proof and verified-time columns go beyond E-WORK-LIST. Settle this in F-02 product acceptance. |
| SCR-15 | Alerts and notification settings | main 10: default, settings, email, whatsapp, account | FE-M4 / F-12 | planned (F-12, NOT-READY) | **Partial.** Proposed slices F-12A (in-app alerts) and F-12A2 (bell and account menu), blocked on D-NOTIFY-MODEL r3. The email and WhatsApp boards go to backend T-ALERTS. Sign-out depends on D-AUTH. |
| SCR-16 | Record a response | main 26: default, validation, success, team-input, sow-signed, rfp-outcome(-lost/-pending/-unknown), rfp-won/-lost/-pending/-unknown | FE-M2B-RESPONSE / F-09 | planned (F-09) | E-RESPONSE, E-EVIDENCE-UPLOAD, E-RFP-OUTCOME, E-TASK-CLAIM. |
| SCR-17 | Sign in | main 8: default, error, reset, setup | — | **UNASSIGNED** | F-01 excludes it. D-AUTH (proposed) relies on the existing Django sign-in. |
| SCR-18 | Restricted payroll matching | fin 4: default, permission | FE-M3-FINANCE | planned (task only) | Proposed slice F-10B. E-PAYROLL-MATCH. |
| SCR-19 | Mark a milestone complete | main 2: default | — | **UNASSIGNED** | Opened from the Milestones tab. |
| SCR-20 | Payments and follow-up | fin 4: default, record | — | **UNASSIGNED** | |
| SCR-21 | Staff accounts | main 6: default, invite, deactivate | FE-M3-SETUP | planned (task only) | Proposed slice F-11C, NOT-READY. E-PEOPLE is read-only. invite, deactivate and reassigning open items have no endpoint. |
| SCR-22 | Project list | main 2: default | FE-M3-PROJECTS / F-07 | building | |
| SCR-23 | Log a received RFP | main 2: default | — | **UNASSIGNED** | F-05 excludes it. |
| SCR-24 | Assign the accountable PM | main 2: default | — | **UNASSIGNED** | F-11 readiness says this belongs to the My work lane, but no task takes it. |
| SCR-25 | Weekly client update | main 12: default, invalid, assembling, review, returned, received | — | **UNASSIGNED** | Starting this work is in F-05; this workspace is not. |
| SCR-26 | RFP response workspace | main 12 (+1 concept): default, review, edit, accepted, reject, response-review | — | **UNASSIGNED** | Team input (SCR-16) is in F-09. |
| SCR-27 | Costing sheet | main 8: default, adjust, ask, approvals | — | **UNASSIGNED** | The CEO's final decision is an FE-DECIDE-VARIANTS variant. |
| SCR-28 | Confirm the minutes | main 12: default, suggesting, drafted, review, internal, published | — | **UNASSIGNED** | Starting this work is in F-05. |
| SCR-29 | Project actions | main 2: default | FE-M3-PROJECT-TABS | planned (task only) | E-PROJECT-TAB `actions`. |
| SCR-30 | Issue detail | main 8: default, overdue, no-owner, verified | — | **UNASSIGNED** | |
| SCR-31 | Change request detail | main 18: default, impact, decision, rejected, authorise, notice, execution, go-live-note, closed | — | **UNASSIGNED** | |
| SCR-32 | Payment reminder | fin 2: default | — | **UNASSIGNED** | |
| SCR-33 | Project retrospective | main 2: default | — | **UNASSIGNED** | A closure prerequisite. |
| SCR-34 | Setup: templates | main 2: default | FE-M3-SETUP | planned (task only) | Proposed slice F-11D. E-TEMPLATES is read-only. Versioned upload has no endpoint. |
| SCR-35 | Clients and client details | main 4: default, detail | — | **UNASSIGNED** | F-11 readiness says this belongs to the projects lane, but no task takes it. |
| SCR-36 | Month-end | fin 2: default | FE-M3-FINANCE / F-10 | planned (F-10, readiness READY in draft) | E-MONTH-END. |
| SCR-37 | Payroll corrections (restricted) | fin 2: default | FE-M3-FINANCE (R-FINANCE includes the back-office lines) | planned (task only) | Proposed slice F-10C. NOT-READY: the HR Lead decision (`payroll.hr_correction`) has no endpoint. |
| SCR-38 | Project milestones | main 4: default, changed | FE-M3-PROJECT-TABS | planned (task only) | E-PROJECT-TAB `milestones` (D-PROJECT-TAB-ROWS). The audit request listed this screen as unassigned, but v6 assigns it. |
| SCR-39 | Setup: costing rule | main 8: default, review, example, review-own | FE-M3-SETUP (R-SETUP) | planned (task only) | Proposed slice F-11F. NOT-READY: there is no endpoint for the review, the worked examples or withdrawing a version, and the backend must change to one studio-wide rule. |
| SCR-40 | RFP submission | main 8: draft, review, submitted, submitted-portal | — | **UNASSIGNED** | |
| SCR-41 | Engagement | main 4: default, register | — | **UNASSIGNED** | |
| SCR-42 | Planning | main 10: default, record, held, readiness, ready | — | **UNASSIGNED** | |
| SCR-43 | Delivery overview | main 2: default | — | **UNASSIGNED** | F-07 excludes it. |
| SCR-44 | Release gates | main 12: default, decision, returned, owner-needed, readiness, ready | — | **UNASSIGNED** | |
| SCR-45 | Go-live acceptance | main 10: default, signatures, accepted, changes, declined | — | **UNASSIGNED** | |
| SCR-46 | Hypercare | main 12: default, record, evaluating, qualified, not-met, setup-needed | — | **UNASSIGNED** | |
| SCR-47 | Archive | main 6: default, working, uncertain | — | **UNASSIGNED** | |
| SCR-48 | Handover to Support | main 8: default, record, gaps, received | — | **UNASSIGNED** | |
| SCR-49 | Closure | main 10: default, blocked, decision, returned, closed | — | **UNASSIGNED** | |
| SCR-50 | Emergency change | main 10: record, refused, review, retro, report | — | **UNASSIGNED** | The CTO decision is an FE-DECIDE-VARIANTS variant. |
| SCR-51 | Escalation | main 12: investigating, decide, not-escalated, draft, review, received | — | **UNASSIGNED** | |
| SCR-52 | Leadership report | main 10: setup, drafting, review, tuesday, received | — | **UNASSIGNED** | FE-M3-OVERVIEW refers to R-REPORTS, but F-08 excludes SCR-52 and no other task takes it. |
| SCR-53 | Management accounts | fin 22: quarantined, units, investigating, reviews, owner-needed, setup-needed, returned, drafting, publishing, uncertain, verified | FE-M3-FINANCE (R-FINANCE includes the back-office lines) | planned (task only) | Proposed slices F-10E1 (intake) and F-10E2 (reviews and publication). The workspace content has no endpoint. |
| SCR-54 | Income detail and schedules | fin 14: investigating, held, review, returned, verified, export, withdrawn | FE-M3-FINANCE (R-FINANCE includes the back-office lines) | planned (task only) | Proposed slice F-10F. No workspace endpoint. |
| SCR-55 | Fixed asset (PPE) schedule | fin 14: investigating, register-review, date-review, calculating, schedule-review, returned, verified | FE-M3-FINANCE (R-FINANCE includes the back-office lines) | planned (task only) | Proposed slice F-10G. No workspace endpoint. |
| SCR-56 | Cash forecast and actuals | fin 14: investigating, review, group-rows, group-review, uncertain, verified, actuals | FE-M3-FINANCE (R-FINANCE includes the back-office lines) | planned (task only) | Proposed slice F-10H. No workspace endpoint. |
| SCR-57 | Business-unit totals | fin 14: source-review, investigating, held, result-review, publish, receipts, verified | FE-M3-FINANCE (R-FINANCE includes the back-office lines) | planned (task only) | Proposed slice F-10I. No workspace endpoint. |
| SCR-58 | Ledger source reference | fin 12: investigating, duplicate, observe, review, rejected, verified | FE-M3-FINANCE (R-FINANCE includes the back-office lines) | planned (task only) | Proposed slice F-10J. No workspace endpoint. |
| SCR-59 | Payroll run (restricted) | fin 18: input-review, combine-review, match-held, match-review, totals-review, publish, receipts, verified, followup | FE-M3-FINANCE (R-FINANCE includes the back-office lines) | planned (task only) | Proposed slice F-10D. Only match-review uses E-PAYROLL-MATCH; the rest has no endpoint. |

## Reference-only boards (62)

These are not platform screens. No frontend task builds them, but tasks use them as reference.

- **Concept boards (open or decided):** main: `AGENT-concepts`, `MYWORK-queue-concepts`, `NAV-concepts`, `SCR-01-empty-concepts`, `SCR-01-floor-concepts`, `SCR-04-progress-concepts`, `SCR-04-start-concepts`, `SCR-06-overview-concepts`, `SCR-26-team-input-concepts`.
- **Concept directions A to D:** `a-item`, `a-phone`, `a-queue`, `b-item`, `b-phone`, `b-queue`, `c-assistant`, `c-item`, `c-phone`, `c-queue`, `d-item`, `d-phone`, `d-queue`.
- **Step maps:** `PRESALE-flow-desktop`, `PMO-flow-desktop`, `DELIVERY-flow-desktop`; fin: `FINANCE-flow-desktop`.
- **Line maps:** main: `LINES-desktop` and 18 `LINE-*-desktop` boards (pmo-finance, -issues, -leadership-report, -minutes, -escalation, -weekly-report, -emergency, -change, rfp-response, engagement, commercial, planning, delivery-release, -go-live, -hypercare, -handover, -archive, -closure); fin: 7 `LINE-finance-*-desktop` boards (accounts, schedules, ppe, forecast, bu, ledger, payroll).
- **Storyboard:** `J04-desktop`, `J04-mobile`.
- **Navigation and shared patterns:** `SITEMAP-desktop`; `STATES-desktop` and `STATES-mobile` (the shared empty, loading and error pattern, applied inside each list feature); `Main` (on both canvases); `FINANCE-moved-desktop`; `mascot-family`, `mascot-poses`.

## Proposed new frontend tasks for the 27 unassigned screens

What all of these have in common: the v6 contract already supplies the generic work-item frame for every line screen. That frame is:
- E-WORK-ITEM: stations, agent checklist, tasks with `decision` and `response`, `reconcile`, `allowed_actions`;
- E-WORK-HISTORY;
- E-TASK-CLAIM and E-TASK-DECIDE: approve, return, reject, revoke;
- E-RESPONSE and E-EVIDENCE-UPLOAD;
- E-WORK-ACTION;
- E-DOCUMENT.

What v6 does **not** have is the line-specific content of each workspace (matrices, calculations, suggestion lists, review findings, recipient receipts) or the line-specific writes. So most tasks below are "partial": the frame and the decisions can be built now, but the workspace body needs a v7 contract.

**Engineering proposal, not a business rule:** decide in architecture whether to add one typed `workspace` block per line on E-WORK-ITEM, following the same pattern as `rfp_outcome` and `reconcile` in v6, plus one generic line-step write. The alternative is per-line endpoints. One shared block would avoid about 25 new endpoints. Each task below should start with its contract revision.

| Proposed task | Screens (board files) | Endpoints v6 already has | Missing from v6 | Contract has it? |
|---|---|---|---|---|
| FE-SIGNIN | SCR-17 (8); also the SCR-15 account menu sign-out | E-ME only (401 when signed out) | Sign-in, sign-out, password reset request and confirm, accept invite and set password. All of these depend on D-AUTH (proposed, owned by the backend developer). Alternative: style the Django-rendered pages to the boards. | No |
| FE-RFP-INTAKE | SCR-23 (2), SCR-24 (2) | E-LINES, E-LINE-OPTIONS, E-EVIDENCE-UPLOAD, E-WORK-START; E-WORK-LIST `queue=unassigned` | E-WORK-START requires `case_id`, but a new RFP has no case yet. This needs a fixed intake case (D-START-INTAKE `case_scope`) or a start that creates the case. Assigning a PM (`rfp.assign`) has no endpoint. | Partial |
| FE-RFP-RESPONSE | SCR-26 (12) | E-WORK-ITEM, E-TASK-DECIDE (response review), E-RESPONSE (team input, F-09) | Reading the requirements matrix rows with filter and select-all; accepting, editing or rejecting a suggestion, and writing your own answer; undo | Partial |
| FE-RFP-SUBMIT | SCR-40 (8) | E-WORK-ITEM, E-DOCUMENT (pack), E-TASK-DECIDE (document reviewer), E-WORK-ACTION reconcile | Pack checks, the submission method (email or portal), the submit action by the configured publisher, and the receipt check | Partial |
| FE-COSTING | SCR-27 (8). Build it after F-11F (SCR-39), which has the same contract needs. | E-TASK-DECIDE (approval chain PM, then PMO Lead, then CEO); E-SETUP-RULES and E-SETUP-RULE-SAVE (save the rule as a new version); E-RESPONSE (estimate as team input) | Costing sheet read: inputs, calculation steps, total shown as Unknown while any estimate is missing. Adjustment write, which restarts approvals. The ask-for-estimate action. Worked examples with match results, rule review, and withdrawing a proposed version. The backend still needs to change to one studio-wide rule. | Partial |
| FE-ENGAGEMENT-PLANNING | SCR-41 (4), SCR-42 (10) | E-WORK-ITEM (agent steps, owner needed), E-RESPONSE and E-EVIDENCE-UPLOAD (department input with proof), E-TASK-DECIDE | Planning packet content with Unknowns kept; confirm PM and register (creates the project); the list of departments asked and the readiness checklist | Partial |
| FE-LINE-WEEKLY | SCR-25 (12) | E-WORK-ITEM, E-TASK-DECIDE (review, return), E-DOCUMENT, E-WORK-ACTION (delivery uncertain) | The week's source records (meetings, actions, milestones, issues, changes); writing the PM's four sections, each citing a record | Partial |
| FE-LINE-MINUTES | SCR-28 (12) | E-WORK-ITEM, E-EVIDENCE-UPLOAD (notes), E-TASK-DECIDE, E-DOCUMENT | The agent's suggested decisions and actions; confirming, editing or discarding each one (owner, due date); choosing the audience (internal or published) | Partial |
| FE-ISSUE | SCR-30 (8) | E-PROJECT-TAB `registers` (rows), E-WORK-ITEM, E-WORK-HISTORY | Issue facts beyond the work item; the owner's follow-up (acknowledge, started, progress: `issue.work`) | Partial |
| FE-CHANGE | SCR-31 (18) | E-WORK-ITEM, E-TASK-DECIDE (decision, authorise), E-DOCUMENT (notice), E-PROJECT-TAB milestones (SCR-38 changed) | Impact assessments per team as recorded by the PM; several deciders. Open question: does the change need all five deciders or only some? | Partial |
| FE-EMERGENCY-ESCALATION | SCR-50 (10), SCR-51 (12) | E-WORK-START (incident and escalation drawers, F-05), E-WORK-ITEM, E-TASK-DECIDE (the CTO variant is parked under FE-DECIDE-VARIANTS), E-DOCUMENT | Emergency record and refusal, retrospective and report content; escalation findings, the escalate or not-escalated decision, and draft review content. Open question: who decides an emergency when the decider has no login? | Partial |
| FE-LEADERSHIP-REPORT | SCR-52 (10) | E-WORK-START (leadership drawer), E-WORK-ITEM, E-TASK-DECIDE (monthly review), E-REPORT (figures and their sources) | Report setup (recipients, Tuesday or monthly cadence); receipts per recipient | Mostly yes |
| FE-MILESTONE-COMPLETE (could be folded into FE-M3-PROJECT-TABS) | SCR-19 (2) | E-PROJECT-TAB `milestones`, E-EVIDENCE-UPLOAD, E-WORK-START (pmo-finance line intake) | Confirm that "mark complete" is an E-WORK-START of the invoice line and not its own milestone write (D-START-INTAKE) | Probably yes; confirm |
| FE-DELIVERY-RELEASE | SCR-43 (2), SCR-44 (12), SCR-45 (10) | E-PROJECT (lines per project), E-WORK-ITEM, E-TASK-DECIDE (PMO Lead gate), E-RESPONSE, E-EVIDENCE-UPLOAD | Six-line delivery overview with the status of each gate; readiness checklist content; go-live signatures and changes-requested or declined outcomes. The E-RESPONSE `variant` only allows client_response, sow_signature and team_input. | Partial |
| FE-DELIVERY-HYPERCARE-ARCHIVE | SCR-46 (12), SCR-47 (6) | E-WORK-ITEM, E-WORK-ACTION reconcile (archive uncertain), E-SETUP-RULES (criteria Not set) | Hypercare release record, evaluation against criteria, qualified or not met; the archive index | Partial |
| FE-DELIVERY-CLOSURE | SCR-48 (8), SCR-49 (10), SCR-33 (2) | E-WORK-ITEM, E-RESPONSE (Support reply recorded by the PM), E-TASK-DECIDE (PMO Lead closure decision), E-DOCUMENT, E-PROJECT-TAB money (debt still owed) | Handover gaps list; closure blockers checklist; retrospective sections citing records, and participants | Partial |
| FE-PAYMENTS | SCR-20 (4), SCR-32 (2) | E-PROJECT-TAB `money` (per project only), E-WORK-ACTION reconcile (reminder delivery), E-TASK-DECIDE (the short payment is parked under D-DECISION-VARIANTS) | A Finance-wide invoice list (invoiced, received, owed, with Unknown where data is missing); recording a receipt with bank reference and proof; allocations kept separate from receipts; the reminder draft, edit and send. A financial rule is involved, so build nothing for the short payment until PSL sets it. | No |
| FE-CLIENTS | SCR-35 (4) | — | Client register; client detail; billing contact write (which blocks invoices until it exists) | No |

### Contract needs for the proposed FE-M3-FINANCE slices

These screens are assigned (they come under R-FINANCE), so they are not new tasks. They are listed here because, like the line workspaces above, they cannot be built until v7 adds the workspace content.

| Proposed slice | Screens (board files) | Endpoints v6 already has | Missing from v6 | Contract has it? |
|---|---|---|---|---|
| F-10E1 and F-10E2 | SCR-53 (22) | E-LINES, E-IMPORT (FE-M2A-PROOF), E-WORK-ITEM, E-TASK-DECIDE (the six reviews; revoke), E-WORK-ACTION, E-MONTH-END (link), E-DOCUMENT | Quarantine findings, units needed, review results, calculation results, recipients and receipts | Partial |
| F-10F and F-10G | SCR-54 (14), SCR-55 (14) | Same frame as F-10E | Income or schedule rows, duplicate checks, adjustment export, correct and resubmit (D-RETURN is open); register changes, unclear dates, and the schedule by asset class with Unknown | Partial |
| F-10H and F-10I | SCR-56 (14), SCR-57 (14) | Same frame | Forecast months with Unknown, group disclosure rows, actuals against forecast; BU totals with hold reasons (small-group protection), recipients and receipts | Partial |
| F-10J | SCR-58 (12) | Same frame | Ledger lineage; recording what was found in QuickBooks; duplicate refusal; independent review result | Partial |
| F-10D and F-10C | SCR-59 (18), SCR-37 (2) | Same frame, plus E-PAYROLL-MATCH (match-review, HR roles only) | Input and combine review, totals per BU, recipients and receipts, follow-up after cancelling; HR correction requests and the HR Lead decision (`payroll.hr_correction`), with identities masked | Partial |

Gaps in assigned tasks to close in their readiness:
- **FE-M3-SETUP / F-11:** SCR-21 invite and deactivate, and SCR-34 template upload, have no endpoints.
- **FE-M3-PROJECT-TABS:** name the SCR-08 document review page explicitly.
- **FE-M4 / F-12:** sign-out in the account menu depends on D-AUTH.
- **FE-DECIDE-VARIANTS and FE-M2A-PROOF:** neither has a feature record yet. FE-DECIDE-VARIANTS stays parked until PSL decides D-DECISION-VARIANTS.
