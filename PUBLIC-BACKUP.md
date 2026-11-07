# Public source backup

This source-only development update preserves 29 accepted implementation, test and fixture/helper files from frozen checkpoint `4b3191f9be35dfcf70983a86f3b975cb128510b1` on top of public backup `b06e8ae`. It is not a release, deployment or main-branch merge.

## Included changes

Invoice delivery pins canonical local adapter callables and requires an outer autocommit boundary for custom adapters before claiming work or contacting a provider. Related synthetic fixtures explicitly establish invoice identity and refresh the real review packet. QuickBooks MCP rejects decoded responses containing the exact current bearer secret, including object keys; it does not claim detection of arbitrary encodings. Direct QBO transport uses bounded chunk reads with a monotonic body budget, not a strict end-to-end DNS/TLS/header deadline.

## Verification boundary

Accepted bounded provider verification covers 35 selected tests. Invoice verification covers 63 selected tests across split runs, not one uninterrupted full-suite execution. These results support the reviewed increments only; they do not establish full 108-process acceptance, all caller compatibility, live provider operation or the only-owner-inputs-remain readiness gate. Older public documents may describe earlier checkpoints. No hosted CI result is claimed.

Browser testing remains excluded by user direction. Restricted security/performance work remains held. Pending cold-recovery work and the separate historical test-organization repair are excluded. Real provider setup, accounts, credentials, source mappings and owner policy choices remain separate; none is invented or enabled by this backup.

## Publication boundary

Only the 29 reviewed source/test/helper files and this sanitized note change. Runtime wrapper checks, harnesses, raw proof, logs, screenshots, archives, private coordination and local Git history are excluded. All other public blobs and the existing evidence subtree remain unchanged. Main is unchanged. No deployment or live service action is performed.
