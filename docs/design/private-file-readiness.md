# Native private metadata export and file backup readiness

Status: historical engineering proposal, subsequently implemented/tested as BUILD-PRIVATE-FILE-READINESS. See docs/runbooks/private-file-readiness.md and the actual RUN229–232 evidence. The proposal below is preserved for design context, not business policy; actual implementation distinguishes SQL export artifacts from sealed file bytes. All 122 process statuses remain partial.

## Existing implementation to reuse

`apps/workflows/operator_delivery.py` reserves immutable export/backup/restore intents and uses fenced durable execution with receipt-first recovery. `adapters/operator_protection.py` writes sealed metadata files and reads exact existing file receipts; isolated PostgreSQL restore is a different effect. `private_readiness_operations.py` enforces selected accepted metadata scope and original source grants. Existing source-authorised operator diagnostics already cover these jobs.

`private_protection_readiness.py` and its native adapter currently bind **restore** jobs to health/receipt observations. `documents.PrivateProtectionPacket` and its SQL lineage explicitly describe native restore capability. Those contracts must not silently relabel export/file backup proof as restore evidence.

## Next connected increment

1. Inspect the actual export/backup intent, artifact, file receipt and readiness contracts before choosing a forward-compatible binding/model change. Preserve applied migrations and historical snapshot schemas. Reuse shared readiness workers, observations, independent review and operator recovery.
2. Capture an exact native export or backup job, plan, source packet inventory, immutable intent/manifest hashes and storage identity. Bind private source history before any private receipt projection. Public/general contracts must not persist private provenance. Capture may precede missing readiness configuration; dependent probes, review and enrollment require it.
3. Add a closed native adapter. A health result should describe the precise local storage capability tested, without claiming password authentication, provider authenticity or full recovery. A receipt lookup must verify the original job's actual sealed bytes/manifest and receipt lineage. Return only IDs, hashes, kind, capability classification and found/not_found state; exclude source quotes, file paths, manifests, credentials and financial payloads.
4. Extend typed/versioned configuration only after reviewing the existing independent private readiness component. Require exact job inventory, actual principals/D05 purposes/source grants, independent review, freshness and attempts/lease criteria. Configuration changes must have explicit consequences for existing assessment/acceptance pins. Do not introduce a self-dependency by exporting an accepted packet whose acceptance depends on the readiness policy being replaced. Do not invent policy values or appoint real people.
5. Connect source-filtered UI, draft/validate/activate/history screens, bounded live investigation and typed contract preparation. Agents may investigate and prepare; human review and domain services retain authority over probes, enrollment and effects. Historical source access and current-use readiness are separate checks.
6. Test with real PostgreSQL and temporary native files: actual export/backup bytes, found/not_found, missing/corrupt/conflicting bytes, private/public boundaries, source and owner revocation, policy revision/expiry, exact lineage, duplicate capture/probe requests, competing workers, foreign-source revocation races and fresh-process receipt reconciliation. Mock upstream providers only. Never reset old receipts, main data or unrelated jobs.

## Acceptance evidence and limits

Keep the original selected F01/B13/P13/P15 process IDs/titles and original Finance source approval. New file capability proof needs its own explicit native scope before it can enter AF13 acceptance. Existing restore acceptance must retain its historical meaning. A successful file check is neither full application/database recovery nor business/operational acceptance. Actual owner/provider/SOP evidence, production identities/security and full recovery/load/UAT remain separate work.

Record exact executed commands, failed and successful outcomes, source fingerprints, SQL guards and main-data preservation before marking the new increment verified. Update BUILD-STATE.md, BUILD-BACKLOG.json, BUILD-TESTS.md, BUILD-LOG.md, BUILD-DECISIONS.md and HANDOFF.md; keep engineering gaps distinct from owner-supplied policy inputs.
