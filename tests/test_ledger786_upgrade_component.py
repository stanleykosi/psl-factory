import copy
import json
import unittest
from scripts.ledger786_upgrade import compare, TARGET


class UpgradeComparatorTests(unittest.TestCase):
    def samples(self):
        old = {'tables': {'django_migrations': [], 'policy_pilotbinding': ['committed old binding']},
               'functions': {'psl_pilot_binding_guard()': 'old', 'other()': 'unchanged'},
               'sequences': {'django_migrations_id_seq': {'definition': [1], 'state': [5, True]},
                             'other': {'definition': [1], 'state': [8, True]}}, 'constraints': {'x': 'same'}}
        new = copy.deepcopy(old)
        new['tables']['django_migrations'] = [json.dumps({'id': 6, 'app': TARGET[0], 'name': TARGET[1], 'applied': 'synthetic'})]
        new['functions']['psl_pilot_binding_guard()'] = 'new'
        new['sequences']['django_migrations_id_seq']['state'] = [6, True]
        return old, new

    def test_only_exact_declared_delta_passes(self):
        a, b = self.samples()
        self.assertEqual(compare(a, b, 'old', 'new')['status'], 'EXACT_DECLARED_UPGRADE_ONLY')

    def test_existing_binding_or_other_schema_change_fails(self):
        for section, key, value in [('tables', 'policy_pilotbinding', []), ('constraints', 'x', 'changed'),
                                    ('functions', 'other()', 'changed')]:
            with self.subTest(section=section):
                a, b = self.samples(); b[section][key] = value
                with self.assertRaises(RuntimeError): compare(a, b, 'old', 'new')

    def test_unexpected_sequence_or_marker_fails(self):
        for mutate in [lambda b: b['sequences']['other']['state'].__setitem__(0, 9),
                       lambda b: b['sequences']['django_migrations_id_seq']['state'].__setitem__(0, 7),
                       lambda b: b['tables']['django_migrations'].append('{}')]:
            a, b = self.samples(); mutate(b)
            with self.assertRaises(RuntimeError): compare(a, b, 'old', 'new')

    def test_missing_section_or_function_fails(self):
        a, b = self.samples(); del b['constraints']
        with self.assertRaises(RuntimeError): compare(a, b, 'old', 'new')
        a, b = self.samples(); del b['functions']['other()']
        with self.assertRaises(RuntimeError): compare(a, b, 'old', 'new')

    def test_frozen_migration_bodies_load_without_database(self):
        from scripts.ledger786_upgrade import body, PREVIOUS
        old, new = body(PREVIOUS[1]), body(TARGET[1])
        self.assertIn("WHEN 'pmo.decision.record'", old)
        self.assertNotIn("WHEN 'ledger.review'", old)
        self.assertIn("WHEN 'ledger.review'", new)
