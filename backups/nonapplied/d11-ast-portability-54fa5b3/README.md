# NONAPPLIED D11 AST-format portability fix

This additive test-source snapshot preserves checkpoint `54fa5b39daa5825b11a4d8398385a40ac257f042`. Only `tests/test_d11_dispatch_isolation_component.py` changed. Product source and existing frozen expected hashes are unchanged.

Reconstruct the previous inert803, D11, portable-fixture and runtime-contract snapshot chain in an isolated candidate first. Verify MANIFEST.json and replace the indicated test target with its complete `.source` copy. No active repository source or main is changed by this backup.

The test normalizes AST dump formatting across Python 3.12 and 3.13 by selecting `show_empty=True` when supported. This fixes the earlier portable snapshot's Python 3.13 AST formatting mismatch without changing its original expected integrity hashes. The current selected 97 pure tests passed normally and with optimization after independent review. That is pure source-test coverage, not database/application/provider/deployment acceptance or a claim that all tests were run.

The test still requires the reviewed public function fixture and mapping hashes from the prior portable snapshot. No private full-source proof, failed-run evidence, runtime database, credentials, environment installer, held operations or other source changes are included. Native acceptance remains NOT_MET. Previous snapshots remain intact.
