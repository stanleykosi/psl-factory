from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.policy import impact
from apps.policy.recognition_validators import REVIEW
from apps.finance.recognition_models import RecognitionRecord
from adapters import policy_impact as adapter
from tests.recognition_helpers import fixture, reviewed, policy
from tests.helpers import rev

KEY='finance.recognition_records'
class RecognitionPolicyImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=fixture();cls.record=reviewed(cls.f)
    def successor(self):
        f=self.f
        return policy(f['actor'],f['case'],REVIEW,deepcopy(f['config']['review']),f['evidence']['policy_decision'])
    def capture(self):
        f=self.f;new=self.successor()
        return impact.capture(f['actor'],f['case'].pk,f['review_policy'].pk,new.pk,[KEY],f['evidence']['policy_decision'].pk,'Bounded metadata reassessment')
    def test_exact_authority_and_review_policy_consumers(self):
        f=self.f
        self.assertEqual(set(adapter.query(f['authority'],KEY).values_list('kind',flat=True)),{'attest','review'})
        self.assertEqual(list(adapter.query(f['review_policy'],KEY).values_list('pk',flat=True)),[self.record.pk])
        self.assertFalse(adapter.query(self.successor(),KEY).exists())
    def test_private_metadata_and_no_business_effect(self):
        f=self.f;before=list(RecognitionRecord.objects.values())
        report=impact.page(f['actor'],f['case'].pk,f['review_policy'].pk,KEY)
        value=report['records'][0]
        self.assertTrue(value['metadata_only']);self.assertTrue(value['native_current'])
        self.assertFalse(value['business_approval']);self.assertFalse(value['accounting_effects_performed'])
        for word in ['Explicit synthetic human statement','operation_key','contact_context','access_context']:
            self.assertNotIn(word,str(report))
        self.assertEqual(before,list(RecognitionRecord.objects.values()))
    def test_revoked_domain_access_precedes_query(self):
        f=self.f;Grant.objects.filter(case=f['case'],user=f['actor'],action='recognition.read').update(active=False)
        with patch.object(adapter,'query',side_effect=AssertionError('private lookup forbidden')):
            with self.assertRaises(PermissionDenied):impact.page(f['actor'],f['case'].pk,f['review_policy'].pk,KEY)
    def test_successor_marks_native_record_noncurrent_without_mutation(self):
        f=self.f;self.successor();before=list(RecognitionRecord.objects.values())
        result=impact.page(f['actor'],f['case'].pk,f['review_policy'].pk,KEY)['records'][0]
        self.assertFalse(result['native_current']);self.assertEqual(before,list(RecognitionRecord.objects.values()))
    def test_engineering_assessment_agent_and_review_do_not_attest(self):
        from apps.agents.policy_impact import investigate
        f=self.f;row=self.capture();before=list(RecognitionRecord.objects.values())
        user=get_user_model().objects.create_user(username='impact792-reviewer')
        Grant.objects.bulk_create([Grant(case=f['case'],user=user,action=g.action) for g in Grant.objects.filter(case=f['case'],user=f['actor'])])
        impact.review(user,f['case'].pk,row.pk,'accept',f['evidence']['policy_decision'].pk,'Independent metadata assessment')
        result=investigate(user,f['case'].pk,row.pk)
        self.assertFalse(result['business_approval']);self.assertEqual(result['effect_tools'],[])
        self.assertNotIn('Explicit synthetic human statement',str(result))
        self.assertEqual(before,list(RecognitionRecord.objects.values()))
    def test_native_successor_packet_stales_assessment(self):
        from apps.finance import recognition
        f=self.f;row=self.capture();self.assertTrue(impact.inspect(f['actor'],f['case'].pk,row.pk)['current'])
        recognition.prepare(f['actor'],f['case'].pk,f['packet'].reference,deepcopy(f['packet'].payload),f['evidence']['completion'].pk,rev(f['case']))
        self.assertFalse(impact.inspect(f['actor'],f['case'].pk,row.pk)['current'])
    def test_unrelated_case_configuration_has_no_matches(self):
        from tests.helpers import setup_case,prepared
        from apps.policy.services import resolve
        a,c=setup_case(username='impact792-other');e=prepared(a,c)
        config=resolve('D05.role_principal_assignments',c).configuration
        self.assertFalse(adapter.query(config,KEY).exists())
    def test_ui_choices_and_route_are_domain_scoped(self):
        from apps.policy.impact_views import choices
        from django.urls import reverse
        f=self.f
        self.assertIn(KEY,dict(choices(f['actor'],f['case'])))
        self.assertTrue(reverse(adapter.ROUTES[KEY],args=[f['case'].pk]))
        Grant.objects.filter(case=f['case'],user=f['actor'],action='recognition.read').update(active=False)
        self.assertNotIn(KEY,dict(choices(f['actor'],f['case'])))
    def test_exact_d05_authority_pin_matches_both_human_records(self):
        from apps.policy.services import resolve
        f=self.f;config=resolve('D05.role_principal_assignments',f['case']).configuration
        self.assertEqual(set(adapter.query(config,KEY).values_list('kind',flat=True)),{'attest','review'})
        for row in adapter.query(config,KEY):self.assertEqual(row.authority[config.component],config.pk)
    def test_revoked_reader_cannot_inspect_saved_assessment_or_agent(self):
        from apps.agents.policy_impact import investigate
        f=self.f;row=self.capture()
        Grant.objects.filter(case=f['case'],user=f['actor'],action='recognition.read').update(active=False)
        for action in [impact.inspect,investigate]:
            with self.assertRaises(PermissionDenied):action(f['actor'],f['case'].pk,row.pk)
    def test_sql_closed_list_rejects_unknown_duplicate_empty_and_excess(self):
        from django.db import transaction,DatabaseError
        from apps.policy.models import ImpactAssessment
        from apps.policy.impact import digest
        row=self.capture()
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ['id','created_at']}
        for index,keys in enumerate([['finance.unknown'],[KEY,KEY],[],[KEY]*18]):
            data=dict(base,adapters=keys,operation_key=digest(['invalid-impact792',index]))
            with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.create(**data)
