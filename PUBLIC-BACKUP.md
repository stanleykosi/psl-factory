# Public source backup

This is a source-only development backup, not a release or deployment. This update adds the four reviewed registry-validation source, test and runbook files from accepted snapshot `f09e0ec` to the previously published runtime snapshot `9236b7b`.

## Verification status

The offline integration registry now uses explicit validation that remains active under optimized Python, rejects malformed or duplicate JSON references and unsafe origins, and provides an offline reference-only preflight. Finance sender credential binding uses the same explicit validation. Eight synthetic component tests passed under both normal and optimized Python. The Finance credential function was tested in isolation; this is not full ORM/HTTP workflow regression or live-provider acceptance.

The earlier permitted selected regression covered 461 unique test IDs across 95 accepted batches, executed on `c212331` (165), `3f3a1ed` (115), and `9236b7b` (181), with source/helper equivalence verified for the earlier 280 IDs. It does not cover this new delta and was not a single latest-snapshot run. No hosted CI result is claimed.

Full 108-process acceptance and the only-owner-inputs-remain readiness gate remain NOT_MET. Cross-case invoice identity work is not included or accepted here. Browser verification remains unverified and is outside the current requested testing scope. Operational provider selection, configuration and integration acceptance remain separate.

## Publication boundary

Only `config/integration_runtime.py`, `apps/finance/followup_intake.py`, `tests/test_integration_runtime.py`, `docs/runbooks/integration-readiness.md` and this note change. All other public blobs, including existing evidence, remain unchanged and may describe earlier checkpoints. No raw proof, private status files, runtime data, screenshots, secrets, private operational data or local Git history is published. Main is unchanged. No merge or deployment is performed.
