import json
from pathlib import Path
from types import SimpleNamespace
from django.conf import settings
from django.test import SimpleTestCase,RequestFactory,override_settings
from django.template.loader import render_to_string

class FactoryCoverageTests(SimpleTestCase):
    def test_original_process_fields_and_all_release_deferred_bindings_are_retained(self):
        read=lambda p:json.loads((settings.BASE_DIR/p).read_text(encoding='utf-8'))
        current=read(Path('contracts/implementation-coverage.json'));source=read(Path('contracts/process-map.json'))['rows']
        original=read(Path('docs/test-evidence/2026-11-01-factory-baseline.json'))['coverage_rows']
        rows={r['id']:r for r in current['rows']};self.assertEqual(len(rows),122)
        for row in original:
            self.assertEqual({k:rows[row['id']][k] for k in row},row)
        release={r['id'] for r in source if r['department'] in ['PMO','Finance']};deferred={r['id'] for r in source if r['department']=='BaaS'}
        self.assertEqual(len(release),108);self.assertEqual(len(deferred),14)
        self.assertEqual(set(current['factory_consolidation']['release_ids']),release)
        self.assertEqual(set(current['factory_consolidation']['deferred_baas_ids']),deferred)
        for row in rows.values():
            self.assertEqual(row['factory_consolidation']['release_scope'],'first_release' if row['id'] in release else 'deferred_baas')
            self.assertEqual(row['status'],'partial')
        from scripts.check_internal_mock_acceptance import validate
        validate(settings.BASE_DIR, current, {'rows': source})
        for key,count in [('requirements',25),('acceptance_tests',20),('activities',15),('agent_assertions',15),('routing_scenarios',16)]:
            self.assertEqual(len(current['factory_consolidation'][key]),count)
        self.assertFalse(current['factory_consolidation']['full_product_complete'])

    @override_settings(ROOT_URLCONF='config.cold_urls')
    def test_shared_shell_keeps_recovery_plane_separate_without_adding_operational_routes(self):
        request=RequestFactory().get('/');request.user=SimpleNamespace(is_authenticated=True,is_superuser=False,username='synthetic-recovery',get_short_name=lambda:'')
        case=SimpleNamespace(title='Isolated control workspace',synthetic=True)
        html=render_to_string('base.html',{'user':request.user,'case':case},request=request)
        self.assertIn('Recovery work',html);self.assertNotIn('New workspace',html)
        self.assertNotIn('/factory/',html);self.assertNotIn('/workspaces/',html)
