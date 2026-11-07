import json
from pathlib import Path
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.pmo import commercial_intake,commercial
from apps.pmo.models import CommercialDecision,CommercialDocumentBinding
from apps.pmo.costing_models import CostingRun
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,register_reference
from apps.documents.controlled import register_template,reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt,Publication,PublicationJob
from apps.agents.models import AgentRun
from apps.workflows import factory,factory_commercial
from apps.workflows.models import FactoryWork,HumanTask
from adapters.commercial_intake import FIELDS
from tests.costing_helpers import fixture as costing_fixture
from tests.document_helpers import artifact
from tests.helpers import activate,rev

DEFINITION={'document_type':'sow','required_fields':['executive_summary','scope','timeline'],'audience_fields':{'client': ['executive_summary', 'scope', 'timeline', 'risks', 'dependencies', 'status']}}

def setup(configure=True,missing=False):
    f=costing_fixture();a=f['actor'];c=f['case'];e=f['sources']
    t=register_template(a,c.pk,'Synthetic factory client SOW',DEFINITION,e['policy_decision'].pk,rev(c))
    r=register_reference(a,c.pk,'factory-commercial:recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':a.pk},e['policy_decision'].pk)
    activate(a,c,'D11.recipient_grant_refs',[r.ref],e['policy_decision'])
    artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30},e['policy_decision'])
    values={key:None for key in FIELDS}
    values.update({key:e[key].pk for key in commercial_intake.PUBLIC})
    values.update(inputs=f['inputs'].pk,rule_id=f['rule'].pk,oracle_id=f['oracle'].pk,template_id=t.pk,context_id=e['requirements'].pk)
    if missing:values['engineering_estimate']=None
    head=commercial_intake.capture(a,c.pk,values)
    value=json.loads(Path('fixtures/factory-commercial.json').read_text());value.pop('classification');value['executor_id']=a.pk
    if configure:
        p=draft_operator_policy(a,c.pk,'OPS.factory_commercial_execution',value,e['policy_decision'].pk,timezone.now())
        transition(a,p.pk,'validated');transition(a,p.pk,'active');f['execution_profile']=p
    w=factory_commercial.start(a,c.pk,'COMMERCIAL-1',head.pk,'Commercial factory example',rev(c))
    f.update(work=w,head=head,intake=values,template=t,execution_value=value)
    return f

class FactoryCommercialTests(TestCase):
    def test_primary_http_decisions_use_native_records_and_reject_stale_resubmission(self):
        f=setup();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        self.client.force_login(f['actor']);url=reverse('factory_detail',args=[w.pk])+'?queue=decisions&q=Commercial'
        for role in commercial.ROLES:
            w.refresh_from_db();data={'action':'commercial_decision','kind':'commercial','target':role,'verdict':'approve','revision':w.revision,'note':'Synthetic exact source review'}
            self.assertRedirects(self.client.post(url,data),url)
            count=CommercialDecision.objects.count()
            self.assertContains(self.client.post(url,data),'STALE_VERSION');self.assertEqual(CommercialDecision.objects.count(),count)
        factory.run_until_wait(w.pk);w.refresh_from_db();version=factory_commercial.document(w)
        self.assertRedirects(self.client.post(url,{'action':'commercial_decision','kind':'document','target':version.pk,'verdict':'approve','revision':w.revision,'note':'Synthetic exact client payload'}),url)
        self.assertEqual(version.reviews.count(),1)
        self.assertFalse(HumanTask.objects.filter(case=f['case'],kind='factory_review').exists())
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        page=self.client.get(url);self.assertContains(page,'Declared costing, the reviewed client version and its recipient receipts match.')

    def test_corrected_source_before_dispatch_preserves_the_original_unsent_publication(self):
        f=setup();version=self.prepared_review(f);factory.run_once(f['work'].pk)
        publication=Publication.objects.get(version=version)
        source=add_evidence(f['actor'],f['case'].pk,'sow','Synthetic corrected source before any send','synthetic:before-dispatch')
        commercial_intake.capture(f['actor'],f['case'].pk,dict(f['intake'],sow=source.pk),f['head'].pk)
        run_publication_once(case_id=f['case'].pk,job_id=publication.job.pk);publication.job.refresh_from_db()
        self.assertEqual(publication.job.status,'held');self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
        self.assertEqual(publication.factory_source_id,f['head'].pk)

    def test_reviewed_costing_policy_rollforward_creates_a_fresh_unapproved_proposal(self):
        from tests.costing_helpers import policy
        f=setup();w=f['work'];self.prepared_review(f);factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'verified',w.finding)
        old=factory_commercial.proposal(w);old_run=factory_commercial.calculation(w);spent=w.budget_used
        policy(f)
        factory_commercial.reassess(f['actor'],w.pk,w.revision,'Review the newly activated native costing contract')
        factory.run_until_wait(w.pk);w.refresh_from_db()
        revised=factory_commercial.proposal(w)
        self.assertEqual(w.status,'waiting',w.finding);self.assertNotEqual(revised.pk,old.pk);self.assertEqual(revised.previous_id,old.pk)
        self.assertNotEqual(factory_commercial.calculation(w).pk,old_run.pk)
        self.assertFalse(CommercialDecision.objects.filter(revision=revised).exists())
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=w).count(),1)
        self.assertEqual(w.source_head_id,f['head'].pk);self.assertGreater(w.budget_used,spent);self.assertEqual(w.budget_limit,20000)

    def test_revoked_private_source_authority_holds_selected_dispatch(self):
        from apps.identity.models import Grant
        f=setup();version=self.prepared_review(f);factory.run_once(f['work'].pk)
        publication=Publication.objects.get(version=version)
        Grant.objects.filter(case=f['case'],user=f['actor'],action='costing.source.read').update(active=False)
        run_publication_once(case_id=f['case'].pk,job_id=publication.job.pk);publication.job.refresh_from_db()
        self.assertEqual(publication.job.status,'held');self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())

    def test_unprivileged_factory_reader_has_no_private_costing_or_intake_projection(self):
        from django.contrib.auth import get_user_model
        from apps.identity.models import Grant
        f=setup();factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        reader=get_user_model().objects.create_user(username='synthetic-commercial-reader')
        Grant.objects.bulk_create([Grant(case=f['case'],user=reader,action=action) for action in ['case.read','factory.read']])
        panel=factory_commercial.projection(reader,f['work'])
        self.assertIsNone(panel['costing_report']);self.assertIsNone(panel['intake_sources']);self.assertEqual(panel['owner_reviews'],[])
        self.assertIsNotNone(factory_commercial.projection(f['actor'],f['work'])['costing_report'])
        self.client.force_login(reader);page=self.client.get(reverse('factory_detail',args=[f['work'].pk]))
        self.assertEqual(page.status_code,200);self.assertNotContains(page,'"investigation"')

    def test_selected_agent_worker_leaves_an_unrelated_human_publication_pending(self):
        from tests.test_commercial_changes import fixture as legacy_fixture,proposal as legacy_proposal,approvals as legacy_approvals
        from apps.documents.controlled import request_review,review_version
        a,c,e,t=legacy_fixture(username='unrelated-commercial-publisher')
        proposal=legacy_proposal(a,c,e);legacy_approvals(a,c,proposal)
        version=commercial.draft_submission(a,c.pk,proposal.pk,t.pk,rev(c));request_review(a,c.pk,version.pk,rev(c));review_version(a,c.pk,version.pk,'approve','Synthetic unrelated native client version',rev(c))
        unrelated=reserve_publication(a,c.pk,version.pk,rev(c))
        f=setup();self.prepared_review(f);factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'verified',f['work'].finding)
        unrelated.job.refresh_from_db();self.assertEqual(unrelated.job.status,'pending');self.assertEqual(unrelated.job.attempts,0)
        self.assertFalse(PublicationReceipt.objects.filter(publication=unrelated).exists())

    def test_unchanged_unknown_receipt_parks_without_model_polling_or_duplicate_effect(self):
        from adapters.publications import InternalPublicationAdapter
        class Unavailable(InternalPublicationAdapter):
            def lookup(self,publication):return None
            def deliver(self,job_id,fence):raise TimeoutError('Synthetic unavailable local transport')
        f=setup();self.prepared_review(f);factory.run_until_wait(f['work'].pk,adapter=Unavailable());f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'waiting_effect',f['work'].finding);spent=f['work'].budget_used
        factory.run_until_wait(f['work'].pk,adapter=Unavailable());f['work'].refresh_from_db()
        self.assertEqual(f['work'].budget_used,spent);self.assertFalse(PublicationReceipt.objects.filter(publication__factory_work=f['work']).exists())

    def test_reviewed_source_reassessment_keeps_receipts_and_original_budget(self):
        f=setup();w=f['work'];self.prepared_review(f);factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'verified',w.finding);spent=w.budget_used
        previous=factory_commercial.proposal(w)
        sow=add_evidence(f['actor'],f['case'].pk,'sow','Synthetic revised client scope after feedback','synthetic:commercial-rework')
        values=dict(f['intake'],sow=sow.pk,predecessor_id=previous.pk)
        head=commercial_intake.capture(f['actor'],f['case'].pk,values,f['head'].pk)
        self.client.force_login(f['actor']);self.assertContains(self.client.get(reverse('home')+'?queue=exceptions'),'Prior commercial submission needs review')
        self.assertNotContains(self.client.get(reverse('home')+'?queue=verified'),'Commercial factory example')
        self.assertNotContains(self.client.get(reverse('factory_detail',args=[w.pk])),'Declared costing lineage and all reviewed client-document recipient receipts are verified.')
        factory_commercial.reassess(f['actor'],w.pk,w.revision,'Review actual source-owned client scope successor')
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.source_head_id,head.pk);self.assertGreater(w.budget_used,spent);self.assertEqual(w.budget_limit,20000)
        revised=factory_commercial.proposal(w);self.assertNotEqual(revised.pk,previous.pk);self.assertEqual(revised.previous_id,previous.pk)
        for role in commercial.ROLES:
            w.refresh_from_db();factory_commercial.decide(f['actor'],w.pk,w.revision,'commercial',role,'approve',0,'Synthetic revised exact proposal')
        factory.run_until_wait(w.pk);w.refresh_from_db();version=factory_commercial.document(w)
        factory_commercial.decide(f['actor'],w.pk,w.revision,'document',str(version.pk),'approve',0,'Synthetic revised exact client payload')
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=w).count(),2);self.assertEqual(FactoryWork.objects.filter(case=f['case']).count(),1)
        self.assertContains(self.client.get(reverse('home')+'?queue=verified'),'Commercial factory example')

    def test_missing_business_model_owner_retains_capture_and_never_approves_or_calculates(self):
        from copy import deepcopy
        from apps.pmo import costing
        f=setup();data=deepcopy(f['rule'].payload);data.update(owner_id=None,oracle_owner_id=None)
        source=add_evidence(f['actor'],f['case'].pk,'p14_rule',json.dumps(data),'synthetic:unassigned-calculator')
        rule=costing.capture_rule(f['actor'],f['case'].pk,f['rule'].reference,source.pk,predecessor=f['rule'].pk)
        values=dict(f['intake'],rule_id=rule.pk,oracle_id=None)
        head=commercial_intake.capture(f['actor'],f['case'].pk,values,f['head'].pk)
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'owner_needed',f['work'].finding);self.assertEqual(f['work'].source_head_id,head.pk)
        self.assertFalse(CostingRun.objects.filter(case=f['case']).exists());self.assertFalse(CommercialDecision.objects.filter(revision__dossier__case=f['case']).exists())
    def prepared_review(self,f):
        w=f['work'];factory.run_until_wait(w.pk)
        for role in commercial.ROLES:
            w.refresh_from_db();factory_commercial.decide(f['actor'],w.pk,w.revision,'commercial',role,'approve',0,'Synthetic current native commercial role')
        factory.run_until_wait(w.pk);w.refresh_from_db();version=factory_commercial.document(w)
        factory_commercial.decide(f['actor'],w.pk,w.revision,'document',str(version.pk),'approve',0,'Synthetic exact client payload')
        return version

    def test_agent_publication_is_bound_and_lost_response_reconciles_original_receipt(self):
        from adapters.publications import PublicationTimeoutAfterAccept
        f=setup();w=f['work'];version=self.prepared_review(f)
        factory.run_once(w.pk) # native reservation under the explicit publisher
        publication=Publication.objects.get(version=version)
        self.assertEqual(publication.factory_work_id,w.pk);self.assertEqual(publication.factory_policy_id,f['execution_profile'].pk);self.assertEqual(publication.factory_source_id,f['head'].pk)
        factory.run_once(w.pk,adapter=PublicationTimeoutAfterAccept())
        publication.job.refresh_from_db();self.assertEqual(publication.job.status,'unknown');self.assertEqual(PublicationReceipt.objects.filter(publication=publication).count(),1)
        factory.run_until_wait(w.pk);w.refresh_from_db();publication.job.refresh_from_db()
        self.assertEqual(w.status,'verified',w.finding);self.assertEqual(publication.job.status,'confirmed');self.assertEqual(PublicationReceipt.objects.filter(publication=publication).count(),1)

    def test_accepted_receipt_survives_cancellation_and_reconciles_without_new_send(self):
        from apps.documents.delivery import claim_publication,deliver_internal
        f=setup();w=f['work'];version=self.prepared_review(f);factory.run_once(w.pk);w.refresh_from_db()
        publication=Publication.objects.get(version=version);pk,fence=claim_publication(case_id=f['case'].pk,job_id=publication.job.pk)
        deliver_internal(pk,fence) # actual internal acceptance before the worker response
        factory.manage(f['actor'],w.pk,w.revision,'cancel')
        from apps.documents.delivery import finish_publication
        finish_publication(pk,fence,'unknown','Synthetic response lost after acceptance')
        w.refresh_from_db();factory_commercial.reconcile(f['actor'],w.pk,w.revision);w.refresh_from_db()
        self.assertEqual(w.status,'followup_needed');self.assertEqual(PublicationReceipt.objects.filter(publication=publication).count(),1)

    def test_cancellation_before_selected_publication_send_preserves_the_unpublished_document(self):
        from apps.documents.delivery import run_publication_once
        f=setup();w=f['work'];version=self.prepared_review(f);factory.run_once(w.pk);w.refresh_from_db()
        publication=Publication.objects.get(version=version)
        factory.manage(f['actor'],w.pk,w.revision,'cancel')
        run_publication_once(case_id=f['case'].pk,job_id=publication.job.pk);publication.job.refresh_from_db()
        self.assertEqual(publication.job.status,'held');self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
        self.assertTrue(CommercialDocumentBinding.objects.filter(version=version).exists())

    def test_changed_execution_profile_is_rechecked_by_the_native_publication_worker(self):
        from apps.documents.delivery import run_publication_once
        f=setup();w=f['work'];version=self.prepared_review(f);factory.run_once(w.pk)
        publication=Publication.objects.get(version=version)
        changed=dict(f['execution_value'],max_tokens=30000)
        p=draft_operator_policy(f['actor'],f['case'].pk,'OPS.factory_commercial_execution',changed,f['sources']['policy_decision'].pk,timezone.now())
        transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active')
        run_publication_once(case_id=f['case'].pk,job_id=publication.job.pk);publication.job.refresh_from_db()
        self.assertEqual(publication.job.status,'held');self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
    def test_native_calculation_proposal_human_decisions_controlled_review_and_receipts(self):
        self.assertEqual(connection.vendor,'postgresql');f=setup();w=f['work'];a=f['actor'];c=f['case']
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'waiting',w.finding)
        row=factory_commercial.calculation(w);self.assertIsNotNone(row,w.finding);self.assertEqual(row.result['status'],'known')
        revision=factory_commercial.proposal(w);self.assertIsNotNone(revision,w.finding)
        self.assertEqual(CommercialDecision.objects.filter(revision=revision).count(),0)
        for role in commercial.ROLES:
            w.refresh_from_db();factory_commercial.decide(a,w.pk,w.revision,'commercial',role,'approve',0,'Synthetic exact source decision')
        factory.run_until_wait(w.pk);w.refresh_from_db()
        version=factory_commercial.document(w);self.assertIsNotNone(version,w.finding)
        self.assertEqual(HumanTask.objects.filter(case=c,version=version,kind='document_review').count(),1)
        factory_commercial.decide(a,w.pk,w.revision,'document',str(version.pk),'approve',0,'Synthetic exact client version review')
        # This initial subincrement observes an independently authorised native human
        # publication. Controlled agent scope/reservation remains a separate code gap.
        reserve_publication(a,c.pk,version.pk,rev(c));self.assertTrue(run_publication_once())
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(PublicationReceipt.objects.filter(publication__version=version).count(),1)
        result=factory_commercial.verify(w);self.assertFalse(result['native_workbook_verified']);self.assertFalse(result['signed_baseline_adopted']);self.assertFalse(result['invoice_created'])

    def test_unknown_sources_hold_only_calculation_and_source_successor_retains_allowance(self):
        f=setup(missing=True);w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'waiting',w.finding);self.assertFalse(CostingRun.objects.filter(case=f['case']).exists());spent=w.budget_used
        fixed=dict(f['intake'],engineering_estimate=f['sources']['engineering_estimate'].pk)
        head=commercial_intake.capture(f['actor'],f['case'].pk,fixed,f['head'].pk)
        again=factory_commercial.start(f['actor'],f['case'].pk,'NEW-FORM',head.pk,'Corrected commercial sources',rev(f['case']))
        self.assertEqual(again.pk,w.pk);factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.source_head_id,head.pk);self.assertGreater(w.budget_used,spent);self.assertEqual(w.budget_limit,20000)
        self.assertIsNotNone(factory_commercial.proposal(w),w.finding)

    def test_intake_before_execution_policy_and_forged_source_false_verification_are_blocked(self):
        f=setup(configure=False);w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'configuration_needed');self.assertEqual(w.budget_used,0)
        forged=add_evidence(f['actor'],f['case'].pk,'agent_private_commercial_intake',f['head'].body,'synthetic:forged-commercial')
        with self.assertRaises(ValidationError):factory_commercial.start(f['actor'],f['case'].pk,'FORGED',forged.pk,'Forged',rev(f['case']))
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=w.pk).update(source_head=forged)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=w.pk).update(status='verified')

    def test_capture_is_idempotent_and_private_agent_results_stay_out_of_generic_workspace(self):
        f=setup();same=commercial_intake.capture(f['actor'],f['case'].pk,f['intake'],f['head'].pk)
        self.assertEqual(same.pk,f['head'].pk)
        factory.run_once(f['work'].pk)
        run=AgentRun.objects.get(case=f['case'],provider='synthetic_factory_v1')
        self.assertEqual(run.evidence_id,f['head'].pk)
        self.client.force_login(f['actor']);response=self.client.get(reverse('case',args=[f['case'].pk]))
        self.assertNotIn(run.pk,[r.pk for r in response.context['runs']])
        page=self.client.get(reverse('factory_detail',args=[f['work'].pk]));self.assertContains(page,'COSTING AND COMMERCIAL SUBMISSION')

    def test_primary_commercial_intake_and_configuration_use_plain_native_source_choices(self):
        f=setup();self.client.force_login(f['actor'])
        response=self.client.get(reverse('factory_create')+'?definition=commercial/v1&case='+str(f['case'].pk))
        self.assertContains(response,'Declared costing inputs');self.assertNotContains(response,'Case object (')
        response=self.client.get(reverse('factory_configuration',args=[f['case'].pk])+'?definition=commercial/v1')
        self.assertContains(response,'Controlled document publisher')


from django.test import TransactionTestCase

class FactoryCommercialConcurrencyTests(TransactionTestCase):
    def test_racing_forms_and_selected_publication_claim_share_native_identity(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.contrib.auth import get_user_model
        from apps.documents.delivery import claim_publication
        f=setup();barrier=Barrier(2)
        def intake(n):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=f['actor'].pk);barrier.wait(timeout=10)
                return factory_commercial.start(actor,f['case'].pk,'RACING-'+str(n),f['head'].pk,'Same commercial intent').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(intake,[1,2]))
        self.assertEqual(ids,[f['work'].pk]*2);self.assertEqual(FactoryWork.objects.filter(case=f['case']).count(),1)
        FactoryCommercialTests.prepared_review(self,f);factory.run_once(f['work'].pk)
        job=PublicationJob.objects.get(publication__factory_work=f['work']);barrier=Barrier(2)
        def claim(n):
            close_old_connections()
            try:
                barrier.wait(timeout=10);return claim_publication(case_id=f['case'].pk,job_id=job.pk)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(claim,[1,2]))
        self.assertEqual(sum(value is not None for value in claims),1)
        job.refresh_from_db();self.assertEqual(job.attempts,1);self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
