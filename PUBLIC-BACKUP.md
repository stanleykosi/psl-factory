# Public source backup

This is an incomplete source-only development checkpoint, not a release, deployment, main-branch integration or full native acceptance. This update preserves 33 implementation, configuration, template, test/fixture and operator-runbook files from frozen source `858bf8e0e33d17d4da4327c25fccb5ca9fe498dc`, on top of backup `3896f2b`.

## Scope and verification

The checkpoint includes optional direct QBO application linkage, the optional hosted QuickBooks MCP read broker and commands, readiness/factory connections, initial invoice-identity fixture compatibility and the F32 correction, plus native invoice adapter checks against exact source and delivery hashes. Earlier cross-case identity source and the optional QBO component remain present.

Native testing has 46 individually passed tests across partial runs. Four selected tests, including the new adapter contrast, remain pending. The overall 50-test native selection is NOT accepted. Individual successes are not a complete current-head regression. This note supersedes older verification-status prose retained in the source runbooks; those documents may describe earlier component checkpoints.

No real provider acceptance, operational account, credential, source mapping or owner policy has been established. Tests use synthetic/provider-mocked inputs where specified. Browser testing remains excluded by user direction; restricted security/performance work remains held. Full 108-process acceptance and the only-owner-inputs-remain readiness gate remain NOT_MET. No hosted CI result is claimed.

## Publication boundary

Only the 33 reviewed source/runbook files and this note change. Newer unreviewed compatibility branches, private BUILD/HANDOFF status, runtime harnesses, coordination manifests, raw proof, screenshots, runtime data, secrets and local Git history are excluded. All other public blobs, including the existing evidence subtree, remain unchanged. Main is unchanged; no merge or deployment is performed.
