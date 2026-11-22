import json
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from unittest.mock import patch
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,close_old_connections
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.core.evidence_access import public_timeline
from apps.documents.models import PublicationJob
from apps.identity.models import Grant
from apps.pmo import engagement,engagement_won as won,planning
from apps.pmo.rfp_outcomes import historical_submission
from apps.pmo.models import Baseline
from apps.workflows import factory,factory_engagement as d
from apps.workflows.models import FactoryWork
from tests import test_rfp as upstream
from tests.helpers import rev
from tests.test_engagement_intake import activate
from tests.test_factory_engagement import register


def fixture(quote='100.00',*,create_work=True,reference='RFP-001'):
    a,c,e,t,route=upstream.fixture(reference=reference)
    terms=(json.dumps({'schema':'psl/rfp-commercial-terms/v1','amount':quote,'currency':'NGN','basis':'whole_contract',
        'terms':'Synthetic submitted client price only; no internal rates.'}) if quote is not None
        else 'Synthetic supplied terms do not establish an amount or currency.')
    e['rfp_commercial_terms']=add_evidence(a,c.pk,'rfp_commercial_terms',terms,'synthetic:won-public-terms')
    response=upstream.response(a,c,e);upstream.approve(a,c,e,response)
    version=upstream.rfp_documents.draft(a,c.pk,response.pk,t.pk,'client_bid',rev(c))
    upstream.request_review(a,c.pk,version.pk,rev(c))
    upstream.review_version(a,c.pk,version.pk,'approve','Synthetic exact submitted version',rev(c))
    upstream.reserve_publication(a,c.pk,version.pk,rev(c))
    job=PublicationJob.objects.get(publication__version=version)
    upstream.run_publication_once(case_id=c.pk,job_id=job.pk)
    # The actual matching business receipts below establish submission, not a job label.
    submission=upstream.rfp_documents.capture_submission(a,c.pk,version.pk,rev(c))
    outcome=upstream.rfp.outcome(a,c.pk,submission.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Synthetic actual win',rev(c))
    disposition=upstream.rfp.dispose(a,c.pk,outcome.pk,None,rev(c))
    profile=json.loads(Path('fixtures/factory-engagement.json').read_text());profile.pop('classification')
    activate(a,c,'OPS.factory_engagement_execution',profile,e['policy_decision'])
    rules=json.loads(Path('fixtures/engagement-intake.json').read_text())
    activate(a,c,'D11.engagement_assignment',rules['assignment'],e['policy_decision'])
    work=d.receive(a,c.pk,'WON-SOURCES','A',e['rfp_outcome'].pk,'SYN-WON-PLANNING',rev(c),disposition.pk) if create_work else None
    return {'a':a,'c':c,'e':e,'policy':e['policy_decision'],'w':work,'response':response,'submission':submission,'disposition':disposition}


class EngagementWonSourcesTests(TransactionTestCase):
    def test_actual_winning_inputs_are_carried_without_reusing_approval_or_inventing_costs(self):
        f=fixture();a,c,e=f['a'],f['c'],f['e']
        context=won.read(a,c)
        self.assertEqual(context['quoted_price'],{'amount':'100.00','currency':'NGN','basis':'whole_contract'})
        self.assertFalse(context['historical_authority_reused']);self.assertFalse(context['planning_approval_granted'])
        self.assertNotIn('costing',context)
        factory.run_until_wait(f['w'].pk)
        packet,value=planning.packet(c)
        expected={'prd_id':e['requirements'].pk,'scope_id':e['plan'].pk,
            'engineering_estimate_id':e['engineering_estimate'].pk,'security_estimate_id':e['security_estimate'].pk}
        self.assertEqual({k:value['payload'][k] for k in expected},expected)
        self.assertTrue(all(row['contact_id'] is None for row in value['payload']['stakeholders']))
        self.assertNotIn('100.00',packet.body);self.assertNotIn('quoted_price',packet.body)
        self.assertEqual(planning.report(a,c.pk)['status'],'dependent_readiness_held')
        self.assertTrue(any(row['code']=='correlation_unknown' for row in planning.report(a,c.pk)['source_correlation']['findings']))
        marker=c.audit.get(action='planning.won_sources_adopted')
        self.assertEqual(marker.data['packet'],packet.pk)
        self.assertFalse(public_timeline(c).filter(pk=marker.pk).exists())
        self.assertFalse(Baseline.objects.filter(case=c,signed__isnull=False).exists())

    def test_complete_engagement_keeps_real_planning_handoff_and_source_fields(self):
        f=fixture();a,c=f['a'],f['c'];factory.run_until_wait(f['w'].pk)
        # Reuse the fixture's actual current role bundle; only the new D11 assignment rule is needed.
        rules=json.loads(Path('fixtures/engagement-intake.json').read_text())
        activate(a,c,'D11.engagement_assignment',rules['assignment'],f['policy'])
        engagement.assign(a,c.pk,a.pk,'PMO Lead',f['e']['rfp_outcome'].pk,'won-manager')
        factory.run_until_wait(f['w'].pk)
        f['plan']=f['e']['plan'];f['e']=f['e']['rfp_outcome']
        register(f,value='SYN-WON-ID')
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        self.assertTrue(d.verified_output(f['w'])['verified'])
        child=FactoryWork.objects.get(pk=d.verified_output(f['w'])['planning_work'])
        self.assertEqual(child.source_head_id,planning.latest(c,'packet').pk)
        self.assertEqual(FactoryWork.objects.filter(case=c,definition='planning/v1').count(),1)

    def test_no_proposal_access_loads_no_proposal_payload_and_preserves_unknown_intake(self):
        f=fixture();a,c=f['a'],f['c']
        Grant.objects.filter(user=a,case=c,action='rfp.read').update(active=False)
        with patch('apps.pmo.engagement_won.historical_submission',side_effect=AssertionError('Payload read before permission')):
            with self.assertRaises(PermissionDenied):won.read(a,c)
            state=won.projection(a,c);self.assertTrue(state['held'])
            factory.run_until_wait(f['w'].pk)
        packet,value=planning.packet(c)
        self.assertEqual(value['payload'],d.empty_planning_payload())
        self.assertFalse(c.audit.filter(action='planning.won_sources_adopted').exists())
        self.assertTrue(engagement.Record.objects.filter(case=c,kind='capture').exists())

    def test_explicit_adoption_fills_unknowns_and_retains_human_questions_without_replacing_conflicts(self):
        f=fixture();a,c=f['a'],f['c'];payload=d.empty_planning_payload()
        payload['questions']=[{'key':'human-question','detail':'When is the client available?','state':'unresolved','action_id':None,'evidence_id':None}]
        original=planning.capture(a,c.pk,payload)
        adopted=won.adopt(a,c.pk,original.pk)
        _,current=planning.packet(c)
        self.assertEqual(current['payload']['questions'],payload['questions'])
        self.assertEqual(won.adopt(a,c.pk,adopted.pk).pk,adopted.pk)
        with self.assertRaises(ValidationError):won.adopt(a,c.pk,original.pk)
        different=add_evidence(a,c.pk,'plan','Independent human plan','synthetic:different-plan')
        supplied=dict(current['payload']);supplied['scope_id']=different.pk
        conflicting=planning.capture(a,c.pk,supplied,adopted.pk)
        count=c.evidence.count()
        with self.assertRaisesMessage(ValidationError,'Existing Planning sources differ'):won.adopt(a,c.pk,conflicting.pk)
        self.assertEqual(c.evidence.count(),count);self.assertEqual(planning.latest(c,'packet').pk,conflicting.pk)

    def test_current_reader_revocation_hides_quote_and_one_tap_manager_source(self):
        f=fixture();a,c=f['a'],f['c'];self.client.force_login(a)
        page=self.client.get(reverse('factory_detail',args=[f['w'].pk]))
        self.assertContains(page,'NGN 100.00');self.assertContains(page,'Winning proposal')
        from apps.workflows.factory_engagement_views import human_forms
        manager=next(panel['form'] for panel in human_forms(a,f['w']) if panel['operation']=='assign')
        self.assertEqual(manager.fields['pm_id'].initial,a.pk)
        self.assertEqual(manager.fields['evidence_id'].initial,f['e']['rfp_outcome'].pk)
        Grant.objects.filter(case=c,user=a,action='rfp.read').update(active=False)
        page=self.client.get(reverse('factory_detail',args=[f['w'].pk]))
        self.assertNotContains(page,'NGN 100.00');self.assertContains(page,'current proposal access')
        self.assertNotContains(self.client.get(reverse('planning',args=[c.pk])),'Use supplied sources from the winning proposal')

    def test_unknown_quote_remains_unknown(self):
        f=fixture(quote=None)
        self.assertIsNone(won.read(f['a'],f['c'])['quoted_price'])
        self.client.force_login(f['a'])
        page=self.client.get(reverse('factory_detail',args=[f['w'].pk]))
        self.assertContains(page,'Unknown — the supplied terms do not establish a structured amount')
        self.assertNotContains(page,'NGN 0')

    def test_explicit_zero_quote_is_preserved(self):
        f=fixture(quote='0.00')
        self.assertEqual(won.read(f['a'],f['c'])['quoted_price']['amount'],'0.00')
        self.client.force_login(f['a'])
        self.assertContains(self.client.get(reverse('factory_detail',args=[f['w'].pk])),'NGN 0.00')

    def test_historical_manifest_and_cost_kind_checks_do_not_load_internal_cost_bodies(self):
        f=fixture();a,c=f['a'],f['c'];cost_id=f['e']['costing'].pk
        with CaptureQueriesContext(connection) as queries:
            actual=historical_submission(c,f['submission'])
        self.assertEqual(actual.pk,f['response'].pk)
        cost_queries=[row['sql'] for row in queries if 'FROM "core_evidence"' in row['sql'] and
                      re.search(r'"core_evidence"\."id" = '+str(cost_id)+r'\D',row['sql'])]
        self.assertTrue(cost_queries)
        self.assertTrue(all('"core_evidence"."body"' not in sql.split(' FROM ',1)[0] for sql in cost_queries))
        with CaptureQueriesContext(connection) as queries:won.read(a,c)
        self.assertLess(len(queries),90)

    def test_new_private_finance_reference_blocks_before_proposal_bodies_are_loaded(self):
        from tests import forecast_helpers
        f=fixture();a,c=f['a'],f['c']
        value=forecast_helpers.payload(a,c)
        value['items'][0]['evidence_id']=f['e']['rfp_commercial_terms'].pk
        forecast_helpers.scenario(a,c,value)
        with patch('apps.pmo.engagement_won.historical_submission',side_effect=AssertionError('Historical payload read before current classification')):
            with CaptureQueriesContext(connection) as queries:
                with self.assertRaises(PermissionDenied):won.read(a,c)
        selected=[row['sql'].split(' FROM ',1)[0] for row in queries]
        self.assertFalse(any('"core_evidence"."body"' in sql or '"documents_version"."fields"' in sql for sql in selected))
        from apps.workflows.factory_engagement_views import human_forms
        with patch('apps.pmo.rfp_outcomes.historical_submission',side_effect=AssertionError('Manager reuse read before current classification')):
            panel=next(p['form'] for p in human_forms(a,f['w']) if p['operation']=='assign')
        self.assertIsNone(panel.fields['pm_id'].initial)

    def test_original_capture_owner_revocation_blocks_both_reuse_readers(self):
        f=fixture();a,c=f['a'],f['c']
        creator=get_user_model().objects.create_user(username='won-capture-recorder')
        Grant.objects.bulk_create([Grant(user=creator,case=c,action=action) for action in ['case.read','engagement.read','engagement.capture']])
        engagement.capture(creator,c.pk,'A',f['e']['rfp_outcome'].pk,'source-owner-reaffirmed','fresh-owner-capture',f['disposition'].pk)
        Grant.objects.filter(user=creator,case=c,action='engagement.capture').update(active=False)
        with patch('apps.pmo.engagement_won.historical_submission',side_effect=AssertionError('Read before original source authority')):
            with self.assertRaises(PermissionDenied):won.read(a,c)
        with patch('apps.pmo.rfp_outcomes.historical_submission',side_effect=AssertionError('Manager read before original source authority')):
            with self.assertRaises(PermissionDenied):engagement.won_rfp_manager(a,c)

    def test_concurrent_adoption_preserves_the_first_successor_and_rejects_the_stale_form(self):
        f=fixture();a,c=f['a'],f['c'];original=planning.capture(a,c.pk,d.empty_planning_payload());barrier=Barrier(2)
        def adopt(_):
            close_old_connections()
            try:
                barrier.wait(timeout=30)
                try:return ('saved',won.adopt(a,c.pk,original.pk).pk)
                except ValidationError:return ('stale',None)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(adopt,range(2)))
        self.assertEqual(sorted(row[0] for row in results),['saved','stale'])
        self.assertEqual(c.evidence.filter(kind='planning_packet').count(),2)
        self.assertEqual(c.audit.filter(action='planning.won_sources_adopted').count(),1)

    def test_adoption_checks_supplied_document_kinds_without_loading_their_bodies(self):
        f=fixture();a,c=f['a'],f['c'];ids=[f['e'][kind].pk for kind in ['requirements','plan','engineering_estimate','security_estimate','costing']]
        with CaptureQueriesContext(connection) as queries:won.adopt(a,c.pk)
        inspected=[]
        for row in queries:
            sql=row['sql']
            if 'FROM "core_evidence"' in sql and any(re.search(r'"core_evidence"\."id" = '+str(pk)+r'\D',sql) for pk in ids):
                inspected.append(sql.split(' FROM ',1)[0])
        self.assertTrue(inspected)
        self.assertFalse(any('"core_evidence"."body"' in sql for sql in inspected))
