# Internal mock process acceptance

Run `python scripts/check_internal_mock_acceptance.py` from any working directory, or pass `--root PATH`. This read-only, database-free check derives the accepted count from the canonical 122 coverage rows and the source process map (108 PMO/Finance release IDs; 14 deferred BaaS IDs). It does not change coverage, source snapshots or production authorization.

## Meaning and promotion

A row counts only when `factory_consolidation.mock_acceptance.status` is `PASS` **and** its `scope` is exactly `whole_process_internal_mock`. Existing bounded mock PASS results remain valid historical declarations but do not count. A status by itself is not whole-process acceptance.

Use `NOT_EVALUATED`, `BLOCKED`, `FAIL` or `PASS`. Internal mock acceptance covers source-defined behavior through real native services/PostgreSQL, useful agent work, required human decisions, verified outputs/receipts and meaningful recovery, with synthetic authority and mocked external transport. Owner policy values, provider setup, external connections, independent UAT and production authorization remain distinct. Do not defer missing internal implementation under those labels.

The validator checks evidence consistency, not truth by fiat: reviewers must inspect the actual assertions, browser observations, logs and runtime dependency scope. It cannot establish that a screenshot is truthful, an assertion is sufficient or a human review really occurred. Never manufacture evidence or a composition review to satisfy the schema.

## Per-process packet

Put these fields in the existing `mock_acceptance` object:

- `status`: `PASS` only after every required proof has passed.
- `scope`: `whole_process_internal_mock`.
- `runtime_files`: nonempty unique repository-relative runtime paths, selected from the actual source manifest. Include the process services, shared controls it relies on, adapters, relevant configuration/contracts, UI/templates/static files and dependency locks. Do not use a token file to evade dependency checks. Unrelated components need not be included.
- `runtime_scope_review`: a substantive explanation of the reviewed dependency boundary and reviewer identity.
- `remaining_internal_engineering`: an empty list for PASS.
- `deferrals`: list of `{ "kind": "owner_policy", "description": "Actual configured role owners remain unset" }` objects. Allowed kinds: `owner_policy`, `provider_setup`, `external_connection`, `independent_uat`, `production_authorization`. Empty list is allowed.
- `runs`: list of `{ "kind": "native", "record": "docs/test-evidence/RUN.json", "source_manifest": "docs/test-evidence/RUN-source.json", "tests": ["tests.test_module.TestClass.test_method"] }`. Include `native`, `connected` and `recovery` kinds. The same actual run can support multiple kinds when the mapped tests actually cover them.
- `assertions`: object keyed by **every exact** `source_assertion_ids` entry from this coverage row. Each value is `{ "status": "PASS", "tests": ["fully.qualified.passing.test"] }`. No omitted or extra assertions. Test names must appear among the validated runs.
- `browser`, `fresh_schema`, `preservation`: repository-relative JSON proof paths described below.
- `composition_reviews`: optional list of reviewed composition JSON paths.

Run records use the existing runner format: `status: finished`, integer `returncode: 0`, a PostgreSQL `database`, `command`, `started_at`, and `log`. The source manifest defaults to the run record filename with `.json` replaced by `-source.json`; a record may explicitly supply `source_manifest` instead. The supplied manifest must match that binding. Source manifests have the existing `{ "files": { "relative/path": "sha256" } }` structure.

Run logs must finish successfully with a standalone `OK`, and each mapped test must have its actual verbose unittest line `test_name (fully.qualified.test_name) ... ok`. Selected labels, skipped tests, log excerpts with no successful completion, unfinished and failed records do not qualify. A run selected at module level still requires individual passing test names in the packet.

## Browser and schema proof format

Each proof object has:

- `status: PASS` and `kind`: `browser`, `fresh_schema` or `preservation`.
- `source_manifest`: actual source snapshot captured for this proof.
- `command`, `observed_at`, `log`: what executed, when, and the nonempty saved observation log.

Browser proof also requires `browser`, `environment`, `role`, `fixture`, `viewport`. Name the actual surface, e.g. Chromium on the cloud computer; do not call it native desktop evidence. Its `journeys` object must contain `queue_to_case`, `agent_work`, `evidence_review`, `exact_version_approval`, `exception_recovery`, `verified_outcome`, `keyboard`, and `narrow_screen`. Each has `status: PASS`, a concrete `observation`, and a nonempty `screenshots` list of existing repository-relative files. The narrow-screen observation records its viewport and actual usability result. Record failures rather than deleting journeys.

Fresh-schema and preservation proof additionally require a nonempty `checks` object, with every named check `PASS`. Reviewers select the substantive checks: fresh zero-business-row migration chain, retained rowsets/indexes/guards and other relevant preservation invariants. Existing proof formats can remain immutable: create a reviewed normalized evidence record pointing at their original logs and source manifest rather than rewriting historical results.

## Source changes and composition

Every declared runtime file must appear in each source manifest and exist currently. Its SHA-256 must match current bytes. Files outside the reviewed process scope do not invalidate acceptance merely because another component changed.

If scoped bytes differ, rerun the relevant evidence or provide a composition review with `status: PASS`, the exact `source_manifest`, `reviewer`, a substantive `rationale`, `unchanged_runtime_behavior: true`, and `changes` mapping **exactly every changed scoped path** to `{ "before": "manifest sha256", "after": "current sha256" }`. This records a reviewed unchanged-behavior composition, not permission to waive changed business behavior. A later edit invalidates that review until re-evaluated. Relevant behavior changes require new tests/browser proof, not an unchanged-behavior declaration.

## Summary and connected gate

Once any whole-process internal mock packet passes, `factory_consolidation.internal_mock_acceptance` must exactly equal the derived object:

```
{
  "accepted_ids": ["actual validated IDs, sorted"],
  "accepted_count": 1,
  "release_count": 108,
  "deferred_count": 14,
  "full108_internal_handoff_gate": "NOT_MET"
}
```

The illustrative ID string is a placeholder, not a valid ID. Counts are derived, never a fixed target of five. `MET` requires **all** 108 release IDs to validate. When the accepted set is empty, the summary may be absent for compatibility. A root consolidation `full108_internal_handoff_gate`, if present, must agree. Historical nested checkpoint gates remain historical.

`connected_process_acceptance: PASS` is supported only with `connected_acceptance_scope: whole_process_internal_mock` and that row's validated whole-process packet (including connected and recovery runs). Otherwise leave connected acceptance separately unevaluated. Neither field promotes model evaluation, UAT, production authorization or full-product completion.

The original baseline field-preservation test remains unchanged. Write evolving acceptance only inside consolidation metadata; do not alter frozen top-level fields or source definitions.

## Verification

`python manage.py test tests.test_factory_coverage tests.test_internal_mock_acceptance` runs only SimpleTestCase tests and needs no database. Negative fixtures exercise missing evidence/assertions, failed/unfinished/skipped/unmapped tests, SQLite, stale source, missing browser journeys, failed preservation, internal gaps, untyped deferrals, deferred/duplicate IDs, inflated summaries and connected-scope bypass. Synthetic unit-test packets never become real process evidence.
