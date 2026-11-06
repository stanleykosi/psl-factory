# Selected live-pilot preflight — engineering contract and remaining scope

This is proposed engineering work. It is not a live-run receipt, source-backed business policy or a claim of production readiness. Owner policies remain deferred globally; only rules needed by an explicitly selected pilot operation affect that operation.

Implementation checkpoint (28 October2026): the bounded single-case selection, immutable metadata observation, UI/export and native investigator are implemented; actual verification outcomes are recorded in BUILD-TESTS.md. See docs/runbooks/pilot-preflight.md for the implemented interface. This design remains the broader target, not evidence that every item below is operationally verified. Operation-to-participant permission sufficiency, real source/oracle contracts, independently attested worker/storage/monitoring and supervised staff verdict bindings remain explicit follow-up work. A pack's current flag means its observed heads/freshness/authority match; it never means operational readiness or live acceptance.

Build a read-only, access-filtered preflight/rehearsal evidence pack over the existing identity, policy, workflow, adapter readiness, operator recovery and deployment interfaces. Reuse those services instead of creating another authority or readiness system.

The selected pilot contract must explicitly name permitted case(s), existing operation/family IDs, intended participants, source/target contracts and effect boundaries. Do not assume all124 interfaces are prerequisites for one workflow, use synthetic rules for operational resolution, appoint users, install credentials or schedule effects from preflight.

Report separately:

- Software/source coverage: declared workflow and impact-adapter scope, current observed heads, known variants and unknown consumers. A tested selected path is not acceptance of all122 process IDs.
- Technical deployment: actual web/worker build and schema identity, secure deployment checks, storage/retention and monitoring configuration. Report findings with evidence; do not silently turn off safeguards or output secrets.
- Identity and policy: exact current participant record/action grants, selected source scopes and independently resolved operation dependencies. Missing authority/value holds only that operation and does not erase evidence work.
- Integrations/providers: current reviewed target/source contracts, authenticated health/evaluation/receipt evidence, deployment-owned credential revision references and actual receipt meaning. Fixture HTTP success is not a real-provider or incumbent-system acceptance.
- Recovery: actual accessible backup/export/restore and unknown-effect recovery evidence. Preserve committed receipts, quarantined archives, fresh authority and receipt-first reconciliation; never replay jobs to prove readiness.
- Human acceptance: bounded rehearsal steps, source facts vs engineering decisions, observed results, unresolved holds and explicit staff verdict. Keep operational acceptance and owner configuration inputs separate from implemented software.

Provide ordinary UI and a bounded investigator over the same projection. Version the selected contract and evidence observation; stale source/policy/grant/build/receipt heads invalidate the report instead of silently becoming a new authorization. Test PostgreSQL access/privacy/stale/unknown-effect cases and technical deployment findings without installing real owner values or executing live effects.

docs/runbooks/supervised-impact-pilot.md is the proposed human sequence. Actual completion evidence belongs in BUILD-TESTS.md and pilot receipts, not this design.
