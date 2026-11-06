"""F43 synthetic disclosure controls; no owner accounting oracle claimed."""
import copy
import json
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, IntegrityError, DatabaseError
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.core.models import Evidence
from apps.finance import group_forecast as group, forecast_documents
from apps.documents.controlled import register_template, reserve_publication, create_version
from apps.documents.models import Publication, PublicationReceipt, ControlledReview, Version
from apps.documents.delivery import run_publication_once
from apps.documents.contracts import digest
from apps.policy.services import register_reference, active_component, reference_values
from adapters.publications import PublicationTimeoutAfterAccept
from .forecast_helpers import fixture, run, review, payload
from .billing_helpers import evidence, policy
from .document_helpers import artifact
from .helpers import rev, activate


def configured():
    a,c,_=fixture();value=payload(a,c)
    value['items'][1].update(key='RESTRICTED_X',source_ref='SECRET_X',owner='PRIVATE_X',amount='7391')
    r=run(a,c,value);review(a,c,r)
    reader=get_user_model().objects.create_user(username='group-reader')
    Grant.objects.create(case=c,user=reader,action='document.receive:group')
    owner=evidence(a,c,'policy_decision','Synthetic explicit group eligibility and recipients, not real policy')
    definition={'document_type':'finance_group_report','required_fields':['executive_summary','financial_metrics','bu_totals'],'audience_fields':{'group':['executive_summary','financial_metrics','bu_totals']},'internal_review_required':True}
    template=register_template(a,c.pk,'Synthetic separate group report',definition,owner.pk,rev(c))
    artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},owner)
    ref=register_reference(a,c.pk,'group:recipient','schema:psl/document-recipient/v1',{'audience':'group','user_id':reader.pk},owner.pk)
    activate(a,c,'D11.recipient_grant_refs',[ref.ref],owner)
    g={'implementation':'native_selected_items_v1','run_id':r.pk,'run_hash':r.sha256,'rows':['receipt-1'],
       'fields':['kind','residual','expected_on'],'metadata':['currency','basis','as_of'],
       'recipient_ids':[reader.pk],'reviewer_roles':['Finance'],'publisher_roles':['Finance'],
       'allow_preparer_review':True,'oracle_evidence_id':1}
    expected={'implementation':group.IMPLEMENTATION,'metadata':{'currency':'NGN','basis':'gross_cash','as_of':value['as_of']},
       'rows':[{'kind':'other_inflow','residual':'50','expected_on':value['as_of']}],
       'scope':'selected_assumptions_only_no_group_balances','execution_authorized':False}
    oracle=evidence(a,c,'forecast_group_oracle',json.dumps(expected));g['oracle_evidence_id']=oracle.pk
    projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',c))[0]);projection['group']=g
    policy(a,c,'D10.audience_projection_rules',projection)
    return a,c,r,reader,template,g,expected


class GroupForecastTests(TestCase):
    def setUp(self):
        self.a,self.c,self.r,self.reader,self.t,self.g,self.expected=configured()

    def draft(self):return group.draft(self.a,self.c.pk,self.r.pk,self.t.pk,rev(self.c))
    def approve(self,v):return group.review(self.a,self.c.pk,v.pk,'Finance','approve','Reviewed exact group content and destinations',rev(self.c))
    def reserve(self,v):return reserve_publication(self.a,self.c.pk,v.pk,rev(self.c))
    def no_secret(self,value):
        text=json.dumps(value,sort_keys=True,default=str)
        for secret in ['RESTRICTED_X','SECRET_X','PRIVATE_X','7391','opening','closing','periods','omitted_receivables']:
            self.assertNotIn(secret,text)

    def test_native_end_to_end_only_projected_content_and_minimum_recipient_access(self):
        v=self.draft();self.no_secret(v.fields['financial_metrics']);self.no_secret(v.source_manifest)
        self.assertEqual(group.check_content(v.forecastbinding),self.expected)
        self.assertEqual(v.baseline_manifest,{})
        with self.assertRaises(ValidationError):self.reserve(v)
        self.approve(v);p=self.reserve(v);run_publication_once(case_id=self.c.pk)
        p.job.refresh_from_db();self.assertEqual(p.job.status,'confirmed')
        self.assertEqual(group.verified(v)['recipient_count'],1)
        receipt=PublicationReceipt.objects.get(publication=p);self.no_secret(receipt.payload['sections'][1])
        self.assertFalse(Grant.objects.filter(user=self.reader,action='finance.read').exists())
        self.client.force_login(self.reader)
        response=self.client.get(reverse('document_inbox'));self.assertEqual(response.status_code,200)
        self.assertContains(response,'50');self.assertNotContains(response,'RESTRICTED_X');self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual(self.client.get(reverse('finance_forecast',args=[self.c.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('documents',args=[self.c.pk])).status_code,404)

    def test_absent_policy_and_aggregate_method_hold_group_only(self):
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0]);projection.pop('group')
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        with self.assertRaisesMessage(ValidationError,'owner_needed'):self.draft()
        self.assertEqual(forecast_documents.report_inputs(self.r,'internal')['audience'],'internal')
        projection['group']=dict(self.g,implementation='owner_aggregate_pending')
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        with self.assertRaisesMessage(ValidationError,'financial oracle'):self.draft()

    def test_allowed_native_unknown_and_excluded_amount_independence(self):
        original=group.project(self.r.result,self.g);changed=copy.deepcopy(self.r.result)
        changed['items'][1]['residual']='999999';changed['periods'][0]['closing']='999999'
        self.assertEqual(group.project(changed,self.g),original)
        changed['items'][0]['residual']=None
        self.assertIsNone(group.project(changed,self.g)['rows'][0]['residual'])
        with self.assertRaises(ValidationError):group.project(changed,dict(self.g,fields=['closing']))
        with self.assertRaises(ValidationError):group.project(changed,dict(self.g,rows=['absent']))
        with self.assertRaises(ValidationError):group.project(changed,dict(self.g,metadata=['currency','basis']))

    def test_generic_draft_cannot_bypass_group_boundary(self):
        with self.assertRaises(ValidationError):
            create_version(self.a,self.c.pk,self.t.pk,'Unsafe','group',{'financial_metrics':{'text':'SECRET_X','evidence_ids':[]}},rev(self.c))

    def test_supplied_oracle_mismatch_holds(self):
        bad=evidence(self.a,self.c,'forecast_group_oracle',json.dumps({'rows':['SECRET_X']}))
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0]);projection['group']['oracle_evidence_id']=bad.pk
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        with self.assertRaisesMessage(ValidationError,'oracle'):self.draft()

    def test_exact_policy_replacement_invalidates_review_and_delivery(self):
        v=self.draft();self.approve(v);p=self.reserve(v)
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0])
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        run_publication_once(case_id=self.c.pk);p.job.refresh_from_db();self.assertEqual(p.job.status,'held')
        self.assertFalse(PublicationReceipt.objects.filter(publication=p).exists())
        with self.assertRaises(ValidationError):group.approved(v)

    def test_revoked_review_and_recipient_grants_hold(self):
        v=self.draft();self.approve(v)
        Grant.objects.filter(user=self.a,case=self.c,action='document.review_controlled').update(active=False)
        with self.assertRaises(PermissionDenied):self.reserve(v)
        Grant.objects.filter(user=self.a,case=self.c,action='document.review_controlled').update(active=True)
        p=self.reserve(v);Grant.objects.filter(user=self.reader,action='document.receive:group').update(active=False)
        run_publication_once(case_id=self.c.pk);p.job.refresh_from_db();self.assertEqual(p.job.status,'held')
        self.assertFalse(PublicationReceipt.objects.filter(publication=p).exists())

    def test_timeout_reconciles_original_receipts_once(self):
        v=self.draft();self.approve(v);p=self.reserve(v)
        run_publication_once(adapter=PublicationTimeoutAfterAccept(),case_id=self.c.pk)
        p.job.refresh_from_db();self.assertEqual(p.job.status,'unknown');self.assertEqual(PublicationReceipt.objects.count(),1)
        with self.assertRaisesMessage(ValidationError,'Reconcile'):group.verified(v)
        run_publication_once(case_id=self.c.pk);p.job.refresh_from_db();self.assertEqual(p.job.status,'confirmed')
        self.assertEqual(PublicationReceipt.objects.count(),1);self.assertEqual(group.verified(v)['publication'],p.pk)

    def test_direct_database_publication_requires_group_review(self):
        v=self.draft()
        with self.assertRaises(DatabaseError),transaction.atomic():
            Publication.objects.create(version=v,actor=self.a,review=None,policies={},recipient_ids=[self.reader.pk],retention_days=30,operation_key='unsafe-group')

    def test_same_run_source_and_currentness_are_mandatory(self):
        from .forecast_helpers import scenario
        v=self.draft();self.approve(v)
        scenario(self.a,self.c,reference=self.r.scenario.reference)
        with self.assertRaises(ValidationError):self.reserve(v)

    def test_console_is_read_only_and_group_recipient_is_not_management(self):
        self.client.force_login(self.a)
        before=(Version.objects.count(),ControlledReview.objects.count(),Evidence.objects.count())
        response=self.client.get(reverse('finance_forecast',args=[self.c.pk]))
        self.assertEqual(response.status_code,200);self.assertContains(response,'Group cash report work')
        self.assertEqual(before,(Version.objects.count(),ControlledReview.objects.count(),Evidence.objects.count()))
        self.assertEqual(response['Cache-Control'],'no-store')
        self.assertFalse(Grant.objects.filter(user=self.reader,action='document.receive:management').exists())

    def raw_context(self,v):
        from apps.documents.controlled import guard_reserve_publication
        _,ctx,_=guard_reserve_publication(self.a,self.c,v.pk)
        return dict(version=v,actor=self.a,review_id=ctx['review'],policies=ctx['policies'],recipient_ids=ctx['recipients'],retention_days=ctx['retention_days'],operation_key='synthetic-direct-group')

    def test_hidden_cache_comment_and_metadata_injection_rejected_by_service_and_sql(self):
        from apps.finance.models import ForecastBinding
        v=self.draft();r=self.approve(v);kwargs=self.raw_context(v)
        for channel in ['payload','fields','source_manifest','baseline_manifest']:
            with self.subTest(channel=channel),transaction.atomic():
                data={f.name:getattr(v,f.name) for f in Version._meta.fields if f.name not in ['id','created_at']}
                data['number']=2
                data[channel]=copy.deepcopy(data[channel])
                if isinstance(data[channel],dict):data[channel]['cache_comments_hidden_rows']='RESTRICTED_X SECRET_X PRIVATE_X 7391'
                else:data[channel].append({'hidden_rows':'RESTRICTED_X 7391'})
                data['payload_sha256']=digest(data['payload']);bad=Version.objects.create(**data)
                v.document.current=bad;v.document.save(update_fields=['current'])
                binding=ForecastBinding.objects.create(version=bad,run=self.r,snapshot=v.forecastbinding.snapshot)
                bad_review=ControlledReview.objects.create(version=bad,actor=self.a,verdict='approve',note='synthetic forged review',authority=r.authority,payload_sha256=bad.payload_sha256)
                with self.assertRaises(ValidationError):group.check_content(binding)
                with self.assertRaises(DatabaseError),transaction.atomic():
                    Publication.objects.create(**dict(kwargs,version=bad,review_id=bad_review.pk))
                transaction.set_rollback(True)

    def test_direct_sql_revoked_role_assignment_and_reviewer_grant_rejected(self):
        from apps.policy.models import PolicyState
        v=self.draft();self.approve(v);kwargs=self.raw_context(v)
        config=active_component('D05.role_principal_assignments',self.c)
        with transaction.atomic():
            PolicyState.objects.create(configuration=config,state='revoked',actor=self.a)
            with self.assertRaises(DatabaseError),transaction.atomic():Publication.objects.create(**kwargs)
            transaction.set_rollback(True)
        Grant.objects.filter(case=self.c,user=self.a,action='document.review_controlled').update(active=False)
        with self.assertRaises(DatabaseError),transaction.atomic():Publication.objects.create(**kwargs)

    def test_direct_sql_changed_oracle_policy_and_destination_rejected(self):
        v=self.draft();self.approve(v);kwargs=self.raw_context(v)
        with self.assertRaises(DatabaseError),transaction.atomic():Publication.objects.create(**dict(kwargs,recipient_ids=[self.a.pk]))
        other=evidence(self.a,self.c,'forecast_group_oracle',json.dumps(self.expected))
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0]);projection['group']['oracle_evidence_id']=other.pk
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        with self.assertRaises(ValidationError):self.reserve(v)
        with self.assertRaises(DatabaseError),transaction.atomic():Publication.objects.create(**kwargs)

    def test_policy_reduction_and_recipient_removal_hide_historical_receipts(self):
        v=self.draft();self.approve(v);p=self.reserve(v);run_publication_once(case_id=self.c.pk)
        receipt=PublicationReceipt.objects.get(publication=p)
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0])
        projection['group']['fields']=['kind']
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        with self.assertRaises(PermissionDenied):group.recipient_access(self.reader,receipt)
        self.client.force_login(self.reader);self.assertNotContains(self.client.get(reverse('document_inbox')),'Selected group cash forecast')
        projection['group']['recipient_ids']=[self.a.pk]
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        with self.assertRaises(PermissionDenied):group.recipient_access(self.reader,receipt)
        self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(),1)

    def test_absent_disclosure_oracle_holds_only_group_and_full_payload_is_clean(self):
        from .forecast_helpers import publication
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0]);projection['group']['oracle_evidence_id']=999999
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        with self.assertRaises(ValidationError):self.draft()
        for audience in ['internal','management']:self.assertEqual(forecast_documents.report_inputs(self.r,audience)['audience'],audience)
        projection['group']=self.g;policy(self.a,self.c,'D10.audience_projection_rules',projection)
        v=self.draft();self.approve(v);p=self.reserve(v);run_publication_once(case_id=self.c.pk)
        receipt=PublicationReceipt.objects.get(publication=p)
        stored={'payload':v.payload,'fields':v.fields,'source_manifest':v.source_manifest,'baseline_manifest':v.baseline_manifest,
                'binding':v.forecastbinding.snapshot,'receipt':receipt.payload,'projection_evidence':Evidence.objects.get(pk=v.source_manifest[0]['id']).body}
        for secret in ['RESTRICTED_X','SECRET_X','PRIVATE_X','7391']:
            self.assertNotIn(secret,json.dumps(stored,sort_keys=True))
        self.client.force_login(self.reader)
        page=self.client.get(reverse('document_inbox'))
        for secret in ['RESTRICTED_X','SECRET_X','PRIVATE_X','7391']:self.assertNotContains(page,secret)

    def test_direct_sql_unassigned_reviewer_and_publisher_are_not_authority(self):
        v=self.draft();r=self.approve(v);kwargs=self.raw_context(v)
        for action in ['document.review_controlled','finance.read','document.publish','finance.publish']:
            Grant.objects.create(case=self.c,user=self.reader,action=action)
        with self.assertRaises(PermissionDenied):group.review(self.reader,self.c.pk,v.pk,'Finance','approve','Not an assigned reviewer',rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():Publication.objects.create(**dict(kwargs,actor=self.reader))
        forged=ControlledReview.objects.create(version=v,actor=self.reader,verdict='approve',note='Synthetic unassigned reviewer',authority=r.authority,payload_sha256=v.payload_sha256)
        with self.assertRaises(DatabaseError),transaction.atomic():Publication.objects.create(**dict(kwargs,review_id=forged.pk))

    def test_preparer_review_choice_and_cancelled_delivery_remain_explicit(self):
        from apps.documents.delivery import operate_publication
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0]);projection['group']['allow_preparer_review']=False
        policy(self.a,self.c,'D10.audience_projection_rules',projection);v=self.draft()
        with self.assertRaises(PermissionDenied):self.approve(v)
        projection['group']['allow_preparer_review']=True;policy(self.a,self.c,'D10.audience_projection_rules',projection)
        v=self.draft();self.approve(v);p=self.reserve(v)
        operate_publication(self.a,self.c.pk,p.job.pk,'cancel','Synthetic owner cancels before local delivery',rev(self.c))
        self.assertFalse(run_publication_once(case_id=self.c.pk));self.assertFalse(PublicationReceipt.objects.filter(publication=p).exists())
        with self.assertRaises(ValidationError):group.verified(v)

    def test_generic_workspace_document_and_agent_grants_do_not_disclose_native_forecast(self):
        from apps.agents.services import extract_evidence
        from apps.core.evidence_access import public_evidence,restricted
        # A generic item source is also restricted once it belongs to the exact
        # captured forecast inventory, not only evidence named forecast_input.
        source=Evidence.objects.get(pk=self.run_source_id())
        self.assertTrue(restricted(source));self.assertFalse(public_evidence(Evidence.objects.all()).filter(pk=source.pk).exists())
        owner=evidence(self.a,self.c,'policy_decision','Synthetic internal template')
        definition={'document_type':'finance_report','required_fields':['executive_summary','financial_metrics','bu_totals'],
                    'audience_fields':{'internal':['executive_summary','financial_metrics','bu_totals']},'internal_review_required':False}
        t=register_template(self.a,self.c.pk,'Internal forecast only',definition,owner.pk,rev(self.c))
        internal=forecast_documents.draft(self.a,self.c.pk,self.r.pk,t.pk,'internal',rev(self.c))
        self.assertIn('7391',json.dumps(internal.payload))
        v=self.draft();self.approve(v);p=self.reserve(v);run_publication_once(case_id=self.c.pk)
        for action in ['case.read','document.read','document.draft','agent.extract']:
            Grant.objects.create(case=self.c,user=self.reader,action=action)
        self.client.force_login(self.reader)
        for url in [reverse('case',args=[self.c.pk]),reverse('documents',args=[self.c.pk])]:
            response=self.client.get(url);self.assertEqual(response.status_code,200)
            for secret in ['RESTRICTED_X','SECRET_X','PRIVATE_X','7391']:self.assertNotContains(response,secret)
        for eid in [self.r.scenario.evidence_id,source.pk,internal.source_manifest[0]['id'],v.source_manifest[0]['id']]:
            with self.assertRaises(ValidationError):extract_evidence(self.reader,self.c.pk,eid,'F43')
        fields={'executive_summary':{'text':'Unsafe copied source','evidence_ids':[source.pk]}}
        with self.assertRaises(ValidationError):create_version(self.reader,self.c.pk,t.pk,'No private sources','internal',fields,rev(self.c))
        with self.assertRaises(TypeError):create_version(self.reader,self.c.pk,t.pk,'No public bypass','internal',fields,rev(self.c),authorized_restricted_source_ids=[source.pk])
        self.assertEqual(self.client.get(reverse('finance_forecast',args=[self.c.pk])).status_code,403)
        self.assertContains(self.client.get(reverse('document_inbox')),'Selected group cash forecast')

    def run_source_id(self):return self.r.scenario.payload['items'][0]['evidence_id']

    def test_native_group_helper_cannot_substitute_other_same_case_private_source(self):
        from .forecast_helpers import scenario
        from apps.finance import forecast
        from apps.documents.controlled import _create_version
        other=scenario(self.a,self.c,reference='OTHER-PRIVATE-SCENARIO')
        other_run=forecast.prepare(self.a,self.c.pk,other.pk,rev(self.c));review(self.a,self.c,other_run)
        with self.assertRaisesMessage(ValidationError,'exact reviewed'):group.draft(self.a,self.c.pk,other_run.pk,self.t.pk,rev(self.c))
        with self.assertRaises(ValidationError):
            _create_version(self.a,self.c.pk,self.t.pk,'Invalid internal source set','group',{'financial_metrics':{'text':'x','evidence_ids':[other.evidence_id]}},rev(self.c),authorized_restricted_source_ids=[self.r.scenario.evidence_id])
        with self.assertRaises(TypeError):group.draft(self.a,self.c.pk,self.r.pk,self.t.pk,rev(self.c),evidence_id=other.evidence_id)

    def test_changed_native_recipient_policy_hides_original_receipt(self):
        v=self.draft();self.approve(v);p=self.reserve(v);run_publication_once(case_id=self.c.pk)
        receipt=PublicationReceipt.objects.get(publication=p)
        owner=evidence(self.a,self.c,'policy_decision','Synthetic replacement group recipient policy')
        other=get_user_model().objects.create_user(username='different-group-reader')
        Grant.objects.create(case=self.c,user=other,action='document.receive:group')
        ref=register_reference(self.a,self.c.pk,'group:replacement-recipient','schema:psl/document-recipient/v1',{'audience':'group','user_id':other.pk},owner.pk)
        activate(self.a,self.c,'D11.recipient_grant_refs',[ref.ref],owner)
        with self.assertRaises(PermissionDenied):group.recipient_access(self.reader,receipt)
        self.client.force_login(self.reader);self.assertNotContains(self.client.get(reverse('document_inbox')),'Selected group cash forecast')
        self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(),1)
