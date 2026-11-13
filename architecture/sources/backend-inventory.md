# Backend inventory (observed, 13 Nov 2026)

Read-only survey of the existing Django backend, made to design the data API for the
new frontend. Observed facts with file references; not a design.

## Platform
- Django 5.2, psycopg 3, PostgreSQL (`config/settings.py:24-26`). No API framework
  (`requirements.in` lists Django, psycopg, jsonschema, cryptography only).
- Default `django.contrib.auth.User`; session authentication with CSRF middleware
  (`config/settings.py:16-19`). No token or JWT login.
- One URLconf, `config/urls.py` (149 paths, function views, mostly HTML). About 40 views
  already return `JsonResponse` reports or exports (Cache-Control: no-store).
- No `frontend/` folder exists yet.

## Permissions
- `apps/identity/services.py:6` `require(actor, case, action)`: an active
  `identity.Grant(case, user, action)` row per case and action.
- `apps/identity/services.py:12` `visible_cases(actor)` uses the `case.read` grant.
- Authority: `apps/policy/services.py:303` `role_policy`, `:346` `decision_authority`;
  `apps/policy/role_assignments.py:58` `eligibility`, `:72` `assert_assigned`.
- Case locking and audit: `apps/core/services.py:13` `lock_case(actor, case_id, action, expected)`, `:9` `event()`.

## Factory engine
- Work: `apps/workflows/factory_models.py:8` `FactoryWork` (case, key, definition, request,
  status, revision, lease/fence, cancel_requested, budget); `FactoryActivity`, `FactoryAttempt`
  (linked to `agents.AgentRun`).
- Human tasks: `workflows.HumanTask` (kind, context, claimed_by, revision, required_role, status), `TaskEvent`.
- Services (`apps/workflows/factory.py`): `start` (:55), `snapshot` (:213), `claim_task` (:754),
  `decide(actor, task_id, expected, verdict, evidence_id, reason)` (:781), `manage(... 'cancel'|'resume')` (:801),
  `adopt_profile` (:822), `release_task_claim` (:842), `advance` (:854),
  `provide_information` (:865), `reconcile` (:883).
- Work states: ready, waiting, verified, blocked, owner_needed, configuration_needed,
  followup_needed, waiting_effect, cancelled (`apps/workflows/factory.py:22`).
- Evidence: `apps/core/services.py:29` `add_evidence(actor, case_id, kind, body, source, expected)`.
- Agent steps: `factory.run_once` / `run_until_wait` through `apps.agents.factory_coordinator`;
  default provider `SyntheticFactoryCoordinator`; real cases refuse unapproved providers.

## Jobs
- No Celery. Database-leased job tables (`workflows.Outbox`, `FactoryWork`, `InvoiceJob`,
  `PublicationJob`, ...) driven by `work_*` management commands.

## Records relevant to screens
- Projects: `core.Case` (kind project/support), `pmo.EngagementRecord`, `pmo.Milestone`.
- Money: `finance.Invoice`, `InvoiceReview`, `InvoiceIssue`, `InvoiceDelivery`, `CashReceipt`,
  `CashAllocation`, `PaymentDecision`, `BillingCoverage`.
- Documents: `documents.Template`, `Document`, `Version`, `Review`, `Publication`, `PublicationReceipt`.
- PMO: `Issue`, `ChangeRequest`, `EscalationRequest`, emergencies, `Meeting`, `ActionItem`, RFP records.
- Configuration: `policy.Configuration` (versioned envelopes), `PolicyState`; "Not set" is a
  display default only, not a stored value.
- History: `core.Audit` (append-only event log via `core.services.event()`), `TaskEvent`.
- Not found: any notification or alert-preference model; any WhatsApp or email adapter; any
  assistant conversation model.

## Tests
- Django test runner against the real PostgreSQL test database (`python manage.py test tests`);
  379 test files; external providers mocked or synthetic.
