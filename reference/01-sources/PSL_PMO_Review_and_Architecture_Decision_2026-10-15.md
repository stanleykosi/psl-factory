# PSL Product Studio
## PMO SOP review, register reconciliation and architecture decision

**Review date:** 15 October 2026  
**New source:** `PMO_SOP_v1.1.pdf`, 17 pages, revised 12 October 2026; document owner: Head of PMO.  
**Baseline:** `PSL_Process_Automation_Register.xlsx` and `PSL_Product_Studio_Automation_and_Architecture_Review.docx`, 11 October 2026.  
**Decision:** Retain the modular operations-hub architecture and Django/PostgreSQL default. Strengthen the workflow, approval, evidence, document-publication and integration boundaries. Proceed to bounded scoping; do not treat the SOP as proof of implementation or as the missing pricing calculator.

## 1. Decision in plain English

PSL should connect the systems it already uses through a small, controlled operations application. It should not replace accounting, rebuild Engineering/QA/Security processes, create another deployment-approval system, or make an AI agent responsible for business approvals.

The PMO SOP materially strengthens the case for this design. It describes a governed project lifecycle, not just a reporting dashboard: client engagement, costing, signatures, planning, delivery, production release, Finance notifications and closure, with separate RFP and change paths. It explicitly preserves other departments' process ownership. [S1, §§2–3; Phases 1–4; §§6–9]

The original recommendation was already a federated model: QuickBooks for accounting, the existing PMO tool for its authoritative project records, useful Power Automate flows retained, and a Django/PostgreSQL hub for verified gaps and cross-system coordination. Azure Container Apps, Entra sign-in and governed Microsoft 365 document/interaction services were conditional defaults, not confirmed licences or deployments. That direction remains appropriate. [S2, §§2, 7, 11]

**What changes:** the hub now needs explicit phase-transition rules, conditional and sequential approval sets, evidence of other teams' sign-offs, version-specific commercial decisions, GLPI references, controlled external-document release, and reliable milestone handoffs. A generic task list or chatbot is insufficient.

**What does not change:** existing authoritative systems remain in place; financial arithmetic is deterministic; people retain approval authority; new external writes require separately agreed scope; AI is optional and bounded. The original Finance, BaaS, HR/payroll and disclosure validation gaps remain open unless the new SOP directly addresses them. [S2, §§5–11]

## 2. Updated process register

| Department | Original entries | Updated entries | Added entries |
|---|---:|---:|---:|
| BaaS | 14 | 14 | 0 |
| Finance | 45 | 45 | 0 |
| PMO | 15 | 63 | 48 |
| **Total** | **74** | **122** | **48** |

The 48 newly extracted PMO entries are **P16–P63**. All original 74 IDs remain. The 15 original PMO entries have been refined in place; **F34** has also been updated because milestone notifications are now an explicit SOP duty, while their software integration remains proposed. All 14 BaaS rows and the other 44 Finance rows retain their original values. These counts are the reconciliation performed in this review against S3.

The main sheet retains its six columns: Entry ID, Department, Workflow group, Process / activity, Classification, and Responsible team in source. Supporting sheets contain the detailed source references, approval rules, open decisions, change log and historical baseline. The workbook contains 64 detailed reconciliations, 28 approval/no-gate rules, and 16 focused clarification items.

**Counting rule:** 122 entries are not 122 independent end-to-end processes, 122 implementation tasks, 122 implemented automations or a denominator for ROI. The list contains substeps, outputs, references, proposals, umbrella activities and four discovery items. Scope must consolidate related entries into bounded workflow families.

Examples of overlap to preserve without double-counting:

- P01 checks pre-SOW release eligibility; P09 records the costing decision; P53 is the separate document-quality gate. They belong to one commercial path, not three full SOW workflows.
- P04 is the reporting umbrella; P40–P42 specify the weekly/monthly outputs.
- P12, P34 and F34 are the same project-to-Finance chain at different levels and departmental viewpoints.
- P03 contains incumbent project registration; P16 specifies engagement intake.
- P63 describes phase-gate orchestration over the detailed controls, not another independent lifecycle.

**Evidence classifications:** new SOP obligations are labelled SOP-prescribed workflow/control/output, not Existing workflow or Completed merely because they appear in a document. Referenced prerequisites remain distinct from PMO-owned work. Mixed documented + proposed identifies a documented obligation whose automated solution is still a proposal.

## 3. What the SOP establishes

### 3.1 Initiation starts with client engagement

There are three routes: an RFP win, a direct client engagement, or an engagement supported by a Product-prepared product paper. PMO logs the engagement, records its route, assigns a PM, coordinates requirements and stakeholders, and obtains Engineering and Security estimates. Both types of effort must enter costing and planning. [S1, Phase 1, pp.2–3; Phase 2 step 5, p.4]

All SOW costing follows **Project Manager → Head of PMO → CEO**, in that sequence, before a cost or SOW reaches the client. Cost-changing revisions repeat the chain. The client signs both SOW and PRD; the PM then shares the signed costing and milestones with Finance. The SOP says commencement is immediate on signing. [S1, Phase 1 steps 5–7, p.3]

This supplies approval roles and mandatory inputs. It does **not** supply the calculator, rates, pricing formulas, margins, tax treatment, rounding, currency rules or permitted overrides. P14 remains open.

### 3.2 Planning is a separate controlled phase

Planning registers the formal project ID, includes two PRD alignment sessions, and confirms UI design, technical design, test-strategy and UAT-approach approvals owned by other teams. Product Owner approves scope; Engineering Lead approves estimates. PMO Lead approves the detailed project plan, which must align with the signed SOW and share milestones with Finance. [S1, Phase 2, pp.3–5]

The app must preserve the difference between PMO verifying another team's decision and PMO owning that decision. It must also distinguish the early engagement record from the formal Planning project identifier, while linking them.

### 3.3 Execution has distinct gates, not one approval flag

Engineering and QA execute under their own SOPs while PMO tracks delivery. QA exit requires QA Lead sign-off with no critical defects outstanding before Product UAT. UAT has the listed Product Manager, Product Owner and client-contact approvals. Engineering's Go / No-Go precedes the GLPI deployment request. The PM raises that request; **Security, CTO and CEO** approve on GLPI before Infrastructure/DevOps releases to production. [S1, Phase 3 steps 2–7, pp.5–6]

Go-live sign-off is **after** release, by the PM and Client. It is also business acceptance; a separate business-acceptance step must not be invented. Milestone completion is recorded and Finance notified so Finance can invoice or follow up. [S1, Phase 3 steps 8–10, pp.6–7]

### 3.4 Closure is not a payment-collection gate

PMO confirms Engineering/Infrastructure stability, verifies technical-document completion, archives artifacts, hands over support/escalation documents, and captures lessons learned. The PM prepares the closure report; Head of PMO approves it. Finance must have been notified of all milestones. The SOP does not require all invoices to be paid before closure and explicitly requires no separate operational-handover approval. [S1, Phase 4, pp.7–8]

### 3.5 Communication and document governance are operational workflows

Internal PMO status meetings are every Tuesday; client reports are weekly; executive reporting is monthly. Every formal meeting needs minutes containing purpose, decisions, actions, owners, deadlines, and scope/timeline changes, stored in the PMO repository. [S1, §§5.1–5.5, pp.8–9]

Internal escalations have 24-hour and 48-hour rules. Client-dependent escalation is within 24 hours where unresolved/dependent, with PMO Lead/Head approval before client escalation or de-escalation. Delivery-timeline-impacting blockers must be escalated immediately. The document does not define all clock/calendar semantics. [S1, §5.6, p.9]

Every external document needs the PMO Lead quality review, valid formatting and current content, without unresolved comments/placeholders. Client-facing outputs cannot simply expose raw issue logs, internal commentary or unreviewed meeting notes. [S1, §§9.3–9.8, pp.12–15]

### 3.6 RFP, issue, risk, incident and change paths add important boundaries

RFPs are all answered; no bid/no-bid approval is required. Internal review is by PMO Lead and Engineering Lead; commercial sign-off follows the full costing chain. Wins enter Initiation Route A; losses are archived with lessons. [S1, §6, pp.9–10]

Issues require identifiers, owner, severity, status, timestamps and next actions; duplicate tracking is prohibited. QA and PM close by updating the issue log, with no separate closure approval. Security owns the risk register, while Engineering owns incident management. These must not become new competing PMO masters. [S1, §§9.1–9.2, p.12; §§9.6 and 9.9, pp.14–15]

Changes have required intake fields, PM classification, cross-team impact assessment and conditional approval paths. Product and Engineering approvals are required; Client approval is conditional on client-facing impact; cost impact invokes PM → Head of PMO → CEO. Engineering Lead and Security Manager agree timelines. Production deployment uses GLPI. Change closure includes the signed PM/Client go-live document. [S1, §§9.10.1–9.10.7, pp.15–16]

Emergency changes require prior Incident Lead and Engineering Lead authorisation, plus CTO for P1. They must be logged within 24 hours, reviewed, and retrospectively approved by Product and Engineering Lead within 1–2 working days. The relationship with mandatory pre-deployment GLPI approvals is not explicitly resolved. [S1, §9.10.9, p.17]

## 4. Selected architecture

### 4.1 Architecture shape

**A modular monolith with federated systems of record and explicit workflow state.** In practical terms: one maintainable application/codebase, divided into business modules, with one operational database. Connectors link to existing authoritative tools. This is not one universal database containing all PSL information.

Recommended modules, implemented only as chosen during scoping:

| Module | Responsibility | Important boundary |
|---|---|---|
| Shared workflow core | Cases, tasks, phase transitions, approvals, timers, evidence references and audit history | No generic agent deciding which approval can be skipped |
| PMO delivery and commercial | Engagement-to-project links, SOW/estimate versions, stage gates, RFPs and CR coordination | Reuse incumbent PMO capabilities and IDs; price arithmetic awaits the calculator |
| Finance preparation | Existing proposed reconciliation, allocation and billing-preparation capabilities | QuickBooks remains the accounting authority; no inferred writeback |
| Cross-team handoffs | Signed-baseline and milestone events, delivery receipts, exception handling | Not automatic invoice posting, revenue recognition or cash confirmation |
| Documents and reporting | Template/version references, review queues, internal/client projections and publication records | External publication tied to reviewed version and approved audience |
| BaaS operations | The previously identified support/onboarding/usage/renewal capabilities where validated | No changed settlement/corrective-credit authority merely because a case is visible |
| Integration adapters | PMO tool, GLPI, QuickBooks, approved repositories and existing flows | Each object/workflow has one authoritative owner of state |

The SOP supports the functional boundaries; this module decomposition is the architecture recommendation, not a claim that PSL already uses these modules.

### 4.2 Technology decision

| Layer | Selected default | Reason and qualification |
|---|---|---|
| Application | Python with the latest patched **Django 5.2 LTS** | Retains the original supported-stack direction. The official support table lists extended support through April 2028. Pin the reviewed patch during implementation; do not mistake LTS for the newest feature release. [W1] |
| Interface | Django-rendered staff pages, forms and review screens; modest client-side enhancement only as needed | Fits the documented approval/reporting work without committing to a separate frontend application. This is a design choice, not a product limitation. |
| Operational storage | Managed **PostgreSQL** | Store state, version references, decisions, outbox/job records and derived snapshots; not another general ledger. Financial values use exact decimals with owner-approved rounding. |
| Background work | Same-codebase worker with durable PostgreSQL job/outbox/timer records; finite scheduled work on Azure Container Apps Jobs | The platform supports finite manual/scheduled/event-driven jobs. Persist human waits as state, not sleeping jobs. [W2] |
| Hosting | **Azure Container Apps** and approved managed PostgreSQL | Retain the original cloud default only after PSL confirms hosting/residency, budget and support. No region, size or cost is invented. |
| Identity | **Microsoft Entra ID** for staff sign-in plus application-enforced project/department/audience authority | Container Apps supports Entra integration; authentication is not business approval authority. [W5] |
| Documents | Existing governed repository; **SharePoint** where approved, licensed and adequate | Use versioned references and tested access/content-review controls. SharePoint content approval is a document capability, not automatic commercial or deployment authority. [W6] |
| Existing interactions | Retain useful **Teams/Power Automate** interfaces and invoice work | Each workflow has one durable state owner. Do not create a second sender or duplicate approval engine. |
| AI | Optional, later, direct bounded model calls; original Azure OpenAI direction remains conditional | Extraction, meeting/report drafts and read-only answers over permitted evidence. No model is selected or needed to establish the business controls. |

Django 5.2 is the recommended implementation default, not a claim it is universally best regardless of PSL's maintainers. If the long-term owner has a different supported stack, implement the same architecture there after an explicit decision. That is a language/framework change, not a reason to discard the process design. [S2, §2]

### 4.3 Systems-of-record boundaries

**Existing PMO tool:** retain authoritative project records and any existing adequate lifecycle functionality. A hub project object should hold an external reference and coordination state, not a second editable master. If the hub must become the master for a selected object, that requires an explicit migration and cutover decision with reconciliation.

**GLPI:** retain authoritative deployment requests and approvals. The hub can show prerequisites, link a request and verify evidence/status. A hub “approved” checkbox cannot authorise production release. GLPI publishes both high-level and legacy REST API paths, but the installed version, enabled APIs, objects and permissions must be inspected. API capability in public documentation is not evidence of a working PSL connector. [S1, Phase 3 step 7 and §7; W3]

**QuickBooks:** retain the ledger and existing posting route. Initially use approved exports or verified read-only access; the source does not establish the QuickBooks edition or API. Derived PMO/Finance views are not ledger truth. [S2, §2 and F01–F02 mapping]

**Security and Engineering:** risks stay in the Security-owned register; incidents and their lifecycle stay under Engineering. PMO receives allowed references/status. “No duplicate tracking” means a projected view must not become another place to change the same issue independently. [S1, §§9.1–9.2, 9.6, 9.9]

**Repository and existing flows:** document content stays with its approved repository; the hub stores version/evidence references. Existing invoice-generation flows retain ownership until assessed and deliberately changed. New hub-owned approval state must not also be independently controlled by a parallel Power Automate state machine. [S2, §§2 and 7]

### 4.4 Minimum workflow design

Implement typed business transitions and a reusable approval primitive, not one giant generic workflow builder. A project phase, RFP, SOW version, issue reference and CR are distinct business objects. They can share identity, evidence, audit and notification mechanisms without being forced into one state machine.

For each transition, evaluate:

1. The current authoritative state and expected version.
2. The user's relevant role, project/entity scope and permitted action.
3. Required deliverables and applicable external prerequisite evidence.
4. The correct approval set, sequence and conditions.
5. The exact commercial/document/release version covered by the decisions.
6. The next state and any resulting notification/action intent.

These are proposed implementation safeguards. The source-prescribed cost-revision rule is mandatory; broader handling of non-cost revisions, revoked approvals and policy changes must be agreed rather than invented.

Represent the cost chain sequentially. For approvals where the SOP lists several roles without an order, keep the complete required set and ask the owner to confirm execution semantics; do not silently make them sequential. Record both the human identity and the role under which the decision was made. Role overlaps, substitutes and segregation of duties require owner agreement.

External prerequisite records need source-system identity, object/version, decision, owner/approver, timestamp, evidence reference and verification status. Those fields are the proposed evidence contract. Missing, stale, inaccessible or superseded evidence must not silently pass a consequential gate.

Do not add approval gates the SOP explicitly omits: bid/no-bid, PM change classification, issue closure, operational handover, separate business acceptance, or an extra CR acceptance after its prescribed go-live sign-off. [S1, §6.1; §9.10.2; §9.1; Phase 4 step 3; Phase 3 step 8; §9.10.7]

### 4.5 Reliability and operating controls

Use short database transactions to commit the business-state change, audit entry and outbound work intent together. Workers claim eligible work with a lease, record attempts/outcomes and retry with limits. PostgreSQL documents `SKIP LOCKED` as suitable for queue-like consumption, not a replacement for a correct job lifecycle. [W7]

Use stable event/action keys, such as project + milestone + completion version + destination. Keep dispatch intent, confirmed delivery and a Finance acknowledgement (if agreed) separate. On ambiguous external success, inspect the destination before retrying. A retry must not create a second GLPI request, invoice, client communication or milestone event. Do not promise exactly-once effects across arbitrary applications.

Long approvals remain durable database records. Power Automate's documented cloud-flow run-duration limit is 30 days including pending approvals; this does not make Power Platform incapable of long-running business processes, but it rules out relying on one waiting flow as the sole durable record. [W4]

Scheduled batches alone cannot be promised to meet an “immediate” escalation requirement. The selected slice must define its actual notification target and have an appropriate active worker/dispatch path, with scheduled recovery sweeps as a backstop. Engineering's existing emergency route must not be disabled while the new workflow is still being validated.

Test restart recovery, duplicate/out-of-order callbacks, stale documents, timed-out external writes, revoked access and concurrent decisions. Provide operator-visible failures, an exception inbox and a manual fallback. Before live use, agree monitoring, support ownership, backups, retention and restore objectives; none are specified by the SOP.

### 4.6 Security, publication and AI

Staff sign-in must be followed by record-, department-, project- and audience-level checks on every screen, export, background job and connector action. Django's default backend does not implement object-level permissions; these checks must be designed and tested. Do not treat superuser/admin access as the normal review interface. [W8]

Keep raw payroll, restricted Finance working data, commercial costing and client-facing content appropriately separated. Preserve the earlier Finance internal/group disclosure distinction. Entra sign-in does not solve the client-signature method: retain verified evidence from the approved existing signing route until an external identity workflow is specifically justified. [S2, §5; S1, Phase 1 step 7 and §§9.4–9.8]

External publication should reference the exact reviewed version and permitted recipients. Recheck stale source content and unresolved comments. A change after review creates a version/evidence question, not a licence to distribute the latest unreviewed file. Automated format checks can help, but PMO Lead content review remains human authority. [S1, §§9.7–9.8]

AI may propose extracted fields, summarise permitted meeting records or draft report narrative. It must not choose cost rates, approve a change, infer that a milestone recognises revenue, approve a release, send unreviewed client documents or gain unrestricted SQL/system access. Core operations should continue when AI is disabled. These are architectural controls, not assertions about current implementation.

## 5. Options considered

| Option | Assessment | Decision |
|---|---|---|
| Configure/extend the existing PMO tool only | Best for any capability it already handles adequately; its product/version/features are still unknown. It may not cover the distinct Finance and BaaS transformation needs. | Capability-fit check is mandatory before custom duplication; not enough evidence to declare the incumbent a complete solution. |
| Power Platform-first application with Dataverse and managed flows | A credible alternative if PSL has suitable licensing, maintainers, governance and connectors. Persistent-state designs can address long human waits. Cost, maintainability and complex cross-domain rule fit are unmeasured. | Do not reject on the 30-day limit alone. Not enough new evidence to overturn the existing Python/PostgreSQL default. |
| Django/PostgreSQL modular hub around authoritative tools | Directly accommodates bespoke deterministic transformations plus human approvals, evidence and adapters in one maintainable codebase. Requires real engineering ownership, recovery testing and access controls. | **Selected default, with existing-tool reuse.** |
| Dedicated BPM/durable-workflow platform or microservices from day one | Could help if non-developers must frequently redesign flows, orchestration recovery becomes unusually complex, or independently operated domains justify separation. Those demands and volumes are not established. | Defer. The number of register entries alone does not justify added platform overhead. |
| Autonomous agent platform | Does not supply the missing pricing policy, named authority, source ownership or reliable approval evidence. | Not the operating core. Use bounded assistance only where justified. |

No vendor is declared cheapest. Hosting, licensing, developer skill, support load, migration and exit/export costs require actual PSL data. The decision is about fit to the evidenced work, not a fabricated numerical vendor score.

## 6. What is now resolved and what still needs clarification

**Resolved at documentation level:** the missing revised PMO SOP has arrived; the four-phase lifecycle, entry routes, named costing chain, main PMO/client/referenced gates, Finance notification duties, document-quality gate, RFP path and change/emergency requirements are now documented. [S1]

**Not resolved:** the actual calculator; installed PMO/GLPI capability; precise actor/delegation and revision rules; client signature/evidence method; full other-team SOPs; report/template examples; integration contracts; retention/hosting/licensing; baseline workload and live operating evidence. The Open decisions sheet gives Q01–Q16, suggested routing owners and feature-specific impact.

The main policy tensions are:

| Question | Source tension | Treatment before clarification |
|---|---|---|
| Emergency vs GLPI | §9.10.9 permits immediate authorised implementation; §7/9.10.4 require Security/CTO/CEO GLPI approval before production changes. | Do not invent a waiver or re-interpret the SOP. Keep new automated production execution out of scope until the responsible authorities resolve it. |
| Standard change | §9.10.2 calls it pre-approved; §9.10.4 requires documented approval before implementation. | Obtain the catalogue and what pre-approval actually satisfies. Do not auto-bypass review. |
| Signed SOW vs Planning baseline | SOW/PRD are signed in Initiation; the Planning baseline is later described as the basis for the SOW. | Confirm preliminary/final baseline linkage and the change/re-sign path for differences. |
| Immediate commencement vs phase gate | Phase 1 step 7 states immediate commencement on signatures; §3 requires PMO approval at every gate. | Confirm the representation of PMO gate acceptance without inventing a delaying approval. |
| Roles, severity and timers | PMO Lead/Head, Product Manager/Owner, Critical/P1 and “defined SLA” are not fully resolved. | Preserve terminology; obtain actor maps, severity routing, working calendar and actual SLA definitions. |
| Risk/incident record boundary | Risk is an issue type, but Security owns the risk register; production issues are centralised while Engineering owns incident lifecycle. | Use references/projections and agree one owner for each state change. |

These are not allegations that PSL operates incorrectly. They are decisions the supplied text does not fully settle. Some are blocking for a particular write/approval feature, not for the entire programme.

## 7. Position for the next scoping step

**The architecture direction can be selected now.** The document does not require a platform redesign. It does require disciplined workflow modelling and firm ownership boundaries.

Scoping should select outcomes and workflow families from the register, not purchase or implement all 122 entries. For each selected family, define trigger/end state, primary owner, system of record, fields and evidence, permitted read/write actions, unresolved rule dependencies, acceptance examples, manual fallback, migration boundary and success measure.

The original first candidate remains a bounded Finance shadow-reconciliation slice, subject to actual workbook/export/rule access. The new SOP also makes a controlled signed-baseline/milestone-to-Finance handoff a credible candidate to compare during scoping. Neither should be declared the final first build without checking owner access and readiness. [S2, §§9–11; S1, Phase 1 step 7, Phase 3 step 10]

Pricing can initially retain the approved spreadsheet as evidence while the workflow tracks the proposal/version and required people. Recreating its arithmetic remains gated on P14/Q01. Similarly, GLPI status verification can be scoped separately from creating requests or taking any production action.

No implementation schedule, budget, ROI, complete rollout or consequential-write authorisation is established here. The next decision is a bounded scope with measurable acceptance—not another open-ended architecture search.

## Appendix A. SOP coverage crosswalk

Every numbered operational section and phase step has a register mapping. Repeated approval summaries are mapped back to the same activity rather than added as duplicate processes. This is supplied-document coverage, not proof that the inventory is complete for all PSL departments.

| SOP location | Register mapping |
|---|---|
| Document control / purpose / ownership, §§1–2 | P13, P02, P51, P55 |
| Governance model and roles, §§3–4 | P63 plus named roles in PMO detail and Approval rules |
| Phase 1 step 1 | P03, P16 |
| Phase 1 steps 2–3 | P17 |
| Phase 1 step 4 | P06, P07, P18 |
| Phase 1 step 5 | P09, P01 |
| Phase 1 step 6 | P19, P08 |
| Phase 1 step 7 | P20, P12, F34 |
| Phase 2 step 1 | P03 |
| Phase 2 steps 2 and 7 | P21 |
| Phase 2 steps 3–4 | P22, P23 |
| Phase 2 step 5 | P18, P06 |
| Phase 2 step 6 | P24 |
| Phase 2 step 8 | P25 |
| Phase 2 step 9 | P26, P12 |
| Phase 3 step 1 / §5.1 | P27 |
| Phase 3 steps 2 and 9 | P28, P04 |
| Phase 3 step 3 | P29 |
| Phase 3 steps 4–5 | P30 |
| Phase 3 step 6 | P31 |
| Phase 3 step 7 | P32 |
| Phase 3 step 8 | P33 |
| Phase 3 step 10 | P34, P12, F34 |
| Phase 4 steps 1–4 | P35, P36, P37, P38 |
| Phase 4 steps 5–6 | P39, P12 |
| All phase entries/exits | P63 and the corresponding detailed phase controls |
| §§5.2–5.5 | P40, P41, P42, P43; P04 reporting umbrella |
| §5.6 | P44 |
| §§6.1–6.2 | P45, P46 |
| §§6.3–6.4 | P47 |
| §§6.5–6.6 | P48 |
| §6.7 | P49 |
| §7 | P63, P09, P32, P12 |
| §8 | Approval rules G01–G24; existing detailed processes, not additional copies |
| §9.1 | P50 |
| §9.2 | P51 |
| §9.3 | P52, P10–P11 |
| §§9.4–9.5 | P53 |
| §9.6 | P54, P40, P42 |
| §9.7 | P52, P11 |
| §9.8 | P53 |
| §9.9 | P55 |
| §§9.10.1–9.10.2 | P56 |
| §9.10.3 | P57 |
| §9.10.4 | P58, P32 |
| §§9.10.5–9.10.6 | P59 |
| §9.10.7 | P60 |
| §9.10.8 | P58, P61–P62 |
| §9.10.9 | P61–P62 |

P05 remains the earlier shared-view proposal, and P13–P15 preserve discovery history. No new process is created solely from a technology recommendation or an unanswered exception question.

## Appendix B. Source register

### Supplied project evidence

**S1.** `PMO_SOP_v1.1.pdf`. Project Management Office SOP; 17 pages; v1.1 revised 12 October 2026. Primary source for this update. Page numbers above refer to its PDF pages.

**S2.** `PSL_Product_Studio_Automation_and_Architecture_Review.docx`. Review draft dated 11 October 2026; 46 pages. Baseline architecture, inherited Finance/BaaS findings, evidence limitations and validation gates. This update does not repeat the earlier original recording/workbook audit.

**S3.** `PSL_Process_Automation_Register.xlsx`. 11 October 2026 baseline, 74 entries across Finance/BaaS/PMO. Original values retained in the updated workbook's Baseline 11 Oct sheet.

**S4.** `PMO Process Automation.docx`. 8 October 2026 discovery transcript. Used through the baseline review for current/manual practice, proposed integration and the still-pending pricing-calculator walkthrough.

### Public technical references checked for the architecture decision

These support product capabilities and limitations, not claims about PSL's actual installations, licences or approvals. Retrieved 15 October 2026.

**W1. Django supported releases:** https://www.djangoproject.com/download/  
Supports the Django 5.2 LTS maintenance horizon.

**W2. Azure Container Apps jobs:** https://learn.microsoft.com/en-us/azure/container-apps/jobs  
Supports finite manual, scheduled and event-driven job execution; not a standalone human-approval engine.

**W3. GLPI RESTful API V2:** https://help.glpi-project.org/documentation/modules/configuration/general/api/restful-api-v2  
Supports the existence of API choices; local feature/access checks remain mandatory.

**W4. Power Automate limits:** https://learn.microsoft.com/en-us/power-automate/limits-and-config  
Supports the 30-day cloud-flow run-duration limit, including pending approvals.

**W5. Container Apps Entra authentication:** https://learn.microsoft.com/en-us/azure/container-apps/authentication-entra  
Supports the staff identity integration option, not application-specific authority.

**W6. SharePoint document approval:** https://learn.microsoft.com/en-us/sharepoint/dev/business-apps/power-automate/guidance/require-doc-approval  
Supports document-library content approval; actual library permissions and review policy must be configured and tested.

**W7. PostgreSQL SELECT locking:** https://www.postgresql.org/docs/current/sql-select.html  
Supports queue-like consumption using row locks and SKIP LOCKED; durable job semantics remain application responsibilities.

**W8. Django authentication backend reference:** https://docs.djangoproject.com/en/5.2/ref/contrib/auth/  
Supports the limitation of the default backend regarding object-level permissions.
