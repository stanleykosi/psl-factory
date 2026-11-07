"""Preserve exact PPE operations while declaring their identity table dependency.

The single-migration replacement supports fresh and already-applied histories.
Keep 0068_factory_ppe.py immutable and available for old migration identities.
"""
from importlib import import_module
from django.db import migrations

ORIGINAL=import_module('apps.workflows.migrations.0068_factory_ppe')

class Migration(migrations.Migration):
    replaces=[('workflows','0068_factory_ppe')]
    dependencies=[('workflows','0067_factory_forecast'),('identity','0001_initial')]
    operations=ORIGINAL.Migration.operations
