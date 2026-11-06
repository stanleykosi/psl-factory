# AI agent operations factory architecture

Retain the documented modular Django/PostgreSQL core, server-rendered staff UI and durable PostgreSQL jobs/outbox. Use Django 5.2 LTS as the documented family and select reviewed compatible patch/interpreter/database/driver versions during implementation. Record the lockfile and environment; this pack does not claim an installed/latest patch.

One maintainable factory application, explicit production stations implemented by domain modules, one operational database, separate web/worker processes as needed. The primary server-rendered console shows intake, production queues, agent execution, human decisions, exceptions, handoffs and outputs. Domain pages provide supporting context. Reuse native state and current grants for projections; do not create a second workflow engine or a generic status that overrides business state. Use framework auth/session/CSRF/forms/migrations and transactional services. No speculative microservices or custom orchestration platform. PostgreSQL is the integration-test target; SQLite cannot prove its concurrency behavior.

## Repository map
- config/: environment profiles, application/worker startup and dependency configuration.
- apps/core/: cases, evidence versions, source provenance, audit and shared errors.
- apps/identity/: authenticated actors and record/action/project/department/tenant policies.
- apps/workflows/: versioned state machines, tasks, human waits, timers, leases/fencing, outbox and effect reconciliation.
- apps/pmo/: engagements, plans, costing/SOW, project lifecycle, RFPs, issues/changes and external gate evidence.
- apps/finance/: imports/mappings, management accounts, BU allocation, billing/receipts, forecast and controlled reporting.
- apps/baas/: support, reconciliation evidence, partner/customer operations and usage.
- apps/documents/: templates, immutable artifacts, reviews, audience projections and publication records.
- apps/policy/: typed business configuration, version/effective dates, validation, impact preview and missing-policy UX.
- apps/agents/: O01 orchestration, A01–A08 capabilities, typed gateway, model adapters and evaluations.
- adapters/: evidence repositories, accounting, PMO, GLPI, billing flows, communications, HR inputs and model providers, each with contract-faithful mock and real implementation interfaces.
- templates/, static/, tests/, docs/adr/, docs/runbooks/, fixtures/ plus durable BUILD-* files.

## Cross-cutting design
State transitions and their audit/outbox records commit atomically. Workers lease/fence jobs, revalidate current grants/versions at dispatch, and reconcile uncertain effects by stable operation keys before retrying. Preserve separate task, workflow, business-record and effect states. Resume agent tasks and human waits from persisted records, not conversation memory. Correlate case/process/family, intake, intended output, station, task/attempt, responsible actor, dependencies and receipt references. Agent/job completion proves only its operation; required review, business acceptance and downstream receipts remain distinct.

Django sign-in alone is not object authorization. Check every screen, POST, export, task and tool against its actual record/action scope. Tenant context remains explicit for future reuse without building speculative SaaS provisioning. The agent gateway exposes typed domain actions, not arbitrary shell/SQL/network or credentials.

Business configurations select validated rule implementations and explicit parameters; they are not unrestricted executable code. Missing configuration returns a typed dependency result. The same domain code supports isolated synthetic policy fixtures and later real configuration without hard-coded fixture defaults.

Existing systems retain authority for accounting, risk, incident and deployment decisions. PSL supplies the required document/evidence tooling and coordinates handoffs. Inspect existing tool capabilities before duplicating functionality. Integrations use external IDs, versions, idempotency and ownership maps.

## Environment and operations
Use the implementation team's chosen development environment; native Windows guidance is available but not mandatory. Separate development/test/staging/production configuration, secrets and data. Provide migrations, backup/restore, observability, diagnostics, export and operator recovery runbooks. Hosting/SSO/providers are deploy-time configuration, not facts inferred from a historical budget. Azure/Entra/M365 are conditional source defaults rather than mandatory licenses.
