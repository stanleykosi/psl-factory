# B14 source revisions, clock corrections and shared operations

This is an engineering contract extending the proposed B14 Support flow. It does not supply a native customer-channel API, actual source mappings, business appointments or owner acceptance. Configure actual rules and people through the existing versioned policy lifecycle. Synthetic examples are never operational defaults.

## Configuration and human work

The channel workbench at `/cases/<case>/support/channels/` accepts `B14.clock_corrections`. Its closed schema requires actual proposer and independent reviewer IDs, permitted modes, whether source revision is allowed, explicit receipt/review age limits, `reviewed_human_customer_delivery` basis and `immutable_events_separate_metric_projection` history handling. Enabled source revision additionally requires its actual source author; when explicitly disabled, source_author_id may be null and its action grant is not required to configure clock correction. Actual source, relevant channel-action, Support-purpose and D05 grants are required. Mandatory receipt/correction independence is enforced directly even when the older Support policy permits self-review. Missing correction configuration holds only corrections/source revisions; original receipt capture, checks, release and clock configuration remain independently usable.

Capture private source-revision, correction-reason and review evidence through the workbench. A source successor identifies its exact predecessor and a distinct supplied receipt version. It retains the same tenant/channel/account/external identity, customer/recipient/sender and exact human-released message. It is a supplied claim, not a new verified observation. Run a new authenticated read-only check and an independent receipt review. Old claims, jobs, receipts and reviews remain immutable; a source successor prevents current reuse of its predecessor. A different message or customer requires a separately authorised release, not a renamed old receipt.

Propose a clock correction with an explicit latest predecessor, stable key, private evidence and bounded reason. The configured independent reviewer then confirms, returns or withdraws that exact proposal. Review does not send a message or modify a Support event. Modes:

- `revalidate` retains the exact released-message lineage and timestamp while binding a renewed receipt review/current policy.
- `replace` retains the original released-message lineage and installs the exact independently reviewed timestamp from a newer verified observation.
- `late` reconciles previously unbound delivery evidence that predates the current ordered Support history. No historical event is inserted or backdated.
- `withdraw` installs an explicitly reviewed unknown clock; it cannot install another receipt.

A new proposal immediately holds current reuse until its review. Latest proposal/review, actual authority, policy, receipt source head and freshness determine the current projection. No fallback to an old corrected clock follows withdrawal or staleness. Original ordered events, attestations and `first_response_at` remain historical facts. Workbench history shows these beside the separate current projection. A reviewed Support report pins the correction projection; changed evidence/review requires a successor report. Reopen metric semantics remain the original configured Support rule.

If a proposal's context changes before approval, prepare a successor under current policy/evidence. Do not edit its snapshot or reset its version. All source revisions and correction/review records have PostgreSQL guards. Case/principal locks serialize human decisions and source revocation.

## Shared operator and readiness integration

The closed `supportchannel` family lists only check ID/status/lease/fence/attempt metadata and a source link. Native source and `support.channel.read` grants apply separately from `supportresponse` grants. Cached inventories, metadata downloads, protection plans and readiness contracts recheck the original private family authority. Generic persisted agents omit both private families. Protected live channel guidance investigates correction and check status without applying decisions or creating generic agent history.

`OPS.operator_rules` can explicitly authorise `supportchannel` retry/cancel for actual D05 operators with native source/read/operate grants. `replace_intent` is forbidden. Recovery delegates to the original channel service and retains immutable intent, actor and attempt budget. Unknown reads require the case-scoped worker; committed observations reconcile before current source/runtime/readiness checks. Operators cannot cancel an observation that already exists.

Optional `INT.adapter_readiness` enrollment uses the existing `internal_postgres_session_v1` contract with `internal:supportchannel`, reviewed database credential revision, actual principal and `psl.internal-receipts/v1`. Real separate PostgreSQL health and scoped local observation lookup probes are independently reviewed. An absent local receipt proves lookup capability only. This local readiness neither proves gateway availability nor delivery meaning: `B14.channel_receipts` separately binds the authenticated gateway. Enrolled readiness gates only new reads after local receipt lookup. Readiness never approves a receipt, clock correction or customer dispatch.

Metadata export/backup/isolated restore contains job metadata and safe evidence hashes only. It does not export response bodies, customer/recipient identities, correction content, credentials or replay business jobs. Full application/database restore, native vendor contracts and operational acceptance remain separate work.
