# Proposed next: native source-owner follow-up receipt readback

Status28 October2026: the bounded internal v1 contract is implemented and verified in RUN293. See `docs/runbooks/finance-followup-readback.md` and current build records for evidence and limits. Authenticated request transport, financial successor lineage and operational acceptance remain separate gaps. The original engineering proposal follows.

Engineering proposal, not source-backed policy or tested implementation.

The invoice/correction increment supports exact native receipts, independently reviewed publication and human-supplied metadata intake into the current source Finance workflow. The current source owner can investigate, decline or explicitly link an existing intent under current configured authority. The supplied handoff itself is not authenticated control authority, and the link is not execution approval.

Next connect these source-owned records back to the original control mapping through the independently registered current Finance PostgreSQL provider. Match the exact exported request digest, source case/invoice/correction and published companion hash. A native acknowledgement must distinguish request receipt, historical owner disposition and a disposition whose current policy/role/grant/intent binding has been verified. Missing, conflicting, revoked and stale records need separate visible states. Do not infer present financial effects from a request acknowledgement or owner link.

Build a typed versioned request/response and owner-validity projection selected from code-owned contracts. Use independent current provider identity/credential binding, exact case scope, bounded read-only queries and canonical payload hashes. Exclude source document bodies, personal data, raw operations and credentials. Capture immutable observations and independent reviews in the existing native evidence path where possible; avoid another chain of AF13 acceptances.

Any authenticated transport into the source application must authenticate the sender separately from supplied content, remain idempotent and create only a source-owned investigation request. A source human retains the normal invoice/correction decision, execution and uncertain-effect reconciliation interfaces. New financial successor intents need explicit lineage to the original request and their ordinary current approvals; no recovered job replay or grant import.

Add source-owner and control UI/agents, absence/conflict/expiry/revocation/credential-rotation/duplicate and fresh-process PostgreSQL tests. Preserve all122 process identities,13 families,15 leased job families, original receipts/debt and recovered startup quarantine. Operational principals, owner policy values, credentials, topology, vendor semantics and real-provider/security/load/UAT evidence remain separate configuration/deployment slots.
