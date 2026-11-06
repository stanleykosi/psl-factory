# Selected statement convention conversion

This is a bounded engineering interface for F08/F09, not an owner accounting policy, whole-SOCE certification or a complete financial statement. Only exact same-case native formula outputs are accepted. PPE ScheduleWork and other producer types remain outside this increment.

## Configure and review

Use the existing Finance policy draft UI and policy activation lifecycle. Both new components use existing native `formula` review purpose and configured Finance role/action/preparer rules. No approver or independence rule is added.

1. `D06.producer_conventions`, schema `schema:psl/producer-conventions/v1`, holds `declarations`. Each has a unique `key`, exact `source_run`, `operation_key`, `source_review`, `metric`, `unit`, `convention` identifier and same-case `finance_review` `evidence_id`. The output review must identify this formula result. This declaration is a human-reviewed producer assertion; signs are never inferred from a coefficient or from the amount.
2. `D06.statement_conversions`, schema `schema:psl/statement-conversions/v1`, holds `declarations`. Each has a unique `key`, exact `from_convention`, `to_convention`, same `unit`, `operation`, string `factor`, decision `evidence_id`, `oracle_evidence_id` and four `oracles`. Allowed operation/factor pairs are `identity`/`1` and `reverse_sign`/`-1`. Identity retains the exact identifier; reversal requires distinct identifiers. Scaling and currency conversion are excluded.
3. Each oracle has `kind`, decimal-string-or-null `input`, and `expected`. Exactly one positive, negative, zero and unknown example is required. Values must agree with the factor; unknown must remain null. The largest supported decimal values are validated with the same exact operation as runtime, without context rounding. Duplicate producer identities cannot carry conflicting convention declarations. The entire example list must exactly match the cited same-case `finance_oracle` evidence body.
4. `D06.statement_contract` selects v2 by `convention_mode: producer_verified`. Each existing selected-line input also names `producer_contract_id`, `producer_key`, `conversion_contract_id`, `conversion_key`. Its `source_sign`, `destination_sign`, `unit` and `transfer` must exactly match the reviewed declarations. Null declaration selectors hold the statement, never mapping, allocation or base-output review. Missing/stale/revoked configurations prevent the dependent statement transition.

The owner-selected statement oracle still enumerates exactly the chosen destinations. Existing v1 identity contracts continue as legacy consumer declarations. The UI explicitly states that they are not producer-verified. A v1 mismatch never performs conversion.

## Execution and recovery

One declared identity or sign-reversal operation occurs only at the selected statement boundary. Original formula values, expression coefficients, subtraction, scaling and `rules.evaluate` are unchanged. The statement snapshot pins both configuration revisions, exact declaration bodies, native reviews, original amount, presented amount and one application. Immutable relational input rows retain the selected source/run/output-review inventory. Rebuilding uses original formula producers and cannot treat a presented statement as another formula source.

Current-use checks repeat the same deterministic boundary calculation and compare the complete snapshot/result. Stale, superseded, revoked or newly reviewed declarations invalidate old snapshots. Native PostgreSQL factory verification and publication guards add exact conversion checks while preserving predecessor guards. Both legacy v1 and producer-verified v2 statements also recheck exact contract, source and statement-output review authority: active human, Finance review grant, current role assignment and eligibility, the configured Finance matrix entry and its preparer rule. Unrelated matrix namespaces do not create new review requirements. New output reviews cannot reauthorize an older document binding. Queued publication rechecks current eligibility. Already committed receipts remain historical facts and are reconciled through existing recovery, never silently resent.

Agents can investigate the selected evidence and findings using their existing bounded tools. They do not receive approval tools or authority from declarations. Recipient documents remain aggregate projections, not private convention/evidence inventories.

## Acceptance limits

Synthetic tests cover F08-N01 (-500 displayed as +500 once), F08-E01 (no second conversion/reinterpretation), F08-N02 (-SUM(-5000)/1000 remains +5), valid subtraction, identity, unknown/zero/positive boundary behavior, finite factors, exact operation/review/metric/unit/convention pins, actual oracle validation, authority, staleness and native receipts. Test status is recorded in BUILD-TESTS.md; this runbook itself is not a pass claim. There are no live services, owner rules or new whole-process acceptance claims.
