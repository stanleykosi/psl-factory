# Native application recovery checkpoint

Verified bounded engineering implementation; actual results are in BUILD-TESTS.md and docs/test-evidence/2026-10-27-application-recovery-runs.json. See docs/runbooks/native-application-recovery.md for current scope, transforms, limits and controls. BUILD-COLD-RECOVERY is proposed separately for fresh-authority source-unavailable restore; offline read-only inspection is implemented and grants no restoration authority. All122 processes remain partial.

## Original engineering proposal retained for history

# Proposed next connected application recovery increment

Proposed engineering work, not implemented or tested behavior. The current native operator adapter exports/restores portable case metadata. Its full-database/application flags correctly remain false. AF13 operator health/receipt proof ends at that bounded capability; it must not generate another recursive owner-packet chain.

Inspect a distinct full application recovery contract and adapter. Use a transaction-consistent PostgreSQL archive plus an explicitly inventoried attachment set, schema/migration/build compatibility, closed manifests, content hashes and independently configured encryption/storage references. Keep this artifact type distinct from portable metadata and from operational deployment approval. Never put credentials, runtime secret files or the demo access file in a manifest or archive.

The first implementation/test target should be an explicitly provisioned isolated synthetic database and owned temporary files. Validate exact source/target identities, permissions, retention/size/time criteria and storage/key references through typed versioned configuration. Missing actual values must hold only the dependent capture/restore action. Do not invent financial policy, real owners or production runtime identities.

Restore into a separately named empty isolated target through a code-owned adapter; never drop/reset an existing application database. Verify schema, constraints/functions, migration identity, row/content inventory and attachment bytes. Retain receipts, failure and compatibility evidence. The restored copy must have outbound effects and authentication disabled before any application is started; restoring historical grant/approval rows is not restoration of live authority. Human review and fresh operational principal/provider configuration remain independent.

Reuse durable exact-intent jobs, receipt-first uncertain-outcome reconciliation, human review, bounded live investigation and record/action access checks. Build authenticated source-filtered UI and actual PostgreSQL/archive/file/concurrency/fresh-process tests together. Preserve all existing source/migration/history bytes and main application data. Test wrong target/type/build, incomplete archives, missing/corrupt attachments, partial restore failure, revoked authority and duplicate workers without destructive cleanup or receipt overwrite.

After an isolated synthetic implementation passes, actual infrastructure, external source/provider contracts, security/load/UAT and process-owner/SOP evidence remain distinct requirements. A successful isolated recovery must not claim production recovery objectives, operational acceptance or deployment authority.
