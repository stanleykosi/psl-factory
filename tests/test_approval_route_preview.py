"""Source-only native definitions; execution requires separately approved PostgreSQL run."""
from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from apps.core.models import Audit, Case
from apps.identity.models import Grant
from apps.pmo import approval_routing as routing
from apps.pmo.models import ApprovalRouteJob, ApprovalRouteReceipt
from adapters import approval_route_guard as preview
from .approval_helpers import fixture, policy
from apps.policy.approval_validators import CONTRACTS
from apps.pmo import approvals


class ApprovalRoutePreviewTests(TestCase):
    def setUp(self):
        self.f = fixture('approval-preview')

    def reminders(self):
        f=self.f;value=f['v']['contracts'];value['contracts'][0].update(reminders_enabled=True,maximum_reminders=1)
        policy(f,CONTRACTS,value)
        approvals.review_contract(f['owner'],f['case'].pk,'qa_exit',f['e']['approval_contract_review'].pk)

    def check(self, purpose='request'):
        f=self.f
        return preview.guard(f['actor'], f['case'], f['request'].pk, purpose)

    def test_ready_observation_has_no_effect_or_source_payload(self):
        f=self.f; before=(Audit.objects.count(),Case.objects.get(pk=f['case'].pk).revision)
        with patch.object(routing,'reserve',side_effect=AssertionError('No speculative command')):
            request,context,existing=self.check()
        self.assertEqual(request.pk,f['request'].pk);self.assertIsNone(existing)
        self.assertFalse(context['approval_granted']);self.assertFalse(context['effects_scheduled'])
        self.assertNotIn('subject',context);self.assertNotIn('source_owner',context)
        self.assertFalse(ApprovalRouteJob.objects.exists());self.assertFalse(ApprovalRouteReceipt.objects.exists())
        self.assertEqual(before,(Audit.objects.count(),Case.objects.get(pk=f['case'].pk).revision))

    def test_existing_exact_request_reuses_native_reservation(self):
        f=self.f;job=routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
        self.assertEqual(self.check()[2].pk,job.pk)
        self.assertEqual(routing.reserve(f['actor'],f['case'].pk,f['request'].pk).pk,job.pk)
        self.assertEqual(ApprovalRouteJob.objects.count(),1)

    def test_outstanding_reminder_is_held(self):
        self.reminders()
        f=self.f;routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
        with self.assertRaises(ValidationError):self.check('reminder')

    def test_no_receipt_reminder_is_held(self):
        self.reminders()
        with self.assertRaises(ValidationError):self.check('reminder')

    def test_revoked_actor_or_owner_is_held(self):
        f=self.f
        for user,action in [(f['actor'],'approval.route'),(f['owner'],'approval.receive')]:
            Grant.objects.filter(case=f['case'],user=user,action=action).update(active=False)
            with self.assertRaises(PermissionDenied):self.check()
            Grant.objects.filter(case=f['case'],user=user,action=action).update(active=True)

    def test_observer_requires_approval_read(self):
        f=self.f;Grant.objects.filter(case=f['case'],user=f['actor'],action='approval.read').update(active=False)
        with self.assertRaises(PermissionDenied):preview.head(f['actor'],f['case'],f['request'].pk)

    def test_foreign_request_and_nonproject_are_held(self):
        f=self.f;other=fixture('approval-preview-foreign')
        with self.assertRaises(ValidationError):preview.guard(f['actor'],f['case'],other['request'].pk,'request')
        f['case'].kind='support'
        with self.assertRaises(ValidationError):self.check()

    def test_receipt_interval_and_budget_are_not_skipped(self):
        self.reminders();f=self.f
        job=routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
        routing.run_once(case_id=f['case'].pk,job_id=job.pk)
        receipt=ApprovalRouteReceipt.objects.get(job=job)
        original_created_at=receipt.created_at
        boundary=original_created_at+timedelta(seconds=3600)
        with patch('apps.pmo.approval_routing.timezone.now',return_value=boundary-timedelta(microseconds=1)):
            with self.assertRaisesMessage(ValidationError,'Confirmed receipt and configured reminder interval required'):
                self.check('reminder')
        with patch('apps.pmo.approval_routing.timezone.now',return_value=boundary):
            self.assertIsNone(self.check('reminder')[2])
            reminder=routing.reserve(f['actor'],f['case'].pk,f['request'].pk,'reminder')
            routing.run_once(case_id=f['case'].pk,job_id=reminder.pk)
        reminder_receipt=ApprovalRouteReceipt.objects.get(job=reminder)
        with patch('apps.pmo.approval_routing.timezone.now',return_value=reminder_receipt.created_at+timedelta(seconds=3600)):
            with self.assertRaisesMessage(ValidationError,'Configured reminder budget exhausted'):
                self.check('reminder')
        receipt.refresh_from_db();reminder_receipt.refresh_from_db()
        self.assertEqual(receipt.created_at,original_created_at)
        self.assertEqual(reminder_receipt.created_at,boundary)
        self.assertEqual(ApprovalRouteReceipt.objects.count(),2)

    def test_superseded_request_is_held(self):
        f=self.f;r=f['request']
        approvals.create_request(f['actor'],f['case'].pk,r.reference,f['candidate'].pk,'qa_exit','BUILD-2','RELEASE-2',f['e']['approval_request'].pk,predecessor=r.pk)
        with self.assertRaises(ValidationError):self.check()

    def selection(self):
        from .helpers import rev
        f=self.f
        return {'operation':'approval.route','user_id':f['actor'].pk,'arguments':{'expected_revision':rev(f['case']),'approval_request_id':f['request'].pk,'approval_purpose':'request'}}

    def test_registry_revision_and_existing_reservation_no_effects(self):
        from adapters.pilot_guards import check
        f=self.f;g=self.selection();before=Audit.objects.count()
        result=check(f['actor'],f['case'],g)
        self.assertEqual(result['state'],'READY_AT_OBSERVATION');self.assertFalse(result['business_approval'])
        self.assertFalse(ApprovalRouteJob.objects.exists());self.assertEqual(before,Audit.objects.count())
        g['arguments']['expected_revision']+=1
        self.assertEqual(check(f['actor'],f['case'],g)['state'],'HELD')
        job=routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
        result=check(f['actor'],f['case'],self.selection())
        self.assertEqual(result['state'],'EXISTING_RESERVATION_SOURCE_RECOVERY');self.assertEqual(result['existing_reservation'],job.pk)

    def test_binding_ui_agent_and_sql_closed_variant(self):
        from copy import deepcopy
        from django.db import transaction,DatabaseError
        from apps.policy import pilot,pilot_bindings,pilot_binding_validators
        from apps.policy.models import PilotBinding
        from apps.policy.pilot_binding_views import BindingForm
        from .test_pilot_preflight import selection
        from .test_document_guard import payload
        from apps.agents.pilot import investigate
        f=self.f;a=f['actor'];c=f['case'];g=self.selection();contract_value=selection(a,c)
        contract_value['operations']=['approval.route'];contract_value['participants']=[{'user_id':a.pk,'actions':['approval.route']}]
        contract=pilot.configure(a,c.pk,contract_value)
        value=payload(a,c,type('Subject',(),{'pk':1})());value['guards']=[g]
        binding=pilot_bindings.configure(a,c.pk,contract.pk,value)
        self.assertEqual(binding.payload['guards'][0]['operation'],'approval.route')
        form=BindingForm(a,contract);self.assertEqual(form.fields['approval_request_id'].label_from_instance(f['request']),'#'+str(f['request'].pk))
        observation=pilot.capture(a,c.pk,contract.pk);report=investigate(a,c.pk,observation.pk)
        import json
        self.assertNotIn(f['request'].reference,json.dumps(report,default=str))
        self.assertFalse(ApprovalRouteJob.objects.exists());self.assertFalse(ApprovalRouteReceipt.objects.exists())
        for key,bad in [('approval_request_id',True),('approval_request_id',1.5),('approval_purpose','approve'),('approval_purpose',None),('approval_request_id',None),('expected_revision',None),('unexpected',1)]:
            raw=deepcopy(value);raw['guards'][0]['arguments'][key]=bad
            with self.assertRaises(ValidationError):pilot_binding_validators.validate(contract,raw)
            with self.assertRaises(DatabaseError),transaction.atomic():PilotBinding.objects.create(contract=contract,actor=a,payload=raw,sha256='a'*64)
        for key in ['approval_request_id','approval_purpose','expected_revision']:
            raw=deepcopy(value);del raw['guards'][0]['arguments'][key]
            with self.assertRaises(ValidationError):pilot_binding_validators.validate(contract,raw)
            with self.assertRaises(DatabaseError),transaction.atomic():PilotBinding.objects.create(contract=contract,actor=a,payload=raw,sha256='c'*64)
        other=fixture('approval-binding-foreign');raw=deepcopy(value);raw['guards'][0]['arguments']['approval_request_id']=other['request'].pk
        with self.assertRaises(DatabaseError),transaction.atomic():PilotBinding.objects.create(contract=contract,actor=a,payload=raw,sha256='b'*64)
        Grant.objects.filter(case=c,user=a,action='approval.read').update(active=False)
        self.assertFalse(BindingForm(a,contract).fields['approval_request_id'].queryset.exists())
        with self.assertRaises(PermissionDenied):pilot_bindings.configure(a,c.pk,contract.pk,value)
