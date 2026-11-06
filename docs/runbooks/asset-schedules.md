# Assets, depreciation and Finance note references

Source-backed boundary: F07 names the asset/depreciation schedule and Notes8–9 but supplies no asset register, capitalization threshold, useful-life table, method, start/stop convention, disposal policy or numerical oracle. The reported March label in a September workbook is an unresolved date/basis question, not proof of an error. Preserve both dates. The implementation and fixtures below are proposed engineering behavior and synthetic evidence, not installed PSL accounting policy.

## Connected workflow

Open `/cases/<case-id>/finance/assets/` with explicit case.read, finance.read and ppe.read grants. Capture bounded ppe_register JSON evidence with the typed shape in fixtures/ppe.json. Capture works before calculation/source policy or review authority is configured. It stores immutable facts, original label/reporting/extraction dates, declared population coverage, asset opening balances/classification evidence and signed event references. Duplicate asset/event IDs, unknown authority fields, nonfinite/out-of-budget amounts, future/invalid dates and out-of-period or absent-asset events are rejected. Unknown amounts remain null.

An actual configured Finance human reviews the precise register, including source classification, life/residual/fraction and event evidence. This is not inferred from a source label. Date/basis explanation is a separate configured purpose with ppe_basis_explanation evidence and a human note. It may explain a legitimate roll-forward without altering the original label. Unexplained mismatches prevent output acceptance while source collection and rule preparation continue.

## Typed policies

- F07.source_rules: entity/provider/currency/unit/effective periods, freshness, external-opening/prior requirement, optional exact bootstrap period, ledger-note requirement/line/sign/tolerance and Finance-local versus required AF13 method-definition acceptance. No default source contract or accounting authority is installed.
- F07.calculation_rules: exact category, method evidence, opening/closing cost basis, capitalization threshold/below-threshold handling, supplied fraction convention, residual-cap behavior, precision/rounding and known/unknown or held numerical oracles. Configured unsupported methods explicitly require engineering; entering a method name does not create an executable algorithm.
- F07.review_authority: actual active Finance principals by register, basis and schedule purpose, with explicit reviewer independence. D05 actual role assignment, current action grants and case scope still apply.

Use the existing draft -> validate -> activate workbench. Numerical oracles are checked against the selected finite implementation before activation. Synthetic fixture values are scoped to synthetic cases and cannot become operational fallback values.

## Finite calculation contract

`straight_line_explicit_fraction_v1` calculates `(configured opening or closing cost - supplied residual) / supplied life units * supplied period fraction`, with explicitly configured precision/rounding and remaining-value hold/cap. The life and fraction are source facts under exact register review; the code derives no calendar proration, useful life, start/stop date or rate. Different methods require a reviewed implementation. `unimplemented_method` retains a precise row hold instead of estimating a result.

Signed events roll forward cost and accumulated balances. Additions use nonnegative supplied cost and explicit zero accumulated movement; disposals use supplied nonpositive balances. Reclassifications must conserve cost and accumulated balances across the selected population. Broader gain/loss, impairment, tax, multi-currency and asset-event conventions remain engineering work. This is a reference schedule, not an authoritative asset master or posting engine.

Each row retains event IDs, the chosen category and individual holds. Unknown life/classification/movements, invalid basis, unsupported methods, below-threshold holds and over-depreciation prevent the dependent row from producing a charge. Other rows can still be calculated. Aggregates remain unknown if a required row is unknown. Explicit closing controls must reconcile within the supplied tolerance before a schedule is approved.

When a prior schedule is supplied, it must remain current and human-approved, have the exact entity/provider/currency/unit, and end immediately before the new period starts. Opening cost/accumulated balances match prior closing values numerically; missing previous assets are not silently dropped. New assets need explicit zero opening and addition evidence. `prior_required` can permit an explicitly configured bootstrap period; no previous period or external-opening exception is guessed. New periods require distinct stable source/output references, while corrections within a period create reviewed successors. The bounded prior chain supports36 links.

An optional or required exact existing Finance mapping run reconciles the selected signed note line to PPE closing book value, using the explicit sign coefficient and tolerance. Source scope/unit/period, source acceptance and existing Finance configuration reviews must still be certifiable. The approved output retains the Finance mapping ID/hash as its read-only F06/F09 note reference. It neither injects amounts into a statement nor posts to QuickBooks. Native statement/workbook equivalence remains unverified.

## AF13 and current use

Source policy can require an AF13 F07 definition or synthetic-implementation acceptance package. Current meaning/normal-and-exception expectations/acceptance must cover the configured method evidence. Required acceptance missing or revoked holds schedule approval; calculation candidates and source collection remain available. Definition acceptance and supplied comparisons are distinct from native execution. AF13 still prevents operational acceptance without verified native execution adapters.

Case/grant locks serialize source correction, schedule preparation, human review and report read. Source versions, exact reviews, basis decisions, prior outputs, effective policies, actor access, freshness and Finance inputs are checked again on controlled use. Supersession, revocation or a changed calculation requires a successor. Historical evidence/reviews/amounts are never rewritten. Reused ScheduleWork/ScheduleReview records retain their existing PostgreSQL append-only guards; migration0037 extends the parent-kind check for PPE. Legacy F12/F13 surfaces and services explicitly reject PPE work IDs.

## UI, agents and adapters

The server-rendered workbench provides permitted typed capture, preparation, policy and decision commands; original dates, current/historical review state, row holds, controls and reviewed Finance note references are visible. Human reports and explicit JSON equivalents use no-store and require ppe.report. Read-only viewers receive no decision grant. The supplied JSON adapter executes no workbook or external write. The local reviewed-report adapter checks current record/action authority inside a transaction.

The bounded deterministic investigator selects at most40 reference/status/gap records and drafts evidence, event, method, date and reconciliation questions. It selects no numerical asset fields, approves nothing and makes no real-provider evaluation claim.

## Remaining engineering versus owner inputs

Engineering: verified native register/accounting/workbook adapters and authenticity; more depreciation/event/period conventions, gain/loss and impairment handling; native F06/F09 statement bindings; source-specific AF13 implementation/native replay; remote controlled delivery and operational restore/export/load/UAT. These are not merely values to enter into a form.

Owner inputs: actual register/opening/events, capitalization and exception policy, method/cost basis/lives/residual/start-stop/fractions, precision/caps, actual reviewers/authority, source and note reconciliation contracts, date explanations and genuine numerical acceptance oracles. Synthetic fixtures and local tests establish none of these operational facts.
