---
specification: PSL Operations Factory Component Design
revision_date: 2026-11-01
status: proposed design and consolidation specification
release_processes: 108
deferred_baas_processes: 14
architecture_processes: 122
source_format: editable DOCX
---

# PSL Operations Factory Component Design

Agent native operating design and build consolidation specification

Revised for discussion and build consolidation  |  1 November 2026

I recommend building the stronger factory around the existing Django and Postgres application, with the operator console as its main surface. Incoming work should become a controlled run: agents assess and act within authority, people make consequential decisions, services execute business actions, and receipts and evidence establish the result. The console should make that work visible and actionable, rather than resemble a collection of department dashboards.

The next design work is substantive, not just a terminology change. It requires shared work and run contracts, explicit decisions, a common action gateway, versioned policies, reliable effect handling and evidence-backed completion. Mature products provide useful patterns and selected code; they do not require replacing the PSL core.

### What is established and what remains proposed

The October 30 inspection identified Outbox, HumanTask, TaskEvent, claim and finish fencing, run_once, workbench views, AgentRun, scoped actors/processes, provider configuration, budgets and citations. Preserve and test these foundations; their presence does not prove every recovery guarantee. The later consolidation baseline records the November 1 read-only findings.

The component names, logical contracts, state examples and screen behavior in this document are proposed extensions or clarifications unless explicitly called an existing foundation. They are not claims that the changes are saved, implemented or production-ready. New SDKs and engines remain conditional choices, not settled replacements.

### Scope and readiness

The first release covers 108 process IDs: 63 PMO and 45 Finance. The wider architecture includes 14 deferred BaaS processes. Observed coverage spans all 122 with every row partial; 16 of 92 preview guards are evaluated and 76 NOT_EVALUATED. These dated observations are not passed controls or a current full-suite result.

Use one PMO completion to invoice line to prove the shared architecture, then extend that proven design across the first-release scope. That first line is a validation sequence, not an artificial cap on the factory. Integrations, policy approval, provider evaluation and UAT still require evidence.

### How to use this proposal

The operating and console chapters explain the product. Expanded agent and ownership chapters show how AI drives work. Research chapters retain reuse sources. Consolidation chapters define requirement IDs, contracts, transitions, migration and acceptance. Matching Markdown carries the same body; a separate Codex prompt guides implementation.

The principal design decision is to keep one authoritative chain from business record to work item, agent run, decision, command, receipt and verified output. No SDK checkpoint, browser state or vendor execution history should become a competing source of business authority.

## Reading guide and revision notes

This revision preserves the operating design and research and expands agent activities, ownership routing and implementation detail. The Word and Markdown bodies match. Word comments identify major revisions.

| Start page | Section |
| --- | --- |
| 3 | Foundation and existing services |
| 4 | Work queue case decisions and recovery |
| 8 | Process states execution and command authority |
| 11 | Adaptive agent operating model and roles |
| 12 | ACT01 to ACT15 execution catalogue |
| 14 | Activity contract loop autonomy and recovery |
| 17 | End to end agent example and evaluations |
| 19 | Policy owners approvers and routing tests |
| 22 | Human tasks policies evidence and adapters |
| 27 | Proof line and implementation gates |
| 29 | Framework shortlist exact sources and licenses |
| 33 | Dated build baseline and reconciliation |
| 34 | REQ01 to REQ25 and release coverage |
| 36 | Commands decisions receipts and transitions |
| 39 | Duplicates callbacks timers and security |
| 41 | Migration restore and rollback |
| 42 | TEST01 to TEST20 and evidence reporting |
| 45 | Business decisions and unknown use cases |

The behavior is a target to reconcile with the actual build, not a claim of completed implementation. Logical names and examples must map to current models. Business owners must resolve thresholds, appointments and live permissions; unknown values remain blockers.

REQ, TEST, AGT and ROUTE identify shared requirements and tests, not the 108 process IDs. Each process needs its own evidence. Upload both specification formats and paste the separate Codex prompt into the existing build thread; inspect current state before changes.

## The shared operating model and existing seams

The factory is a way of operating the existing business system. Department modules continue to own their domain rules and records. Shared services coordinate work around those records so PMO, Finance and supervisors can see the same case at the level appropriate to their roles.

### One traceable chain of work

Intake creates or identifies a business case. A versioned process determines the next eligible step. That step may run a bounded agent, request a human decision or invoke a deterministic action. Execution records attempts and receipts. Verification checks the business postcondition before the console calls the result complete. An exception returns to an accountable person with evidence and a safe next action.

| Existing code seam | Preserve | Proposed extension or clarification |
| --- | --- | --- |
| apps/workflows/models.py | Outbox, HumanTask, TaskEvent | Link work, decisions, commands and receipts through stable case and run identifiers. |
| apps/workflows/services.py | Claim and finish fencing, run_once | Document ownership, lease and retry semantics; prove them against crash and concurrency tests. |
| apps/core/workbench.py | Discover and work | Present shared queues and a case workspace, with backend-derived available actions. |
| apps/agents/models.py and services.py | AgentRun and scoped controls | A typed specialist interface and traceable proposed or executed actions within existing authority. |
| Existing domain and policy services | Business invariants and lifecycle | Expose versioned commands and policy decisions without relocating business truth into an SDK. |

### Contracts rather than mandatory new tables

Use logical records for ProcessDefinition, ProcessRun, WorkItem, Decision, ActionDefinition, CommandAttempt, EvidenceReference and VerificationResult. These names describe responsibilities for design discussion; they do not prescribe eight new tables or services. Map each responsibility to existing models first, add only missing fields or entities, and keep a single authoritative owner for each fact.

Every link needs stable identifiers, tenant and process scope, schema or definition version, timestamps and provenance. Evidence references must remain resolvable by authorized readers. A common correlation ID helps diagnostics, but never substitutes for tenant authorization or a business-stable idempotency key.

### Authority follows the business service

The console requests a command; the agent requests a command; the process requests a command. All three pass through the same deterministic authorization and domain checks. HumanTask owns the business decision. The outbox owns dispatch intent. Adapter receipts report what the external system observed. Verification owns the conclusion about the business result.

Discuss which existing model is the canonical case or run anchor, and whether a work item can span several domain records. Settle that mapping before building another catalogue or status store. Acceptance means the first proof line is reconstructable through this chain without manual joins across unrelated screens.

## The operator console and work queue

The console should answer what needs attention, what is happening, who owns the next step, which action is safe and what evidence proves the result. Its home is an actionable queue, not a management dashboard. Build on the existing workbench using Django templates and model-backed partial updates where appropriate; a new client framework is not a prerequisite.

### Navigation organized around work

Use Work queue, Active work, Exceptions and Completed outcomes as views over the same business work. Administration holds process blueprints, policy, connector and access configuration behind separate permissions. Every work item needs a stable URL and a reliable link to its AgentRuns, HumanTasks, commands and receipts. If a relationship is missing, show that gap rather than invent a combined status.

Default to Needs my attention: decisions, claimed exceptions and verification work the current person may perform. Adjacent views include Unassigned, At risk, Overdue, Awaiting external response, Awaiting verification and All active. Counts must use the same filters as their rows. A small operational summary can highlight oldest unassigned work; charts should not push actionable rows below the fold.

### The row is an operational summary

Show the business reference and intended outcome, process type, current step, state, responsible person or team, due time and age, blocker or decision reason, and last confirmed update. Use business language such as “Awaiting Finance approval.” Do not label an item simply Running when it is waiting for a person, callback, worker or receipt. Unknown owner and missing deadline are visible conditions.

Search should accept project and invoice references before internal UUIDs. Filter by process, owner or team, state, exception class, due range, project and evidence freshness where supported. Preserve filters, sorting, selected item and scroll position when entering and leaving a case. Saved views need an explicit personal or shared scope and stable tie-breakers for urgency sorting.

### Safe updates and accessibility

Live updates must not move a row under the pointer during an action. Offer an updated-items notice while the operator is interacting. Keep bulk operations narrower than single-case actions: reassignment may be appropriate, but select-all approval or retry needs explicit policy, per-item eligibility and a preview of consequences.

Support keyboard navigation, visible focus, labeled controls and text as well as color. Preserve sensible focus after updates. Display local time with an accessible absolute timestamp and timezone. Empty, loading, stale, denied and concurrent-update states belong in the design from the start.

### Acceptance and discussion

An operator should identify the next action, owner, due time and blocker from a row, open the case, and return without losing context. Test keyboard-only triage and direct API permission checks. Discuss which roles see shared queues, how urgency is determined, and which SLA clocks pause while work waits on an external party.

Sources  [Camunda queue and task details](https://docs.camunda.io/docs/components/tasklist/userguide/using-tasklist/)  |  [Trigger context preserving navigation](https://trigger.dev/changelog/move-between-adjacent-runs)

## The case workspace decisions and agent activity

Opening a queue item should retain context in one workspace. Use an identity and state header, a readable progress and evidence area, and a next-action panel. On narrow screens, place the action panel after its immediate context rather than squeezing a permanent third column. This is a proposed interaction model, not a claim that the screen already exists.

### Identity and progress stay visible

Retain the business reference, intended outcome, current step, owner, deadline, state and freshness. Back returns to the same queue; previous and next move within its result set. Define whether navigation follows the original or refreshed set so work does not appear to disappear unexpectedly. The Overview shows latest established facts, the blocker and the next safe action.

A compact stage trail shows the business step, actor or service, start and end time, outcome and linked evidence. Keep a stage that failed twice and then succeeded readable as one stage with expandable attempts; never erase the failures. Parallel work appears as sibling activities. Evidence and outputs, Decisions and Technical details remain directly accessible without forcing operators through department screens.

### Start a decision with the question

Ask “Approve this invoice draft for delivery?” before presenting buttons. Show why review is required, the requester, applicable policy reason, exact proposed change, recipient or destination, consequences and evidence version. Summarize material differences from the previous draft. Missing or inaccessible evidence must be explicit, not an empty panel.

Only expose actions implemented and authorized by the backend: claim, reassign, approve, reject, request information, escalate or a scoped recovery action as supported. On submission, recheck authority, ownership, task version, artifact version and transition validity. A stale page must not authorize a changed draft. Preserve unsent notes on conflict, explain what changed and require a fresh decision.

Require reasons for rejection, override and recovery according to policy, not ceremonial text for every routine click. Confirmation wording names the consequence. After submission, show the recorded decision and action reference; an accepted request is not proof of external delivery. Deduplicate server-side and offer safe status refresh rather than another send button.

### Observable agent work not private reasoning

Show evidence accessed, tool requested, response received, artifact produced, validation result and escalation, with timestamps and source links. Use concise evidence-backed explanations. Do not expose or fabricate hidden chain-of-thought. Redacted payloads, structured events and technical logs belong in a permission-controlled detail view. A successful AgentRun can still leave the case awaiting review or verification.

### Acceptance and discussion

An operator can explain what the agent did without JSON, inspect the exact evidence behind a decision and see a safe conflict after another person changes the task. Discuss what supervisors need to see without broadening evidence access, and which action-specific consequences require explicit confirmation.

Sources  [Windmill minimal and detailed approval](https://www.windmill.dev/docs/flows/flow_approval)  |  [Temporal grouped history](https://temporal.io/blog/the-dark-magic-of-workflow-exploration)  |  [Temporal summary component](https://github.com/temporalio/ui/blob/main/src/lib/components/event/event-summary-row.svelte)

## Exception recovery and a complete operator journey

Exceptions should be work with an owner and a safe remedy. Group by missing input, policy conflict, validation or authorization failure, unavailable dependency, exhausted retries and uncertain external outcome. Show the affected step, business impact, age, last attempt, diagnosis evidence and permitted next actions. Similar error text does not mean one remedy is safe for every case.

### Recovery must establish a result

Separate recovery requested, dispatched, observed progress and verified outcome. “Waiting” means an expected event has not arrived; “blocked” means a prerequisite or policy prevents progress. A retry request is not proof of an active retry or a fix. For ambiguous send timeouts, inspect the external reference or idempotency key before resending; unresolved uncertainty goes to reconciliation or manual review.

Sources  [Camunda explains the retry verification gap](https://docs.camunda.io/docs/components/operate/userguide/resolve-incidents-update-variables/)

### Illustrative PMO to invoice journey

The following case uses illustrative references and begins with a mock external adapter. It shows the proposed experience, not existing production behavior.

PMO submits a billing request for project P184 with milestone acceptance evidence. The case routes to Finance Operations with a named next owner.

Intake validation finds a missing purchase order reference. A HumanTask requests it from PMO; the case shows the exact blocker instead of Running.

PMO supplies the reference. The new evidence version is recorded, validation resumes and the history retains the original information gap.

An agent reviews evidence and proposes cited invoice inputs or narrative. Finance domain services calculate and validate totals and create draft v1. The case is Awaiting review.

Finance identifies a mismatch and requests correction with a reason. Draft v1 remains in history; a corrected draft v2 is produced and revalidated.

Finance approves the exact v2 publication packet, including destination, amount and evidence. The command gateway rechecks current authority before queuing it.

The mock adapter publishes but its first response is lost. The console shows Delivery uncertain and blocks a blind resend while reconciliation checks the same business key.

Reconciliation finds the original mock invoice, matches it to v2 and records verification. The exception closes with evidence. No claim of customer payment is made.

### Completed outcomes retain the proof

Keep the artifact and version, decisions, attempts, receipt, verification criterion and resolved exceptions together. Generated, reviewed, acknowledged and verified are different facts, not one universal sequence. An API acknowledgement alone must not be labeled customer receipt or payment. Retention, redaction, exports and downloads follow backend policy.

Acceptance means an operator can recover this lost-response case without duplicating publication, distinguish a recorded decision from a verified outcome, and inspect all earlier attempts. Discuss which actions permit automatic reconciliation, which require a human verifier and who owns cases that remain unresolved.

## Console routes interactions and acceptance

Extend the existing server-rendered workbench and staff interface. The route names below describe destinations, not existing URLs or a requirement to introduce a new frontend. Inspect current routes first, retain compatible deep links and map each destination to the native record that owns it.

### Work queue and case destinations

The work queue defaults to Needs me and supports Unassigned, Running, Decisions, Exceptions, Awaiting verification and Verified outcomes. Preserve role-safe filters, sorting, search, selected row and return position in stable URLs where appropriate. A supervisor's view can widen to their authorized scope without implicitly granting access to all client evidence. Show each queue's as-of time and evaluated coverage; a metric derived from partial records must disclose its denominator.

A case destination accepts a stable case identity and an optional selected activity, decision, command or evidence reference. Its header gives business identity, intended outcome, current step, owner, timing and blocker. The main panel shows the next required action and its consequence. Tabs or sections expose Work, Agent activity, Decisions, Evidence and outputs, and Action receipts. Previous and Next preserve the originating queue and selected panel. A direct link must repeat backend authorization rather than rely on a previously filtered list.

The activity view shows objective, role, parent/child work, plan revision, observed commands, evidence, usage, result and next safe action. Summaries explain; tool events and receipts establish effects. A child success cannot make its parent verified.

### Every interaction has an explicit result

Buttons come from server-evaluated capabilities. Selecting Approve submits the exact decision and target versions shown; the server rechecks eligibility, scope, policy, evidence and concurrency. Disable repeated submission locally for usability, but rely on server idempotency for correctness. Show submitting, accepted, conflicted, denied and failed states separately. Refresh the affected native records after acceptance; never optimistically display verified completion because a request returned successfully.

If the record changes during review, show a clear stale notice and a comparison of material changes before fresh approval. A denied action explains the permitted next step without leaking restricted policy or evidence. Loading retains useful context; an empty queue states whether there is no work or filters exclude it; an unavailable source is not shown as zero work. A network interruption preserves safe unsent form input without retaining secrets and offers a state refresh before retry.

### Browser proof required

Demonstrate an operator locating owner, blocker and next action from one queue and one case workspace, without navigating four departmental screens. Demonstrate keyboard-only claim, evidence review, exact-version decision and return to the same queue position. On narrow screens, prioritize identity, state and next action; do not hide essential controls behind an inaccessible horizontal table. Use semantic labels, visible focus, accessible error summaries, status announcements and non-colour-only states.

Retain screenshots or a screen recording for normal, loading, empty, stale, denied, conflict, waiting, retry requested, uncertain effect and verified output states, with fixture, role, viewport and test IDs. Browser proof complements backend assertions; it cannot prove tenancy or authorization by appearance alone.

## Process definitions and the lifecycle of work

A process definition describes how a class of business work should reach an acceptable outcome. A run is one execution of that definition against a real case. The proposed design gives both an explicit identity while preserving the existing workflow services, HumanTask and TaskEvent. It does not require a BPMN engine or a new catalogue service.

### Proposed definition and run contracts

A definition should identify the process ID, immutable version, entry conditions, required evidence, allowed step types, action and policy references, deadlines or escalation rules, exception routes and completion criteria. Start with reviewed Python or typed configuration appropriate to the existing codebase. Business-authored visual models are a later requirement to prove, not an assumed necessity.

A run should bind the case and tenant, definition version, initiating actor, current step, relevant business record versions, linked work items, attempts and final outcome. Definitions used by active runs must not change silently. Corrections need a new version or an explicit, reviewed migration with retained history.

### Keep different kinds of state separate

| Record | Illustrative logical states and meaning |
| --- | --- |
| Process run | Ready, running, waiting, blocked, cancel requested, cancelled, failed or completed with its required evidence. |
| Work item | Unassigned, claimed, in progress, waiting for information, handed off or closed. |
| Human decision | Pending, approved, rejected, expired or invalidated by a material change. |
| Command attempt | Queued, executing, acknowledged, uncertain, failed or reconciled. Compensation is a separate action. |
| Domain record and output | The invoice retains its business lifecycle; output verification has its own result. Neither is inferred from worker status. |

These are proposed state families, not a migration-ready enum. “Cancel requested” must not claim a remote action was cancelled; “compensated” must not imply it never happened. A rejected decision can close a case or route it for correction according to its definition. An uncertain effect must not be treated as a safe-to-retry failure.

### Runtime and acceptance

For the PMO line, evidence intake makes assessment eligible; assessment may create an information request; a valid draft makes an approval task eligible; an approved exact payload makes publication eligible. The run closes only under an explicit outcome rule. Test duplicate triggers, missing evidence, rejected and expired decisions, cancellation races and resuming a v1 wait after a v2 deployment.

Pin the definition and historical policy evidence, but recheck current execution authorization. Revocation or a material policy change can block execution or require a new decision. Discuss who may publish definitions, what migrations require approval, and which business outcomes count as successful closure.

Sources  [OMG process case and decision concepts](https://www.omg.org/dmn/)  |  [Temporal compatible workflow changes](https://docs.temporal.io/develop/python/workflows/versioning)

## Execution ownership outbox and recovery

The execution layer should reliably move eligible work forward and stop safely when the result is unknown. Preserve the existing Outbox, claim and finish fencing, run_once and receipt-recovery foundations. First establish their actual guarantees; a new engine is not the starting point.

### Proposed execution contract

Each executable unit needs a stable command identity, target and version, scope, canonical payload hash, business idempotency key, policy and approval references, attempt history and effect classification. Distinguish the identity of the business effect from the identity of an attempt: a retry gets another attempt record, not a new invoice-publication identity.

Where the architecture permits, commit the local domain transition and outbox dispatch intent in one database transaction. Do not hold that transaction open across an external network call. A worker claims eligible work, validates its ownership and current preconditions, performs the allowed action, then records the receipt or uncertainty and finishes under the fencing rules. Verify those steps against the current implementation before promising atomicity.

### Failures that must remain visible

If a worker dies before dispatch, another authorized worker may recover the claim. If it dies after the external system acts but before PSL records success, the result is uncertain. Query or reconcile using the same business key before sending again. A local run_once marker or successful retry cannot prove that an external payment or publication happened only once.

Retries require a classified error, a bounded policy, backoff and a clear owner. A validation failure or rejected approval should not be retried like a transient network error. Human waits should release workers. Exhausted attempts should produce an owned exception with the last trustworthy observation, not leave a spinner running indefinitely.

### Console behavior and acceptance

- Show queued, dispatching, awaiting receipt, uncertain, retry requested and observed retry as distinct facts when relevant. Include attempt, last observation and next permitted recovery action.

- Inject a crash before send, after send and before finish. Confirm that a stale claimant cannot finalize local state, duplicate callbacks do not create new effects, and uncertain results enter reconciliation.

- Test a cancelled or revoked action while queued, lease expiry during execution and a deployment while work is waiting. Retain evidence of all attempts and decisions.

### Decision to discuss

Agree which component owns retries and reconciliation for each adapter. Only a measured unmet gap should trigger a DBOS or Temporal comparison. A candidate engine must reduce total operating complexity while preserving domain authority, HumanTask and the outbox; it must not create a competing execution ledger.

Sources  [Idempotent Receiver](https://www.enterpriseintegrationpatterns.com/patterns/messaging/IdempotentReceiver.html)  |  [DBOS side effect and checkpoint limits](https://docs.dbos.dev/architecture)  |  [Temporal safe message handling](https://github.com/temporalio/samples-python/tree/main/message_passing/safe_message_handlers)

## The action registry and deterministic command gateway

The action registry describes what PSL can do; the command gateway decides whether a request may do it now. It applies the same rules to console, agents and workflows, while domain services remain authoritative.

### What to borrow and what to build

Activepieces separates authentication, action properties, implementation, triggers and shared connector code. Adapt that contract, not a second business platform. Windmill OpenFlow contributes typed inputs and step definitions. TypeScript pieces need an adapter; they are not automatic Django drop-ins.

Sources  [Activepieces action authoring](https://www.activepieces.com/docs/build-pieces/building-pieces/create-action)  |  [Community connector example](https://github.com/activepieces/activepieces/tree/main/packages/pieces/community/airtable)  |  [OpenFlow specification](https://github.com/windmill-labs/windmill/blob/main/openflow.openapi.yaml)

Proposed ActionDefinition fields are action ID and version, description, typed inputs and outputs, required capability, tenant and resource scope, side-effect class, approval rule, timeout and retry classification, idempotency strategy, adapter binding and receipt schema. A side-effect class should distinguish reads, reversible internal changes, external publication and consequential financial actions.

### Request to execution

A caller submits an action version, target and target version, validated payload, evidence references and any decision reference. The gateway resolves trusted actor context, validates schema, checks current policy and resource access, verifies the approval binding where required, then invokes the domain service or creates dispatch intent. A preview or dry run must clearly state that it has not committed an effect.

For invoice publication, an agent may propose or request the command, but cannot choose its own role, approver or tenant. The gateway compares the canonical payload and record version to the decision. If either has materially changed, it refuses execution and returns a specific reason and the next safe route.

Illustrative interfaces are propose_action for validated proposals and authorize_and_queue for queued, needs approval, denied or stale results. The canonical hash covers destination, amounts, currency and every execution-relevant field, not just a narrative summary. Process configuration may select reviewed handlers; it cannot invent executable code.

### Operator behavior and tests

Available actions in the case workspace come from the backend contract. Show the required inputs, expected effect and approval requirement before a consequential action. A hidden or disabled button is a usability aid, not a security boundary; the API must reject the same unauthorized request.

- Exercise the same action from the operator UI, process and agent adapter; each must receive equivalent authorization and validation results.

- Reject unknown versions, wrong-tenant targets, altered approval payloads, out-of-scope evidence and reused keys with conflicting payloads.

- Confirm repeat delivery returns the original business result or enters reconciliation, rather than executing a second effect.

Discuss which actions may be autonomous and what makes them reversible. An undo must preserve history and may require authority; technical ease does not make an action safe.

## AI agent activities and execution specification

The factory is agent native: a goal, event or operator request starts work; agents interpret the case, decide the next useful permitted activity, use tools to carry it out, inspect the result and adapt until an evidenced outcome or an explicit blocker is reached. Agents are not restricted to writing suggestions. They can autonomously collect authorized evidence, classify work, create validated internal drafts, schedule eligible activities, open required human tasks and reconcile known operations through scoped tools. The application, rather than the model, enforces permissions, business invariants, budgets and durable transitions.

Use a bounded coordinator inside each versioned process envelope. The process defines legal stages, mandatory gates and allowed outcome types. Within those limits, the coordinator chooses which permitted activity to undertake, what additional evidence is needed and whether to delegate, verify, wait or escalate. It cannot invent a new business process, waive an approval, change policy or declare its own evidence sufficient to override a mandatory control. This combines adaptive work with reproducible authority. A fixed happy-path workflow alone is insufficient acceptance evidence: the implementation must demonstrate an agent choosing an allowed alternative in response to missing or conflicting evidence.

The following role names, contracts and state names are proposed implementation targets, not assertions about current repository classes. Map them to existing models and services before creating equivalents. Reuse AgentRun, HumanTask, Outbox and TaskEvent as the established responsibilities where current inspection confirms them. Do not create a separate agent-owned approval ledger, business-status database or competing retry scheduler. The 108 first-release processes do not imply 108 separate agents. Each process should compose a small library of tested activities, with coverage derived from the authoritative repository manifest.

## Reusable agent roles

A role is a versioned capability profile with narrow tools and output schemas. The same deployed service or model can perform several roles under separate profiles. A role is not a permanently running chatbot, a department with unlimited access or a new employee identity.

Case coordinator. Trigger: new eligible work, new evidence, completed activity, human decision or verified external event. Inputs: authorized case snapshot, current stage, pending dependencies, allowed activities, remaining budget and relevant outcomes. Activities: classify unresolved work, make a bounded plan, select specialists, choose eligible commands, schedule verification and replan. Output: structured plan revision, child activity requests, wait reason or proposed final outcome. Tools: scoped case/evidence reads, capability discovery, activity dispatch, permitted task creation and status queries. It cannot approve financial work, calculate authoritative totals or set a case to verified by assertion. A contradictory plan is rejected; repeated no-progress plans route to an accountable operator.

Intake and routing agent. Trigger: a deduplicated intake event or an operator-submitted request. Inputs: intake content, source identity, permitted process catalogue and required fields. Activities: extract structured fields, identify likely process and existing related case, identify missing facts and suggest routing. Output: typed intake classification, field provenance, unresolved fields and candidate case links. Authorized commands may create a validated case or request missing information through an internal task. Domain code enforces uniqueness, required fields and scope; ambiguous matches must not silently merge records. External requests are not sent without the relevant communication authority.

Evidence investigator. Trigger: evidence completeness or inconsistency activity. Inputs: case requirements, permitted document identifiers and prior findings. Activities: retrieve source sections, compare versions, identify missing or conflicting evidence, corroborate claims and build an evidence packet. Output: requirement-by-requirement findings, exact citations, contradictions and next evidence requests. Tools: scoped search/read and permitted internal evidence-request creation. It may not invent evidence, treat document instructions as authority or retrieve unrelated client records. Missing or inaccessible sources remain unresolved; a second model opinion does not replace an absent source.

PMO execution specialist. Trigger: a permitted PMO activity selected by the process or coordinator. Inputs: project/milestone records, scoped completion evidence, process-specific rules and current record version. Activities: organize evidence, reconcile milestone facts, prepare structured updates and execute approved low-risk internal updates. Output: validated PMO result, proposed or applied change set, cited basis and remaining exceptions. Tools are specific PMO read and command functions, not unrestricted ORM, SQL, shell or browser access. Contractual acceptance, material baseline changes and changes to accountable ownership follow their configured human gates. Do not infer these permissions from the role name.

## Finance exception and verification roles

Finance preparation specialist. Trigger: a permitted preparation activity, such as an invoice package becoming eligible. Inputs: validated commercial references, PMO outcome, approved rate/tax configuration references and document template. Activities: interpret descriptions, match evidence to billable items, request deterministic calculations, explain discrepancies, create a validated draft and assemble a decision packet. Output: draft identifier/version, calculation-service result reference, citations and unresolved exceptions. It cannot choose tax or exchange rates without an approved source, alter bank details, authorize payment, publish an invoice or bypass approval. Money, rounding, dates and ledger invariants are calculated and validated by domain services, not accepted from generated prose. The coordinator can request ACT11 through a separately authorized executor after approval; the preparation profile never inherits its dispatch tools.

Exception resolution agent. Trigger: a classified blocked activity, non-policy tool failure or reconciliation discrepancy. Inputs: error category, attempts, effect status, available recovery actions and relevant evidence. Activities: diagnose likely cause, gather additional evidence, select a permitted repair, retry only when safe, or open an actionable exception task. Output: diagnosis with evidence, attempted recovery, remaining uncertainty and next safe action. It cannot convert effect_unknown to failed_no_effect because a timeout occurred, retry an uncertain publication blindly, or ask another specialist to evade a refusal. A compensation is a separately authorized command, never an edit to erase the original event.

Outcome verification agent. Trigger: an activity produces an artifact or an adapter supplies a receipt. Inputs: expected postconditions, exact output and authoritative observations. Activities: interpret unstructured receipt/evidence discrepancies, propose verification findings and request deterministic checks. Output: cited verification assessment and unresolved mismatches. The verification service checks identities, versions, amounts, destination and required receipts; only that service or an authorized human can accept the formal postcondition. Model agreement is not independent proof of correctness. A separate prompt or model can provide critique, but authoritative checks must still pass.

Operator explanation agent. Trigger: an operator asks what happened or requests a summary within their access scope. Inputs: redacted structured activity history and current blockers. Activities: explain completed actions, evidence, consequences and safe next choices. Output: concise factual explanation with links and explicit uncertainty. This read-only profile cannot issue commands merely because an operator asks in chat; a separate authorized command flow must handle requested actions. It must never expose hidden chain-of-thought or claim that queued work succeeded.

## Per activity implementation mapping

The identifiers below are proposed reusable activity contracts. Tool names describe required capabilities to map onto existing services, not confirmed function names. Every activity inherits the trusted scope, version checks, audit trail, deadline, budget and recovery contract above. AGT identifiers below are stable acceptance-test references; bind them to actual test paths during consolidation.

- ACT01 classify intake. Role: Intake and routing. Input: deduplicated authorized source and permitted catalogue. Tools: scoped source read and classification service. Output: typed process candidates, extracted fields and citations. Autonomy: classification only; ambiguity remains unresolved. Verification: AGT01 checks expected classifications, missing fields, unsupported citations and malicious source instructions.

- ACT02 resolve case and process. Role: Intake and routing. Input: ACT01 result and authorized candidate cases. Tools: scoped case lookup and validated case creation. Output: existing case link or one new case with process version. Autonomy: eligible internal creation; no automatic ambiguous merge. Verification: AGT02 covers duplicate delivery, conflicting matches and wrong-scope lookup.

- ACT03 plan next permitted work. Role: Case coordinator. Input: current case revision, requirements, dependencies and available capability slice. Tools: scoped state read and activity dispatch. Output: validated plan revision and bounded child requests. Autonomy: only legal process edges; cannot waive gates. Verification: AGT03 covers missing-evidence alternate paths, illegal edges, child-budget reservation and no-progress loops.

- ACT04 investigate evidence. Role: Evidence investigator. Input: required facts and authorized source references. Tools: scoped search/read and evidence-link validation. Output: cited findings, contradictions and missing facts. Autonomy: read and allowed internal evidence linking. Verification: AGT04 covers fabricated citations, stale versions, conflicting sources and cross-case leakage.

- ACT05 request missing information. Role: Evidence investigator or Case coordinator. Input: specific missing fact, case scope and eligible internal resolver. Tools: internal HumanTask creation. Output: deduplicated information task and waiting state. Autonomy: internal task only; external communications need separately authorized command. Verification: AGT05 covers duplicate task creation, inaccessible recipients, missing resolver and wake after verified response.

- ACT06 reconcile PMO facts. Role: PMO execution specialist. Input: milestone/project versions and evidence packet. Tools: scoped PMO reads and deterministic reconciliation checks. Output: discrepancy report and proposed validated change set. Autonomy: analysis; acceptance or material baseline changes retain their gates. Verification: AGT06 covers conflicting completion evidence, stale target and unauthorized acceptance.

- ACT07 apply allowed internal update. Role: PMO execution specialist or an explicitly permitted profile. Input: typed change set, target version and evidence. Tools: specific internal-update command through gateway. Output: updated record/version and receipt or explicit refusal. Autonomy: only policy-classified eligible internal writes; other changes request approval. Verification: AGT07 covers concurrent writes, scope refusal, duplicate intent and precondition changes.

- ACT08 prepare Finance draft. Role: Finance preparation specialist. Input: validated commercial references, PMO evidence and approved calculation configuration. Tools: deterministic calculation and draft-creation commands. Output: draft version, calculation reference, narrative and unresolved discrepancies. Autonomy: validated draft creation, never publication under this capability profile. Verification: AGT08 covers rounding, currency/configuration references, conflicting rates, unsupported lines and duplicate draft requests.

- ACT09 assemble decision packet. Role: Finance preparation specialist or Case coordinator. Input: exact draft/target versions, destination, amount, evidence and intended command. Tools: packet assembly/canonicalization service. Output: immutable versioned packet and payload hash. Autonomy: packet preparation only. Verification: AGT09 covers hash equivalence and invalidation after material payload or evidence change.

- ACT10 resolve decision routing. Owner: deterministic policy service, invoked by Case coordinator. Input: trusted scope, exact packet and current policy/role/delegation data. Tools: approved policy resolver and HumanTask creation. Output: routing decision, eligible stages/principals or routing exception. Autonomy: resolve and assign only as policy allows; never make the decision. Verification: ROUTE-01 through ROUTE-16 below, plus AGT10 for decision-packet binding.

- ACT11 dispatch approved command. Initiator: Case coordinator; executor: narrowly authorized service identity. Input: exact command identity, valid approval references and current target version. Tools: command gateway and Outbox dispatch; first proof uses mock adapter. Output: command/attempt reference and observed effect status. Autonomy: resume after required human decision only if current checks pass. Verification: AGT11 covers stale/revoked approval, duplicate dispatch and changed destination. Finance preparation profile cannot call this tool.

- ACT12 reconcile uncertain effect. Role: Exception resolution agent with deterministic adapter service. Input: original command identity, attempt and effect_unknown evidence. Tools: scoped provider/mock status query using existing identity. Output: confirmed success, confirmed no effect or unresolved uncertainty with evidence. Autonomy: reconciliation reads; a retry requires established safety and current gateway checks. Verification: AGT12 covers crash after remote effect, delayed receipt and no blind retry.

- ACT13 verify outcome. Role: Outcome verification agent plus authoritative verification service. Input: expected postconditions, exact output, receipts and business records. Tools: deterministic validators and scoped evidence reads. Output: accepted verification record or explicit mismatch. Autonomy: service acceptance only when all mandatory checks pass; model assessment alone cannot close case. Verification: AGT13 covers fake receipt, wrong amount/destination/version and missing postcondition.

- ACT14 diagnose exception. Role: Exception resolution agent. Input: classified failure, attempts, effect status and allowed remedies. Tools: scoped diagnostics and specifically permitted repair commands. Output: evidenced diagnosis, recovery result or owned blocker. Autonomy: repairs only where safe and authorized; no retry after rejection or uncertain effect. Verification: AGT14 covers provider failure, schema repair exhaustion, no-progress loop, cancellation and absent resolver.

- ACT15 explain case history. Role: Operator explanation agent. Input: current operator scope and redacted event/evidence view. Tools: read-only case history. Output: cited explanation, uncertainty and available next actions. Autonomy: read-only; requests for action enter a separate gateway-authorized flow. Verification: AGT15 covers scope redaction, no hidden reasoning disclosure and queued-versus-completed truthfulness.

## The typed agent activity contract

Every activity must be registered with a stable activity_type and semantic version. Its record contains the following groups; this is a minimum interface, not a requirement to create a table for each group.

- Identity and lineage: activity_id, case_id, process_run_id, parent_activity_id, AgentRun reference, capability version, prompt version and schema version. Preserve the link from intake to final outcome.

- Trigger and eligibility: event_id, trigger_type, expected case revision, legal process stage, prerequisites and applicable policy references. Deduplicate trigger delivery before starting another logical activity.

- Trusted scope: organization, client/project scope where applicable, initiating actor, service identity, delegated capability set and data classification. These are resolved server-side, not accepted from model-supplied fields.

- Input: typed business fields, immutable evidence references, required facts, optional facts and explicit unknowns. Include source versions and capture time. Do not substitute a narrative summary for the source record.

- Allowed work: read-tool allowlist, command allowlist, permitted resource scope, required human gates and output destinations. Discovery returns only currently eligible capabilities.

- Execution limits: deadline, per-call timeout, maximum steps, parallelism, child depth/count, retries and cumulative token/cost reservation. Define tested configuration per activity profile; missing limits fail configuration validation.

- Output: structured status, findings and citations, artifacts and versions, proposed command intents, command/receipt references for work already executed, unresolved questions and next eligible activity requests. Required outputs must be checked before acceptance.

- Verification: deterministic validators, business postconditions, required evidence and any human review rule. Output schema validity is necessary but not sufficient.

- Recovery: error category, effect classification, safe-retry rule, reconciliation operation, retry owner, cancellation handling and escalation owner.

- Audit and evaluation: model/provider identifier, configuration/version references, sanitized tool events, usage, latency, test-suite version and structured outcome. Store concise evidence-backed decision summaries, not private reasoning traces.

An activity request is not executable authority. The server creates the trusted envelope, validates the current policy and record revision, reserves budget and grants only the required capability slice. Model output may reference evidence and select an available operation; it may not supply a role override, unrestricted URL, credential or policy bypass.

Illustrative request and result schemas should be represented in typed code and tested fixtures. These names describe the contract and do not prescribe a framework:

```text
ActivityRequest
  activity_type, activity_version
  case_id, expected_case_revision, process_run_id
  input, evidence_refs
  deadline, budget_reservation_ref
  trusted_context_ref  # server-created and immutable to the model

ActivityResult
  activity_id, attempt_id
  status: succeeded | waiting | blocked | failed | cancelled
  findings[], evidence_refs[], artifact_refs[]
  command_refs[], verification_refs[]
  unresolved_questions[], next_activity_requests[]
  error_category?, usage
```

A command intent should contain action_type, action_version, target_ref, expected_target_version, typed arguments and supporting evidence references. The gateway resolves caller scope, computes a canonical payload hash, creates or resolves the business idempotency identity and binds the required approval. Do not permit a model-generated random idempotency key to turn every retry into a new business effect. The exact hashing/canonicalization algorithm must be versioned and exercised with equivalent payload, changed amount, changed destination and changed evidence fixtures.

## How one agent execution cycle works

1. Observe. Load current durable case state and outstanding activity, command and human-task records. Check cancellation, revocation and policy changes. Do not resume from chat history alone.

2. Constrain. Build the minimum authorized evidence context and current eligible capability list. Reserve the configured budget and load model/prompt versions. An expired or unavailable approval is not an eligible execution path.

3. Plan. The coordinator returns a short structured plan with prerequisites, expected outcomes and stopping conditions. Persist a plan revision and the evidence references used. The plan is an operational artifact, not a transcript of private reasoning.

4. Validate. Code validates the plan against the process envelope, schemas, dependency graph, scope and available budget. Invalid edges or attempts to bypass gates are rejected before tools run.

5. Act. Dispatch one or more eligible activities through existing task services. Each tool call independently rechecks permission, scope and resource version. All business writes pass through the same command gateway used by operators and workflows.

6. Observe effects. Record tool outcomes, command attempts, receipts and effect classification. A provider timeout can mean effect_unknown. Local worker fencing prevents stale local completion; it cannot undo a remote call already accepted.

7. Verify. Run postcondition checks against authoritative state. An agent may explain the result; the verifier owns acceptance. Mark the activity successful only when its own contract is satisfied, and leave the case open if downstream requirements remain.

8. Replan or wait. Use the new evidence to choose another permitted activity. Wake on a correlated event when waiting for a person or receipt; do not repeatedly call the model while nothing has changed. Detect repeated state/plan fingerprints and stop no-progress loops.

9. Finish or escalate. A process service accepts the final outcome only when all mandatory postconditions pass. Otherwise create an owned exception or information task with cause, evidence, permitted next actions and an explicit deadline or escalation policy.

Persist activity lifecycle transitions such as queued, claimed, running, waiting_for_input, waiting_for_approval, waiting_for_effect, verifying, succeeded, blocked, failed and cancelled only after mapping them to existing state models. Keep attempt state separate from logical activity and case state. A worker crash creates a new attempt for the same logical activity after reconciliation, not a second business operation. Final result writes need the current lease/fencing token and optimistic version check.

## Autonomy delegation and human control

Define autonomy on each command, not on an agent's confidence score. Read operations remain scoped. Approved low-risk internal writes can run autonomously when all preconditions and record-version checks pass. Examples are attaching an existing authorized evidence reference, creating a draft, recording a classification, opening an internal task and scheduling an eligible verification. These still require bounded permissions, audit records and a tested recovery path.

Consequential actions require the configured business approval bound to the exact payload, destination, record version and evidence packet. The agent may assemble and request that approval, then continue automatically when a valid decision arrives and the gateway rechecks current authority. Any material change invalidates the old decision. High model confidence never waives a gate. Do not silently broaden permitted communications, deployment authority, credentials, financial commitments or data sharing during consolidation.

Human rejection is a decision, not a transient tool failure. The coordinator may resolve identified defects and submit a genuinely revised packet when the process permits; it must not repeatedly resubmit the same rejected operation. Human edits become versioned evidence and may invalidate dependent activities. An operator takeover pauses new agent writes for the affected scope until explicitly released; in-flight external actions remain visible until reconciled.

### Delegation and coordination

A parent issues a child a typed objective, authorized evidence slice, capability subset, budget slice, deadline and required output schema. A child cannot expand its permissions, choose another tenant, grant approvals or recursively spawn unrestricted workers. Capability delegation can only narrow rights. Budget is reserved centrally so parallel agents cannot independently spend the full case allowance.

Parallelize independent evidence reads or independent draft sections. Serialize conflicting writes to the same business object through domain concurrency checks. If child findings disagree, preserve both and their evidence; a coordinator cannot select the convenient answer and hide the conflict. Only reconcile through authoritative facts or a human decision. Child completion records a result; it does not directly advance the parent business case without validation.

## Context memory models and recovery

Durable business state lives in existing application records. AgentRun stores execution identity and relevant metadata. The plan and activity history are recoverable operational state. Retrieved context is a temporary, permission-filtered view; model conversation context is not authoritative memory. Summaries must retain source references and known gaps. Recheck access when resuming or retrieving a referenced artifact; prior visibility does not imply ongoing permission.

Use separate context per case and capability. Include only data needed for the activity and never credentials. Approved knowledge sources, process rules and source documents are distinguishable from untrusted instructions embedded in documents. Model outputs and tool results are untrusted inputs until validated. Do not permit self-modification of prompts, policies, tools or persistent shared memory. Proposed reusable knowledge must follow a versioned review/publish process. Retention and deletion rules must cover prompts, extracts, traces and provider processing, not just final artifacts.

A configurable model policy maps activity profiles to evaluated models. Lower-cost models may handle extraction and routine classification when tests support them. More capable models may handle ambiguous synthesis or exception diagnosis. Model capability is not business authority. Set allowed provider/data-region constraints and fallback routes explicitly. A fallback must meet the same data, schema and tool constraints; never send confidential evidence to a new provider merely because the primary failed. Do not embed current model prices as permanent business logic. Use configurable price metadata and reconcile estimated versus reported usage. A provider outage should permit deterministic work to continue and place model-dependent work in an explicit recoverable state.

### Failure recovery and stopping

Classify failures as invalid input, missing evidence, policy refusal, conflict/stale version, provider transient, tool transient, schema invalid, budget/deadline exhausted, cancellation or effect_unknown. Each class has an explicit handler and one retry owner. Limited output-schema repair can correct formatting, but cannot add missing evidence or erase a refusal. Safe transient retries retain logical identity and consume the same overall budget. Effect_unknown always enters reconciliation before another attempt capable of duplicating an external effect.

Cancellation prevents new actions at the gateway and requests cooperative worker stop. It does not claim to reverse dispatched work. Reconcile any in-flight remote action and show its eventual outcome. A kill switch can disable a capability, provider or process scope without erasing history. Budget exhaustion and no-progress loops end in a visible owned blocker. The UI must distinguish a requested pause from a confirmed safe pause and a requested retry from verified resolution.

## An agent driven PMO to Finance example

The following is a representative proposed process. Actual field names, acceptance authorities and billable rules must be mapped to the repository's approved process contracts before implementation.

1. An authorized milestone-completion event is deduplicated and linked to a case. The coordinator sees the required completion evidence and invoice-preparation goal.

2. The evidence investigator finds a missing acceptance reference. It gathers other permitted records, identifies exactly what is absent and creates an internal PMO information task. The case becomes waiting_for_input; no invoice is marked eligible merely because a model expects approval.

3. PMO supplies a versioned acceptance record. The event wakes the same run. The coordinator selects a PMO reconciliation activity, rather than repeating all intake work. The activity validates evidence linkage and records an allowed internal update.

4. The Finance specialist requests deterministic billable-line calculation from approved references, prepares narrative and creates a draft through the command gateway. It checks the returned draft version and totals against service output. Conflicting rates stop the draft from advancing and open a Finance exception.

5. The coordinator assembles the exact publication packet and creates the required HumanTask. The console displays amounts, recipient, evidence, document version and consequences. The model cannot approve its own packet.

6. The eligible human approves. A later edit to the recipient or amount makes that approval stale. Otherwise the gateway rechecks authority and queues the approved publication command. In the first proof, this targets the mock adapter, not live delivery or payment.

7. If the mock adapter records acceptance but the worker crashes before local completion, recovery queries by the same business idempotency identity. The receipt is attached to the original command; no second invoice is created.

8. Deterministic verification checks the receipt, payload hash, invoice identity, destination and relevant status. The verification agent explains any mismatch. Only a passing verified outcome closes the process and appears in Completed outcomes.

This example should run unattended through the permitted internal steps, pause only for missing information or required decisions, and resume from durable state. The agent's observable choices, commands, evidence and outcomes are visible in the operator console. That is the required demonstration of agent-native operation.

## Evidence that agent activities work

For every activity show role, objective, current step, status, start/finish time, evidence used, commands requested and completed, artifact versions, cost/budget status, blocker and next safe action. Show parent-child relationships without forcing operators to read raw JSON. Plans are concise intent summaries; execution events and receipts prove what actually happened. The console must not render “agent succeeded” as “business outcome verified”.

Required tests include:

- Complete evidence allows autonomous eligible internal work through draft creation without a human clicking every tool call; mandatory publication approval still blocks dispatch.

- Missing evidence causes the agent to select authorized retrieval or an internal information request, then resume the same case when evidence arrives.

- Conflicting evidence produces an explicit unresolved finding, never a fabricated resolution or selective omission.

- A malicious document requests a role change or exfiltration. Neither tool discovery nor gateway scope expands, and the injection is recorded safely.

- A valid-schema answer with a nonexistent or unsupported citation fails evidence validation.

- A model requests an unlisted command or child with broader permissions. The request is denied before any business effect.

- Two parallel activities exceed a shared budget if considered separately. Central reservation prevents overspend and leaves recoverable blockers.

- Duplicate intake or child-completion events do not duplicate the logical activity or business effect.

- Approval is revoked or target version changes between planning and dispatch. The gateway rejects the action and routes to fresh review.

- An external effect occurs before a worker crash. Reconciliation discovers it and prevents duplicate execution.

- Provider outage, schema repair exhaustion, cancellation and repeated no-progress plans produce distinct actionable states.

- One client's evidence cannot appear in another case's tool result, summary, trace or export.

- A fake receipt, changed amount or wrong destination prevents verified completion even when the model says success.

- A new prompt/model/capability version must pass the same representative and adversarial activity suite before promotion. Record quality, refusal correctness, completion rate, cost, latency and human correction rate separately; never trade authorization failures for a higher average quality score.

Each first-release process must reference the activities it uses, allowed autonomy, human gates, evidence requirements, postconditions and test IDs. A process without this mapping remains incomplete even if a generic agent endpoint exists. Preserve the full PMO and Finance coverage requirement; do not imply that the first invoice demonstration covers all 108 processes.

## Activity identifiers and ownership resolution

Assign stable proposed identifiers to reusable activities, independently of role and model names. The initial catalogue is ACT01 classify intake; ACT02 resolve case and process; ACT03 plan next permitted work; ACT04 investigate evidence; ACT05 request missing information; ACT06 reconcile PMO facts; ACT07 apply an allowed internal update; ACT08 prepare Finance draft; ACT09 assemble decision packet; ACT10 resolve decision routing; ACT11 dispatch approved command; ACT12 reconcile uncertain effect; ACT13 verify outcome; ACT14 diagnose exception; ACT15 explain case history. These are proposed capabilities, not the authoritative 108-process list. A role may own several activities; deterministic services implement actions such as approval routing and dispatch even when an agent initiates the activity.

ACT10 is a deterministic policy-resolution service, not an LLM guessing who should approve. Its input includes trusted organization/client/project scope, activity and action versions, target record/version, action risk, amount and currency where relevant, initiating principal and applicable business policy references. Its output is a versioned routing decision containing matched rule IDs, the evaluated condition results, required approval stages, eligible principals at each stage, delegation basis, separation-of-duties exclusions, expiry and escalation route. The agent can call this service, explain its answer and create the prescribed task; it cannot rewrite the returned authority.

Keep the following responsibilities distinct:

- Process owner maintains the business outcome and process definition.

- Activity owner is accountable for this work unit and its operational follow-through.

- Policy owner maintains a particular policy and resolves interpretation questions through the approved change process.

- Approval authority is the role or designated responsibility permitted by the policy to make this specific decision.

- Resolved approver is a currently active, eligible person holding that authority in the applicable scope.

- Escalation recipient receives overdue or blocked work; receiving an escalation does not itself grant approval power.

- System executor is the narrowly scoped service identity allowed to dispatch an approved action. It is not the human approver.

A rule must reference the authority source, effective period, version, policy owner, scope predicates, decision type and approved resolution method. Role membership and delegations are independently versioned organizational data. No developer fixture, model suggestion or free-text document is an authoritative appointment of an approver. Mock data must label fictional principals and never be promoted as live responsibility assignments.

Routing first validates the request and scope, selects effective applicable rules, applies documented precedence and any explicitly configured combination rule, resolves role holders, removes ineligible principals and returns either a complete decision plan or a typed routing exception. Multiple applicable rules cannot silently collapse to the least restrictive one. Mixed currencies must use the policy's approved threshold/FX convention and effective rate reference; no model conversion decides authority. Missing rates, rule conflicts, empty role membership or ambiguous scope block consequential execution and create a task for the configured owner to resolve.

Human-task creation snapshots the routing decision, but eligibility is rechecked when a person claims, decides and when the approved command dispatches. Policies can preserve historical workflow versions for audit without grandfathering revoked authority. If a relevant policy, amount, destination, evidence requirement, target version, role membership or delegation changes, determine whether the decision remains valid using explicit versioned rules. If validity cannot be established, invalidate or suspend the decision and reroute; do not silently retain old authority.

If the normal policy/process resolver is missing or ineligible, put the routing exception into a protected governance-resolution queue whose eligible administrators and assignment rule are explicitly configured. Queue visibility does not grant approval authority. If that governance resolver is also missing, retain owner_needed as an unassigned configuration blocker, expose it to existing authorized administrators and prevent consequential execution. Do not fabricate an assignee, grant a role, use a convenient executive or repeatedly create identical tasks. A valid authority configuration must be established through the approved administration process before work resumes.

## Delegation and multi stage approval

A delegated approver must have an active, bounded delegation covering decision type, scope, limits and dates. Apply separation of duties after delegation resolution, so delegation cannot make the requester approve their own action. Do not infer delegation from absence, job seniority or email forwarding. If no eligible alternate exists, surface a routing exception. An urgent or break-glass path exists only where explicitly designed and approved, with named authority, narrow conditions, independent recording and retrospective review; it is not a general agent fallback.

For sequential approvals, define stage prerequisites and whether a rejection terminates the request or returns it for revision. For parallel approvals, define quorum, mandatory roles, veto behavior, duplicate-person counting and whether one person can satisfy more than one role. A person holding two roles must not automatically count twice. Expiry, abstention, nonresponse and rejection are distinct events. Escalation may notify or reassign according to policy. First-release consequential actions never treat nonresponse, timeout or escalation as approval. Any proposed exception requires a separate explicit approved policy decision and tests before enabling it; it is not a built-in fallback or something an agent may infer.

The console must let an operator trace an activity to its policy, policy owner, routing rule, required approver role, resolved person, current eligibility and outstanding stage. Explain “Finance approval required because condition X matched policy Y version Z” using service-generated facts, not invented prose. Show absent/missing authority and the responsible resolver. Policy-owner maintenance belongs in protected administration with validation, effective-date checks, overlapping-rule detection, test cases, review/approval and a change log. Agents may draft suggested changes but cannot self-publish authority changes.

## Approval and ownership scenario catalogue

The first release must test at least the following routing scenarios and preserve the mapping from test ID to actual process/activity. Enumerating these cases does not establish that every future business situation is known; an unknown case must stop safely and be added through the extension process.

- ROUTE-01. Normal single approver: exact scope resolves one eligible principal, with visible policy reason.

- ROUTE-02. Several eligible approvers: assignment/claim rule is deterministic, race-safe and policy-consistent; only valid decisions count.

- ROUTE-03. No policy or no owner: execution blocks with a typed configuration exception; the model cannot invent an owner.

- ROUTE-04. Multiple conflicting policies: block and expose matched rules and policy owners; never pick the convenient policy.

- ROUTE-05. Absent, inactive, departed or suspended role holder: use only an active valid delegation or approved reassignment rule.

- ROUTE-06. Requester is otherwise an approver: separation-of-duties exclusion applies, including delegation and multi-role membership.

- ROUTE-07. Cross-client or cross-project role holder: scope mismatch prevents assignment and evidence access.

- ROUTE-08. Threshold boundary, negative adjustment or split request: exact deterministic amount/risk rules apply; splitting must not evade configured aggregation rules.

- ROUTE-09. Foreign-currency threshold or missing FX source: use approved convention or block, never model-estimated authority.

- ROUTE-10. Sequential, parallel, quorum and veto decisions: enforce the configured dependency and counting semantics under concurrent responses.

- ROUTE-11. Approver rejects, requests changes, abstains or times out: each produces its distinct workflow result, without automatic retry as approval.

- ROUTE-12. Role, delegation or policy is revoked after approval: dispatch recheck fails or requires the explicitly specified revalidation route.

- ROUTE-13. Target, amount, destination or material evidence changes: invalidate the exact-payload approval and present the changed packet for review.

- ROUTE-14. Human overrides a proposed agent finding: preserve both finding and authorized decision, require reason/evidence where configured and rerun dependent checks.

- ROUTE-15. A policy owner changes an approval rule: change governance and conflict checks run before it becomes effective; no retroactive erasure of old decisions.

- ROUTE-16. Agent cannot resolve an unprecedented case: record unknown_case with evidence, send to the configured process/policy resolver and prevent consequential action until a reviewed rule or explicit permitted case decision exists.

A complete release coverage record links process ID → activity ID/version → action ID/version → policy IDs/versions → policy owner → approval authority → resolved-principal mechanism → escalation owner → test IDs. Current role assignments are resolved at runtime, not hard-coded into the build document. Review this record with PMO and Finance before live transition, and keep unresolved authority assignments visible rather than filling them with plausible names.

## Human work decisions and responsibility

HumanTask should remain the authoritative place for business decisions and accountable human work. The console should bring the relevant evidence and proposed change to the person, rather than ask them to approve an unexplained agent message. SDK interruptions, links and callbacks are delivery mechanisms, not approval authority.

### Proposed task and decision contract

Link the task to the case, run, step, target record and exact proposed action. Record the eligible role or candidate set, current assignee, claim state, due or escalation rule, required evidence, decision options and the applicable policy evidence. On decision, retain actor identity, timestamp, decision, reason, payload hash, target version, scope and any expiry.

Use separate records or events when a work item gathers missing information before a decision. Do not overwrite an earlier rejection with a later approval. An approved decision is valid only for its bound scope and payload; it is not indefinite permission for the agent to continue acting on a changed invoice.

### Claiming and reviewing work

Borrow Flowable’s distinction between claiming and merely assigning, and Frappe’s link from a workflow action to the business document. Claim must be race-safe. Delegation should preserve who remains responsible and why the handoff occurred. A supervisor’s reassignment must not impersonate the original approver or erase the history.

Sources  [Flowable task contract](https://github.com/flowable/flowable-engine/blob/main/modules/flowable-engine/src/main/java/org/flowable/engine/TaskService.java)  |  [Frappe business linked workflow actions](https://github.com/frappe/frappe/blob/develop/frappe/workflow/doctype/workflow_action/workflow_action.py)

The decision panel should show the proposed invoice, changes from the prior version, supporting completion evidence, policy reason, consequences and unresolved questions. Offer approve, reject, request information or authorized delegation according to the task type. Missing evidence should be visible before approval, not discoverable only in a technical trace.

### Safety and recovery

Enforce segregation of duties and self-approval rules in services. Recheck current authority at execution; a person’s earlier eligibility does not survive revocation automatically. Concurrent claim, expired approval, changed target version, replayed callback and rejected decision must produce explicit outcomes. Rejection must not leave a queued action eligible for dispatch.

- Two simultaneous claims yield one valid owner; an old owner cannot complete the task after reassignment.

- A payload change invalidates the approval; an approval callback cannot authorize a different action or case.

- The business trail identifies who requested, reviewed, approved, executed and verified, including delegation and overrides.

### Decision to discuss

Who can approve each invoice class, what thresholds or exceptions require another reviewer, and when does approval expire? These are PSL policy decisions to capture and test, not defaults to inherit from a sample application.

## Versioned policies and controlled configuration

Policies determine what may happen, who may decide and which evidence is necessary. Reuse the existing policy lifecycle and deterministic services. The proposal is to make policy versions visible and testable across work, agents and actions; it is not to move every business rule into a new policy engine.

### A policy contract people can review

Separate business policy from secrets and deployment settings. A proposed policy version should identify its scope, rule or decision table, relevant action and process versions, required inputs, approval requirements, autonomous-action limits, effective period, author, reviewer, tests and change reason. Amount-based rules must identify currency and the trusted amount source. Do not invent approval limits to make a demo work.

Use an explicit draft, review, approved, active and retired lifecycle, with revocation handled as a current safety condition. Preserve old versions for evidence. A process definition can reference its historical policy basis, but executing an action still requires current authorization and active safety controls. A material policy change may pause runs or require renewed approval rather than silently reinterpret history.

### The authorization interface

The common gateway should ask a deterministic authorization interface about the trusted actor, action, resource, current business facts and relevant decision. Return allow or deny with a reason code, obligations and policy version. Missing required data should fail closed for protected actions. Model confidence or persuasive text is never an authorization input.

OPA demonstrates a policy decision point for agent tool calls, but introducing it adds a runtime and policy language. Keep the interface in PSL first; consider extraction only if cross-service governance makes it worth the operating cost. DMN is useful for readable decision tables even without installing a DMN engine.

Sources  [OPA agent tool policy pattern](https://www.openpolicyagent.org/docs/agent-tool-calling)  |  [OMG decision models](https://www.omg.org/dmn/)

### Console and deployment behavior

An authorized policy editor needs a version diff, test results, affected actions and a clear activation step. Operators need the business reason why a case is blocked, not unrestricted policy internals. A supervisor should see which active runs may be affected before a consequential policy change. Secrets, tokens and connector credentials belong outside this editor.

- Test missing facts, conflicting rules, tenant scope, self-approval, policy revocation while queued and an expired decision.

- Replaying old evidence explains the historical decision without granting old permissions to a new execution.

- Activating or rolling back a policy preserves the change history and does not silently rewrite prior decisions.

### Decision to discuss

Identify business owners and independent reviewers for Finance and PMO policy. Decide which policy changes affect already-approved work, which require reapproval and who may apply an emergency stop. Treat exceptions as explicit governed decisions, not undocumented configuration edits.

## Evidence outputs and the meaning of verified

The factory should make it possible to prove why it acted and what actually resulted. Preserve existing citation requirements, TaskEvent, domain records and receipt recovery. Add a clear distinction between evidence used to decide, artifacts generated, external acknowledgement and the verified business postcondition.

### Proposed evidence and output contracts

An EvidenceReference should identify the source record or artifact, immutable version or content hash where supported, location or excerpt locator, owner and tenant scope, capture time, provenance and permitted access. Avoid copying sensitive source content into every run. Validate that an agent’s citation resolves to material available to that run and supports the specific finding.

An OutputRecord should identify the intended result, linked business record and version, generating action or agent run, artifact version, review state, dispatch receipt and verification result. Verification should state what was checked, against which expected payload and business rule, by which code or authorized person, and when. A generated PDF is not proof that an invoice was published or accepted.

### A practical verification sequence

For the PMO line, the assessment cites milestone completion evidence. Domain services calculate the draft. A human decision binds the publication payload. The adapter records its external reference and acknowledgement. Verification compares the reference, target, amount, currency and payload identity with the intended action and the resulting local state. A mismatch creates an exception; it does not increment a success counter.

Show generated, reviewed, submitted, acknowledged and verified as distinct facts where they apply. Verification may be automated for strong machine-checkable postconditions, manual where business judgement is necessary, or blocked when the external result is unknown. Define those rules per action rather than using one universal green status.

### Retention access and failure behavior

Keep business evidence and decision history authoritative in PSL, not solely in model traces. Ordinary change-history rows are not inherently tamper-proof. Define append-only or protected-write controls, correction events, retention, redaction and authorized export deliberately. Never erase an adverse attempt by replacing it with the latest success.

Sources  [Frappe change history reference](https://github.com/frappe/frappe/blob/develop/frappe/core/doctype/version/version.py)  |  [OpenAI SDK trace controls](https://openai.github.io/openai-agents-python/tracing/)

- Test fabricated citations, a source edited after assessment, missing artifacts, revoked evidence access and cross-tenant references.

- A receipt for the wrong invoice or payload must fail verification. Replayed receipts must not create another result.

- An auditor can reconstruct the intended action, approval, attempts, receipt and verification without depending on an agent summary.

### Decision to discuss

What evidence is sufficient for each PMO completion and invoice publication, who may verify exceptions, and how long must the source and decision trail remain available? Agree these rules before calling a run verified or building aggregate completion metrics.

## External adapters receipts and reconciliation

Adapters translate authorized PSL actions into external API calls and responses into receipts, without another approval system. Begin with a mock, then substitute an approved sandbox or live connector under the same command and verification contracts.

### Proposed adapter boundary

An adapter accepts a validated action version, business idempotency key, authorized target, canonical payload, tenant-bound credential reference and correlation context. It returns a normalized outcome with provider reference, acknowledgement time, relevant response evidence and error classification. Credentials stay server-side and should not be exposed to the agent, browser or business evidence store.

Document provider support for idempotency, business-reference lookup, signed webhooks, status queries and cancellation. Implement that actual contract, not sample assumptions. Version mappings, scopes and receipt parsing alongside the action.

Use a tri-state publish result: confirmed success with receipt, confirmed no effect with a classified error, or effect unknown. The corresponding reconcile operation returns confirmed success, confirmed absent or unresolved. “Confirmed absent” is valid only when the provider can actually establish it; absence of a response is not that proof.

Sources  [Activepieces authentication and action structure](https://github.com/activepieces/activepieces/blob/main/packages/pieces/CLAUDE.md)  |  [Community connector example](https://github.com/activepieces/activepieces/tree/main/packages/pieces/community/airtable)

### Uncertain outcomes are first class

A timeout does not mean nothing happened. After ambiguous success, place the action in an uncertain or awaiting-reconciliation state. Query the provider using the same business reference where possible, match the result to the intended payload, and retain the evidence. If the provider offers neither idempotency nor a reliable lookup, use a controlled manual reconciliation path instead of blind automatic retries.

Webhooks must be authenticated, deduplicated, correlated to the right tenant and action, and checked for stale or out-of-order updates. An inbound status is evidence to evaluate, not a command to bypass policy. A correction or compensation is a new authorized action with its own receipt; it must not rewrite the original attempt as if it never occurred.

### The console recovery path

Show provider, last observation, action reference, requested effect and what is still unknown. Offer safe recheck, request information, escalate or reconcile actions according to capability. A retry button should explain why retry is safe and what key it will reuse. Keep dispatch state separate from business verification.

- Contract-test malformed responses, rate limits, permission errors, transport timeout after success and provider outage.

- Replay signed and invalid callbacks, send callbacks out of order, and test a receipt belonging to another tenant or payload.

- Swap the mock for the selected connector in the same proof suite; require matching semantics, not just a successful API call.

Discuss the authoritative publication system, sufficient receipt and reconciliation owner. Resolve credentials, test environments and authorized effects before connecting it; the proof does not require a live payment.

## Monitoring evaluations and release evidence

Operational monitoring should show where work is stuck and what action is safe next. Evaluation should establish whether agents and business controls behave as intended. Neither a dashboard nor an LLM score replaces acceptance evidence. Keep metrics secondary in the console and maintain the authoritative business trail in PSL.

### Three separate evidence layers

Deterministic tests prove authorization, calculations, state transitions, concurrency and effect handling. Model evaluations measure evidence extraction, classification, useful explanations, tool selection and abstention. Operator UAT proves that a person can understand the case, make a correct decision and recover exceptions. Record all three separately; a strong model score does not make a failed authorization test acceptable.

For each release candidate, retain the application revision, definition and action versions, policy versions, adapter versions, model and prompt configuration, dataset version, test result and known limitations. Do not silently compare evaluations from different evidence sets or tool permissions. Use synthetic data and explicitly marked mock adapters until connected testing is authorized.

### Agent evaluation contract

Build a small reviewed set of representative PMO completion and Finance cases, including incomplete evidence, conflicting totals, stale records, malicious instructions in documents and requests outside the actor’s scope. Validate citations and command proposals mechanically. Human review can assess narrative usefulness. LLM judges may assist with quality scoring, but never decide whether an authorization or accounting invariant passed.

Sources  [PydanticAI controlled test models](https://pydantic.dev/docs/ai/guides/testing/)  |  [PydanticAI evaluation examples](https://github.com/pydantic/pydantic-ai/blob/main/docs/evals.md)

### Operational signals and controls

Track queue age, unassigned work, blocked reasons, decision latency, stale worker observations, retries, uncertain effects, receipt mismatches, verification latency and agent budget use. Correlate these to cases and responsible owners. Define alert thresholds from business risk and observed behavior rather than inventing targets in this document.

Provider errors, budget exhaustion and tool refusal must leave an explicit recoverable state. A kill switch should stop new relevant execution and describe what happens to in-flight commands; it must not promise to undo an action already committed externally. Trace export needs redaction and tenant isolation. Optional trace products are not replacements for the business audit trail.

- The proof suite must include crash injection, racing claims, stale or revoked decisions, duplicate effects, tenant isolation and definition-version compatibility.

- A reviewer can distinguish not evaluated, failed and passed. Preserve incomplete coverage rather than painting all process IDs green after one successful line.

- UAT must show an operator finding a blocker, reviewing evidence, declining a bad proposal and reconciling an uncertain outcome without raw logs.

### Decision to discuss

Name the release approver, operational owner and evaluation reviewer. Agree severity rules, what blocks expansion to another process, and what evidence is required to move from mocked to connected operation. The current partial acceptance status is a starting point, not a release claim.

## Prove one PMO completion to invoice line

Prove PMO completion evidence through invoice draft, human approval, controlled publication, receipt and verified output. Begin with a mock external adapter; no live payment is required.

| Stage | Proposed behavior and completion evidence |
| --- | --- |
| 1  Intake | Link project, milestone, completion evidence and authorized client context. Give the run a stable business identifier. |
| 2  Agent assessment | Check evidence completeness, explain discrepancies and propose invoice inputs. Allow only scoped, policy-permitted tools; return cited findings. |
| 3  Deterministic draft | Existing domain services calculate amounts and validate billable facts. Persist the draft and the exact proposed publication payload. |
| 4  Human decision | HumanTask displays evidence, changes and consequences. An eligible person approves or rejects the exact payload and version. |
| 5  Controlled action | Recheck authority and preconditions, then enqueue through the existing outbox. Publish to the mock adapter using a stable idempotency key. |
| 6  Verified output | Match receipt to the intended invoice and payload. Close only when business state and receipt agree; otherwise create a visible exception. |

### Before and after failure tests

“Before” is the baseline to run against today’s implementation, not an assertion that it currently fails. “After” is the required observable result for the proposed line.

| Inject into the baseline | Required result after the change |
| --- | --- |
| Two workers claim the same task | One current lease owner; stale workers cannot finalize. Recheck dispatch ownership; deduplicate or reconcile in-flight remote races. |
| Repeat a callback or outbox delivery | One business effect and a recorded duplicate or existing receipt, not another invoice publication. |
| Crash after external success before finish | Recover or reconcile the original receipt; do not blindly send again. |
| Change invoice details after approval | Reject stale approval and require a decision on the changed payload. |
| Revoke the approver before execution | Execution-time authorization fails; the action remains blocked. |
| Resume a v1 wait after a v2 deploy | Retain definition and history; recheck current authority and require a fresh decision when policy changes invalidate approval. |
| Inject instructions into evidence | Ignore attempted privilege changes; reject fabricated citations and out-of-scope tools. |

Retain run and record versions, policy, action, decision, attempts, effect key and receipt for each test. A successful click or worker log is insufficient evidence.

## Implementation gates and decisions to discuss

Proceed incrementally across the agreed PMO and Finance scope. Each phase should leave a stronger, usable system and explicit acceptance evidence. The first line validates shared architecture; it does not reduce the eventual factory to a single workflow.

### Gate one agree the operating contracts

Map logical case, run, work item, decision, command and evidence responsibilities to current models. Define the first process’s completion and exception outcomes. Review console queue and case-workspace behavior with PMO and Finance operators. Exit with agreed contracts, owners and a baseline failure matrix; do not start by installing an engine.

### Gate two prove the mocked line

Implement the smallest missing shared contracts and console interactions around existing services. Run PMO completion evidence through assessment, invoice draft, exact-payload approval, mocked publication, receipt and verification. Show exceptions as real work. Exit when concurrency, stale approval, crash recovery and operator acceptance tests pass with retained evidence.

### Gate three improve only the missing capabilities

If typed agent tooling is weak, compare the existing adapter against one SDK behind AgentRun. If reliability is inadequate, compare a focused PSL repair against one isolated engine candidate. Avoid introducing both changes at once. Exit with measured benefit, known cost, deployment compatibility, rollback behavior and no duplicate authority.

### Gate four connect and expand

After authorization and connector readiness review, substitute the approved real integration for the mock and prove receipts and reconciliation. Extend the same contracts across additional PMO and Finance processes, grouping similar patterns where appropriate. Each process still needs its own policy, evidence and acceptance criteria. BaaS remains deferred from the first release.

### The design decisions worth discussing first

- Which existing record anchors a case, and which links or fields are actually missing?

- Which actions may agents perform autonomously, and what makes each one operationally reversible?

- Who can approve, delegate, change policy, reconcile uncertainty and verify output?

- Which facts make an invoice output verified, rather than merely generated or acknowledged?

- What should a supervisor see in the console without broadening access to sensitive case evidence?

- Which failure, if any, cannot be addressed cleanly by the current engine and therefore justifies a new dependency?

The implementation plan should follow these decisions and measured gaps. This document proposes no new delivery deadline and does not treat an earlier mock-data handover target as a production guarantee. Preserve the full scope while making progress demonstrable one validated increment at a time.

## Six primary sources for selective reuse

The ranking favors fit with PSL’s existing Python application, clear reuse boundaries and concrete implementation examples. “Adapt” means a candidate for narrow reuse after review, not a recommendation to install the whole product. “Reference” means borrow the design and write PSL-native behavior.

| Priority and source | Reuse decision | Most useful contribution and boundary |
| --- | --- | --- |
| 1  Frappe Framework | Adapt contracts | Business-linked workflow actions, transition validation, assignments and change history. MIT framework; ERPNext application is GPLv3. Not a drop-in Django library. |
| 2  Activepieces | Adapt selected actions | Versioned connector inputs, authentication, triggers and outputs. Community code is a strong selective donor; enterprise paths and third-party exceptions differ. |
| 3  Flowable OSS | Reference task semantics | Claim, delegation, suspension and case versus process states. Apache 2.0 source; borrowing semantics does not require adding Java services. |
| 4  Windmill OpenFlow | Adapt spec and clients | Process definition, input forms, waiting steps and run inspection. Apache 2.0 specs and named clients; server and UI have different terms. |
| 5  PydanticAI | Conditional adapter | Typed specialist outputs, deferred tool requests and test models behind existing AgentRun. MIT. Add only if current adapter has a measured capability gap. |
| 6  Temporal samples | Reference reliability | Safe message handling, replay tests, patching and versioning. MIT samples; adopting the runtime is a separate, higher-cost decision. |

Sources  [Frappe source](https://github.com/frappe/frappe)  |  [Activepieces actions](https://www.activepieces.com/docs/build-pieces/building-pieces/create-action)  |  [Flowable source](https://github.com/flowable/flowable-engine)  |  [OpenFlow specification](https://github.com/windmill-labs/windmill/blob/main/openflow.openapi.yaml)  |  [PydanticAI source](https://github.com/pydantic/pydantic-ai)  |  [Temporal samples](https://github.com/temporalio/samples-python)

### Why this is not a platform shopping list

Frappe supplies the strongest operations-product model, Activepieces the clearest reusable action structure, and Flowable precise human-task behavior. Windmill is useful for process and run presentation. PydanticAI and Temporal contribute narrower agent and reliability capabilities. Together they describe interfaces to improve, not six services to deploy.

### Keep the alternatives conditional

The existing agent adapter is the default. PydanticAI and OpenAI Agents SDK are conditional alternatives, not additional layers. Preserve AgentRun and HumanTask authority. LangGraph, SpiffWorkflow and Restate need a proved gap; n8n and Camunda remain references. Sources were reviewed for the October 30 research; verify the selected release and license before adoption.

Sources  [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)  |  [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)  |  [SpiffWorkflow BPMN](https://spiffworkflow.readthedocs.io/en/latest/bpmn/index.html)  |  [Restate server license](https://github.com/restatedev/restate/blob/main/LICENSE)

Sources  [PydanticAI deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)  |  [Version policy](https://pydantic.dev/docs/ai/project/version-policy/)  |  [Controlled tests](https://pydantic.dev/docs/ai/guides/testing/)  |  [OpenAI approval example](https://github.com/openai/openai-agents-python/blob/main/examples/agent_patterns/human_in_the_loop.py)

## Concrete product modules worth studying

### Frappe for work linked to business records

Study transition validation in workflow.py, business-linked decisions in workflow_action.py, routing in assignment_rule.py and field-level history in version.py. The proposed PSL adaptation is a shared work item with the actual project or invoice, proposed change, eligible decision makers and history together. Keep authorization in PSL services. Frappe’s ORM and session dependencies make whole-file transplantation unattractive; ordinary change history also does not establish an immutable audit ledger.

Sources  [Transition validation](https://github.com/frappe/frappe/blob/develop/frappe/model/workflow.py)  |  [Workflow actions](https://github.com/frappe/frappe/blob/develop/frappe/workflow/doctype/workflow_action/workflow_action.py)  |  [Assignment rules](https://github.com/frappe/frappe/blob/develop/frappe/automation/doctype/assignment_rule/assignment_rule.py)  |  [Version history](https://github.com/frappe/frappe/blob/develop/frappe/core/doctype/version/version.py)

### Activepieces for a versioned action registry

Its piece structure separates connector authentication, action properties, implementation, triggers and shared code. Apply that contract to PSL actions used by the operator UI, processes and agents alike. Proposed fields include action version, input and output schemas, required permission, side-effect class, timeout, retry policy and receipt shape. Keep credentials server-side; route business writes through existing services. Selected TypeScript connectors need an adapter rather than silently becoming Python-native modules.

Sources  [Action authoring guide](https://www.activepieces.com/docs/build-pieces/building-pieces/create-action)  |  [Airtable community connector](https://github.com/activepieces/activepieces/tree/main/packages/pieces/community/airtable)  |  [Piece structure](https://github.com/activepieces/activepieces/blob/main/packages/pieces/CLAUDE.md)

### Flowable for precise human task behavior

TaskService distinguishes claim from simply assigning a user, and separates delegation, suspension and activation. Emulate those distinctions in the existing HumanTask lifecycle. A claim must be race-safe; delegation should preserve responsibility and history. Task state, process state and invoice state are separate facts. The inspected API does not itself verify that an assignee exists, so identity and authority checks remain PSL responsibilities. Do not mistake commercial Flowable Work UI for OSS engine functionality.

Sources  [TaskService contract](https://github.com/flowable/flowable-engine/blob/main/modules/flowable-engine/src/main/java/org/flowable/engine/TaskService.java)  |  [Flowable releases and boundaries](https://github.com/flowable/flowable-engine/releases)

### Windmill for definitions and run inspection

Use OpenFlow as a reference for versioned process definitions, inputs, steps and suspended execution. Borrow the operator questions: what is waiting, on whom, why, and what happened on earlier attempts? A human wait should release the worker. Adapt the Apache-licensed specification or client material selectively; treat UI and server implementation as reference-first. A resume URL must never replace an authenticated PSL decision or confer business authority.

Sources  [OpenFlow guide](https://www.windmill.dev/docs/openflow)  |  [OpenFlow source](https://github.com/windmill-labs/windmill/blob/main/openflow.openapi.yaml)  |  [Approval behavior](https://www.windmill.dev/docs/flows/flow_approval)

## Prove the current engine before choosing another

A new orchestrator is justified by an unmet failure or operating requirement, not by the factory label. Establish a baseline with the existing Outbox, HumanTask, TaskEvent and service-layer controls. Record actual results; “primitive exists” and “failure case passed” are different evidence.

| Area | Existing starting point | Evidence still required |
| --- | --- | --- |
| External effects | Outbox, run_once, receipt recovery | Crash after a successful external call but before local finish must not create a second effect. Reconcile ambiguous outcomes. |
| Human decisions | HumanTask, scoped actors | Race-safe claim, rejected and expired decisions, revoked authority, and approval bound to the exact payload and target version. |
| Waiting and deployment | Workflow state and event history | A v1 wait survives a v2 deployment with its definition and history intact; current authority is rechecked before execution. |
| Agent execution | AgentRun, budgets, evidence | Untrusted document text cannot grant tool authority; wrong-tenant access, fabricated evidence and budget exhaustion fail safely. |
| Recovery and audit | TaskEvent, domain services, receipts | Reconstruct who decided, what was executed, which version governed it and why the output is verified. |

### Use an explicit decision gate

- If the baseline passes, keep the current engine. Borrow better contracts, deployment tests and operator views without adding infrastructure.

- If a reproducible durability gap remains, compare the smallest extension against one isolated engine prototype. Assign one owner for scheduling, retries, waits and idempotency at each boundary.

- If long-running cross-system histories, replay and deployment management exceed the current model, evaluate Temporal. If a narrower Python and Postgres recovery gap remains, evaluate DBOS. Neither is a default install.

Temporal provides useful samples for safe message handlers, patching, replay and worker versioning. DBOS provides an official Django integration, durable messages and checkpointed execution; its own architecture still requires idempotent steps. No engine makes a remote financial effect atomic with PSL’s database.

Sources  [Temporal safe message handlers](https://github.com/temporalio/samples-python/tree/main/message_passing/safe_message_handlers)  |  [Replay samples](https://github.com/temporalio/samples-python/tree/main/replay)  |  [DBOS Django integration](https://docs.dbos.dev/integrations/django)  |  [DBOS architecture](https://docs.dbos.dev/architecture)

Operational cost is part of the decision. Temporal adds server or cloud operations and replay discipline. DBOS still needs an explicit executor lifecycle, database capacity and deployment compatibility; its Django startup example is not a production topology prescription. Do not let a new engine create a parallel approval store or compete with the current outbox.

Sources  [Temporal versioning](https://docs.temporal.io/develop/python/workflows/versioning)  |  [DBOS workflow upgrades](https://docs.dbos.dev/python/tutorials/upgrading-workflows)

## License boundaries and a safe reuse process

Public source is not blanket permission to copy, embed or host. The distinctions below guide selection; they are not legal clearance. Review the exact files, dependencies, notices, distribution model and version before reuse. Hosted services, models, enterprise features and third-party connectors may have separate terms.

| Project or material | Boundary that changes the reuse decision |
| --- | --- |
| Frappe and ERPNext | Frappe Framework is MIT; ERPNext is GPLv3. Do not apply the framework license to ERP business implementation. GPL conveyance obligations are not the same as AGPL network provisions. |
| Activepieces | MIT outside specified enterprise directories and third-party exceptions. Paid governance features are product references, not automatically free implementation material. |
| Windmill | Specs and named clients are Apache 2.0; backend and UI are AGPLv3 with enterprise exceptions. Prebuilt Community Edition terms allow as-is internal/API use but restrict modification, embedding or wrapping; review the intended use. |
| Flowable and agent SDKs | Flowable OSS is Apache 2.0. PydanticAI and OpenAI Agents SDK repositories are MIT. Keep notices and inspect selected dependencies and examples. |
| Temporal and DBOS | Temporal SDK, server and samples have MIT licenses. DBOS Python core is MIT, but its separate Django starter demo license was not verified. Automatic workflow upgrading is a DBOS enterprise feature. |
| SpiffWorkflow and Restate | SpiffWorkflow engine and cited examples are LGPLv3. Restate SDK and examples are MIT; server is BSL 1.1 source-available with a specific additional grant, not an OSS-default stack. |
| n8n and Camunda | n8n uses Sustainable Use terms, not standard OSS; external user workflow configuration can require commercial licensing. Camunda 8 core self-managed production use requires an enterprise license. |
| bpmn.io toolkits | Custom license for bpmn-js, dmn-js, form-js and cmmn-js. Preserve notices and keep the required watermark fully visible and unobscured; do not label it plain MIT. |

Sources  [Frappe MIT](https://github.com/frappe/frappe/blob/develop/LICENSE)  |  [ERPNext GPL](https://github.com/frappe/erpnext/blob/develop/license.txt)  |  [Activepieces terms](https://github.com/activepieces/activepieces/blob/main/LICENSE)  |  [Windmill terms](https://github.com/windmill-labs/windmill/blob/main/LICENSE)  |  [Flowable source](https://github.com/flowable/flowable-engine)  |  [DBOS core](https://github.com/dbos-inc/dbos-transact-py/blob/main/LICENSE)  |  [SpiffWorkflow](https://github.com/sartography/SpiffWorkflow/blob/main/COPYING)  |  [Restate server](https://github.com/restatedev/restate/blob/main/LICENSE)  |  [n8n use cases](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case?trk=article-ssr-frontend-pulse_little-text-block)  |  [Camunda terms](https://docs.camunda.io/docs/reference/licenses/)  |  [bpmn.io terms](https://bpmn.io/license/)

### Before importing any code

Freeze an exact release and full commit SHA. Record repository, source path, applicable LICENSE and NOTICE, dependency licenses, required attribution and every modification. The links in this brief navigate inspected live branches; they are not an immutable source bundle. Reopen the selected files at the pinned revision, implement the smallest PSL-specific example, and run the relevant failure and security tests before adoption.

Recent release activity is useful maintenance evidence, not proof of safety, integration fit or support. Keep a written adopt, reference or defer decision for each candidate. The next implementation decision should close a demonstrated PSL gap, not expand the stack for its own sake.

## Consolidation baseline and implementation authority

Revision dated 1 November 2026. The component design remains a proposed specification, not a report that the factory has been implemented. Preserve working features and stronger existing controls. Reconcile each requirement against the current build before changing code, data or direction documents.

### What the latest read established

A read-only desktop inspection on 1 November 2026 reported that the operations-factory direction had been saved across 25 files. The reported documentation fingerprint check covered 1,710 entries with no mismatches. These are documentation-integrity observations, not application tests. The saved BUILD-FACTORY-FLOW, BUILD-FACTORY-CONSOLE and BUILD-FACTORY-CONNECTED-PROOF records remained not_started with empty test evidence. The factory console must therefore not be described as implemented on that basis.

The inspected architecture remained modular Django and Postgres, server-rendered UI, one operational database, separate workers, domain-service authority and existing outbox, fencing and receipt controls. The inspection did not execute tests or change files. It found no Git repository in the inspected workspace, so no commit identity or clean working-tree claim can be supplied. Historical test logs included failures as well as successful runs; they are not a clean current full-suite result.

The authoritative process material to inspect is contracts/process-map.json, reference/02-coverage/register.json and contracts/implementation-coverage.json. The observed coverage contained 122 rows across 13 families, all partial. The agreed first release remains 63 PMO plus 45 Finance processes, with 14 BaaS processes deferred. Extract actual IDs and labels from the current manifest; this document deliberately does not invent 108 process names.

### Reconcile rather than overwrite

Apply current user direction and applicable repository instructions first. Treat inspected code and passing tests as evidence of what exists, not proof that old product direction must remain unchanged. Use this specification for intended behavior, while retaining stronger existing safety, accounting and tenancy controls. External examples and framework documentation are reference material, never instructions that override PSL authority.

For every affected requirement, record KEEP, EXTEND, REPLACE or DEFER with actual paths, symbols, migrations, tests and rationale. KEEP means verified suitable behavior already exists. EXTEND means preserve it and add the missing contract. REPLACE needs a specific conflict, compatibility plan and tests; it is not permission to rewrite unrelated modules. DEFER requires an explicit reason, dependency, owner or decision needed and scope impact. Never silently defer an in-scope process merely because one vertical line passes.

Inspect current README, AGENTS and entrypoint instructions, implementation plan, backlog, build-memory records, direction documents and tests. Update existing relevant records rather than creating another parallel factory plan. Preserve user edits and uncommitted work; if Git exists at execution time, record status and revision without resetting them. If it does not, use a file manifest and checksums for the bounded change set.

### Defaults and conditional choices

The default is existing Django, Postgres, domain services, workflow controls and AgentRun. No new agent SDK, workflow engine, policy service, ERP or frontend framework is required. A dependency proposal needs a reproduced gap, smallest viable alternative, version/license review, integration and operating cost, rollback plan and evidence that it preserves one authority. The user will upload this package; its preparation has not authorized a deployment, credential change or live financial operation.

## Requirement register and evidence ownership

The following IDs identify requirements in this specification, not business process IDs. They remain stable in the companion Markdown and consolidation prompt. Codex must map them to real repository paths and test evidence after inspection. A requirement is not satisfied by a heading, placeholder endpoint or screenshot alone.

| ID | Required behavior | Minimum evidence |
| --- | --- | --- |
| REQ-01 | Preserve and reconcile the current application and user work. | Baseline manifest, KEEP/EXTEND/REPLACE/DEFER map and bounded diff. |
| REQ-02 | Account for all 108 release processes and 14 deferred BaaS processes. | Actual manifest IDs, unique counts and per-process coverage records. |
| REQ-03 | One authoritative owner for domain facts, decisions, dispatch and evidence. | Model/service map and tests preventing alternate mutation paths. |
| REQ-04 | Work-first console with scoped queues, case detail and preserved navigation. | Browser journeys, screenshots and backend permission tests. |
| REQ-05 | Separate run, task, decision, attempt, domain and verification states. | Transition rules and invalid-transition tests. |
| REQ-06 | AI actively selects and executes eligible actions within a governed envelope. | Agent traces showing allowed choice, action, verification and replan. |
| REQ-07 | Reusable activity contracts with shared aggregate budgets and bounded delegation. | Catalogue, schemas, budget exhaustion and delegation tests. |
| REQ-08 | Context and memory never widen actor, tenant or resource authority. | Cross-tenant, revoked-access and prompt-injection tests. |
| REQ-09 | One deterministic command gateway for UI, processes and agents. | Equivalent authorization results across all callers. |
| REQ-10 | Exact command and approval binding with concurrency protection. | Stale version, payload change, duplicate and revoked-approval tests. |
| REQ-11 | Versioned policy evidence with current authorization at dispatch. | Policy activation, revocation and in-flight race evidence. |
| REQ-12 | Idempotent dispatch and explicit uncertain-effect reconciliation. | Lost response, key collision, lease loss and provider-expiry tests. |

### What each evidence record must say

For a requirement, retain requirement_id, applicable_process_ids, intended behavior, observed implementation, change classification, paths and symbols, schema or migration impact, test IDs, exact test command, environment, revision or manifest fingerprint, result, artifact paths and limitations. Name an owner only when actually assigned; otherwise record owner_needed. Do not invent ownership to make a table look complete.

Use result values NOT_EVALUATED, BLOCKED, FAIL and PASS. A test not run is NOT_EVALUATED, even if the code appears correct. BLOCKED names the prerequisite and who must decide or provide it. PASS names the assertion and evidence, not just an exit code. A mocked connector result must remain marked mock in every view and report.

## Complete process coverage and release states

| ID | Required behavior | Minimum evidence |
| --- | --- | --- |
| REQ-13 | Authenticated durable webhook intake with deduplication and ordering rules. | Duplicate, invalid-signature, delayed and out-of-order callback tests. |
| REQ-14 | Versioned evidence, deterministic checks and explicit output verification. | Citation lookup, stale source, wrong receipt and verifier tests. |
| REQ-15 | Timers, deadlines, business clocks and escalation ownership are explicit. | Clock, timezone, pause/resume and duplicate wake-up tests. |
| REQ-16 | Capability-gated administration, delegation, export and emergency stop. | Permission matrix and direct-request negative tests. |
| REQ-17 | Secure inputs, secrets, connector egress and data retention. | Security tests and reviewed configuration; no secrets in artifacts. |
| REQ-18 | Safe schema/data migration and in-flight-run compatibility. | Dry run, backfill counts, compatibility and rollback rehearsal. |
| REQ-19 | Monitoring, agent quality evaluation and audit evidence remain distinct. | Versioned evaluation results, operational alerts and audit reconstruction. |
| REQ-20 | Accessible, responsive console including stale and conflict states. | Keyboard, focus, narrow-screen and status-announcement evidence. |
| REQ-21 | One full PMO-to-Finance line proves the shared architecture. | End-to-end mock run plus deliberate lost-response recovery. |
| REQ-22 | Each release process earns its own acceptance result. | Manifest-derived process matrix and unresolved-gap register. |
| REQ-23 | Dependencies remain conditional and reuse retains provenance. | Decision record, exact version/file license checks and notices. |
| REQ-24 | Consolidation updates existing direction and reports evidence honestly. | Updated canonical records, bounded change summary and residual risks. |
| REQ-25 | Deterministic activity to policy owner and active approver mapping. | ROUTE-01 through ROUTE-16 and AGT10; current owner, delegation, SoD and revocation evidence. |

### Per process mapping schema

Use or extend the existing coverage record rather than create a competing authority. Each actual process ID needs its original label and source, family, release scope, trigger, actors and capabilities, inputs, entry guards, domain records, valid branches and parallel work, reusable agent activities, actions, human gates, evidence requirements, outcomes, exception and rework routes, integrations, console journey, tests and acceptance state. Link shared requirements by ID instead of repeating their prose.

Preserve source-required branches, parallel activities, rework, cancellation and human waits. Do not force every process into the same linear intake-to-invoice path. Where the manifest and application disagree, record both sources and resolve the discrepancy explicitly. Do not manufacture IDs or rename approved process identities simply to fit a new catalogue.

### Separate readiness from completion

DESIGN_MAPPED means the process is accounted for, not implemented. IMPLEMENTED_UNVERIFIED means code exists but assertions are not established. MOCK_ACCEPTED requires representative synthetic runs and failure tests with a marked mock adapter. CONNECTED_ACCEPTED requires authorized integration tests and verified receipts. UAT_ACCEPTED requires the responsible operators’ acceptance evidence. PRODUCTION_AUTHORIZED requires the separate operational and deployment decision. These labels are proposed reporting states to map to existing vocabulary, not a demand for another database enum.

One connected planning-to-Finance line does not certify all 108 release processes or all 122 architecture rows. Report coverage denominators and as-of time. The release report must expose partial, blocked and not-evaluated rows rather than averaging them into a green completion metric.

## Typed command and concurrency contracts

These are proposed logical contracts. Bind them to inspected PSL models and service signatures; do not create a parallel command store if suitable records already exist. Field names may be adapted through a documented mapping without weakening the invariants. All example IDs are synthetic placeholders, not manifest entries or execution-ready payloads.

### Common field rules

IDs are nonempty opaque strings in the repository’s established format. Versions are required immutable identifiers or monotonically increasing integers as appropriate. Timestamps are timezone-aware UTC values with explicit serialization. Money uses the Finance domain’s fixed-precision representation and currency, never binary floating-point model arithmetic. A missing required field is invalid; null means explicitly not applicable only where allowed by the schema.

| Command field | Required type and authority |
| --- | --- |
| schema_version, command_id, command_version | Required string, string, integer; command service owns identity and revision. |
| tenant_id, actor_id, process_id, run_id | Required strings derived or resolved from trusted context; process_id must exist in the manifest. |
| action_id, action_version, target_id, target_version | Required typed references validated against the registry and current resource. |
| payload, payload_hash | Required object and digest; canonical payload is immutable after authorization. |
| effect_key, evidence_snapshot_id | Required business effect identity and evidence reference; both scoped to tenant and action. |
| policy_version, decision_id | Policy reference required; decision reference required only when policy demands human approval. |
| expected_version, requested_by, created_at | Required concurrency token, trusted initiator and server timestamp. |

### Illustrative command shape

```json
{
  "schema_version": "command.v1",
  "command_id": "cmd_demo_001",
  "command_version": 1,
  "process_id": "<actual manifest process ID>",
  "run_id": "run_demo_001",
  "action_id": "<registered publication action>",
  "action_version": "v1",
  "target_id": "invoice_demo_001",
  "target_version": 3,
  "payload": {"amount": "100.00", "currency": "USD"},
  "payload_hash": "<computed canonical digest>",
  "effect_key": "<stable tenant scoped business key>",
  "evidence_snapshot_id": "evidence_demo_001",
  "policy_version": "<reviewed policy version>",
  "decision_id": "decision_demo_001"
}
```

The displayed shape omits the trusted envelope for readability; the service must supply and validate every required context field above. Canonicalization must cover destination, recipient, amounts, currency, target/version and every execution-relevant field, with defined string, decimal and null rules. Persist its algorithm version. The agent’s explanation is not the canonical payload.

## Decisions receipts verification and event records

### Exact human decision binding

A Decision requires decision_id, task_id/version, command_id/version, payload_hash, target_version, evidence_snapshot_id, policy_basis_version, decided_by, decided_at and outcome. expires_at may be null only when policy explicitly permits no expiry. Reason is required for the outcomes configured by policy. Outcomes include APPROVED, REJECTED, EXPIRED, REVOKED and SUPERSEDED; do not overwrite an old decision to represent a new one. Current dispatch authorization is recorded separately from the historical policy basis.

```json
{
  "schema_version": "decision.v1",
  "decision_id": "decision_demo_001",
  "task_id": "task_demo_001", "task_version": 4,
  "command_id": "cmd_demo_001", "command_version": 1,
  "payload_hash": "<same computed command digest>",
  "target_version": 3,
  "evidence_snapshot_id": "evidence_demo_001",
  "outcome": "APPROVED",
  "decided_by": "<server resolved eligible actor>",
  "policy_basis_version": "<reviewed policy version>"
}
```

## Provider facts verification and event records

A Receipt requires receipt_id, command_id/version, attempt_id, adapter_id/version, effect_key, outcome_class, request_fingerprint, observed_at and response_evidence_ref. external_reference is required on confirmed success when the provider supplies one; null must carry an explicit provider limitation. Preserve original responses only within access and retention policy. The receipt reports a provider observation, not automatic business completion.

```json
{
  "schema_version": "receipt.v1",
  "command_id": "cmd_demo_001", "attempt_id": "try_demo_002",
  "outcome_class": "CONFIRMED_SUCCESS",
  "external_reference": "mock_invoice_demo_001",
  "request_fingerprint": "<approved request digest>",
  "response_evidence_ref": "receipt_evidence_demo_001",
  "environment": "mock"
}
```

A VerificationResult requires verification_id, case/run and target/version references, receipt or artifact references, verifier_id/version, checked_at, expected_payload_hash, individual checks and overall ACCEPTED, NEEDS_REVIEW or REJECTED. Each check includes a stable code, expected value or rule, observed evidence and result. Manual verification records an authorized person and reason; it is not an unrestricted override of failed accounting checks.

All decision and receipt examples are abbreviated illustrations; required fields from the surrounding contracts must be supplied and validated by trusted services.

An AuditEvent requires event_id, schema_version, case/run and relevant child references, actor or service identity, event_type, occurred_at, recorded_at, prior/current version, correlation and causation IDs, outcome code and evidence references. Retain sequence or version semantics per aggregate. Correct history by an additional event, not by silently editing a prior assertion. Do not log secrets or hidden model reasoning.

## Transition transactions and error semantics

Each implemented transition must name the actor/capability, expected record version, guards, local transaction boundary, external effect if any, emitted event and recovery rule. The following is a minimum transition matrix, not a replacement for domain-specific states.

| Transition | Guard and owner | Transaction and recovery |
| --- | --- | --- |
| Proposed to validated | Command service validates scope, schema, target and evidence. | Persist version/hash and validation result; invalid proposals remain inspectable. |
| Validated to awaiting approval | Policy requires a human decision. | Create/link one HumanTask atomically with readiness state; repeated wake-ups reuse it. |
| Approved to queued | Current authority, decision binding, expiry and target still valid. | Persist authorization evidence and outbox intent in one local transaction where required. |
| Queued to claimed | Eligible worker acquires current lease/fence. | Claim atomically; stale owner cannot finalize a newer attempt. |
| Claimed to dispatched | Recheck ownership and current dispatch conditions. | Record attempt; network call occurs outside the DB transaction. In-flight revocation is a race, not guaranteed cancellation. |
| Dispatched to uncertain | Result does not prove success or no effect. | Preserve identity and enter reconciliation; do not create a new effect key or blindly resend. |
| Receipt to verified | Verifier matches approved payload, target and required postconditions. | Persist checks/evidence; mismatch becomes an owned exception. |
| Cancel requested to cancelled | No effect occurred, or provider confirms cancellation under its contract. | Retain decision and observation. If dispatch may have happened, reconcile instead of claiming cancellation. |
| Completed to correction needed | Authorized discovery of invalidated evidence or business error. | Open a linked correction/rework case or supported reopened state; preserve original completion evidence. |
| Effect to compensated | New action is independently authorized. | Execute and verify a new command; never delete the original receipt. |

### Stable result and error vocabulary

Use typed results such as QUEUED, NEEDS_APPROVAL, ALREADY_APPLIED and WAITING_RECONCILIATION. Minimum failures are INVALID_INPUT, FORBIDDEN, STALE_VERSION, STALE_EVIDENCE, APPROVAL_REQUIRED, APPROVAL_EXPIRED, APPROVAL_REVOKED, POLICY_CHANGED, IDEMPOTENCY_CONFLICT, LEASE_LOST, BUDGET_EXHAUSTED, DEPENDENCY_UNAVAILABLE and EFFECT_UNKNOWN. Map these to the repository’s API conventions; do not infer safe retry from HTTP status alone.

An error response must include a stable code, safe human message, correlation ID, retryable boolean, permitted next action and current version only when the caller may see it. Return field errors for invalid input. A concurrency conflict preserves unsent operator notes but requires a fresh decision. Hidden controls and friendly errors never replace server authorization.

## Idempotency inbound events and business clocks

### One business effect across repeated attempts

Define database uniqueness over the relevant tenant, action and business-effect identity. Repeated submission with the same key and canonical payload returns the existing command or result. The same key with a different execution payload returns IDEMPOTENCY_CONFLICT and produces no new effect. Repeated attempts have different attempt IDs but retain the business key and approved fingerprint.

Document provider key retention and expiration. If the provider’s deduplication window has elapsed, reconciliation must establish the previous result before any retry that could duplicate it. A provider’s temporary “not found” response under eventual consistency is not proof of no effect. Only its documented final-absence contract or a controlled human investigation can justify that conclusion.

Local fencing prevents stale finalization, not an already-sent remote request from completing. Record the authorization and ownership observations before dispatch, and recheck as close to the call as practical. If revocation or cancellation races with dispatch, retain the sequence and classify the result honestly. Compensate only through a new authorized command.

### Durable inbound event processing

Use the existing inbox/event mechanism where available. Otherwise add the smallest durable intake needed to authenticate, validate, record and deduplicate callbacks before they wake business work. A callback identity is scoped by provider, tenant and event ID or a reviewed fingerprint. Verify signature, expected destination, timestamp/replay window and key version using that provider’s contract. Do not invent a universal replay window or assume every provider signs identically.

Acknowledgement must mean the event was durably accepted or deliberately rejected according to the integration contract, not that the business process completed. Resolve tenant and command through trusted mappings, not callback text alone. Treat a duplicate as a no-op with retained evidence. For delayed or out-of-order events, compare provider version or aggregate ordering and requery authoritative state where necessary; an old status must not regress a verified record silently.

### Timers and escalation

Store instants in UTC, with the business timezone, calendar and clock rule explicitly associated with deadlines. Define whether each timer measures elapsed time or business hours; identify pause reasons, resume behavior, daylight-saving handling, overdue calculation and the escalation owner. Missing configuration is visible and blocks claims of SLA compliance.

Timer wake-ups are repeatable identifiers, not authority to advance a process. Re-evaluate current state and guards after a wake-up; a cancelled or already-resolved item must not be escalated again. Show due time, timezone, pause reason, last observation and responsible person in the console. Test duplicated wake-ups, pause/resume, clock changes and overdue work waiting on external parties.

## Capabilities security and protected data

Define capabilities against current PSL roles rather than invent a new identity system or assume SSO exists. The table describes responsibilities to map, not grants that become active because this document names them. Every query and mutation must check tenant, resource, process and action scope server-side.

| Responsibility | Capabilities to decide and test | Default boundary |
| --- | --- | --- |
| Requester or PMO operator | Create/read own scoped cases, submit evidence, answer information tasks. | Cannot self-approve where segregation is required; no implicit Finance publication right. |
| Work operator | Read eligible queues, claim, correct allowed fields, request information. | Claim does not grant every action; access follows current resource authority. |
| Approver | Review exact packet and approve/reject within delegated scope. | Cannot alter the approved payload while preserving the same approval. |
| Supervisor | Reassign/escalate and inspect permitted operational context. | Supervision does not automatically grant access to all sensitive evidence. |
| Reconciler or verifier | Recheck provider facts and verify named postconditions. | No blind resend or accounting override; correction is separately authorized. |
| Policy or configuration administrator | Draft/review/activate permitted configuration. | Separation of author and approver where policy requires it; secrets remain separate. |
| Auditor or exporter | Read retained evidence and authorized exports. | Export is a capability, not an automatic consequence of screen access. |
| Agent or worker service identity | Invoke only registered capabilities under delegated context. | Cannot mint tenant, roles, approvers, credentials or additional tools. |

### Inputs and network boundaries

Apply the existing application’s authentication, session, CSRF and request-validation controls. Review evidence uploads for size, allowed type, actual content/MIME and malware handling before downstream processing. Treat document text, retrieved pages and connector responses as untrusted data. Model prompts cannot grant permissions or supply executable handlers.

Constrain connector and evidence-fetch destinations with reviewed egress rules, URL parsing and SSRF defenses, including redirects and private/internal address handling appropriate to the deployment. Do not hand agents unrestricted HTTP, shell, database-write or credential tools. Required exceptions need a scoped adapter and review, not a prompt instruction.

Minimize model inputs to authorized task-relevant evidence. Keep credentials in tenant-bound server-side configuration. Redact logs and trace exports before transmission. Define retention, correction, revocation and deletion handling for source artifacts, snapshots, outputs and audit events; preserve required historical evidence without retaining unnecessary copies. Access revocation must be checked when evidence is reopened or exported, not only when the original snapshot was created.

Test direct forbidden requests, cross-tenant links, revoked evidence, malicious uploads, injected instructions, unsafe URLs and secret leakage. Block the affected path if its security configuration is unknown; continue unrelated safe work and record the exact decision needed.

## Migration compatibility and operational recovery

### Expand and verify before switching

First inspect actual schemas, migrations, workers, fixtures, tests and active-run representations. Prefer additive fields, references and constraints that existing code can tolerate. Do not delete or rename domain models, historical IDs or working routes merely to match terminology. Capture the current data shape and a bounded file or revision baseline before changing it.

Use expand, backfill, verify, switch and contract as a sequence, not one destructive migration. Expand supports old and new readers where needed. Backfill derives links or versions from real evidence with a restartable, idempotent job. Verify counts, uniqueness, tenant consistency, missing associations and representative records; unresolved mappings remain explicit. Switch a bounded cohort or feature flag only after compatibility tests. Contract removes obsolete paths only after readers, writers and in-flight runs no longer depend on them and the removal is authorized.

### Preserve active work

Retain the original definition and activity versions needed to explain or resume active runs. Define compatibility for task payloads, approved hashes, adapter requests and queued commands. Do not silently regenerate a materially different payload from mutable records during resume. Re-evaluate current authority while retaining historical decision evidence. A version migration needs explicit eligibility, transformation, validation, audit and rollback behavior.

Use one authoritative writer for each fact. A temporary compatibility projection may exist, but dual writers or two approval stores need an explicit consistency protocol and are not the default. Separate mock and real connector configuration. New real-provider execution and externally consequential actions stay disabled until explicitly authorized; a feature flag is not permission to bypass business approval.

### Rollback and restoration

Rehearse schema/data rollback or forward repair on a safe representative copy. Establish backup and restore procedures, then demonstrate recovery of decisions, outbox identity, receipts and active runs. Restoration must not reset business-effect keys and cause old commands to be sent again. Identify post-backup remote effects that require reconciliation before workers resume.

A code rollback cannot undo an external invoice, message or financial effect. Drain or pause the appropriate work, inspect uncertain attempts and preserve old compatible workers where required. Compensation is a new authorized action. State what is irreversible and which parts require manual reconciliation.

### Exit evidence

Record migration version, data counts before/after, rejected or unmapped rows, validation results, active-run compatibility tests, restore rehearsal, flag defaults and rollback limits. Define deployment, credential and live-operation approvals separately; this package does not grant them. If the environment cannot support a safe rehearsal, report the specific missing resource and leave the relevant readiness claim blocked.

## Acceptance tests for controls and recovery

The following tests establish shared invariants. Implement them using the existing test framework and real service boundaries, with synthetic data and a mock provider initially. Record exact commands, environment, revision or file fingerprint, assertions and artifact paths. Test IDs are stable across the human and Markdown specifications.

| ID | Setup and action | Required assertion and evidence |
| --- | --- | --- |
| TEST-01 | Two actors or workers claim the same eligible item concurrently. | One current owner; stale local finalization rejected; retain race trace. |
| TEST-02 | Submit identical command twice, including a repeated click. | One business command/effect key; original result returned or referenced. |
| TEST-03 | Reuse effect key with changed amount, destination or target. | IDEMPOTENCY_CONFLICT; no second effect; both request fingerprints auditable. |
| TEST-04 | Change a draft after approval, then request dispatch. | Stale approval rejected; new decision required for changed payload. |
| TEST-05 | Revoke authority or policy after queueing. | Pre-dispatch recheck blocks where possible; any in-flight race is recorded and reconciled, never falsely cancelled. |
| TEST-06 | Mock publishes successfully but response or local finish is lost. | EFFECT_UNKNOWN; reconciliation finds the same publication; no duplicate. |
| TEST-07 | Expire provider idempotency window and return temporary not-found. | No blind retry or false confirmed absence; unresolved state stays owned. |
| TEST-08 | Replay valid callback and send invalid, delayed or out-of-order callbacks. | Durable dedupe; invalid rejected; old event cannot silently regress current state. |
| TEST-09 | Access another tenant’s case, tool result, evidence or export. | Denial at service/query boundary; no sensitive existence or payload leak. |
| TEST-10 | Edit/revoke source evidence or fabricate a citation. | Citation/version check fails; downstream readiness or approval is invalidated as required. |

### Evidence quality rules

A test log that merely reaches an endpoint is insufficient. Assert the database/business state, authorized actor, effect count, event history and receipt where relevant. Preserve failure artifacts as well as success. Record intentionally unsupported provider behavior and which adapter or deployment would need additional evidence. Do not use an LLM judge to decide whether these invariants passed.

Run the baseline before changing a relevant control where feasible, then the focused regression suite after each bounded slice. If an existing failure predates the change, record it distinctly; do not relabel it passed or silently weaken the test. A missing runtime or fixture is a blocker, not an excuse to claim implementation verified.

## Acceptance tests for agents console and release coverage

| ID | Setup and action | Required assertion and evidence |
| --- | --- | --- |
| TEST-11 | Feed injected evidence instructing the agent to expand scope or skip approval. | Allowed tool set and actor remain fixed; attempted escalation rejected and visible. |
| TEST-12 | Exhaust the aggregate budget through tools, delegation and retries. | Shared cap stops further calls; resumable bounded state and owner are recorded. |
| TEST-13 | Crash or interrupt an activity after a tool result or internal write. | Resume from persisted business facts; do not repeat an effect merely by replaying chat. |
| TEST-14 | Give the coordinator two eligible safe next actions and new contradictory evidence. | It selects, acts, verifies and revises within the envelope; no unsupported completion or invented evidence. |
| TEST-15 | Cancel before dispatch, during dispatch and after confirmed success. | Distinct cancelled, uncertain/reconcile and new-compensation outcomes; history retained. |
| TEST-16 | Resume v1 work after v2 code/policy change. | Definition/history preserved or explicitly migrated; current authority rechecked. |
| TEST-17 | Exercise deadlines, pause/resume and duplicate timer wake-ups. | Correct configured clock behavior; no repeated escalation or invalid transition. |
| TEST-18 | Restore a backup containing active runs and old dispatch intent. | Recovery reconciles later remote effects and avoids resending committed business effects. |
| TEST-19 | Perform queue-to-decision-to-exception-to-verification journey by keyboard and narrow screen. | Context, focus, state labels and version-safe actions work; capture screenshots or recording and assertions. |
| TEST-20 | Reconcile manifest to implementation and acceptance results. | Every actual 108 release ID accounted for, BaaS14 deferred; no invented IDs or aggregate green from one line. |

### Concrete console review packet

Demonstrate Needs my attention, unassigned, blocked, awaiting receipt and awaiting verification views. Show one case with readable agent activity, evidence, the exact decision packet, previous attempts and next permitted action. Exercise empty, loading, stale, denied, missing-evidence, concurrent-claim and expired-decision states. Keep status in text as well as color. Test direct requests independently of button visibility.

Capture route or stable URL, role/capabilities, fixture IDs, viewport, action, expected and actual result, screenshot/recording path and related backend test. Do not mandate guessed route names; map the intended views to inspected PSL routes. Live updates must not move the target row under an operator’s pointer. A recorded approval, dispatch request, provider acknowledgement and verified business outcome must remain visibly distinct.

### Completion report for each bounded slice

Report what changed and what was kept; actual files, symbols and migrations; requirement and process IDs covered; exact tests and results; UI evidence; dependency decisions; remaining partial or blocked work; risks and required approvals. Include an as-of time and the revision or bounded manifest. Never say the entire factory is complete from a subset. Stop only the dependent work when authority, business policy or access is missing, and name the exact action, target, reason and status needed to proceed.

## Decisions needed and safe extension

This specification defines safe default boundaries, not PSL policy values or appointments. Resolve the following configuration decisions with the actual accountable people before enabling affected live work. Unresolved configuration must appear as a blocker, not a developer-invented business rule.

| Decision | Required recorded result |
| --- | --- |
| Case anchor and process mapping | Actual native record, manifest IDs, branches and evidence links for each release process. |
| Autonomy and risk | Allowed command classes, reversible limits, mandatory gates and emergency stop scope. |
| Ownership and approval | Process and policy owners, role membership source, delegation rules, SoD, thresholds and fallback resolver. |
| Decision validity | Material-change rules, expiry, quorum or veto behavior and current-authorization checks. |
| Verification | Authoritative postconditions, accepted receipt sources, human exception route and correction rules. |
| Data and model use | Provider approval, permitted data classes/regions, retention, context freshness and budgets. |
| Service operation | Worker lifecycle, business calendars, SLAs, alert owners, restore procedure and support permissions. |
| Integration readiness | Connector identity, signatures, idempotency retention, reconciliation guarantees and mock/live boundary. |

### New use cases without uncontrolled behavior

No document can predict every future case. Add a use case by identifying the actual process or proposing a governed new one, defining input and outcome contracts, allowed activities and actions, policy and owner mapping, evidence requirements, state transitions, failure routes and tests. Simulate normal and adversarial cases before enabling it. Review whether existing activities suffice; create a new activity only when its contract differs meaningfully, not because another department needs a differently named agent.

An unknown or contradictory case records the relevant facts and a typed exception. It may continue independent low-risk work only when the existing process and policy permit it; the blocked consequential action stays blocked. Route configuration exceptions to a separately configured governance queue with an accountable operational resolver. If that resolver is absent or ineligible, stop the dependent action and expose an owner_needed configuration blocker to authorized administration. Do not require the same missing policy owner to solve the missing-owner problem.

A case-specific human decision is valid only within an already authorized exception mechanism. It does not silently create a reusable policy or grant a new role. Promote a recurring resolution through the normal policy review, versioning, simulation and activation process. Keep the original exception and decisions in the audit history.
