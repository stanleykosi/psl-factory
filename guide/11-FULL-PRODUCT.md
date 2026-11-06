# PSL AI Agent Operations Factory — product blueprint

Build PSL Product Studio as PSL’s AI agent operations factory. Incoming requests, projects, transactions and service issues move through connected production stations to verified business outputs. Agents do useful scoped work; people make accountable decisions; deterministic services enforce policy, calculations, permissions and effects. This is the user-confirmed product direction of 30 October 2026, replacing workbench-first framing. It is not a claim that the full factory is implemented.

The13 families below are connected production capabilities. Preserve all122 process IDs, source ownership and business boundaries. The agreed first release is63 PMO +45 Finance IDs (108); all14 BaaS IDs are retained but deferred, including BaaS entries in shared families. Scope is derived from each original department/ID, not just a family or title. The matching 1 November component design and task request are retained under docs/design/2026-11-01/. Console/projection design is engineering interpretation; source definitions and rule references remain business evidence.

## Factory operating model

Every increment identifies intake and intended output, case/project/contract/service scope, production stations and dependencies, agent tasks and typed tools, required human decisions, downstream handoffs and verification/recovery evidence. Correlate existing records rather than duplicating domain state. Preserve branching, parallel work, rework, human waits and source-defined gates instead of forcing every process into one pipeline.

Agent work is operational execution with a scoped assignment, expected result, persisted attempt, cited output and next action. O01 coordinates permitted tasks; reusable A01–A08 capabilities perform them through typed domain tools. Agents carry permitted work forward without a human prompt at every step and surface source-required decisions and exceptions for accountable people. Domain services validate results and execute permitted transitions. Required human acceptance, business outcomes and effect receipts remain separate from agent/job completion. Do not introduce an approval step into a process that does not require one.

## Primary operating experience

Lead with incoming work, work in progress, agent execution, decisions waiting on people, exceptions and verified outputs. Use layout and clear business language to show the current station, responsible actor, next step and why work is waiting. Work moves across PMO, Finance, BaaS and shared evidence rather than disappearing into disconnected department menus.

Provide overall operation, production-line, work-item, agent-execution, decision and exception-recovery views. Domain workspaces, documents, configuration and diagnostics support them. Keep technical identifiers and schemas secondary; keep real business holds visible.

Counts, ageing, throughput and bottleneck views derive from current authorised source records and explicit event/time definitions. State coverage and as-of time; missing data is unknown. Do not invent priorities, deadlines, service targets, capacity limits or utilisation figures. Reading a queue or metric grants no action authority.

Outputs are complete only with the source-required validation, review/acceptance and receipt evidence for that operation. Dispatch, generated text or an agent’s success claim cannot close debt, approve release or prove downstream acceptance. Exceptions retain ownership, evidence, uncertainty and a controlled correction/recovery path.

The operating descriptions below are proposed implementation requirements, not claims that those agent paths already work. Apply the per-ID A01–A08/O01 assignments and human-reserved decisions in contracts/process-map.json. Each family may contribute several stations to a work item; cross-family dependencies and receipts connect them. Actual completion remains tracked per process in contracts/implementation-coverage.json.


## AF01: baas.support
Station detail: Support inbox, case detail, triage/merge review, timeline and response metrics.

Production flow: Channel intake → identity/evidence triage → investigation/internal task → owned resolution/reopen and summary.

Records: Case/channel/transaction links, response timestamps, resolution evidence.

Adapters: BaaS support sources; communications.

Business boundary: No corrective credit implied by support status.

Operational work: agents triage incoming evidence, investigate the issue, prepare responses and coordinate specialist tasks. Show the current owner, response work, specialist wait and next action. Resolution/reopen follows the source-defined controls; drafting or sending a response is not proof of resolution. Link any corrective-finance request to its independently owned workflow and result.

## AF02: baas.reconciliation
Station detail: Reconciliation workbench, discrepancy detail, corrective-request and receipt tracker.

Production flow: Compare settlement evidence → investigate → Engineering-owned corrective request → reconcile result.

Records: Settlement/reference evidence, request/queue identifiers and effect receipt.

Adapters: Reconciliation/Engineering queue adapters.

Business boundary: Business queue/funds authority is separate from infrastructure jobs.

Operational work: agents compare settlement evidence, investigate discrepancies and prepare Engineering-owned corrective requests. Follow the request through acknowledgement and result verification, preserving unresolved or uncertain outcomes. A queued request or infrastructure job cannot prove a financial correction.

## AF03: baas.partner_operations
Station detail: Partner agreements/renewal calendar, onboarding board, ageing and usage dashboard.

Production flow: Agreement/onboarding intake → configured stages/deadlines → follow-up → usage/report handoff.

Records: Partner agreement, onboarding history, usage period/batch.

Adapters: Partner/customer/usage sources; communications.

Business boundary: Unknown stage/calendar policy is explicit.

Operational work: agents assemble onboarding evidence, identify configured renewal/ageing follow-ups and prepare usage reports. Show the partner's next stage, known owner and outstanding evidence. Verify usage handoff to Finance separately from onboarding or renewal completion; missing calendar rules remain specific dependencies.

## AF04: finance.management_accounts
Station detail: Import/validation wizard, mapping editor, rule lineage, reconciliation and report workbench.

Production flow: Import TB/source → map/validate → deterministic schedules/reports → investigate differences → review output.

Records: Import batch, account map, formula lineage, management report versions.

Adapters: Accounting/QuickBooks, controlled spreadsheet inputs.

Business boundary: Actual owner oracles validate financial rules.

Operational work: agents examine imported sources, investigate mapping or reconciliation differences and explain deterministic report results. Show incomplete inputs, unresolved differences and review work. Financial schedules and totals come from validated rule implementations; trace the reviewed output to exact imports, mappings, formula versions and source coverage.

## AF05: finance.bu_performance
Station detail: BU mappings/allocation configuration, payroll-input validation, comparison and performance views.

Production flow: Import permitted inputs → effective attribution/allocation → tie out company/BU → YTD/performance/report.

Records: BU/staff references, allocation pool/rule, period/rounding and report lineage.

Adapters: Finance/HR-read inputs; accounting exports.

Business boundary: No guessed payroll ratios or silent historical restatement.

Operational work: agents investigate permitted HR/Finance matches, attribution gaps and company-to-BU differences, then explain the configured calculations. Keep restricted inputs and reviews within their authorised scope. Follow allocation exceptions and report preparation to the required review/output evidence without exposing private payroll through shared queues or metrics.

## AF06: finance.billing
Station detail: Client/service register, usage batch, price-rule editor, invoice queue, receivables and receipt/allocation views.

Production flow: Usage/contract stage → approved pricing/evidence → invoice preparation/issuance/delivery → receipts/allocation/correction.

Records: Service/contract/schedule/stage, invoice/obligation, receipt/cash lot, allocation/adjustment.

Adapters: Existing billing/Power Automate; accounting; communications.

Business boundary: Generation, posting, sending and cash settlement stay separate.

Operational work: agents gather usage/contract evidence, investigate preparation holds and support invoice, receipt and correction follow-up through permitted tools. Show invoice preparation, required review, issuance, delivery, receipt verification and allocation as separate work and outcomes. Verify each effect against its own receipt and current authority; agent/job success alone does not prove a settled invoice or verified cash.

## AF07: finance.forecast
Station detail: Forecast inputs, horizon/opening balance, scenario/actual comparison and audience reporting.

Production flow: Select inflow/outflow evidence → deterministic forecast → management review → actual update/roll-forward.

Records: Forecast version, included sources/coverage, opening balance and projection.

Adapters: Accounting/receivable inputs; reporting.

Business boundary: Partial source coverage cannot be labelled complete cash forecast.

Operational work: agents identify missing forecast inputs, investigate variances and draft explanations of deterministic projections. Track preparation, management review, permitted publication and actual roll-forward separately. Carry source coverage, opening balance and version references into the output; omitted inflows/outflows remain visible rather than becoming zero.

## AF08: handoffs
Station detail: Cross-team inbox, milestone/Finance view, evidence packet and delivery/reconciliation detail.

Production flow: Signed baseline/milestone/HR evidence → audience projection → durable handoff → receipt/next owned task.

Records: Handoff correlation, source/evidence versions, Finance projection and receipt.

Adapters: PMO/Finance/HR; evidence and communications.

Business boundary: PMO completes; Finance invoices; HR scope remains read-limited.

Operational work: agents assemble the permitted evidence projection, track downstream work and investigate stalled handoffs. Correlate sender intent, source versions, recipient access, delivery receipt and any required acceptance or next task. Delivery does not approve the recipient's business action; keep PMO, Finance and HR responsibilities distinct.

## AF09: pmo.delivery
Station detail: Engagement/project workspace, requirements/plan, phase-gate/evidence board, UAT/release/closure views.

Production flow: Engagement → pre-signature planning → delivery → owned external gate evidence → release/closure handoffs.

Records: Project/plan, estimate/signoff evidence, milestone and closure record.

Adapters: Incumbent PMO; Engineering/QA/Product/Security/GLPI references.

Business boundary: Do not replace external approval owners or invent paid-invoice closure gate.

Operational work: agents prepare plans and evidence packets, coordinate permitted tasks and follow missing estimates or external gate evidence. Show current delivery stage, dependencies, human decisions and readiness exceptions. PMO records completion; Engineering/QA/Product/Security/client gates retain their source owners. Connect release, hypercare and closure to their actual evidence and downstream support/Finance work.

## AF10: pmo.commercial
Station detail: Costing/SOW editor, decision inbox, revision comparison, RFP workspace.

Production flow: Requirements/estimates → costing chain and document review → client baseline/revisions; RFP to project/archive.

Records: Cost/SOW versions, decisions, signed artifacts and RFP response.

Adapters: Document/evidence/signature references; communications.

Business boundary: Plan/cost before signature; exact prescribed costing order.

Operational work: agents interpret requirements/estimates, prepare costing/SOW or RFP drafts and coordinate revision follow-up. Keep costing decisions, document-quality review, client response and signed-baseline evidence distinct. Approved amounts use configured deterministic rules, not agent-invented formulas. Carry each accepted revision or won opportunity into its appropriate delivery/handoff path with the exact accepted evidence.

## AF11: documents.reporting
Station detail: Template library, version/review detail, publication queue, shared project/report/minutes views.

Production flow: Template/evidence → draft → quality review → permitted audience projection → publication receipt.

Records: Template/document/review/report/minutes and audience versions.

Adapters: Document repositories; communications.

Business boundary: Current reviewed artifact and audience bound to publication.

Operational work: agents prepare cited drafts, minutes and audience-specific reports, then route required review and correction work. Track draft, current reviewed version, audience permission, publication intent and delivery receipt separately. Recurring preparation does not bypass review or authorise publication to a new audience.

## AF12: pmo.issues_changes
Station detail: Issue board, risk/incident links, change/emergency workspace and escalation queue.

Production flow: Intake/classification → impact assessment → conditional decisions → implementation evidence → validation/closure.

Records: Issue/change history, external incident/risk refs, decision/timer/release evidence.

Adapters: Engineering/Security/GLPI; communications.

Business boundary: Emergency/Standard ambiguity is a configured rule, not inferred waiver.

Operational work: agents investigate source evidence, draft impact assessments and coordinate configured follow-ups or escalation work. Show accountable owners, pending decisions, implementation/testing evidence and closure work. Preserve Emergency preauthorisation, retrospective and scope/cost follow-up requirements where applicable; urgency or an agent classification cannot waive a required control.

## AF13: evidence.validation
Station detail: Evidence-gap/decision workbench, SOP/calculator reference library and owner validation/test board.

Production flow: Collect/compare process evidence → validate rules/examples → record accepted policy/configuration/test evidence.

Records: Source version, gap/decision, owner example and validation record.

Adapters: Controlled document/evidence imports.

Business boundary: Discovery is implemented workflow, not an item to mark automated away.

Operational work: agents collect and compare process evidence, identify missing procedures/calculator examples and assemble owner-validation packets. Track requested evidence, validation findings, responsible owner and exact acceptance versions. An accepted example or configuration document is not proof that an integration ran, a recovery succeeded or every process is complete.

## Cross-cutting product surfaces
The factory console connects production queues, individual work progress, agent execution, human decisions, exceptions, verified outputs and cross-team handoffs. Search, evidence/documents, identity/access, policy configuration, audit, integration health, provider evaluation and recovery/export/backup diagnostics support the operation. Distinguish business waits, missing rules, agent/provider failures and uncertain effects; show the correct next action without granting authority through the view.

## Product completion
Every original process has a concrete implemented disposition and tests connected to intake, agent/human execution, exception handling and verified outputs. Demonstrate actual cross-family flow through services and receipts; a directory of records or polished department forms is insufficient. Known human-owned/external activities are represented by the correct evidence, decision or handoff UX, not secretly replaced by automation. All missing business decisions plug into built configuration infrastructure. Structural completion, owner-policy completeness and operational validation are reported separately; none may be used to disguise unfinished engineering.
