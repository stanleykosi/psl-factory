# PSL agent and workflow architecture

Version 0.3 architecture proposal · 19 October 2026

## The recommendation in plain language

Build around **shared business cases, governed workflows and capable specialist agents**. Give agents meaningful work: understand messy inputs, connect evidence, investigate exceptions, coordinate permitted next steps and complete bounded internal tasks. Do not give a language model ownership of permissions, money, approval authority or the definition of the system itself.

A durable workflow runtime is the execution authority. An orchestration agent reasons about what to do next, then requests typed task operations. The runtime checks whether that operation is allowed for this case, actor, evidence version and current state before it executes anything. Specialist agents perform reusable capabilities inside these task boundaries. Humans contribute expertise, supply missing policy and make the decisions reserved to their roles. Routine, low-risk operations do not need a fresh human click when a business owner has explicitly authorized the relevant workflow action.

This is not a generic chatbot with tools attached, and it is not 122 separate bots. It is one coherent work system with shared records, reusable capabilities, explicit authority and traceable business outcomes. Agents can compose permitted capabilities into a plan; they cannot invent capabilities, alter the workflow graph or rewrite policy.

### What this revision changes

The user's latest direction makes agents and workflows central to the architecture from the start. This supersedes the earlier design assumption that AI must sit outside the initial system. It does **not** turn proposed automation into approved business policy or authorize a build. The 15 October register, source facts, original IDs and existing scope/timeline documents remain unchanged historical evidence. This pass makes no scope, deadline or build decision. A separate presentation budget uses explicit adjustable usage assumptions and verified public API rates; it is not a purchase commitment.

The source-reconciled v0.2 definitions remain the business-process foundation. The process assignment catalogue in this folder is the architecture overlay. Where an older proposed-design paragraph excludes AI from the initial system, use this overlay for the revised architecture; do not alter the original source statement or infer that all other historical scope decisions changed.

## 1. The system's three responsibilities

### Understand and decide what to propose

Models interpret documents and messages, connect related evidence, identify uncertainties, propose permitted task plans, draft communications and explain exceptions. They can judge which authorized read/search or diagnostic task is useful next. Their output carries evidence, uncertainty and the exact task purpose. A model's confidence is not approval, proof or a calibrated probability unless separately validated.

### Enforce and execute

Deterministic services own identity, authorization, schemas, semantic validation, workflow state transitions, exact arithmetic, version checks, persistence, effect records and delivery. They can execute an explicitly permitted low-risk action without human review when all required checks pass. These services do not decide business questions that the sources leave unresolved.

### Authorize and resolve accountable questions

Verified human roles supply policy and make reserved decisions, such as costing approval, client signature acceptance, accounting interpretation or release authorization. Some approvals belong to external systems and teams. Their evidence is referenced, not replaced by an agent's verdict. A person may also intervene when a model cannot reconcile evidence or a tool result is uncertain.

The architecture separates these responsibilities even when they appear in one user experience.

## 2. Logical components

1. **Human workbench and task inbox.** People see a case, current state, evidence, pending decisions and a plain-language explanation of why action is needed. They can correct a proposed interpretation, return work, approve within their role or stop a case. Approval is a structured action against a specific subject/version, not an ambiguous chat message.
2. **Ingress and evidence gateway.** Authorized source connectors produce immutable source references and content versions. Documents, messages, transcripts and images are untrusted data. The gateway records provenance, redactions, access labels, extraction method and uncertainty.
3. **Case and record service.** Shared client/engagement/project, milestone, issue, usage, report and evidence references connect the original processes. It preserves owning systems. A shared view is not a replacement ledger, payroll master, risk register or deployment-approval system.
4. **Workflow runtime.** A versioned state machine stores case and task progress durably. It exposes only transitions and task types allowed by the pinned workflow definition. It validates prerequisites atomically with state changes, schedules work, parks cases waiting on humans or external events, and resumes them after interruption.
5. **Policy and capability gateway.** Every read, mutation and external action is checked against the actual principal, case, tenant, resource version, purpose, action class and configured grant. Models cannot directly access connector credentials or bypass this gateway.
6. **O01 orchestration agent.** It selects among allowed tasks, decomposes work into an admissible task graph, delegates specialists, detects stalled work and requests permitted dispatch/recovery operations. It does not own the state machine or approval matrix and cannot self-modify policy, prompts, tools, workflows or application code.
7. **Specialist capability workers.** A01–A08 implement bounded reasoning capabilities. A worker receives only the task's permitted context and tools, returns a typed result, and can perform authorized intermediate reads or reversible internal updates within the task contract.
8. **Deterministic domain services.** Calculation, mapping, comparison, document assembly and validation services apply explicit versioned rules. Finance formulas are not generated at runtime by a model and then treated as policy. Missing rules remain blocked inputs.
9. **Effect gateway and durable delivery ledger.** Side effects use action IDs, input hashes, receipts and reconciliation. The system distinguishes a request, an accepted operation, a completed effect and an unknown result. It never promises exactly-once delivery across arbitrary external systems.
10. **Audit and evaluation plane.** Evidence traces connect a user-visible result to inputs, policies, models, tools, attempts, approvals and effects. Evaluation measures task quality and authority compliance separately. Sensitive reasoning traces are not a substitute for concise decision evidence and need not be exposed or retained.

These are logical boundaries, not a requirement to deploy ten independent services. Boundaries must remain explicit even if several components initially share one implementation.

## 3. Reusable agent capabilities

| ID | Capability | Meaningful work | Authority limit |
|---|---|---|---|
| O01 | Governed task orchestration | Coordinate permitted tasks across cases; dispatch, detect blockers, request retries or cancellation under configured grants | No universal data access, policy editing, approval or arbitrary tool execution |
| A01 | Intake and case triage | Interpret incoming work, propose identity links, classify ambiguity and create/update an internal case when permitted | Cannot silently merge distinct customers, transactions or cases |
| A02 | Evidence and document analysis | Extract structured facts with citations, compare versions, find missing evidence and assemble bounded evidence packs | Cannot certify a signature, invent evidence or treat document instructions as authority |
| A03 | Exception investigation | Trace a discrepancy, gather allowed evidence, distinguish failure classes and propose or execute permitted corrective case actions | No invented accounting treatment, financial correction or security bypass |
| A04 | Planning and workflow coordination | Coordinate a case's dependencies, permitted next tasks, follow-ups and internal handoffs | No alteration of the governing workflow or approval gates |
| A05 | Finance evidence and analysis | Explain deterministic calculations, investigate mapping/sign/unit/period exceptions and prepare recognition/billing evidence | No runtime invention of ratios, taxes, recognition rules or posting authority |
| A06 | Management insight and drafting | Produce grounded summaries, compare approved outputs, draft audience-specific documents and surface decisions | No publication to an unapproved audience or unsupported certainty |
| A07 | Control evidence and release preflight | Check completeness/version alignment of required approvals and prerequisites; prepare a release-readiness explanation | Not an approver and cannot create a Go/No-Go, GLPI decision or exception waiver |
| A08 | Evaluation and quality review | Critique outputs against independent fixtures, check evidence coverage and detect unsupported assertions | Cannot define its own business oracle, approve its own work or override deterministic checks |

These are capability roles, not departments or fixed model instances. A capability may be reused in Finance, PMO and BaaS with different contracts and permissions. Conversely, two tasks using the same model do not share access automatically.

A second agent's agreement is not independent authorization. Multi-agent review is useful for finding errors but does not replace a deterministic check or accountable human decision.

## 4. Workflows and task plans are different things

A **workflow definition** is owner-reviewed, versioned configuration: allowed states, task types, transitions, approval prerequisites, data contracts and recovery rules. A **task plan** is a case-specific selection and ordering of permitted tasks. The model may propose a task plan inside the workflow's constraints. It cannot add a new transition, tool, approver or business rule.

A plan validator checks every node and edge before dispatch. It checks task types, required input types, allowed outputs, authority, effect class, dependency cycles, maximum fan-out and completion criteria. An allowed plan can branch or run independent read tasks in parallel. A task can request a new allowed evidence-gathering step when an exception is discovered. This is controlled adaptation, not a fixed script and not self-rewriting software.

A plan change is itself versioned. If it changes evidence relied on by an approval, the runtime applies the configured invalidation rule. The model cannot declare that an old approval still applies. If a workflow lacks a rule for the situation, the case waits for a human decision or follows an explicitly approved manual fallback.

### Separate state machines

- **Business record state:** for example a milestone's reported completion or an invoice's actual state in its owning system.
- **Workflow state:** the case is collecting evidence, awaiting a decision, ready for an allowed transition, completed or stopped.
- **Task state:** proposed, validated, queued, leased, running, waiting, completed, failed, outcome-unknown or cancelled.
- **Effect state:** prepared, authorized, submitted, receipt-known, confirmed, rejected or unknown.

A task completing does not mean a milestone is accepted. A notification delivered does not mean Finance recognized revenue. A preflight check passing does not mean production release was authorized.

## 5. Typed capability contracts

The companion `capability-contracts.json` defines the proposed common envelope and representative task contracts. It is a design specification, not installed executable policy.

Every invocation needs:

- Tenant, case and task identifiers, stable original process IDs and correlation IDs.
- Purpose and capability ID, pinned workflow/policy/tool/model/prompt versions.
- The authenticated principal and a short-lived capability grant reference, not an agent-written role claim.
- Typed input references with content hashes, source versions, access labels and provenance.
- Allowed read resources, allowed action types and output schema.
- Required evidence, preconditions, approval references and expected state version.
- A stable operation/idempotency key where an effect is possible.
- Completion conditions, failure classes, escalation and recovery policy.

Every result needs:

- Outcome status and typed outputs, with citations tied to the exact source version.
- Explicit unknowns and conflicting evidence; no silent conversion of missing data to zero or a guessed status.
- Proposed state/effect requests separate from factual extraction.
- Validation findings, dependency/approval references and audit correlation.
- A reason suitable for a human to inspect, without relying on hidden model reasoning.

JSON shape validation is only the first check. The gateway must also validate semantic identity, units, periods, allowed state transition, data ownership, record freshness, approval scope and recipient permissions. Valid JSON can still contain a malicious or unauthorized action.

## 6. Permission model without constant human clicking

Define grants by **action**, not by the agent's name. For example, a configured grant may allow a specialist to attach evidence to an existing internal case, update a proposed classification, create a non-final draft, or queue an internal clarification task. Such a grant can permit autonomous execution when identity, access, state and validation checks all pass.

The architecture does not assert that PSL has already approved these grants. The process assignment catalogue distinguishes candidate operations from actual business permission. Until a grant is configured by the authorized owner, the gateway denies execution or leaves a reviewable proposal.

Three proposed action classes help owners make that decision:

- **Read and analyze:** permissioned retrieval, extraction, comparison and deterministic calculation. No business mutation. Still enforce data access and purpose limits.
- **Bounded internal work:** reversible case annotations, draft artifacts, internal task creation and routine coordination explicitly allowed by policy. Record before/after state, provenance and undo/reversal semantics. A reversible label does not excuse leaking confidential data.
- **Consequential action:** financial postings or corrections, customer commitments, external distribution, actual approvals, security changes and production release. Require the prescribed authority and any action-specific controls. An agent can prepare and validate the request but cannot manufacture authority.

The same tool can contain operations in different classes. `document.prepare` is not `document.publish`; invoice generation is not invoice posting or sending. Grant checks must apply to the exact operation and payload.

Human approvals use an authenticated actor and bind the exact subject, content hash/version, policy version, decision type, allowed action and expiry or invalidation condition. The runtime prevents replay against revised content. Where the SOP specifies joint approvals without an order, do not invent a serial order. Preserve the actual serial costing chain where prescribed.

## 7. Durable execution and recovery

Persist a task before dispatch. Use a transactional state update and outbox where supported, then let workers acquire a lease. Persist the validated output and effect intent before external submission. Record attempt IDs separately from stable operation IDs.

Before a mutation, re-check the resource version, policy grant and approval freshness. A model may have reasoned on an older snapshot; the tool cannot rely on that earlier check. Competing case updates use optimistic concurrency or an equivalent transactional guard. A conflict returns a typed stale-state outcome and triggers permitted re-evaluation, not a blind overwrite.

On timeout after possible acceptance, mark **outcome-unknown**. Query the destination by stable operation key or reconcile its receipt before retrying. If the destination lacks idempotency or a trustworthy lookup, escalate rather than pretending the retry is safe. Exactly-once business outcomes require specific downstream guarantees; the architecture instead makes duplicates detectable and recovery explicit.

A restart resumes persisted state, not an untrusted model conversation. Replay recorded decisions and tool results where appropriate. Do not re-run a nondeterministic model step or consequential tool action merely because execution history is being reconstructed. A changed model or policy version starts a deliberately migrated/new task version, not a silent replay mutation.

Cancellation stops new work and revokes unused grants, but cannot undo an effect already committed elsewhere. Recovery uses defined compensation or a human-owned correction path. For example, an internal draft can be withdrawn; an accounting effect may require an approved correction rather than deletion. Every workflow must state which recovery behavior is actually available.

Bound execution by maximum task depth, fan-out, attempts, elapsed time and repeated-no-progress detection. These are reliability controls, not a cost estimate. When the bound is reached, preserve evidence and park the task with a useful next question.

## 8. Evidence and memory

Evidence is immutable by version. A later extraction or correction creates a new artifact linked to the original, not a replacement that erases provenance. Distinguish source statements, observed data, model interpretation, deterministic result, human decision and proposed action in storage as well as prose.

Case memory is a permissioned derived view over those records. It may retain a concise status summary with links, but it is not the authoritative record. Rebuild it when a source changes or access is revoked. Do not let long conversation history become an invisible repository of stale permissions or business rules.

Retrieval applies tenant, subject and access filters before search and verifies access again before returning content. Caches include tenant, principal/purpose, resource version and policy version. A shared vector index must not become a cross-tenant or cross-role side channel. Derived summaries and exports inherit appropriate source restrictions until explicitly cleared for a narrower audience.

Sensitive values and credentials should be minimized in model context. Tools use secured credentials outside prompts. Audit records preserve enough identifiers/hashes and approved redacted evidence to explain decisions without indiscriminately copying payroll, private balances or secrets. Retention and deletion rules are owner-defined; this proposal does not invent them.

## 9. Prompt-injection and trust boundaries

Treat every retrieved document, transcript, message, attachment and tool-returned text as untrusted content. A source may say “ignore the policy,” contain a fake approval or ask the model to send data elsewhere. None of that creates authority.

The system's policy comes from signed/versioned owner-controlled configuration, not from ordinary retrieved material. Extraction tools label source content separately from instructions. The model cannot promote an embedded instruction into a tool permission, new recipient, rule or credential request.

Keep tools narrow and purpose-specific. Validate identifiers against actual allowed records; validate destinations against approved recipient references rather than arbitrary URLs or email strings. Retrieval and connector tools must reject paths, queries or payloads that exceed the grant. Do not allow arbitrary shell, unrestricted SQL or unconstrained network requests through a business-task capability.

Use allowlisted data fields for cross-boundary outputs. Test malicious content in apparently normal invoices, SOWs, case messages and spreadsheet comments. A safe-looking model response is not the security boundary; server-side authorization, semantic validation and effect controls must prevent the action even if the model is deceived.

## 10. PSL end-to-end examples

### A. P12/P20/P34/P39 to F33/F34: project evidence reaches Finance

A02 extracts the signed baseline and milestone references, identifying missing or conflicting evidence. A04 links the evidence to the engagement and project without waiting for a formal project ID that is only assigned in Planning. The workflow validates the required source and permission checks. With an explicitly configured internal handoff grant, it emits one versioned handoff event and records delivery/receipt. O01 coordinates a missing-evidence task or receipt reconciliation without treating an uncertain send as failure.

A05 prepares the Finance evidence view and distinguishes baseline, progress, milestone completion, actual payments and accounting treatment. It can investigate missing references and summarize the relevant contract terms. It cannot infer a universal revenue-recognition percentage or issue an invoice simply because completion was reported. Finance retains the recognition and billing decision under actual policy. Closure checks notification evidence, not an invented paid-invoice gate.

### B. B01–B07: a complaint may need a corrective transaction

A01 connects authorized channel messages to a proposed case identity, flags ambiguous customer/transaction matches and performs permitted internal triage. A03 gathers settlement evidence through read-only scoped tools and determines what is missing. A04 can create and route a permitted internal specialist task, track the response and request clarification.

Settlement success and customer credit are separate facts. A proposed corrective request goes to the established Engineering route with the required evidence. The agent does not gain fund-movement or queue-write authority because it understood the complaint. It may reconcile an execution receipt when authorized, but cannot declare successful financial correction from a conversational “done.” The missing Support SOP and Recon brief remain explicit dependencies.

### C. F03/F05–F27: investigate a report discrepancy

A deterministic service imports a versioned synthetic or authorized dataset and applies owner-supplied mappings/formulas. A05 and A03 investigate why a company/BU comparison differs: missing account, duplicated input, wrong unit, sign, period or stale link. They can inspect approved evidence and run permitted diagnostic comparisons; they do not silently change a formula to force a tie.

The observed divide-by-1,000 and multiply-by-1,000 examples are source-specific. The selected cost-of-sales link does not establish a revenue mapping. F12 must distinguish splitting an existing total from genuinely adding income. A proposed correction identifies the exact rule/data version and expected impact. Actual accounting adjustments and policy changes need their prescribed authority. A missing allocation table remains missing, not an invitation to estimate ratios.

### D. B12/F28–F30: price-bearing usage becomes billing evidence

A02 validates that client, service, period and usage references are present; A05 investigates missing or conflicting pricing evidence. Deterministic pricing uses an authorized, effective-dated rate source and rule set. A04 can route an internal missing-price task and assemble the candidate billing batch when permitted.

The workflow distinguishes generation, posting and sending as separate operations without assuming that all three require the same approval. The actual incumbent Power Automate design must be inspected before a capability is bound to it. The Word/audio phrase conflict does not create a new signature gate. Neither O01 nor a specialist may invent price, tax, discount or invoice-release policy.

### E. P29–P33/P55–P62: release preflight and exception handling

A07 assembles the required QA, UAT, Engineering and GLPI evidence for the exact build/version. It can detect a mismatch, open a permitted internal follow-up and explain why the case cannot progress. The workflow enforces actual prerequisites and role decisions. A green preflight result is not a deployment approval.

An emergency label does not create a GLPI waiver. The unresolved emergency relationship remains a policy question. O01 can coordinate the correct clarification path but cannot rewrite the release workflow to meet a requested date.

## 11. PSL-first reuse without flattening business differences

The reusable kernel contains cases, task contracts, workflow runtime, evidence envelopes, grants, human decision records, effect ledger and evaluation hooks. A PSL policy pack contains the actual SOP requirements, roles, record mappings, templates, formulas and business-specific workflows. Connector adapters map typed operations to the actual owning systems.

Keep tenant ID and authorization context explicit in every contract even when only PSL is configured. A later establishment receives a separate policy pack, data namespace, credentials, retrieval index boundary and audit partition. Never reuse PSL's approval matrix or private evidence as another establishment's default policy.

Reuse a capability such as evidence extraction or discrepancy investigation, not an assumed business rule. Version the capability independently from a workflow and from a connector adapter. Contract tests determine whether a replacement remains compatible. Breaking changes require explicit migration, not silent reinterpretation of historical cases.

A model/provider swap must not change a business contract. It may change quality, latency, tool-calling reliability or data-handling terms, so it requires evaluation and an approved routing update. The current official-document research in [the model and orchestration memo](research/agent-model-and-orchestration-research.md) supports the model/runtime recommendation; no “most capable” claim is treated as established without PSL-specific evaluation.

## 12. Validation and human control

The evaluation catalogue tests interpretation quality, evidence fidelity, tool/action correctness, authorization, durable recovery and user usefulness separately. A successful model answer is not proof of a safe workflow. Golden cases need independently reviewed expected outcomes; A08 may critique them but cannot supply its own approval oracle.

Humans must be able to pause a case, revoke a grant, correct a proposed fact, reject or return a task, choose the permitted manual path, and inspect why a transition was blocked. Overrides are explicit typed actions with role, reason, evidence and expiry. They do not erase history. An override cannot bypass a restriction for which the actor lacks authority.

The final deliverable is an architecture proposal and process allocation, not application code or operational authorization. No API credential, paid model experiment, external-data test, integration write or deployment is performed by this documentation work.
