"""Native policy-change replay contrasts; no changed production semantics."""
from copy import deepcopy
from django.test import TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from apps.core.models import Audit, Evidence
from apps.finance import recognition as native, recognition_preview as preview
from apps.finance.recognition_models import RecognitionRecord
from apps.policy.services import transition
from apps.policy.recognition_validators import AUTHORITY
from adapters.pilot_guards import check
from .recognition_helpers import fixture, policy
from .helpers import rev

class RecognitionPolicyReplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()

    def setUp(self):
        f=self.f;self.original=self.capture('original791','original private note791')
        # Capture contrasting proposals while actual authority is still current.
        self.changed=self.capture('original791','changed private note791')
        self.fresh=self.capture('fresh791','fresh private note791')
        self.record=self.command('original791','original private note791')

    def capture(self,key,note):
        f=self.f
        return preview.capture(f['actor'],f['case'].pk,f['packet'].pk,key,f['evidence']['completion'].pk,note,rev(f['case']))

    def command(self,key,note):
        f=self.f
        return native.record(f['actor'],f['case'].pk,f['packet'].pk,'attest',key,f['evidence']['completion'].pk,note,rev(f['case']))

    def observe(self,row):
        f=self.f
        return check(f['actor'],f['case'],{'operation':'recognition.attest','user_id':f['actor'].pk,'arguments':{
            'expected_revision':rev(f['case']),'recognition_input_id':row.pk,'recognition_input_sha256':row.sha256}})

    def state(self):
        return (list(RecognitionRecord.objects.order_by('pk').values()),list(Evidence.objects.order_by('pk').values()),
            list(Audit.objects.order_by('pk').values()),rev(self.f['case']))

    def assert_contrast(self,new_error):
        f=self.f;before=self.state()
        # Return of the immutable original is historical recovery, not current authority.
        self.assertEqual(self.command('original791','original private note791').pk,self.record.pk)
        result=self.observe(self.original)
        self.assertEqual(result['state'],'EXACT_RECORDED_REPLAY_ONLY')
        self.assertEqual(result['existing_record'],self.record.pk)
        self.assertFalse(result['business_approval']);self.assertFalse(result['effects_scheduled'])
        self.assertFalse(result['separately_entered_intent_bound'])
        with self.assertRaises(new_error):native.record_current(self.record)
        with self.assertRaises(new_error):
            native.record(f['actor'],f['case'].pk,f['packet'].pk,'request','request791',
                f['evidence']['completion'].pk,'not new authority',rev(f['case']))
        # Changed intent with the original key is never an idempotent retry.
        with self.assertRaisesMessage(ValidationError,'Operation key reused for changed intent'):
            self.command('original791','changed private note791')
        with self.assertRaises(new_error):self.command('fresh791','fresh private note791')
        with self.assertRaises(new_error):self.capture('later791','later private proposal')
        for row in [self.changed,self.fresh]:
            held=self.observe(row)
            self.assertEqual(held['state'],'HELD');self.assertFalse(held['effects_scheduled'])
            self.assertNotIn('existing_record',held)
            for text in ['original private note791','changed private note791','fresh private note791']:
                self.assertNotIn(text,str(held))
        self.assertEqual(self.state(),before)
        self.assertEqual(RecognitionRecord.objects.count(),1)

    def test_exact_replay_after_authority_policy_revocation_is_not_new_authority(self):
        f=self.f;transition(f['actor'],f['authority'].pk,'revoked')
        self.assert_contrast(ValidationError)

    def test_exact_replay_after_successor_removes_principal_is_not_new_authority(self):
        f=self.f;replacement=deepcopy(f['config']['authority'])
        replacement['assignments']=[r for r in replacement['assignments'] if r['purpose']!='attest']
        successor=policy(f['actor'],f['case'],AUTHORITY,replacement,f['evidence']['policy_decision'])
        self.assertNotEqual(successor.pk,f['authority'].pk)
        self.assert_contrast(PermissionDenied)
