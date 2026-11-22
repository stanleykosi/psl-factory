# Department handoff acceptance on Railway

Railway verified these processes on isolated PostgreSQL with synthetic records. The grouped checks simulated model replies and file storage. The department services, specialist queues, permission checks, native approvals and receipt records ran in the application.

PMO checks ran on `44b5d9aa-0e71-478e-a4ad-dedf57b72ab6`, Finance close and allocation on `ca2df73e-d7d7-42cd-adcd-3d7f5ae71e61`, and Finance operations on `44b5d9aa-0e71-478e-a4ad-dedf57b72ab6`.

Each internal receiving command checks the exact specialist handoff. P05 records the recipient's explicit acknowledgment. For P19 the customer response can arrive independently and PMO consumes the findings during signed-baseline adoption.

| Process | Triggering record | Specialist team | Verified receiving record |
| --- | --- | --- | --- |
| P01 · Confirm required approvals before an SOW is shared | pmo.CommercialDocumentBinding | A07 Control evidence and release preflight, A02 Evidence and document analysis, A04 Planning and workflow coordination | documents.publicationreceipt |
| P02 · Automate routing and visibility without taking over other teams’ approvals | pmo.ApprovalRequest | A04 Planning and workflow coordination, A07 Control evidence and release preflight | pmo.approvalroutereceipt |
| P04 · Maintain PMO tracking and prepare periodic reports | pmo.MinutesReportBinding | A06 Management insight and drafting, A04 Planning and workflow coordination, A02 Evidence and document analysis | documents.publicationreceipt |
| P05 · Provide a permissioned shared project view for PMO, management and engineering | policy.PolicyState | A02 Evidence and document analysis, A06 Management insight and drafting, A07 Control evidence and release preflight | core.audit |
| P08 · Control cost-changing revisions and proposed pricing-model updates | pmo.CommercialRevision | A03 Exception investigation, A05 Finance evidence and analysis, A07 Control evidence and release preflight | pmo.commercialdocumentbinding |
| P09 · Route SOW costing for Project Manager → Head of PMO → CEO approval | pmo.CommercialRevision | A04 Planning and workflow coordination, A07 Control evidence and release preflight | pmo.commercialdocumentbinding |
| P10 · Select the applicable SOW or other controlled document template | documents.TemplateScope | A02 Evidence and document analysis, A07 Control evidence and release preflight | documents.version |
| P11 · Standardise templates and maintain governed repository references | documents.Template | A02 Evidence and document analysis, A04 Planning and workflow coordination | documents.templateclaim, documents.templateresolution |
| P12 · Share signed costs and milestones, notify completion and confirm closure handoffs | pmo.Milestone | A04 Planning and workflow coordination, A02 Evidence and document analysis, A07 Control evidence and release preflight | finance.handoff |
| P13 · Maintain PMO SOP and document approval points; v1.1 received | documents.DiscoverySource | A02 Evidence and document analysis, A03 Exception investigation, A08 Evaluation and quality review | documents.validationreview |
| P15 · Validate documented workflows and automation with process users | documents.ValidationPackage | A08 Evaluation and quality review, A02 Evidence and document analysis, A04 Planning and workflow coordination | documents.validationreview |
| P17 · Define requirements and map required delivery stakeholders | core.Evidence | A02 Evidence and document analysis, A04 Planning and workflow coordination | core.evidence |
| P18 · Collect Engineering and Security effort/timeline estimates | core.Evidence | A04 Planning and workflow coordination, A02 Evidence and document analysis, A05 Finance evidence and analysis | core.evidence |
| P19 · Submit approved client documents and manage feedback/revisions | documents.PublicationReceipt | A02 Evidence and document analysis, A04 Planning and workflow coordination, A07 Control evidence and release preflight | pmo.clientresponse |
| P20 · Obtain client-signed SOW and PRD and hand the signed baseline to Finance | pmo.CommercialSignaturePacket | A07 Control evidence and release preflight, A02 Evidence and document analysis, A04 Planning and workflow coordination | finance.signedbaselineintake |
| P21 · Run both PRD alignment sessions and resolve scope/dependency gaps | core.Evidence | A02 Evidence and document analysis, A04 Planning and workflow coordination, A06 Management insight and drafting | core.evidence |
| P22 · Confirm referenced UI design sign-off before UI development | pmo.DeliverySource | A07 Control evidence and release preflight, A02 Evidence and document analysis | pmo.deliveryrecord |
| P23 · Confirm referenced technical-design sign-off before development | pmo.DeliverySource | A07 Control evidence and release preflight, A02 Evidence and document analysis | pmo.deliveryrecord |
| P24 · Confirm test-strategy and UAT-approach sign-offs | pmo.DeliverySource | A07 Control evidence and release preflight, A04 Planning and workflow coordination | pmo.deliveryrecord |
| P25 · Approve scope and effort/timeline estimate baselines | core.Evidence | A07 Control evidence and release preflight, A03 Exception investigation, A04 Planning and workflow coordination | core.evidence |
| P27 · Hold delivery kick-off and document agreed expectations | pmo.MeetingVersion | A04 Planning and workflow coordination, A06 Management insight and drafting | pmo.deliveryrecord |
| P29 · Confirm QA exit with no critical defects before Product UAT | pmo.GateRecord | A07 Control evidence and release preflight, A03 Exception investigation | pmo.deliveryrecord |
| P30 · Validate UAT and collect the prescribed UAT approvals | pmo.GateRecord | A07 Control evidence and release preflight, A02 Evidence and document analysis, A04 Planning and workflow coordination | pmo.deliveryrecord |
| P31 · Confirm Engineering pre-production Go / No-Go before GLPI request | pmo.GateRecord | A07 Control evidence and release preflight, A03 Exception investigation | pmo.deliveryrecord |
| P38 · Conduct retrospective and capture improvement actions | pmo.MeetingVersion | A06 Management insight and drafting, A03 Exception investigation, A04 Planning and workflow coordination | pmo.deliverydocumentbinding |
| P45 · Receive and log every RFP and assign a PM | pmo.RFPIntake | A01 Intake and case triage, A04 Planning and workflow coordination | pmo.rfpassignment |
| P51 · Reference the Security-owned risk register without creating a PMO risk master | pmo.IssueReferenceObservation | A02 Evidence and document analysis, A03 Exception investigation, A07 Control evidence and release preflight | pmo.issuereferencerevision |
| P52 · Maintain versioned, owned and structurally compliant project documents | documents.Version | A02 Evidence and document analysis, A06 Management insight and drafting, A08 Evaluation and quality review | documents.publicationreceipt |
| P53 · Review and quality-gate every external document and sanitize external issue reports | documents.Version | A07 Control evidence and release preflight, A02 Evidence and document analysis, A08 Evaluation and quality review | documents.publicationreceipt |
| P54 · Track production issue visibility, severity, resolution timing and critical root cause | pmo.IssueState | A03 Exception investigation, A06 Management insight and drafting, A07 Control evidence and release preflight | pmo.issuestate |
| P55 · Reference Engineering incident management and link required production changes | pmo.IssueReferenceObservation | A03 Exception investigation, A04 Planning and workflow coordination, A07 Control evidence and release preflight | pmo.issuereferencerevision |
| P56 · Log each change request and classify Standard, Normal or Emergency | pmo.ChangeVersion | A01 Intake and case triage, A03 Exception investigation, A04 Planning and workflow coordination | pmo.changeassessment |
| P58 · Obtain change approvals, conditional cost approval and timeline agreement | pmo.ChangeVersion | A07 Control evidence and release preflight, A04 Planning and workflow coordination, A03 Exception investigation | pmo.changeauthorization |
| P63 · Enforce documented phase entry/exit gates and traceable decisions | pmo.DeliveryRecord | A04 Planning and workflow coordination, A07 Control evidence and release preflight, A02 Evidence and document analysis | pmo.deliveryrecord |
| F02 · Trial-balance extraction from QuickBooks | finance.FinanceSource | A01 Intake and case triage, A05 Finance evidence and analysis, A03 Exception investigation | finance.financerun |
| F04 · Trial-balance adjustments movement and total check | finance.FinanceAdjustment | A05 Finance evidence and analysis, A03 Exception investigation, A07 Control evidence and release preflight | finance.financerun |
| F05 · Notes aggregation for income cost and expenses | finance.FinanceRun | A05 Finance evidence and analysis, A03 Exception investigation | finance.financeperiod |
| F06 · Cash and other-asset note aggregation and scaling | finance.FinanceRun | A05 Finance evidence and analysis, A03 Exception investigation | finance.financeperiod |
| F08 · Liability note aggregation and sign reversal | finance.FinanceRun | A05 Finance evidence and analysis, A03 Exception investigation | finance.financeperiod |
| F10 · Income-statement actuals and comparison presentation | finance.FinancePerformance | A05 Finance evidence and analysis, A06 Management insight and drafting | documents.publicationreceipt |
| F11 · Manual management-account budget import and monthly update | finance.FinanceBudget | A01 Intake and case triage, A05 Finance evidence and analysis, A07 Control evidence and release preflight | finance.financeperformance |
| F14 · BU revenue classification from management accounts | finance.FinanceRun | A05 Finance evidence and analysis, A03 Exception investigation | finance.financeperiod |
| F15 · BU cost-of-sales and direct cost attribution | finance.FinanceRun | A05 Finance evidence and analysis, A03 Exception investigation | finance.financeperiod |
| F19 · Allocate other staff costs by headcount | finance.FinanceRun | A05 Finance evidence and analysis, A03 Exception investigation | finance.financeperiod |
| F20 · Standard shared-service staff allocation | finance.BUWork | A05 Finance evidence and analysis, A03 Exception investigation | finance.bureceipt |
| F24 · BU year-to-date aggregation | finance.FinancePerformance | A05 Finance evidence and analysis, A03 Exception investigation | documents.publicationreceipt |
| F25 · BU year-to-date budget linkage and prorating | finance.FinancePerformance | A05 Finance evidence and analysis, A03 Exception investigation | documents.publicationreceipt |
| F26 · BU performance metrics and bar-chart presentation | finance.FinancePerformance | A06 Management insight and drafting, A05 Finance evidence and analysis, A08 Evaluation and quality review | documents.publicationreceipt |
| F27 · Business-unit reporting scope change and historical rework | finance.FinanceRestatement | A05 Finance evidence and analysis, A04 Planning and workflow coordination, A07 Control evidence and release preflight | finance.financeperiod |
| F28 · BaaS monthly client-usage report handoff | finance.UsageIntakeSource | A01 Intake and case triage, A05 Finance evidence and analysis, A04 Planning and workflow coordination | finance.usageintakeacceptance |
| F31 · IT service client-list and mixed billing cadence | finance.CoveragePreparationRequest | A02 Evidence and document analysis, A05 Finance evidence and analysis, A04 Planning and workflow coordination | finance.coveragepreparationreceipt |
| F32 · Receivable paid/unpaid tracking and IT collection issues | finance.CashReceipt | A03 Exception investigation, A05 Finance evidence and analysis, A04 Planning and workflow coordination | finance.receivablesnapshot |
| F33 · Manual project-progress handoff for revenue recognition | finance.ProgressPacket | A02 Evidence and document analysis, A04 Planning and workflow coordination, A07 Control evidence and release preflight | finance.recognitionrecord |
| F34 · PMO finance-layer integration and milestone notifications | pmo.Milestone | A04 Planning and workflow coordination, A02 Evidence and document analysis, A07 Control evidence and release preflight | finance.handoff |
| F35 · HR-to-finance information interface and proposed HR integration | finance.HRDisclosure | A02 Evidence and document analysis, A07 Control evidence and release preflight, A04 Planning and workflow coordination | finance.hrhandoffrecord |
| F36 · Select expected cash inflows from receivables and other sources | finance.ForecastScenario | A05 Finance evidence and analysis, A03 Exception investigation, A06 Management insight and drafting | finance.forecastrun |
| F37 · Estimate recurring and newly reported cash outflows | finance.ForecastScenario | A05 Finance evidence and analysis, A03 Exception investigation, A04 Planning and workflow coordination | finance.forecastrun |
| F38 · Establish cash opening balance and near-term obligation view | finance.ForecastScenario | A05 Finance evidence and analysis, A03 Exception investigation, A07 Control evidence and release preflight | finance.forecastrun |
| F40 · Management cash prioritization and client follow-up decisions | finance.ForecastReview | A06 Management insight and drafting, A05 Finance evidence and analysis, A04 Planning and workflow coordination | pmo.actionstate |
| F41 · Update forecast after actual receipts and payments | finance.ForecastMatch | A03 Exception investigation, A05 Finance evidence and analysis | finance.forecastrun |
| F42 · Roll unresolved cash items to next month and adjust horizon | finance.ForecastScenario | A05 Finance evidence and analysis, A03 Exception investigation, A04 Planning and workflow coordination | finance.forecastrun |
| F43 · Separate internal and group cash-flow reporting | finance.ForecastBinding | A06 Management insight and drafting, A07 Control evidence and release preflight, A08 Evaluation and quality review | documents.publicationreceipt |
| F45 · Business-line client/service register and billing-period coverage | finance.CoverageTerms | A01 Intake and case triage, A05 Finance evidence and analysis, A04 Planning and workflow coordination | finance.coverageassessment |
