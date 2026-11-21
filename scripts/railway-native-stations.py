"""Run the three real workflow suites on separate synthetic PostgreSQL databases."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys

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


def run(group):
    module, required = SUITES[group]
    environment = dict(os.environ, DJANGO_SETTINGS_MODULE="config.native_station_acceptance", PSL_STATION_SUITE=group, PYTHONUNBUFFERED="1")
    modules = [module]
    if group == "pmo":
        modules += ["tests.test_native_station_controls", "tests.test_specialist_loop.SpecialistLoopTests"]
    cmd = [sys.executable, "manage.py", "test", *modules, "--keepdb", "--noinput", "--verbosity", "1"]
    observed = set()
    with subprocess.Popen(cmd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
        for line in process.stdout:
            print(f"[{group}] {line}", end="", flush=True)
            if "Native station verified " in line and " -> " in line:
                observed.add(line.split("Native station verified ", 1)[1].split(" -> ", 1)[0])
        status = process.wait()
    print(f"[{group}] Passed receiver checks {sorted(observed)}. Missing {sorted(required - observed)}.", flush=True)
    return status == 0 and observed == required


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
    parser.add_argument("groups", nargs="*", default=list(SUITES))
    provider = parser.add_mutually_exclusive_group()
    provider.add_argument("--live", action="store_true", help="Also run both synthetic provider and storage checks.")
    provider.add_argument("--live-case", choices=LIVE_CASES, help="Run one fresh synthetic provider case before the department suites.")
    options = parser.parse_args()
    groups = options.groups
    if not groups or set(groups) - SUITES.keys() or len(set(groups)) != len(groups):
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
    with psycopg.connect(**params, autocommit=True) as admin:
        for group in groups:
            name = "test_psl_stations_" + group
            if not admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
                admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(name), sql.Identifier(template)))
    selected_passed = live(params, template, [options.live_case]) if options.live_case else True
    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        passed = all(list(pool.map(run, groups)))
    if passed and options.live:
        passed = live(params, template, LIVE_CASES)
    return passed and selected_passed


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
