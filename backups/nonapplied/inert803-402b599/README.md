# NONAPPLIED inert803 source snapshot

This directory preserves frozen source commit `402b59930572c1b1d12ed7916889e3e0f0e8e62d` relative to `8aaaecc7752543bc78cf3afdfce621b3c70cfebc`. It is a backup, not an active integration, deployment, native test pass or completed feature. **Native acceptance remains NOT_MET.** No product files outside this namespace are changed by adding this snapshot.

## Contents and restoration boundary

The manifest covers84 original source/test/design paths:73 complete new files under `files/`, plus11 zero-context patches under `patches/`. Complete source copies use the inert `.source` suffix, preventing normal Python test discovery/import from treating this backup as active code. The suffix is not part of the original filename. Each entry records the original mode/path, base and target Git blob hashes, SHA256 hashes and exact byte lengths. Snapshot storage files use mode100644.

The11 patches contain only reviewed changed lines, not unrelated unchanged baseline bodies. Their base blobs exactly match both the accepted main checkpoint0b2820ea and public backupf77f2f0. Reconstruction was verified in memory against each exact base blob, including CRLF/LF fidelity, and every resulting target matched the frozen Git object and SHA256. No reconstructed existing file was saved into active source. Restoring requires those exact base blobs; mismatched bases must stop restoration. Apply only in a separately authorized isolated worktree using a tool that supports zero-context patches, then verify all manifest target hashes and original modes. Do not apply this backup automatically to the working branch.

## Scope and limitations

This source work includes template owner/scope/source privacy preparation, permission and resource-accounting components, and associated tests/design notes. It is not all opt-in: the patch to `apps/policy/services.py` includes the reviewed default resolver streaming change. Therefore even a clean patch application is not sufficient evidence for product integration. Full composition, native database behavior, concurrency and adapter equivalence remain separately gated. The preserved native public-evidence predicate has global JSON expansion/cast work: bounded returned IDs are not a bound on database work.

One test file contains a deliberately synthetic password literal used to create a bootstrap user inside a Django TransactionTestCase after asserting a synthetic case. It is a test fixture, not a live account credential. No live login or credential use is included. Pattern screening found that documented fixture occurrence; it is not a repository-wide security audit or proof that all possible secret formats were detected.

Excluded: runtime databases, raw evidence/logs/screenshots, five divergent BUILD/HANDOFF records, newer or uncommitted source, and unrelated baseline implementations. Existing held performance/F08/conversion restrictions, browser exclusions and provider/security boundaries remain unchanged. Publishing this snapshot does not authorize any held action or signify acceptance of unfinished work.
