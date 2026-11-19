#!/usr/bin/env python3
"""Builds delivery/psl-decisions/PSL-DECISIONS.html from the decision data below.
Every entry is drawn from the repo sources named in its Reference line."""
import html, json, re

ROOT = "/Users/Hunchoo/psl-factory"
OUT = ROOT + "/delivery/psl-decisions/PSL-DECISIONS.html"

reg = {e["id"]: e for e in json.load(open(ROOT + "/contracts/decision-registry.json"))["entries"]}
def P(did):
    return reg[did]["affected_process_ids"]

ALL122 = P("D11")

AREAS = [
    ("pmo", "Projects & PMO"),
    ("com", "Commercial: costing, RFPs & SOW"),
    ("del", "Delivery, UAT, go-live & hypercare"),
    ("fin", "Finance: invoices, receipts, payment exceptions, forecasting, ledger, fixed assets"),
    ("pay", "Payroll & HR"),
    ("ppl", "People, roles & approvals"),
    ("ntf", "Notifications & templates"),
    ("oth", "Other"),
]

SRC = "src"; ENG = "eng"
OPEN, PART, CONF = "Open", "Partly answered", "Answered, awaiting PSL confirmation"

E = []
def add(**k):
    E.append(k)

# ---------------- Projects & PMO ----------------
add(area="pmo", key="PMO-1",
    q="Who receives each department's planning requests (Engineering, QA, Security, Infrastructure, Product), and may Tola send routine requests without a person approving each one?",
    means="Planning needs input from several departments. The factory can route requests, but it must not take over other teams' approvals. Once PSL names a receiver per department and says whether routine requests need a person's approval, Tola can route them and the planning item stops waiting.",
    where="Setup › Rules (a department-receiver rule; not yet defined). Proposed owner: PMO Lead.",
    procs=["P02", "P17", "P18", "P26"],
    hold="Sending a planning request to a department with no named receiver. The planning item shows “owner needed” for that department.",
    works="Planning items, recording each department's input by the PM with proof, and every other department's request.",
    status=OPEN, basis=[SRC, ENG],
    basis_note="The rule that routing must not take over other teams' approvals is in PSL's documents (P02). The receiver rule and the approval-per-send question are engineering proposals.",
    refs="P02.owner_routes, P02.evidence_contracts; gaps-b G-42-3, G-42-4; BACKEND-HANDOFF “Held for PSL” (F-31)")

add(area="pmo", key="PMO-2",
    q="When an engagement becomes a project, which identifiers link the two, who confirms the PM and who registers the project? Is a client project contact required?",
    means="Registration links the RFP or engagement, the project and later invoices. PSL's answer fixes how records are matched and who is accountable for the step. The factory currently asks for the PM a second time, prefilled. PSL may keep or drop that step.",
    where="Decisions meeting, then Setup › Rules. Proposed owner: PMO Lead.",
    procs=["P03", "P16"],
    hold="Registering an engagement as a project when identifiers conflict or are missing (engagement assignment and identity resolution).",
    works="Logging the engagement, recording the route, assigning the PM, and the planning packet.",
    status=OPEN, basis=[SRC, ENG],
    basis_note="Linked identifiers are required by PSL's documents (P03). The confirm-PM step and the contact field are engineering or design proposals.",
    refs="D11.engagement_assignment, D11.project_identifiers, D11.engagement_identity_resolution; gaps-b G-41-2, G-41-6, line 153")

add(area="pmo", key="PMO-3",
    q="Who accepts planning readiness, and what must be true for planning to count as verified before the project goes to delivery?",
    means="PSL's process ends Planning with an exit approval. The factory needs the accepting role and the exact checks. Without them, Tola can write a readiness summary, but no one can accept it.",
    where="Decisions meeting; then Setup › Rules. Owner: PMO (PSL to name the role).",
    procs=["P21", "P25", "P26", "P27", "P63"],
    hold="“Prepare readiness” and the hand-off to delivery. The step shows a disabled reason.",
    works="Collecting estimates, the readiness summary draft, and comparison with the RFP costing.",
    status=OPEN, basis=[SRC],
    basis_note="The Planning exit approval comes from PSL's documents (P26, P63). The approver and the criteria are missing.",
    refs="D11.planning_alignment (operation planning.readiness); gaps-b G-42-6")

add(area="pmo", key="PMO-4",
    q="On the shared project view, which roles see which parts, for example money, issues and documents?",
    means="PSL wants one permissioned view for PMO, management and engineering. Access is checked per record, so the factory needs PSL's view rules before it shows each audience its parts.",
    where="Decisions meeting; Setup › Rules. Owner: PMO Lead with Finance Lead.",
    procs=["P05"],
    hold="The configured shared-view presentation for each audience. Until then, each person sees only what their own grants allow.",
    works="Projects list, project journey and the tabs each person can already open.",
    status=OPEN, basis=[SRC],
    basis_note="The permissioned shared view is in PSL's documents (P05).",
    refs="D11.shared_project_view (operation project_view.presentation); gaps-a line 100 (money tab readers)")

add(area="pmo", key="PMO-5",
    q="Who may mark a milestone complete (only the project's PM, or anyone in PMO)? Should completing a milestone start the stage invoice draft automatically?",
    means="PMO marks milestones complete and Finance then invoices; that split is settled. What remains is which PMO role may press “Mark complete”, and whether completion starts Chidi's invoice draft or Finance starts it.",
    where="Decisions meeting; Setup › Rules. Owner: PMO Lead with Finance Lead.",
    procs=["P34", "F34", "P12"],
    hold="The milestone-completion write and any automatic start of the invoice draft.",
    works="Milestone tabs, evidence upload, and Finance starting an invoice by hand.",
    status=OPEN, basis=[SRC, ENG],
    basis_note="PMO marking milestones complete comes from PSL (U03). The per-role permission and the auto-start are engineering questions.",
    refs="gaps-a G-SCR19-1, G-SCR19-5, line 121")

add(area="pmo", key="PMO-6",
    q="Which day does the week end for the weekly client report, and which record does its timeline cite (meeting minutes or the weekly sync)?",
    means="The weekly report cites this week's records. A fixed week end decides which records count. Weekly cadence is known; the cut-off day is not.",
    where="Setup › Rules (calendar values, see OTH-1). Owner: PMO Lead.",
    procs=["P41"],
    hold="The week-end sentence on the report. The report itself is still written, cited and reviewed.",
    works="Writing, citing, assembling and reviewing the weekly report.",
    status=OPEN, basis=[ENG],
    refs="F-21 spec conflict 7; BQ-33; BACKEND-HANDOFF “Added during F-21”; related D04.deadline_parameters")

add(area="pmo", key="PMO-7",
    q="For meeting minutes: which audiences may skip review, where are internal minutes filed, and are actions created when the PM confirms them or only after approval?",
    means="Client-facing minutes always go through review. The boards show internal minutes filed straight away, which is a rule PSL has not given. The answer sets when owners and deadlines become real actions.",
    where="Setup › Rules. Owner: PMO Lead.",
    procs=["P43"],
    hold="Filing internal minutes without review and creating actions from them. Client minutes still go through review.",
    works="Drafting minutes, review, and recording decisions.",
    status=OPEN, basis=[ENG],
    refs="gaps-c lines 56-57, G-SCR28-7; F-28 spec “Held”")

add(area="pmo", key="PMO-8",
    q="Who reviews the Tuesday status summary and the monthly executive report, who receives each, and do Tuesday reports really go out without review?",
    means="Both reports are in PSL's process. The factory needs the reviewer and audience before it can send one version to leaders. The report also needs a basis: does it reflect the author's visibility or a reviewer-approved snapshot? Projects the author cannot see must appear as a count only.",
    where="Setup › Rules. Owner: PMO Lead (PSL to confirm).",
    procs=["P40", "P42"],
    hold="Approving and sending a leadership report.",
    works="Drafting from visible records, the coverage note, and review tracking.",
    status=OPEN, basis=[SRC, ENG],
    basis_note="The Tuesday meeting and the monthly report are in PSL's documents. The reviewer, the audience and the review-skip rule are not.",
    refs="OPS.leadership_review_authority, OPS.leadership_audience; gaps-c G-SCR52-2, G-SCR52-3, line 152; F-35 readiness questions 1-3")

add(area="pmo", key="PMO-9",
    q="Who decides a change request (all five deciders on the board, or only some, and in which order)? Who is the change authoriser, and what makes a closed change verified?",
    means="Change requests need approvals, conditional cost approval and timeline agreement. The board draws five deciders as a placeholder. PSL's answer sets the decision chain and when a closed change updates a milestone's scope.",
    where="Decisions meeting; Setup › Rules. Owner: PMO Lead with the delivery approvers.",
    procs=["P56", "P57", "P58", "P59", "P60"],
    hold="The change decision and authorisation steps.",
    works="Logging and classifying changes and the impact assessments.",
    status=OPEN, basis=[SRC, ENG],
    basis_note="Change approvals are in PSL's documents (P58). The number of deciders and the authoriser role are open.",
    refs="D-CHANGE-DECIDERS; gaps-c G-SCR31-2, G-SCR31-3, G-SCR31-6")

add(area="pmo", key="PMO-10",
    q="Which internal escalation notes may skip review (client messages never do), and who reviews the outcome of an escalation?",
    means="Escalation and de-escalation need approval in PSL's process. The boards say some internal notes skip review, but no rule names them.",
    where="Setup › Rules. Owner: PMO Lead.",
    procs=["P44"],
    hold="Sending an internal escalation note without a review task.",
    works="Raising escalations, drafting notes, and the client-message review.",
    status=OPEN, basis=[SRC, ENG],
    refs="gaps-c G-SCR51-1, lines 89 and 113")

# ---------------- Commercial ----------------
add(area="com", key="COM-1",
    q="What is PSL's costing rule: rates, units, margin, tax, currency, rounding and allowed overrides, with worked examples? Who owns the rule, who owns the examples, and how is a new version proposed, reviewed and withdrawn?",
    means="Every project price comes from this rule, and no rate may be guessed. Once PSL supplies it with worked examples, the factory can calculate costing sheets, show margin to the CEO and fix the SOW price. The proposer may not review their own version (12 Nov).",
    where="Setup › Costing rule (placeholder today). Collected in the pricing-calculator walkthrough. Owner: commercial owner (PSL to name; the names on the boards are sample data).",
    procs=["P06", "P07", "P08", "P09", "P14", "P46", "P48"],
    hold="Calculating any cost or price. The costing total stays “Unknown”, and the CEO's margin figure cannot show.",
    works="Collecting Engineering and Security estimates, the costing sheet's structure, adjustments with reasons, and routing approvals.",
    status=OPEN, basis=[SRC],
    basis_note="PSL's process uses a pricing calculator (P14 walkthrough). Its formula and values were never supplied.",
    refs="P14-Q01.commercial_costing_rule_oracle; D-COSTING-RULE; gaps-b G-27-1; gaps-a G-SCR39-6, G-SCR39-11")

add(area="com", key="COM-2",
    q="Who may adjust a project's costing, and is there a limit per role?",
    means="The PM can add a project adjustment with a reason. PSL decides who may do this and up to what amount. No limit is assumed.",
    where="Setup › Rules › Pre-sale (“Who may adjust a project's costing”, “Costing adjustment limit”). Owner: commercial owner.",
    procs=["P06", "P08"],
    hold="The adjustment step on the costing sheet.",
    works="The rest of the costing sheet and approvals.",
    status=OPEN, basis=[ENG],
    refs="presale.costing_adjuster, presale.costing_adjustment_limit; gaps-b G-27-7")

add(area="com", key="COM-3",
    q="When planning estimates differ from the RFP costing, does pricing always run again as a new costing version?",
    means="If Engineering's planning estimate is higher than the costing, the SOW price cannot come from the old version. PSL's sources already say cost-changing revisions repeat the costing chain. PSL needs to confirm that every changed estimate counts as such a revision.",
    where="Decisions meeting. Owner: PMO Lead with the CEO.",
    procs=["P07", "P08", "P26"],
    hold="Creating the next costing version from planning estimates.",
    works="Planning, estimate comparison and flagging the difference.",
    status=PART, basis=[SRC, ENG],
    basis_note="The registry says known cost-changing revisions repeat the costing chain (D02 note). Whether that covers all planning differences is an open board question.",
    refs="gaps-b G-42-5; decision-registry D02 “do not re-ask”")

add(area="com", key="COM-4",
    q="In the confirmed approval order (PM, then PMO Lead, then CEO), may the PM who prepared the costing sheet also approve as step 1? What does the CEO's final costing decision record and show?",
    means="The order is settled. Separation of duties normally stops a preparer approving their own work, so PSL must say whether the PM step is an exception. The CEO's decision page still needs its fields (figures, margin, basis) before it can be designed.",
    where="Decisions meeting. Owner: CEO with PMO Lead.",
    procs=["P09", "P48"],
    hold="The CEO's final costing decision page and the PM's own approval step, if separation applies.",
    works="PMO Lead approval and the rest of the chain.",
    status=PART, basis=[SRC, ENG],
    basis_note="The approval order is PSL's (P09; confirmed 13 Nov). The separation question and the CEO page fields are engineering proposals.",
    refs="gaps-b G-27-4, G-27-11; D-DECISION-VARIANTS (CEO costing); gaps-e G-SCR03V-2, G-SCR03V-7")

add(area="com", key="COM-5",
    q="Who may assign an RFP to a PM, who may record an RFP outcome, and does an “unknown” outcome need proof?",
    means="Every RFP is logged and given a PM. The assigning role is recorded as the authority in the audit trail, so it must come from PSL, not an Admin default.",
    where="Setup › Rules › Pre-sale. Owner: PMO Lead.",
    procs=["P45", "P49"],
    hold="The assign control and real outcome recording. No fallback assigner is shown.",
    works="Logging the RFP, the RFP response work, and team input.",
    status=OPEN, basis=[SRC, ENG],
    basis_note="Assigning a PM to every RFP is in PSL's documents (P45). Which roles may do it is open.",
    refs="presale.rfp_assigner, presale.rfp_outcome_recorder; gaps-b G-24-1; BQ-28; F-36 readiness")

add(area="com", key="COM-6",
    q="RFP submission: may a pack that still contains a test-template part be sent? How many days before the client's deadline must PSL submit? What counts as “delivered”? Can the person who submits also be the document reviewer?",
    means="These rules govern the real send of a bid. Today every template is a test template, so the first question decides whether any pack can go out before PSL's real templates arrive.",
    where="Setup › Rules. Owner: PMO Lead.",
    procs=["P47", "P48"],
    hold="The real send of a submission pack.",
    works="Assembling the pack, checks and review.",
    status=OPEN, basis=[ENG],
    refs="gaps-b G-40-3, G-40-5, G-40-6; F-38 spec questions 11-15")

add(area="com", key="COM-7",
    q="Where does the library of past bid answers live, who may read each one (they belong to other clients), and may Tola learn from a PM's rejection reasons?",
    means="Tola suggests answers from PSL's past bids. Past answers are per-record data, and nothing may be learned from them without PSL's agreement.",
    where="Decisions meeting. Owner: PMO Lead.",
    procs=["P46", "P47"],
    hold="Tola's suggestions from real past bids, and any learning from rejection reasons.",
    works="The RFP response, with the PM writing or editing each answer.",
    status=OPEN, basis=[ENG],
    refs="gaps-b G-26-5, line 77; F-37 spec item 3")

add(area="com", key="COM-8",
    q="Who reviews client documents (SOW, PRD, go-live and other external documents) before they are shared?",
    means="Every external document passes a quality gate, and required approvals come before an SOW is shared. The reviewer role sets who gets the review task.",
    where="Setup › Rules (“Who reviews client documents”). Owner: PMO Lead.",
    procs=["P01", "P19", "P53"],
    hold="The document review decision while no reviewer is configured.",
    works="Drafting, checks against costing and templates, and version history.",
    status=OPEN, basis=[SRC],
    basis_note="The review gate is in PSL's documents (P01, P53). The mock fixture shows PMO Lead, but that is sample data, not a PSL answer.",
    refs="documents.client_reviewer (mock value only); gaps-b G-40-7")

# ---------------- Delivery ----------------
add(area="del", key="DEL-1",
    q="How does an emergency deployment relate to the general rule that every production release needs GLPI approval first? Which changes count as Standard (pre-approved), and which gates do they skip? Who approves an emergency retrospective?",
    means="PSL's documents conflict: emergency authorisation versus GLPI before every deployment. No waiver or blanket pre-approval may be inferred. PSL's written reconciliation and a Standard-change catalogue make emergency and Standard releases possible.",
    where="Decisions meeting (written reconciliation). Owners: PMO, Engineering, Security and the prescribed approvers. Then CTO emergency decision page.",
    procs=P("D01"),
    hold="Emergency and Standard production dispatch, any inferred GLPI waiver, and the CTO emergency decision page.",
    works="Normal changes, logging emergency changes within 24 hours, and GLPI references.",
    status=OPEN, basis=[SRC],
    refs="D01 (D01.change_type_catalogue, D01.emergency_glpi_relationship, D01.satisfied_gate_map); D-DECISION-VARIANTS (CTO emergency); gaps-c line 89")

add(area="del", key="DEL-2",
    q="Is the delivery gate a release decision rather than a planning decision? Who holds release authority? Does “Reject” apply to a release?",
    means="The boards label the gate “Planning decision”, but its buttons approve a release. Planning must finish before the SOW is signed, so the label matters. The confirmed PMO Lead scope covers closure, commercial approvals and escalations, not release.",
    where="Decisions meeting. Owner: PMO Lead with Engineering.",
    procs=["P29", "P30", "P31", "P32", "P33", "P63"],
    hold="A real release decision. No release authority is configured.",
    works="Release readiness, gates and the delivery tab.",
    status=OPEN, basis=[ENG],
    refs="F-32 spec items 1-3; BACKEND-HANDOFF “Added during F-32”; D-ROLE-PMO scope")

add(area="del", key="DEL-3",
    q="How do clients sign (method, who signs, what proof)? Does a client signature apply to change go-live as well as to the SOW, PRD, UAT and go-live?",
    means="Staff record client responses with proof (decided). PSL still has to say which signature counts as valid for each step, so a recorded response can close it.",
    where="Decisions meeting. Owner: PMO Lead.",
    procs=["P20", "P30", "P33", "P60"],
    hold="Treating a recorded client signature as valid where the signature rule is not set.",
    works="Recording client responses with date, contact, proof and attestation.",
    status=PART, basis=[SRC],
    refs="D11.client_signature_contract, D11.change_go_live_client_applicability (source question Q09)")

add(area="del", key="DEL-4",
    q="What is the hypercare window, and what must be true at its end for a project to qualify for closure?",
    means="PSL's process confirms hypercare stability before closure, with Engineering's criteria. Until they are set, the factory records observations but never shows “met”.",
    where="Setup › Rules › Delivery (“Hypercare window”, “What hypercare must meet”). Owner: Engineering Lead with PMO Lead.",
    procs=["P35"],
    hold="Evaluating hypercare (“qualified”). The item stays “setup needed”.",
    works="Recording the release, logging observations and incidents.",
    status=OPEN, basis=[SRC],
    refs="D11.hypercare_criteria_ref; delivery.hypercare_window, delivery.hypercare_criteria; F-34 spec; gaps-d line 97")

add(area="del", key="DEL-5",
    q="When does a handover to Support need review (for example above a threshold)?",
    means="The handover is published to Support with escalation documentation. The board shows “Review needed? No” with no rule behind it.",
    where="Setup › Rules › Delivery (“When a handover needs review”). Owner: PMO Lead.",
    procs=["P37"],
    hold="Publishing the handover.",
    works="Preparing the handover document and recording Support's reply with proof.",
    status=OPEN, basis=[ENG],
    refs="delivery.handover_review; gaps-d G-48-3; F-40 spec item 1")

add(area="del", key="DEL-6",
    q="Who confirms Finance before closure, and where does that confirmation come from?",
    means="Closure confirms the Finance notifications. Money still owed stays owed after closure. PSL must name the confirmer and the source before closure can complete.",
    where="Setup › Rules › Delivery (“Who confirms Finance before closure”). Owner: PMO Lead with Finance Lead.",
    procs=["P39"],
    hold="The closure states that depend on the Finance confirmation.",
    works="Closure report, retrospective and archive preparation. Finance follow-up continues after closure.",
    status=OPEN, basis=[SRC],
    refs="delivery.closure_finance_confirmer; gaps-d G-49-2, G-49-3; F-40 readiness; flow-audit 5.4")

add(area="del", key="DEL-7",
    q="If a client declines go-live, what happens to hypercare, archive, handover and the milestone?",
    means="The boards show these as on hold and the milestone not complete, but no rule defines the effect.",
    where="Decisions meeting. Owner: PMO Lead.",
    procs=["P33", "P34"],
    hold="The defined after-effects of a declined go-live.",
    works="Recording the client's response and drafting the next go-live document version.",
    status=OPEN, basis=[ENG],
    refs="gaps-d G-45-2")

add(area="del", key="DEL-8",
    q="How long are project archives and controlled documents kept, where are they stored, and may anything be purged?",
    means="Archiving is final evidence. Retention and storage are PSL policy and are also needed before documents can be published.",
    where="Setup › Rules (“Archive storage and retention”). Owner: PMO Lead with document repository owner.",
    procs=["P36", "P52"],
    hold="Archive retention decisions and document publishing that needs the storage rule.",
    works="Collecting and checking archive contents.",
    status=OPEN, basis=[SRC],
    basis_note="The mock shows “keep, never purge”. That is a fixture value, not a PSL answer.",
    refs="D11.template_storage_retention_rules; delivery.archive_retention, delivery.archive_storage (mock); gaps-d line 9")

# ---------------- Finance ----------------
add(area="fin", key="FIN-1",
    q="For each contract: the stage amounts or percentages, currency and tax basis, due terms and rounding; which UAT record triggers the UAT invoice and which event marks completion? Is there a default payment term?",
    means="Three stages are known (after signed SOW, at UAT, at completion), with no 50/30/20 default. Each contract has its own schedule, so Finance cannot issue a stage invoice without that contract's terms.",
    where="Per contract, captured with the signed SOW; Setup › Rules (“Invoice payment terms default”). Owners: PMO and Finance with the commercial contract owner.",
    procs=P("D12"),
    hold="Preparing a stage invoice for a contract whose terms are missing. The signed-SOW invoice needs only its own stage terms, not the UAT or completion ones.",
    works="Invoice inbox, milestone evidence, receipt infrastructure and the other contracts.",
    status=PART, basis=[SRC],
    refs="D12 (D12.contract_version_ref, D12.currency_amount_basis, D12.stage_terms, D12.uat_billing_predicate_ref, D12.completion_billing_predicate_ref); finance.invoice_payment_terms; U03-U05")

add(area="fin", key="FIN-2",
    q="In the billing narrative, did PSL mean “prices” or “sign”? Is there a signature gate before an invoice is released?",
    means="Two transcriptions disagree. No new signature gate is assumed. PSL's written confirmation settles whether invoice release needs a signature.",
    where="Decisions meeting (check the recording or confirm in writing). Owner: Finance Lead.",
    procs=P("D03"),
    hold="Evaluating invoice release controls that depend on this statement.",
    works="Invoice drafting and review.",
    status=OPEN, basis=[SRC],
    basis_note="Some of these IDs are BaaS billing processes, which are deferred from this release.",
    refs="D03 (D03.verified_billing_statement, D03.invoice_release_control_refs)")

add(area="fin", key="FIN-3",
    q="How are invoices priced and produced: price rules with effective dates, tax, tiers, rounding, billing dates, duplicate and correction handling, and the existing Power Automate flow's real behaviour? How are invoices numbered?",
    means="Finance's billing flow exists outside the factory. Without evidence of what it does and the approved price rules, the factory cannot price or produce live invoices.",
    where="Decisions meeting plus flow export and examples. Owners: Finance with the pricing and flow owners.",
    procs=P("D08"),
    hold="Live invoice pricing, adapter actions, scheduled billing and invoice identity.",
    works="Drafting, review and the mock invoice path.",
    status=OPEN, basis=[SRC],
    refs="D08 (D08.adapter_contract_ref, D08.effective_price_rule_refs, D08.tax_tier_rounding_rules, D08.billing_calendar, D08.duplicate_correction_rules); D08.obligation_namespace")

add(area="fin", key="FIN-4",
    q="Who (which human role and people) may approve a payment exception that lets deployment go ahead below the payment expectation? How long is an exception valid, and how is it revoked? Is the stated “at least 80% paid” measured against the contract total, the invoiced amount or something else, and which funds count?",
    means="PSL confirmed that an exception can be given and that a human must approve it. The role is not named yet. An exception never erases debt and never bypasses release controls.",
    where="Decisions meeting, then the payment-exception rules in Setup. Owners: PMO, Finance and existing release authority owners.",
    procs=P("D13"),
    hold="The payment assessment result (shown as Unknown) and approving an exception. Exception requests can still be tracked.",
    works="Document work, milestone evidence, Finance inbox and receipts infrastructure.",
    status=PART, basis=[SRC],
    refs="D13 (authority, principals, delegation, validity, denominator, qualifying funds); U06-U08; D-DECISION-VARIANTS (payment exception page); gaps-e line 47")

add(area="fin", key="FIN-5",
    q="How is a payment received verified, who records it, and how is it allocated to invoices and stages, including part payments and short payments such as tax deducted?",
    means="Clients pay irregularly between stages, and Finance owns receipts. Receipts and allocations are separate records. Recording a short payment must not write anything off.",
    where="Setup › Rules (“Short payments”) and the receipt allocation rule. Owner: Finance Lead.",
    procs=P("D14") + ["F41"],
    hold="Recording a payment received, allocating it, and matching forecast actuals to receipts.",
    works="Payments list, reminders, owed and overdue views (unknown stays Unknown).",
    status=PART, basis=[SRC],
    refs="D14 (receipt_verification_source_ref, recorder_authority_ref, allocation_rule_ref); D-RECEIPT-ALLOCATION; finance.short_payments; gaps-e G-SCR20-8, G-SCR20-9; gaps-f G-56-6")

add(area="fin", key="FIN-6",
    q="What are the rules for refunds, credits, write-offs and chargebacks? Who may correct a financial record, and which legal or accounting documents are required?",
    means="Technical audit rules do not decide accounting policy. Corrections need PSL's approved treatment with examples, including unmatched and excess payments.",
    where="Decisions meeting. Owner: Finance Lead.",
    procs=P("D14"),
    hold="Any financial correction, refund, credit or write-off.",
    works="Recording facts and audit history.",
    status=OPEN, basis=[SRC],
    refs="D14.adjustment_correction_rule_refs, D14.legal_document_requirements")

add(area="fin", key="FIN-7",
    q="Who may send payment reminders to clients, is the PM always copied, and how long until a second reminder?",
    means="Chidi drafts reminders and a person sends them. The board's “7 days” is not shown until PSL sets it.",
    where="Setup › Rules. Owner: Finance Lead.",
    procs=["F32"],
    hold="The real reminder send (also needs the email provider) and the second-reminder timing.",
    works="Drafting and editing reminders and the payments list.",
    status=OPEN, basis=[ENG],
    refs="gaps-e lines 176-178, G-SCR32-5; BACKEND-HANDOFF “Added during F-41”")

add(area="fin", key="FIN-8",
    q="Management accounts: please supply the redacted trial-balance export and workbooks, account and BU maps, formula lineage, unit/sign/currency/period conventions and worked examples. What is the statement contract, which BU metrics apply, which report template and audience are used, and who publishes?",
    means="The chain from QuickBooks to the management accounts is known, but its maps and formulas are not. Without them the factory can import and check files but cannot calculate or publish statements.",
    where="Data handover meeting; Setup › Finance rules › Management accounts. Owner: Finance reporting owner (Finance Lead).",
    procs=P("D06"),
    hold="Validating imports against PSL's schema, calculating statements and reports, and publishing them.",
    works="File intake, completeness checks, lineage capture and review tasks.",
    status=PART, basis=[SRC],
    refs="D06 (source_schema_ref, account_bu_maps, unit_sign_currency_period, rule_oracle_refs); D06.statement_contract; finance.management_accounts.*; gaps-f G-53-7")

add(area="fin", key="FIN-9",
    q="Ledger sources: what verifies a captured QuickBooks entry, how are conflicts resolved, who reviews, what may the agent see, and when is a source accepted and published?",
    means="Chidi captures lineage from export files. PSL's rules decide when a captured source is trusted.",
    where="Setup › Finance rules › Ledger sources. Owner: Finance Lead.",
    procs=["F01"],
    hold="Verifying, reviewing and resolving ledger sources.",
    works="Capturing sources and duplicate detection.",
    status=OPEN, basis=[ENG],
    refs="F01.verification_rules, F01.review_authority, F01.conflict_rules, F01.agent_projection, F01.validation_handoff, F01.accepted_publication; finance.ledger_sources.*")

add(area="fin", key="FIN-10",
    q="Income schedules: what are the income-detail and inventory rules, who reviews schedules, and what must a “justified” adjustment show (reason, proof)?",
    means="Schedules carry manual supplemental adjustments. PSL decides how each is justified and who checks it.",
    where="Setup › Finance rules › Income schedules. Owner: Finance Lead.",
    procs=["F12", "F13"],
    hold="Schedule review.",
    works="Investigating and preparing schedules.",
    status=OPEN, basis=[ENG],
    refs="F12.detail_rules, F13.inventory_rules, SCHEDULES.review_authority; finance.income_schedules.*; gaps-f G-54-2")

add(area="fin", key="FIN-11",
    q="Fixed assets: what are the register rules and the depreciation calculation rules (including which date depreciation starts from)? Who reviews the asset schedule, and who explains unclear dates?",
    means="Chidi never calculates or reads asset values. The calculation is a deterministic rule PSL must supply with examples.",
    where="Setup › Finance rules › Fixed assets. Owner: Finance Lead.",
    procs=["F07"],
    hold="Register review and the depreciation calculation (item stays “setup needed”).",
    works="Investigating the register and listing unclear dates.",
    status=OPEN, basis=[SRC, ENG],
    basis_note="PSL's sources ask for F07 expected examples (D06). The review and register rules are engineering interfaces.",
    refs="F07.source_rules, F07.calculation_rules, F07.review_authority; finance.asset_schedule.*; gaps-f G-55-1")

add(area="fin", key="FIN-12",
    q="Cash forecast: which expected inflows are included, how are the opening balance and partial receipts treated, who prepares it, who reviews the group forecast, and what goes to internal versus group recipients?",
    means="The forecast is partial, not assumed complete. PSL's inclusion and projection rules decide what the forecast calculates and who sees which version.",
    where="Setup › Finance rules › Cash forecast. Owner: Finance Lead.",
    procs=["F36", "F37", "F38", "F39", "F40", "F41", "F42", "F43"],
    hold="Forecast calculation, group review and the internal or group publication.",
    works="Collecting inflows and outflows and recording actuals as facts.",
    status=PART, basis=[SRC],
    refs="D10.forecast_inclusion_rule_id, D10.audience_projection_rules; finance.cash_forecast.*; gaps-f G-56-3, G-56-4")

add(area="fin", key="FIN-13",
    q="When reporting categories were added, what were they called and from when? How should history be restated?",
    means="Changing BU scope means reworking history. PSL's approved treatment prevents silent rewrites.",
    where="Decisions meeting. Owner: Finance Lead.",
    procs=["F14", "F15", "F23", "F24", "F25", "F26", "F27"],
    hold="Applying new categories to history and restating past reports.",
    works="Current-period reports.",
    status=OPEN, basis=[SRC],
    refs="D10.report_category_effective_dates, D10.restatement_rule_id")

add(area="fin", key="FIN-14",
    q="BU totals: where do events come from and how are they attributed to BUs? Who reviews BU totals, and what are the disclosure rules and recipients, including the minimum group size?",
    means="Small BUs can reveal individual pay. PSL's disclosure rule decides what may be published. No threshold is assumed.",
    where="Setup › Finance rules › BU totals. Owner: Finance Lead (with HR Lead for disclosure).",
    procs=["F14", "F15", "F22", "F23", "F44"],
    hold="Publishing BU totals and any BU below the unset minimum.",
    works="Collecting sources and preparing drafts.",
    status=OPEN, basis=[ENG],
    refs="BU.review_authority, BU.disclosure_rules, F44.source_rules, F44.attribution_rules; finance.bu_totals.event_source/reviewer/disclosure; gaps-f G-57-2")

add(area="fin", key="FIN-15",
    q="For revenue recognition: who attests project progress, who reviews it, and what criteria must a review meet?",
    means="Project progress is handed to Finance by hand today. The factory can collect evidence, but a reviewed recognition conclusion needs PSL's criteria.",
    where="Decisions meeting. Owner: Finance Lead with PMO Lead.",
    procs=["F33"],
    hold="A reviewed recognition conclusion. Receipts and collection do not depend on it.",
    works="The progress hand-off and evidence.",
    status=OPEN, basis=[ENG],
    refs="F33.authority_rules, F33.recognition_review_rules; BUILD-DECISIONS ARCH-123")

# ---------------- Payroll & HR ----------------
add(area="pay", key="PAY-1",
    q="Which payroll fields are restricted, who may change that, how are staff references masked, and may Finance, the BU reviewer and Chidi see staff count and cost per BU as totals?",
    means="Payroll data belongs to HR. Until PSL decides, every payroll field is treated as HR-only, and Finance sees nothing derived from it.",
    where="Setup › Payroll visibility (placeholder today). Owner: HR Lead (to confirm).",
    procs=["F16", "F17", "F18", "F19", "F20", "F21", "F22", "F35", "F44"],
    hold="Every payroll row outside HR, BU staff figures, and the payroll and BU start drawers.",
    works="HR's own payroll work and the rest of Finance.",
    status=OPEN, basis=[ENG],
    refs="D-PAYROLL-VISIBILITY; gaps-e lines 7-19, G-SCR37-3; gaps-f G-56-4, G-57-1; F-44 readiness question 1")

add(area="pay", key="PAY-2",
    q="Payroll inputs: who may read the two payroll inputs, how are they combined (joins and overlaps), how is payroll matched to HR staff and BU membership over time, and who may release a held row?",
    means="PSL has withheld the private workings. With redacted samples and rules, the factory can combine and match payroll. Without them it shows a preview only.",
    where="Setup › Finance rules › Payroll (“Who may read inputs”, “Merge rules”, “Match rules”). Owners: HR data owner with Finance allocation owner.",
    procs=["F16", "F17"],
    hold="Capturing, combining and matching payroll.",
    works="Import preview, rule screens, lineage and test runs.",
    status=OPEN, basis=[SRC],
    refs="D07.authorized_input_refs, D07.join_overlap_rule_id, D07.effective_membership_ref; F16.input_access_rules, F16.merge_rules, F17.match_rules; finance.payroll.input_readers/merge/match")

add(area="pay", key="PAY-3",
    q="Payroll reporting: what are the reporting rules and recipients, who reviews payroll, may the HR Lead also be the reviewer, and should totals be called “gross pay” or “staff cost”?",
    means="Payroll totals go to a few named roles as totals only. PSL decides who those roles are and who checks the figures first.",
    where="Setup › Finance rules › Payroll (“Reporting rules”, “Who reviews payroll”). Owner: HR Lead with Finance Lead.",
    procs=["F18"],
    hold="Payroll report review and publishing.",
    works="Preparing totals.",
    status=OPEN, basis=[ENG],
    refs="F18.reporting_rules, F18.review_authority; finance.payroll.reporting/reviewer; gaps-e G-SCR59-8, G-SCR59-13, line 232")

add(area="pay", key="PAY-4",
    q="Staff cost allocation to BUs: pool and ratio tables, the headcount denominator, monthly treatment, rounding and residuals, and individual executive or exceptional allocations?",
    means="Headcount applies only to the described other-staff pool. The rest of the allocation workings are private to PSL and must come with worked examples.",
    where="Data handover meeting; Setup › Finance rules › BU totals (“Staff allocation rules”). Owner: Finance allocation owner.",
    procs=["F19", "F20", "F21", "F22"],
    hold="A real allocation result.",
    works="Import preview, rule configuration screens, lineage and other reports.",
    status=PART, basis=[SRC],
    refs="D07.allocation_pool_rules, D07.rounding_residual_rule_id; F21.allocation_rules; finance.bu_totals.staff_allocation")

add(area="pay", key="PAY-5",
    q="HR-to-Finance information: who authorises what HR gives Finance, what may be disclosed, and how are scope questions raised?",
    means="Finance reads HR data only. PSL decides what HR shares and who signs it off.",
    where="Decisions meeting. Owner: HR Lead with Finance Lead.",
    procs=["F35"],
    hold="Authorising and snapshotting HR information for Finance.",
    works="The rest of Finance and HR.",
    status=PART, basis=[ENG],
    basis_note="That Finance only reads HR data is already established.",
    refs="F35.authority_rules, F35.disclosure_rules, F35.scope_clarification_route")

# ---------------- People ----------------
add(area="ppl", key="PPL-1",
    q="Who at PSL approves this scope and the final design, and where is the approval recorded?",
    means="The design gate runs under the design engineer's recorded exception, not a PSL approval. One person in a PMO leadership role is expected to approve both.",
    where="Decisions meeting. Owner: PSL leadership (a PMO leadership role).",
    procs=[],
    hold="PSL's formal approval of scope v1 and of the final design.",
    works="Design and delivery continue under the recorded exception.",
    status=OPEN, basis=[ENG],
    refs="scope Q-01; assumption A-02; interview Q3")

add(area="ppl", key="PPL-2",
    q="Which roles does PSL have? Please confirm the roles PSL's documents name that the app lacks (Product Manager, Design Lead, QA Lead, Incident Lead, Infrastructure/DevOps, Support and Operations, Management). Please also confirm the proposed names Finance Lead, Finance Reviewer and HR Lead.",
    means="The factory is role-based. Each missing role either needs adding or must be removed from the boards. Work held for a missing role (for example Design Lead) waits until the role exists and has a holder.",
    where="Decisions meeting (worksheet item ppl-10); then Setup › Roles. Owner: PSL leadership.",
    procs=[],
    hold="Assigning holders for missing roles and the work held for them.",
    works="Every role that already exists.",
    status=PART, basis=[SRC, ENG],
    basis_note="The missing roles are named in PSL's documents. Finance Lead, Finance Reviewer and HR Lead are proposed names.",
    refs="memory: role catalogue gap; gaps-a G-SCR13B-2")

add(area="ppl", key="PPL-3",
    q="Who holds Admin, and who may assign roles, invite staff and deactivate accounts?",
    means="Admin gives no approval authority. Until PSL names the Admin, no one can assign roles, invite or deactivate, and Setup shows read-only to everyone.",
    where="Decisions meeting; then Setup › Roles and Setup › Staff. Owner: PSL leadership.",
    procs=[],
    hold="Role assignment, invitations, deactivation and work hand-over on deactivation.",
    works="Viewing roles and staff.",
    status=OPEN, basis=[ENG],
    refs="D-ADMIN-AUTHORITY; gaps-a G-SCR21-1, lines 225, 295; F-11 readiness")

add(area="ppl", key="PPL-4",
    q="For each decision: which role may approve, return, reject or withdraw it? Who holds each role (assigned in the app)? May one person hold two roles on the same item, for example a PM who is also PMO Lead, or an HR Lead who is also the payroll reviewer?",
    means="This is the core authority table. Without it, every real approval shows “owner needed”. Known approval gates and the role matrix stay as they are. Only the people assignments, eligibility and separation rules are missing.",
    where="Decisions meeting (approvals worksheet); then Setup › Roles. Owners: the prescribed approval owners and the identity administrator.",
    procs=P("D05"),
    hold="Every real human approval or verdict (decisions are evaluated against the configured role).",
    works="Drafting, evidence, agent work, review routing and all screens.",
    status=OPEN, basis=[SRC],
    refs="D05.role_principal_assignments, D05.decision_action_matrix; P02 approval.route; gaps-d line 171")

add(area="ppl", key="PPL-5",
    q="Delegation and absence: which roles may delegate, to whom, up to what authority, and what proof of absence is needed?",
    means="The delegation screen is built but grants nothing until PSL sets the rules. A wrong default would give someone authority.",
    where="Setup › Delegation. Owners: the prescribed approval owners.",
    procs=P("D05"),
    hold="Creating real delegations.",
    works="Viewing delegations and every non-delegated decision.",
    status=OPEN, basis=[SRC],
    refs="D05.delegation_rules; F-27 readiness and spec; gaps-a G-SCR13A-1..6")

add(area="ppl", key="PPL-6",
    q="When a document changes in a way that does not affect cost, which earlier approvals still stand?",
    means="Cost-changing revisions already repeat the costing chain. For other changes, PSL decides which approvals carry over. Until then the factory asks again.",
    where="Decisions meeting. Owners: the prescribed approval owners.",
    procs=P("D05"),
    hold="Reusing an approval after a revision.",
    works="New approvals on the new version.",
    status=OPEN, basis=[SRC],
    refs="D05.revision_invalidation_rules (operation decision.reuse_after_revision)")

add(area="ppl", key="PPL-7",
    q="What do Return, Reject and Withdraw do on each line? Does a return create a “correct and resubmit” task for the preparer? Are earlier reviews kept or reopened? Who may withdraw an approval?",
    means="Most review steps offer Return and Reject. The proposal is that every return creates a correct-and-resubmit task. Today, accounts, schedules and the shared engine behave differently.",
    where="Decisions meeting. Owner: business owner with the backend developer.",
    procs=[],
    hold="The defined consequences of Return, Reject and Withdraw. The screens are built on a working assumption.",
    works="Approve paths and the return note itself.",
    status=OPEN, basis=[ENG],
    refs="D-RETURN; gaps-b G-26-10, G-40-7; gaps-f SP-3, lines 68 and 92")

add(area="ppl", key="PPL-8",
    q="Who receives an “ask for access” request (for example to see staff-cost totals), and what may they grant?",
    means="An access request notifies someone and grants nothing by itself. PSL decides who receives it.",
    where="Setup › Rules. Owner: HR Lead (for payroll), otherwise PSL leadership.",
    procs=[],
    hold="The “Ask for access” button in the assistant.",
    works="Everything else in the assistant.",
    status=OPEN, basis=[ENG],
    refs="gaps-a G-SCR05-5")

add(area="ppl", key="PPL-9",
    q="Must every change to a Setup rule carry proof (for example a signed note)?",
    means="Rules decide authority, so PSL may want evidence for each change. Today proof is optional.",
    where="Decisions meeting. Owner: PSL leadership.",
    procs=[],
    hold="Nothing. Rule saves work with optional proof.",
    works="All Setup rules.",
    status=OPEN, basis=[ENG],
    refs="OVERNIGHT-DECISIONS D-15c; F-11")

add(area="ppl", key="PPL-10",
    q="How do people sign in, reset a password and finish setting up an invited account?",
    means="Sign-in is a security boundary. The model names the backend developer as owner, while the overnight log lists the sign-in method for PSL.",
    where="Decisions meeting. Owner: backend developer with PSL.",
    procs=[],
    hold="The sign-in screen, account menu, sign-out and invite set-up.",
    works="Everything behind sign-in (tested on the mock).",
    status=OPEN, basis=[ENG],
    refs="D-SIGNIN; D-AUTH; OVERNIGHT-DECISIONS “For PSL”")

# ---------------- Notifications & templates ----------------
add(area="ntf", key="NTF-1",
    q="WhatsApp and email: which WhatsApp Business number and provider, which Meta-approved message templates, which staff numbers with opt-in, and which email provider and sender?",
    means="Alerts by WhatsApp and email are decided. PSL owns the accounts. Until they are set up, every send runs on a mock and nothing reaches a person.",
    where="Decisions meeting; then alert settings. Owner: business owner with the backend developer.",
    procs=[],
    hold="Every real WhatsApp or email send: alerts, client messages, reminders and department requests.",
    works="In-app notifications, the bell, alert preferences and every drafted message.",
    status=OPEN, basis=[ENG],
    refs="D-ALERT-PROVIDERS; scope I-03; D11.adapter_configuration_refs; INT.provider_readiness")

add(area="ntf", key="NTF-2",
    q="Please supply PSL's real document templates (SOW, invoice, go-live document, minutes, reports, submission forms).",
    means="Every document uses a clearly labelled test template meanwhile. Money templates leave amounts, tax and terms blank. Real templates are uploaded as new versions. Documents already sent keep the template they used.",
    where="Setup › Templates. Owner: PMO Lead and Finance Lead (their own documents).",
    procs=["P10", "P11", "P52"],
    hold="Nothing is blocked, but every document carries “TEST TEMPLATE”. See COM-6 on sending test-template packs.",
    works="All document drafting and review.",
    status=PART, basis=[SRC],
    refs="D11.template_storage_retention_rules; F-20; product decision 7 Nov")

add(area="ntf", key="NTF-3",
    q="Who receives each published document and report, and what may each recipient see?",
    means="Publishing needs named recipients and grants. Without them, documents are drafted and reviewed but not published.",
    where="Setup › Rules. Owners: PMO, Finance and repository owners.",
    procs=ALL122,
    hold="Publishing a document or accepted Finance output to recipients.",
    works="Drafting, review and verification of each document.",
    status=OPEN, basis=[SRC],
    refs="D11.recipient_grant_refs (operations document.publish, finance.accepted.publish)")

add(area="ntf", key="NTF-4",
    q="How do internal reports (management accounts, cash forecast, BU totals, leadership report) reach internal and group recipients?",
    means="Client messages and alerts have a channel. Internal reports with amounts have none, and alerts may not carry amounts.",
    where="Decisions meeting. Owner: Finance Lead with PMO Lead.",
    procs=["F43", "P42"],
    hold="Sending internal reports.",
    works="Preparing and reviewing those reports.",
    status=OPEN, basis=[ENG],
    refs="suggested D-REPORT-DELIVERY; BACKEND-HANDOFF priority 7; G-C-7; F-35 question 4")

add(area="ntf", key="NTF-5",
    q="Does PSL have a brand guide?",
    means="The design engineer recorded that PSL has none, so the visual identity is created in design. PSL should confirm this.",
    where="Design review. Owner: PSL leadership.",
    procs=[],
    hold="Nothing.",
    works="Everything.",
    status=CONF, basis=[ENG],
    refs="interview Q-03, Q8; interview line 44 still lists it as open")

add(area="ntf", key="NTF-6",
    q="Can the agent mascots be called Tola (PMO), Chidi (Finance) and Zainab (HR)? Please confirm no staff member shares these names.",
    means="Agents must never be confused with people.",
    where="Design review. Owner: PSL leadership.",
    procs=[],
    hold="Final mascot exports.",
    works="Everything.",
    status=OPEN, basis=[ENG],
    refs="memory: mascots, 12 Nov")

# ---------------- Other ----------------
add(area="oth", key="OTH-1",
    q="Working calendar and deadline clocks: time zone, working days and holidays, when each clock starts and pauses, the exact value where sources say “1-2 working days”, the meeting hour and report day, SLA notice clauses and billing dates?",
    means="The Tuesday, weekly, monthly, 24-hour and 48-hour rules are known. Without the calendar, the factory cannot say a task is overdue or an SLA is breached.",
    where="Setup › Rules (calendar). Owners: PMO and the relevant service or agreement owners.",
    procs=P("D04"),
    hold="Overdue, SLA and schedule determinations.",
    works="All work items. Dates are shown as recorded.",
    status=PART, basis=[SRC],
    refs="D04 (iana_timezone, working_calendar_ref, clock_anchor_pause_rules, deadline_parameters)")

add(area="oth", key="OTH-2",
    q="Which AI model provider may agents and the assistant use, with which data, in which regions, and for how long may data be kept?",
    means="Real cases refuse unapproved providers. Agents run on a synthetic provider until PSL approves one.",
    where="Decisions meeting. Owner: business owner with the backend developer.",
    procs=[],
    hold="Agent work and assistant answers on real cases.",
    works="Every screen and workflow, with sample agent output.",
    status=OPEN, basis=[ENG],
    refs="D-AGENT-PROVIDER; INT.agent_data; design 1 Nov “Data and model use”")

add(area="oth", key="OTH-3",
    q="Which actions may agents take on their own, within which reversible limits, and who can stop them in an emergency?",
    means="Agents draft, check and follow up today. People decide. Any wider autonomy needs PSL's explicit limits.",
    where="Decisions meeting. Owner: PSL leadership with the CTO.",
    procs=[],
    hold="Any agent action beyond drafting and checking.",
    works="Current agent work.",
    status=OPEN, basis=[ENG],
    refs="design 1 Nov “Decisions needed”: Autonomy and risk")

add(area="oth", key="OTH-4",
    q="May the assistant offer speech input (“Speak your request”)?",
    means="Browser speech recognition can send audio to a third party. Options: leave it off, use an approved local engine, or remove it.",
    where="Decisions meeting. Owner: business owner.",
    procs=[],
    hold="The microphone button.",
    works="Typed requests.",
    status=OPEN, basis=[ENG],
    refs="D-SPEECH-INPUT")

add(area="oth", key="OTH-5",
    q="How much work flows through each line per month (volumes)?",
    means="PSL said “a lot of work”. Real numbers help size lists, alerts and review load.",
    where="Decisions meeting. Owner: PMO Lead and Finance Lead.",
    procs=[],
    hold="Nothing.",
    works="Everything.",
    status=OPEN, basis=[ENG],
    refs="memory: product decisions 7 Nov")

add(area="oth", key="OTH-6",
    q="Who validates the documented workflows with process users and accepts them, and what are the acceptance criteria?",
    means="PSL's process includes validating workflows and automation with the people who use them. Acceptance must come from PSL owners, not from engineering.",
    where="Acceptance sessions. Owners: process owners (PSL to name).",
    procs=["P13", "P15", "B13"],
    hold="Owner review and acceptance of validated workflows.",
    works="Capturing validation evidence.",
    status=OPEN, basis=[SRC],
    refs="AF13.owner_validation_rules, AF13.acceptance_rules, AF13.protection_acceptance_rules, AF13.protection_owner_rules")

add(area="oth", key="OTH-7",
    q="Who may run recovery, restore and data-protection operations, and what recovery targets apply?",
    means="These are operator controls for running the factory safely. No recovery targets or operators are assumed.",
    where="Decisions meeting. Owner: CTO with PSL leadership.",
    procs=[],
    hold="Real recovery, restore and protection actions.",
    works="Day-to-day work.",
    status=OPEN, basis=[ENG],
    refs="OPS.* (operator, protection, recovery, factory execution components); INT.* readiness components")

add(area="oth", key="OTH-8",
    q="What evidence proves that records migrated from existing tools are complete and correct?",
    means="Migration must be checked against PSL's own evidence before old records are trusted.",
    where="Decisions meeting. Owners: PMO, Finance and repository owners.",
    procs=ALL122,
    hold="Validating a migration.",
    works="New work in the factory.",
    status=OPEN, basis=[SRC],
    refs="D11.migration_evidence_rules")

add(area="oth", key="OTH-9",
    q="BaaS (deferred from this release): the Support SOP, reconciliation brief, queue states and commands, onboarding stages, and the support case-flow rules.",
    means="These 14 BaaS processes are kept but not built in this release. PSL's answers will be needed when BaaS starts.",
    where="Later release. Owners: Support, Reconciliation and Engineering owners.",
    procs=P("D09") + ["B14"],
    hold="BaaS queue writes, financial corrections and support flow (deferred anyway).",
    works="All PMO and Finance work in this release.",
    status=OPEN, basis=[SRC],
    refs="D09 (support_sop_ref, reconciliation_contract_ref, queue_state_command_map, onboarding_stage_catalogue); B14.* support components")

# ---------------- Top blocking ----------------
TOP = [
    ("PPL-4", "Every real human approval in PMO and Finance"),
    ("OTH-1", "Overdue, SLA and schedule judgements"),
    ("NTF-3", "Publishing any document or accepted output"),
    ("COM-1", "Any cost or price calculation; SOW price"),
    ("FIN-1", "Stage invoices for each contract"),
    ("FIN-5", "Recording and allocating payments received"),
    ("FIN-8", "Calculating and publishing management accounts"),
    ("PAY-1", "All payroll rows and BU staff figures outside HR"),
    ("NTF-1", "Every real WhatsApp and email send"),
    ("PPL-7", "Return and Reject results on most review steps"),
    ("FIN-4", "Payment assessment and exception approval"),
    ("PPL-3", "Assigning roles, inviting and deactivating staff"),
]

DECIDED = [
    ("Planning and costing come before the client signs the SOW.", "PSL (U01, 19 Oct)", "D02, resolved"),
    ("PMO marks a milestone complete; Finance then invoices and records payments. Finance does not approve milestone completion.", "PSL (U03)", "D11, partly"),
    ("Three payment stages: after signed SOW, at UAT and at completion. No default split.", "PSL (U04)", "D12, partly"),
    ("Clients may pay irregularly between stages; PMO needs to see what is owed.", "PSL (U05)", "D14, partly"),
    ("A payment exception may allow deployment below the stated payment expectation; it must be approved by a human. It never erases debt.", "PSL (U07, U08)", "D13, partly"),
    ("The requested document and evidence tooling does not exist yet; this product provides it.", "PSL (U02)", "D11, partly"),
    ("Head of PMO and PMO Lead are one role; screens say PMO Lead.", "PSL, confirmed 13 Nov", "D-ROLE-PMO"),
    ("Commercial approval order: PM, then PMO Lead, then CEO (CEO last).", "PSL, confirmed 13 Nov", "D-APPROVAL-ORDER"),
    ("The factory is role-based: only the acting role is needed; people are assigned to roles in the app.", "Design engineer, 7 Nov", "product decisions"),
    ("Logged-in roles: PMO, PMO Lead, Finance, Finance Lead, HR, HR Lead, plus CEO and CTO. PM maps to PMO.", "Design engineer, 11-13 Nov", "scope Q-02, Q4"),
    ("CEO and CTO may start every line; mainly they review and approve.", "Design engineer, 13 Nov", "D-LEADERS-START"),
    ("Engineering Lead, QA, Security and Support do not log in; the PM records their part with proof.", "Design engineer, 7 and 13 Nov (final)", "flow-audit conflict C"),
    ("No client portal: staff record client responses (decision, date, contact, proof, attestation) for SOW/PRD, UAT, go-live and change sign-offs.", "Design engineer, 7 Nov", "product decisions"),
    ("Alerts go by WhatsApp and email; decisions are still taken in the app.", "Design engineer, 7 Nov", "product decisions"),
    ("Clearly labelled test templates are used until PSL supplies real ones; money templates leave amounts, tax and terms blank.", "Design engineer, 7 Nov", "product decisions"),
    ("Screens work on phone, tablet and desktop.", "Design engineer, 7 Nov", "product decisions"),
]

# ---------------- rendering ----------------
def esc(s): return html.escape(s, quote=True)

def fmt_ids(ids):
    if not ids: return ""
    seen = []
    for i in ids:
        if i not in seen: seen.append(i)
    def k(i):
        m = re.match(r"([A-Z]+)(\d+)", i); return (m.group(1), int(m.group(2)))
    seen.sort(key=lambda i: ("PFB".index(k(i)[0][0]) if k(i)[0][0] in "PFB" else 9, k(i)[1]))
    out = []; run = []
    def flush():
        if not run: return
        if len(run) >= 3: out.append(f"{run[0]}–{run[-1]}")
        else: out.extend(run)
    for i in seen:
        if run:
            a, b = k(run[-1]), k(i)
            if a[0] == b[0] and b[1] == a[1] + 1:
                run.append(i); continue
            flush(); run.clear()
        run.append(i)
    flush()
    return ", ".join(out)

def proc_text(ids):
    if not ids: return "None directly (applies across the app)"
    if len(set(ids)) >= 120: return "All 122 processes"
    return f"{fmt_ids(ids)} <span class='n'>({len(set(ids))})</span>"

STATUS_CLASS = {OPEN: "st-open", PART: "st-part", CONF: "st-conf"}
BASIS_LABEL = {SRC: "From PSL's documents", ENG: "Engineering proposal awaiting PSL"}

bykey = {e["key"]: e for e in E}
area_counts = {a: sum(1 for e in E if e["area"] == a) for a, _ in AREAS}
status_counts = {s: sum(1 for e in E if e["status"] == s) for s in (OPEN, PART, CONF)}
total = len(E)

def card(e):
    basis = "".join(f"<span class='tag {b}'>{BASIS_LABEL[b]}</span>" for b in e["basis"])
    note = f"<p class='bnote'>{esc(e['basis_note'])}</p>" if e.get("basis_note") else ""
    return f"""
<article class="card" id="{e['key']}">
  <header>
    <span class="key">{e['key']}</span>
    <span class="status {STATUS_CLASS[e['status']]}">{e['status']}</span>
  </header>
  <h3>{esc(e['q'])}</h3>
  <dl>
    <dt>What it means</dt><dd>{esc(e['means'])}</dd>
    <dt>Where it's taken</dt><dd>{esc(e['where'])}<br><span class="proc">Processes: {proc_text(e['procs'])}</span></dd>
    <dt>On hold until then</dt><dd><strong>{esc(e['hold'])}</strong> <span class="keeps">Everything else keeps working, including: {esc(e['works'][0].lower() + e['works'][1:])}</span></dd>
    <dt>Basis</dt><dd>{basis}{note}</dd>
  </dl>
  <p class="ref">Reference: {esc(e['refs'])}</p>
</article>"""

sections = []
for a, title in AREAS:
    cards = "".join(card(e) for e in E if e["area"] == a)
    sections.append(f"<section class='area'><h2><span>{esc(title)}</span><span class='cnt'>{area_counts[a]} decisions</span></h2>{cards}</section>")

top_rows = ""
for i, (k, held) in enumerate(TOP, 1):
    e = bykey[k]
    n = len(set(e["procs"]))
    ptxt = "all 122" if n >= 120 else (str(n) if n else "app-wide")
    short = e["q"].split("?")[0] + "?"
    if len(short) > 150: short = short[:147].rsplit(" ", 1)[0] + "…"
    top_rows += f"<tr><td class='num'>{i}</td><td class='key2'><a href='#{k}'>{k}</a></td><td>{esc(short)}</td><td>{esc(held)}</td><td class='num'>{ptxt}</td><td><span class='status {STATUS_CLASS[e['status']]}'>{e['status']}</span></td></tr>"

area_list = "; ".join(f"{t.split(':')[0]} {area_counts[a]}" for a, t in AREAS)
src_only = sum(1 for e in E if e["basis"] == [SRC])
eng_only = sum(1 for e in E if e["basis"] == [ENG])
both = total - src_only - eng_only

dec_rows = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td class='refc'>{esc(c)}</td></tr>" for a, b, c in DECIDED)

area_toc = "".join(f"<li><span>{esc(t)}</span><span>{area_counts[a]}</span></li>" for a, t in AREAS)

doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSL Decisions Needed</title>
<style>
:root {{
  --ink:#1f2a30; --muted:#5d6b73; --faint:#8a969c; --line:#d9dfe2; --paper:#ffffff; --wash:#f4f6f5;
  --accent:#2f6f6a; --accent-wash:#e5efed;
  --open:#9a4a2a; --open-wash:#f7e9e2; --part:#8a6a12; --part-wash:#f6efd9; --conf:#2f5d86; --conf-wash:#e3edf6;
  --src:#2f6f6a; --src-wash:#e5efed; --eng:#5b4a86; --eng-wash:#ece8f4;
}}
@page {{ size: A4; margin: 16mm 15mm 16mm 15mm; }}
* {{ box-sizing: border-box; }}
html, body {{ background: var(--paper); color: var(--ink); }}
body {{ margin:0; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.45; }}
a {{ color: var(--accent); text-decoration: none; }}
.page {{ max-width: 180mm; margin: 0 auto; }}
.cover {{ }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .12em; font-size: 8pt; color: var(--accent); font-weight: 700; margin-top: 4mm; }}
.cover h1 {{ font-size: 28pt; line-height: 1.1; margin: 6mm 0 3mm; font-weight: 700; letter-spacing: -.01em; }}
.date {{ color: var(--muted); font-size: 11pt; margin-bottom: 6mm; }}
.summary {{ font-size: 10pt; line-height: 1.55; max-width: 160mm; }}
.stats {{ display:grid; grid-template-columns: repeat(4, 1fr); gap: 4mm; margin: 6mm 0 5mm; }}
.stat {{ background: var(--wash); border-radius: 3mm; padding: 3mm 4mm; }}
.stat b {{ display:block; font-size: 17pt; line-height:1.1; }}
.stat span {{ font-size: 8.5pt; color: var(--muted); }}
.toc {{ list-style:none; padding:0; margin: 0; columns: 2; column-gap: 8mm; font-size: 9pt; }}
.toc li {{ display:flex; justify-content:space-between; border-bottom: 1px solid var(--line); padding: 1.6mm 0; break-inside: avoid; }}
.toc li span:last-child {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
.cover .foot {{ margin-top:3mm; font-size: 7.5pt; color: var(--faint); }}
.howto {{ border: 1.5px solid var(--accent); background: var(--accent-wash); border-radius: 3mm; padding: 4mm 6mm; margin-top: 7mm; break-inside: avoid; font-size: 9.2pt; }}
.howto h2 {{ margin: 0 0 2mm; font-size: 13pt; }}
.howto p, .howto li {{ margin: 1.2mm 0; }}
.howto ul {{ padding-left: 5mm; margin: 2mm 0; }}
h2 {{ font-size: 15pt; margin: 0 0 4mm; }}
.toppage {{ break-before: page; break-after: page; }}
.toppage p.lead {{ color: var(--muted); margin: 0 0 4mm; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.6pt; }}
th {{ text-align:left; font-size: 7.5pt; text-transform: uppercase; letter-spacing:.06em; color: var(--muted); border-bottom: 1.5px solid var(--ink); padding: 1.6mm 1.6mm; }}
td {{ border-bottom: 1px solid var(--line); padding: 1.8mm 1.6mm; vertical-align: top; }}
td.key2 {{ white-space: nowrap; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
tr {{ break-inside: avoid; }}
.area {{ break-before: page; }}
.area h2 {{ display:flex; justify-content:space-between; align-items: baseline; border-bottom: 2px solid var(--accent); padding-bottom: 2mm; margin-bottom: 5mm; }}
.area h2 .cnt {{ font-size: 9pt; color: var(--muted); font-weight: 400; }}
.card {{ border: 1px solid var(--line); border-left: 3px solid var(--accent); border-radius: 2mm; padding: 3.5mm 4.5mm 3mm; margin: 0 0 4mm; break-inside: avoid; background: var(--paper); }}
.card header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom: 1.5mm; }}
.key {{ font-size: 8pt; font-weight: 700; color: var(--accent); letter-spacing: .06em; }}
.status {{ font-size: 7.5pt; font-weight: 700; padding: .6mm 2.2mm; border-radius: 10mm; white-space: nowrap; }}
.st-open {{ color: var(--open); background: var(--open-wash); }}
.st-part {{ color: var(--part); background: var(--part-wash); }}
.st-conf {{ color: var(--conf); background: var(--conf-wash); }}
.card h3 {{ font-size: 10.5pt; line-height: 1.4; margin: 0 0 2.5mm; font-weight: 700; }}
dl {{ display:grid; grid-template-columns: 30mm 1fr; column-gap: 4mm; row-gap: 1.6mm; margin: 0; }}
dt {{ font-size: 7.5pt; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); padding-top: .5mm; font-weight: 700; }}
dd {{ margin: 0; }}
dd strong {{ font-weight: 600; }}
.keeps {{ display:block; color: var(--muted); margin-top: .8mm; }}
.proc {{ display:block; color: var(--muted); font-size: 8.6pt; margin-top: .6mm; }}
.n {{ color: var(--faint); }}
.tag {{ display:inline-block; font-size: 7.5pt; font-weight: 700; padding: .4mm 2mm; border-radius: 1mm; margin: 0 1.5mm .6mm 0; }}
.tag.src {{ color: var(--src); background: var(--src-wash); }}
.tag.eng {{ color: var(--eng); background: var(--eng-wash); }}
.bnote {{ margin: .8mm 0 0; color: var(--muted); font-size: 8.6pt; }}
.ref {{ margin: 2.5mm 0 0; padding-top: 1.6mm; border-top: 1px dashed var(--line); font-size: 7.3pt; color: var(--faint); font-family: "SF Mono", Menlo, Consolas, monospace; word-break: break-word; }}
.appendix {{ break-before: page; }}
.appendix p.lead {{ color: var(--muted); }}
td.refc {{ color: var(--faint); font-size: 7.6pt; white-space: nowrap; }}
.legend {{ display:flex; gap: 3mm; flex-wrap: wrap; margin-top: 2mm; }}
@media screen {{ body {{ background: var(--wash); }} .page {{ background: var(--paper); padding: 16mm 15mm; margin: 8mm auto; box-shadow: 0 1px 4px rgba(0,0,0,.08); }} }}
@media screen and (max-width: 700px) {{ .page {{ padding: 16px; margin: 0; }} dl {{ grid-template-columns: 1fr; }} .stats {{ grid-template-columns: repeat(2,1fr); }} .toc {{ columns: 1; }} }}
</style></head>
<body><div class="page">

<section class="cover">
  <div class="eyebrow">PSL Product Studio · Operations factory</div>
  <h1>Decisions PSL needs to take</h1>
  <div class="date">18 November 2026 · prepared for PSL by the design engineer</div>
  <p class="summary">The factory is built to run while these business decisions are open. Each missing answer holds only the exact operation that depends on it; all other work keeps going. This pack lists <b>{total} decisions</b> PSL still has to take: {status_counts[OPEN]} open, {status_counts[PART]} partly answered and {status_counts[CONF]} answered but awaiting PSL's confirmation. {src_only + both} come from PSL's own documents ({both} of them also include engineering proposals), and {eng_only} are engineering proposals awaiting PSL. They cover the 13 open decision groups in the policy guide (D01 and D03 to D14; D02 is resolved), the separate costing-rule question, the Setup rules shown as “Not set”, and the open questions raised while building the screens. Duplicates across sources are merged into one entry. Decisions already taken are listed in the appendix.</p>
  <div class="stats">
    <div class="stat"><b>{total}</b><span>decisions in this pack</span></div>
    <div class="stat"><b>{status_counts[OPEN]}</b><span>open</span></div>
    <div class="stat"><b>{status_counts[PART]}</b><span>partly answered</span></div>
    <div class="stat"><b>{status_counts[CONF]}</b><span>answered, awaiting confirmation</span></div>
  </div>
  <ul class="toc">{area_toc}</ul>
<div class="howto">
  <h2>How to read this</h2>
  <p>Each card is one decision. It shows:</p>
  <ul>
    <li><b>The decision</b>: the question PSL must answer, in bold at the top.</li>
    <li><b>What it means</b>: why it matters and what changes once it is answered.</li>
    <li><b>Where it's taken</b>: the screen, Setup page or meeting; the PSL role that owns it; the process IDs it affects.</li>
    <li><b>On hold until then</b>: the exact operation that waits. Everything else keeps working.</li>
    <li><b>Status</b>: <span class="status st-open">Open</span> <span class="status st-part">Partly answered</span> <span class="status st-conf">Answered, awaiting PSL confirmation</span></li>
    <li><b>Basis</b>: <span class="tag src">From PSL's documents</span> means the question comes from PSL's own SOPs, testimony or confirmed clarifications. <span class="tag eng">Engineering proposal awaiting PSL</span> means the build team raised it, so it is not a PSL fact.</li>
  </ul>
  <p>Owner roles are roles, never named people. Where a card says “proposed owner”, PSL should confirm the role. Sample names, amounts and roles on design boards are not answers. The grey <b>Reference</b> line lists the internal IDs, so the build team can trace each answer.</p>
</div>
  <div class="foot">Sources: guide/10-POLICY-CONFIGURATION.md; contracts/policy-slots.json, decision-registry.json and *-policy-components.json; architecture/model.json; BUILD-DECISIONS.md; delivery/BACKEND-HANDOFF.md and backend-handoff/*.md; delivery/features/*/readiness.md and spec.md; docs/design/2026-11-01 component design; scope/scope.md and interview.md; product decisions of 7–13 Nov 2026. No rate, amount, approver or deadline in this pack is a PSL fact unless it is marked “From PSL's documents”.</div>
</section>


<section class="toppage">
  <h2>Top decisions blocking the most work</h2>
  <p class="lead">Ranked by how much live work each one holds: how many processes depend on it and how many screens wait. Answering these first releases the most.</p>
  <table>
    <thead><tr><th>#</th><th>Card</th><th>Decision</th><th>What stays on hold</th><th>Processes</th><th>Status</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>
</section>

{''.join(sections)}

<section class="appendix">
  <h2>Appendix: already decided</h2>
  <p class="lead">These are settled and are not to be asked again. Items marked “design engineer” were decided on PSL's behalf for the build. PSL may still revisit them, but they do not hold any work.</p>
  <table>
    <thead><tr><th>Decision</th><th>Decided by</th><th>Reference</th></tr></thead>
    <tbody>{dec_rows}</tbody>
  </table>
</section>

</div></body></html>
"""
open(OUT, "w").write(doc)
print("entries", total, area_counts, status_counts, "src", src_only, "eng", eng_only, "both", both)
