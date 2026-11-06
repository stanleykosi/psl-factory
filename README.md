INCOMPLETE SOURCE-ONLY BACKUP: backup/incomplete-sign-conversion

This branch preserves the independently tested statement sign/conversion feature on public backup54178de. It deliberately excludes pending performance source and all newly generated runtime evidence. It is not a runnable integration, deployment candidate or milestone acceptance: migration0065 references predecessor0064_factory_performance and document0022 references0021_factory_performance, which are intentionally absent here. Do not migrate or deploy this branch. The feature passed104 tests on its complete isolated test source; that result does not certify this deliberately partial backup tree. Continue from the coordinated integration branch when its dependencies are accepted.

# PSL Product Studio — AI Agent Operations Factory

PSL Product Studio is being built as **PSL’s AI agent operations factory**. Requests, projects, transactions and service issues enter as traceable work, move through connected production stations, and produce verified business outputs. Agents perform useful operational work, people make accountable decisions, and deterministic services enforce the rules.

The primary experience is the flow of work: intake, work in progress, agent execution, human decisions, exceptions, handoffs and completed outputs. Department screens, record libraries and configuration support that flow. An aggregation of department tools, a chatbot or an agent activity dashboard does not constitute the factory.

Start with [START-HERE](START-HERE.md), [AGENTS.md](AGENTS.md) and the [product blueprint](guide/11-FULL-PRODUCT.md). [START-PROMPT](START-PROMPT.md) carries the same direction into future sessions.

## How the factory works

1. Capture work with its source, scope, intended output and known owner; expose unknowns explicitly.
2. Route it through relevant PMO, Finance, BaaS and shared-document stations using durable workflow state.
3. Give agents scoped tasks for intake, evidence interpretation, investigation, planning, drafting, follow-up and permitted internal execution.
4. Bring people the exact decision or exception requiring their authority, with evidence and a clear next step.
5. Verify outputs and any required acceptance or delivery receipt before marking the relevant operation complete. Keep retries, uncertain outcomes and rework visible.

This is the current product direction confirmed on 30 October 2026. Detailed console/projection design is engineering interpretation; original source definitions govern business ownership, financial rules and required decisions.

## Production capabilities and controls

The connected invoice flow carries useful agent preparation through responsibility checks, a separate human Finance decision and verified mock issuance/delivery receipts. Recorded Finance rule and role authority is checked through claim, decision and visible controls; stale tasks replan through the native ledger, and the form offers only configured verdicts. Uncertain original sends are reconciled before changed-source rework; receipt-only lookup cannot send. Changed terms on an issued invoice require Finance correction. New sends enforce current authority and configured source freshness. Missing owners hold the dependent action; nomination and governance recheck grant no approval. The [responsibility and recovery runbook](docs/runbooks/factory-finance-responsibility.md) and [build state](BUILD-STATE.md) separate these tested bounded paths from remaining routing and product gaps. Actual owner values remain unconfigured in the main database; whole-process acceptance remains incomplete.

The first release covers 63 PMO and45 Finance process IDs (108 total). PMO handles commercial planning and delivery; Finance handles financial preparation, invoices, receipts, allocations and reporting. The14 BaaS process IDs remain preserved but deferred from this release; their existing behavior is retained. Shared evidence, documents, handoffs and human decisions connect the operation. All122 IDs across13 families remain the architectural traceability baseline. A Finance process consuming BaaS inputs remains Finance release work.

Retain modular Django/PostgreSQL, a server-rendered staff UI, durable workflows/jobs/outbox and integration adapters. Reuse existing domain services and agent capabilities. Agents work through typed tools; deterministic services enforce permissions, calculations, state, policy and effects. Existing systems of record and Engineering/Security/HR/client authorities retain their responsibilities.

Planning/costing precede signed SOW. PMO completes milestones; Finance handles invoices/receipts. Stages, invoices, receipts and allocations remain separate. Unknown values are not zero. Human payment exceptions do not waive debt or replace independent release controls. Missing owner policy holds only the dependent action; independent work can continue.

## Build status

The application implements tested portions of these operations. Nine connected factory paths cover invoice preparation/review/receipt recovery, planning through department-owned observations into a delivery handoff, declared costing through reviewed commercial submission, delivery gates through release readiness, go-live report production through human sign-off, configured hypercare assessment, archive inventory, Support handover and controlled project closure. They share native records, lifetime execution allowances and the work-first console. Planning handoff establishes a source-referenced artifact; commercial verification checks declared costing and exact internal recipient receipts. Delivery readiness binds the native Planning decision, actual kickoff and current upstream/GLPI references, with source corrections requiring fresh review. Actual-event recording does not manufacture prior readiness. Agents investigate go-live inputs, prepare the exact client report, request native review and deliver the reviewed projection through a configured publisher. A human PM attests actual distinct PM/Client signature evidence; the agent verifies the native acceptance. Corrected accepted evidence requires a fresh exact package and explicitly configured human reaffirmation, retaining the unique original go-live event. Hypercare qualifies only current source observations against reviewed periods, confirmations, metrics and units; unknown or negative results remain held. Closure consumes an actual retrospective and Finance notification confirmation, prepares the controlled PM report, waits for prescribed reviews and the exact Head of PMO decision, then records and verifies closure through a currently authorised PM. Rework and interrupted execution preserve prior reports, decisions, receipts and the original allowance. Closure, deployment and financial release retain their separate controls.

Stale artifacts remain in history and leave the current Verified queue. Live source authenticity, native workbook verification, signed-contract acceptance and full process readiness require separate evidence. The complete108-process release is **not accepted**; all122 architectural process rows remain partial. [BUILD-STATE](BUILD-STATE.md), [HANDOFF](HANDOFF.md), [BUILD-BACKLOG](BUILD-BACKLOG.json) and [BUILD-TESTS](BUILD-TESTS.md) record actual behavior and evidence. Plans, mock acceptance and documentation checks are distinct from connected acceptance, model evaluation, UAT and production authorisation.

The console keeps cancelled agent work separate from retained human reviews and issued-invoice follow-up. Stopped preparation preserves its history and original execution allowance; document withdrawal and Finance correction use their existing human authority. Engineering gaps, deferred owner decisions and operational readiness are tracked separately. The factory direction supplies no new policy values, approvers, service targets or autonomous financial authority.

## Repository and local use

For a fresh GitHub checkout or another build agent, start with the [checkout and agent handoff](docs/runbooks/agent-checkout.md). It distinguishes portable source from the original machine's retained databases, credentials and runtime evidence.

- [Implementation plan](IMPLEMENTATION-PLAN.md): connected increments and all-process coverage.
- [Architecture](guide/02-ARCHITECTURE.md), [phases](guide/05-PHASES.md) and [quality gates](guide/09-QUALITY-GATES.md): how to build and verify the factory.
- [Process map](contracts/process-map.json): original business identities and family responsibilities.
- [Policy configuration](guide/10-POLICY-CONFIGURATION.md): typed, versioned interfaces for missing business decisions.
- [Development runbook](docs/runbooks/development.md): local setup. The application uses http://127.0.0.1:8000 when running.
- `reference/` and `SOURCE-MANIFEST.json`: unchanged source evidence. Original pack manifests and QA describe the released v0.7 pack; dated build evidence records subsequent application changes.
