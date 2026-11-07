"""Independent guard diagnostic; not a final migration or composed acceptance run."""
from importlib import import_module
from django.test.runner import DiscoverRunner
from django.db import connection
class Runner(DiscoverRunner):
    def setup_databases(self,**kwargs):
        result=super().setup_databases(**kwargs)
        from scripts.p43_guard_sql import workflow,documents
        with connection.cursor() as c:
            c.execute(workflow(import_module('apps.workflows.migrations.0069_factory_schedules').SQL))
            c.execute(documents(import_module('apps.documents.migrations.0023_factory_forecast').SQL))
        print('P43 INDEPENDENT DIAGNOSTIC ONLY: provisional additive guard on accepted0070/0023; not final0074/0027 migration proof',flush=True)
        return result
