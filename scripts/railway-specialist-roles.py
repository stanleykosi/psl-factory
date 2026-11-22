"""Run synthetic OpenRouter acceptance for each specialist on an isolated Railway clone."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb


def main(ticket, processes, require_f02_calculation, coordinator):
    if (os.getenv("RAILWAY_SERVICE_ID"), os.getenv("RAILWAY_SERVICE_NAME")) != (
        "00c14ca1-5361-4bee-97a5-2ec7aba6ef18", "psl-design-checks"
    ):
        raise RuntimeError("The isolated Railway checks service is required.")
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.specialist_acceptance"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import django
    django.setup()
    from django.db import connection
    from tests.test_specialist_role_receipts import TEAMS

    params = connection.get_connection_params()
    for key in ("cursor_factory", "context"):
        params.pop(key, None)
    template = connection.settings_dict["TEST"]["NAME"]
    if template != "test_psl_specialist_loop":
        raise RuntimeError("Unexpected acceptance template.")
    name = "test_psl_stations_roles_" + ticket.hex
    deployment = os.environ["RAILWAY_DEPLOYMENT_ID"]
    with psycopg.connect(**{**params, "dbname": template}, autocommit=True) as state:
        state.execute("CREATE SCHEMA IF NOT EXISTS specialist_acceptance")
        state.execute("""CREATE TABLE IF NOT EXISTS specialist_acceptance.role_run(
            ticket uuid PRIMARY KEY, deployment text NOT NULL UNIQUE, passed boolean, evidence jsonb)""")
        if state.execute("SELECT EXISTS(SELECT 1 FROM auth_user)").fetchone()[0]:
            raise RuntimeError("The synthetic template contains accounts.")
        admitted = state.execute(
            "INSERT INTO specialist_acceptance.role_run(ticket,deployment) VALUES(%s,%s) "
            "ON CONFLICT DO NOTHING RETURNING ticket", (ticket, deployment),
        ).fetchone()
        if not admitted:
            prior = state.execute(
                "SELECT passed FROM specialist_acceptance.role_run WHERE ticket=%s", (ticket,),
            ).fetchone()
            print("This ticket has already run. No additional model calls.", flush=True)
            return prior == (True,)
    # PostgreSQL requires all template sessions to close before cloning.
    evidence = []
    methods = {"F02": "test_f02_trial_balance_review_and_mapping",
               "F35": "test_f35_hr_approval_before_private_finance_receipt",
               "P52": "test_p52_approved_document_delivered_to_named_recipient"}
    if set(methods) != set(TEAMS) or set().union(*TEAMS.values()) != {f"A{i:02}" for i in range(1, 9)}:
        raise RuntimeError("Representative routes must cover all eight configured specialists.")
    required = {(process, role) for process in processes for role in TEAMS[process]}
    passed = False
    checked_access = False
    checked_coordinator = set()
    try:
        for key in ("PSL_ACCEPTANCE_SOURCE_KEY", "PSL_ACCEPTANCE_SOURCE_MODEL"):
            if not os.getenv(key):
                raise RuntimeError("The temporary Railway provider binding is incomplete.")
        # Check the upload bucket's exact-key version-listing permission before
        # buying a reading. Cleanup deletes only versions minted by this run.
        from adapters import case_uploads
        client, bucket = case_uploads.bucket()
        try:
            client.list_object_versions(Bucket=bucket, Prefix=f"synthetic-specialist-check/{ticket.hex}", MaxKeys=1)
        finally:
            client.close()
        with psycopg.connect(**{**params, "dbname": "postgres"}, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(name), sql.Identifier(template)))
            try:
                environment = dict(os.environ, DJANGO_SETTINGS_MODULE="config.native_station_acceptance",
                                   PSL_STATION_LIVE="1", PSL_STATION_SUITE="roles", PSL_STATION_RUN=ticket.hex,
                                   PSL_REQUIRE_F02_CALCULATION="1" if require_f02_calculation else "0")
                suite = "LiveCoordinatorTests" if coordinator else "LiveRoleApprovalTests"
                labels = [f"tests.test_specialist_role_receipts.{suite}.{methods[pid]}" for pid in processes]
                if require_f02_calculation:
                    labels.insert(0, "tests.test_finance_import_projection")
                test_command = [sys.executable, "manage.py", "test", "--keepdb", "--noinput", "--verbosity", "2"]
                if coordinator:
                    smoke = subprocess.run([*test_command, "tests.test_specialist_coordination",
                        "tests.test_specialist_role_receipts.SimulatedCoordinatorTests"],
                        env={**environment, "PSL_STATION_LIVE": "0"})
                    if smoke.returncode:
                        raise RuntimeError("Coordinator PostgreSQL checks failed before any provider calls.")
                command = [*test_command, *labels]
                with subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as run:
                    for line in run.stdout:
                        print(line, end="", flush=True)
                        if "ROLE_ACCESS F02 " in line:
                            checked_access = True
                        if "Coordinator loop receipt " in line:
                            checked_coordinator.add(json.loads(line.split("Coordinator loop receipt ", 1)[1])["process"])
                        prefix = "Specialist approval receipt "
                        if prefix in line:
                            evidence.append(json.loads(line.split(prefix, 1)[1]))
                    status = run.wait()
                observed = {(row["process"], row["role"]) for row in evidence if row["mode"] == "openrouter"}
                passed = status == 0 and observed == required and len(evidence) == len(required)
                if require_f02_calculation:
                    passed = passed and checked_access
                if coordinator:
                    passed = passed and checked_coordinator == set(processes)
            finally:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
    finally:
        with psycopg.connect(**{**params, "dbname": template}, autocommit=True) as state:
            state.execute("UPDATE specialist_acceptance.role_run SET passed=%s,evidence=%s WHERE ticket=%s",
                          (passed, Jsonb(evidence), ticket))
    print(f"Specialist approval checks: processes={processes}; passed={passed}; verified={len(evidence)} routes/roles.", flush=True)
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket", type=UUID, help="One-time UUID for this specific authorised run.")
    parser.add_argument("--process", choices=("F02", "F35", "P52"), help="Run just one independent approval and its team.")
    parser.add_argument("--require-f02-calculation", action="store_true",
                        help="Also require A05 to support its conclusion and cite the computed trial-balance control.")
    parser.add_argument("--coordinator", action="store_true", help="Run OpenRouter routing, report review and the department assistant.")
    args = parser.parse_args()
    if args.require_f02_calculation and args.process != "F02":
        parser.error("--require-f02-calculation requires --process F02")
    sys.exit(0 if main(args.ticket, [args.process] if args.process else ["F02", "F35", "P52"],
                       args.require_f02_calculation, args.coordinator) else 1)
