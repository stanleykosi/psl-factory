# Resume from a GitHub checkout

The repository is the source/build handoff for PSL's AI agent operations factory. Read root AGENTS.md, START-HERE.md, BUILD-STATE.md, HANDOFF.md and BUILD-BACKLOG.json before changing it. The user paused feature work on 6 November 2026 to make this initial GitHub handoff. Do not interpret this initial commit as product completion or production approval.

## What travels with the repository

Application code, migrations, server-rendered UI, agent/tool contracts, typed policy interfaces, synthetic fixtures, tests, original process sources, the component design, all build records and checked-in test evidence are included. Historical manifests describe the exact files tested at their recorded time; they do not claim every present file existed in that earlier run. Keep failed evidence and source snapshots immutable.

Local .runtime/, .venv/, database clusters/archives, credentials and generated environment state are excluded. References to the original Windows path, process IDs, retained databases, preview contexts and .runtime helpers in dated evidence describe that machine. They are not instructions to recreate operational records. The original local workspace and its databases have been retained; GitHub transfer does not copy or reset them.

The latest completed run at handoff is665:6PASS (578.937s unittest/590.254s process), including cancelled reservation→fresh outward review→one successor receipt, native document reuse, returned-document rework, complete primary HTTP RFP flow and closed policy-shape validation.664 reached16/21 with15PASS/1FAIL at an uninstrumented worker-tick setup assertion.665 changed only that test setup; production source is identical.663's broader51PASS predates the historical-outcome changes. Read the exact numbered evidence; do not add overlapping test counts as unique process coverage.

No current-source native-browser acceptance, retained-schema upgrade or fresh-schema proof is claimed for the RFP increment. Retained databases on the original machine were workflows0059/documents0018; test_psl reached0062/documents0019. A new checkout should migrate a NEW development database through the current graph, rather than replay old seeds or migration commands against any retained database.

## Fresh environment

Use Python3.13 and PostgreSQL16, with the exact packages in requirements.lock. Create a virtual environment and install the lock file:

```sh
python -m venv .venv
# Activate .venv for your operating system, then:
python -m pip install -r requirements.lock
```

Provision a new isolated PostgreSQL development database and a role permitted to create its separate Django test database. Set PGDATABASE, PGUSER, PGPASSWORD, PGHOST and PGPORT in your environment; .env.example is a template and is not loaded automatically. The checked-in defaults use loopback port55432, database/userpsl. Supply your own credentials. Do not point tests at operational data.

```sh
python manage.py migrate --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test tests.test_rfp_outcome_policy tests.test_rfp_historical_outcome --noinput --verbosity 2
```

Windows portable PostgreSQL is an optional alternative documented in development.md and scripts/start-dev-postgres.ps1; binaries and database files are not distributed in Git. Docker or a new database service is not required by the application architecture. No SQLite fallback exists.

For numbered source/log evidence, use `python scripts/run_factory_tests.py <unused-number> <Django-test-label> ...`. It preserves the existing historical1November filename convention; actual UTC timestamps are authoritative. Run one suite at a time and freeze application/test/contract/fixture/template/static source while it runs. Choose an unused number by inspecting docs/test-evidence, not by assuming this document is the newest record.

Broader operator/recovery suites require their documented isolated drill database and deployment/readiness fixture bindings. Recreate test-owned infrastructure from their fixtures/runbooks; never copy secret registries, credentials, source-machine database contexts or actual owner policies from another environment. Tests mock external providers where stated; they exercise native services and PostgreSQL.

## Resume the build

Verify the latest source and test outcomes first. Next RFP work is source-specific branch/regression acceptance, preservation/fresh migration proof and a fresh synthetic native-browser journey. Then continue the connected Finance increment in HANDOFF.md/BUILD-BACKLOG.json.63 PMO+45 Finance remain the release scope;14 BaaS IDs remain preserved/deferred. Owner policy, real model evaluations, UAT and live integration remain separate from code and mock acceptance.

Do not activate workers, external effects, real providers, credentials or business policies merely because this checkout starts. Keep agent work scoped to native typed tools and keep accountable human decisions separate from verified business outputs.
