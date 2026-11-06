# Business decisions and evidence gaps

Fourteen recorded groups: D02 resolved, thirteen wholly/partly open. These are runtime configuration/evidence dependencies, not build restrictions. Implement the workflows, screens, adapters and typed interfaces now. Suggested owner roles in source evidence are routing context, not appointments.

## D01: Emergency deployment versus GLPI and Standard preapproval
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Written reconciliation of emergency authorization and general predeployment GLPI; approved Standard-change catalogue and explicit satisfied/remaining gates.

Known already: Do not infer emergency waiver or blanket preapproval.

Dependent operational behavior: Emergency/Standard production dispatch and inferred GLPI waivers

## D02: Signed SOW before Planning versus Planning inputs forming SOW basis
Status: resolved_by_user.

Resolved source rule; implement planning before signature.

Required evidence: None for the sequence. Actual contract revisions still follow the established change/costing controls.

Known already: Known cost-changing revisions already repeat costing chain; do not ask that again.

Dependent operational behavior: None for the resolved planning/signature sequence.

## D03: Prices versus signing in billing narrative
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Check source recording segment or obtain written confirmation of intended statement plus actual invoice-flow release controls.

Known already: FIN P0023 says prices; VID U0079 says sign. No new signature gate assumed.

Dependent operational behavior: Inferred invoice-release signature gate or actual unknown flow behavior

## D04: Clock and deadline applicability
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: IANA timezone, clock anchors/pauses, holidays/working calendar; exact choice within1–2workingdays; meeting hour/report day; actual SLA notice clauses and billing dates.

Known already: Known Tuesday/weekly/monthly and24h/48h rules are already filled.

Dependent operational behavior: Production schedules/overdue/SLA determinations dependent on missing clock/calendar config

## D05: Identity delegation and decision revisions
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Named role assignments, delegation/absence, dual-role eligibility, reject/return/withdraw authority and non-cost invalidation rules.

Known already: Do not request new approval gates or replace known role matrix.

Dependent operational behavior: Real approvals/delegation/reject/return authority and ambiguous approval reuse

## D06: Native financial imports maps and exact oracles
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Redacted TB/export plus native workbooks, account/BU maps, formula lineage, unit/sign/currency/period conventions, F07/F09/F39 expected examples and missing-match behavior.

Known already: Known chain, exact F23 tie-out and narrated F25 formula are not unknown; observed cells remain narrow.

Dependent operational behavior: Unverified import mappings, financial formulas and purported reconciliation success

## D07: Payroll sources and private allocation workings
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Authorized redacted two-source samples, join/overlap semantics, effective staff/BU history, pool/ratio tables, denominator/monthly/rounding/residual examples.

Known already: Headcount applies to described other-staff pool only; Finance HR-read-only boundary is already established.

Dependent operational behavior: Real payroll joins/allocation/rounding/residual treatment

## D08: Actual invoice flow pricing and correction behavior
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Flow export/environment/run evidence, exact input/output/effects, approved price effective dates/tax/tier/rounding, service billing dates, batch duplicate/correction examples and actual permissions.

Known already: Generation/posting/sending are distinct actions, not invented mandatory approval gates.

Dependent operational behavior: Live invoice adapter actions/pricing/tax/tier/rounding/correction behavior

## D09: Support reconciliation and financial queues
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Referenced Support SOP and Reconciliation brief; redacted settled/pending/failed/corrected examples, identifiers/cutoff, queue commands/states/access and completion evidence; onboarding stage catalogue.

Known already: Do not infer business queue semantics from infrastructure queues or grant direct credit access.

Dependent operational behavior: Business queue writes, financial corrections and unsupported operational transitions

## D10: Historical reporting and forecast controls
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Names/effective dates of added categories; approved restatement/correction treatment; forecast inclusion/opening-balance/partial-receipt rules and exact internal/group projection.

Known already: Forecast is partial, not assumed100% coverage; known annual budget method need not be rediscovered.

Dependent operational behavior: Unapproved historical restatement, forecast inclusion and disclosure projections

## D11: Remaining integration and document configuration
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Named recipients/grants and any remaining external adapter details; controlled document templates, storage/retention, migration and evidence requirements; Engineering hypercare criteria. PMO milestone ownership and absence of requested document tooling are now answered by U02/U03.

Known already: Do not ask which existing document/evidence tool to integrate or whether Finance must approve PMO milestone completion. PSL tooling is requested; PMO establishes completion.

Dependent operational behavior: Unconfigured real recipients/adapters/templates/retention/migration and hypercare interpretation

## D12: Stage schedule and precise trigger evidence
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Approved contract schedule with stage amounts or percentages, currency/tax basis, due terms and rounding; exact completion-stage event; which UAT record establishes the billing trigger. Example signed agreement with invoice/receipt references.

Known already: Three stages, signed-SOW opening trigger, UAT-stage invoice and PMO milestone ownership are already supplied. No50/30/20 default.

Dependent operational behavior: Stage invoice issuance without contract amount/tax/due terms or exact UAT/completion trigger

## D13: Configure human payment exception authority and assessment basis
Status: open_configuration.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Actual authorized human role/principals and delegation evidence when available; approved exception validity/revocation/reassessment rules; agreed payment denominator and qualifying funds basis. Do not enable exception approval before authority is configured.

Known already: Exception capability and human-only approval are confirmed. The user cannot name the role yet; keep UNCONFIGURED without blocking unrelated definition work.

Dependent operational behavior: Payment percentage decision without basis; exception approval/payment waiver/deployment authorization while authority unconfigured

## D14: Receipts allocations and adjustments
Status: open.

Build the complete dependent infrastructure and typed configuration interface now. Missing operational values hold only the specifically dependent transition/calculation, never the whole module.

Required evidence: Verification source and authorized receipt recorder; allocation priority/approval, refunds/credits/write-offs/chargebacks, correction permissions and legal/accounting document requirements. Provide approved examples including unmatched and excess payment.

Known already: Irregular partial payments and Finance responsibility are known. Technical conservation and audit rules do not decide accounting policy.

Dependent operational behavior: Actual receipt verification/allocation/adjustment/refund/write-off effects without approved policy/grants

Record new owner decisions with source, subject/effective scope, actual authority, policy version and tests. Do not reopen answered questions or promote synthetic values into operational policy. Use guide/10-POLICY-CONFIGURATION.md and contracts/policy-slots.json for the plug-in implementation contract.
