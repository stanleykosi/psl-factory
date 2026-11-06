# Factory controls, agent work and human responsibility

These are application requirements grounded in PSL workflows, not personalized instructions for a coding assistant.

## Human and deterministic ownership
PMO owns milestone completion; Finance owns invoicing and receipt records. Preserve PM → Head of PMO → CEO costing order and the distinct PMO Lead document-quality review. Engineering, Security, Product, QA, client and GLPI decisions remain their source-defined responsibilities. Role-to-person/delegation configuration is separate from role descriptions. A system administrator is not automatically a business approver.

Implement decision inboxes, exact subject/version/hash binding, reject/return/withdraw where configured, delegation, expiry/revocation and audit. A cost revision cannot reuse prior cost approval. Missing non-cost invalidation rules hold only affected decision reuse. Do not introduce new approvals where source processes explicitly have none. Payment-exception decisions require a configured human role; their release use separately validates release controls and does not alter debt.

Record/action/project/department/tenant/audience checks apply to UI, API, worker, export and tool paths. Ordinary login/admin flags are not sufficient. Implement policy configuration and test fixtures; distinguish test actors from operational identities.

## Agent roles
- O01: coordinate permitted factory work across stations: persist dependencies, assign scoped specialist tasks, interpret validated results, resume human waits and reconcile uncertain effects before safe retries. Reuse domain services and source ownership; orchestration cannot create business authority.
- A01: intake/identity triage without silently merging ambiguous customers/cases.
- A02: cited extraction, evidence reconciliation and controlled draft preparation.
- A03: discrepancy/exception investigation and receipt reconciliation.
- A04: planning, task coordination and configured internal handoffs.
- A05: explain deterministic Finance results and investigate mappings/units/periods, not invent formulas.
- A06: grounded management insight and audience-specific drafting.
- A07: release/control evidence preflight, not release approval.
- A08: independently specified quality/evidence checks, not business authority.

The full per-process role and operation assignments live in contracts/process-map.json and the frozen capability catalogue. Reuse capabilities across production stations rather than one bot per process. Agents are operational workers with scoped inputs, expected outputs and persisted attempts. They advance permitted work without a human prompt at every step, escalating only source-required decisions and exceptions; configuration and domain services still control each action. Surface their task, cited result, next handoff, wait/failure reason and safe recovery. Chat transcripts and generated text are not completion evidence. Build real provider adapters/evaluations alongside deterministic fake providers used for tests.

## Typed tool gateway
Use C01–C10 capability contracts, X01–X08 execution mechanisms and versioned task/command/result envelopes. Each invocation carries tenant/case/process/task IDs, authenticated principal/grant, purpose, input hashes/versions, allowed reads/actions, output schema, policy/workflow/tool/model versions, expected state and operation key. Results separate facts, uncertainty, proposed transitions and completed effects with cited evidence and concise audit rationale.

Examples: evidence read/search; restricted draft creation; case allowlisted patch; validated task dispatch; deterministic rule calculation; internal handoff; stable-key effect lookup (C08 A03/A04, coordinated by O01); grounded summary and independent review. Catalogue membership alone is not an application grant. Human decision operations cannot be forged by a model actor string.

## Trust and reliability
Retrieved documents/tool text/model output are data, not permission or policy. Validate schema and semantic identity/scope/currency/period/state server-side. Keep model tools narrow; no arbitrary shell, raw SQL, credentials or unrestricted network. Filter retrieval before search and again at return; propagate source labels into drafts/exports and avoid cross-project cache leakage.

Persist task state, bound work by configurable technical budgets, detect no progress, and surface actionable exceptions. A provider outage must leave safe manual workflows usable. Reconcile outcome-unknown operations before retrying. Financial calculations, rule selection, approvals and external effects remain deterministic even when agents do meaningful work around them.

Test adversarial documents, false approval text, cross-tenant identifiers, stale grants, malformed output and over-budget task graphs. Store sufficient audit evidence, not hidden chain-of-thought or indiscriminate sensitive payloads. Treat privacy, retention and allowed provider data as explicit operational configuration.
