# Development setup and portability

The pack is environment-neutral. Native Windows is supported by the selected Django stack, but no specific user's computer, path or execution service is assumed. Inspect the existing repository/environment and adapt commands rather than impose a new machine.

## Setup deliverable
Document supported Python/Django/PostgreSQL/driver versions, a reviewed lockfile, local environment creation, configuration variables, database creation/migrations, fixtures, web/worker startup, tests and troubleshooting. Use official compatibility documentation and record actual versions. Do not equate LTS with the latest feature release.

On Windows, the Python launcher/venv can support project-local environments; using the environment's python executable avoids activation-policy dependencies. On other supported systems use equivalent standard tooling. PostgreSQL is required for concurrency/integration acceptance. Keep example commands consistent with the actual application layout once created.

## Environment profiles
Provide development, test, staging and production profiles with explicit database/provider/adapter endpoints. Synthetic test mode isolates data and external effects. Real integrations are separately configured, not hard-coded fixture fallbacks. Secrets come from environment/secret storage, never source files, prompts, fixtures or logs.

## Repository hygiene
Preserve existing work. Track source, migrations, tests, lockfile, placeholder environment example, runbooks and build memory. Ignore local virtual environments, credentials, private inputs, caches and runtime dumps. Review diffs and scan for secrets. Keep frozen source snapshots and implementation status distinct. Repository hosting/CI/deployment choices belong in implementation decisions, not personalized restrictions in this pack.

## Reproducibility
A clean checkout should support dependency setup, disposable test database, migrations, synthetic data, web/worker launch, full tests and shutdown. Provide backup/restore/migration tests and operator instructions before operational readiness. Record actual command results; this specification is not evidence that any setup or test has run.
