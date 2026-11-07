"""F42 continuation is a reviewed expectation, not fresh external support."""
import copy
import json
from datetime import date
from unittest.mock import patch
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.test import TestCase
from apps.finance import forecast, forecast_documents, group_forecast
from apps.finance.models import ForecastRun, ForecastReview
from apps.identity.models import Grant
from apps.agents.forecast import investigate
from .forecast_helpers import fixture, payload, scenario, review, publication
from .billing_helpers import evidence, policy
from .helpers import rev


class ForecastContinuationTests(TestCase):
    def setUp(self):
        self.a,self.c,self.m=fixture()

    def initial(self,state=None):
        with patch('django.utils.timezone.localdate',return_value=date(2026,9,15)):
            value=payload(self.a,self.c);value['items']=value['items'][:1]
            if state is not None:value['items'][0]['uncertainty']=state
            s=scenario(self.a,self.c,value);r=forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c));review(self.a,self.c,r)
        return r

    def carried(self,parent,month=10):
        on=date(2026,month,1)
        with patch('django.utils.timezone.localdate',return_value=on):
            value=payload(self.a,self.c);value['items']=copy.deepcopy(parent.scenario.payload['items'])
            value['items'][0]['expected_on']=f'2026-{month:02}-10'
            value['rollover']=[{'key':value['items'][0]['key'],'disposition':'carry','reason':'Explicit timing continuation; not new corroboration'}]
            s=scenario(self.a,self.c,value,parent=parent)
            return forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c))

    def test_structured_dispute_and_human_continuation_do_not_reset_source(self):
        old=self.initial('disputed');october=self.carried(old)
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            decision=review(self.a,self.c,october)
            self.assertEqual(decision.snapshot['review_kind'],'continuation_of_uncertain_expectation')
            self.assertEqual(forecast.approved(october).pk,decision.pk)
            self.assertEqual(forecast.prepare(self.a,self.c.pk,october.scenario_id,rev(self.c)).pk,october.pk)
        november=self.carried(october,11);item=november.result['items'][0];p=item['provenance']
        self.assertEqual(november.result['status'],'partial')
        self.assertEqual(p['uncertainty'],'disputed');self.assertTrue(p['continued_review_required'])
        self.assertEqual(p['carry_count'],2)
        self.assertEqual(p['original_due'],'2026-09-15')
        self.assertEqual(p['original_evidence_id'],old.result['items'][0]['evidence_id'])
        self.assertEqual(p['original_evidence_sha256'],old.result['items'][0]['provenance']['original_evidence_sha256'])
        self.assertEqual([x['expected_on'] for x in p['history']],['2026-09-15','2026-10-10','2026-11-10'])
        self.assertEqual(p['reliability'],'unknown');self.assertFalse(p['fresh_external_support'])
        self.assertEqual((item['residual'],item['matched']),('50','0'))
        self.assertFalse(november.result['execution_authorized'])

    def test_legacy_unknown_remains_unknown_and_prose_is_not_classification(self):
        old=self.initial();r=self.carried(old)
        p=r.result['items'][0]['provenance'];self.assertEqual(p['uncertainty'],'unknown')
        self.assertEqual(r.result['status'],'partial');self.assertTrue(p['continued_review_required'])
        # The literal legacy red assertion separately supplies disputed prose. No
        # keyword parser is needed or permitted to produce this carry finding.
        self.assertNotIn('disputed',p['uncertainty'])

    def test_rollover_cannot_clear_supplied_dispute_or_replace_original_proof(self):
        old=self.initial('disputed')
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            value=payload(self.a,self.c);value['items']=copy.deepcopy(old.scenario.payload['items'])
            value['items'][0].update(expected_on='2026-10-10',uncertainty='no_known_uncertainty')
            value['rollover']=[{'key':'receipt-1','disposition':'carry','reason':'Review alone is not resolution'}]
            with self.assertRaisesMessage(ValidationError,'preserves'):scenario(self.a,self.c,value,parent=old)
            value['items'][0]['uncertainty']='disputed';value['items'][0]['evidence_id']=evidence(self.a,self.c,'document','Different source').pk
            with self.assertRaisesMessage(ValidationError,'preserves'):scenario(self.a,self.c,value,parent=old)

    def test_existing_partial_policy_and_current_reviewer_authority_still_control(self):
        r=self.carried(self.initial('uncertain'))
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            policy(self.a,self.c,forecast.METHOD,dict(self.m,partial_publication='hold'))
            r=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c))
            with self.assertRaisesMessage(ValidationError,'incomplete'):review(self.a,self.c,r)
            policy(self.a,self.c,forecast.METHOD,self.m);r=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c))
            review(self.a,self.c,r)
            Grant.objects.filter(case=self.c,user=self.a,action='finance.forecast.review').update(active=False)
            with self.assertRaises(PermissionDenied):forecast.approved(r)
            self.assertEqual(r.result['status'],'partial')

    def test_agent_staff_and_management_aggregate_preserve_anonymous_warning(self):
        r=self.carried(self.initial('disputed'))
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            review(self.a,self.c,r);agent=investigate(self.a,self.c.pk,r.pk,rev(self.c))
            self.assertTrue(agent.result['assumptions'][0]['provenance']['continued_review_required'])
            self.client.force_login(self.a);response=self.client.get(f'/cases/{self.c.pk}/finance/forecast/')
            self.assertContains(response,'Continued review');self.assertEqual(response['Cache-Control'],'no-store')
            t,_=publication(self.a,self.c);v=forecast_documents.draft(self.a,self.c.pk,r.pk,t.pk,'management',rev(self.c))
            projected=json.loads(v.fields['financial_metrics']['text'])
            self.assertEqual(projected['continuation']['label'],'continued_review_uncertainty')
            self.assertEqual(projected['continuation']['item_count'],1)
            for secret in ['receipt-1','expected-1','finance-team','original_evidence_id']:
                self.assertNotIn(secret,json.dumps(v.payload))

    def test_group_warning_uses_only_selected_rows_without_private_lineage(self):
        from .test_group_forecast import configured
        self.a.username='continuation-fixture';self.a.save(update_fields=['username'])
        a,c,r,reader,t,g,expected=configured()
        changed=copy.deepcopy(r.result)
        changed['items'][1]['provenance']['continued_review_required']=True
        self.assertEqual(group_forecast.project(changed,g),expected)
        changed['items'][0]['provenance']['continued_review_required']=True
        projected=group_forecast.project(changed,g)
        self.assertEqual(projected['continuation']['label'],'continued_review_uncertainty')
        self.assertEqual(projected['continuation']['item_count'],1)
        for secret in ['RESTRICTED_X','SECRET_X','PRIVATE_X','7391','receipt-1','original_evidence_id']:
            self.assertNotIn(secret,json.dumps(projected))

    def test_database_rejects_forged_ready_and_missing_provenance_runs(self):
        r=self.carried(self.initial())
        for field,value in [('status','ready'),('items',[{k:v for k,v in r.result['items'][0].items() if k!='provenance'}])]:
            bad=copy.deepcopy(r.result);bad[field]=value
            with self.assertRaises(DatabaseError),transaction.atomic():
                ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=r.manifest,result=bad,sha256='a'*64,actor=self.a)

    def support(self,r,*,previous=None,e=None,mode='renewed_support',state='disputed',observed=None,actor=None):
        e=e or evidence(self.a,self.c,'forecast_support','Synthetic newly supplied support; continuing dispute; not authenticated externally')
        return forecast.record_support(actor or self.a,self.c.pk,r.scenario_id,'receipt-1',previous.pk if previous else None,e.pk,mode,state,observed,'Finance','Explicit supplied support/authority statement',rev(self.c))

    def test_explicit_renewal_is_not_resolution_and_stales_exact_review(self):
        r=self.carried(self.initial('disputed'))
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            old_review=review(self.a,self.c,r);support=self.support(r)
            with self.assertRaisesMessage(ValidationError,'changed'):forecast.approved(r)
            new=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c))
            self.assertNotEqual(new.pk,r.pk);self.assertEqual(new.result['status'],'partial')
            p=new.result['items'][0]['provenance'];self.assertTrue(p['renewed_supplied_support']);self.assertEqual(p['uncertainty'],'disputed')
            self.assertFalse(p['fresh_external_support']);self.assertIsNone(p['support_history'][-1]['observed_on'])
            decision=review(self.a,self.c,new);self.assertNotEqual(decision.pk,old_review.pk)
            proof=evidence(self.a,self.c,'forecast_support','Synthetic later explicit resolution statement supplied, not guaranteed collection')
            next_support=self.support(new,previous=support,e=proof,state='no_known_uncertainty',observed='2026-09-30')
            resolved=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c))
            self.assertEqual(resolved.result['status'],'ready');self.assertEqual(resolved.result['items'][0]['provenance']['reliability'],'unknown')
            self.assertEqual(resolved.result['items'][0]['original_due'],'2026-09-15')
            with self.assertRaisesMessage(ValidationError,'approval'):forecast.approved(resolved)
            review(self.a,self.c,resolved)
        november=self.carried(resolved,11)
        self.assertEqual(november.result['status'],'partial')
        self.assertEqual(november.result['items'][0]['provenance']['support_id'],next_support.pk)
        self.assertEqual(november.result['items'][0]['provenance']['carry_count'],2)

    def test_same_bytes_and_stale_predecessor_cannot_be_renewal(self):
        r=self.carried(self.initial('disputed'))
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            first=self.support(r);duplicate=evidence(self.a,self.c,'forecast_support',first.evidence.body)
            with self.assertRaisesMessage(ValidationError,'different evidence bytes'):self.support(r,previous=first,e=duplicate)
            with self.assertRaisesMessage(ValidationError,'predecessor'):self.support(r)
            with self.assertRaisesMessage(ValidationError,'not a review or opening'):
                self.support(r,previous=first,e=evidence(self.a,self.c,'forecast_review','Human approval is not new external support'))

    def test_revoked_attester_current_reaffirmation_preserves_unknown_and_source(self):
        from django.contrib.auth import get_user_model
        from apps.policy.services import register_reference
        from .helpers import activate
        r=self.carried(self.initial('disputed'))
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            first=self.support(r)
            new=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c));review(self.a,self.c,new)
            replacement=get_user_model().objects.create_user(username='continuation-reviewer')
            for action in ['case.read','finance.read','finance.forecast.capture','finance.forecast.review','finance.forecast.calculate']:
                Grant.objects.create(case=self.c,user=replacement,action=action)
            decision=evidence(self.a,self.c,'policy_decision','Synthetic authorized replacement role')
            ref=register_reference(self.a,self.c.pk,'forecast:replacement-role','schema:psl/role-assignment/v1',{'role':'Finance','user_id':replacement.pk},decision.pk)
            activate(self.a,self.c,'D05.role_principal_assignments',[ref.ref],decision)
            Grant.objects.filter(case=self.c,user=self.a,action='finance.forecast.review').update(active=False)
            stale=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c))
            self.assertFalse(stale.result['items'][0]['provenance']['support_authority_current'])
            proof=evidence(self.a,self.c,'forecast_review','Synthetic current reviewer cannot hide revoked support declaration')
            with self.assertRaisesMessage(ValidationError,'authority changed'):
                forecast.review(replacement,self.c.pk,stale.pk,'Finance','approve',proof.pk,'Must explicitly reaffirm first',rev(self.c))
            with self.assertRaisesMessage(ValidationError,'preserves'):
                self.support(r,previous=first,e=first.evidence,mode='reaffirmation',state='no_known_uncertainty',actor=replacement)
            reaffirmed=self.support(r,previous=first,e=first.evidence,mode='reaffirmation',actor=replacement)
            self.assertIsNone(reaffirmed.observed_on);self.assertEqual(reaffirmed.evidence_id,first.evidence_id)
            current=forecast.prepare(replacement,self.c.pk,r.scenario_id,rev(self.c))
            self.assertEqual(current.result['status'],'partial')
            self.assertFalse(current.result['items'][0]['provenance']['renewed_supplied_support'])
            approved=forecast.review(replacement,self.c.pk,current.pk,'Finance','approve',proof.pk,'Exact current continuation review',rev(self.c))
            self.assertEqual(forecast.approved(current).pk,approved.pk)
            self.assertEqual(current.result['items'][0]['provenance']['uncertainty'],'disputed')

    def test_native_group_delivery_retains_selected_uncertainty_and_exact_oracle(self):
        from django.contrib.auth import get_user_model
        from apps.documents.controlled import register_template, reserve_publication
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt
        from apps.policy.services import register_reference,active_component,reference_values
        from .document_helpers import artifact
        from .helpers import activate
        value=payload(self.a,self.c);value['items'][0]['uncertainty']='disputed'
        value['items'][1].update(key='PRIVATE_ITEM',source_ref='PRIVATE_SOURCE',owner='PRIVATE_OWNER',amount='7331')
        s=scenario(self.a,self.c,value);r=forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c));review(self.a,self.c,r)
        reader=get_user_model().objects.create_user(username='continuation-group-reader')
        Grant.objects.create(case=self.c,user=reader,action='document.receive:group')
        proof=evidence(self.a,self.c,'policy_decision','Synthetic explicitly selected group uncertainty disclosure')
        definition={'document_type':'finance_group_report','required_fields':['executive_summary','financial_metrics','bu_totals'],'audience_fields':{'group':['executive_summary','financial_metrics','bu_totals']},'internal_review_required':True}
        t=register_template(self.a,self.c.pk,'Group continuation disclosure',definition,proof.pk,rev(self.c))
        artifact(self.a,self.c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30},proof)
        ref=register_reference(self.a,self.c.pk,'continuation:group-recipient','schema:psl/document-recipient/v1',{'audience':'group','user_id':reader.pk},proof.pk)
        activate(self.a,self.c,'D11.recipient_grant_refs',[ref.ref],proof)
        g={'implementation':'native_selected_items_v1','run_id':r.pk,'run_hash':r.sha256,'rows':['receipt-1'],'fields':['kind','residual','expected_on'],
            'metadata':['currency','basis','as_of'],'recipient_ids':[reader.pk],'reviewer_roles':['Finance'],'publisher_roles':['Finance'],'allow_preparer_review':True,'oracle_evidence_id':1}
        expected={'implementation':group_forecast.IMPLEMENTATION,'metadata':{'currency':'NGN','basis':'gross_cash','as_of':value['as_of']},
            'rows':[{'kind':'other_inflow','residual':'50','expected_on':value['as_of']}],
            'scope':'selected_assumptions_only_no_group_balances','execution_authorized':False,
            'continuation':{'label':'continued_review_uncertainty','item_count':1,'reliability':'unknown','review_is_fresh_support':False}}
        oracle=evidence(self.a,self.c,'forecast_group_oracle',json.dumps(expected));g['oracle_evidence_id']=oracle.pk
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0]);projection['group']=g
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        v=group_forecast.draft(self.a,self.c.pk,r.pk,t.pk,rev(self.c));self.assertEqual(group_forecast.check_content(v.forecastbinding),expected)
        group_forecast.review(self.a,self.c.pk,v.pk,'Finance','approve','Exact selected uncertainty and recipients',rev(self.c))
        p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c));run_publication_once(case_id=self.c.pk)
        receipt=PublicationReceipt.objects.get(publication=p);text=json.dumps(receipt.payload)
        self.assertIn('continued_review_uncertainty',text)
        for secret in ['PRIVATE_ITEM','PRIVATE_SOURCE','PRIVATE_OWNER','7331','receipt-1','original_evidence_id']:
            self.assertNotIn(secret,text)
        self.assertFalse(Grant.objects.filter(user=reader,action='finance.read').exists())
        self.client.force_login(reader);self.assertContains(self.client.get('/documents/inbox/'),'continued_review_uncertainty')
