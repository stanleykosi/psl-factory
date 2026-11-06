# Quality and completion criteria

Review each increment and keep building. Gates describe evidence quality, not artificial stops after a milestone.

## Increment acceptance
Trace behavior to process IDs and source/configuration versions. Exercise intake, useful scoped agent/tool execution, deterministic checks, any required human decision, verified output and downstream receipt/next task through actual services. Exercise data/services, UI, agents and adapters together. Check that factory views reflect current authorised source state, next actions, responsible actors, waits, exceptions and recovery. Test queue/count coverage, time basis and privacy; missing data is not zero and service targets cannot be invented. Run schema/unit checks, actual PostgreSQL transaction tests, object-access tests, state/version/duplicate tests, restart/lease/outbox/unknown-outcome tests and UI/error/accessibility checks. Record command/environment/result and useful evidence. Never hide failures as a completed feature.

## Full-product acceptance
All 13 families and 122 IDs have an implemented disposition: workflow/control/output/reference/evidence-discovery, with UI/contract/test links. A reference-only activity must have the intended evidence/handoff behavior rather than be silently dropped. All stations have useful agent execution, deterministic controls, configuration UX and adapter contracts. Demonstrate work moving across stations and teams; completed forms, agent responses and green infrastructure jobs do not prove completed business outcomes. All policy slots can be entered/validated/versioned without changing workflow infrastructure.

Test absent, invalid, active, superseded and revoked policy; unrelated actions continue while dependent runtime transitions report exact missing keys. Test fixture-only policies cannot be promoted silently. Report structural build completion separately from operational policy readiness.

Real-provider evaluation measures extraction/citations/task completion/tool choice/injection resistance and cost/latency with independent oracles. Mock success is not model quality. Real-adapter tests verify target behavior and recovery. Include cross-family UAT, security/privacy review, migration/export/restore and load/recovery evidence. Runbooks cover configuration, deployment, monitoring, support and rollback.

## Recovery
Missing policy → typed dependency with decision/key/source; continue independent work. Denied application action → no state/effect mutation and minimal audit. Stale/conflict → refresh and re-evaluate, not overwrite. Known transient failure → bounded recorded retry. Unknown external outcome → stable-key reconciliation. Crash → lease/fence and persisted recovery. Pause/cancel → stop new dispatch while preserving existing effects/history. Irrecoverable state → visible operator queue and defined correction path.

## Completion reporting
Update build memory and coverage after each increment: implemented behavior, tests actually run, remaining engineering work and separate policy/deployment dependencies. Do not call a plan, fixture or schema check an implemented/validated workflow. Do not claim operational readiness while required real-world configuration/testing remains unavailable.
