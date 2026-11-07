import json,copy
from datetime import date
from unittest.mock import patch
from django.test import TestCase
from django.db import connection,transaction,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from apps.finance import forecast,forecast_documents
from apps.finance.models import ForecastScenario,ForecastRun,ForecastMatch,ForecastActualVerification
from apps.policy.services import active_component,transition
from apps.policy.finance_drafts import draft_finance_policy
from apps.identity.models import Grant
from apps.documents.controlled import reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt
from apps.agents.forecast import investigate
from .forecast_helpers import fixture,payload,scenario,run,review,actual,match,publication,month
from .billing_helpers import evidence,policy
from .helpers import rev

class ForecastTests(TestCase):
    def setUp(self):self.a,self.c,self.m=fixture()
    def test_month_chain_and_negative_balance_are_exact(self):
        r=run(self.a,self.c);self.assertEqual([x['closing'] for x in r.result['periods']],['150','130']);self.assertEqual(r.result['status'],'ready');self.assertFalse(r.result['full_business_cash_forecast'])
        v=payload(self.a,self.c,amount='0');v['items'][1]['amount']='200';r=run(self.a,self.c,v);self.assertEqual(r.result['periods'][1]['closing'],'-100')
    def test_unknown_amount_propagates_instead_of_zero(self):
        r=run(self.a,self.c,payload(self.a,self.c,amount=None));self.assertIsNone(r.result['periods'][0]['closing']);self.assertIsNone(r.result['periods'][1]['opening']);self.assertEqual(r.result['status'],'partial')
    def test_undated_item_keeps_unknown_balance(self):
        v=payload(self.a,self.c);v['items'][0]['expected_on']=None;r=run(self.a,self.c,v);self.assertIsNone(r.result['periods'][0]['closing']);self.assertIn('timing',' '.join(r.result['findings']))
    def test_capture_and_held_calculation_without_policy(self):
        transition(self.a,active_component(forecast.METHOD,self.c).pk,'revoked');r=run(self.a,self.c);self.assertEqual(r.result['status'],'held')
        with self.assertRaises(ValidationError):review(self.a,self.c,r)
    def test_opening_missing_account_is_not_zero(self):
        v=payload(self.a,self.c);v['coverage']['accounts'].append('missing-account');r=run(self.a,self.c,v);self.assertIsNone(r.result['periods'][0]['opening'])
    def test_opening_proof_must_match_exact_source(self):
        v=payload(self.a,self.c);v['openings'][0]['amount']='999'
        with self.assertRaisesMessage(ValidationError,'differs'):scenario(self.a,self.c,v)
    def test_duplicate_item_and_unordered_horizon_are_rejected(self):
        v=payload(self.a,self.c);v['items'].append(copy.deepcopy(v['items'][0]))
        with self.assertRaisesMessage(ValidationError,'Duplicate'):scenario(self.a,self.c,v)
        v=payload(self.a,self.c);v['months'].reverse()
        with self.assertRaises(ValidationError):scenario(self.a,self.c,v)
    def test_precision_and_false_oracle_hold_validation(self):
        with self.assertRaisesMessage(ValidationError,'precision'):run(self.a,self.c,payload(self.a,self.c,amount='1.001'))
        m=copy.deepcopy(self.m);m['oracles'][0]['expected']='999';o=evidence(self.a,self.c,'forecast_oracle',json.dumps(m['oracles']));m['oracle_evidence_id']=o.pk
        with self.assertRaisesMessage(ValidationError,'oracle'):policy(self.a,self.c,forecast.METHOD,m)
    def test_partial_publication_explicit_policy_and_review(self):
        v=payload(self.a,self.c);v['coverage']['outflows']='unknown';r=run(self.a,self.c,v);review(self.a,self.c,r);self.assertEqual(forecast.approved(r).verdict,'approve')
        policy(self.a,self.c,forecast.METHOD,dict(self.m,partial_publication='hold'));r=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c))
        with self.assertRaisesMessage(ValidationError,'incomplete'):review(self.a,self.c,r)
    def test_actual_report_is_not_verified_money(self):
        r=run(self.a,self.c);a=actual(self.a,self.c,verified=False)
        with self.assertRaisesMessage(ValidationError,'verified'):match(self.a,self.c,r.scenario,a)
        r=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c));self.assertEqual(r.result['periods'][0]['actual_inflow'],'0')
    def test_explicit_partial_match_actual_capacity_and_semantic_key(self):
        r=run(self.a,self.c);a=actual(self.a,self.c);m=match(self.a,self.c,r.scenario,a)
        self.assertEqual(match(self.a,self.c,r.scenario,a).pk,m.pk)
        with self.assertRaisesMessage(ValidationError,'capacity'):match(self.a,self.c,r.scenario,a,'1',op='MATCH-2')
        with self.assertRaisesMessage(ValidationError,'changed facts'):match(self.a,self.c,r.scenario,a,'14')
        new=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c));self.assertEqual(new.result['items'][0]['residual'],'35.00000000');self.assertEqual(new.result['periods'][0]['closing'],'150.00000000')
    def test_exact_only_matching_and_wrong_direction(self):
        policy(self.a,self.c,forecast.METHOD,dict(self.m,matching='exact_only'));r=run(self.a,self.c);a=actual(self.a,self.c)
        with self.assertRaisesMessage(ValidationError,'full settlement'):match(self.a,self.c,r.scenario,a)
        a=actual(self.a,self.c,direction='outflow',transaction='TX-OUT')
        with self.assertRaisesMessage(ValidationError,'direction'):match(self.a,self.c,r.scenario,a)
    def test_actual_verification_requires_proof_and_current_human_role(self):
        a=actual(self.a,self.c,verified=False);proof=evidence(self.a,self.c,'forecast_actual_verification',json.dumps(dict(a.payload,amount='999')))
        with self.assertRaisesMessage(ValidationError,'exact actual'):forecast.verify_actual(self.a,self.c.pk,a.pk,'Finance',proof.pk,rev(self.c))
        proof=evidence(self.a,self.c,'forecast_actual_verification',json.dumps(a.payload));policy(self.a,self.c,forecast.METHOD,dict(self.m,distinct_actual_reporter=True))
        with self.assertRaises(PermissionDenied):forecast.verify_actual(self.a,self.c.pk,a.pk,'Finance',proof.pk,rev(self.c))
    def test_actual_identity_conflict_and_unknown_verification(self):
        actual(self.a,self.c)
        with self.assertRaisesMessage(ValidationError,'different facts'):actual(self.a,self.c,'16')
        a=actual(self.a,self.c,None,transaction='UNKNOWN',verified=False);p=evidence(self.a,self.c,'forecast_actual_verification',json.dumps(a.payload))
        with self.assertRaises(ValidationError):forecast.verify_actual(self.a,self.c.pk,a.pk,'Finance',p.pk,rev(self.c))
    def test_changed_actual_or_method_stales_existing_review(self):
        r=run(self.a,self.c);review(self.a,self.c,r);actual(self.a,self.c)
        with self.assertRaisesMessage(ValidationError,'changed'):forecast.approved(r)
    def test_review_reject_and_admin_flag_do_not_grant_authority(self):
        r=run(self.a,self.c);review(self.a,self.c,r,'return')
        with self.assertRaises(ValidationError):forecast.approved(r)
        self.a.is_superuser=True;self.a.save();Grant.objects.filter(case=self.c,user=self.a,action='finance.forecast.review').update(active=False)
        with self.assertRaises(PermissionDenied):review(self.a,self.c,r)
    def test_publication_uses_existing_durable_worker_and_private_projection(self):
        r=run(self.a,self.c);review(self.a,self.c,r);t,reader=publication(self.a,self.c)
        v=forecast_documents.draft(self.a,self.c.pk,r.pk,t.pk,'management',rev(self.c));p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c));run_publication_once()
        receipt=PublicationReceipt.objects.get(publication=p);self.assertEqual(receipt.recipient_id,reader.pk)
        text=json.dumps(receipt.payload);self.assertIn('captured_case',text);self.assertNotIn('requester-1',text);self.assertNotIn('expected-1',text);self.assertNotIn('opening',text)
        self.client.force_login(reader);self.assertContains(self.client.get('/documents/inbox/'),'Reviewed cash forecast')
    def test_publication_holds_after_source_change_and_preserves_old_artifact(self):
        r=run(self.a,self.c);review(self.a,self.c,r);t,_=publication(self.a,self.c);v=forecast_documents.draft(self.a,self.c.pk,r.pk,t.pk,'internal',rev(self.c));p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c));actual(self.a,self.c);run_publication_once()
        self.assertFalse(PublicationReceipt.objects.filter(publication=p).exists());self.assertIn('50',json.dumps(v.payload))
    def test_sql_guards_reject_forecast_mutation(self):
        r=run(self.a,self.c)
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cur:cur.execute('UPDATE finance_forecastrun SET sha256=%s WHERE id=%s',['x'*64,r.pk])
    def test_roll_forward_preserves_original_due_and_global_residual(self):
        with patch('django.utils.timezone.localdate',return_value=date(2026,9,21)):
            v=payload(self.a,self.c);r=run(self.a,self.c,v);review(self.a,self.c,r)
        a=actual(self.a,self.c);match(self.a,self.c,r.scenario,a)
        v2=payload(self.a,self.c);v2['items']=copy.deepcopy(v['items'])
        for i in v2['items']:i['expected_on']=v2['as_of']
        v2['rollover']=[{'key':i['key'],'disposition':'carry','reason':'Actual partial settlement; explicitly revised date'} for i in v2['items']]
        s=scenario(self.a,self.c,v2,parent=r);out=forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c));review(self.a,self.c,out)
        self.assertEqual(out.result['items'][0]['original_due'],'2026-09-21');self.assertEqual(out.result['items'][0]['residual'],'35.00000000');self.assertEqual(s.root_id,r.scenario_id)
        with self.assertRaisesMessage(ValidationError,'capacity'):match(self.a,self.c,s,a,'1',op='MATCH-SECOND-GENERATION')
    def test_roll_forward_requires_all_dispositions_and_fresh_opening(self):
        with patch('django.utils.timezone.localdate',return_value=date(2026,9,21)):
            r=run(self.a,self.c);review(self.a,self.c,r)
        v=payload(self.a,self.c);v['items']=copy.deepcopy(r.scenario.payload['items'])
        with self.assertRaisesMessage(ValidationError,'every unresolved'):scenario(self.a,self.c,v,parent=r)
    def test_agent_is_cited_and_has_no_execution_tools(self):
        r=run(self.a,self.c);a=investigate(self.a,self.c.pk,r.pk,rev(self.c));self.assertTrue(a.result['citations']);self.assertFalse(a.result['cash_mutated']);self.assertFalse(a.result['approval_granted'])
    def test_staff_ui_full_connected_path_and_policy_draft(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/forecast/'
        def post(action,**values):
            r=self.client.post(url,dict(action=action,revision=rev(self.c),**values));self.assertEqual(r.status_code,302,r.content[:500])
        v=payload(self.a,self.c);e=evidence(self.a,self.c,'forecast_input',json.dumps(v));post('capture',reference='UI-F',evidence=e.pk,reason='Explicit UI inventory')
        s=ForecastScenario.objects.get();post('prepare',scenario=s.pk);r=ForecastRun.objects.get();e=evidence(self.a,self.c,'forecast_review','Synthetic UI review evidence')
        post('review',run=r.pk,role='Finance',verdict='approve',evidence=e.pk,reason='UI exact review');post('investigate',run=r.pk)
        t,_=publication(self.a,self.c);post('draft',run=r.pk,template=t.pk,audience='internal');self.assertContains(self.client.get(url),'Current captured evidence');self.assertContains(self.client.get(url),'Cited forecast investigation')
        owner=evidence(self.a,self.c,'policy_decision','Synthetic UI typed method draft')
        post('policy',component=forecast.METHOD,content=json.dumps(self.m),evidence=owner.pk,effective_from='2026-10-20T00:00:00Z')
        from apps.policy.models import Configuration
        p=Configuration.objects.filter(case=self.c,component=forecast.METHOD).order_by('-pk').first();self.assertEqual(p.states.order_by('-pk').first().state,'draft');transition(self.a,p.pk,'validated');transition(self.a,p.pk,'active')
    def test_full_match_reversal_restores_both_capacities_without_erasing_history(self):
        r=run(self.a,self.c);a=actual(self.a,self.c);m=match(self.a,self.c,r.scenario,a);proof=evidence(self.a,self.c,'forecast_match','Synthetic full match correction')
        x=forecast.unmatch(self.a,self.c.pk,m.pk,proof.pk,'Explicit wrong assumption correction',rev(self.c));self.assertEqual(forecast.unmatch(self.a,self.c.pk,m.pk,proof.pk,'Repeated exact correction',rev(self.c)).pk,x.pk)
        match(self.a,self.c,r.scenario,a,op='REPLACEMENT-MATCH');self.assertEqual(ForecastMatch.objects.count(),2);self.assertEqual(forecast.matched(r.scenario,'receipt-1'),15)
    def test_source_occurrence_duplicate_is_not_hidden_by_new_item_key(self):
        v=payload(self.a,self.c);v['items'].append(dict(v['items'][1],key='different-key'))
        with self.assertRaisesMessage(ValidationError,'source occurrence'):scenario(self.a,self.c,v)
    def test_old_opening_date_does_not_invent_interim_reconciliation(self):
        v=payload(self.a,self.c);opening=dict(v['openings'][0],observed_on='2026-10-01');opening.pop('evidence_id');proof=evidence(self.a,self.c,'forecast_opening',json.dumps(opening));v['openings'][0]=dict(opening,evidence_id=proof.pk)
        r=run(self.a,self.c,v);self.assertIsNone(r.result['periods'][0]['closing']);self.assertIn('intervening',' '.join(r.result['findings']))
    def test_cross_case_forecast_ids_and_cross_component_schemas_are_rejected(self):
        from apps.core.models import Case
        other=Case.objects.create(tenant='other',title='Other',synthetic=True);r=run(self.a,self.c)
        with self.assertRaises(ValidationError):forecast.exact(other,ForecastRun,r.pk)
        from apps.policy.services import register_reference
        owner=evidence(self.a,self.c,'policy_decision','Synthetic invalid schema test')
        ref=register_reference(self.a,self.c.pk,'wrong-schema','schema:psl/forecast-method/v1',self.m,owner.pk)
        from .helpers import envelope
        from apps.policy.services import save_draft
        config=save_draft(self.a,self.c.pk,envelope(self.c,'D10.restatement_rule_id',ref.ref,owner))
        with self.assertRaises(ValidationError):transition(self.a,config.pk,'validated')
    def test_priority_uses_configured_human_and_existing_owned_action_lifecycle(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.pmo.meetings import change_action
        r=run(self.a,self.c);review(self.a,self.c,r);proof=evidence(self.a,self.c,'forecast_review','Synthetic management priority and accountable owner')
        priority=forecast.prioritize(self.a,self.c.pk,r.pk,'Finance','FOLLOWUP-1','Confirm expected receipt date',self.a.pk,timezone.now()+timedelta(days=2),proof.pk,'Explicit priority, not authority to pay',rev(self.c))
        self.assertEqual(priority.action.current.owner_id,self.a.pk);self.assertEqual(priority.review.run_id,r.pk)
        change_action(self.a,self.c.pk,priority.action_id,'complete',proof.pk,'Actual follow-up completed',rev(self.c),1);priority.action.refresh_from_db();self.assertEqual(priority.action.current.status,'completed')
        self.client.force_login(self.a);self.assertContains(self.client.get(f'/cases/{self.c.pk}/finance/forecast/'),'FOLLOWUP-1')
    def test_priority_cannot_infer_owner_or_role_from_administrator(self):
        from django.utils import timezone
        r=run(self.a,self.c);review(self.a,self.c,r);proof=evidence(self.a,self.c,'forecast_review','Synthetic invalid priority')
        with self.assertRaises(ValidationError):forecast.prioritize(self.a,self.c.pk,r.pk,'Finance','BAD','No inferred owner',None,timezone.now(),proof.pk,'No owner supplied',rev(self.c))
        Grant.objects.filter(case=self.c,user=self.a,action='action.own').update(active=False)
        with self.assertRaises(ValidationError):forecast.prioritize(self.a,self.c.pk,r.pk,'Finance','BAD','Forbidden owner',self.a.pk,timezone.now(),proof.pk,'Owner grant withdrawn',rev(self.c))
    def test_roll_forward_explicit_cancellation_preserves_original_expected_history(self):
        with patch('django.utils.timezone.localdate',return_value=date(2026,9,21)):
            r=run(self.a,self.c);review(self.a,self.c,r)
        v=payload(self.a,self.c);v['items']=[];v['rollover']=[{'key':i['key'],'disposition':'cancel','reason':'Explicit cancellation of forecast assumption only'} for i in r.scenario.payload['items']]
        s=scenario(self.a,self.c,v,parent=r);out=forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c));review(self.a,self.c,out)
        self.assertEqual(len(r.scenario.payload['items']),2);self.assertEqual(out.result['items'],[]);self.assertFalse(out.result['execution_authorized'])
    def test_forecast_projection_can_preserve_existing_finance_reporting_namespace(self):
        from django.conf import settings
        base=json.loads((settings.BASE_DIR/'fixtures/finance-analysis.json').read_text(encoding='utf-8'))['projection']
        for a in base['audiences']:a.update(columns=['actual'],charts=False)
        extra=json.loads((settings.BASE_DIR/'fixtures/finance-forecast.json').read_text(encoding='utf-8'))['projection']
        p=policy(self.a,self.c,'D10.audience_projection_rules',dict(base,**extra));from apps.policy.services import reference_values
        value=reference_values(p)[0];self.assertEqual(value['audiences'],base['audiences']);self.assertEqual(value['forecast'],extra['forecast'])
    def test_direct_commands_require_current_finance_read_as_well_as_action(self):
        r=run(self.a,self.c);a=actual(self.a,self.c);Grant.objects.filter(case=self.c,user=self.a,action='finance.read').update(active=False)
        with self.assertRaises(PermissionDenied):match(self.a,self.c,r.scenario,a)
        with self.assertRaises(PermissionDenied):review(self.a,self.c,r)
    def test_historical_review_survives_old_reviewer_withdrawal_but_new_review_still_requires_authority(self):
        with patch('django.utils.timezone.localdate',return_value=date(2026,9,21)):
            old=run(self.a,self.c);review(self.a,self.c,old)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.forecast.review').update(active=False)
        v=payload(self.a,self.c);v['items']=copy.deepcopy(old.scenario.payload['items'])
        for item in v['items']:item['expected_on']=v['as_of']
        v['rollover']=[{'key':i['key'],'disposition':'carry','reason':'Explicit revised assumption with fresh opening'} for i in v['items']]
        s=scenario(self.a,self.c,v,parent=old);r=forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c))
        with self.assertRaises(PermissionDenied):review(self.a,self.c,r)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.forecast.review').update(active=True)
        review(self.a,self.c,r);self.assertEqual(forecast.approved(r).verdict,'approve')

class ForecastSettlementIntegrationTests(TestCase):
    def test_corrected_receivables_and_current_cash_successor_are_real_inputs(self):
        from .correction_helpers import fixture as corrected_fixture,note as legal_note,apply as apply_note,successor,review as correction_review
        from .forecast_helpers import configure
        from .settlement_helpers import receipt
        from apps.finance import cash,cash_successors
        a,c,cov,issue,e=corrected_fixture();apply_note(a,c,legal_note(a,c,issue,e),e);configure(a,c)
        v=payload(a,c);v['items'][0].update(kind='receivable',issue_id=issue.pk,amount='27.25',source_ref='canonical-invoice')
        s=scenario(a,c,v);r=forecast.prepare(a,c.pk,s.pk,rev(c));self.assertEqual(r.result['items'][0]['residual'],'27.25')
        too_much=copy.deepcopy(v);too_much['items'][0]['amount']='32.25'
        with self.assertRaisesMessage(ValidationError,'corrected receivable'):scenario(a,c,too_much)
        # This integration requires a same-business-day source. The generic
        # receipt helper intentionally defaults to a prior UTC hour, which can
        # predate the current Lagos forecast cutoff near midnight.
        from django.utils import timezone
        reported,lot=receipt(a,c,received_at=timezone.localtime().isoformat())
        def imported(l):
            value=cash.lot_payload(l);doc={'entity':'synthetic-company','account':'account-1','currency':value['currency'],'basis':'gross_cash','source':value['source'],'transaction':value['transaction_ref'],'direction':'inflow','amount':str(l.amount),'occurred_on':value['received_at'][:10]}
            proof=evidence(a,c,'forecast_actual',json.dumps(doc));return forecast.capture_actual(a,c.pk,proof.pk,rev(c),l.pk)
        # An explicitly prior-day verified cash source remains ineligible for
        # this current-day forecast, regardless of UTC/local midnight overlap.
        from datetime import timedelta
        _,prior_lot=receipt(a,c,ref='prior-business-day',received_at=(timezone.localtime()-timedelta(days=1)).isoformat())
        prior_actual=imported(prior_lot)
        with self.assertRaisesMessage(ValidationError,'predates original forecast cut-off'):
            match(a,c,s,prior_actual,'10',op='PRIOR-DAY-REJECTED')
        self.assertEqual(forecast.matched(s,'receipt-1'),0)
        old=imported(lot);m=match(a,c,s,old,'10');cash.reverse(a,c.pk,'lot',lot.pk,'Finance',e['cash_correction'].pk,'Full source correction',rev(c))
        held=forecast.prepare(a,c.pk,s.pk,rev(c));self.assertIsNone(held.result['periods'][0]['closing'])
        request=successor(a,c,lot,e,'40');correction_review(a,c,request,e,'cash');accepted=cash_successors.apply(a,c.pk,request.pk,'Finance',rev(c));new=imported(accepted.lot)
        self.assertEqual(new.supersedes_id,old.pk);proof=evidence(a,c,'forecast_match','Explicit source reversal reconciled');forecast.unmatch(a,c.pk,m.pk,proof.pk,'Reversed predecessor actual',rev(c));match(a,c,s,new,'10',op='SUCCESSOR-MATCH')
        self.assertEqual(forecast.matched(s,'receipt-1'),10);self.assertEqual(forecast.residual(s,s.payload['items'][0]),__import__('decimal').Decimal('17.25'))
