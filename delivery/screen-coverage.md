# Screen coverage: approved screens and the frontend tasks that build them

Regenerated 14 Nov 2026 for architecture v7 (`architecture/packages/v7/model.json`, commit 61a7ade). It replaces the v6 audit. Nothing is unassigned any more: every approved screen has at least one frontend task in v7.

## Summary

- **Screens:** 59, all in the client approval (`design/review.json`, canvas 1794581312-b166, 13 Nov 2026). **Board files:** 585 (442 main, 143 Finance and payroll): 523 belong to the 59 screens, and 62 are reference-only (listed at the end).
- **Frontend tasks in v7:** 58 active (owner role "frontend developer") plus 3 retired (FE-M2, FE-M3, FE-M4). 13 task ids have a feature record (one of them, FE-M4, is retired); 46 active tasks do not yet.
- **Merged so far:** app frame (T-FRONTEND-SHELL, F-01), My work (FE-MYWORK, F-02; reopened for a fidelity round), work item (FE-WORKITEM, F-03), decision (FE-DECIDE, F-04). Exceptions (FE-M2B, F-06) is in review and expected to merge soon; it is not counted as merged, and no task depends on it.

| Task status | Tasks | Screens whose first task has this status | Board files |
|---|---|---|---|
| Merged | 4 | 4 | 59 |
| In review | 2 | 3 | 6 |
| Building | 2 | 2 | 36 |
| Planned, can start now | 4 | 3 | 44 |
| Planned, waits on other tasks | 36 | 42 | 330 |
| Gated by an open decision | 10 | 5 | 48 |
| **Total** | **58** | **59** | **523** |

The screen column counts a screen once, by the first task in its row of the screen table. A screen with several tasks (for example SCR-03, whose standard decision is merged and whose variants are gated) can be partly built.

### Building or in review (4)

- `FE-M2A`: Feature: F-05.
- `FE-M2B` (PR #11 open): Feature: F-06.
- `FE-M3-PROJECTS` (in review): Feature: F-07.
- `FE-M3-OVERVIEW`: Feature: F-08.

### Can start now (every dependency is merged, no open decision) (4)

- `FE-M3-FINANCE`: Feature: F-10.
- `FE-M3-SETUP`: Feature: F-11.
- `FE-M2B-RESPONSE`: Feature: F-09.
- `FE-CONTRACT-V7`: Feature: F-13.

### Wait on other tasks (nothing else blocks them) (36)

- `FE-CONNECT-1`: Waits on: T-FOUNDATION, T-MYWORK, T-WORKITEM, T-DECIDE.
- `FE-M2A-PROOF`: Waits on: FE-M2A, FE-M2B-RESPONSE.
- `FE-M3-PROJECT-TABS`: Waits on: FE-M3-PROJECTS.
- `FE-M3-REPORT`: Waits on: FE-M3-PROJECTS.
- `FE-M2B-RFP`: Waits on: FE-M2B-RESPONSE, FE-CONTRACT-V7.
- `FE-WORKSPACE-FRAME`: Waits on: FE-M2B-RESPONSE, FE-CONTRACT-V7.
- `FE-RFP-INTAKE`: Waits on: FE-M2A, FE-CONTRACT-V7.
- `FE-RFP-RESPONSE`: Waits on: FE-WORKSPACE-FRAME, FE-M2B-RFP.
- `FE-RFP-SUBMIT`: Waits on: FE-WORKSPACE-FRAME, FE-M2B-RFP.
- `FE-ENGAGEMENT-PLANNING`: Waits on: FE-WORKSPACE-FRAME.
- `FE-LINE-WEEKLY`: Waits on: FE-WORKSPACE-FRAME.
- `FE-LINE-MINUTES`: Waits on: FE-WORKSPACE-FRAME.
- `FE-ISSUE`: Waits on: FE-WORKSPACE-FRAME, FE-M3-PROJECT-TABS.
- `FE-EMERGENCY-ESCALATION`: Waits on: FE-WORKSPACE-FRAME, FE-M2A.
- `FE-LEADERSHIP-REPORT`: Waits on: FE-WORKSPACE-FRAME, FE-M3-REPORT.
- `FE-MILESTONE-COMPLETE`: Waits on: FE-M3-PROJECT-TABS, FE-M2A-PROOF.
- `FE-DOCUMENT-REVIEW`: Waits on: FE-M3-PROJECT-TABS.
- `FE-DELIVERY-RELEASE`: Waits on: FE-WORKSPACE-FRAME, FE-M3-PROJECTS.
- `FE-DELIVERY-HYPERCARE-ARCHIVE`: Waits on: FE-WORKSPACE-FRAME.
- `FE-DELIVERY-CLOSURE`: Waits on: FE-WORKSPACE-FRAME.
- `FE-PAYMENTS`: Waits on: FE-WORKSPACE-FRAME.
- `FE-CLIENTS`: Waits on: FE-M3-PROJECTS, FE-CONTRACT-V7.
- `FE-FIN-PAYROLL-IMPORT`: Waits on: FE-WORKSPACE-FRAME.
- `FE-FIN-PAYROLL-CORRECTIONS`: Waits on: FE-WORKSPACE-FRAME.
- `FE-FIN-PAYROLL-RUN`: Waits on: FE-FIN-PAYROLL-IMPORT.
- `FE-FIN-ACCOUNTS-INTAKE`: Waits on: FE-WORKSPACE-FRAME, FE-M2A-PROOF.
- `FE-FIN-ACCOUNTS-PUBLISH`: Waits on: FE-FIN-ACCOUNTS-INTAKE, FE-M3-FINANCE.
- `FE-FIN-SCHEDULES`: Waits on: FE-WORKSPACE-FRAME.
- `FE-FIN-PPE`: Waits on: FE-WORKSPACE-FRAME.
- `FE-FIN-FORECAST`: Waits on: FE-WORKSPACE-FRAME.
- `FE-FIN-BU`: Waits on: FE-WORKSPACE-FRAME.
- `FE-FIN-LEDGER`: Waits on: FE-WORKSPACE-FRAME.
- `FE-SETUP-DELEGATION`: Waits on: FE-M3-SETUP, FE-CONTRACT-V7.
- `FE-SETUP-TEMPLATES`: Waits on: FE-M3-SETUP, FE-CONTRACT-V7.
- `FE-ALERTS`: Waits on: FE-CONTRACT-V7.
- `FE-ASSISTANT`: Waits on: FE-CONTRACT-V7, FE-M2A.

### Gated by an open decision (10)

- `FE-DECIDE-VARIANTS`: Open decision: D-DECISION-VARIANTS. Nothing else blocks it.
- `FE-COSTING`: Open decision: D-COSTING-RULE. Also waits on: FE-WORKSPACE-FRAME, FE-SETUP-COSTING.
- `FE-CHANGE`: Open decision: D-CHANGE-DECIDERS. Also waits on: FE-WORKSPACE-FRAME, FE-M3-PROJECT-TABS.
- `FE-PAYMENTS-RECEIPT`: Open decision: D-RECEIPT-ALLOCATION. Also waits on: FE-PAYMENTS.
- `FE-SIGNIN`: Open decision: D-SIGNIN. Nothing else blocks it.
- `FE-SETUP-ROLES`: Open decision: D-ADMIN-AUTHORITY. Also waits on: FE-M3-SETUP, FE-CONTRACT-V7.
- `FE-SETUP-PAYROLL-FIELDS`: Open decision: D-PAYROLL-VISIBILITY. Also waits on: FE-M3-SETUP, FE-CONTRACT-V7.
- `FE-SETUP-COSTING`: Open decision: D-COSTING-RULE. Also waits on: FE-M3-SETUP, FE-CONTRACT-V7.
- `FE-ALERTS-MENU`: Open decision: D-ALERTS-ENTRY, D-SIGNIN. Also waits on: FE-ALERTS, FE-M2A.
- `FE-ASSISTANT-SPEECH`: Open decision: D-SPEECH-INPUT. Also waits on: FE-ASSISTANT.

Notes on the start-now list: FE-CONTRACT-V7 (F-13) unblocks most of the line workspaces, so it is the first one to take. FE-M2B-RESPONSE (F-09) is next because FE-WORKSPACE-FRAME, FE-M2B-RFP and FE-M2A-PROOF wait on it. FE-M3-FINANCE (F-10) and FE-M3-SETUP (F-11) are independent of both. FE-CONNECT-1 is not a screen task; it also needs the backend tasks T-FOUNDATION, T-MYWORK, T-WORKITEM and T-DECIDE.

Record problems found in this pass:
- `delivery/features/F-12/feature.json` still lists `FE-M4`, which v7 retired. Its work is now FE-ALERTS, FE-ALERTS-MENU, FE-ASSISTANT and FE-ASSISTANT-SPEECH. Re-point F-12 (or split it) before readiness.
- F-10 and F-11 cover only FE-M3-FINANCE and FE-M3-SETUP. Their proposed slices (F-10B to F-10J, F-11B to F-11F) are now the separate FE-FIN-* and FE-SETUP-* tasks, and none of them has a feature record yet. F-09B (FE-M2B-RFP) has none either.
- The F-02 feature record still says IMPLEMENTING (fidelity round on `fe-mywork-fidelity`), although the first version is merged. FE-MYWORK is treated as merged here, as instructed.

Status key: **merged**; **in review** (a PR is open); **building** (the feature is IMPLEMENTING); **planned, can start now**; **planned, waits on** the named tasks; **gated by** an open decision. "Feature" is the id in `delivery/features/F-*/feature.json` `task_ids`, or "none yet".

## Screen table

Board column: canvas folder, file count, then the state suffixes. Each state has a `-desktop` and a `-mobile` file, for example `SCR-25-desktop-review.dc.html`. "default" means `SCR-nn-desktop.dc.html` and `SCR-nn-mobile.dc.html`. main = `design/canvas/project/`; fin = `design/canvas/finance/project/`.

| Screen | Title | Boards | v7 frontend task | Feature | Status |
|---|---|---|---|---|---|
| SCR-01 | My work (work queue) | main 9 (+2 concept): default, my-work, empty, filter, lead | `FE-MYWORK` (default, my-work, empty, filter, lead) | F-02 | merged |
| SCR-02 | Work item | main 26: default, ready, processing, waiting, setup-needed, awaiting-reconciliation, cancelled, owner-needed, effect-uncertain, verified, permission, issue, history; fin 6: evidence-asked, evidence-supplied, returned | `FE-WORKITEM` (all states, read-only)<br>`FE-M2B-RESPONSE` (awaiting-reconciliation, evidence actions)<br>`FE-WORKSPACE-FRAME` (line workspace body) | F-03<br>F-09<br>none yet | merged<br>planned, can start now<br>planned, waits on FE-M2B-RESPONSE, FE-CONTRACT-V7 |
| SCR-03 | Decision | main 14: default, done, not-yours, stale, payment-exception, ceo-costing, cto-emergency; fin 2: own | `FE-DECIDE` (default, done, not-yours, stale, own)<br>`FE-DECIDE-VARIANTS` (payment-exception, ceo-costing, cto-emergency) | F-04<br>none yet | merged<br>gated by D-DECISION-VARIANTS |
| SCR-04 | Start work | main 34 (+2 concept): default, lines, validation, weekly, minutes, issue, change, incident, escalation, leadership, accounts, schedules, ppe, forecast, bu, ledger, payroll | `FE-M2A` (default, lines, validation and the core drawers)<br>`FE-M2A-PROOF` (proof fields; accounts, schedules, ppe, forecast, bu, ledger, payroll drawers) | F-05<br>none yet | building<br>planned, waits on FE-M2A, FE-M2B-RESPONSE |
| SCR-05 | Assistant | main 10: default, thread, draft-started, cant, working | `FE-ASSISTANT` (all states)<br>`FE-ASSISTANT-SPEECH` (Speak your request) | none yet<br>none yet | planned, waits on FE-CONTRACT-V7, FE-M2A<br>gated by D-SPEECH-INPUT (also waits on FE-ASSISTANT) |
| SCR-06 | Overview: factory floor | main 2 (+1 concept): default (reduced-motion uses the flat view) | `FE-M3-OVERVIEW` | F-08 | building |
| SCR-07 | Project journey | main 2: default | `FE-M3-PROJECTS` | F-07 | in review |
| SCR-08 | Document review | main 4: default, returned | `FE-DOCUMENT-REVIEW` | none yet | planned, waits on FE-M3-PROJECT-TABS |
| SCR-09 | Import and reconcile | fin 4: default, error | `FE-FIN-PAYROLL-IMPORT` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-10 | All exceptions | main 2: default | `FE-M2B` | F-06 | in review (PR #11) |
| SCR-11 | Registers (issues, changes, RFPs) | main 2: default | `FE-M3-PROJECT-TABS` (registers) | none yet | planned, waits on FE-M3-PROJECTS |
| SCR-12 | Report with drill-down | main 2: default | `FE-M3-REPORT` | none yet | planned, waits on FE-M3-PROJECTS |
| SCR-13 | Setup: roles, rules, delegation | main 16: default, validation, permission, fields, rules, delegation, delivery-rules, finance-rules | `FE-M3-SETUP` (rules, delivery-rules, finance-rules)<br>`FE-SETUP-DELEGATION` (delegation)<br>`FE-SETUP-ROLES` (default, permission, validation)<br>`FE-SETUP-PAYROLL-FIELDS` (fields) | F-11<br>none yet<br>none yet<br>none yet | planned, can start now<br>planned, waits on FE-M3-SETUP, FE-CONTRACT-V7<br>gated by D-ADMIN-AUTHORITY (also waits on FE-M3-SETUP, FE-CONTRACT-V7)<br>gated by D-PAYROLL-VISIBILITY (also waits on FE-M3-SETUP, FE-CONTRACT-V7) |
| SCR-14 | Verified outputs | main 2: default | `FE-MYWORK` (Done queue, Verified filter) | F-02 | merged |
| SCR-15 | Alerts and notification settings | main 10: default, settings, email, whatsapp, account | `FE-ALERTS` (default, settings)<br>`FE-ALERTS-MENU` (account) | none yet<br>none yet | planned, waits on FE-CONTRACT-V7<br>gated by D-ALERTS-ENTRY, D-SIGNIN (also waits on FE-ALERTS, FE-M2A) |
| SCR-16 | Record a response | main 26: default, validation, success, team-input, sow-signed, rfp-outcome(-lost/-pending/-unknown), rfp-won/-lost/-pending/-unknown | `FE-M2B-RESPONSE` (default, validation, success, sow-signed)<br>`FE-M2B-RFP` (team-input and the rfp-outcome boards) | F-09<br>none yet | planned, can start now<br>planned, waits on FE-M2B-RESPONSE, FE-CONTRACT-V7 |
| SCR-17 | Sign in | main 8: default, error, reset, setup | `FE-SIGNIN` | none yet | gated by D-SIGNIN |
| SCR-18 | Restricted payroll matching | fin 4: default, permission | `FE-FIN-PAYROLL-IMPORT` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-19 | Mark a milestone complete | main 2: default | `FE-MILESTONE-COMPLETE` | none yet | planned, waits on FE-M3-PROJECT-TABS, FE-M2A-PROOF |
| SCR-20 | Payments and follow-up | fin 4: default, record | `FE-PAYMENTS` (default)<br>`FE-PAYMENTS-RECEIPT` (record) | none yet<br>none yet | planned, waits on FE-WORKSPACE-FRAME<br>gated by D-RECEIPT-ALLOCATION (also waits on FE-PAYMENTS) |
| SCR-21 | Staff accounts | main 6: default, invite, deactivate | `FE-SETUP-ROLES` | none yet | gated by D-ADMIN-AUTHORITY (also waits on FE-M3-SETUP, FE-CONTRACT-V7) |
| SCR-22 | Project list | main 2: default | `FE-M3-PROJECTS` | F-07 | in review |
| SCR-23 | Log a received RFP | main 2: default | `FE-RFP-INTAKE` | none yet | planned, waits on FE-M2A, FE-CONTRACT-V7 |
| SCR-24 | Assign the accountable PM | main 2: default | `FE-RFP-INTAKE` | none yet | planned, waits on FE-M2A, FE-CONTRACT-V7 |
| SCR-25 | Weekly client update | main 12: default, invalid, assembling, review, returned, received | `FE-LINE-WEEKLY` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-26 | RFP response workspace | main 12 (+1 concept): default, review, edit, accepted, reject, response-review | `FE-RFP-RESPONSE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2B-RFP |
| SCR-27 | Costing sheet | main 8: default, adjust, ask, approvals | `FE-COSTING` | none yet | gated by D-COSTING-RULE (also waits on FE-WORKSPACE-FRAME, FE-SETUP-COSTING) |
| SCR-28 | Confirm the minutes | main 12: default, suggesting, drafted, review, internal, published | `FE-LINE-MINUTES` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-29 | Project actions | main 2: default | `FE-M3-PROJECT-TABS` (actions) | none yet | planned, waits on FE-M3-PROJECTS |
| SCR-30 | Issue detail | main 8: default, overdue, no-owner, verified | `FE-ISSUE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M3-PROJECT-TABS |
| SCR-31 | Change request detail | main 18: default, impact, decision, rejected, authorise, notice, execution, go-live-note, closed | `FE-CHANGE` | none yet | gated by D-CHANGE-DECIDERS (also waits on FE-WORKSPACE-FRAME, FE-M3-PROJECT-TABS) |
| SCR-32 | Payment reminder | fin 2: default | `FE-PAYMENTS` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-33 | Project retrospective | main 2: default | `FE-DELIVERY-CLOSURE` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-34 | Setup: templates | main 2: default | `FE-SETUP-TEMPLATES` | none yet | planned, waits on FE-M3-SETUP, FE-CONTRACT-V7 |
| SCR-35 | Clients and client details | main 4: default, detail | `FE-CLIENTS` | none yet | planned, waits on FE-M3-PROJECTS, FE-CONTRACT-V7 |
| SCR-36 | Month-end | fin 2: default | `FE-M3-FINANCE` | F-10 | planned, can start now |
| SCR-37 | Payroll corrections (restricted) | fin 2: default | `FE-FIN-PAYROLL-CORRECTIONS` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-38 | Project milestones | main 4: default, changed | `FE-M3-PROJECT-TABS` (milestones) | none yet | planned, waits on FE-M3-PROJECTS |
| SCR-39 | Setup: costing rule | main 8: default, review, example, review-own | `FE-SETUP-COSTING` | none yet | gated by D-COSTING-RULE (also waits on FE-M3-SETUP, FE-CONTRACT-V7) |
| SCR-40 | RFP submission | main 8: draft, review, submitted, submitted-portal | `FE-RFP-SUBMIT` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2B-RFP |
| SCR-41 | Engagement | main 4: default, register | `FE-ENGAGEMENT-PLANNING` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-42 | Planning | main 10: default, record, held, readiness, ready | `FE-ENGAGEMENT-PLANNING` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-43 | Delivery overview | main 2: default | `FE-DELIVERY-RELEASE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M3-PROJECTS |
| SCR-44 | Release gates | main 12: default, decision, returned, owner-needed, readiness, ready | `FE-DELIVERY-RELEASE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M3-PROJECTS |
| SCR-45 | Go-live acceptance | main 10: default, signatures, accepted, changes, declined | `FE-DELIVERY-RELEASE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M3-PROJECTS |
| SCR-46 | Hypercare | main 12: default, record, evaluating, qualified, not-met, setup-needed | `FE-DELIVERY-HYPERCARE-ARCHIVE` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-47 | Archive | main 6: default, working, uncertain | `FE-DELIVERY-HYPERCARE-ARCHIVE` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-48 | Handover to Support | main 8: default, record, gaps, received | `FE-DELIVERY-CLOSURE` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-49 | Closure | main 10: default, blocked, decision, returned, closed | `FE-DELIVERY-CLOSURE` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-50 | Emergency change | main 10: record, refused, review, retro, report | `FE-EMERGENCY-ESCALATION` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2A |
| SCR-51 | Escalation | main 12: investigating, decide, not-escalated, draft, review, received | `FE-EMERGENCY-ESCALATION` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2A |
| SCR-52 | Leadership report | main 10: setup, drafting, review, tuesday, received | `FE-LEADERSHIP-REPORT` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M3-REPORT |
| SCR-53 | Management accounts | fin 22: quarantined, units, investigating, reviews, owner-needed, setup-needed, returned, drafting, publishing, uncertain, verified | `FE-FIN-ACCOUNTS-INTAKE` (intake states)<br>`FE-FIN-ACCOUNTS-PUBLISH` (reviews, publication) | none yet<br>none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2A-PROOF<br>planned, waits on FE-FIN-ACCOUNTS-INTAKE, FE-M3-FINANCE |
| SCR-54 | Income detail and schedules | fin 14: investigating, held, review, returned, verified, export, withdrawn | `FE-FIN-SCHEDULES` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-55 | Fixed asset (PPE) schedule | fin 14: investigating, register-review, date-review, calculating, schedule-review, returned, verified | `FE-FIN-PPE` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-56 | Cash forecast and actuals | fin 14: investigating, review, group-rows, group-review, uncertain, verified, actuals | `FE-FIN-FORECAST` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-57 | Business-unit totals | fin 14: source-review, investigating, held, result-review, publish, receipts, verified | `FE-FIN-BU` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-58 | Ledger source reference | fin 12: investigating, duplicate, observe, review, rejected, verified | `FE-FIN-LEDGER` | none yet | planned, waits on FE-WORKSPACE-FRAME |
| SCR-59 | Payroll run (restricted) | fin 18: input-review, combine-review, match-held, match-review, totals-review, publish, receipts, verified, followup | `FE-FIN-PAYROLL-RUN` | none yet | planned, waits on FE-FIN-PAYROLL-IMPORT |

## Frontend task table

| Task | Feature | Status | Depends on |
|---|---|---|---|
| `T-FRONTEND-SHELL` | F-01 | merged | none |
| `FE-MYWORK` | F-02 | merged | T-FRONTEND-SHELL |
| `FE-WORKITEM` | F-03 | merged | T-FRONTEND-SHELL |
| `FE-DECIDE` | F-04 | merged | T-FRONTEND-SHELL |
| `FE-DECIDE-VARIANTS` | none yet | gated by D-DECISION-VARIANTS | FE-DECIDE |
| `FE-CONNECT-1` | none yet | planned, waits on T-FOUNDATION, T-MYWORK, T-WORKITEM, T-DECIDE | FE-MYWORK, FE-WORKITEM, FE-DECIDE, T-FOUNDATION, T-MYWORK, T-WORKITEM, T-DECIDE |
| `FE-M2A` | F-05 | building | T-FRONTEND-SHELL |
| `FE-M2B` | F-06 | in review (PR #11) | FE-WORKITEM |
| `FE-M3-PROJECTS` | F-07 | in review | T-FRONTEND-SHELL |
| `FE-M3-OVERVIEW` | F-08 | building | T-FRONTEND-SHELL |
| `FE-M3-FINANCE` | F-10 | planned, can start now | T-FRONTEND-SHELL |
| `FE-M3-SETUP` | F-11 | planned, can start now | T-FRONTEND-SHELL |
| `FE-M2A-PROOF` | none yet | planned, waits on FE-M2A, FE-M2B-RESPONSE | FE-M2A, FE-M2B-RESPONSE |
| `FE-M2B-RESPONSE` | F-09 | planned, can start now | FE-WORKITEM |
| `FE-M3-PROJECT-TABS` | none yet | planned, waits on FE-M3-PROJECTS | FE-M3-PROJECTS |
| `FE-M3-REPORT` | none yet | planned, waits on FE-M3-PROJECTS | FE-M3-PROJECTS |
| `FE-CONTRACT-V7` | F-13 | planned, can start now | T-FRONTEND-SHELL |
| `FE-M2B-RFP` | none yet | planned, waits on FE-M2B-RESPONSE, FE-CONTRACT-V7 | FE-M2B-RESPONSE, FE-CONTRACT-V7 |
| `FE-WORKSPACE-FRAME` | none yet | planned, waits on FE-M2B-RESPONSE, FE-CONTRACT-V7 | FE-WORKITEM, FE-DECIDE, FE-M2B-RESPONSE, FE-CONTRACT-V7 |
| `FE-RFP-INTAKE` | none yet | planned, waits on FE-M2A, FE-CONTRACT-V7 | FE-M2A, FE-MYWORK, FE-CONTRACT-V7 |
| `FE-RFP-RESPONSE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2B-RFP | FE-WORKSPACE-FRAME, FE-M2B-RFP |
| `FE-RFP-SUBMIT` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2B-RFP | FE-WORKSPACE-FRAME, FE-M2B-RFP |
| `FE-COSTING` | none yet | gated by D-COSTING-RULE (also waits on FE-WORKSPACE-FRAME, FE-SETUP-COSTING) | FE-WORKSPACE-FRAME, FE-SETUP-COSTING |
| `FE-ENGAGEMENT-PLANNING` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-LINE-WEEKLY` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-LINE-MINUTES` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-ISSUE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M3-PROJECT-TABS | FE-WORKSPACE-FRAME, FE-M3-PROJECT-TABS |
| `FE-CHANGE` | none yet | gated by D-CHANGE-DECIDERS (also waits on FE-WORKSPACE-FRAME, FE-M3-PROJECT-TABS) | FE-WORKSPACE-FRAME, FE-M3-PROJECT-TABS |
| `FE-EMERGENCY-ESCALATION` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2A | FE-WORKSPACE-FRAME, FE-M2A |
| `FE-LEADERSHIP-REPORT` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M3-REPORT | FE-WORKSPACE-FRAME, FE-M3-REPORT |
| `FE-MILESTONE-COMPLETE` | none yet | planned, waits on FE-M3-PROJECT-TABS, FE-M2A-PROOF | FE-M3-PROJECT-TABS, FE-M2A-PROOF |
| `FE-DOCUMENT-REVIEW` | none yet | planned, waits on FE-M3-PROJECT-TABS | FE-M3-PROJECT-TABS, FE-DECIDE |
| `FE-DELIVERY-RELEASE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M3-PROJECTS | FE-WORKSPACE-FRAME, FE-M3-PROJECTS |
| `FE-DELIVERY-HYPERCARE-ARCHIVE` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-DELIVERY-CLOSURE` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-PAYMENTS` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-PAYMENTS-RECEIPT` | none yet | gated by D-RECEIPT-ALLOCATION (also waits on FE-PAYMENTS) | FE-PAYMENTS |
| `FE-CLIENTS` | none yet | planned, waits on FE-M3-PROJECTS, FE-CONTRACT-V7 | FE-M3-PROJECTS, FE-CONTRACT-V7 |
| `FE-SIGNIN` | none yet | gated by D-SIGNIN | T-FRONTEND-SHELL |
| `FE-FIN-PAYROLL-IMPORT` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-FIN-PAYROLL-CORRECTIONS` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-FIN-PAYROLL-RUN` | none yet | planned, waits on FE-FIN-PAYROLL-IMPORT | FE-FIN-PAYROLL-IMPORT |
| `FE-FIN-ACCOUNTS-INTAKE` | none yet | planned, waits on FE-WORKSPACE-FRAME, FE-M2A-PROOF | FE-WORKSPACE-FRAME, FE-M2A-PROOF |
| `FE-FIN-ACCOUNTS-PUBLISH` | none yet | planned, waits on FE-FIN-ACCOUNTS-INTAKE, FE-M3-FINANCE | FE-FIN-ACCOUNTS-INTAKE, FE-M3-FINANCE |
| `FE-FIN-SCHEDULES` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-FIN-PPE` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-FIN-FORECAST` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-FIN-BU` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-FIN-LEDGER` | none yet | planned, waits on FE-WORKSPACE-FRAME | FE-WORKSPACE-FRAME |
| `FE-SETUP-DELEGATION` | none yet | planned, waits on FE-M3-SETUP, FE-CONTRACT-V7 | FE-M3-SETUP, FE-CONTRACT-V7 |
| `FE-SETUP-ROLES` | none yet | gated by D-ADMIN-AUTHORITY (also waits on FE-M3-SETUP, FE-CONTRACT-V7) | FE-M3-SETUP, FE-CONTRACT-V7 |
| `FE-SETUP-TEMPLATES` | none yet | planned, waits on FE-M3-SETUP, FE-CONTRACT-V7 | FE-M3-SETUP, FE-CONTRACT-V7 |
| `FE-SETUP-PAYROLL-FIELDS` | none yet | gated by D-PAYROLL-VISIBILITY (also waits on FE-M3-SETUP, FE-CONTRACT-V7) | FE-M3-SETUP, FE-CONTRACT-V7 |
| `FE-SETUP-COSTING` | none yet | gated by D-COSTING-RULE (also waits on FE-M3-SETUP, FE-CONTRACT-V7) | FE-M3-SETUP, FE-CONTRACT-V7 |
| `FE-ALERTS` | none yet | planned, waits on FE-CONTRACT-V7 | FE-CONTRACT-V7 |
| `FE-ALERTS-MENU` | none yet | gated by D-ALERTS-ENTRY, D-SIGNIN (also waits on FE-ALERTS, FE-M2A) | FE-ALERTS, FE-M2A |
| `FE-ASSISTANT` | none yet | planned, waits on FE-CONTRACT-V7, FE-M2A | FE-CONTRACT-V7, FE-M2A |
| `FE-ASSISTANT-SPEECH` | none yet | gated by D-SPEECH-INPUT (also waits on FE-ASSISTANT) | FE-ASSISTANT |

Retired in v7: `FE-M2`, `FE-M3`, `FE-M4`.

Tasks with no screen of their own: `T-FRONTEND-SHELL`, `FE-CONNECT-1`, `FE-CONTRACT-V7`. FE-CONNECT-1 connects merged features to the real API; FE-CONTRACT-V7 repoints the contract.

## Reference-only boards (62)

These are not platform screens. No frontend task builds them, but tasks use them as reference.

- **Concept boards (open or decided):** main: `AGENT-concepts`, `MYWORK-queue-concepts`, `NAV-concepts`, `SCR-01-empty-concepts`, `SCR-01-floor-concepts`, `SCR-04-progress-concepts`, `SCR-04-start-concepts`, `SCR-06-overview-concepts`, `SCR-26-team-input-concepts`.
- **Concept directions A to D:** `a-item`, `a-phone`, `a-queue`, `b-item`, `b-phone`, `b-queue`, `c-assistant`, `c-item`, `c-phone`, `c-queue`, `d-item`, `d-phone`, `d-queue`.
- **Step maps:** `PRESALE-flow-desktop`, `PMO-flow-desktop`, `DELIVERY-flow-desktop`; fin: `FINANCE-flow-desktop`.
- **Line maps:** main: `LINES-desktop` and 18 `LINE-*-desktop` boards (pmo-finance, -issues, -leadership-report, -minutes, -escalation, -weekly-report, -emergency, -change, rfp-response, engagement, commercial, planning, delivery-release, -go-live, -hypercare, -handover, -archive, -closure); fin: 7 `LINE-finance-*-desktop` boards (accounts, schedules, ppe, forecast, bu, ledger, payroll).
- **Storyboard:** `J04-desktop`, `J04-mobile`.
- **Navigation and shared patterns:** `SITEMAP-desktop`; `STATES-desktop` and `STATES-mobile` (the shared empty, loading and error pattern, applied inside each list feature); `Main` (on both canvases); `FINANCE-moved-desktop`; `mascot-family`, `mascot-poses`.
