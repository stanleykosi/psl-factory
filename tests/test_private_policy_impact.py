"""Actual domain metadata; engineering review never grants payload/effect authority."""
import json
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.policy import impact
from apps.policy.services import resolve
from tests.helpers import rev


class PrivateImpactTests(TestCase):
    def assessed(self,a,c,old,new,key,pk):
        evidence=add_evidence(a,c.pk,'policy_decision','Explicit synthetic engineering reassessment evidence','synthetic:impact')
        reviewer=get_user_model().objects.create_user(username='private-impact-reviewer')
        Grant.objects.bulk_create([Grant(user=reviewer,case_id=case_id,action=k) for case_id,k in Grant.objects.filter(user=a,active=True).values_list('case_id','action')])
        page=impact.page(a,c.pk,old.pk,key)
        self.assertIn(pk,[r['id'] for r in page['records']])
        row=impact.capture(a,c.pk,old.pk,new.pk,[key],evidence.pk,'Check declared private metadata against current policy')
        impact.review(reviewer,c.pk,row.pk,'accept',evidence.pk,'Independent engineering reassessment only')
        report=impact.inspect(a,c.pk,row.pk)
        self.assertTrue(report['current']);self.assertFalse(report['business_approval']);self.assertEqual(report['effect_tools'],[])
        value=json.dumps(report)
        for private in ['E001','E002','250.00','PRIVATE TRACE','QB-101','TX-001']:
            self.assertNotIn(private,value)
        return row,reviewer,evidence

    def test_payroll_rule_change_is_inspectable_without_staff_values_and_current_grants_apply(self):
        from tests import payroll_helpers as h
        from apps.policy.payroll_validators import MERGE
        f=h.fixture();run=h.combined(f);old=f['policies'][MERGE];new=h.policy(f,MERGE,f['config']['merge'])
        a,c=f['preparer'],f['case'];row,_,_=self.assessed(a,c,old,new,'finance.payroll_work',run.pk)
        with self.assertRaises(ValidationError):
            from apps.finance.payroll import private_run
            private_run(a,c.pk,run.pk)
        h.combined(f,key='current-policy-successor')
        self.assertFalse(impact.inspect(a,c.pk,row.pk)['current'])
        Grant.objects.filter(user=a,case=c,action='payroll.read').update(active=False)
        with self.assertRaises(PermissionDenied):impact.inspect(a,c.pk,row.pk)

    def test_hr_disclosure_metadata_does_not_read_staff_snapshot(self):
        from tests import hrfinance_helpers as h
        from apps.policy.hrfinance_validators import DISCLOSURE
        f=h.fixture();h.capture(f);old=f['disclosure_policy']
        new=h.policy(f['hr'],f['case'],DISCLOSURE,f['config']['disclosure'],f['e']['owner'])
        self.assessed(f['hr'],f['case'],old,new,'finance.hr_disclosures',f['contract'].pk)

    def test_bu_work_and_upstream_payroll_policy_lineage_are_declared_metadata(self):
        from tests import bu_helpers as h
        from apps.policy.bu_validators import SOURCE
        f=h.fixture();source=h.source(f);old=f['bu_policies'][SOURCE];new=h.policy(f,SOURCE,f['bu_config']['source'])
        self.assessed(f['preparer'],f['case'],old,new,'finance.bu_work',source.pk)

    def test_ledger_projection_rechecks_all_historical_private_participants_before_projection(self):
        from tests import ledger_agent_helpers as h
        from tests.ledger_resolution_helpers import second_case,propose,confirm,current
        from tests.ledger_helpers import capture,verify,policy
        from apps.policy.ledger_validators import PROJECTION
        f=h.fixture('impact-private');g=second_case(f);g['case'].tenant=f['case'].tenant;g['case'].save(update_fields=['tenant'])
        other=capture(g);verify(g,other);verify(f,f['lineage']);r=propose(f,f['lineage'],[other]);confirm(f,r);current(f,f['lineage'])
        projection=h.project(f);old=f['native_policy'];new=policy(f,PROJECTION,f['native_rules'])
        row,reviewer,_=self.assessed(f['actor'],f['case'],old,new,'finance.ledger_projections',projection.pk)
        Grant.objects.filter(user=f['actor'],case=g['case'],action='ledger.private.read').update(active=False)
        with self.assertRaises(PermissionDenied):impact.page(f['actor'],f['case'].pk,old.pk,'finance.ledger_projections')
        with self.assertRaises(PermissionDenied):impact.inspect(f['actor'],f['case'].pk,row.pk)

    def test_verified_publication_receipts_remain_distinct_from_new_audience_authority(self):
        from tests.document_helpers import publication_fixture,reserved,artifact
        from apps.documents.delivery import run_publication_once
        a,c,e,source,template,recipient,recipients,old=publication_fixture()
        publication=reserved(a,c,template,source);run_publication_once()
        new=artifact(a,c,old.component,'schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},e)
        row,_,_=self.assessed(a,c,old,new,'documents.publication_effects',publication.pk)
        self.assertEqual(row.observation['domains']['documents.publication_effects'][0]['state'],'committed_effect')
        self.assertTrue(row.observation['domains']['documents.publication_effects'][0]['receipts'])

    def test_reviewed_private_draft_uses_source_permissions_in_http_and_agent_reads(self):
        from tests import ledger_agent_helpers as h
        from tests.ledger_helpers import policy
        from tests.readiness_helpers import endpoint
        from apps.finance import ledger_agents as native
        from apps.policy.ledger_validators import PROJECTION
        from apps.agents.policy_impact import investigate
        from django.test import Client
        from django.urls import reverse
        f=h.fixture('impact-draft')
        with endpoint():
            receipt=h.extracted(f)
            draft=native.reuse(f['actor'],f['case'].pk,receipt.pk,'reviewed-draft')
            native.review(f['reviewer'],f['case'].pk,draft.pk,'approve')
        old=f['native_policy'];new=policy(f,PROJECTION,f['native_rules'])
        a,c=f['actor'],f['case'];row,reviewer,e=self.assessed(a,c,old,new,'finance.ledger_drafts',draft.pk)
        client=Client(enforce_csrf_checks=True);client.force_login(a)
        url=reverse('policy_impact',args=[c.pk]);self.assertContains(client.get(url),'finance.ledger_drafts')
        self.assertEqual(client.post(url,{}).status_code,403)
        response=client.get(reverse('policy_impact_assessment',args=[c.pk,row.pk]))
        self.assertContains(response,'private_draft_requires_revalidation');self.assertNotContains(response,'QB-101')
        run=investigate(a,c.pk,row.pk);self.assertEqual(run['effect_tools'],[])
        self.assertNotIn('QB-101',json.dumps(run))
        Grant.objects.filter(user=a,case=c,action='ledger.private.read').update(active=False)
        for url in [url,reverse('policy_impact_assessment',args=[c.pk,row.pk]),reverse('policy_impact_records',args=[c.pk,old.pk,'finance.ledger_drafts'])]:
            response=client.get(url)
            if response.status_code==200:self.assertNotContains(response,'private_draft_requires_revalidation')
            else:self.assertEqual(response.status_code,403)
        with self.assertRaises(PermissionDenied):investigate(a,c.pk,row.pk)


    def test_partial_recipient_receipts_are_conflicts_and_never_proof_of_committed_publication(self):
        from tests.document_helpers import publication_fixture,reserved,artifact
        from tests.helpers import activate
        from apps.policy.services import register_reference
        from apps.documents.models import PublicationReceipt,PublicationJob
        from apps.agents.policy_impact import investigate
        a,c,e,source,template,first,recipients,old=publication_fixture()
        second=get_user_model().objects.create_user(username='second-impact-recipient')
        Grant.objects.create(user=second,case=c,action='document.receive:client')
        ref=register_reference(a,c.pk,'second-impact-recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':second.pk},e.pk)
        activate(a,c,'D11.recipient_grant_refs',recipients.envelope['value']+[ref.ref],e)
        publication=reserved(a,c,template,source)
        # Adversarial persisted partial state, not a successful workflow or external receipt.
        PublicationReceipt.objects.create(publication=publication,recipient=first,operation_key='partial-fixture',payload=publication.version.payload,payload_sha256=publication.version.payload_sha256)
        new=artifact(a,c,old.component,'schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},e)
        row=impact.capture(a,c.pk,old.pk,new.pk,['documents.publication_effects'],e.pk,'Investigate incomplete historical recipient evidence')
        self.assertEqual(row.observation['domains']['documents.publication_effects'][0]['state'],'receipt_conflict_requires_reconciliation')
        report=investigate(a,c.pk,row.pk);self.assertEqual(len(report['receipt_conflicts']),1)
        self.assertEqual(report['committed_effects'],[]);self.assertEqual(report['effect_tools'],[])
        self.assertEqual(PublicationReceipt.objects.count(),1)
        self.assertEqual(PublicationJob.objects.get(publication=publication).attempts,0)


from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import transaction,close_old_connections
from django.test import TransactionTestCase


class PrivateImpactConcurrencyTests(TransactionTestCase):
    def test_busy_native_publication_job_holds_assessment_without_wait_or_effect(self):
        from tests.document_helpers import publication_fixture,reserved,artifact
        from apps.documents.models import PublicationJob,PublicationReceipt
        from apps.policy.models import ImpactAssessment
        a,c,e,source,template,recipient,recipients,old=publication_fixture()
        publication=reserved(a,c,template,source)
        new=artifact(a,c,old.component,'schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},e)
        locked,release=Event(),Event()
        def holder():
            close_old_connections()
            try:
                with transaction.atomic():
                    PublicationJob.objects.select_for_update().get(publication=publication);locked.set()
                    self.assertTrue(release.wait(20))
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(holder);self.assertTrue(locked.wait(10))
            try:
                with self.assertRaisesMessage(ValidationError,'Publication work is being reconciled'):
                    impact.capture(a,c.pk,old.pk,new.pk,['documents.publication_effects'],e.pk,'Do not race a native worker')
            finally:release.set()
            future.result(timeout=25)
        self.assertFalse(ImpactAssessment.objects.exists());self.assertFalse(PublicationReceipt.objects.exists())
        job=PublicationJob.objects.get(publication=publication);self.assertEqual((job.status,job.fence,job.attempts),('pending',0,0))
