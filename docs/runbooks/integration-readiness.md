# Adapter and provider readiness

Phase 5 engineering increment BUILD-NATIVE-READINESS. Original business responsibilities, all 122 process IDs and source approval/financial controls remain unchanged. This workbench records bounded capabilities and current evidence; it does not establish deployment or operational acceptance.

Open `/cases/<case-id>/integrations/`. Separate record/action grants govern metadata, private contract/observation bodies, capture, probing, assessment, human review and dependency enrollment. Generic evidence/document/AF13/meeting/extraction readers exclude private `integration_` sources. The deterministic investigation agent sees ordinal/status/recorded-assessment metadata and questions, not endpoints, secrets, raw model output or business payloads.

## Contracts and configuration

Capture immutable versioned adapter/provider contracts before policy or credentials exist. Target, credential reference/revision, principal, protocol version and model can remain null. Runtime probes hold while required fields are unknown. Contracts select reviewed implementation IDs, a logical target key, credential reference/version, expected authenticated principal/protocol/model, capabilities and a fixed data scope. They cannot contain URLs, authentication headers, executable code or credential values. Credential references use `runtime:postgres` or `secret:<logical-name>`; endpoint aliases use `internal:<family>` or `endpoint:<logical-name>`.

Two supplemental INT engineering components, `INT.adapter_readiness` and `INT.provider_readiness`, use existing registered-reference/versioned policy lifecycle facilities. They are not new consolidated D groups or PSL policy facts. Typed rules declare actual probe/reviewer principals and D05 roles, independence, freshness and bounded lease/attempt budgets. The adapter receipt-probe dependency is configurable. Provider evaluation always uses idempotent receipt-first recovery; its public canary has a fixed independently specified oracle. Synthetic values and appointments are fixtures, never operational defaults.

`READINESS_ENDPOINTS` and `READINESS_SECRET_REFS` are deployment/code-owned registries. The UI cannot create arbitrary network destinations or read environment variables. Endpoint entries contain a reviewed origin and synthetic/operational classification. Secret entries contain an environment-variable name and explicit revision. Values are resolved privately at execution. No environment dump, raw credential, authentication header or raw endpoint error is stored in evidence, audit, forms or agent output. A keyed credential binding detects rotation even when the revision is mistakenly reused; it is not an unkeyed password hash. Keep the application signing secret and actual credentials outside evidence/configuration.

`PSL_READINESS_DATABASE_REVISION` supplies an explicit revision for the existing runtime PostgreSQL credential reference. An absent revision holds new database probes, not contract capture. Native sessions use the configured source connection; protection uses the existing separately configured metadata drill database. There is no database creation, reset, arbitrary SQL or target selection through this interface.

## Implemented adapters and evidence classes

`internal_postgres_session_v1` opens a real separate PostgreSQL session, checks server-reported current principal/database and SELECT privileges for a reviewed receipt-table registry. Receipt probes use an exact case-scoped existing source job and its real adapter lookup. Protection probes read the actual isolated restore receipt. Results distinguish found from not found; neither observation is a new invoice, payment, publication, Engineering correction, approval or restore. PostgreSQL session identity does not prove that password authentication/TLS/production access policy was enforced. The evidence explicitly leaves password authentication unproven.

`authenticated_json_v1` is an engineering gateway protocol, not a claim that an incumbent system/vendor already implements it. Reviewed endpoints expose bounded JSON `/health`, idempotent public-canary `/evaluate` and exact operation-key `/receipts/<key>`. Normal deployments require verified HTTPS; only explicitly synthetic loopback targets may use HTTP. Environment proxies, redirects, userinfo/query/fragment/path-bearing origins and unbounded/non-JSON/duplicate-property responses are rejected. Authorization rejection is sanitized. No private business evidence is transmitted.

Health compares exact expected principal, protocol version, model and declared capabilities. The provider canary sends only the fixed public sentence and compares the exact independently fixed extractive oracle; the implementation never repairs the returned answer. Store match flags and output hash, not raw model output. Synthetic authenticated HTTP tests are provider mocks. An operational gateway response can establish an authenticated public-canary transport result; it cannot independently prove which underlying model executed or establish general model quality. Native business dispatch/provider acceptance remains separate.

Supplied reports bind the exact contract hash, kind, outcome, actual timestamp and source reference. Even a supplied success cannot satisfy authenticated readiness. An unavailable report can invalidate current readiness while preserving native history. Corrective native probes and fresh assessment/review are needed; source wording cannot create authority.

## Durable probing and human review

Reserve a health, receipt or evaluation probe with a stable intent key. Run `manage.py work_integration_readiness --limit 20`. Jobs pin contract, target/credential identity, scoped authority, policy and budgets. Workers use skip-locked leases/fences, revalidate before probing and reconcile committed local observations or remote evaluation receipts before current permission/budget checks. Lost responses do not cause blind provider reruns. Changed credentials/targets require a new intent key; uncertain old evaluations still require original-target receipt reconciliation. Operator retry/cancel is scoped and cannot overwrite proven or unknown work.

Assessment pins current contract, policies, runtime binding and observation/probe heads. Freshness, current principal/grants, negative or unavailable evidence and pending/uncertain probes govern current readiness. Human review uses the exact configured current role and source access, with configured independence from preparation. New context requires reassessment and review, never history rewriting. Return/withdraw remain human evidence dispositions and grant no dispatch authority.

## Connected source workers and provider gateway

Enrollment adds a live readiness dependency for the selected case/family. It does not choose a new destination or rewrite the source business intent. Source workers retain their existing permission, review, calculation, idempotency and receipt checks. Implemented connections are handoff, controlled publication, invoice issuance/delivery/correction, Engineering corrective requests, partner Finance, department approval routing and metadata restore. Export/backup remain independent of the restore enrollment. Existing un-enrolled workflows retain their original controls. There is no silent unenrollment or policy-missing fallback after enrollment.

Committed source effects reconcile before readiness checks. A later readiness failure cannot erase debt, cash, business receipts or independent release controls. Readiness observation receipts and source business receipts are separate records.

The readiness gateway runs the fixed public canary after current review/enrollment. Separate reviewed factory-planner and private-evidence gateway clients, signed Finance follow-up metadata transport, and domain receipt/preflight clients are implemented. These interfaces retain their own scoped contracts, data-egress controls, authority and receipt checks. Their existence is not evidence of a configured vendor or successful real-provider evaluation. A target contract or successful canary does not unlock private data transmission or business tools; operational draft generation remains separately unavailable without a reviewed implementation.

## Verification and remaining work

Current connector status: QuickBooks system/agent MCP provisions and direct REST reads are implemented, with bounded synthetic native acceptance781 (50 attributed passes:42+4+4, not50 fresh on one revision) and later provider hardening785 (35 native passes). See quickbooks-mcp.md, docs/design/quickbooks781-final-proof.json and docs/design/provider-hardening785.md; local integration records44ec9c5 andd2efff5 preserve exact attribution. These results do not establish a configured or accepted live provider.

Use the existing QuickBooks setup-input checklist for hosted eligibility, actual company/principal, consent, credential references and actual tool/schema/projection requirements. Genuine owner/HOD policy and source decisions remain distinct from provider setup and unresolved engineering/acceptance gaps. Follow the latest BUILD-BACKLOG/BUILD-STATE/HANDOFF rather than historical pending-work lists; browser testing is excluded and held security/performance/F08/sign-conversion work is not authorized by connector acceptance. No new provider, credential or business authority is created by this status update.

See BUILD-TESTS for actual runs, failures and PostgreSQL concurrency/process evidence. HTTP fixtures authenticate requests and persist idempotent mock provider receipts over real loopback HTTP; internal domain workflows and PostgreSQL services are not mocked. Native database sessions and real-provider/vendor evaluation are reported separately. Never read `.runtime/demo-access.txt`, rerun one-shot walkthrough seeds, reset existing databases or backdate naturally expired evidence.

Remaining integration setup and acceptance: select actual vendor/incumbent protocols and configure reviewed target/credential/principal/version/model contracts, grants/roles and acceptance criteria; verify independent model/provider quality, production authentication/TLS, managed identity/secret-store setup and operational acceptance. Existing generic gateway clients are not proof that a selected vendor implements their protocol. Provider-specific adapter gaps must be assessed against that selected contract. Current broader milestone gaps are tracked in BUILD-STATE and HANDOFF; this runbook does not declare full acceptance.


For focused operations, both `work_integration_readiness` and `work_outbox` support `--case <UUID>`. This selects the queue scope; it does not grant authority or bypass original-actor checks. Use it for walkthroughs/recovery so unrelated queued work is untouched. The readiness walkthrough preserved every pre-existing handoff state hash, including an older claimable job. Do not drain an unrelated queue to demonstrate a new case. RUN157 verifies scoped CLI behavior, default competing workers/process recovery and source permission checks.


## Offline deployment registry preflight (RUN780)

`PSL_INTEGRATION_PROFILE` is an absolute path to a bounded regular JSON registry file.
An absent setting preserves empty registries and holds dependent adapters. The loader
rejects duplicate JSON properties, nonfinite values, unexpected fields, malformed
references, mismatched sender revisions, duplicate/noncanonical case UUIDs, and
unsafe origins. Validation remains active with optimized Python (`-O`).
Secret references contain only environment-variable names and explicit revisions;
never put credential values in registry JSON. Endpoint and secret aliases follow
the existing `endpoint:<logical-name>` and `secret:<logical-name>` contracts.

Run `python -m config.integration_runtime --profile /absolute/path/to/registry.json`
(or omit `--profile` to use the setting). This offline command opens only the registry,
resolves no secret values, performs no DNS/network/database requests, and reports
logical aliases rather than origins, environment-variable names or case bindings.
Exit 0 means valid references or an explicitly reported unconfigured environment;
exit 2 means invalid input. Neither result proves credential availability, provider
identity, connectivity, readiness, authorization, quality or owner acceptance.
The 1 MiB file, 1,024 entries per section/case list, and bounded reference/origin
lengths are engineering input limits, not owner business policies.

Focused verification: `python -m unittest tests.test_integration_runtime` and
`python -O -m unittest tests.test_integration_runtime`. These use synthetic files
and environment mappings; the Finance credential-function test executes the exact
production function without importing ORM endpoints. It is not a database/HTTP
workflow test or a substitute for existing integration suites.
