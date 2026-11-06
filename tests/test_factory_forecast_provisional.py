"""Isolated diagnostic only. Does not claim accepted composed migration graph."""
from django.db import connection
from . import test_factory_forecast as final_suite
from .forecast_factory_provisional_schema import PREVIOUS_WORK,PREVIOUS_DOC,work_sql,doc_sql

class ProvisionalForecastFactoryTests(final_suite.ForecastFactoryTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute(work_sql(PREVIOUS_WORK))
            cursor.execute(doc_sql(PREVIOUS_DOC))

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute(PREVIOUS_DOC)
            cursor.execute(PREVIOUS_WORK)
        super().tearDownClass()
