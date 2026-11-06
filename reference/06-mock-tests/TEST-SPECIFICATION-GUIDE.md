# How to use the mock-test catalogue

## Current status

This is a test specification, not a software test run. No PSL application has been built or deployed as part of this documentation task. All examples are fictional and must remain isolated from production data and external recipients.

## Required fields for a future executable case

1. Stable test ID and related original process IDs.
2. Source-derived rule or explicitly proposed technical safeguard.
3. Preconditions: version, role, lifecycle state, referenced evidence and any approved test assumptions.
4. Synthetic input and action.
5. Expected observable result, including forbidden side effects.
6. Evidence/assertion to collect and reset procedure.
7. Business decision blocking the case, if any.

Departmental JSON tests supply the scenario, expected result and basis. Before execution, resolve their business decisions and add concrete fixture/role/version values without changing the intended rule. A vague expected result such as “works” or “correct” is insufficient.

## Cross-process proposed safety cases

- **X01 Wrong role:** a user without the required role attempts an approval or restricted read. Expected: denied, no state change or sensitive-data disclosure, auditable denial.
- **X02 Changed evidence:** a previously reviewed subject is revised. Expected: earlier decision remains attached to the earlier version; handling of the revised version follows the confirmed revision policy. Do not assume every harmless edit requires every approval again.
- **X03 Duplicate handoff:** replay an identical event. Expected: one business effect, traceable repeated attempts.
- **X04 Unknown outcome:** a timeout follows possible destination acceptance. Expected: unresolved state and receipt reconciliation before replay, not blind duplication.
- **X05 Restart recovery:** restart after a queued event but before confirmed receipt. Expected: recover outstanding item without losing evidence or creating a duplicate effect.
- **X06 Out-of-order input:** milestone completion arrives before its baseline. Expected: held for reconciliation, no invented linkage or downstream accounting action.
- **X07 Missing mapping/rate:** absent Finance rule/input. Expected: explicit exception, not zero, default rate, guessed BU or balancing plug.
- **X08 Restricted export:** an internal report contains payroll/commercial/internal issue details. Expected: external version follows an approved allowed-field and review policy; no raw internal copy is sent.
- **X09 Unresolved emergency policy:** an emergency change requests an assumed GLPI bypass. Expected: no invented waiver; route remains explicitly blocked pending the authority decision.
- **X10 Notification sink:** every notification in mock mode targets an internal fake sink. Expected: zero real email, client message, invoice posting, transfer, live project update or deployment.
- **X11 Source drift:** a source file or rule version changes. Expected: identify affected definitions/results and require deliberate revalidation; do not silently rewrite the immutable baseline.
- **X12 Recovery copy:** extract release archive into an empty directory and recompute all manifest hashes. Expected: exact paths and bytes match; missing or changed files are reported. This is documentation recovery, not an application restore test.

## Important negative expectations from the PMO source

Do not add deposit/paid-invoice gates to Planning; a separate business-acceptance gate to post-release go-live; a separate operational handover approval to P37; a bid/no-bid gate to P45; a separate issue-closure approval to P50; approval to classify P56; or an assumed Emergency GLPI waiver. Tests should detect these invented requirements as well as missing legitimate controls.

## What mock success would not prove

It would not validate live credentials or integrations, actual Finance calculations, real signature authority, complete source data, accepted hosting/licensing, production load, legal/accounting policy or practical owner acceptance. Record those verification dimensions separately.

## Additional source-reconciliation cases for v0.2

These are proposed synthetic mock specifications, not executed tests or approved accounting policy. Each requires an owner-supplied expected result before implementation acceptance.

- X13 Unit/sign provenance: a fixture explicitly declares 2,000 base units and a divide-by-1,000 presentation mapping. Expect 2 displayed units, with source unit and mapping version retained; reject an undeclared scale change. This verifies only the supplied fixture, not a universal PSL convention. Related F05/F06/F08/F12/F15.
- X14 Allocation rule absent: a staff-cost batch has no effective-dated approved allocation basis. Expect an unresolved allocation exception, not adoption of spoken sample ratios or today's headcount. Related F19–F22.
- X15 Period mismatch: a synthetic September report links an asset schedule labelled March without explanatory evidence. Expect a date-applicability exception for owner review, not silent relabelling. Related F07/F09/F10.
- X16 Partial formula: a source contains only a truncated external budget reference or names VLOOKUP without its expression. Expect the exact formula to remain unverified; do not fabricate a link target, match mode or month multiplier. Related F03/F11/F25.
- X17 Incomplete forecast population: a forecast is explicitly limited to major expected inflows. Expect a visible coverage limitation; do not mark the receivables ledger reconciled or complete. Related F36/F39/F42.
- X18 Transcript conflict: machine speech suggests a sign-off while the Word passage describes prices on a report. Expect a recorded evidence conflict and owner question; no signature gate is added automatically. Related B12/F28–F30.
- X19 Isolated cash formula: a fixture explicitly supplies inflow 100, outflow 60 and opening/movement input 20. The observed cell expression gives 60. This does not validate the next month's carry-forward formula, currency, opening balance or actual receivables. Keep those checks blocked pending independent owner evidence. Related F38/F39.
