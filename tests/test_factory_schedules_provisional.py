"""DISPOSABLE TEST ONLY: unaccepted envelope on accepted0065, not final706."""
from importlib import import_module
from django.db import connection
from apps.workflows.schedules_factory_guard import extend
from .test_factory_schedules import FactorySchedulesTests as Base
class ProvisionalSchedulesTests(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as c:c.execute(extend(import_module('apps.workflows.migrations.0065_factory_emergency').SQL))
# Avoid duplicate imported base discovery.
del Base
