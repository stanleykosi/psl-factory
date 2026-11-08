# NONAPPLIED portable D11 test snapshot

This additive backup preserves five source targets from local checkpoint `e5439c469818d0ddd731790f3321eebe490bad63`, based on `773ad4964dc163ce0c5c008057ca6a131a8918bb`. It does not change active product code, any earlier snapshot, or main.

Reconstruct the prior inert803-402b599 and inert803-d11-773ad49 snapshots in a separate candidate first. Then copy each `files/<target>.source` to the target path listed in MANIFEST.json after verifying SHA256 and Git blob identities. These are complete replacements/additions, not executable installation instructions. Production source is unchanged by this increment.

The five targets include a test-only pre-change `validate_envelope` function fixture, its provenance and four mapping hashes, the portable regression test, and design documentation. The fixture is only that independently reviewed function, not the complete services module. No private full-source proof or runtime evidence is included.

The reconstructed pure component suite supports 12 tests with standard-library fake imports, without Django or a database: `python -B -m unittest tests.test_d11_dispatch_isolation_component`, also with `-O`. This is source regression coverage only, not native database, application startup, provider, performance, or full milestone acceptance. The earlier D11 dispatch default-behavior change remains nonapplied to the active public source. Native acceptance remains NOT_MET.

Runtime databases, raw proof, private artifacts, environment installation plans, credentials, held operations, and unrelated newer work are excluded. This is not a complete restoration of the lost runtime environment or original source history.
