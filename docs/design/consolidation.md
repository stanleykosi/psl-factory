# Factory screen consolidation

The 59 screen IDs come from `delivery/screen-coverage.md` at `4689cee`. Desktop, phone and alternate states belong to the same screen. Core permissions, document versions, policy values, approvals, amounts, agent handoffs and receipt checks come from the existing application. The design supplies layout and interaction guidance. A native destination below establishes a place to integrate and on its own does not establish design parity or acceptance.

The first increment uses one server-rendered shell for native screens, including sign-in, onboarding, workspace creation, access setup and password change. My Work, Overview, Project Journey and the Assistant use native data. The Assistant accepts synthetic documents, queues one of eight worker roles and links to the draft, human review and native handoff. The standalone frontend remains a design reference. Its sample data and proposed workflow effects are outside the hosted application.

The newer GitHub design expands the registered screen IDs into [262 distinct non-concept states](screen-state-inventory.csv). The [current state acceptance ledger](screen-state-acceptance.md) records actual browser outcomes for the Assistant, reports, minutes, project tabs, Money, delegation, release returns and Finance review, including cash forecasts. Remaining states still need their own acceptance.

The isolated Railway preview has 163 directly observed states. Of those, 162 still list follow-up checks, and 99 await first observation. The latest pass added portal receipt verification, comparison of exact reviewed and awarded prices, assigned-manager draft review and reminder, selected minutes through verified internal release, and workspace rules and registers. The [state ledger](screen-state-acceptance.md) lists open variants, including live provider receipts, customer communications, and independent role and device checks.

GitHub `main` advanced to `4e720682` during this pass. Its changes add the F-23 minutes mock and reviewed F-25 project tab design exceptions. The inventory files in `design/canvas` have no changes against the previous main tip. The native minutes decision screen showed an uncertain delivery and sent the operator to the original receipt lookup. The updated design still calls for common checked suggestions, in-row editing and a single reviewed confirmation. Mock fixture behavior supplies interaction detail. Native authority and real publication remain governed by the application.

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
| Payroll import and HR correction | Uploaded a mapped CSV, saw the new source become current and approved the exact corrected HR export. The HR page showed the recipient receipt required for Finance use. |
| Payment reminder | Saved, checked and attached a private test invoice PDF. Scheduled the release, confirmed no early receipt, and read the verified test mailbox receipt after the due time. A separate schedule was cancelled and confirmed undelivered. |
| Weekly approval and recovery | Approved one exact weekly report and verified its receipt. Verified a second report against its original receipt following the worker's recovery of a simulated lost response. |
| Release and go-live | Approved Planning exit. Reassessed changed release evidence, recorded the replacement deployment request and verified its three approvals. The worker verified successor readiness. Reviewed a go-live report and used a separate recovery case to recover the original receipt and record and verify both signatures. |
| Closure | Restarted stopped work, approved the fresh report, queued continuation and verified the recorded native closure. |
| Escalation and leadership | Approved the escalation request and exact document, then verified delivery. Approved a leadership report and verified its delivery. Separate cases recovered their original receipts. |
| Management accounts and close | Claimed and approved the exact accounting output and verified its recipient receipt. Reconciled a separate original report delivery. Captured the current date's receivables and opened the reviewed October figure in the company close. |
| Emergency actual evidence | Recorded the implementation through the response screen and checked that the native outcome preserved the missing preauthorization exception. |
| Staff lifecycle | Created and renewed a one-use synthetic invitation, opened the recipient setup page, removed a seeded account's access with a selected successor and saw the inactive roster entry after reload. Account activation and historical reassignment were also verified by PostgreSQL HTTP tests. |
| Other PMO and Finance destinations | Opened native destinations, including separate delivery intake forms, post-release work, ledger, schedules, assets and payroll. Many write, return, recovery and permission states still need interactive acceptance. |

## Functions added by the design

| Design behavior | Native implementation | Open work |
| --- | --- | --- |
| Desktop split Start Work control and mobile chooser, search, select, continue, project-dependent form, start a registered work item | Current same-project grants determine available lines. The drawer loads and submits native forms, keeps returned validation errors in place and retains the request if the outcome is uncertain. Every line validates its sources and repeat request. | Remaining design-specific proof controls, browser acceptance of the drawer and a preferred initial line for users with multiple eligible lines. |
| Tola, Chidi and Zainab can answer questions and continue a conversation | Saved project conversations, queued requests and up to five selected native records per message. Tola reads authorized project work, meeting and milestone facts, Chidi reads Finance invoice and handoff facts, and Zainab checks for readable HR handoffs. The worker rechecks current records before saving the answer and the page hides stale answers. OpenRouter receives bounded synthetic context. | Wider source tools, more draft types, deeper answer evaluation and speech. Operational provider access requires owner approval. |
| The assistant suggests another department, or turns an answer into work | Reviewed transfer with access on both sides. Planning, invoice, commercial and bid intake save exact editable draft versions and link the confirmed version to native work. The eight file specialists can use a human-edited summary and questions with their original excerpts. | Add the remaining draft types, more prefilled fields and expected output previews. |
| Queue and overview show who is next, station progress, wait reasons and verified outcomes | Native work, tasks and receipts. Overview groups authorized open work. Project Journey adds access-scoped milestones, documents, invoices, registers and actions. | Consistent evidence and station views across all lines, including detailed filters and live agent progress. |
| The factory keeps eligible work moving in the background | The 26 primary Start Work lines can request background progression as part of native start. Existing work also supports enrolling and pausing. Native gates handle current authority, unchanged waits and uncertain effects. | Connect background preferences to specialised prerequisite intake and verify remaining individual approval, recovery and final effect journeys. |
| Decisions, response and recovery show exact version, allowed choices, proof, recipient and what happened | Invoice, bid, Emergency, accounting, weekly report, leadership report, escalation, release, go-live and closure use focused pages over the existing commands. Standalone status reports show exact audience, review decisions, returned wording and the reviewed recipient packet. | Exercise the remaining returned, declined and uncertain branches by line in the browser, and match the remaining board-specific presentation. |
| Alerts, client register, templates and month-end summarize work across cases | In-app alert read state and preferences. Scoped billing contacts and verified amounts. Protected template files and revisions. Company Month-end shows reviewed figures, verified cash, captured receivables and reconciliation exceptions with exact workspace coverage. | Approved email and WhatsApp delivery, approved use of contacts as recipients, and owner decisions for cross-workspace consolidation and sign-off. |

The implementation uses required proofs and stoppable exceptions along each workflow, narrow agent tools that return source facts, and persistent request keys at the handoff. These are engineering choices informed by the [Toyota Production System](https://global.toyota/en/company/vision-and-philosophy/production-system/), [Anthropic's tool-design guidance](https://www.anthropic.com/research/writing-tools-for-agents), and [Temporal's durable activity guidance](https://docs.temporal.io/activity-definition). The referenced guidance supplies no PSL policy values.

| Screen | Existing destination or service | Remaining design work |
| --- | --- | --- |
| SCR-01 My work | `home`, `work_inbox`; authorized factory work and recorded assignments | Match filters and verify queue coverage |
| SCR-02 Work item | `factory_detail`; definition-specific views, coordinator and recovery | Align station progress, evidence and actions across definitions |
| SCR-03 Decision | Focused native invoice, bid, Emergency, accounting, weekly report, leadership report, escalation, release, go-live and closure views, plus `approvals`, `payment_controls` and `costing` | Verify remaining return and authority-hold variants in the browser |
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
| SCR-15 Alerts | Scoped unread bell preview, in-app alert history, personal read state, opt-in email and WhatsApp alerts, and exact delivery receipts | Operational relay and approved channel destinations. Both sample channel receipts were verified in Codex. |
| SCR-16 Record a response | Dedicated bid, Emergency and go-live response views, plus exact invoice and supported workflow receipt recovery | Remaining source-specific proof fields and browser acceptance of each recovery state |
| SCR-17 Sign in | Native sign-in, sessions and one-use account recovery with delivery receipt and expiry | Fresh sign-in and account setup variants in the browser, and operational recovery email |
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
| SCR-32 Payment reminder | Issued invoice facts suggest wording. Finance saves an exact PDF attachment, can release or schedule under configured timing rules, and can cancel before delivery. Test mailbox stores the original message and attachment with verified receipt. Approved manual channel uses matched delivery evidence. | Operational mail adapter, actual destination and cadence approval, and recurring drafts based on recorded customer responses |
| SCR-33 Retrospective | `closure_preparation`, `delivery` | Retrospective view tied to exact closure evidence |
| SCR-34 Templates | Protected catalogue, private Word/Excel/PDF first project template and revision uploads, and native owner current-use review | Revision notes, interactive file walkthrough and protected Finance definitions through their own domain |
| SCR-35 Clients | Searchable project/client register with versioned contacts and currency-separated native invoiced, applied and owed amounts per approved customer scope | Approved destination use and cross-project customer identity when agreed |
| SCR-36 Month-end | Project and company Month-end display reviewed figures, verified cash, immutable dated receivables, unallocated cash and reconciliation exceptions. Coverage and links use authorised workspaces and the native area grants. | Approved close scope, period sign-off and group consolidation rules, plus operational data validation |
| SCR-37 Payroll corrections | Finance raises an exact match-version concern. The HR-only desk records approval with a corrected export, return or rejection. Finance needs its own receipt before use | Approved masking presentation and new source variants from HR owner examples |
| SCR-38 Project milestones | `commercial`, `delivery_progress`, `case` | Milestone table with controlled changes and completion state |
| SCR-39 Costing rule | `costing`, `policy`, `policy_scopes` | Exact version, examples and reviewed configuration |
| SCR-40 Bid submission | `rfp`, `factory_detail` for `rfp-response/v1` | Controlled presentation of reviewed submission and actual receipts |
| SCR-41 Engagement | `engagement`, `factory_detail` for `engagement/v1` | Engagement register and case-specific forms |
| SCR-42 Planning | `planning`, `factory_detail` for `planning/v1` | Match readiness and held states |
| SCR-43 Delivery overview | `delivery`, `delivery_progress` | Case-scoped delivery and release progress |
| SCR-44 Release gates | `delivery`, focused Planning exit decision and changed-evidence recovery for `delivery-release/v1`, with owning-team approval links and worker verification | Operational approvers, authentic source receipts and remaining device variants |
| SCR-45 Go-live acceptance | Exact report review, original delivery receipt recovery and a separate human sign-off record for the distinct PM and Client signatures | Operational signature source and any additional supported response variants |
| SCR-46 Post-release support | `delivery`, `factory_detail` for `delivery-hypercare/v1` | Configured stability criteria and actual observations |
| SCR-47 Archive | `delivery`, `factory_detail` for `delivery-archive/v1` | Controlled inventory and unresolved archive effects |
| SCR-48 Support handover | `delivery`, `factory_detail` for `delivery-handover/v1` | Recipient gaps and verified receipt |
| SCR-49 Closure | `closure_preparation`, exact Finance confirmation, missing-evidence and returned views, fresh review, retained decisions and durable worker finalisation | Operational Head of PMO and finaliser authority, and separate-reviewer and device acceptance |
| SCR-50 Emergency change | `emergencies`, `authority_recovery`, `factory_detail` for `pmo-emergency/v1` | Preauthorization, refusal, actual work and retrospective receipt |
| SCR-51 Escalation | `escalations`, exact request decision, document review, controlled delivery and receipt recovery for `pmo-escalation/v1` | Operational clocks, recipients and remaining rework variants |
| SCR-52 Leadership report | `leadership_report`, selected source citations, exact review, delivery and original receipt lookup | Actual audience, authority and calendar rules |
| SCR-53 Management accounts | `finance_analysis`, `finance_performance`, exact report claim, Finance decision, verified recipient publication and original receipt lookup for `finance-accounts/v1` | Real input and accounting rules, receipt recipients and remaining source-rework variants |
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
