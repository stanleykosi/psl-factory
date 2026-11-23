from time import monotonic
from django.db import connection,transaction
from django.test import TestCase
from apps.core.read_budget import limit_queries,ReadLimit


class ReadLimitRecoveryTests(TestCase):
    def test_exhaustion_unwinds_native_savepoints_and_preserves_the_outer_transaction(self):
        with self.assertRaises(ReadLimit):
            with limit_queries(2):
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT 1')
                        cursor.execute('SELECT 2')
        self.assertFalse(connection.needs_rollback)
        with connection.cursor() as cursor:
            cursor.execute('SELECT 3');self.assertEqual(cursor.fetchone(),(3,))
        self.assertEqual(connection.vendor,'postgresql')

    def test_deadline_exhaustion_does_not_poison_a_nested_native_read(self):
        with self.assertRaises(ReadLimit):
            with limit_queries(100,deadline=monotonic()-1):
                with transaction.atomic():
                    with connection.cursor() as cursor:cursor.execute('SELECT 1')
        with connection.cursor() as cursor:
            cursor.execute('SELECT 4');self.assertEqual(cursor.fetchone(),(4,))
