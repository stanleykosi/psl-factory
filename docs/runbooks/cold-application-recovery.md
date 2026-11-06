# Fresh-authority source-unavailable recovery

Engineering runbook. Actual test results and remaining limitations are in BUILD-TESTS.md and HANDOFF.md. This path recovers a bounded native PostgreSQL/managed-attachment archive to an isolated target. It does not activate the recovered application.

Provision a separate empty PostgreSQL control database named `psl_cold_<deployment-reference>`, independent of the source and target. Use `config.cold_settings` for its management commands and web process. Provision a separate empty `psl_recovery_<target-reference>` database, disjoint existing archive/attachment directories, an independent control secret and the archive encryption key. Never point the control application at a recovered database. Normal recovered application/worker startup remains prohibited.

The deployment-owned JSON selected by `PSL_COLD_RECOVERY_PROFILE` has these exact fields:

```json
{
  "control_ref": "<independent opaque reference>",
  "control_database": "<fresh psl_cold_ database>",
  "control_secret_env": "PSL_COLD_CONTROL_<dedicated reference>",
  "archives": {
    "<archive reference>": {
      "database": "<historical source database identity>",
      "archives": "<absolute provisioned sealed archive directory>",
      "operation_key": "<exact 64-character native archive operation SHA-256>",
      "sha256": "<independently verified complete sealed file SHA-256>",
      "revision": "<storage inventory revision>"
    }
  },
  "targets": {
    "<target reference>": {
      "database": "<separate empty psl_recovery_ target>",
      "attachments": "<absolute empty isolated attachment directory>",
      "revision": "<target inventory revision>"
    }
  },
  "key_env": {"<key reference>": "PSL_RECOVERY_KEY_<dedicated reference>"},
  "principals": {},
  "build_ref": "<exact compatible application build reference>",
  "pg_bin": "<absolute reviewed PostgreSQL binary directory>"
}
```

Both dedicated environment secrets must decode to32 bytes. Neither is entered through the UI, stored in business policy, printed in job receipts or passed on process command lines. The control secret authenticates the independently initialised control identity; it is distinct from the archive key. Archived policy, principals and grants are never imported into current authority. Exact application build compatibility is required; code-version migration/upgrade is separate work.

Set `DJANGO_SETTINGS_MODULE=config.cold_settings` and the fresh control database connection environment. Run `manage.py migrate` on that fresh database, then `manage.py initialize_cold_control`. Initialization creates only the immutable independent identity; it creates no users, grants, policy, approvals or effects. It refuses preexisting people, cases or authority, an existing identity and quarantined/recovered databases. Provision fresh human accounts and a control case through the organisation's separately controlled database/identity administration after initialization. Do not recover user accounts or copy source grants. Assign scoped `case.read`, appropriate `cold.read/capture/operate/review/agent/configure`, existing evidence/configuration permissions and fresh D05 role assignments. The deployment principal registry additionally pins each actual user PK to its username and allowed purposes, for example `{"<actual PK>": {"username": "<fresh account>", "purposes": ["read", "review"]}}`. No names or roles have defaults.

Start the separate control web process with these same settings. Its home lists authorised control cases. Capture the three opaque archive/target/key references; capture checks authenticated sealed input and records exact file/manifest/runtime hashes even before recovery policy exists. The workbench records fresh configuration-decision evidence and drafts `OPS.cold_recovery`; the linked configuration lifecycle validates/activates explicit versions. Configure actual distinct operator/reviewer IDs, D05 roles, scope and archive/command/lease/attempt/authorization validity criteria. The JSON schema is visible. Missing criteria hold approval/dispatch rather than capture and investigation.

An independent configured human reviews the exact captured request. The configured operator queues that immutable intent. Run `manage.py run_cold_recovery --limit <bounded count>` in the control environment. Workers inspect target receipts first; absent a receipt, current criteria, fresh operator/reviewer purposes, current role assignments, independent approval, exact deployment/build identity and the original attempt budget must all match. Native restore uses one PostgreSQL transaction including constraints and the exact receipt, and verifies complete row/schema/migration/sequence/attachment evidence. It never connects to the historical source. The sealed archive's inactive source users are evidence only.

A held intent may be reconciled through the workbench without resetting its attempts or overwriting target history. A crashed committed restore can be confirmed by a later fresh worker even after the original actor is revoked or the attempt budget is exhausted; this reconciliation records existing physical evidence and cannot create a new effect. A changed archive/key/build/target requires an explicit captured successor and new independent decision. Nonempty unrelated targets remain unavailable. Do not delete/reset databases, receipts or archive bytes to force a retry.

After physical confirmation, the independent reviewer records a recovered decision against current physical proof. Reports and bounded agents disclose scoped status and next steps, never archive bodies, native stderr, keys or paths. This decision does not confer operational acceptance, activate users, send external work or satisfy process-owner/SOP/provider/security/load/UAT requirements. Larger/streamed archives, external repositories and operational activation remain separate engineering work.
