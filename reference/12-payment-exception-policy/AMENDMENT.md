# Human approval for payment exceptions

Version 0.6 | 19 October 2026 | Compact amendment to v0.5

## Confirmed decision

The user confirmed that an exception can be given below the stated 80% payment expectation and that the approver must be human. The user cannot identify the authorized role yet. Record the role as UNCONFIGURED, not CEO, Finance, PMO or an agent.

The proposed workflow may prepare, request and track an exception under the relevant existing request permissions. It cannot approve the exception, mark it authorized or claim payment is waived while authority remains unconfigured. This does not stop unrelated process-definition work. Existing Engineering, Security, Go/No-Go, GLPI and other release controls remain unchanged.

A deployment payment exception is not a debt waiver. Even after a properly authorized future approval, invoices, receipts, outstanding balances and financial obligations remain unchanged unless a separately authorized financial action says otherwise. No such action is authorized here.

## Source and chronology

U07: user message Sentinel_cf2e9c2d23c881918e40d8b6eebc5506: “for this an exception can be given”. This answered whether an exception below 80% can be approved.

The assistant then asked who has authority to approve, stating it would be explicit recorded approval rather than agent self-approval (Sentinel_a2838b2209fc8191828fac1d502c5467).

U08: user message Sentinel_17e84655ed6c8191875c4d8e3bd2116e: “it has to be a human but for now i can't tell”. Exception capability and human-only approval are now answered. Actual authority remains deliberately unconfigured. This narrows D13; it does not reopen the answered questions or change the agreed planning/Finance responsibilities.

## Proposed technical defaults

Bind the request to tenant, project, contract version, exact deployment, complete current payment snapshot manifest and assessment-policy version. Include reason, evidence, requester, requested validity window and immutable versions. The requested window is not an approval. Audit each accepted action with an idempotent operation key and authenticated identity. The outer record stores server-verified requester_principal_ref; trusted runtime resolves it from identity and enforces own-request withdrawal. Caller-provided tenant and project references must match trusted authorization scope; they are not grants.

The current schema permits only prepared, requested, awaiting-authority-configuration and withdrawn states. It requires UNCONFIGURED authority, null approval and false authorization/waiver flags. A submitted role name or approved flag is not accepted as authority. These restrictions describe the current design, not a deployed enforcement mechanism.

A separate future decision contract defines how an authorized human could approve or reject after the real authority policy is configured. Identity and permission must come from a trusted authorization service, not a document or model assertion. Configuring that authority requires separate owner-approved evidence; no permission to configure it is granted by this amendment. An agent may assemble evidence and track requests but cannot grant, extend or revoke authority on its own.

Proposed future decisions retain reason, evidence, actor, policy, bound versions, validity and audit. Revocation, expiry or material changes in the contract, payment snapshot, policy or deployment require reassessment rather than silent reuse. Exact validity/delegation/revocation rules remain owner configuration. No invented second approver or automatic exception is introduced.

Validate exception status and all other release controls at the dispatch reservation. Revocation before reservation prevents its use. A change after reservation may race with an external release; preserve evidence and use the existing reconciliation/incident path, not a promise of automatic rollback.

## Remaining configuration and tests

D13 now asks only for actual human authority when available, its delegation/validity/revocation rules, and the still-needed agreed payment calculation basis. Do not keep asking whether exceptions exist or whether the approver can be an agent: those are settled.

The twelve negative mock scenarios cover unconfigured or spoofed authority, agent self-approval, stale evidence, wrong deployment, expiry/revocation, independent Security gates, duplicate requests and unchanged financial balances. They are specified acceptance cases, not executed application tests. Schema checks validate only shape; later implementation must enforce authorization, timestamps, concurrency and other semantic rules.

All 122 original IDs and the earlier v0.5 release remain preserved. Current bindings add U07/U08 only to P30, P31, P32, P34 and F34. No app build, deployment, live invoice/payment action, new credential or scope/timeline change is authorized.
