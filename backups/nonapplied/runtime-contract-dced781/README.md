# NONAPPLIED intended runtime contract

This isolated additive source snapshot preserves `.python-version`, one pure component test, and a zero-context README append from checkpoint `dced7819eb736fefd2a672012af2c30128b433cf`. It does not apply a runtime change to active public source or modify main.

Reconstruct the earlier inert803, D11 and portable-test snapshots in a separate candidate, verify the target/base hashes in MANIFEST.json, copy the two `.source` files to their target paths, and apply the README patch preserving original CRLF bytes. The README patch contains only the added runtime guidance, not unrelated existing contents.

Python 3.13 is the intended interpreter line for the audited pinned dependency closure. This is not a claim that dependencies installed successfully, that the current host satisfies the application contract, or that native startup/database tests passed. Four standard-library component tests passed normally and with optimization on the source checkpoint; these are static runtime-contract checks only. Existing entry points, settings and lockfile are unchanged.

No production server, Railway installation/account/configuration/deployment, secret, database, automatic migration, hosting readiness, raw runtime proof, held operation, or private evidence is included. Native application acceptance remains NOT_MET. Prior default-behavior changes remain solely in nonapplied snapshots.
