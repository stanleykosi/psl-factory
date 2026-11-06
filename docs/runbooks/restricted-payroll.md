# Restricted payroll combination, HR matching and BU staff costs

Source-backed scope: F16 combines two owner-explained payroll exports; F17 matches exact employee identifiers and HR-owned BU membership; F18 brings reviewed component totals into BU reporting. Source values do not determine precedence, adjustments, transfer allocation, inclusion, review authority or disclosure. Those remain owner decisions.

## Local workflow

1. Collect a payroll need with entity, period, unit/currency and exactly two provider identities. Shared evidence holds scope/contract/review metadata, never employee rows or pay values.
2. In the payroll workbench draft the five typed configurations, validate and activate them in the shared policy screen. Configure actual source owners/readers and review/report recipients against current D05 principal appointments. fixtures/payroll.json is explicitly synthetic, not operational policy.
3. Each nominated source owner captures a bounded supplied JSON export. Exact contract fields, source/version/period, completeness, extraction age, decimal precision, duplicate rows and declared controls are checked. Malformed exports retain hashes and sanitised codes only. No invented native payroll API.
4. A named Finance reader prepares combination with two exact current input versions. Unknowns, control differences and overlaps without explicit treatment hold approval. Private provenance preserves source and row references. The finite methods are disjoint union, explicitly ordered provider precedence or explicit overlap sum. Adjustments use a new source version; there is no silent manual overwrite.
5. Obtain a separate current F35 HR-authorised, received read-only snapshot for payroll_matching, with only employee_id, BU and effective dates. Exact matching is case-sensitive. Whole-period or explicitly configured as-of membership is supported; multiple/missing/unknown membership holds. No inferred proration. An accepted-source mismatch can create a real HR correction reference; HR supplies a successor export.
6. Prepare F18 aggregates with configured component coefficients, rounding and minimum employee count. Inspect private included/excluded/control/BU tie-outs. Any unresolved population or protected small group holds the whole publication, including eligible totals, so totals cannot reveal a suppressed group by subtraction.
7. Configured Finance humans review exact source, combination, matching and aggregate versions independently when configured. A separate explicit publish action creates an immutable local aggregate report. A configured recipient reads/acknowledges it through the local adapter. Employee rows and group counts are excluded from this output.
8. Corrected payroll/HR sources, changed policy, revoked review/grants, freshness or retained-access expiry invalidate current use. Rebuild and re-review successors. History and exact retry receipts remain intact; a stale report is not silently restated.

## Access and evidence

Metadata boards and deterministic investigations defer private JSON. Named readers use the separate no-store input/working endpoint with fresh exact checks. A report recipient has no general employee-row access. The agent cites safe IDs/hashes/holds and drafts owner questions; it cannot read private payroll/HR values, approve, publish, appoint people, edit HR, issue payroll payments or post journals. Source text cannot grant authority.

Seven append-only record types have PostgreSQL guards; case/grant locks serialize private reads, revocation and mutation. Unique operation/version identities support retries. Local report handoff is in the same database transaction and has no remote uncertain effect. Native source authenticity/API adapters, real owner oracles/appointments, UAT, encryption/key management and physical retention purge remain separate work. Restrict-after-expiry denies access and dependent use; it is not deletion.

Finite configuration is an engineering interface, not a claim that these variants exhaust actual payroll practice. Split unsupported native schemas, multi-provider or transfer-proration variants into reviewed extensions. Never substitute zero for unknown pay or choose a staff/BU row by display name.
