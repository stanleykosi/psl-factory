# Shared data and integration contracts

## Shared records
Principal/Grant; Engagement/Project; Case/Task; EvidenceVersion; DocumentTemplate/DocumentVersion/Review; WorkflowDefinition/WorkflowInstance; HumanDecision; PolicyConfigurationVersion; Outbox/EffectReceipt/Audit. Stable aggregate IDs link append-only revisions. The proposed factory projection correlates existing case/process/family, intake, intended output, station, agent task/attempt, human decision, dependency, effect and receipt. This is a design requirement, not a claim of new implemented tables or permission to replace domain state. Preserve distinctions between waiting on people, missing policy, execution failure and unknown effects; no global queue status implies financial or release completion. Store provenance, content hashes, ownership/access labels, effective policy and causal references.

## Domain records
- PMO: requirements, stakeholder/effort evidence, plan, costing/SOW version, phase gates, milestone, RFP, issue/change and closure references.
- Finance: import batch/source/account map/rule lineage, management-account report, BU allocation/performance, service/contract schedule, invoice, receipt/cash lot, allocation/adjustment, balance snapshot and forecast version.
- BaaS: support case/channel/transaction references, reconciliation evidence and corrective request, partner agreement, onboarding stage/history, usage batch and billing handoff.
- Shared documents/reporting: controlled template, draft/review/published version, audience projection, report/minute and delivery receipt.

Keep schedule, stage, milestone, invoice, cash receipt and allocation facts independent. Three payment stages do not imply three receipts. Use exact decimal values with explicit currency/unit/tax/period basis. Missing values are not zero. Policy selects validated mappings/formula implementations and rounding/qualification parameters. No LLM-generated finance formula becomes authoritative.

## Persistence behavior
Authenticate/authorize, validate current policy/evidence/dependency versions, apply transition and append audit/outbox atomically. Use database uniqueness for semantic operation identity, not just request keys. Version conflicts return explicit stale/conflict outcomes. Multi-record capacity checks share one transaction. Worker leases/fencing prevent expired owners from committing.

Dispatch outside the database transaction with a durable reserved intent and stable key. Recheck current state/grants/cancellation. Record accepted, confirmed, rejected and unknown separately. Timeout after possible acceptance is unknown until lookup/reconciliation; no blind duplicate retry. Cancellation stops undispatched work, not accepted external effects. Corrections preserve prior history and source-defined compensation semantics.

## Billing detail
Implement the exact v0.5 command/record schemas with v0.6 exception semantics. Stage amounts/triggers/due terms are contract configuration. Receipt assignment and invoice allocation are separate; prevent duplicate cash across contracts, over-allocation and duplicate reversals. Snapshot inputs are complete service-generated manifests, not caller subsets. Preserve obligation identity across corrections and separate document delivery from issuance. Partial refunds, allocation priority and qualifying funds require their own configured treatment.

## Adapter interface
Every adapter specifies owning system, supported operations, input/output schema, external IDs/versions, data projection, credentials/identity source, idempotency guarantee, pagination/callback correlation, timeouts/rate limits and unknown-outcome lookup/recovery. Provide deterministic mocks with fault controls and contract tests; then implement verified real targets. Mock internal application state only in unit tests, not end-to-end proofs.

Adapters: incumbent PMO/project identifiers; accounting/QuickBooks read and specified writes; existing invoice/Power Automate flow; GLPI decision/status; document/evidence storage; communications; HR inputs with Finance-read boundary; support/reconciliation sources; model providers. Inspect actual APIs/configuration rather than assume product/version behavior. Acknowledgment does not prove financial posting or release.

## Migration and operations
Version migrations and reference imports; protect append-only audit/decisions. Provide export, backup/restore and migration rehearsal tools, constraints and documented correction paths. Maintain environment isolation and ownership maps. Configuration changes invalidate affected evaluations/decisions using explicit policy, not silent history rewrites.
