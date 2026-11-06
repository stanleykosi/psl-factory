# Product acceptance specification

acceptance.json contains initial connected-increment, cross-cutting and all-13-family cases. The initial M1-labelled IDs are stable test identifiers, not a scope limit. LATER-labelled IDs are full-product policy/provider cases, not features deferred out of the product. All cases remain SPECIFIED_NOT_RUN until actual execution evidence is recorded.

Every process in contracts/process-map.json links its exact source scenario IDs, family acceptance test, definition/execution contracts, UI and responsibilities. Read the frozen 266 per-ID scenarios, 19 cross-process safeguards, execution/billing/exception cases and agent evaluations as applicable. Collections overlap; do not total them into fictitious independent pass counts. Interpret historical cases through current business precedence.

Implement real domain/service/PostgreSQL/UI tests; mock external providers/targets where needed. Run initial M1-29 across the complete actual internal path. Each family must likewise prove its connected path, not merely display a screen. Test absent/invalid/active/stale/revoked policy, actual human/agent boundaries, denial with no state change, duplicate/concurrent delivery, worker restart and unknown-outcome reconciliation.

Financial expected results need independent owner oracles; until supplied, synthetic rules prove mechanics only. Real-provider evaluation and real-adapter operational validation are separate deliverables, not inferred from canned tests. Include security/privacy, configuration activation, migration/export/restore, performance and UAT checks across families.

Record actual commands/environment/results in BUILD-TESTS.md and link them to the coverage/backlog. Keep engineering completeness, test evidence, business configuration readiness and live readiness distinct.
