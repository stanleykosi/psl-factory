# AI agent operations factory topology

Status: proposed implementation topology, grounded in the retained modular architecture and process contracts. One application/codebase with logical boundaries, not a claim that each box is a separate service.

## Nodes (left-to-right visual layers)
1. People: PMO/commercial; Finance; BaaS/Support; management; referenced Engineering/Security/Product/QA/client decision owners.
2. Factory operating console: intake, production queues, work in progress, agent execution, human decisions, exceptions, handoffs and verified outputs. Domain records, evidence, configuration and diagnostics are supporting detail.
3. Domain modules: PMO delivery/commercial/issues/RFP; Finance reports/BU/billing/forecast; BaaS support/reconciliation/partners; documents/reporting; shared handoffs/evidence validation.
4. Shared deterministic core: identity/action policy gateway; versioned business-policy configuration; domain rule/calculation services; workflow/state/decision runtime; evidence/document versioning; effect/idempotency/reconciliation gateway.
5. Agent layer: O01 orchestrator plus A01 intake, A02 evidence, A03 investigation, A04 coordination, A05 Finance analysis, A06 insight/drafting, A07 controls preflight, A08 evaluation; provider adapter underneath. All tools pass through the gateway/core.
6. Persistence/runtime: PostgreSQL records and policy versions, append-only decision/audit/evidence metadata, tasks/jobs/leases, transactional outbox and effect receipts; controlled artifact storage; workers/timers.
7. External adapters/systems: PMO, accounting/QuickBooks, billing/Power Automate, GLPI/Engineering/Security references, document/signature repositories, support/reconciliation/usage, HR inputs, communications and model providers. Use mock or real adapter behind the same contract.
8. Operations/evaluation: observability, audit/lineage, configuration health, independent tests/evals, migration/export/backup/restore.

## Directed edges
People → factory console → domain services → deterministic core → PostgreSQL transaction + outbox.
Workers ← persisted jobs/outbox → effect gateway → adapter → owning external system → callback/lookup → receipt/reconciliation → workflow/UI.
Domain/workflow → scoped agent task → O01/specialist → typed gateway → permitted evidence/domain tools → cited result → deterministic validation → workflow/UI or human decision.
Human decision inbox → authenticated version-bound decision → workflow guard; an agent cannot substitute for this edge.
Policy configuration → schema/semantic/source-authority validation → active immutable policy version → dependent transition/calculation. Missing slot → narrow waiting/configuration indicator, not disabled application.
All boundaries → redacted audit/observability; tests/evals inspect results and controls rather than granting business authority.

## Important visual annotations
- Agents interpret evidence, investigate, draft, coordinate and carry out permitted operations through typed domain tools. Deterministic services enforce each action; humans decide reserved matters. Agent completion, business completion and effect verification remain separate.
- One authoritative owner per business state; PSL connects systems rather than replacing accounting/release authority.
- Planning/costing → signed SOW → milestone/Finance handoff; billing stages and irregular cash remain separate.
- Business policy is replaceable typed configuration, not hard-coded unknowns.
- Payment exception approval is human-only/configured; release controls remain independent; no debt waiver.
- Mock adapters support development, real adapters/provider evaluation complete operational readiness.

Suggested visual: show intake, production work, decisions, exceptions and verified outputs across the top, with people and the factory console operating that flow. Show supporting domain capabilities centrally; the shared core and agent layer connected through the gateway; persistence/workers below; external systems at right; and audit/evaluation across all boundaries. Label logical versus external boundaries clearly.
