"""P39 native closure station: actual evidence/human decision, no parallel approval ledger."""
import json
from pathlib import Path
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,DatabaseError,transaction
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo.models import DeliveryRecord,DeliveryDocumentBinding
from apps.documents.controlled import register_template
from apps.workflows import factory,factory_closure as closure
from apps.workflows.models import FactoryWork,HumanTask
from tests.helpers import rev
from tests.test_delivery import DeliveryFixture


class FactoryClosureDistinctAuthorityTests(TestCase):
    def test_actual_head_principal_decides_without_worker_privileges_and_pm_cannot_impersonate_head(self):
        from django.contrib.auth import get_user_model
        from apps.policy.services import register_reference
        from tests.helpers import activate
        f=DeliveryFixture();f.setup_delivery()
        head=get_user_model().objects.create_user(username='synthetic-closure-head')
        Grant.objects.bulk_create([Grant(case=f.case,user=head,action=a) for a in
            ['case.read','factory.read','delivery.read','delivery.closure_decide']])
        ref=register_reference(f.actor,f.case.pk,'closure-head:actual','schema:psl/role-assignment/v1',
            {'role':'Head of PMO','user_id':head.pk},f.e['policy_decision'].pk)
        activate(f.actor,f.case,'D05.role_principal_assignments',['role:0',ref.ref,'role:2','role:3'],f.e['policy_decision'])
        from apps.pmo.signature_exemptions import assert_current_baseline_assurance
        from tests.signature_helpers import reaffirm_for
        with self.assertRaisesMessage(ValidationError,'Signature recorder authority changed'):
            assert_current_baseline_assurance(f.case)
        reaffirm_for(f.actor,f.case)  # Explicit same-document current-authority fixture evidence.
        f.closure_selected=f.closing();f=setup(base=f)
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();version=closure.document(f.work)
        self.assertIsNotNone(version);url=reverse('factory_detail',args=[f.work.pk])
        self.client.force_login(f.actor);self.assertNotContains(self.client.get(url),'Approve exact closure report')
        with self.assertRaises(PermissionDenied):approve(f)
        self.client.force_login(head);page=self.client.get(url)
        self.assertContains(page,'Approve exact closure report');self.assertNotContains(page,'Continue eligible work')
        self.assertNotContains(page,'Record reviewed source changes')
        response=self.client.post(url,{'action':'decide','revision':f.work.revision,'case_revision':rev(f.case),
            'version':version.pk,'verdict':'approve','evidence':f.e['requirements'].pk,'note':'Distinct synthetic Head reviews exact native report'})
        self.assertRedirects(response,url)
        decision=DeliveryRecord.objects.get(dossier=f.d,kind='closure_decision');self.assertEqual(decision.actor_id,head.pk)
        self.assertFalse(Grant.objects.filter(case=f.case,user=head,action__in=['factory.execute','factory.manage','policy.configure']).exists())
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        closed=DeliveryRecord.objects.get(dossier=f.d,kind='closure');self.assertEqual(closed.actor_id,f.actor.pk)
        self.assertEqual(closure.verify(f.work)['decision'],decision.pk)


def configure(f,owner=True,tokens=20000):
    value=json.loads(Path('fixtures/factory-closure.json').read_text());value.pop('classification')
    value.update(executor_id=f.actor.pk if owner else None,max_tokens=tokens)
    p=draft_operator_policy(f.actor,f.case.pk,'OPS.factory_closure_execution',value,f.e['policy_decision'].pk,timezone.now())
    transition(f.actor,p.pk,'validated');transition(f.actor,p.pk,'active');return p


def setup(known=True,profile=True,owner=True,review=False,base=None,capture=True):
    if base is None:
        f=DeliveryFixture();f.setup_delivery();selected=f.closing()
    else:f=base;selected=f.closure_selected
    closure_template=f.t
    if review:
        definition=dict(f.t.definition,internal_review_required=True)
        closure_template=register_template(f.actor,f.case.pk,'Reviewed closure report',definition,f.e['policy_decision'].pk,rev(f.case))
        from tests.document_helpers import artifact
        from apps.pmo import delivery_closure as native
        from apps.pmo.delivery_documents import draft_delivery_document
        artifact(f.actor,f.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v2',
            {'template_ids':[f.t.pk,closure_template.pk],'repository':'internal-versioned','retention_days':30,
             'closure_inventory':{'required_kinds':['technical_document','test_results','project_artifact'],'archive_mode':'immutable_local_manifest'}},f.e['policy_decision'])
        previous=DeliveryRecord.objects.filter(dossier=f.d,kind='archive').latest('pk')
        native.archive_artifacts(f.actor,f.case.pk,f.d.pk,previous.data['inventory'],previous.evidence_id,'Synthetic re-index under current reviewed template storage',rev(f.case))
        previous_binding=DeliveryDocumentBinding.objects.filter(dossier=f.d,purpose='handover').latest('pk')
        handover=draft_delivery_document(f.actor,f.case.pk,f.d.pk,'handover',f.t.pk,previous_binding.data,rev(f.case));receipt=f.publish(handover)
        native.acknowledge_handover(f.actor,f.case.pk,f.d.pk,receipt.pk,'received',f.e['requirements'].pk,'Actual synthetic receipt of current-storage handover',rev(f.case))
    f.inputs={'template_id':closure_template.pk,**selected} if known else {k:None for k in closure.FIELDS}
    f.known_inputs={'template_id':closure_template.pk,**selected}
    if profile:f.profile=configure(f,owner)
    if capture:f.work=closure.start(f.actor,f.case.pk,'CLOSURE-1',f.d.pk,f.inputs,'Project closure',rev(f.case))
    return f


def approve(f):
    f.work.refresh_from_db();v=closure.document(f.work)
    return closure.decide(f.actor,f.work.pk,f.work.revision,rev(f.case),v.pk,'approve',f.e['requirements'].pk,'Synthetic Head of PMO reviewed the exact report and current native prerequisites')


class FactoryClosureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery();f.closure_selected=f.closing();cls.base=f

    def assert_stopped_history(self,f):
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();version=closure.document(f.work)
        self.assertIsNotNone(version);spent=f.work.budget_used
        closure.cancel(f.actor,f.work.pk,f.work.revision);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'cancelled');self.client.force_login(f.actor)
        page=self.client.get(reverse('factory_detail',args=[f.work.pk]));row=page.context['row']
        self.assertEqual(row['state'],'Cancelled');self.assertEqual(row['owner'],'No action required')
        self.assertEqual(row['blocker'],'');self.assertEqual(row['next_action'],'Inspect the stopped work and its retained history')
        for key in ['can_advance','can_cancel','can_reconcile','can_reassess','needs_me','department_wait']:self.assertFalse(row[key],key)
        self.assertTrue(row['closure']['can_restart']);self.assertFalse(row['closure']['verdicts'])
        self.assertEqual(f.work.budget_used,spent);self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        with self.assertRaises(ValidationError):closure.decide(f.actor,f.work.pk,f.work.revision,rev(f.case),version.pk,'approve',f.e['requirements'].pk,'Stopped work cannot accept a Head decision')
        self.assertFalse(factory.run_once(f.work.pk));return version

    def test_stopped_native_head_decision_wait_does_not_own_or_reactivate_cancelled_work(self):
        f=setup(base=self.base);version=self.assert_stopped_history(f)
        self.assertTrue(DeliveryDocumentBinding.objects.filter(version=version).exists())
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure_decision').exists())

    def test_stopped_native_quality_review_remains_independent_without_false_active_owner(self):
        f=setup(base=self.base,review=True);version=self.assert_stopped_history(f)
        task=HumanTask.objects.get(version=version);self.assertEqual(task.status,'open')
        self.assertFalse(task.events.filter(action='withdraw').exists())
        self.assertTrue(task.events.filter(action='requested').exists())

    def test_agent_prepares_waits_for_actual_head_decision_then_finalises_and_verifies_native_closure(self):
        f=setup(base=self.base);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();v=closure.document(f.work)
        self.assertIsNotNone(v);self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind__in=['closure_decision','closure']).exists())
        self.assertFalse(HumanTask.objects.filter(case=f.case,kind='factory_review').exists())
        self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk]);page=self.client.get(url)
        self.assertContains(page,'Head of PMO closure decision');self.assertContains(page,'PM performance summary, risks and resolutions')
        self.assertNotContains(page,'Continue eligible work');self.assertEqual(page['Cache-Control'],'no-store')
        decision=approve(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);proof=closure.verify(f.work)
        self.assertTrue(proof['verified']);self.assertEqual(proof['decision'],decision.pk)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').count(),1)
        self.assertEqual(DeliveryDocumentBinding.objects.filter(dossier=f.d,purpose='closure').count(),1)
        for flag in ['debt_waived','deployment_authorized','external_authenticity_verified','separate_retrospective_approval','finance_attestation_inferred']:self.assertIs(proof[flag],False)
        self.assertEqual(connection.vendor,'postgresql');self.assertGreater(f.work.budget_used,0)
        page=self.client.get(url);self.assertContains(page,'Closure recorded');self.assertNotContains(page,'Current project scope</strong> · Needs attention')
        from apps.pmo.delivery_closure import closure_requirements
        result=closure_requirements(f.d,{k:f.inputs[k] for k in ['retrospective_id','report_evidence_id']})
        self.assertEqual(result['checks'][0]['status'],'closed');self.assertFalse(result['ready_to_prepare'])
        self.assertEqual(result['recorded_closure_id'],proof['closure'])

    def test_unknown_intake_and_missing_profile_capture_correct_and_continue_with_same_allowance(self):
        f=setup(known=False,profile=False,base=self.base);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'configuration_needed');self.assertEqual(f.work.budget_used,0)
        closure.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.known_inputs,'Declare the actual synthetic source records')
        configure(f,owner=False);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertIsNotNone(closure.document(f.work))
        approve(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'owner_needed',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists());spent=f.work.budget_used
        p=configure(f,tokens=40000);factory.adopt_profile(f.actor,f.work.pk,f.work.revision,p.pk,'Explicit current finaliser configuration adoption')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(f.work.budget_limit,20000);self.assertGreater(f.work.budget_used,spent)

    def test_configured_document_review_is_native_and_head_decision_does_not_get_inferred(self):
        f=setup(review=True,base=self.base);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();v=closure.document(f.work)
        self.assertIsNotNone(v);self.assertEqual(HumanTask.objects.filter(version=v,status='open').count(),1)
        with self.assertRaises(ValidationError):approve(f)
        closure.review(f.actor,f.work.pk,f.work.revision,rev(f.case),v.pk,'approve','Synthetic configured exact document review')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        approve(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertFalse(HumanTask.objects.filter(case=f.case,kind='factory_review').exists())

    def test_corrected_report_requires_new_head_decision_and_preserves_native_history_and_budget(self):
        f=setup(base=self.base);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();first=closure.document(f.work);old=approve(f)
        report=f.evidence('closure_report','Corrected synthetic PM closure report')
        closure.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),dict(f.inputs,report_evidence_id=report.pk),'Correct the PM report before finalisation')
        spent=f.work.budget_used;factory.run_until_wait(f.work.pk);f.work.refresh_from_db();second=closure.document(f.work)
        self.assertNotEqual(first.pk,second.pk);self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists());self.assertTrue(DeliveryRecord.objects.filter(pk=old.pk).exists())
        approve(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertGreater(f.work.budget_used,spent);self.assertEqual(f.work.budget_limit,20000)

    def test_foreign_private_boolean_and_raw_false_verified_requests_are_rejected(self):
        f=setup(base=self.base)
        for key in closure.FIELDS:
            with self.assertRaises(ValidationError):closure.input_rows(f.case,dict(f.inputs,**{key:True}))
        private=f.evidence('agent_private_closure','PRIVATE RAW INPUT')
        with self.assertRaises(ValidationError):closure.input_rows(f.case,dict(f.inputs,report_evidence_id=private.pk))
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f.work.pk).update(status='verified')
        f.work.refresh_from_db();self.assertNotEqual(f.work.status,'verified')
        with self.assertRaises(ValidationError):closure.start(f.actor,f.case.pk,'CLOSURE-1',f.d.pk,f.inputs,'Changed intent',rev(f.case))

    def test_invalid_execution_configuration_cannot_appoint_or_expand_a_closure_operator(self):
        from django.contrib.auth import get_user_model
        from tests.helpers import envelope
        from apps.policy.services import save_draft
        f=setup(profile=False,base=self.base)
        other=get_user_model().objects.create_user(username='unappointed-closure-operator')
        original=json.loads(Path('fixtures/factory-closure.json').read_text());original.pop('classification')
        for changes in [{'executor_id':other.pk},{'review_role':'Head of PMO'},
                        {'information_resolver_id':f.actor.pk},{'definition':'delivery-handover/v1'},
                        {'provider':'operational_provider'},{'tokens_per_call':20001},
                        {'required_evidence_kinds':['p14_inputs']},{'automatic_head_approval':True}]:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                draft=save_draft(f.actor,f.case.pk,envelope(f.case,'OPS.factory_closure_execution',dict(original,**changes),f.e['policy_decision']))
                transition(f.actor,draft.pk,'validated')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())

    def test_provider_cannot_self_approve_select_finalisation_early_or_invent_citations(self):
        f=setup(base=self.base)
        class BadChoice:
            def choose(self,context):return {'activity':'ACT11','citations':context['evidence_ids']}
        self.assertFalse(factory.run_once(f.work.pk,provider=BadChoice()));f.work.refresh_from_db()
        self.assertEqual(f.work.status,'blocked');self.assertIn('outside current capabilities',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind__in=['closure_decision','closure']).exists())
        spent=f.work.budget_used;factory.manage(f.actor,f.work.pk,f.work.revision,'resume')
        class BadCitation:
            def choose(self,context):return {'activity':context['eligible'][0],'citations':[True]}
        self.assertFalse(factory.run_once(f.work.pk,provider=BadCitation()));f.work.refresh_from_db()
        self.assertEqual(f.work.status,'blocked');self.assertIn('Unsupported citation',f.work.finding)
        self.assertGreater(f.work.budget_used,spent);self.assertEqual(f.work.budget_limit,20000)
        self.assertIsNone(closure.document(f.work))

    def test_http_typed_denied_csrf_and_invalid_dossier_requests_have_no_effect(self):
        from django.test import Client
        from django.contrib.auth import get_user_model
        f=setup(base=self.base);url=reverse('factory_detail',args=[f.work.pk]);self.client.force_login(f.actor)
        page=self.client.get(reverse('factory_create'),{'definition':closure.DEFINITION,'case':f.case.pk,'dossier':'malformed'})
        self.assertContains(page,'Choose an available project delivery record.')
        response=self.client.post(url,{'action':'decide','revision':'not-an-integer'})
        self.assertContains(response,'Refresh the work and choose the current recorded references.')
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(f.actor)
        self.assertEqual(csrf.post(url,{'action':'advance','revision':f.work.revision}).status_code,403)
        stranger=get_user_model().objects.create_user(username='foreign-closure-viewer');self.client.force_login(stranger)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.post(url,{'action':'advance','revision':f.work.revision}).status_code,404)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind__in=['closure_decision','closure']).exists())
        self.assertIsNone(closure.document(f.work));f.work.refresh_from_db();self.assertEqual(f.work.budget_used,0)

    def test_native_quality_and_head_return_reject_rework_need_fresh_exact_reports(self):
        f=setup(review=True,base=self.base)
        from tests.document_helpers import artifact
        artifact(f.actor,f.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',
            {'rules':[{'role':'PMO Lead','actions':['return','reject']},{'role':'Head of PMO','actions':['return','reject']}]},f.e['policy_decision'])
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();first=closure.document(f.work)
        self.client.force_login(f.actor);page=self.client.get(reverse('factory_detail',args=[f.work.pk]));self.assertContains(page,'Return exact document')
        closure.review(f.actor,f.work.pk,f.work.revision,rev(f.case),first.pk,'return','Actual synthetic quality review asks for corrected report evidence')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        report=f.evidence('closure_report','Synthetic report corrected after native quality return')
        inputs=dict(f.inputs,report_evidence_id=report.pk)
        closure.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),inputs,'Reviewed source correction after quality return')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();second=closure.document(f.work)
        self.assertNotEqual(first.pk,second.pk)
        closure.review(f.actor,f.work.pk,f.work.revision,rev(f.case),second.pk,'approve','Exact corrected quality document reviewed')
        closure.decide(f.actor,f.work.pk,f.work.revision,rev(f.case),second.pk,'return',f.e['requirements'].pk,'Actual Head of PMO return under configured action authority')
        closure.decide(f.actor,f.work.pk,f.work.revision,rev(f.case),second.pk,'reject',f.e['requirements'].pk,'Actual Head of PMO rejection retained independently')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        report=f.evidence('closure_report','Synthetic final report after Head return and rejection')
        closure.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),dict(inputs,report_evidence_id=report.pk),'Current source after actual Head rejection')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();third=closure.document(f.work)
        closure.review(f.actor,f.work.pk,f.work.revision,rev(f.case),third.pk,'approve','Exact final controlled document reviewed')
        approve(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').count(),1);self.assertEqual(f.work.budget_limit,20000)
        self.assertTrue(HumanTask.objects.filter(version=first,status='returned').exists())

    def test_revoked_finaliser_during_plan_cannot_record_closure_and_fresh_authority_recovers(self):
        f=setup(base=self.base);factory.run_until_wait(f.work.pk);approve(f)
        class Revoke:
            def choose(self,context):
                if 'ACT11' in context['eligible']:Grant.objects.filter(user=f.actor,case=f.case,action='delivery.manage').update(active=False)
                return {'activity':context['eligible'][0],'citations':context['evidence_ids'][:1]}
        factory.run_until_wait(f.work.pk,provider=Revoke());f.work.refresh_from_db()
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        spent=f.work.budget_used;Grant.objects.filter(user=f.actor,case=f.case,action='delivery.manage').update(active=True)
        factory.manage(f.actor,f.work.pk,f.work.revision,'resume');factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertGreater(f.work.budget_used,spent);self.assertEqual(f.work.budget_limit,20000)

    def test_superseded_controlled_version_holds_and_same_input_reassessment_needs_fresh_head_decision(self):
        from apps.documents.controlled import create_version
        f=setup(base=self.base);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();v=closure.document(f.work);old=approve(f)
        create_version(f.actor,f.case.pk,v.template_id,v.document.title,v.audience,v.fields,rev(f.case),document_id=v.document_id)
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        closure.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inputs,'Reassess actual controlled version supersession')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertNotEqual(closure.document(f.work).pk,v.pk)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists());self.assertTrue(DeliveryRecord.objects.filter(pk=old.pk).exists())
        approve(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)

    def test_stop_restart_keeps_original_allowance_and_requires_new_exact_head_decision(self):
        f=setup(base=self.base);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();old=approve(f);spent=f.work.budget_used
        closure.cancel(f.actor,f.work.pk,f.work.revision);f.work.refresh_from_db();self.assertEqual(f.work.status,'cancelled')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        closure.restart(f.actor,f.work.pk,f.work.revision,rev(f.case),'New explicit human closure instruction after stop')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists());self.assertTrue(DeliveryRecord.objects.filter(pk=old.pk).exists())
        approve(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(f.work.budget_limit,20000);self.assertGreater(f.work.budget_used,spent)
