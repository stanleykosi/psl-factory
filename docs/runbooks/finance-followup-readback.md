# Native Finance follow-up acknowledgement and current disposition

Engineering implementation of the incumbent internal Django/PostgreSQL contract. No vendor, bank, financial effect, production-owner appointment or operational acceptance is established.

The native Finance workbench can read back the exact metadata request exported from an actually published invoice companion. It rechecks current control permissions, complete recovered source proof, the original mapping/provider binding and physical immutable publication receipt. The original published request is retained even when subsequent financial evidence changes; readback is needed to investigate those changes. It never replays an archived job or sends a financial command.

`OPS.native_finance_readback` selects `source_finance_authority_v1`, explicit record/query/byte/time budgets, observation/review validity, exact synthetic classification and `acknowledgement_metadata_only` disclosure. Its draft/validate/activate lifecycle uses the existing policy UI. The synthetic fixture is an example, not installed policy. Missing readback criteria hold only readback and its review; ordinary invoice and source follow-up intake continue.

Native reads use the existing separately registered current Finance database, exact case registry, session and independent marker/credential binding. Each evaluation has an ephemeral unique Django connection and context-local router. The provider transaction is repeatable-read/read-only; the router rejects writes and restricts models. The source's installed policy/role/grant/expiry/job evaluator is reused, rather than approximating authority from a generic digest or remote claim. Configuration history/references and byte/query/time budgets are checked before evaluation. Connections and routing context are closed/reset on success or failure.

The registered v1 authority contract is evaluated by shared application code against current source facts. This does not attest the binary/build of a separately deployed source application; that remains deployment-owner evidence. `max_seconds` bounds each SQL statement, with `max_queries` also limiting the evaluation. Only authority-related policy references consume the record budget; unrelated Finance references cannot hold this readback. Job succession checks use invoice IDs without loading invoice document bodies.

Only opaque references, canonical hashes, verdict/status/hold codes and explicit non-executing flags leave the source evaluator. Source document bodies, owner names, notes, passwords, raw operation values and grants are not exported.

Readback distinguishes:

- `unknown`: no exact scoped request observed; no absence or failed-financial-effect proof.
- `conflict`: ambiguous or mismatched request/publication metadata; preserve history and investigate.
- `acknowledged` with `absent` disposition: the exact source request exists, without an owner decision.
- `acknowledged` with `current`: the latest exact disposition passes current source owner, grant, D05 role, policy, validity and current-intent checks.
- `acknowledged` with `revoked`, `stale` or `unavailable`: the request/history still exists, but current authority cannot be accepted; the hold code explains the source condition.

Observations and independent reviews are append-only. A source decision, permission, policy, credential, mapping or publication change can invalidate affected current acceptance. Previously captured evidence remains historical evidence. Use a new observation key for successor evidence; an old key refers to the old immutable observation, not a fresh probe. Live investigation re-reads the current provider and reports currentness separately from recorded state.

The source Finance UI continues to display its current decision status through the same evaluator. The readback agent interprets exact acknowledgement/currentness holds and offers investigation steps without effect tools. Even a currently authorised investigation/intent link neither proves a financial receipt nor authorises financial execution. Normal source invoice/correction approvals, uncertain-effect reconciliation and independent release controls still apply.

Final refinements verify the actual source case's synthetic/operational classification against the reviewed scope. The agent always describes a stale observation as historical, even if its recorded disposition once passed authority checks. RUN293 covers the connected archive workflow; RUN295 covers these final native-provider and advice refinements with source UI and configuration regression.

Separate remaining engineering includes authenticated request transport, explicit source-owned financial successor lineage, cross-identifier contracts and other-family/vendor contracts. Actual owners/grants, provider identities/credentials, deployment criteria, least privilege/TLS/SSO, owner oracles and security/load/UAT remain separate policy/deployment/evidence slots. Do not add recursive AF13 acceptance chains.
