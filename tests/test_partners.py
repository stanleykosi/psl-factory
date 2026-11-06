import copy,json
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.db import connection,transaction,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.partner_validators import STAGES,DEADLINES,ACTIVITY,METER
from apps.baas import partner_operations as domain,partner_delivery
from apps.baas.models import PartnerRecord,PartnerDecision,OnboardingEvent,PartnerFollowup,PartnerReport,PartnerFinanceJob,PartnerFinanceReceipt,PartnerBillingImport,PartnerMeterClaim
from apps.finance.models import BillingUsage,Invoice
from apps.agents.partners import investigate
from .partner_helpers import fixture,capture,body,evidence,policy,terms,stage,report,review,delivered
from .helpers import rev

class PartnerTests(TestCase):
    def setUp(self):self.a,self.c,self.fin,self.f,self.cov=fixture()
    def test_expiry_notice_followup_and_renewal_intent_do_not_renew_contract(self):
        r=capture(self.a,self.c,'agreement');terms(self.a,self.c,r);pos=domain.agreement_position(r)
        self.assertEqual(pos['status'],'in_term');self.assertCountEqual(pos['followups'],['notice_on','expires_on'])
        e=evidence(self.a,self.c,'partner_decision','Synthetic owned review');f=domain.followup(self.a,self.c.pk,r.pk,'notice_on',self.a.pk,timezone.now()+timedelta(days=1),'PM',e.pk,'Review exact clauses internally',rev(self.c))
        self.assertEqual(f.action.current.owner,self.a);self.assertIsNotNone(f.action.current.due_at)
        self.assertEqual(domain.followup(self.a,self.c.pk,r.pk,'notice_on',self.a.pk,timezone.now()+timedelta(days=1),'PM',e.pk,'Same owned review',rev(self.c)).pk,f.pk)
        terms(self.a,self.c,r,'renewal','review_renewal');self.assertEqual(domain.agreement_position(r)['expires_on'],r.payload['expires_on']);self.assertEqual(PartnerRecord.objects.count(),1)
    def test_unknown_expiry_and_uninterpreted_auto_renewal_never_invent_dates(self):
        v=body('agreement');v.update(expires_on=None,notice_on=None,auto_renewal='yes');r=capture(self.a,self.c,'agreement',v);terms(self.a,self.c,r)
        p=domain.agreement_position(r);self.assertEqual(p['status'],'unknown_expiry');self.assertFalse(p['followups'])
    def test_known_notice_review_survives_unknown_expiry(self):
        v=body('agreement');v['expires_on']=None;r=capture(self.a,self.c,'agreement',v);terms(self.a,self.c,r)
        position=domain.agreement_position(r);self.assertEqual(position['status'],'unknown_expiry');self.assertEqual(position['followups'],['notice_on'])
    def test_expiry_day_boundary_is_explicit_versioned_policy(self):
        from datetime import date
        r=capture(self.a,self.c,'agreement');terms(self.a,self.c,r);day=date.fromisoformat(r.payload['expires_on']);self.assertEqual(domain.agreement_position(r,day)['status'],'in_term')
        policy(self.a,self.c,DEADLINES,dict(self.f['deadlines'],expiry_boundary='start_of_day'));terms(self.a,self.c,r);self.assertEqual(domain.agreement_position(r,day)['status'],'supplied_term_ended')
    def test_missing_policy_does_not_prevent_capture(self):
        transition(self.a,domain.rule(self.c,DEADLINES)[0].pk,'revoked');r=capture(self.a,self.c,'agreement')
        self.assertEqual(domain.agreement_position(r)['status'],'unknown')
        with self.assertRaises(ValidationError):terms(self.a,self.c,r)
        transition(self.a,domain.rule(self.c,ACTIVITY)[0].pk,'revoked');out=report(self.a,self.c);self.assertEqual(out.result['status'],'held')
    def test_amendment_invalidates_pending_terms_and_preserves_old_decision(self):
        r=capture(self.a,self.c,'agreement');d=terms(self.a,self.c,r);v=dict(r.payload,auto_renewal='no');new=capture(self.a,self.c,'agreement',v)
        with self.assertRaises(ValidationError):domain.validated_terms(r)
        with self.assertRaises(ValidationError):terms(self.a,self.c,new,'renewal','review_notice')
        self.assertEqual(PartnerDecision.objects.get(pk=d.pk).record,r);terms(self.a,self.c,new)
    def test_missing_or_wrong_executed_agreement_proof_holds_validation_not_capture(self):
        r=capture(self.a,self.c,'agreement',executed=False)
        with self.assertRaisesMessage(ValidationError,'executed agreement evidence'):terms(self.a,self.c,r)
        good=capture(self.a,self.c,'agreement');bad=capture(self.a,self.c,'agreement',dict(good.payload,executed_sha256='0'*64))
        with self.assertRaisesMessage(ValidationError,'hash differs'):terms(self.a,self.c,bad)
    def test_reported_tracker_stage_does_not_create_validated_history(self):
        r=capture(self.a,self.c,'onboarding');self.assertIsNone(domain.age(r)['seconds']);self.assertEqual(OnboardingEvent.objects.count(),0)
    def test_age_pause_resume_reentry_and_completion_evidence(self):
        r=capture(self.a,self.c,'onboarding');now=timezone.now();stage(self.a,self.c,r,at=now-timedelta(hours=5));pause=stage(self.a,self.c,r,operation='pause',at=now-timedelta(hours=3));stage(self.a,self.c,r,operation='resume',at=now-timedelta(hours=1))
        self.assertEqual(domain.age(r,now)['seconds'],10800)
        stage(self.a,self.c,r,'verification',at=now-timedelta(minutes=30));stage(self.a,self.c,r,'review',at=now-timedelta(minutes=10));self.assertEqual(domain.age(r,now)['seconds'],600)
        with self.assertRaises(ValidationError):stage(self.a,self.c,r,'complete',at=now)
        docs=[evidence(self.a,self.c,'document','Verified').pk,evidence(self.a,self.c,'signature','Signed').pk];stage(self.a,self.c,r,'complete',at=now,proofs=docs)
        self.assertTrue(domain.age(r)['terminal']);self.assertFalse(domain.age(r)['followup_due'])
    def test_invalid_initial_transition_and_nonchronological_history_hold(self):
        r=capture(self.a,self.c,'onboarding')
        with self.assertRaises(ValidationError):stage(self.a,self.c,r,'verification')
        stage(self.a,self.c,r)
        with self.assertRaises(ValidationError):stage(self.a,self.c,r,operation='resume',at=timezone.now())
        with self.assertRaises(ValidationError):stage(self.a,self.c,r,operation='pause',at=timezone.now()-timedelta(days=1))
        with self.assertRaises(ValidationError):stage(self.a,self.c,r,operation='pause',at=timezone.now()+timedelta(days=1))
    def test_onboarding_followup_uses_exact_event_and_granted_owner(self):
        r=capture(self.a,self.c,'onboarding');s=stage(self.a,self.c,r);e=evidence(self.a,self.c,'partner_decision','Follow up')
        with self.assertRaisesMessage(ValidationError,'ownership grant'):domain.followup(self.a,self.c.pk,r.pk,'stage:'+str(s.pk),self.fin.pk,timezone.now(),'PM',e.pk,'Exact delayed stage',rev(self.c))
        f=domain.followup(self.a,self.c.pk,r.pk,'stage:'+str(s.pk),self.a.pk,timezone.now(),'PM',e.pk,'Exact delayed stage',rev(self.c));self.assertEqual(f.action.current.owner,self.a)
    def test_stage_policy_change_and_revocation_hold_only_dependent_actions(self):
        r=capture(self.a,self.c,'onboarding');stage(self.a,self.c,r);policy(self.a,self.c,STAGES,self.f['stages']);self.assertIsNone(domain.age(r)['seconds'])
        self.assertEqual(capture(self.a,self.c,'agreement').kind,'agreement')
    def test_activity_deduplicates_active_users_but_not_events_and_excludes_test_kind(self):
        r=report(self.a,self.c);self.assertEqual(r.result['status'],'ready');self.assertEqual(r.result['rows'][0]['event_count'],3);self.assertEqual(r.result['rows'][0]['active_users'],2);self.assertFalse(r.result['activity_is_billable_usage'])
    def test_missing_users_quantities_and_partial_coverage_remain_explicit(self):
        v=body('activity');v['events'][0]['user']=None;r=report(self.a,self.c,capture(self.a,self.c,'activity',v));self.assertIsNone(r.result['rows'][0]['active_users']);self.assertEqual(r.result['status'],'held')
        v=body('activity');v['completeness']='unknown';r=report(self.a,self.c,capture(self.a,self.c,'activity',v));self.assertEqual(r.result['status'],'held')
    def test_duplicate_events_wrong_period_and_unapproved_source_hold(self):
        for mutate in ['duplicate','period','source']:
            v=body('activity')
            if mutate=='duplicate':v['events'].append(v['events'][0])
            elif mutate=='period':v['period']='2000-01'
            else:v['source']='unknown-provider'
            r=report(self.a,self.c,capture(self.a,self.c,'activity',v));self.assertEqual(r.result['status'],'held')
    def test_overlapping_batch_identity_is_not_silently_counted(self):
        first=capture(self.a,self.c,'activity');r=report(self.a,self.c,first);capture(self.a,self.c,'activity',reference='another-source');self.assertEqual(domain.activity_calculation(first)[1]['status'],'held')
        with self.assertRaises(ValidationError):domain.report_current(r)
    def test_preparer_cannot_review_as_finance_without_configured_role(self):
        r=report(self.a,self.c)
        with self.assertRaises(PermissionDenied):review(self.a,self.c,r)
        review(self.fin,self.c,r,'return')
        with self.assertRaises(ValidationError):domain.reserve(self.a,self.c.pk,r.pk,'PM',rev(self.c))
    def test_reviewed_aggregate_handoff_and_explicit_finance_meter_import(self):
        r=report(self.a,self.c);receipt=delivered(self.a,self.c,self.fin,r);text=json.dumps(receipt.payload)
        self.assertNotIn('user-1',text);self.assertNotIn('event-1',text);self.assertNotIn('quantity',text);self.assertNotIn('source',receipt.payload)
        e=evidence(self.fin,self.c,'partner_decision','Accept explicit meter, not active-user count');accepted=domain.import_finance_usage(self.fin,self.c.pk,receipt.pk,'Finance',e.pk,rev(self.c))
        self.assertEqual([row['quantity'] for row in accepted.usage.rows],['2','3','1']);self.assertEqual(Invoice.objects.count(),0);self.assertEqual(PartnerMeterClaim.objects.count(),3)
        self.assertEqual(domain.import_finance_usage(self.fin,self.c.pk,receipt.pk,'Finance',e.pk,rev(self.c)).pk,accepted.pk)
    def test_activity_counts_never_fill_missing_meter_quantities(self):
        v=body('activity');v['events'][0]['quantity']=None;r=report(self.a,self.c,capture(self.a,self.c,'activity',v));receipt=delivered(self.a,self.c,self.fin,r);e=evidence(self.fin,self.c,'partner_decision','Meter review')
        with self.assertRaisesMessage(ValidationError,'quantities'):domain.import_finance_usage(self.fin,self.c.pk,receipt.pk,'Finance',e.pk,rev(self.c))
        self.assertEqual(BillingUsage.objects.count(),0);self.assertEqual(PartnerMeterClaim.objects.count(),0)
    def test_source_revision_or_withdrawn_review_holds_pending_delivery(self):
        r=report(self.a,self.c);review(self.fin,self.c,r);j=domain.reserve(self.a,self.c.pk,r.pk,'PM',rev(self.c));capture(self.a,self.c,'activity');partner_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(PartnerFinanceReceipt.objects.count(),0)
    def test_private_finance_inbox_requires_current_receive_and_finance_read(self):
        receipt=delivered(self.a,self.c,self.fin,report(self.a,self.c));self.client.force_login(self.fin);url='/finance/partner-activity/inbox/';self.assertContains(self.client.get(url),'Receipt #')
        response=self.client.get(url);self.assertContains(response,'Active kinds: use');self.assertContains(response,'Excluded kinds: test');self.assertContains(response,'Period timezone: Africa/Lagos');self.assertContains(response,'Source extracted:');self.assertNotContains(response,'user-1');self.assertNotContains(response,'event-1');self.assertNotContains(response,'synthetic-admin')
        Grant.objects.filter(case=self.c,user=self.fin,action='finance.read').update(active=False);self.assertNotContains(self.client.get(url),'Receipt #')
    def test_receipt_metric_statement_uses_pinned_historical_policy(self):
        delivered(self.a,self.c,self.fin,report(self.a,self.c));policy(self.a,self.c,ACTIVITY,dict(self.f['activity'],active_kinds=['login']))
        self.client.force_login(self.fin);response=self.client.get('/finance/partner-activity/inbox/')
        self.assertContains(response,'Active kinds: use');self.assertNotContains(response,'Active kinds: login')
    def test_superuser_flag_does_not_appoint_stage_or_agreement_authority(self):
        self.fin.is_superuser=True;self.fin.save();r=capture(self.a,self.c,'agreement')
        with self.assertRaises(PermissionDenied):terms(self.fin,self.c,r)
    def test_cross_case_evidence_and_read_revocation_hold(self):
        from apps.core.models import Case
        other=Case.objects.create(tenant='other',title='Other',synthetic=True);r=capture(self.a,self.c,'agreement')
        with self.assertRaises(ValidationError):domain.exact(other,PartnerRecord,r.pk)
        Grant.objects.filter(case=self.c,user=self.a,action='baas.read').update(active=False)
        with self.assertRaises(PermissionDenied):capture(self.a,self.c,'onboarding')
    def test_invalid_policies_and_component_schema_substitution_rejected(self):
        bad=copy.deepcopy(self.f['stages']);bad[1]['key']='review'
        with self.assertRaises(ValidationError):policy(self.a,self.c,STAGES,bad)
        bad=copy.deepcopy(self.f['activity']);bad['excluded_kinds']=['use']
        with self.assertRaises(ValidationError):policy(self.a,self.c,ACTIVITY,bad)
        bad=dict(self.f['deadlines'],timezone='invented')
        with self.assertRaises(ValidationError):policy(self.a,self.c,DEADLINES,bad)
        with self.assertRaises(ValidationError):policy(self.a,self.c,METER,self.f['activity'])
    def test_append_only_record_and_job_intent_guards(self):
        r=report(self.a,self.c);review(self.fin,self.c,r);j=domain.reserve(self.a,self.c.pk,r.pk,'PM',rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():PartnerRecord.objects.filter(pk=r.record_id).update(reference='rewritten')
        with self.assertRaises(DatabaseError),transaction.atomic():PartnerFinanceJob.objects.filter(pk=j.pk).update(intent={})
    def test_agent_cites_facts_and_has_no_completion_notice_or_financial_tools(self):
        capture(self.a,self.c,'agreement');capture(self.a,self.c,'onboarding');report(self.a,self.c);r=investigate(self.a,self.c.pk,rev(self.c))
        self.assertEqual(len(r.result['citations']),3);self.assertFalse(r.result['invoice_created']);self.assertFalse(r.result['renewal_executed']);self.assertFalse(r.result['onboarding_completed'])
    def test_staff_forms_and_typed_policy_draft_lifecycle(self):
        r=capture(self.a,self.c,'activity');self.client.force_login(self.a);url=f'/cases/{self.c.pk}/partners/'
        response=self.client.post(url,{'action':'report','revision':rev(self.c),'record':r.pk});self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(url),'Active users')
        e=evidence(self.a,self.c,'policy_decision','Synthetic draft from staff form')
        response=self.client.post(url,{'action':'policy','revision':rev(self.c),'component':STAGES,'content':json.dumps(self.f['stages']),'evidence':e.pk,'effective_from':timezone.now().isoformat()});self.assertEqual(response.status_code,302)
        from apps.policy.models import Configuration
        c=Configuration.objects.filter(case=self.c,component=STAGES).order_by('-pk').first();transition(self.a,c.pk,'validated');transition(self.a,c.pk,'active')
    def test_staff_review_handoff_and_finance_import_forms(self):
        url=f'/cases/{self.c.pk}/partners/'
        def post(person,action,**values):
            self.client.force_login(person);response=self.client.post(url,dict(action=action,revision=rev(self.c),**values));self.assertEqual(response.status_code,302,response.content[:300])
        a=capture(self.a,self.c,'agreement');e=evidence(self.a,self.c,'partner_decision','Synthetic actual owner review')
        post(self.a,'agreement',record=a.pk,purpose='terms',verdict='approve',role='PM',evidence=e.pk,reason='Explicit synthetic clause validation')
        post(self.a,'followup',record=a.pk,source_key='notice_on',owner_id=self.a.pk,due_at=timezone.now().isoformat(),role='PM',evidence=e.pk,reason='Owned internal notice review')
        o=capture(self.a,self.c,'onboarding');stage_e=evidence(self.a,self.c,'partner_stage','Actual entry');doc=evidence(self.a,self.c,'document','Actual source document')
        post(self.a,'stage',record=o.pk,operation='enter',stage='review',occurred_at=(timezone.now()-timedelta(hours=2)).isoformat(),role='PM',evidence=stage_e.pk,required_evidence_ids=json.dumps([doc.pk]))
        r=report(self.a,self.c);proof=evidence(self.fin,self.c,'partner_decision','Finance review')
        post(self.fin,'review',report=r.pk,role='Finance',verdict='approve',evidence=proof.pk);post(self.a,'reserve',report=r.pk,role='PM');partner_delivery.run_once();receipt=PartnerFinanceReceipt.objects.get()
        post(self.fin,'import',receipt=receipt.pk,role='Finance',evidence=proof.pk);post(self.a,'investigate')
        self.assertContains(self.client.get(url),'Meter acceptance');self.assertContains(self.client.get(url),'Cited partner investigation');self.assertContains(self.client.get(url),'Current approval')
    def test_meter_import_connects_to_real_finance_pricing_without_issuing_invoice(self):
        receipt=delivered(self.a,self.c,self.fin,report(self.a,self.c));e=evidence(self.fin,self.c,'partner_decision','Exact meter acceptance');accepted=domain.import_finance_usage(self.fin,self.c.pk,receipt.pk,'Finance',e.pk,rev(self.c))
        from apps.finance import billing
        p=billing.prepare(self.a,self.c.pk,self.cov.pk,'usage',accepted.usage_id,None,rev(self.c));self.assertIsNone(p.result['total'])
        from .billing_helpers import policy as pricing_policy
        from django.conf import settings
        f=json.loads((settings.BASE_DIR/'fixtures/finance-billing.json').read_text(encoding='utf-8'));rate=dict(f['rule'],coverage_id=self.cov.pk,unit='transaction',from_period=self.cov.from_period,to_period=self.cov.to_period);m=f['arithmetic'];oracle=evidence(self.a,self.c,'billing_oracle',m['oracles']);m['oracle_evidence_id']=oracle.pk
        pricing_policy(self.a,self.c,'D08.effective_price_rule_refs',[rate]);pricing_policy(self.a,self.c,'D08.tax_tier_rounding_rules',m)
        prepared=billing.prepare(self.a,self.c.pk,self.cov.pk,'usage',accepted.usage_id,None,rev(self.c));self.assertEqual(prepared.result['total'],'16.13');self.assertFalse(prepared.result['invoice_issued'])
        self.assertEqual(prepared.snapshot['partner_meter_origin']['acceptance'],accepted.pk)
        capture(self.a,self.c,'activity')
        with self.assertRaises(ValidationError):billing.ensure_current(prepared)
        held=billing.prepare(self.a,self.c.pk,self.cov.pk,'usage',accepted.usage_id,None,rev(self.c));self.assertIsNone(held.result['total']);self.assertTrue(any('Partner meter source' in f for f in held.result['findings']))
        self.assertEqual(BillingUsage.objects.get(pk=accepted.usage_id).rows[0]['quantity'],'2')
    def test_shared_deadline_and_finance_forecast_namespaces_can_coexist(self):
        from django.conf import settings
        from apps.policy.services import reference_values
        deadlines=dict(self.f['deadlines'],action={'unit':'elapsed_hours','amount':2});c=policy(self.a,self.c,DEADLINES,deadlines);self.assertEqual(reference_values(c)[0]['action']['amount'],2)
        base=json.loads((settings.BASE_DIR/'fixtures/finance-analysis.json').read_text(encoding='utf-8'))['projection']
        for audience in base['audiences']:audience.update(columns=['actual'],charts=False)
        forecast=json.loads((settings.BASE_DIR/'fixtures/finance-forecast.json').read_text(encoding='utf-8'))['projection']
        cfg=policy(self.a,self.c,ACTIVITY,dict(self.f['activity'],**base,**forecast));v=reference_values(cfg)[0]
        self.assertEqual(v['audiences'],base['audiences']);self.assertEqual(v['forecast'],forecast['forecast']);self.assertEqual(v['active_kinds'],['use'])
    def test_direct_actions_require_partner_read_independently(self):
        Grant.objects.filter(case=self.c,user=self.a,action='partner.read').update(active=False)
        with self.assertRaises(PermissionDenied):capture(self.a,self.c,'activity')
    def test_source_owner_role_categories_still_require_explicit_actual_assignments(self):
        from apps.policy.services import register_reference
        from .helpers import activate
        r=capture(self.a,self.c,'agreement');policy(self.a,self.c,DEADLINES,dict(self.f['deadlines'],agreement_roles=['Legal']))
        e=evidence(self.a,self.c,'partner_decision','Legal role text alone grants no authority')
        with self.assertRaises(PermissionDenied):domain.decide_agreement(self.a,self.c.pk,r.pk,'terms','approve','Legal',e.pk,'Exact legal owner must be appointed',rev(self.c))
        owner=evidence(self.a,self.c,'policy_decision','Synthetic explicit legal, BaaS and Data owner appointments')
        refs=[register_reference(self.a,self.c.pk,'owner-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':person.pk},owner.pk).ref for role,person in [('PM',self.a),('Finance',self.fin),('Legal',self.a),('BaaS',self.a),('Data',self.fin)]]
        activate(self.a,self.c,'D05.role_principal_assignments',refs,owner)
        d=domain.decide_agreement(self.a,self.c.pk,r.pk,'terms','approve','Legal',e.pk,'Exact synthetic appointed owner validates agreement',rev(self.c));self.assertEqual(d.role,'Legal')
