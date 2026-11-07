# Public source backup

This is a source-only development backup, not a release or deployment. This update adds the separately accepted optional QuickBooks Online pure component checkpoint `980ce3c` on top of registry-validation backup `15ae0c7`. It does not represent integration of that component into the main application workflow.

## Verification status

The optional Invoice-only exact-ID read component uses fixed QBO origins, GET-only bounded transport, explicit binding validation and immutable minimal observations. Registry entries are optional; no operational provider, account, credential or source mapping has been selected. Eighteen distinct synthetic component tests passed under both normal and optimized Python. These include the existing eight registry tests and ten QBO component tests, not 18 additional tests beyond the registry suite.

F01 application linkage, native database authorization/persistence/concurrency verification and live-provider acceptance are not established by this component. Newer application-linkage work is excluded from this snapshot. Cross-case invoice identity work remains excluded and unaccepted here.

The earlier permitted selected regression covered 461 unique test IDs across 95 accepted batches, executed on `c212331` (165), `3f3a1ed` (115), and `9236b7b` (181), with source/helper equivalence verified for the earlier 280 IDs. It does not cover this component delta and was not a single latest-snapshot run. No hosted CI result is claimed.

Full 108-process acceptance and the only-owner-inputs-remain readiness gate remain NOT_MET. Browser verification remains unverified and outside current requested testing scope. Operational provider selection, configuration and integration acceptance remain separate.

## Publication boundary

Only `adapters/quickbooks_online.py`, `config/integration_runtime.py`, `tests/test_quickbooks_online.py`, `docs/runbooks/quickbooks-lineage.md` and this note change. All other public blobs, including existing evidence, remain unchanged and may describe earlier checkpoints. No raw proof, private status files, runtime data, screenshots, secrets, private operational data or local Git history is published. Main is unchanged. No merge or deployment is performed.
