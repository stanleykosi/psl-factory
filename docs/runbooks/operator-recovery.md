# Operator recovery and protection evidence

This is an engineering implementation of phase 5 operator controls. Source responsibilities and all 122 process identities remain in the frozen process map. These infrastructure controls do not introduce a 123rd process or establish operational acceptance.

Open `/cases/<case-id>/operations/`. The inventory queries only that case's currently granted handoff, document publication, invoice, Engineering corrective request, partner Finance, department approval and metadata protection jobs. It exposes status, attempts, fences, lease state and source links. Error strings, effect intents, recipients and source bodies are excluded. Capture an immutable diagnostic snapshot before configuring recovery if useful.

Recovery requires both an explicitly configured operator/purpose/role and the source workflow's current record/action grants. The workbench delegates to the existing source service. Unknown effects cannot be force-cancelled, resent or replaced here: run the source worker's receipt lookup first. Active leases and proven effects retain the source service's controls. Cancelling a job does not remove debt, approvals, cash or historical receipts. Historical actors are not silently replaced.

## Configure only the required interface

`OPS.operator_rules` and `OPS.protection_rules` are versioned supplemental engineering interfaces under the supplemental OPS engineering namespace, using the registered-reference lifecycle. Original 57 component envelopes are unchanged. Typed forms show schemas; draft, validate and activate through the existing policy lifecycle. Actual D05 role appointments and purpose grants are required. Fixtures are explicitly synthetic examples, never PSL appointments or backup objectives.

Operator rules declare principals, purposes, permitted source routes/actions and evidence reviewer independence. Protection rules declare bounded projection size, required proof kinds, freshness, worker leases/attempt budget, backup/restore adapter and nullable RPO/RTO. Missing objectives remain unknown. A reference-only restore configuration holds native restore while configured export/backup remain available. Missing policy does not block plan/report capture, configuration or diagnostics.

## Actual implemented native path

1. Capture a versioned plan with explicit case source, source version, build reference, target reference, process scope, expected metadata count and SHA-256. Unknown count/hash/source/target are nullable during capture.
2. Reserve/export the currently scoped `portable_case_metadata_v1` projection. Only allowlisted evidence metadata and job metadata are included. No source bodies, payroll, credentials or runnable business payloads are exported. Downloads recheck every original source-read grant.
3. Reserve backup of the exact export artifact. The adapter creates a sealed, non-overwriting local JSON copy under `.runtime/operator-artifacts`. Existing conflicting bytes hold the job. Do not edit/delete evidence files to make an assessment pass; investigate and capture a new plan/intent instead.
4. Reserve restore of that exact backup into an explicitly configured **separate metadata database**. Set `PSL_OPERATOR_DRILL_DB` to an existing reviewed `(test_)?psl_drill_*` database and run `manage.py provision_operator_drill`. Provisioning creates only the metadata contract/receipt tables and immutable guard in that target. It never creates/deletes a database, changes the source database or restores business tables. The runtime rejects source/live/system database names. The drill inserts a manifest under the reserved operation key and reads the exact digest/payload back from PostgreSQL.
5. Run `manage.py work_operator_recovery --limit 20`. Durable claims use skip-locked leases/fences and stable intent identities. Receipt lookup precedes current permission checks and retry budget so a committed file/target effect can reconcile after a lost response and later revocation. Changed policy, source visibility or target identity requires explicit held-intent replacement, never silent reuse. Lookup unavailability remains unknown with no dispatch.
6. Assess the exact pinned artifacts/reports. Current assessments recheck file/target receipt availability, freshness, policy and evidence heads. New failed/unknown/unavailable reports can hold current readiness without erasing proven native history. A configured independent human reviews documentary completeness. Review reuse checks current reviewer authority and original source-read visibility.

Native effects are **metadata export/file copy/isolated PostgreSQL insertion and readback**. They are not a full database backup, a full restore, business-job replay, application startup recovery, a measured RPO/RTO, deployment authority or operational readiness. The isolated receipt is immutable and retained; the original job lease/fence is never restored as runnable work.

## Supplied evidence and investigations

Strict supplied reports bind exact plan/source/version/target, actual timestamps, external identity/version, scope, outcome, count/hash and nullable elapsed/lag measurements. Duplicate conflicting or cross-case external receipt claims are rejected. Supplied full-database reports remain unverified documentary evidence even when reviewed. Reported RPO/RTO comparisons are labelled reported; a review cannot upgrade them to native execution.

The bounded local operations agent identifies held/unknown/expired-lease questions and assessment gaps. It reads metadata, stores no raw source bodies/intents/destinations or source-controlled job identifiers, and executes no recovery. Private `ops_` evidence is excluded from generic evidence/document/AF13/meeting/extraction projections.

## Remaining engineering and owner inputs

Engineering: reviewed native full-database backup/isolated restore tooling, storage retention/encryption and target authentication contracts, full application startup/migration verification, large-case pagination/load/security tests, authenticated external receipt lookup/dispatch adapters, real-provider evaluation and owner UAT/operational acceptance across all 13 families.

Owner/system inputs: actual operators/roles/grants/reviewer independence, permitted recovery routes, infrastructure/storage/isolated target selection, retention, expected scope/version/hash/count, freshness and recovery objectives. No retention duration, RPO/RTO, financial policy or real principal is inferred.

Preserve existing databases and immutable artifacts. Tests create a new separately named metadata target only if absent; they never reset it. Each test uses a fresh case UUID so retained files/target receipts cannot contaminate another test. Actual test outcomes and failed runs are recorded in BUILD-TESTS.md.
