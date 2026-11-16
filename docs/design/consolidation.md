# Factory screen consolidation

The 59 screen IDs come from `delivery/screen-coverage.md` at `4689cee`. Desktop, phone and alternate states belong to the same screen. Core permissions, document versions, policy values, approvals, amounts, agent handoffs and receipt checks come from the existing application. The design supplies layout and interaction guidance. A native destination below establishes a place to integrate and on its own does not establish design parity or acceptance.

The first increment uses one server-rendered shell for native screens, including sign-in, onboarding, workspace creation, access setup and password change. My Work, Overview, Project Journey and the Assistant use native data. The Assistant accepts synthetic documents, queues one of eight worker roles and links to the draft, human review and native handoff. The standalone frontend remains a design reference. Its sample data and proposed workflow effects are outside the hosted application.

| Screen | Existing destination or service | Remaining design work |
| --- | --- | --- |
| SCR-01 My work | `home`, `work_inbox`; authorized factory work and recorded assignments | Match filters and verify queue coverage |
| SCR-02 Work item | `factory_detail`; definition-specific views, coordinator and recovery | Align station progress, evidence and actions across definitions |
| SCR-03 Decision | `factory_detail`, `approvals`, `payment_controls`, `costing`, `emergencies` | Standard layout and supported return/reject variants per native transition |
| SCR-04 Start work | `factory_intake`, `factory_create`, `p56_intake` | Match intake panel and each line’s own proof fields |
| SCR-05 Assistant | `design_agents`, `case_uploads`; eight scoped document agents and native reviewed handoffs | Interactive request and follow-up experience; approved provider data policy |
| SCR-06 Overview | `design_overview`; current native factory summaries | Factory floor fidelity and station-level review |
| SCR-07 Project journey | `design_project`, `workspace_overview`, `case`, `project_audience` | Extend recent work and permitted links into source-backed project tabs |
| SCR-08 Document review | `documents`, `case_uploads` | Controlled version, citations and returned state |
| SCR-09 Payroll import | `payroll` | Restricted proof intake, reconciliation table and errors |
| SCR-10 Exceptions | `home?queue=exceptions`, native reconciliation views | Match filters and exception links |
| SCR-11 Registers | `issues`, `changes`, `rfp` | Add project tabs deriving records from each permitted register |
| SCR-12 Report drill-down | `project_audience`, `leadership_report` | Safe drill-down using each source’s reporting grants |
| SCR-13 Setup | `policy`, `policy_scopes`, `factory_configuration`, `factory_responsibility` | Consolidate configuration menus while keeping each scoped validator |
| SCR-14 Verified outputs | `home?queue=verified`, `factory_detail` | Show verified items and current evidence without treating sent as verified |
| SCR-15 Alerts | Existing approval and work inboxes for underlying tasks | Personal read state, preferences and approved delivery |
| SCR-16 Record a response | `factory_detail`, `factory_receipt_recovery_review`, `commercial`, `rfp` | Match proof and recovery panels using native response variants |
| SCR-17 Sign in | `login`, `logout`, Django sessions | Match sign-in and account setup while enforcing redirect safety |
| SCR-18 Restricted payroll matching | `payroll`, `payroll_inspect` | Align HR matching and permission states |
| SCR-19 Milestone completion | `case`, `delivery_progress`; native PMO completion and Finance handoff | Proof and exact version presentation |
| SCR-20 Payments and follow-up | `finance_settlement`, `finance_receipt_followup` | Combine permitted views without conflating invoice, receipt and allocation |
| SCR-21 Staff accounts | `tenant_access`, `case_access`; named-account provisioning and grant controls | Staff inventory and reviewed invite/deactivate behavior |
| SCR-22 Projects | `workspace_overview`, `project_views` | Match list filters and derive open/closed from source |
| SCR-23 Log a bid request | `rfp`, `factory_create` for `rfp-response/v1` | Match request and proof form |
| SCR-24 Assign project manager | `rfp`, `engagement` | Source-backed eligible choices |
| SCR-25 Weekly client update | `factory_detail` for `pmo-weekly-report/v1`; `meetings` reports | Match review, return, and delivery/receipt states |
| SCR-26 Bid response | `rfp`, `factory_detail` for `rfp-response/v1` | Versioned review, edits and line workspace |
| SCR-27 Costing sheet | `costing`, `commercial`, commercial factory line | Use configured approval order and exact costing proof |
| SCR-28 Minutes | `meetings`, `factory_detail` for `pmo-minutes/v1` | Show citations, agreed owners and deadlines through publication |
| SCR-29 Project actions | `meetings`, `work_inbox` | Project action list with native ownership/deadlines |
| SCR-30 Issue detail | `issues`, `factory_detail` for `pmo-issues/v1` | Match owner, due date and verified follow-up states |
| SCR-31 Change request | `changes`, `factory_detail` for `pmo-change/v1` | Align impact through signed closure, with configured approvers |
| SCR-32 Payment reminder | `finance_receipt_followup`, `finance_settlement` | Reminder draft and recorded recipient outcome |
| SCR-33 Retrospective | `closure_preparation`, `delivery` | Retrospective view tied to exact closure evidence |
| SCR-34 Templates | `template_current`, controlled documents | Versioned template list and approved upload flow |
| SCR-35 Clients | Project and engagement records (`workspace_overview`, `engagement`) | Client register and controlled contact updates need separate verification |
| SCR-36 Month-end | `finance_analysis`, `finance_performance`, `finance_forecast` | Finance-scoped month overview with known amounts plus unknown coverage |
| SCR-37 Payroll corrections | `payroll`, `payroll_inspect` | Restricted correction and supersession view |
| SCR-38 Project milestones | `commercial`, `delivery_progress`, `case` | Milestone table with controlled changes and completion state |
| SCR-39 Costing rule | `costing`, `policy`, `policy_scopes` | Exact version, examples and reviewed configuration |
| SCR-40 Bid submission | `rfp`, `factory_detail` for `rfp-response/v1` | Controlled presentation of reviewed submission and actual receipts |
| SCR-41 Engagement | `engagement`, `factory_detail` for `engagement/v1` | Engagement register and case-specific forms |
| SCR-42 Planning | `planning`, `factory_detail` for `planning/v1` | Match readiness and held states |
| SCR-43 Delivery overview | `delivery`, `delivery_progress` | Case-scoped delivery and release progress |
| SCR-44 Release gates | `delivery`, `factory_detail` for `delivery-release/v1` | Match evidence, independent verification and rework |
| SCR-45 Go-live acceptance | `delivery`, `factory_detail` for `delivery-go-live/v1` | Actual signatures and acceptance/decline states |
| SCR-46 Post-release support | `delivery`, `factory_detail` for `delivery-hypercare/v1` | Configured stability criteria and actual observations |
| SCR-47 Archive | `delivery`, `factory_detail` for `delivery-archive/v1` | Controlled inventory and unresolved archive effects |
| SCR-48 Support handover | `delivery`, `factory_detail` for `delivery-handover/v1` | Recipient gaps and verified receipt |
| SCR-49 Closure | `closure_preparation`, `factory_detail` for `delivery-closure/v1` | Independent review and exact Finance confirmation |
| SCR-50 Emergency change | `emergencies`, `authority_recovery`, `factory_detail` for `pmo-emergency/v1` | Preauthorization, refusal, actual work and retrospective receipt |
| SCR-51 Escalation | `escalations`, `factory_detail` for `pmo-escalation/v1` | Decision, draft, reviewed send and recipient evidence |
| SCR-52 Leadership report | `leadership_report`, `factory_detail` for `pmo-leadership-report/v1` | Cited report, review and authorized receipt |
| SCR-53 Management accounts | `finance_analysis`, `finance_performance`, `factory_detail` for `finance-accounts/v1` | Controlled intake through verified aggregate publication |
| SCR-54 Income detail and schedules | `finance_schedules`, `factory_detail` for `finance-schedules/v1` | Match source review, exports and withdrawal |
| SCR-55 Asset schedule | `ppe`, `factory_detail` for `finance-ppe/v1` | Match asset register/date review and verified calculation |
| SCR-56 Cash forecast and actuals | `finance_forecast`, `factory_detail` for `finance-forecast/v1` | Correct coverage and known/unknown figure display |
| SCR-57 Business-unit totals | `bu`, `factory_detail` for `finance-bu/v1` | Authorized roll-up, independent review and proven recipients |
| SCR-58 Ledger source reference | `ledger`, `ledger_agents`, `factory_detail` for `finance-ledger/v1` | Private investigation, duplicate review and verified disposition |
| SCR-59 Restricted payroll run | `payroll`, `hrfinance`, `factory_detail` for `finance-payroll/v1` | Restricted inputs and matching through aggregate-only receipts |

## Delivery order

1. Shared layout, native sign-in, work queue, overview, and eight-agent work entry.
2. Project journey, intake, work item, decisions and proof/recovery. Verify one request through an actual draft, decision and source-backed outcome.
3. Bid, commercial and planning; project records and reviewed communication; release, post-release support and closure.
4. Invoice and receipts, month-end, accounting, forecasting, schedules, assets, ledger and restricted payroll. Verify case and field privacy separately.
5. Finish account, templates and alert operations. Run operator acceptance on isolated Railway, then switch the production entry point when the working journeys pass.
