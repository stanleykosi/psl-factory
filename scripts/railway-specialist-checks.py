"""Run paid synthetic checks at most once for a Railway checks deployment."""

import os
import subprocess
import sys

import psycopg

os.environ["DJANGO_SETTINGS_MODULE"] = "config.specialist_acceptance"
sys.path.insert(0, os.getcwd())
import django

django.setup()
from django.db import connections

database = connections["default"]
name = database.settings_dict["TEST"]["NAME"]
if name != "test_psl_specialist_loop" or os.environ["RAILWAY_SERVICE_NAME"] != "psl-design-checks":
    raise RuntimeError("Synthetic checks require their own service and database.")
params = database.get_connection_params()
params.pop("cursor_factory", None)
params.pop("context", None)
params["dbname"] = "postgres"
with psycopg.connect(**params, autocommit=True) as admin:
    if not admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
        admin.execute("CREATE DATABASE test_psl_specialist_loop")
params["dbname"] = name
deployment = os.environ["RAILWAY_DEPLOYMENT_ID"]
with psycopg.connect(**params, autocommit=True) as state:
    state.execute("CREATE SCHEMA IF NOT EXISTS specialist_acceptance")
    state.execute(
        "CREATE TABLE IF NOT EXISTS specialist_acceptance.run (deployment text PRIMARY KEY, exit_code int)"
    )
    admitted = state.execute(
        "INSERT INTO specialist_acceptance.run VALUES (%s, NULL) ON CONFLICT DO NOTHING RETURNING deployment",
        (deployment,),
    ).fetchone()
    if not admitted:
        (previous,) = state.execute(
            "SELECT exit_code FROM specialist_acceptance.run WHERE deployment=%s", (deployment,)
        ).fetchone()
        print(
            "This deployment already started its provider acceptance. Previous exit code:", previous, flush=True
        )
        sys.exit(1 if previous is None else previous)
    batches = [
        [
            "tests.test_specialist_loop.SpecialistLoopTests",
            "tests.test_design_consolidation.DesignConsolidationTests.test_department_assistant_entry_keeps_file_reviews_on_their_project",
            "tests.test_design_consolidation.DesignConsolidationTests.test_department_chat_does_not_offer_a_manual_specialist_dispatch",
            "tests.test_role_scoped_work.RoleScopedWorkTests.test_lead_can_review_own_file_draft_without_case_wide_document_review",
        ],
        ["tests.test_specialist_loop.LiveSpecialistLoop"],
    ]
    for batch in batches:
        result = subprocess.run(
            [sys.executable, "manage.py", "test", *batch, "--keepdb", "--noinput", "--verbosity", "2"],
            env={**os.environ, "PSL_SPECIALIST_LIVE_TEST": "1"},
        )
        if result.returncode:
            break
    state.execute(
        "UPDATE specialist_acceptance.run SET exit_code=%s WHERE deployment=%s", (result.returncode, deployment)
    )
    print("Specialist acceptance exit code", result.returncode, flush=True)
    sys.exit(result.returncode)
