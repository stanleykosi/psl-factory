# Native cash precondition previews

Engineering interface. Real receipt source/dimension, recorder, independence, allocation and precision rules remain versioned D14/D05 owner policy. Synthetic cash values and roles do not configure operational policy.

Select `receipt.verify` with an exact case cash report, cash-verification evidence and role. Select `receipt.allocate` with an exact verified lot, proven invoice issue, explicit amount, operation identity, allocation evidence and role. The binding form shows identifiers, not cash/source payloads. Python and PostgreSQL independently validate exact types, evidence kinds, case scope, canonical decimal syntax and operation-key syntax.

Both previews reuse native preconditions. Actual effects still lock the case and grant rows, validate evidence, current authority and financial dimensions, and preserve transaction/conservation guarantees. Preview fact resolution does not acquire effect locks and creates no cash verification or allocation. It can run in autocommit; observation is never authority to perform a future effect.

Verification requires the configured exact known statement, independent source/reporter rules and configured precision. Missing policy holds verification while report capture remains available. Allocation requires the exact current verified lot, explicit contract assignment, matching customer/contract/currency/basis, configured precision and separation, no unresolved correction or void, and capacity in both verified cash and open invoice debt. No implicit rounding or FX is introduced.

Exact native retries retain existing receipt identity. Changed operation facts are rejected; reversed history is preserved. Existing source-recovery metadata is not permission to create another lot/allocation or replay an external effect. Source heads include assignments, lots, allocations, reversals and a private position hash so reviewed packs can be reassessed after change. Amount/source bodies are not projected into guard output.

Current Finance source access precedes lookup. Independent review and A04 explain the preconditions only; they do not verify cash, allocate funds, waive debt or authorize a release. Native services enforce current controls again at execution.

BUILD-TESTS.md records actual PostgreSQL service, UI/CSRF, SQL negative/valid controls, concurrency and successor regressions. External bank/provider authentication and live owner acceptance remain separate evidence.
