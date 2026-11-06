import copy,json
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,connection,DatabaseError
from django.utils import timezone
from apps.documents import validation as domain
from apps.documents.validation_models import DiscoverySource,ValidationExample,ValidationPackage,ValidationReview,ValidationReplay,ValidationFollowup
from apps.policy.validation_validators import OWNER,ACCEPTANCE,SOP
from apps.policy.services import active_component,transition,resolve
from apps.policy.validation_drafts import draft_validation_policy
from apps.identity.models import Grant
from apps.agents.validation import investigate
from adapters.validation_evidence import FrozenPackEvidenceAdapter,LocalAcceptanceReportAdapter
from .validation_helpers import fixture,values,policy,evidence,review,replays,ready
from .helpers import rev,setup_case

class EvidenceValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()
    def setUp(self):self.a=self.f['actor'];self.c=self.f['case'];self.p=self.f['package'];self.e=self.f['decision_evidence']
    def revised(self,**updates):
        p=copy.deepcopy(self.p.payload);p.update(updates)
        self.p=domain.prepare_package(self.a,self.c.pk,'review-scope',p,self.e.pk,rev(self.c));self.f['package']=self.p;return self.p

    def test_capture_and_owned_gap_followup_continue_without_owner_configuration(self):
        transition(self.a,active_component(OWNER,self.c).pk,'revoked')
        gap={'key':'support-sop','description':'Obtain the actual Support SOP; meeting narrative is not the procedure','process_ids':['B13'],'state':'open','evidence_id':None}
        self.revised(gaps=[gap]);due=timezone.now()+timedelta(days=1)
        row=domain.followup(self.a,self.c.pk,self.p.pk,gap['key'],self.a.pk,due,self.e.pk,'Request actual controlled evidence',rev(self.c))
        self.assertEqual(row.action.current.owner_id,self.a.pk);self.assertEqual(row.action.current.due_at,due)
        with self.assertRaises(ValidationError):review(self.f)
        self.assertEqual(ValidationReview.objects.count(),0)

    def test_connected_meaning_expectations_comparison_acceptance_and_scoped_report(self):
        reports=ready(self.f);acceptance=review(self.f,'acceptance')
        self.assertEqual(domain.approved_review(self.p,'acceptance').pk,acceptance.pk)
        self.assertTrue(all(r.result['matches'] for r in reports));self.assertTrue(all(not r.result['underlying_workflow_executed'] for r in reports))
        value=LocalAcceptanceReportAdapter().read(self.f['acceptor'],self.c.pk,acceptance.pk)
        self.assertFalse(value['whole_product_accepted']);self.assertFalse(value['deployment_authorized']);self.assertEqual(value['status']['scope'],['B13','P13','P15'])

    def test_receipt_stated_document_owner_and_admin_flag_grant_no_review_authority(self):
        self.a.is_superuser=True;self.a.save()
        with self.assertRaises(PermissionDenied):domain.review(self.a,self.c.pk,self.p.pk,'meaning','approve','admin',self.e.pk,'Source says Head of PMO; not an appointment',rev(self.c))
        self.assertEqual(ValidationReview.objects.count(),0)

    def test_normal_and_exception_examples_are_required_for_each_process(self):
        self.revised(example_ids=[self.f['examples'][0].pk]);review(self.f)
        with self.assertRaisesMessage(ValidationError,'exception'):review(self.f,'expectations')
        self.assertEqual(ValidationReplay.objects.count(),0)

    def test_actual_report_cannot_define_or_replace_expected_output(self):
        with self.assertRaises(ValidationError):replays(self.f)
        review(self.f);review(self.f,'expectations');replays(self.f,wrong=True)
        with self.assertRaisesMessage(ValidationError,'matching evaluation'):review(self.f,'acceptance')
        self.assertEqual(self.f['examples'][0].expected,{'permitted':True})

    def test_source_revision_stales_reviews_and_preserves_original_clauses(self):
        ready(self.f);accepted=review(self.f,'acceptance')
        old=self.f['source'];metadata=copy.deepcopy(old.metadata);metadata['source_version']='1.2'
        newer=domain.capture_source(self.a,self.c.pk,old.reference,old.evidence_id,metadata,rev(self.c))
        self.assertEqual(newer.version,2)
        with self.assertRaises(ValidationError):domain.approved_review(self.p,'acceptance')
        self.assertEqual(ValidationReview.objects.get(pk=accepted.pk).verdict,'approve');self.assertEqual(DiscoverySource.objects.get(pk=old.pk).metadata['source_version'],'1.1')

    def test_changed_example_or_selected_policy_requires_new_package_and_reviews(self):
        ready(self.f);ex=self.f['examples'][0]
        domain.capture_example(self.a,self.c.pk,ex.reference,ex.process_ids,ex.scenario,{'permitted':'changed'},ex.evidence_id,rev(self.c))
        with self.assertRaises(ValidationError):domain.package_current(self.p)

    def test_changed_expectation_review_invalidates_old_result_comparisons(self):
        ready(self.f);review(self.f,'expectations',key='expectation-reconfirmation')
        with self.assertRaises(ValidationError):review(self.f,'acceptance')
        replays(self.f);review(self.f,'acceptance')

    def test_unresolved_gap_and_missing_selected_rule_hold_acceptance_only(self):
        self.revised(policy_components=['D13.payment_denominator_rule_ref']);ready(self.f)
        with self.assertRaisesMessage(ValidationError,'selected domain policy'):review(self.f,'acceptance')
        self.assertEqual(domain.approved_review(self.p,'meaning').verdict,'approve')

    def test_revocation_and_current_case_action_grants_are_rechecked(self):
        ready(self.f);accepted=review(self.f,'acceptance')
        Grant.objects.filter(case=self.c,user=self.f['owner'],action='validation.review').update(active=False)
        with self.assertRaises(PermissionDenied):domain.approved_review(self.p,'acceptance')
        Grant.objects.filter(case=self.c,user=self.f['owner'],action='validation.review').update(active=True)
        review(self.f,'meaning','revoke')
        with self.assertRaises(ValidationError):domain.approved_review(self.p,'acceptance')
        self.assertEqual(ValidationReview.objects.get(pk=accepted.pk).verdict,'approve')

    def test_definition_acceptance_does_not_claim_implementation_or_native_acceptance(self):
        self.revised(level='definition');review(self.f);review(self.f,'expectations');r=review(self.f,'acceptance')
        self.assertEqual(r.snapshot['replays'],[])
        self.revised(level='operational');ready(self.f)
        with self.assertRaisesMessage(ValidationError,'native execution'):review(self.f,'acceptance')

    def test_reported_external_results_never_establish_native_execution_proof(self):
        review(self.f);review(self.f,'expectations')
        for ex in self.f['examples']:
            data=dict(self.f['config']['replay'],example_id=ex.pk,actual=ex.expected,evidence_class='reported_external')
            e=evidence(self.a,self.c,'validation_result',json.dumps(data));r=domain.record_replay(self.f['tester'],self.c.pk,self.p.pk,e.pk,'external-'+str(ex.pk),rev(self.c));self.assertEqual(r.result['execution_evidence'],'supplied_report_only')
        with self.assertRaises(ValidationError):review(self.f,'acceptance')

    def test_policy_schemas_reject_ambiguous_owner_and_fake_process(self):
        bad=copy.deepcopy(self.f['config']['authority']);bad['assignments'].append(bad['assignments'][0])
        r=draft_validation_policy(self.a,self.c.pk,OWNER,bad,self.e.pk,timezone.now())
        with self.assertRaises(ValidationError):transition(self.a,r.pk,'validated')
        bad=copy.deepcopy(self.f['config']['authority']);bad['assignments'][0]['process_ids']=['P99']
        r=draft_validation_policy(self.a,self.c.pk,OWNER,bad,self.e.pk,timezone.now())
        with self.assertRaises(ValidationError):transition(self.a,r.pk,'validated')
        r=draft_validation_policy(self.a,self.c.pk,ACCEPTANCE,{'allowed_levels':['operational'],'independent_tester':True,'independent_acceptor':True},self.e.pk,timezone.now())
        with self.assertRaises(ValidationError):transition(self.a,r.pk,'validated')

    def test_support_sop_reference_requires_current_exact_meaning_review(self):
        meaning=review(self.f)
        value={'source_id':self.f['source'].pk,'source_sha256':self.f['source'].sha256,'meaning_review_id':meaning.pk,'process_ids':['B13']}
        policy(self.a,self.c,SOP,value,self.e);self.assertEqual(resolve(SOP,self.c).status,'ACTIVE')
        review(self.f,'meaning','disputed');self.assertEqual(resolve(SOP,self.c).status,'INVALID')

    def test_exact_quote_scope_and_allowlisted_pack_source_boundaries(self):
        metadata=copy.deepcopy(self.f['source'].metadata);metadata['clauses'][0]['quote']='Invented quoted authority'
        with self.assertRaises(ValidationError):domain.capture_source(self.a,self.c.pk,'false-quote',self.f['source'].evidence_id,metadata,rev(self.c))
        with self.assertRaises(ValidationError):FrozenPackEvidenceAdapter().read('../../.runtime/demo-access.txt')
        body,sha=FrozenPackEvidenceAdapter().read('reference/12-payment-exception-policy/AMENDMENT.md');self.assertIn('human',body);self.assertEqual(len(sha),64)

    def test_cross_case_evidence_and_actor_scopes_are_rejected(self):
        a,c=setup_case(username='other-validation');e=evidence(a,c,'procedure_source','A payment exception does not waive debt.')
        with self.assertRaises(ValidationError):domain.capture_source(self.a,self.c.pk,'cross-scope',e.pk,self.f['source'].metadata,rev(self.c))
        with self.assertRaises(PermissionDenied):LocalAcceptanceReportAdapter().read(a,self.c.pk,9999)

    def test_idempotent_review_and_replay_receipts_reject_changed_intent(self):
        first=review(self.f);self.assertEqual(review(self.f).pk,first.pk)
        with self.assertRaises(ValidationError):review(self.f,verdict='return',key='meaning-approve')
        review(self.f,'expectations');r=replays(self.f)[0]
        again=domain.record_replay(self.f['tester'],self.c.pk,self.p.pk,r.evidence_id,r.operation_key,rev(self.c));self.assertEqual(again.pk,r.pk)

    def test_postgresql_guards_protect_all_validation_history(self):
        ready(self.f);accept=review(self.f,'acceptance')
        rows=[self.f['source'],self.f['examples'][0],self.p,accept,ValidationReplay.objects.first()]
        for row in rows:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cur:cur.execute(f'UPDATE {row._meta.db_table} SET actor_id=actor_id WHERE id=%s',[row.pk])

    def test_bounded_agent_cites_conflicts_and_never_creates_owner_approval(self):
        old=self.f['source'];meta=copy.deepcopy(old.metadata);meta['clauses'][0]['quote']='Source receipt is not implementation acceptance.'
        domain.capture_source(self.a,self.c.pk,'contradiction',old.evidence_id,meta,rev(self.c))
        run=investigate(self.a,self.c.pk,rev(self.c));self.assertTrue(run.result['conflicts']);self.assertIn(old.evidence_id,run.result['citations']);self.assertFalse(run.result['owner_validation_granted']);self.assertEqual(ValidationReview.objects.count(),0)

    def test_staff_ui_and_json_report_use_record_permissions(self):
        ready(self.f);r=review(self.f,'acceptance');self.client.force_login(self.f['acceptor'])
        url=f'/cases/{self.c.pk}/validation/';response=self.client.get(url);self.assertContains(response,'Evidence and owner validation');self.assertContains(response,'supplied reports')
        response=self.client.get(f'{url}report/{r.pk}/');self.assertEqual(response.status_code,200);self.assertFalse(response.json()['whole_product_accepted'])
        Grant.objects.filter(case=self.c,user=self.f['acceptor'],action='validation.export').update(active=False)
        self.assertEqual(self.client.get(f'{url}report/{r.pk}/').status_code,403)

    def test_sop_lost_owner_grant_returns_policy_hold_without_blocking_capture_ui(self):
        meaning=review(self.f);s=self.f['source'];policy(self.a,self.c,SOP,{'source_id':s.pk,'source_sha256':s.sha256,'meaning_review_id':meaning.pk,'process_ids':['B13']},self.e)
        Grant.objects.filter(case=self.c,user=self.f['owner'],action='validation.review').update(active=False)
        self.assertEqual(resolve(SOP,self.c).status,'INVALID')
        self.client.force_login(self.a);self.assertEqual(self.client.get(f'/cases/{self.c.pk}/validation/').status_code,200)

    def test_independent_expected_output_author_cannot_approve_own_examples(self):
        ex=self.f['examples'][0]
        # Granting capture does not grant an exemption from configured independent review.
        Grant.objects.create(case=self.c,user=self.f['owner'],action='validation.example.capture')
        new=domain.capture_example(self.f['owner'],self.c.pk,ex.reference,ex.process_ids,ex.scenario,ex.expected,ex.evidence_id,rev(self.c))
        self.revised(example_ids=[new.pk,self.f['examples'][1].pk]);review(self.f)
        with self.assertRaises(PermissionDenied):review(self.f,'expectations')

    def test_revised_package_historical_report_is_not_current_acceptance(self):
        ready(self.f);old=review(self.f,'acceptance');self.revised(level='definition');review(self.f);review(self.f,'expectations');review(self.f,'acceptance')
        report=LocalAcceptanceReportAdapter().read(self.f['acceptor'],self.c.pk,old.pk)
        self.assertFalse(report['requested_record_is_current']);self.assertEqual(report['verdict'],'approve')

    def test_ui_posts_source_and_rejects_extra_approval_claims_and_stale_commands(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/validation/'
        data={'action':'source','revision':rev(self.c),'reference':'UI-source','evidence':self.f['source'].evidence_id,'metadata':json.dumps(self.f['source'].metadata)}
        response=self.client.post(url,data);self.assertEqual(response.status_code,302);self.assertEqual(DiscoverySource.objects.count(),2)
        response=self.client.post(url,data);self.assertEqual(response.status_code,200);self.assertEqual(DiscoverySource.objects.count(),2)
        data.update(revision=rev(self.c),approved='true');response=self.client.post(url,data);self.assertContains(response,'Unexpected fields');self.assertEqual(DiscoverySource.objects.count(),2)

    def test_gap_followup_is_unique_and_postgresql_guarded(self):
        gap={'key':'clarification','description':'Confirm actual policy with the appointed owner','process_ids':['P13'],'state':'open','evidence_id':None};self.revised(gaps=[gap])
        f=domain.followup(self.a,self.c.pk,self.p.pk,'clarification',self.a.pk,timezone.now()+timedelta(days=1),self.e.pk,'Owner evidence is outstanding',rev(self.c))
        self.assertEqual(domain.followup(self.a,self.c.pk,self.p.pk,'clarification',self.a.pk,timezone.now()+timedelta(days=2),self.e.pk,'Request same gap',rev(self.c)).pk,f.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cur:cur.execute('DELETE FROM documents_validationfollowup WHERE id=%s',[f.pk])

    def test_unknown_source_version_date_and_owner_remain_unknown(self):
        metadata=dict(self.f['source'].metadata,source_version=None,source_date=None,owner_label=None)
        r=domain.capture_source(self.a,self.c.pk,'undated-source',self.f['source'].evidence_id,metadata,rev(self.c))
        self.assertIsNone(r.metadata['source_date']);self.assertIsNone(r.metadata['owner_label']);self.assertIsNone(r.metadata['source_version'])

    def test_non_support_document_cannot_satisfy_support_sop_reference(self):
        meaning=review(self.f);old=self.f['source'];meta=dict(old.metadata,document_kind='pmo_sop')
        source=domain.capture_source(self.a,self.c.pk,'PMO-not-support',old.evidence_id,meta,rev(self.c))
        r=draft_validation_policy(self.a,self.c.pk,SOP,{'source_id':source.pk,'source_sha256':source.sha256,'meaning_review_id':meaning.pk,'process_ids':['B13']},self.e.pk,timezone.now())
        with self.assertRaisesMessage(ValidationError,'Support SOP'):transition(self.a,r.pk,'validated')

    def test_missing_acceptance_policy_holds_only_acceptance(self):
        transition(self.a,active_component(ACCEPTANCE,self.c).pk,'revoked');ready(self.f)
        self.assertEqual(domain.approved_review(self.p,'expectations').verdict,'approve')
        with self.assertRaises(ValidationError):review(self.f,'acceptance')

    def test_acceptance_criteria_supersession_requires_new_acceptance_only(self):
        ready(self.f);old=review(self.f,'acceptance')
        policy(self.a,self.c,ACCEPTANCE,self.f['config']['acceptance'],self.e)
        self.assertEqual(domain.approved_review(self.p,'expectations').verdict,'approve')
        self.assertFalse(LocalAcceptanceReportAdapter().read(self.f['acceptor'],self.c.pk,old.pk)['requested_record_is_current'])
        review(self.f,'acceptance',key='current-criteria-acceptance')

    def test_human_only_and_source_date_validation(self):
        bad=dict(self.f['config']['authority'],human_only=False)
        r=draft_validation_policy(self.a,self.c.pk,OWNER,bad,self.e.pk,timezone.now())
        with self.assertRaises(ValidationError):transition(self.a,r.pk,'validated')
        bad=dict(self.f['source'].metadata,source_date='2026-99-99')
        with self.assertRaises(ValidationError):domain.capture_source(self.a,self.c.pk,'bad-date',self.f['source'].evidence_id,bad,rev(self.c))

class ValidationSupportScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.policy.services import register_reference
        from .helpers import activate
        f=fixture(kind='support');a,c,e=f['actor'],f['case'],f['decision_evidence'];refs=[]
        for person,role in [(f['owner'],'Support'),(f['acceptor'],'Process User')]:
            r=register_reference(a,c.pk,'support-validation-role:'+str(person.pk),'schema:psl/role-assignment/v1',{'user_id':person.pk,'role':role},e.pk);refs.append(r.ref)
        activate(a,c,'D05.role_principal_assignments',refs,e)
        authority=copy.deepcopy(f['config']['authority']);authority['assignments'][0]['role']='Support';authority['assignments'][1]['role']='Process User'
        policy(a,c,OWNER,authority,e);cls.f=f

    def test_support_case_uses_service_scope_and_explicit_support_process_user_roles(self):
        f=self.f;ready(f);r=review(f,'acceptance');self.assertEqual(f['case'].kind,'support')
        report=LocalAcceptanceReportAdapter().read(f['acceptor'],f['case'].pk,r.pk)
        self.assertTrue(report['requested_record_is_current']);self.assertFalse(report['whole_product_accepted'])
        self.assertEqual(active_component(OWNER,f['case']).envelope['subject_scope']['kind'],'service')

    def test_typed_policy_ui_drafts_valid_service_scope_without_automatic_activation(self):
        from apps.policy.models import Configuration
        f=self.f;self.client.force_login(f['actor']);old=active_component(ACCEPTANCE,f['case'])
        response=self.client.post(f'/cases/{f["case"].pk}/validation/',{'action':'policy','revision':rev(f['case']),'component':ACCEPTANCE,'content':json.dumps(f['config']['acceptance']),'evidence':f['decision_evidence'].pk,'effective_from':timezone.now().isoformat()})
        self.assertEqual(response.status_code,302);new=Configuration.objects.filter(case=f['case'],component=ACCEPTANCE).order_by('-revision').first()
        self.assertNotEqual(new.pk,old.pk);self.assertEqual(active_component(ACCEPTANCE,f['case']).pk,old.pk)
        self.assertEqual(new.envelope['subject_scope'],{'kind':'service','ref':str(f['case'].pk)})
        transition(f['actor'],new.pk,'validated');transition(f['actor'],new.pk,'active');self.assertEqual(active_component(ACCEPTANCE,f['case']).pk,new.pk)
