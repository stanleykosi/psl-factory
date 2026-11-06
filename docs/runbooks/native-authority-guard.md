# Native role and delegated authority evaluation

`role.decision.evaluate` reads the actual `decision_authority` service with an exact role, decision action and delegated flag. It creates no business decision, review, grant or effect. Qualification is separate from the action grant and the domain's independent human controls.

The selected variant records its actual required components: nomination always; delegation only when delegated; action matrix only for non-approve actions. The original broader dependency declaration remains visible. A04 distinguishes unused requirements for other variants from runtime holds for the selected variant. This is bounded selected-variant evidence, not a whole-product or live-pilot approval.

Delegation v1 retains distinct named people, role and aware authority window. Operational delegates combining a nominated role with a delegated role need explicit v2 `delegate_eligibility`: exact combined roles and an aware half-open qualification window. The declaration must include the delegated role and overlap the authority window. The runtime matches the current nominated roles; a changed bundle or expired qualification holds the delegated use. Existing nominated roles continue under their own qualification and grants.

Delegating principals must themselves remain nominated, active and qualified. V2 nomination dictionaries are supported; extra eligibility fields cannot make a valid principal disappear from matching. Both principal and delegate qualification are checked again when native services reuse a delegated review. A delegation cannot extend an expired principal qualification or waive independent controls.

Use the policy workbench's scoped delegation draft form with actual owner evidence. Saving a draft does not activate it. Invalid declarations remain drafts. Effective timestamps require an explicit offset. Activate only through the existing reviewed configuration lifecycle; fixtures do not appoint real people.

Observers need current policy/source access. Stored scoped origins are reauthorized even if resolution is unavailable; losing access to a delegation origin does not block an unrelated direct nomination read. The binding schema and forward SQL contract enforce exact boolean variants, closed argument/role/action sets and selected participants.

Tests use PostgreSQL, real delegated document review, grant-revocation concurrency, SQL negative/positive controls and native isolated recovery. Restored declarations, bindings and engineering reviews remain history: old people inactive, grants disabled and application quarantined. Actual owner qualification, production identity and live validation remain separate.
