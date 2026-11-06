# Finance mapping, formula lineage and BU allocation

This is an implemented local subset, with proposed engineering interfaces. Actual source responsibilities remain in the process contracts. Synthetic examples in `fixtures/finance-analysis.json` are tests, never accounting policy or operational authority.

Open `/cases/<case UUID>/finance/` in an explicitly provisioned case. Record/action grants are required: `finance.read`, `finance.import`, `finance.validate`, `finance.source`, `finance.calculate`, `finance.adjust`, `finance.review`, `finance.publish`, `agent.finance`; ordinary evidence, policy and controlled-document permissions are separate. Administrator flags do not supply authority.

1. Register supplied CSV as `financial_input` evidence. Capture the immutable import, then declare entity, actual accounting basis, aware extraction time, complete/partial/unknown inventory and optional source total with `finance_source` evidence. Capture remains available without mappings or review authority. The adapter reparses the exact captured CSV and verifies its hash/rows; it does not authenticate QuickBooks.
2. Save owner-backed configuration drafts in the Finance screen, then validate and activate in the policy screen. The draft form captures immutable hashed references and typed envelopes. Replace every placeholder evidence ID with an actual scoped source. A draft is not active policy.
3. Obtain configured source/rule reviews. Independently configure each Finance purpose in D05. Preparer review is allowed only if its required boolean explicitly permits it. A role name is insufficient: actual current principal assignment and record/action grants are checked. Previews can run before human review; output review/publication requires applicable current reviews.
4. Build the exact mapping preview, optionally selecting current approved reporting adjustments. Missing accounts, amount, currency or period remain explicit findings/unknowns. Approved adjustments are overlays with their own immutable revisions and sources; no ledger is mutated.
5. Select an explicit BU metric scope and build allocation. Direct rows need an effective BU catalogue; fixed pools need explicit weights, rounding and residual treatment. Headcount pools additionally need a separately authorized complete membership snapshot and join/period semantics. Missing HR rules hold only dependent pools. Source, allocated, unallocated, residual and company-only amounts remain separate and conserved.
6. Calculate configured formula metrics. Only the registered finite `linear_decimal_v1` implementation runs: explicit coefficients, bounded acyclic dependencies, rounded/unrounded operand stage, one-time scaling, rounding and owner-cited known/unknown oracle scenarios. No uploaded executable formulas or inferred IFERROR zero.
7. Review the exact complete output under configured Finance authority. Source completeness, required control total and explicit tolerance, and company/BU comparison tolerance are checked. Prepare an aggregate report, inspect it in controlled documents and reserve local publication. The publication worker checks current source/rules/reviews/publisher/recipient grants again, then creates exact local inbox receipts. Changed facts hold queued effects; receipts already created reconcile before retry.

## Versioned configuration interfaces

| Component | Reference schema | Explicit content |
|---|---|---|
| D05.decision_action_matrix | decision-actions/v3 | Existing namespaces plus independent Finance source/mapping/formula/allocation/adjustment/output purpose, role, verdict actions and allow_preparer_review |
| D06.source_schema_ref | controlled-csv/v1 | Controlled account/amount/currency/period CSV columns |
| D06.unit_sign_currency_period | source-conventions/v2 | Currency, major currency unit, period, sign convention, required-source-total flag and explicit source/BU tolerances; v1 remains preview-compatible |
| D06.account_bu_maps | finance-account-map/v1 | Entity/effective periods, exact account, report line/metric, company/direct/pool route and duplicate-row handling |
| D06.rule_oracle_refs | finance-formula/v1 | Named finite implementation, operands/coefficient/stage, divisor/unit/rounding, scope and exact immutable oracle evidence/scenarios |
| D10.report_category_effective_dates | finance-bu/v1 | Effective entity BU identifiers and names |
| D07.allocation_pool_rules | finance-pool/v1 | Effective pool/category, fixed or headcount method, weights, BU/account exclusions |
| D07.rounding_residual_rule_id | finance-rounding/v1 | Precision, rounding, held residual or exact eligible destination, reject excess source precision |
| D07.authorized_input_refs | finance-authorized-basis/v1 | Exact HR/Finance basis evidence, entity, period and purpose |
| D07.join_overlap_rule_id | finance-basis-join/v1 | Single effective snapshot, subject identifier, duplicate rejection, as-of period, unit headcount or explicit FTE |
| D07.effective_membership_ref | finance-membership/v1 | Exact cited structured snapshot, entity/period/as-of/completeness and opaque subject/BU/nullable weights |
| D10.audience_projection_rules | finance-projection/v1 | Aggregate-only internal/management projection, exact metric/BU selection and current publisher roles |

Array components take one reference per object; string/artifact components take a single reference. Numeric values are exact finite bounded decimal strings. Operational policy references cannot borrow synthetic evidence. Oracle execution checks internal consistency against cited scenarios, not genuine original-workbook equivalence or external authenticity.

Finance report templates use `document_type: finance_report`, sections `executive_summary`, `financial_metrics`, `bu_totals`, and explicit `internal_review_required:false`. The configured Finance output review supplies the domain decision. A separate PMO approval is not invented. Unbound finance reports cannot publish. Recipient projection contains aggregate values only; raw import and individual basis rows stay out of it and the bounded diagnostic agent.

Run `python manage.py seed_finance_analysis_demo` once with the existing demo actor to provision an isolated synthetic example through real services. It leaves output review/publication for the UI and refuses overwrite. Run `python manage.py work_publications --limit 1` for local delivery. Test with `python manage.py test tests.test_finance_analysis tests.test_finance_analysis_workers --keepdb --noinput`; never run concurrent test commands against test_psl.

Remaining engineering includes original workbook/native source providers, depreciation, actual payroll merge/HR joins and exceptional executive allocation, budget/prior-period/YTD/restatement/charts, genuine transaction-level attribution, billing, receipts/allocations/corrections and forecast. QuickBooks posting, external authenticity, HR mutation, financial close and money movement are outside this implemented path. Actual owner values and provider evaluations remain separate readiness work.
