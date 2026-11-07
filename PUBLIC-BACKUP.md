# Public source backup

This source-only development update adds 25 accepted implementation, test and fixture/helper files from frozen local checkpoint `4d5074cb1755061b7bea9adbcccb32565b70e1d8` to prior public backup `c5a5156`. It is not a release, deployment or main-branch merge.

## Included changes

The draft-generation worker now refuses execution inside an enclosing transaction or with autocommit disabled, so its claim is durable before provider transport. Focused tests cover both rejection paths and ordinary execution/reconciliation. Invoice-related test fixtures explicitly supply synthetic obligation identities rather than bypassing the new identity contract. The test-only process-crash helper checks its exact isolated database target and synthetic job before running.

## Verification boundary

The accepted selected native regression comprises 77 tests verified across split runs, not a single uninterrupted full-suite run. A separate 18-test native selection for the draft-generation safeguard and related contrasts was accepted. These selected results do not establish full 108-process acceptance or all caller compatibility. Older public runbooks and checkpoint notes can describe earlier verification states; this note records the boundary for this source snapshot.

Newer pending cold-recovery work is excluded and no cold-recovery success is claimed. Browser testing remains excluded by user direction; restricted security/performance work remains held. Real provider setup, operational credentials/accounts, owner policies and source mapping remain separate. The only-owner-inputs-remain readiness gate remains NOT_MET. No hosted CI result is claimed.

## Publication boundary

Only the 25 reviewed source/test/helper files and this sanitized note change. Private BUILD/HANDOFF status, coverage/acceptance coordination records, runtime wrappers, raw proof, logs, screenshots, archives, newer pending changes and local Git history are excluded. All other public blobs and the existing evidence subtree are preserved. Main is unchanged; no deployment or live service action is performed.
