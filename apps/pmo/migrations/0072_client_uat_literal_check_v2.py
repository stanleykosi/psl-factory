"""Admit the exact-reference file-check protocol without rewriting v1 history."""
from importlib import import_module
from django.db import migrations

# Derive only from an immutable earlier migration, never mutable service code.
_prior=import_module('apps.pmo.migrations.0071_client_uat_guards').SQL
_body=_prior.split('CREATE FUNCTION psl_client_uat_verification_guard()',1)[1].split('CREATE TRIGGER psl_client_uat_verification',1)[0]
REVERSE='CREATE OR REPLACE FUNCTION psl_client_uat_verification_guard()'+_body
SQL=REVERSE.replace(
    "NEW.adapter NOT IN ('client-uat-evidence-check/v1',",
    "NEW.adapter NOT IN ('client-uat-evidence-check/v1','client-uat-evidence-check/v2',",
).replace(
    "NEW.adapter='client-uat-evidence-check/v1'",
    "NEW.adapter IN ('client-uat-evidence-check/v1','client-uat-evidence-check/v2')",
).replace(
    "AND adapter='client-uat-evidence-check/v1';",
    "AND adapter IN ('client-uat-evidence-check/v1','client-uat-evidence-check/v2');",
)
assert SQL.count('client-uat-evidence-check/v2')==3


class Migration(migrations.Migration):
    dependencies=[('pmo','0071_client_uat_guards')]
    operations=[migrations.RunSQL(SQL,REVERSE)]
