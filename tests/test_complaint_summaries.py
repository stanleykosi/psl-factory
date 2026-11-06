import json,copy
from pathlib import Path
from datetime import timedelta
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from django.test import TransactionTestCase,Client
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,close_old_connections
from django.urls import reverse
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.summary_validators import SCOPE,REVIEW,SCHEMAS,validate_reference
from apps.policy.support_drafts import draft_support_policy
from apps.policy.services import transition
from apps.baas import summaries as d
from apps.agents.complaint_summaries import draft
from tests.support_helpers import fixture,ready,report,act,policy

class ComplaintSummaryTests(TransactionTestCase):
    def fixture(self):
        f=fixture('summary-root');g=fixture('summary-other',people=[f['actor'],f['reviewer'],f['specialist']]);g['t']=f['t']+timedelta(minutes=5);g['v']['message']['received_at']=g['t'].isoformat()
        ready(f);ready(g);report(f);report(g)
        e=add_evidence(f['actor'],f['case'].pk,d.REQUEST_EVIDENCE,'Synthetic defined-period selected-case summary request','synthetic:summary')
        review=add_evidence(f['reviewer'],f['case'].pk,d.REVIEW_EVIDENCE,'Synthetic review of exact source coverage and omissions','synthetic:summary')
        v=json.loads(Path('fixtures/complaint-summaries.json').read_text());v['review_template']['reviewer_id']=f['reviewer'].pk;v['review_template']['audiences'][0]['recipient_ids']=[f['reviewer'].pk]
        return f,g,e,review,v

    def config(self,f,component,value):
        p=draft_support_policy(f['actor'],f['case'].pk,component,value,f['e']['policy_decision'].pk,timezone.now());transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p

    def request(self,f,g,e,key='request',**changes):
        values={'reference':'period-summary','source_case_ids':[str(f['case'].pk),str(g['case'].pk)],'start':f['t'].isoformat(),'end':(f['t']+timedelta(minutes=10)).isoformat(),'membership':'linked_receipt_half_open_v1','audience':'internal-reviewed','evidence_id':e.pk,'key':key};values.update(changes)
        return d.capture(f['actor'],f['case'].pk,**values)

    def test_capture_before_criteria_agent_draft_reviewed_projection_ui_privacy_and_revocation(self):
        f,g,e,review,v=self.fixture();a,b,c=f['actor'],f['reviewer'],f['case'];r=self.request(f,g,e)
        self.assertEqual(self.request(f,g,e).pk,r.pk)
        with self.assertRaises(ValidationError):d.prepare(a,c.pk,r.pk,'missing-scope')
        self.config(f,SCOPE,v['scope']);agent=draft(a,c.pk,r.pk,'agent-draft');version=d.Version.objects.get(pk=agent['version_id'])
        self.assertTrue(agent['human_review_required']);self.assertEqual(agent['included_cases'],2);self.assertFalse(version.result['source_bodies_included'])
        self.assertEqual(version.result['merge_uncertainty'][0]['finding'],'same_supplied_identity_unmerged')
        self.assertIn('source_references',d.read(a,c.pk,version.pk)['result']['rows'][0])
        with self.assertRaises(ValidationError):d.review(b,c.pk,version.pk,'approve',review.pk,'missing-review-policy')
        self.config(f,REVIEW,v['review_template']);accepted=d.review(b,c.pk,version.pk,'approve',review.pk,'human-approve')
        value=d.read(b,c.pk,version.pk,reviewed=True);self.assertEqual(value['review'],accepted.pk)
        self.assertNotIn('source_references',value['result']['rows'][0]);self.assertNotIn('metrics',value['result']['rows'][0])
        with self.assertRaises(PermissionDenied):d.read(a,c.pk,version.pk,reviewed=True)
        client=Client();client.force_login(b);self.assertContains(client.get(reverse('complaint_summaries',args=[c.pk])),'Period and scope complaint summaries')
        response=client.get(reverse('complaint_summary_export',args=[c.pk,version.pk]));self.assertEqual(response.status_code,200);self.assertIn('attachment;',response['Content-Disposition'])
        client.force_login(a);case=client.get(reverse('case',args=[c.pk]));self.assertNotContains(case,'Synthetic defined-period selected-case summary request')
        for model in [d.Request,d.Version,d.Review]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.all().update(created_at=timezone.now())
        Grant.objects.filter(case=g['case'],user=b,action='support.read').update(active=False)
        with self.assertRaises(PermissionDenied):d.read(b,c.pk,version.pk,reviewed=True)
        Grant.objects.filter(case=g['case'],user=a,action='support.read').update(active=False)
        self.assertFalse(d.visible_requests(a,c).exists())
        with self.assertRaises(PermissionDenied):self.request(f,g,e,'unauthorized-successor')

    def test_period_boundaries_missing_sources_metrics_and_source_successor_hold(self):
        f,g,e,review,v=self.fixture();a,c=f['actor'],f['case'];self.config(f,SCOPE,v['scope'])
        # A receipt exactly at end is excluded from the half-open selection.
        r=self.request(f,g,e,end=g['t'].isoformat());version=d.prepare(a,c.pk,r.pk,'boundary')
        self.assertEqual(version.result['included_count'],1);self.assertEqual(version.result['outside_period'][0]['case_id'],str(g['case'].pk))
        h=fixture('summary-unconfigured',people=[a,f['reviewer'],f['specialist']],configured=False)
        ids=r.payload['source_case_ids']+[str(h['case'].pk)]
        newer=self.request(f,g,e,'larger-scope',source_case_ids=ids)
        with self.assertRaises(ValidationError):d.read(a,c.pk,version.pk)
        next_version=d.prepare(a,c.pk,newer.pk,'with-omission');self.assertEqual(next_version.result['omitted_count'],1);self.assertEqual(next_version.result['omissions'][0]['period_membership'],'unknown')
        self.assertIsNone(next_version.result['rows'][0]['metrics']['first_response_seconds'])
        act(f,'investigate')
        with self.assertRaises(ValidationError):d.read(a,c.pk,next_version.pk)
        # A new current case report permits an explicit successor summary.
        report(f);successor=d.prepare(a,c.pk,newer.pk,'new-source-version');self.assertNotEqual(successor.pin,next_version.pin)

    def test_scope_configuration_independence_budget_and_cross_proof_guards(self):
        f,g,e,review,v=self.fixture();a,b,c=f['actor'],f['reviewer'],f['case']
        for component,name in [(SCOPE,'scope'),(REVIEW,'review_template')]:
            bad={**v[name],'allow_synthetic':False}
            with self.assertRaises(ValidationError):validate_reference(component,SimpleNamespace(schema_ref=SCHEMAS[component][0],content=bad),c)
        self.config(f,SCOPE,{**v['scope'],'max_cases':1});r=self.request(f,g,e)
        with self.assertRaises(ValidationError):d.prepare(a,c.pk,r.pk,'over-budget')
        self.config(f,SCOPE,v['scope']);version=d.prepare(a,c.pk,r.pk,'current-draft')
        self.config(f,REVIEW,{**v['review_template'],'reviewer_id':a.pk})
        with self.assertRaises(PermissionDenied):d.review(a,c.pk,version.pk,'approve',review.pk,'self-review')
        self.config(f,REVIEW,v['review_template']);accepted=d.review(b,c.pk,version.pk,'approve',review.pk,'current-review')
        foreign=add_evidence(a,g['case'].pk,d.REVIEW_EVIDENCE,'Synthetic foreign review proof','synthetic:summary')
        with self.assertRaises(ValidationError):d.review(b,c.pk,version.pk,'approve',foreign.pk,'foreign-proof')
        with self.assertRaises(DatabaseError),transaction.atomic():d.Review.objects.create(version=version,verdict='approve',operation_key='sql-foreign-proof',pin=accepted.pin,evidence=foreign,actor=b)
        bad_ids=[str(c.pk),str(c.pk)]
        with self.assertRaises(ValidationError):self.request(f,g,e,'duplicate-scope',source_case_ids=bad_ids)

    def test_two_connections_converge_on_one_draft(self):
        f,g,e,review,v=self.fixture();self.config(f,SCOPE,v['scope']);r=self.request(f,g,e);barrier=Barrier(2)
        def prepare(_):
            close_old_connections()
            try:barrier.wait(timeout=30);return d.prepare(f['actor'],f['case'].pk,r.pk,'same-draft').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(prepare,range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(d.Version.objects.count(),1)

    def test_actual_merge_reopen_and_unknown_clock_are_explicit(self):
        from apps.baas import support
        f,g,e,review,v=self.fixture();a,c=f['actor'],f['case']
        support.merge(a,g['case'].pk,c.pk,g['e']['support_merge'].pk,timezone.now().isoformat())
        report(f);report(g);self.config(f,SCOPE,v['scope']);r=self.request(f,g,e)
        omitted=d.prepare(a,c.pk,r.pk,'merged-omission');self.assertEqual(omitted.result['included_count'],1)
        self.assertEqual(omitted.result['omissions'][0]['finding'],'merged_case_omitted');self.assertFalse(omitted.result['omissions'][0]['canonical_target_disclosed'])
        self.config(f,SCOPE,{**v['scope'],'merged_case_behavior':'include_marked'})
        marked=d.prepare(a,c.pk,r.pk,'merged-marked');self.assertTrue(next(row for row in marked.result['rows'] if row['case_id']==str(g['case'].pk))['merged'])
        act(f,'investigate');act(f,'resolve');act(f,'reopen');report(f)
        reopened=d.prepare(a,c.pk,r.pk,'after-reopen');row=next(row for row in reopened.result['rows'] if row['case_id']==str(c.pk))
        self.assertTrue(row['reopened']);self.assertIsNone(row['metrics']['resolution_seconds']);self.assertEqual(row['metrics']['finding'],'reopened_clock_undefined')

    def test_event_membership_and_current_audience_successor(self):
        f,g,e,review,v=self.fixture();a,b,c=f['actor'],f['reviewer'],f['case'];at=timezone.now()-timedelta(minutes=5)
        act(f,'investigate',at);report(f)
        rules={**v['scope'],'membership':'event_activity_half_open_v1'};self.config(f,SCOPE,rules)
        r=self.request(f,g,e,membership=rules['membership'],start=at.isoformat(),end=(at+timedelta(seconds=1)).isoformat())
        version=d.prepare(a,c.pk,r.pk,'event-period');self.assertEqual(version.result['included_count'],1);self.assertEqual(version.result['rows'][0]['case_id'],str(c.pk))
        self.config(f,REVIEW,v['review_template']);d.review(b,c.pk,version.pk,'approve',review.pk,'event-review')
        self.assertEqual(d.read(b,c.pk,version.pk,reviewed=True)['result']['included_count'],1)
        self.config(f,REVIEW,{**v['review_template'],'audiences':[{'key':'internal-reviewed','recipient_ids':[a.pk],'fields':[]}]})
        with self.assertRaises(PermissionDenied):d.read(b,c.pk,version.pk,reviewed=True)

    def test_reviewer_must_inspect_draft_and_recipients_need_only_reviewed_projection(self):
        f,g,e,review,v=self.fixture();a,b,c=f['actor'],f['reviewer'],f['case'];self.config(f,SCOPE,v['scope']);r=self.request(f,g,e)
        version=d.prepare(a,c.pk,r.pk,'review-inspection')
        values=copy.deepcopy(v['review_template']);values['audiences'][0]['recipient_ids']=[a.pk,b.pk]
        self.config(f,REVIEW,values);d.review(b,c.pk,version.pk,'approve',review.pk,'review-inspected')
        Grant.objects.filter(case=c,user=a,action='support.summary.draft_read').update(active=False)
        with self.assertRaises(PermissionDenied):d.read(a,c.pk,version.pk)
        self.assertNotIn('source_references',d.read(a,c.pk,version.pk,reviewed=True)['result']['rows'][0])
        Grant.objects.filter(case=c,user=b,action='support.summary.draft_read').update(active=False)
        with self.assertRaises(PermissionDenied):d.review(b,c.pk,version.pk,'approve',review.pk,'review-without-inspection')
        with self.assertRaises(PermissionDenied):d.read(a,c.pk,version.pk,reviewed=True)
