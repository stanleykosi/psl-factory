# Start here

1. Read README.md and AGENTS.md: PSL Product Studio is PSL’s AI agent operations factory. Build connected work from intake to verified outputs through useful agent execution, human decisions and exception recovery.
2. Read BUILD-STATE.md and HANDOFF.md to resume existing work; use BUILD-BACKLOG.json to choose the next increment.
3. Read guide/11-FULL-PRODUCT.md and guide/02-ARCHITECTURE.md for the factory operating model, stations, primary UI and retained architecture. Department modules support production flow; they are not the primary product definition.
4. Read guide/01-BASELINE-AND-PRECEDENCE.md, guide/04-DECISIONS.md and guide/10-POLICY-CONFIGURATION.md before translating business rules into code.
5. Use contracts/process-map.json to load the relevant definitions, execution mechanisms and agent contracts for the current increment. Do not paste the whole archive into one prompt.
6. Implement intake → scoped agent work → verified output and downstream handoff, with human decisions where the source process requires them. Build data/services, UI, adapters, recovery and tests together. guide/03-FIRST-MILESTONE.md is the first demonstration, not the end of the product. Continue using guide/05-PHASES.md.
7. Apply guide/09-QUALITY-GATES.md and update the durable build files after each increment.

## Durable build memory
- BUILD-STATE.md: concise completed/current/next summary and important blockers.
- BUILD-BACKLOG.json: work items, process IDs, dependencies, status and evidence.
- BUILD-DECISIONS.md: architectural/product decisions and supersessions; business-policy decisions link to their source and configuration version.
- BUILD-TESTS.md: actual test runs, environment, failures/skips and evidence.
- BUILD-LOG.md: append-only meaningful change history.
- HANDOFF.md: immediate restart instructions and unfinished work.

Maintain these files in the existing application repository. Update current records rather than creating competing status documents. Source snapshots remain immutable; implementation status lives in build memory and coverage records.

## Evidence navigation
Current all-process binding: reference/12-payment-exception-policy/process-execution-bindings.json. Business definitions: reference/03-definitions. Agent roles/capabilities: reference/08-agent-architecture. Execution mechanisms: reference/09-execution-contracts. Billing contracts: reference/10-billing-workflow-amendment, interpreted through folder12. The source README contains historical navigation; this pack's entrypoints govern how to build.

SOURCE-MANIFEST.json records frozen source bytes. PACK-MANIFEST.json and VALIDATION.json describe the original released pack, not the current application tree or acceptance status. Use the latest manifest named in HANDOFF.md for current build integrity, and BUILD-TESTS.md for actual validation results.
