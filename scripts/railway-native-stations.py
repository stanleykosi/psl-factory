"""Run the three real workflow suites on separate synthetic PostgreSQL databases."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.workflows.native_station_contracts import PROCESSES

SUITES = {
    "pmo": ("tests.test_pmo_coordinator_stations", {p for p in PROCESSES if p.startswith("P")}),
    "accounts": ("tests.test_finance_coordinator_accounts", set("F02 F04 F05 F06 F08 F10 F11 F14 F15 F19 F20 F24 F25 F26 F27".split())),
    "operations": ("tests.test_finance_coordinator_operations", set("F28 F31 F32 F33 F34 F35 F36 F37 F38 F40 F41 F42 F43 F45".split())),
}
LIVE_CASES = {
    "P02": "test_department_routing_from_source_to_receipt",
    "F35": "test_restricted_hr_handoff_to_named_finance_recipient",
}


def run(group, token, role_access):
    environment = dict(os.environ, DJANGO_SETTINGS_MODULE="config.native_station_acceptance", PSL_STATION_SUITE=group, PSL_STATION_RUN=token, PYTHONUNBUFFERED="1")
    if group == 'original':
        from apps.workflows.factory_processes import PROCESS_IDS
        from apps.workflows.native_station_contracts import DEFINITION
        required = {pid for line, processes in PROCESS_IDS.items() if line != DEFINITION for pid in processes}
        modules = ['tests.test_original_process_role_access']
    elif group == 'directory':
        modules = ['tests.test_process_trigger_navigation', 'tests.test_process_role_directory',
                   'tests.test_native_station_role_access', 'tests.test_factory_api',
                   'tests.test_role_scoped_work.RoleScopedWorkTests.test_role_accounts_keep_the_full_factory_shell_and_scoped_destinations']
    elif group == 'surface':
        required = set()
        modules = ['tests.test_process_role_directory', 'tests.test_native_station_role_access', 'tests.test_factory_api',
                   'tests.test_role_scoped_work', 'tests.test_role_guard', 'tests.test_primary_roles',
                   'tests.test_role_eligibility', 'tests.test_finance_document_review',
                   'tests.test_factory_change.FactoryChangeTests.test_withdrawn_decision_authority_invalidates_selected_authorization',
                   'tests.test_factory_payroll.FactoryPayrollTests.test_complete_native_path_requires_reviews_human_publication_and_actual_recipient_receipt',
                   'tests.test_factory_payroll.FactoryPayrollTests.test_current_review_revocation_invalidates_verification',
                   'tests.test_payroll.PayrollTests.test_recipient_grant_revocation_and_HR_approval_revocation_hold_use',
                   'tests.test_payroll.PayrollTests.test_policy_and_retention_revocation_hold_current_read_and_report',
                   'tests.test_payroll.PayrollTests.test_raw_rows_and_salary_values_are_private_to_named_readers',
                   'tests.test_rfp_fresh_intake.FreshBidIntakeTests.test_api_and_form_share_the_original_file_receipt_and_delegation']
    else:
        module, required = SUITES[group]
        modules = [module]
        if role_access:
            environment['PSL_VERIFY_NATIVE_ROLES'] = '1'
    if group == "pmo":
        modules += ["tests.test_native_station_controls", "tests.test_specialist_loop.SpecialistLoopTests"]
    if group == "accounts":
        modules.append("tests.test_finance_import_projection")
    cmd = [sys.executable, "manage.py", "test", *modules, "--keepdb", "--noinput", "--verbosity", "1"]
    if group == 'directory':
        cmd += ["--testrunner", "tests.api_contract_runner.ContractRunner"]
    observed = set()
    role_observed = set()
    with subprocess.Popen(cmd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
        for line in process.stdout:
            print(f"[{group}] {line}", end="", flush=True)
            if "Native station verified " in line and " -> " in line:
                observed.add(line.split("Native station verified ", 1)[1].split(" -> ", 1)[0])
            if 'ROLE_ACCESS ' in line:
                role_observed.add(line.split('ROLE_ACCESS ', 1)[1].split()[0])
        status = process.wait()
    if group in SUITES:
        print(f"[{group}] Passed receiver checks {sorted(observed)}. Missing {sorted(required - observed)}.", flush=True)
        if observed != required:
            return False
    if role_access and group not in ('surface', 'directory'):
        print(f"[{group}] Role reads checked for {len(role_observed)} processes; missing {sorted(required - role_observed)}.", flush=True)
        if role_observed != required:
            return False
    return status == 0


def live(params, database, processes):
    """Reserve any paid run once per deployment, even if the container is restarted."""
    if not all(os.environ.get(k) for k in ("PSL_ACCEPTANCE_SOURCE_MODEL", "PSL_ACCEPTANCE_SOURCE_KEY")):
        raise RuntimeError("The checks service has no temporary provider binding.")
    params = {**params, "dbname": database}
    with psycopg.connect(**params, autocommit=True) as state:
        state.execute("CREATE SCHEMA IF NOT EXISTS specialist_acceptance")
        state.execute("CREATE TABLE IF NOT EXISTS specialist_acceptance.station_live(deployment text PRIMARY KEY, result int)")
        deployment = os.environ["RAILWAY_DEPLOYMENT_ID"]
        new = state.execute("INSERT INTO specialist_acceptance.station_live(deployment) VALUES (%s) ON CONFLICT DO NOTHING RETURNING deployment", (deployment,)).fetchone()
        if not new:
            row = state.execute("SELECT result FROM specialist_acceptance.station_live WHERE deployment=%s", (deployment,)).fetchone()
            return row == (0,)
        names = ["tests.test_native_station_live.NativeProviderAcceptance." + LIVE_CASES[pid] for pid in processes]
        result = subprocess.run([sys.executable, "manage.py", "test", *names, "--keepdb", "--noinput", "--verbosity", "2"],
                                env={**os.environ, "PSL_STATION_LIVE": "1"}).returncode
        state.execute("UPDATE specialist_acceptance.station_live SET result=%s WHERE deployment=%s", (result, deployment))
        return result == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*")
    parser.add_argument('--role-access', action='store_true', help='Check admitted staff on the HTML and API for each process.')
    provider = parser.add_mutually_exclusive_group()
    provider.add_argument("--live", action="store_true", help="Also run both synthetic provider and storage checks.")
    provider.add_argument("--live-case", choices=LIVE_CASES, help="Run one fresh synthetic provider case before the department suites.")
    options = parser.parse_args()
    available = (*SUITES, 'original', 'surface', 'directory') if options.role_access else tuple(SUITES)
    groups = options.groups or available
    if set(groups) - set(available) or len(set(groups)) != len(groups):
        parser.error("Choose distinct department suites.")
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.specialist_acceptance"
    import django
    django.setup()
    from django.db import connections
    if os.environ.get("RAILWAY_SERVICE_NAME") != "psl-design-checks":
        raise RuntimeError("The isolated Railway checks service is required.")
    settings = connections["default"].settings_dict
    template = settings["TEST"]["NAME"]
    if template != "test_psl_specialist_loop" or settings["NAME"].startswith("test_"):
        raise RuntimeError("Unexpected test database environment.")
    params = connections["default"].get_connection_params()
    params.pop("cursor_factory", None)
    params.pop("context", None)
    params["dbname"] = "postgres"
    selected_passed = live(params, template, [options.live_case]) if options.live_case else True
    # A previous container may have stopped in the middle of a transactional
    # fixture. Never reuse its data, even when Railway restarts a deployment.
    with psycopg.connect(**{**params, "dbname": template}) as check:
        if check.execute("SELECT EXISTS(SELECT 1 FROM auth_user)").fetchone()[0]:
            raise RuntimeError("The synthetic template contains accounts. A clean migrated template is required.")
    token = uuid4().hex
    owned = []
    with psycopg.connect(**params, autocommit=True) as admin:
        try:
            for group in groups:
                name = f"test_psl_stations_{group}_{token}"
                admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(name), sql.Identifier(template)))
                owned.append(name)
            with ThreadPoolExecutor(max_workers=len(groups)) as pool:
                results = [pool.submit(run, group, token, options.role_access) for group in groups]
                passed = all([result.result() for result in results])
        finally:
            for name in owned:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
    if passed and options.live:
        passed = live(params, template, LIVE_CASES)
    return passed and selected_passed


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
