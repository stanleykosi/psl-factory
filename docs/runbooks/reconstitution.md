# Reviewed reconstitution and unresolved effects

Engineering runbook. This workflow produces an inert reviewed plan from an independently reviewed cold recovery. It does not activate the recovered application, re-enable authentication/outbound adapters, waive debt, release a project or retry archived jobs. Actual test status is in BUILD-TESTS.md.

Use the independently initialized control database and fresh identity/purpose setup from cold-application-recovery.md. Add explicitly assigned `reconstitution.archive` and per-action `reconstitution.read/capture/operate/review/agent/configure` grants on the control case. Existing cold deployment purposes, record grants and D05 assignments remain independently checked. A model, source document or archived principal cannot assign these permissions. Current physical recovery and independent recovered review are prerequisites; changed recovery evidence invalidates dependent reconstitution work.

Provision a deployment-owned profile through `PSL_RECONSTITUTION_PROFILE`. Its top-level fields are `profiles` and `key_env`. Each opaque profile reference maps to this exact shape, with actual values supplied independently:

```json
{
  "control_case": "<fresh control-case UUID>",
  "recovery_job_id": "<actual confirmed cold recovery integer PK>",
  "archived_case_ids": ["<every archived case UUID>"],
  "destination_ref": "<intended operational destination reference>",
  "revision": "<deployment profile revision>",
  "receipt_path": "<absolute independently supplied current gateway manifest file>",
  "receipt_provider_ref": "<gateway identity reference>",
  "receipt_key_ref": "<dedicated verification key reference>",
  "artifact_root": "<absolute existing independent output directory>"
}
```

The actual `recovery_job_id` is an integer, not a quoted placeholder. `key_env` maps the receipt key reference to a dedicated `PSL_RECONSTITUTION_KEY_<REFERENCE>` environment variable containing a base64-encoded32-byte HMAC key. This key is distinct from the archive/control keys. No secret, filesystem path or executable command is accepted through business policy or the UI. Archive storage, recovered attachments, gateway directory and output directory must be disjoint nonsymlink directories. The destination reference describes intent only; it is not an activation command or URL.

The reconstitution workbench is linked from cold recovery. Capture a complete inventory before downstream criteria exist. The adapter checks all archived cases against the explicit deployment inventory, uses one read-only PostgreSQL snapshot, verifies recovered rows/schema/files and projects only state, opaque hashes and historical-receipt presence. It covers every model with the leased-job field contract, including PMO/Finance handoffs, publication, invoices/corrections, Engineering, partner Finance, approval, private Support responses/channel checks, private Finance extraction, protection, readiness, native application/cold recovery and reconstitution artifacts. A future unmapped leased-job model or a record-budget overflow holds capture instead of producing a partial acceptance. Human tasks are historical application data, not executable effects to drain.

Draft/validate/activate `OPS.reconstitution` through the workbench and shared versioned configuration lifecycle. Actual distinct operator/reviewer IDs and D05 roles, allowed human dispositions, exact profile/destination references, record/receipt bounds, evidence freshness, review validity, lease/attempt criteria and synthetic/operational scope are explicit. `activation_mode` supports only the reviewed-plan contract. Missing criteria hold probes, dispositions and publication; capture and investigation remain available.

The native receipt adapter reads a closed signed gateway manifest:

```json
{
  "body": {
    "format": "psl.receipt-evidence.v1",
    "provider_ref": "<configured gateway reference>",
    "archive_sha256": "<exact sealed recovery archive SHA-256>",
    "revision": "<gateway observation revision>",
    "observed_at": "<timezone-aware observation timestamp>",
    "expires_at": "<timezone-aware expiry timestamp>",
    "records": [{
      "effect_key": "<exact captured case/family/job effect key>",
      "family": "<registered family>",
      "operation_sha256": "<exact inventory operation hash>",
      "intent_sha256": "<exact archived job-row hash>",
      "receipt_sha256": "<independently supplied receipt evidence hash>"
    }]
  },
  "signature": "<hex HMAC-SHA256 over canonical sorted compact UTF-8 body JSON>"
}
```

Signature, exact sealed archive, provider identity, case/family/job effect key, operation/row hashes, bounded closed fields, duplicate identities, timestamps and configured freshness are checked. Signed evidence for another archive is rejected; another effect never matches even if its operation or row hashes coincide. This proves a configured gateway attestation, not direct vendor transaction verification or financial correctness. A missing record yields UNKNOWN, never proof that an effect did not happen. Actual provider-to-gateway verification contracts, keys and ownership remain separate deployment/evidence requirements.

The operator reserves a per-effect receipt observation. Run `manage.py run_reconstitution --limit <1..20>` in the cold control environment. The worker records sanitized immutable evidence artifacts. The independent reviewer records a versioned `receipt_confirmed`, `unresolved`, `retain_quarantine` or `replacement_required` disposition, as permitted by the active policy. Receipt confirmation needs a current authenticated matching observation; a human cannot type a positive provider result into the UI. Retained quarantine and replacement-required record decisions only: they do not cancel source records or dispatch replacements. Replacements need current source-owned business approvals and their own new intents.

Every inventoried effect needs an explicit human disposition before complete-packet approval. Unresolved dispositions remain visibly unresolved even in an approved inert plan. Current evidence, decisions, policy/runtime and review validity bind publication. The operator queues the reviewed plan; native output is append-only and receipt-first reconciliation confirms existing committed bytes after a crash or revocation without creating a new effect. Changed disposition, receipt, reviewer, profile, policy or recovery invalidates affected current approval; old decisions/artifacts remain immutable. Held/uncertain work retries its original identity and attempt history, never an archived business identity.

Read reports and live agents for exact effect keys, missing criteria and next steps. No generic private AgentRun, source bodies, native stderr, passwords or keys are exported. Independently provisioned operational identity, provider enablement, pending/unknown business-effect migration and actual deployment activation are separate work. Unconditional recovered-startup quarantine remains in force. Actual owner/SOP/provider/security/least-privilege/SSO/TLS/load/UAT evidence and larger/external archive variants are not inferred from a reviewed plan.
