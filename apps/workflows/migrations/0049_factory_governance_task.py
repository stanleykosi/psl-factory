"""Add a native governance wait, retaining immutable task identity and packet history."""
from importlib import import_module
from django.db import migrations

original=import_module('apps.workflows.migrations.0038_factory_guards').SQL
SQL=original[original.index('CREATE FUNCTION psl_factory_task_identity()'):original.index('CREATE TRIGGER psl_factory_task_identity')]
SQL=SQL.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)
assert SQL.count("'factory_information','factory_review'")==1
SQL=SQL.replace("'factory_information','factory_review'","'factory_information','factory_review','factory_governance'")

class Migration(migrations.Migration):
    dependencies=[('workflows','0048_factory_go_live_reaffirmation')]
    operations=[migrations.RunSQL(SQL)]
