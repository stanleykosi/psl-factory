# Factory screen consolidation

The 59 screen IDs come from `delivery/screen-coverage.md` at `4689cee`. Desktop, phone and alternate states belong to the same screen. Core permissions, document versions, policy values, approvals, amounts, agent handoffs and receipt checks come from the existing application. The design supplies layout and interaction guidance. A native destination below establishes a place to integrate and on its own does not establish design parity or acceptance.

The first increment uses one server-rendered shell for native screens, including sign-in, onboarding, workspace creation, access setup and password change. My Work, Overview, Project Journey and the Assistant use native data. The Assistant accepts synthetic documents, queues one of eight worker roles and links to the draft, human review and native handoff. The standalone frontend remains a design reference. Its sample data and proposed workflow effects are outside the hosted application.

## Railway browser walkthrough

The named trial account reached the corresponding route or shared workspace for each of the 59 screen IDs. Some visits ended at an expected access hold or an empty state. The interactive runs used separate synthetic workspaces. The remaining board variants and writes are tracked below. See [the test ledger](../../BUILD-TESTS.md) for run IDs and provider boundaries.

| What was exercised | Observed result |
| --- | --- |
| Start Work and alerts | Opened the Planning form from the chooser. Marked an in-app alert as read and observed the updated inbox. |
| Bid, costing and customer outcome | Recorded both reviews and all three ordered approvals. Approved the final draft, queued its controlled synthetic submission, saw the receipt, recorded the customer win and saw the verified Route A intake. |
| Project actions | Completed the action and saw its earlier owner and deadline preserved in history. |
| Report review | Approved one standalone version after checking its audience and citations. Loaded the monthly leadership preparation form and confirmed an unknown report type returns a not-found page. |
| Client billing and company Month-end | Read the synthetic invoice, applied amount and remaining balance in the client view. Opened the scoped company Month-end and read the reviewed monthly figure. |
| Restricted payroll | Opened dedicated input, matching and corrections pages and inspected the upload and matching controls. |
| Other PMO and Finance destinations | Opened native destinations, including separate delivery intake forms, post-release work, ledger, schedules, assets and payroll. Many write, return, recovery and permission states still need interactive acceptance. |

## Functions added by the design

| Design behavior | Native implementation | Open work |
| --- | --- | --- |
| Desktop split Start Work control and mobile chooser, search, select, continue, project-dependent form, start a registered work item | Current same-project grants determine available lines. The drawer loads and submits native forms, keeps returned validation errors in place and retains the request if the outcome is uncertain. Every line validates its sources and repeat request. | Remaining design-specific proof controls, browser acceptance of the drawer and a preferred initial line for users with multiple eligible lines. |
| Tola, Chidi and Zainab can answer questions and continue a conversation | Saved project conversations, queued requests and one selected native record per message. Tola reads authorized project work states, Chidi reads Finance invoice and handoff facts, and Zainab checks for readable HR handoffs. OpenRouter receives bounded synthetic context. | Wider source tools, multiple mentions, deeper answer evaluation and speech. Operational provider access requires owner approval. |
| The assistant suggests another department, or turns an answer into work | Reviewed transfer with access on both sides. Planning, invoice, commercial and bid intake save exact editable draft versions and link the confirmed version to native work. The eight file specialists can use a human-edited summary and questions with their original excerpts. | Add the remaining draft types, more prefilled fields and expected output previews. |
| Queue and overview show who is next, station progress, wait reasons and verified outcomes | Native work, tasks and receipts. Overview groups authorized open work. Project Journey adds access-scoped milestones, documents, invoices, registers and actions. | Consistent evidence and station views across all lines, including detailed filters and live agent progress. |
| The factory keeps eligible work moving in the background | The 26 primary Start Work lines can request background progression as part of native start. Existing work also supports enrolling and pausing. Native gates handle current authority, unchanged waits and uncertain effects. | Connect background preferences to specialised prerequisite intake and verify remaining individual approval, recovery and final effect journeys. |
| Decisions, response and recovery show exact version, allowed choices, proof, recipient and what happened | Invoice, bid, Emergency, accounting, weekly report, leadership report, escalation and go-live use focused pages over the existing commands. Standalone status reports show exact audience, review decisions, returned wording and the reviewed recipient packet. | Exercise returned, declined and uncertain branches by line in the browser, and match the remaining board-specific presentation. |
| Alerts, client register, templates and month-end summarize work across cases | In-app alert read state and preferences. Scoped client contacts and verified billed, applied and owed amounts. Protected template first files and revisions. Company Month-end shows reviewed project figures and confirmed cash-lot coverage independently. | Approved email and WhatsApp delivery, approved use of contacts as recipients and a complete cross-workspace Finance close including receivables coverage. |

The implementation uses required proofs and stoppable exceptions along each workflow, narrow agent tools that return source facts, and persistent request keys at the handoff. These are engineering choices informed by the [Toyota Production System](https://global.toyota/en/company/vision-and-philosophy/production-system/), [Anthropic's tool-design guidance](https://www.anthropic.com/research/writing-tools-for-agents), and [Temporal's durable activity guidance](https://docs.temporal.io/activity-definition). The referenced guidance supplies no PSL policy values.

| Screen | Existing destination or service | Remaining design work |
| --- | --- | --- |
| SCR-01 My work | `home`, `work_inbox`; authorized factory work and recorded assignments | Match filters and verify queue coverage |
| SCR-02 Work item | `factory_detail`; definition-specific views, coordinator and recovery | Align station progress, evidence and actions across definitions |
| SCR-03 Decision | Focused native invoice, bid, Emergency, accounting, weekly report, leadership report, escalation and go-live views, plus `approvals`, `payment_controls` and `costing` | Verify each remaining decision variant, return and authority hold in the browser |
| SCR-04 Start work | Shared drawer or mobile sheet via `factory_intake`, native `factory_create` forms, `p56_intake` | Build remaining line-specific proof and recovery states |
| SCR-05 Assistant | `design_agents`, `assistant_thread`, `assistant_transfer`, `case_uploads`; three conversational roles, one selected record, versioned Planning, invoice, commercial and bid drafts and editable review for eight file specialists | Wider tools, further draft types, multiple mentions, speech and approved provider data scope |
| SCR-06 Overview | `design_overview`; current native factory summaries | Factory floor fidelity and station-level review |
| SCR-07 Project journey | `design_project`, `design_project_tab`, `workspace_overview`, `case`, `project_audience`; current project records by permission | Complete inline proof and decision interactions and board acceptance |
| SCR-08 Document review | `documents`, `case_uploads` and focused standalone status-report audience preview, source citations, return and rework, exact publication and delivery recovery | Coverage for other document types and interactive acceptance |
| SCR-09 Payroll import | `design_payroll_inputs`, bounded JSON and owner-mapped CSV or Excel uploads through the restricted source validator, with original file fingerprint | Confirm operational layout samples and exercise further reconciliation variants |
| SCR-10 Exceptions | `home?queue=exceptions`, native reconciliation views | Match filters and exception links |
| SCR-11 Registers | Project register tab links native `issues`, `changes`, `rfp` | Design filters, dates, dispositions and exact record links |
| SCR-12 Report drill-down | `project_audience`, `leadership_report` | Safe drill-down using each source’s reporting grants |
| SCR-13 Setup | `policy`, `policy_scopes`, `factory_configuration`, `factory_responsibility` | Consolidate configuration menus while keeping each scoped validator |
| SCR-14 Verified outputs | `home?queue=verified`, `factory_detail` | Show verified items and current evidence without treating sent as verified |
| SCR-15 Alerts | Scoped unread bell preview, in-app alert list, personal read state and email/WhatsApp preferences | Browser acceptance of bell interaction and approved channel delivery with receipts |
| SCR-16 Record a response | Dedicated bid, Emergency and go-live response views, plus exact invoice and supported workflow receipt recovery | Remaining source-specific proof fields and browser acceptance of each recovery state |
| SCR-17 Sign in | `login`, `logout`, Django sessions | Match sign-in and account setup while enforcing redirect safety |
| SCR-18 Restricted payroll matching | `design_payroll_matching`, `payroll_inspect` and exact HR-authorised receipts | Match the board's restricted HR and Finance table presentations |
| SCR-19 Milestone completion | `case`, `delivery_progress`; native PMO completion and Finance handoff | Proof and exact version presentation |
| SCR-20 Payments and follow-up | `finance_settlement`, `finance_receipt_followup` | Combine permitted views without conflating invoice, receipt and allocation |
| SCR-21 Staff accounts | Workspace roster, expiring one-use invitation link and renewal, recipient account setup, scoped deactivation and same-role project action reassignment under technical delegation | Approved external invitation delivery and any organization-wide staff policy. Native factory work and claims require their existing handoff before access can be removed |
| SCR-22 Projects | `workspace_overview`, `project_views` | Match list filters and derive open/closed from source |
| SCR-23 Log a bid request | `rfp`, `factory_create` for `rfp-response/v1` | Match request and proof form |
| SCR-24 Assign project manager | `rfp`, `engagement` | Source-backed eligible choices |
| SCR-25 Weekly client update | `factory_detail` for `pmo-weekly-report/v1`; `meetings` reports | Match review, return, and delivery/receipt states |
| SCR-26 Bid response | `rfp`, `factory_detail` for `rfp-response/v1` and versioned Assistant draft with editable cited requirement rows | Remaining in-work response rework and browser acceptance |
| SCR-27 Costing sheet | `costing`, `commercial`, commercial factory line | Use configured approval order and exact costing proof |
| SCR-28 Minutes | `meetings`, `factory_detail` for `pmo-minutes/v1` | Show citations, agreed owners and deadlines through publication |
| SCR-29 Project actions | Project Actions tab and exact action page support native ownership, deadlines, completion and history | Interactive acceptance of reassignment, stale updates, reopening and cancellation for separate operators |
| SCR-30 Issue detail | `issues`, `factory_detail` for `pmo-issues/v1` | Match owner, due date and verified follow-up states |
| SCR-31 Change request | `changes`, `factory_detail` for `pmo-change/v1` | Align impact through signed closure, with configured approvers |
| SCR-32 Payment reminder | Issued invoice facts suggest wording. Finance edits and releases an exact version to an approved billing contact. Synthetic worker commits one receipt. Approved manual channel uses matched delivery evidence and holds repeat releases while the earlier outcome is unresolved | Operational mail adapter, actual destination and cadence approval, and the board's invoice attachment and follow-up automation |
| SCR-33 Retrospective | `closure_preparation`, `delivery` | Retrospective view tied to exact closure evidence |
| SCR-34 Templates | Protected catalogue, private Word/Excel/PDF first project template and revision uploads, and native owner current-use review | Revision notes, interactive file walkthrough and protected Finance definitions through their own domain |
| SCR-35 Clients | Searchable project/client register with versioned contacts and currency-separated native invoiced, applied and owed amounts per approved customer scope | Approved destination use and cross-project customer identity when agreed |
| SCR-36 Month-end | Project and company Month-end display exact reviewed figures, cash receipts and coverage by authorized workspace | A complete cross-workspace close with receivables coverage and reconciliation |
| SCR-37 Payroll corrections | Finance raises an exact match-version concern. The HR-only desk records approval with a corrected export, return or rejection. Finance needs its own receipt before use | Approved masking presentation and new source variants from HR owner examples |
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
