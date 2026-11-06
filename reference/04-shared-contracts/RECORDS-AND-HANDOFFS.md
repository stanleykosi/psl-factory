# Shared records and handoffs

Version 0.2 · 19 October 2026

## In plain language

The departments should pass a clearly identified piece of work to one another, not repeatedly re-create the same facts. Each handoff needs to say what changed, which approved version it refers to, who must act next and whether the receiving team actually received it. The source owner still decides what the fact means. For example, Finance receiving a completed milestone does not mean an invoice was issued or revenue was recognised.

The records and contracts below are **proposed design**, not a claim about installed software or approved field requirements. The authority boundaries are supported by the listed sources; exact fields, permissions and lifecycle rules need owner validation.

## Shared vocabulary

- **Authoritative record:** the record its business owner treats as the source of truth.
- **Reference:** a pointer to a record owned elsewhere. It does not transfer ownership.
- **Version:** an identifiable snapshot. Approval of one version does not automatically approve changed content.
- **Receipt:** evidence that a handoff reached its destination. It is not necessarily business acceptance.
- **Idempotency:** receiving the same event twice must not create two business effects.
- **Reconciliation:** checking that all expected items are present and match their sources, with differences explained.
- **Decision oracle:** an independently agreed expected result used to assess a test. A generated calculation cannot validate itself.
- **Safe fallback:** continue the existing authorised manual process while the proposed automation is unavailable or unverified.

## Record catalogue

### R01 Client and business relationship reference

Used by B08–B12, F28–F34, F45 and PMO engagement/project records. Proposed fields: source system, source client ID, display name, relevant service/product, active period, owner and permitted audience. Business-line client/service coverage (F45) is a proposal. Do not merge similarly named clients without owner review or assume one contract covers all business lines. Client contacts, signatories and recipients require separate purpose-specific authority.

### R02 Engagement, RFP and project references

P03/P16 establish engagement and formal project registration; P45–P49 establish RFP flow and Route A conversion. Proposed links: engagement ID, RFP ID when applicable, project ID, route, PM assignment, current phase and source-system URL. Incumbent PMO ownership must be inspected before designing a second master. Route B/C records must not acquire invented RFP gates. Source: PMO SOP phases 1–2, pp.2–5 and §6, pp.9–10.

### R03 Requirement, estimate and signed commercial baseline

Connect P06–P09, P17–P26 and P46–P48. Keep requirement version, Engineering estimate and Security estimate separate; link approved costing and the client-signed SOW/PRD. Proposed fields include the artefact owner, version, approval evidence and applicable project. Rates, tax, margin and rounding are not supplied. A later Planning baseline that differs from a signed SOW is an unresolved business decision, not permission to amend the agreement. Source: SOP phase 1 steps 2–7, pp.2–3; phase 2 steps 5/8/9, pp.4–5.

### R04 Approval decision and external prerequisite receipt

P09/P48 have the serial PM → Head of PMO → CEO costing chain. Other approvals can have different subjects and no prescribed ordering. Proposed decision fields: subject ID/version, policy reference, decision role, verified actor, outcome, timestamp, reason and evidence reference. An external prerequisite receipt records a decision owned by Design, Engineering, QA or Security; it does not give PMO that decision authority. Delegation, dual-role handling, withdrawal and rejection/resubmission need owner decisions. Source: SOP §§7–8, pp.10–11; register Approval rules.

### R05 Milestone and Finance handoff

Serves P12/P20/P26/P34/P39 and F33–F34. Distinguish planned milestone, observed completion, signed baseline, notification event and Finance response. Do not use one status field to stand for all five. Finance-owned invoicing, recognition and collection remain downstream. See H01 below. Source: SOP phase 1 step7 p.3, phase2 step9 p.5, phase3 step10 p.7, phase4 steps5–6 p.8.

### R06 Financial import, mapping, adjustment and report run

Serves F01–F15/F23–F27/F44. QuickBooks remains the stated accounting source; its edition/API is unknown. Proposed snapshot fields: source/version, entity, accounting period, extract time, row count and fingerprint. Mapping and adjustment versions need separate Finance ownership and explanatory evidence. F12 manual finer breakdown must distinguish disaggregation of an existing total from a genuinely additive adjustment; do not count the same income twice. A report run refers to immutable input versions and approved rules; it is not a new ledger. Missing account mappings must remain visible rather than being silently represented as true zero. Primary extract evidence: FIN P0039/P0097–P0109/P0111–P0121; video-derived observations V01–V14 in the source review addendum. Native workbooks and full calculation policies remain unavailable. Observed note totals divide by 1,000 while selected detailed-income/BU links multiply by 1,000; do not generalise these unit conventions without account-level evidence.

### R07 Restricted staff and allocation input

Serves F16–F22/F35. Separate HR's staff/BU facts from Finance's allocation method and two payroll inputs. Proposed minimum identifiers, period and allocation-driver fields require HR/Finance approval. Do not expose raw payroll to a shared project screen. Historical BU membership, executive exceptions and pooled-cost allocation cannot be inferred from current headcount. Primary extract evidence: FIN P0058–P0069/P0113–P0121; Finance machine transcript U0274–U0304/U0342–U0367/U0531–U0577. Two payroll inputs are described, not two assumed reporting periods. The private allocation calculation was withheld. Headcount pooling and person-specific ratios are distinct; neither approved ratios nor OPEX basis can be inferred.

### R08 Usage, pricing and invoice-preparation batch

Serves B11–B12/F28–F30/F45. Retain usage source/period, client/service identity, approved price version and calculation evidence separately from the invoice generated by the incumbent Power Automate flow. Unknown currency/rounding/discount/tax rules are blocked decisions. A corrected usage batch supersedes or adjusts its predecessor through an agreed process; replay must not create a second invoice. Primary extract evidence: TEM P0007–P0013; FIN P0013–P0025; Finance machine transcript U0034–U0083. Price-inclusive BaaS reporting is proposed; the existing Power Automate work is described, not inspected. Actual flow definition, pricing inputs and billing policies remain pending.

### R09 Receivable and cash expectation

Serves F31–F43. A receivable, expected collection date, cash forecast item and actual bank receipt are different records. Forecast versions preserve the assumptions management considered. Payment execution is not authorised by a forecast. Internal and group reports need distinct allowed audiences/content; actual publication rules remain unresolved. Primary extract evidence: FIN P0048/P0070–P0078/P0127–P0129 and Finance machine transcript U0369–U0411/U0617–U0646. The forecast explicitly omits some receivables; it cannot prove ledger completeness. Group/internal report distinction is supported by FIN P0127; part of the corresponding audio was muted.

### R10 Support case, reconciliation request and corrective-action reference

Serves B01–B07/B14. Keep customer complaint identity, settlement investigation and Engineering's corrective action distinct but linked. Current multichannel handling is not proof of an installed ticket lifecycle. Proposed case states, clocks and ownership must be approved. No proposed automation should move funds merely because a case was labelled resolved. Primary extract evidence: BAAS P0016/P0020/P0030/P0032/P0034/P0051/P0053; TEM P0015–P0035. Settlement success precedes the corrective request in the described example. No post-action verification was demonstrated. B07 remains second-hand description and needs the reconciliation owner; the referenced Support SOP and Recon brief are still absent.

### R11 Issue, risk, incident and change references

P50–P62 require related but distinct records. Issue entries need an owner/next action; Security owns the risk register; Engineering owns incidents; GLPI is deployment approval authority. Proposed linking fields: source system, external ID, record type, project/release reference, owner and permissioned status. A central view must not overwrite the external lifecycle. Emergency authorisation versus GLPI remains unresolved. Source: SOP §§9.1–9.2 pp.12, §§9.9–9.10 pp.15–17.

### R12 Document, template, meeting and report version

Serves P10–P11/P36/P40–P43/P52–P53. Link template/version, author/owner, audience, source records, review decision and distributed version. A document's formatting compliance does not prove factual accuracy. Client-safe projection excludes internal commentary and raw logs; do not create it by merely copying an internal report. Source: SOP §§5.2–5.5 pp.8–9 and §§9.3–9.8 pp.12–15.

## Handoff contracts

### H01 PMO to Finance: one connected chain

**Source facts:** PM shares signed SOW costs/milestones; the plan shares milestones; completed milestones are recorded and notified; closure confirms that every milestone was notified. Finance invoices or follows up. P12 is the umbrella, P34 completion notification, F34 receiving-side integration proposal. F33's recognition evidence remains a separate Finance decision.

**Additional Finance evidence:** FIN P0062–P0066 and Finance machine transcript U0306–U0341 describe Finance phoning PMs because the existing PMO tool does not expose needed price/progress information. A Finance layer and completion notifications were proposed, not demonstrated. Cash receipt alone does not establish recognized monthly revenue; spoken progress percentages are examples, not an approved recognition formula. This current-practice account does not repeal the later PMO SOP.

**Proposed payload:** event ID; event type (signed baseline, plan milestone, completion, correction); stable engagement/business-subject reference; formal project ID once assigned in Planning; milestone source ID when applicable; signed baseline version; effective date; event recorded time; sender role; evidence references; related prior event for corrections. Initiation's signed-baseline sharing must not wait for the formal project ID that the SOP assigns in Planning. Link that ID later without rewriting the original handoff. Amount/currency/due-date fields appear only when Finance confirms they are necessary and identifies their source. Do not duplicate sensitive commercial fields in broad notifications.

**Proposed delivery states:** prepared → validated → queued → sent → acknowledged. Add failed/retry-required, outcome-unknown, rejected and superseded states. These are technical delivery states, not project or accounting states. A timeout after possible acceptance stays outcome-unknown until checked. Never label it failed and blindly resend.

**Proposed recovery:** use a stable event ID for retries; compare destination receipt before replay; preserve original event and issue a linked correction; quarantine out-of-order completion whose baseline is absent; escalate unresolved rejection to named PM/Finance owners. Owner decisions: delivery endpoint, receipt versus business acknowledgement, retry times, correction authority, financial effects and escalation timing.

**Acceptance examples:**
1. Synthetic PROJ-001, baseline SOW-v1, milestone MS-01 complete. The Finance test inbox receives one event with correct IDs/evidence. No invoice, journal or payment is created.
2. Deliver the same event twice. Exactly one inbox item/business effect exists and both attempts are traceable.
3. Destination accepted, sender timed out. The item remains uncertain until checked; recovery finds the receipt instead of duplicating it.
4. Completion arrives before the signed baseline. Hold for reconciliation; do not invent baseline details.
5. Correction points to MS-01's earlier event. Preserve the earlier evidence and show which event supersedes it; Finance decides accounting treatment.
6. Client signatures complete at Initiation exit while only engagement ENG-01 exists. Share the baseline against ENG-01; after Planning assigns PROJ-01, link it to the same engagement/event without delaying or duplicating the original handoff.

These expected technical behaviours are proposed safeguards; Finance must approve their business contract before implementation.

### H02 Data/BaaS to Finance: usage and rate preparation

Input suppliers provide period-specific usage; Finance combines it with client pricing and the incumbent invoice-generation work. Proposed acceptance checks: all expected clients/periods accounted for, duplicate usage identified, unknown prices held, corrected batches traceable. H01 project pricing is not reused as the BaaS tariff model. A missing rate must not become zero or trigger customer billing. Decisions: actual usage schema, price authority/effective dates, taxes/rounding, correction/rebilling and Power Automate interface.

### H03 HR to Finance: staff facts and allocations

HR supplies staff/BU information; Finance combines payroll and attribution/allocation rules. Proposed transfer uses minimum approved fields, period and stable employee references, restricted access and row/control totals. Missing/multiple staff matches produce an exception, not a guessed BU assignment. Decisions: payroll input owners, join key, leavers/joiners, historical membership, executive exceptions and access/retention.

### H04 Owning delivery teams to PMO: prerequisite receipts

Design, Engineering, QA and Infrastructure retain their approvals. A proposed approval-prerequisite receipt binds subject and version/build to issuer and the prescribed decision evidence. A status reference is a different type: P51 risk and P55 incident references point to the owning R11 records and do not require an invented PMO decision or approval receipt. Decision fields are conditional on an actual prescribed decision. A green dashboard label is not a QA exit or Engineering Go/No-Go. Unknown or mismatched versions remain unverified. Decisions: source tools, accepted evidence, freshness and invalidation/revalidation rules.

### H05 Internal reporting to external recipient

Source rules require PMO Lead review of external documents and removal of internal-only material. Proposed publisher checks the reviewed exact version and approved audience. A newer draft must not inherit review without a confirmed revision policy. Delivery records do not prove the recipient read/accepted the report. Decisions: publisher, recipients, channel, retention and re-review rules.

### H06 Support/Reconciliation to Engineering

BAAS P0020/P0030 directly describe Engineering-mediated corrective credit and fund/queue requests after settlement confirmation in the example; Reconciliation says it lacks queue-add access. Proposed request contains a case/reference, the specific anomaly, investigation evidence and requested action; execution authority stays with the established authorised role. No new money-movement authority is defined. Decisions: required validation/approval, duplicate request handling, rejected requests, execution confirmation and reversal controls.

## Cross-cutting proposed controls

Use only synthetic identities and data in later mocks; keep outbound actions in a sink. Maintain role-scoped visibility, immutable evidence/version references, auditable decisions, detectable duplicate/out-of-order events and explicit unknown outcomes. These are design proposals. Business owners must settle retention, recovery time, service levels, delegation, cancellation, migration and publishing rules. No automatic approval is created by time elapsed or missing evidence.

## Recovered evidence handoff crosswalk

The addendum uses its own H01–H10 labels. Prefix these with SRC-H when discussing them here; they do not replace this package’s stable H01–H06 contract IDs. SRC-H01 maps to package H06; SRC-H03 to H02; SRC-H04/H05 to H03; SRC-H06 to H01. SRC-H02 informs R08 partner-usage reporting; SRC-H07 informs R09 service billing; SRC-H08 informs R06 budget inputs; SRC-H09/H10 inform R09 forecast decisions and audience-specific reports. These latter four flows are not new standalone systems. Source: recovered cross_department_handoffs.csv.
