# Optional QuickBooks MCP provisions

This is separate from the direct REST QBO reader. Both remain unconfigured by default. No account, token, OAuth consent, live call or write has been created.

## Provider options and exact scope

The [official hosted Intuit pilot](https://intuitdeveloper.github.io/intuit-3p-ai-pilot/) is invitation-only. Its fixed endpoint is `https://mcp.quickbooks.intuit.com/mcp`, Streamable HTTP / JSON-RPC protocol `2025-11-25`, stateless. This implementation supports that target only. The official [local stdio server](https://github.com/intuit/quickbooks-online-mcp-server) is a different product with broad CRUD; subprocess execution, installation, credential persistence and local-server transport are NOT implemented or enabled here.

Only documented `qbo_sales_get_invoices` is potentially executable. Its actual schema is NOT published in the pilot overview and is NOT invented in this repository. Synthetic test schemas are not Intuit API contracts. Creation, updates, deletion, posting, payment, sending and every other tool are unavailable, regardless of server annotations or agent requests.

## Existing lifecycle, not a parallel approval system

Capture an existing integration contract with implementation `hosted_mcp_read_v1`, kind `adapter`, family `ledgerdata`, target `endpoint:intuit-mcp`, contract version `2025-11-25`, model null, data_scope `scoped_qbo_invoice_identity_read_v1` and capability `["health"]`. Existing scoped integration probe, assessment, configured human review and selection remain mandatory. Health is actual initialize plus bounded tools/list, NOT a PSL /health endpoint. Discovery never executes a business tool or grants permission. MCP does not provide business receipt lookup; a policy requiring receipt probes remains held, never silently waived.

A reference-only profile at `PSL_QUICKBOOKS_MCP_PROFILE` is optional; absence disables MCP. It is a bounded absolute regular non-symlink JSON file. Each alias has exactly: enabled, realm, principal_ref, credential_ref, credential_revision, app_name, contract_id, scopes, reviewed_tool, output_schema, target_argument, result_identity_key, fixed_arguments. Credentials are references to existing READINESS_SECRET_REFS, never values. Scopes must be accounting plus `sales.tools.invoice.read`; broad write MCP scopes are rejected.

Initially reviewed_tool/output_schema/target_argument/result_identity_key can be null. Discovery is retained privately but capability stays unready. Obtain the real tool schema through authorized discovery. Review it and configure exact tool descriptor, a bounded output projection schema, the exact argument field carrying the supplied source invoice ID, output identity field, and fixed non-secret arguments. Unsupported schemas or complex mappings fail closed rather than guessing. This version supports bounded closed JSON-schema objects/arrays/scalars, no references, regex or external schema resolution. Changed descriptions/schema/configuration/credential revision invalidate prior assessment. Re-probe and use the existing configured human review lifecycle.

## Native execution and access

System code calls apps.workflows.quickbooks_mcp reserve/execute/status. Explicit operator command `quickbooks_mcp_read` requires actor, case, lineage, contract and current case revision. The agent entrypoint apps.agents.quickbooks_mcp.read additionally checks agent.ledger and invokes the same broker. The existing Finance-ledger factory offers ACT11 only for a current configured MCP read, reserving an immutable agent-mode intent and reporting pending external read, never completed business output. The existing factory worker dispatches that exact intent after its reservation transaction commits. Explicit `quickbooks_mcp_dispatch --actor ... --case ... --intent ...` can dispatch an interrupted, still-unattempted reservation; no new autonomous scheduler is installed. ACT12 reconciles the completed observation into the same work history without dispatching another call or fabricating Finance verification. Planner `tools: []` remains unchanged.

Caller mode is immutable; agent.ledger is rechecked at reservation, dispatch, post-read currentness and reconciliation. Both callers require current ledger and private integration access, current nonconflicting exact source, matching company, selected reviewed contract, original credential/configuration, freshness and current policies. Arguments come only from the exact source target plus reviewed constants, not model-generated queries. Before call the tool inventory must still match exactly. The provider result must match a reviewed structured schema and exact target identity; text/resources/prompts are discarded. Results remain untrusted private evidence, never a LedgerCheck, Finance approval, accounting treatment or posting permission.

Append-only service-authenticated Evidence/Audit anchors preserve intent, once-only attempt and result. Unknown/interrupted reads are not replayed automatically; a new explicit read can be reserved after inspecting status. Revocation/context change in flight retains the remote fact as stale, without business adjudication. The 429 hold is company scoped for at least60 seconds. Evidence uses existing private integration_ kinds, and ledger.qbo. audit actions are hidden from generic timelines. Secrets/raw transport errors never enter records or logs.

## Setup inputs still needed

Hosted eligibility/invitation and IP onboarding; approved AppID and app name; actual company realm and principal; authorized accounting plus restricted read scope; approved token-reference delivery/rotation; exact actual tool/schema inventory and field projections; source mapping; current integration policy principals/freshness/review/selection. OAuth consent/token acquisition/refresh is an operator-authorized setup task, not automatically performed. Actual company binding is configured, not independently established by MCP serverInfo. Real provider acceptance remains unverified.

## Verification boundary

Component tests use synthetic transport responses only. Native database/service/factory acceptance, UI, actual provider schemas, OAuth, live MCP and operational acceptance are separate and must not be claimed from those tests. Browser testing is excluded from the user request. No changes to held Finance performance/F08 work.

Protocol parser supports bounded comment/heartbeat and priming events before a correlated SSE reply, id/retry metadata without automatic reconnection, and empty202 notifications. Unsupported server requests/notifications remain held. Component compatibility does not prove actual Intuit schema compatibility.

Factory-originated intent additionally pins the exact current execution-profile configuration/value and execution binding. Existing factory.profile checks remain authoritative. Only active ready/waiting/waiting_effect work may dispatch or reconcile; terminal, blocked, configuration-needed, cancelled or superseded-profile work cannot start an old reserved read. If authority/profile changes after a read was already dispatched, its immutable bounded observation is retained as stale, not retried, not promoted and not counted as current Finance verification. Historical status inspection does not grant dispatch authority.

The execution API rejects an enclosing transaction or disabled autocommit before claiming an intent or contacting the provider. This ensures the once-only claim commits before the remote read. Native execution tests use TransactionTestCase and never bypass this boundary.
