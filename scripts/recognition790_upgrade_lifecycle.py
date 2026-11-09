"""One-shot populated0019→0020 native upgrade, only under reviewed owned harness."""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

class RecognitionPreviewUpgradeTests(TransactionTestCase):
    def test_populated_old_planning_binding_survives_one_way_upgrade(self):
        from scripts.recognition790_upgrade import TARGET, PREVIOUS, upgrade
        from tests.planning_helpers import fixture as planning_fixture, observe
        from tests.test_pilot_preflight import selection
        from tests.test_document_guard import payload
        from tests.helpers import rev
        from apps.policy import pilot, pilot_bindings
        from apps.policy.models import PilotBinding
        self.assertEqual(os.environ.get('RUN790_RUNTIME_CLEARANCE'),'coordinator-cleared-recognition790')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations()
        self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_RECOGNITION790_UPGRADE_EVIDENCE'])
        self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        f=planning_fixture(username='recognition790-old-planning');observe(f);a,c=f['a'],f['c']
        cv=selection(a,c);cv['operations']=['planning.readiness'];cv['participants']=[{'user_id':a.pk,'actions':['planning.prepare']}]
        contract=pilot.configure(a,c.pk,cv)
        selected=payload(a,c,type('Subject',(),{'pk':1})())
        selected['guards']=[{'operation':'planning.readiness','user_id':a.pk,'arguments':{'expected_revision':rev(c),'planning_packet_id':f['packet'].pk}}]
        binding=pilot_bindings.configure(a,c.pk,contract.pk,selected)
        before=dict(PilotBinding.objects.values().get(pk=binding.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(PilotBinding.objects.values().get(pk=binding.pk)),before)
        from tests.recognition_helpers import fixture
        from apps.finance import recognition_preview as preview
        from apps.finance.recognition_models import RecognitionRecord
        from adapters.pilot_guards import check
        from apps.core.models import Audit, Evidence
        from apps.workflows.models import Outbox
        f=fixture();a,c=f['actor'],f['case']
        source=preview.capture(a,c.pk,f['packet'].pk,'upgrade-private-key',f['evidence']['completion'].pk,'upgrade-private-note',rev(c))
        cv=selection(a,c);cv['operations']=['recognition.attest'];cv['participants']=[{'user_id':a.pk,'actions':['recognition.attest']}]
        contract=pilot.configure(a,c.pk,cv)
        guard={'operation':'recognition.attest','user_id':a.pk,'arguments':{'expected_revision':rev(c),'recognition_input_id':source.pk,'recognition_input_sha256':source.sha256}}
        selected=payload(a,c,type('Subject',(),{'pk':1})());selected['guards']=[guard]
        new=pilot_bindings.configure(a,c.pk,contract.pk,selected)
        self.assertEqual(new.payload['guards'][0]['operation'],'recognition.attest')
        guard['arguments']['expected_revision']=rev(c)
        before=(Audit.objects.count(),Evidence.objects.count(),Outbox.objects.count(),RecognitionRecord.objects.count(),rev(c))
        result=check(a,c,guard)
        self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertFalse(result['business_approval']);self.assertFalse(result['effects_scheduled'])
        self.assertNotIn('upgrade-private-key',str(result));self.assertNotIn('upgrade-private-note',str(result))
        self.assertEqual(before,(Audit.objects.count(),Evidence.objects.count(),Outbox.objects.count(),RecognitionRecord.objects.count(),rev(c)))
