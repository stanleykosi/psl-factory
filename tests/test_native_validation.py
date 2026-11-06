"""Real PMO -> Finance worker receipts, synthetic human/configuration fixtures only."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,close_old_connections
from django.test import TestCase,TransactionTestCase,Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.policy.services import resolve,reference_values,transition,register_reference
from apps.policy.validation_validators import ACCEPTANCE,NATIVE_SCHEMA
from apps.documents import validation as af13,native_validation as native
from apps.documents.validation_models import ValidationReplay,ValidationReview,ValidationExample
from apps.pmo.services import complete_milestone
from apps.workflows.models import Outbox
from apps.workflows.services import run_once
from apps.finance.models import Handoff
from adapters import validation_native as adapter
from tests import validation_helpers as h
from tests.helpers import signed,prepared,rev,activate,setup_case


def fixture(synthetic=True,level=None,family='handoff'):
    f=h.fixture(synthetic=synthetic);a,c=f['actor'],f['case']
    owner_refs=resolve('D05.role_principal_assignments',c).configuration.envelope['value']
    if synthetic:
        f['pmo']=signed(a,c)
        role_refs=resolve('D05.role_principal_assignments',c).configuration.envelope['value']
        activate(a,c,'D05.role_principal_assignments',owner_refs+role_refs,f['decision_evidence'])
    else:
        from apps.pmo.services import decide,sign_baseline
        f['pmo']=prepared(a,c);refs=list(owner_refs);people={}
        for role in ['PM','Head of PMO','CEO','PMO Lead']:
            person=f['acceptor'] if role=='Head of PMO' else get_user_model().objects.create_user(username='native-'+role.replace(' ','-'))
            for action in ['case.read','decision.record']:Grant.objects.get_or_create(user=person,case=c,action=action)
            if role!='Head of PMO':refs.append(register_reference(a,c.pk,'native-role:'+str(person.pk),'schema:psl/role-assignment/v1',{'role':role,'user_id':person.pk},f['decision_evidence'].pk).ref)
            people[role]=person
        activate(a,c,'D05.role_principal_assignments',refs,f['decision_evidence'])
        for role,person in people.items():decide(person,c.pk,role,rev(c))
        sign_baseline(a,c.pk,f['pmo']['signature'].pk,rev(c))
    v=json.loads((Path(__file__).resolve().parent.parent/'fixtures/native-validation.json').read_text())
    v['criteria']['native_execution']['families']=[family]
    for kind in ['normal','exception']:v[kind].update(family=family,operation=family)
    if family=='publication':
        from tests.document_helpers import artifact,DEFINITION,approved
        from apps.documents import controlled
        template=controlled.register_template(a,c.pk,'Native receipt report',DEFINITION,f['decision_evidence'].pk,rev(c))
        recipient=get_user_model().objects.create_user(username='native-publication-recipient')
        Grant.objects.create(user=recipient,case=c,action='document.receive:client')
        r=register_reference(a,c.pk,'native-pub-client','schema:psl/document-recipient/v1',{'audience':'client','user_id':recipient.pk},f['decision_evidence'].pk)
        activate(a,c,'D11.recipient_grant_refs',[r.ref],f['decision_evidence'])
        artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},f['decision_evidence'])
        source=h.evidence(a,c,'completion','Delivery is progressing. Internal incident trace is private.')
        f['publications']=[approved(a,c,template,source),approved(a,c,template,source)]
    from adapters.native_subjects import planned
    for index,kind in enumerate(['normal','exception']):
        if family=='handoff':identity=planned(a,c,family,f['pmo']['completion'].pk,'native-'+kind)
        elif family=='publication':identity=planned(a,c,family,f['publications'][index].pk)
        else:raise AssertionError('Explicit native source fixture required')
        v[kind]['subject_sha256']=identity['subject_sha256']
    f['native_config']=h.policy(a,c,ACCEPTANCE,v['criteria'],f['decision_evidence'])
    examples=[af13.capture_example(a,c.pk,'native-'+kind,f['package'].payload['process_ids'],kind,v[kind],f['decision_evidence'].pk,rev(c)) for kind in ['normal','exception']]
    payload=dict(f['package'].payload,example_ids=[x.pk for x in examples],level=level or ('synthetic_implementation' if synthetic else 'operational'))
    f['package']=af13.prepare_package(a,c.pk,'native-scope',payload,f['decision_evidence'].pk,rev(c));f['examples']=examples
    from apps.workflows.operator_inventory import ROUTES
    for person in [f['owner'],f['tester'],f['acceptor']]:
        for action in {'workflow.read',ROUTES[family][2]}:Grant.objects.get_or_create(user=person,case=c,action=action)
    h.review(f);h.review(f,'expectations')
    return f


def job(f,name):
    m=complete_milestone(f['actor'],f['case'].pk,name,f['pmo']['completion'].pk,rev(f['case']))
    return Outbox.objects.get(milestone=m)


def evaluate(f,j,index=0,key=None):
    return native.record(f['tester'],f['case'].pk,f['package'].pk,f['examples'][index].pk,'handoff',j.pk,f['decision_evidence'].pk,key or 'native-'+str(j.pk),rev(f['case']))


def ready(f):
    first=job(f,'native-normal');run_once(case_id=f['case'].pk);r1=evaluate(f,first)
    second=job(f,'native-exception');Grant.objects.filter(user=f['actor'],case=f['case'],action='milestone.complete').update(active=False)
    run_once(case_id=f['case'].pk);r2=evaluate(f,second,1)
    Grant.objects.filter(user=f['actor'],case=f['case'],action='milestone.complete').update(active=True)
    return first,second,r1,r2


class NativeValidationTests(TestCase):
    def test_different_successful_subject_cannot_satisfy_reviewed_example(self):
        f=fixture();j=job(f,'unrelated-native-subject');run_once(case_id=f['case'].pk)
        r=evaluate(f,j)
        self.assertFalse(r.result['matches'])
        with self.assertRaises(ValidationError):native.current(r,f['acceptor'])
        self.assertEqual(Handoff.objects.count(),1)

    def test_real_native_positive_and_negative_workers_feed_independent_owner_acceptance(self):
        f=fixture();first,second,r1,r2=ready(f)
        self.assertTrue(r1.result['matches']);self.assertTrue(r2.result['matches'])
        self.assertTrue(r1.result['underlying_workflow_executed'])
        self.assertEqual(Handoff.objects.count(),1)
        before=list(Outbox.objects.values_list('pk','attempts','status'))
        accepted=h.review(f,'acceptance');report=af13.acceptance_report(f['acceptor'],f['case'].pk,accepted.pk)
        self.assertTrue(report['requested_record_is_current']);self.assertFalse(report['whole_product_accepted'])
        self.assertEqual(before,list(Outbox.objects.values_list('pk','attempts','status')))
        self.assertEqual(evaluate(f,first).pk,r1.pk)

    def test_subject_planning_ui_does_not_execute_or_choose_expected_outcome(self):
        from adapters.native_subjects import planned
        f=fixture();a,c=f['actor'],f['case']
        before=(rev(c),Outbox.objects.count(),ValidationExample.objects.count(),ValidationReplay.objects.count())
        expected=planned(a,c,'handoff',f['pmo']['completion'].pk,'native-normal')
        self.assertEqual(expected['subject_sha256'],f['examples'][0].expected['subject_sha256'])
        self.assertFalse(expected['expected_verdict_supplied']);self.assertFalse(expected['effects_scheduled'])
        client=Client(enforce_csrf_checks=True);client.force_login(a);url=reverse('validation',args=[c.pk])
        self.assertContains(client.get(url),'Prepare an independent native source fingerprint')
        response=client.post(url,{'action':'native_subject','revision':rev(c),'family':'handoff','source_id':f['pmo']['completion'].pk,
            'reference':'native-normal','csrfmiddlewaretoken':client.cookies['csrftoken'].value},follow=True)
        self.assertContains(response,expected['subject_sha256'])
        self.assertEqual(before,(rev(c),Outbox.objects.count(),ValidationExample.objects.count(),ValidationReplay.objects.count()))
        Grant.objects.filter(user=a,case=c,action='workflow.read').update(active=False)
        for pk in [f['pmo']['completion'].pk,99999999]:
            with self.assertRaises(PermissionDenied):planned(a,c,'handoff',pk,'native-normal')

    def test_legacy_native_history_is_readable_but_cannot_establish_current_exact_subject_acceptance(self):
        f=fixture();_,_,r,_=ready(f)
        values={field.name:getattr(r,field.name) for field in r._meta.fields if field.name not in ['id','created_at']}
        old=ValidationReplay.objects.create(**dict(values,operation_key='retained-v1-native',
            provenance=dict(r.provenance,format='psl.native-validation/v1'),result=dict(r.result,implementation='psl.native-validation/v1')))
        self.assertTrue(native.native(old))
        with self.assertRaisesMessage(ValidationError,'Legacy native evaluation'):native.current(old,f['acceptor'])
        native.package_access(f['acceptor'],f['package'])
        self.assertFalse(r.provenance['execution_build_verified'])
        self.assertEqual(r.provenance['build_identity_meaning'],'observation_process_only')

    def test_operational_flagged_fixture_uses_native_evidence_without_claiming_live_or_external_acceptance(self):
        f=fixture(synthetic=False);ready(f);accepted=h.review(f,'acceptance')
        report=af13.acceptance_report(f['acceptor'],f['case'].pk,accepted.pk)
        self.assertTrue(report['requested_record_is_current'])
        self.assertFalse(report['deployment_authorized'])
        self.assertTrue(all(not r.provenance['external_acceptance_claimed'] for r in ValidationReplay.objects.all()))
        self.assertEqual(reference_values(f['native_config'])[0]['native_execution']['scope'],'native_source_receipt_only')

    def test_late_reservation_pending_unknown_and_supplied_actuals_cannot_establish_native_acceptance(self):
        f=fixture();j=job(f,'native-normal');r=evaluate(f,j)
        self.assertFalse(r.result['underlying_workflow_executed'])
        with self.assertRaises(ValidationError):native.current(r,f['acceptor'])
        run_once(case_id=f['case'].pk)
        with self.assertRaises(ValidationError):native.current(r,f['acceptor'])
        newer=evaluate(f,j,key='after-execution');self.assertTrue(newer.result['matches'])
        h.review(f,'expectations',key='new-independent-expectations')
        with self.assertRaises(ValidationError):evaluate(f,j,key='old-execution-under-new-expectations')
        with self.assertRaises(ValidationError):native.current(newer,f['acceptor'])

    def test_current_source_permissions_and_recorder_revocation_protect_history_and_reassessment(self):
        f=fixture();first,_,r,_=ready(f);h.review(f,'acceptance')
        Grant.objects.filter(user=f['acceptor'],case=f['case'],action='workflow.read').update(active=False)
        with self.assertRaises(PermissionDenied):af13.position(f['package'],f['acceptor'])
        Grant.objects.filter(user=f['acceptor'],case=f['case'],action='workflow.read').update(active=True)
        Grant.objects.filter(user=f['tester'],case=f['case'],action='validation.replay.record').update(active=False)
        with self.assertRaises(PermissionDenied):native.current(r,f['acceptor'])
        self.assertEqual(Handoff.objects.count(),1)
        outsider,foreign=setup_case(username='foreign-native')
        for pk in [first.pk,999999999]:
            with self.assertRaises(PermissionDenied):adapter.source(f['acceptor'],foreign,'handoff',pk)

    def test_native_criteria_missing_revoked_expired_and_synthetic_promotion_hold_only_acceptance(self):
        f=fixture();_,_,r,_=ready(f)
        with patch('apps.documents.native_validation.timezone.now',return_value=r.created_at+timedelta(seconds=3601)):
            with self.assertRaises(ValidationError):native.current(r,f['acceptor'])
        transition(f['actor'],f['native_config'].pk,'revoked')
        with self.assertRaises(ValidationError):h.review(f,'acceptance')
        self.assertTrue(h.evidence(f['actor'],f['case'],'document','Unrelated capture remains available').pk)
        # No supplied result may be relabelled as a native adapter observation.
        self.assertEqual(ValidationReplay.objects.filter(provenance__format=adapter.FORMAT).count(),2)

    def test_csrf_ui_source_choices_agent_and_sql_native_identity_guards(self):
        f=fixture();j=job(f,'native-normal');run_once(case_id=f['case'].pk)
        client=Client(enforce_csrf_checks=True);client.force_login(f['tester']);url=reverse('validation',args=[f['case'].pk])
        self.assertContains(client.get(url),'Evaluate an actual native workflow')
        self.assertEqual(client.post(url,{}).status_code,403)
        data={'action':'native_replay','revision':rev(f['case']),'package':f['package'].pk,'example_id':f['examples'][0].pk,'family':'handoff','job_id':j.pk,'evidence':f['decision_evidence'].pk,'operation_key':'ui-native','csrfmiddlewaretoken':client.cookies['csrftoken'].value}
        self.assertEqual(client.post(url,data).status_code,302);row=ValidationReplay.objects.get()
        self.assertTrue(row.result['matches'])
        from apps.agents.validation import investigate
        run=investigate(f['actor'],f['case'].pk,rev(f['case']));self.assertFalse(run.result['whole_product_accepted'])
        values={field.name:getattr(row,field.name) for field in row._meta.fields if field.name not in ['id','created_at']}
        with self.assertRaises(DatabaseError),transaction.atomic():
            ValidationReplay.objects.create(**dict(values,operation_key='foreign-job',provenance=dict(row.provenance,job=999999999)))
        with self.assertRaises(DatabaseError),transaction.atomic():
            ValidationReplay.objects.filter(pk=row.pk).update(actual={})
        self.assertEqual(f['native_config'].envelope['value']['schema_ref'],NATIVE_SCHEMA)

    def test_pilot_links_current_native_owner_scope_and_rechecks_revoked_source_and_review(self):
        from apps.policy import pilot
        from tests.test_pilot_preflight import selection
        from apps.agents.pilot import investigate
        f=fixture();ready(f);accepted=h.review(f,'acceptance');a,c=f['actor'],f['case']
        payload=dict(selection(a,c),format='psl.pilot-contract/v2',process_ids=f['package'].payload['process_ids'],acceptance_reviews=[accepted.pk])
        contract=pilot.configure(a,c.pk,payload);pack=pilot.capture(a,c.pk,contract.pk)
        report=pilot.inspect(a,c.pk,pack.pk);human=report['snapshot']['human_acceptance']
        self.assertTrue(report['current']);self.assertTrue(human['references'][0]['current'])
        self.assertTrue(human['references'][0]['native_execution_only']);self.assertEqual(human['uncovered_process_ids'],[])
        self.assertFalse(report['operational_acceptance']);self.assertEqual(investigate(a,c.pk,pack.pk)['effect_tools'],[])
        # Pack capture does not change AF13's source/example/review inputs (no proof cycle).
        self.assertEqual(af13.approved_review(f['package'],'acceptance').pk,accepted.pk)
        h.review(f,'acceptance','revoke',key='withdraw-native-acceptance')
        report=pilot.inspect(a,c.pk,pack.pk);self.assertFalse(report['current'])
        self.assertFalse(pilot.observation(a,c,payload,contract)['human_acceptance']['references'][0]['current'])
        Grant.objects.filter(user=a,case=c,action='workflow.read').update(active=False)
        with self.assertRaises(PermissionDenied):pilot.inspect(a,c.pk,pack.pk)

    def test_pilot_ui_selects_native_review_and_rejects_foreign_or_unsupported_contract_fields(self):
        from apps.policy import pilot,pilot_validators
        from tests.test_pilot_preflight import selection
        f=fixture();ready(f);r=h.review(f,'acceptance');a,c=f['actor'],f['case']
        client=Client(enforce_csrf_checks=True);client.force_login(a);url=reverse('pilot_preflight',args=[c.pk])
        self.assertContains(client.get(url),'AF13 review #'+str(r.pk))
        result=client.post(url,{'process_ids':f['package'].payload['process_ids'],'operations':selection(a,c)['operations'],
            'participants':[str(a.pk)],'actions':['case.read'],'acceptance_reviews':[str(r.pk)],'csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(result.status_code,302);self.assertContains(client.get(result.url),'Source-owned owner decisions')
        payload=dict(selection(a,c),format='psl.pilot-contract/v2',acceptance_reviews=[999999999])
        with self.assertRaises(ValidationError):pilot.configure(a,c.pk,payload,1)
        for bad in [dict(payload,acceptance_reviews=[r.pk,r.pk]),dict(payload,format='psl.pilot-contract/v1')]:
            with self.assertRaises(ValidationError):pilot_validators.validate(c,bad)

    def test_synthetic_case_cannot_promote_native_history_to_operational_acceptance(self):
        f=fixture(level='operational');ready(f)
        with self.assertRaisesMessage(ValidationError,'Synthetic cases'):h.review(f,'acceptance')

    def test_reported_external_actuals_matching_examples_still_cannot_establish_operational_execution(self):
        f=fixture(synthetic=False)
        for ex in f['examples']:
            supplied=dict(f['config']['replay'],example_id=ex.pk,actual=ex.expected,evidence_class='reported_external')
            evidence=h.evidence(f['actor'],f['case'],'validation_result',json.dumps(supplied))
            row=af13.record_replay(f['tester'],f['case'].pk,f['package'].pk,evidence.pk,'supplied-'+str(ex.pk),rev(f['case']))
            self.assertTrue(row.result['matches']);self.assertFalse(row.result['underlying_workflow_executed'])
        with self.assertRaises(ValidationError):h.review(f,'acceptance')

    def test_real_controlled_publication_uses_immutable_reservation_time_and_receipt(self):
        from apps.documents import controlled,delivery
        from apps.documents.models import PublicationJob
        f=fixture(family='publication');a,c=f['actor'],f['case'];e=f['decision_evidence']
        p=controlled.reserve_publication(a,c.pk,f['publications'][0].pk,rev(c))
        j=PublicationJob.objects.get(publication=p);delivery.run_publication_once()
        row=native.record(a,c.pk,f['package'].pk,f['examples'][0].pk,'publication',j.pk,e.pk,'native-publication',rev(c))
        self.assertTrue(row.result['matches']);self.assertEqual(adapter.reserved_at(j,'publication'),p.created_at)
        self.assertEqual(native.current(row,a),row.pk)


class OwnedNativeSourceTests(TestCase):
    def check_source(self,a,c,family,j):
        actual,head,_=adapter.observe(a,c,family,j.pk)
        self.assertEqual(actual['state'],'confirmed');self.assertTrue(actual['receipt_present'])
        self.assertIsNotNone(head['receipt_sha256']);self.assertEqual(head['source_reserved_at'],adapter.reserved_at(j,family).isoformat())
        # Execute each actual SQL source branch as well, rejecting a foreign package.
        f=fixture();_,_,r,_=ready(f)
        values={field.name:getattr(r,field.name) for field in r._meta.fields if field.name not in ['id','created_at']}
        with self.assertRaisesMessage(DatabaseError,'PSL invalid native workflow evaluation identity'),transaction.atomic():
            ValidationReplay.objects.create(**dict(values,operation_key='wrong-source-scope',actual=dict(r.actual,family=family),provenance=dict(r.provenance,family=family,job=j.pk)))

    def test_engineering_immutable_request_timestamp_and_real_receipt(self):
        from tests import reconciliation_helpers as h
        from apps.baas.models import CorrectiveJob
        a,c,engineer,v,batches=h.fixture();a.username='native-engineering-actor';a.save(update_fields=['username'])
        request=h.request(a,c,h.run(a,c,batches));h.delivery(a,c,request)
        self.check_source(a,c,'engineering',CorrectiveJob.objects.get(request=request))

    def test_partner_immutable_report_timestamp_and_real_finance_receipt(self):
        from tests import partner_helpers as h
        a,c,fin,v,cov=h.fixture();a.username='native-partner-actor';a.save(update_fields=['username'])
        report=h.report(a,c);receipt=h.delivered(a,c,fin,report)
        self.check_source(a,c,'partner',receipt.job)

    def test_private_response_immutable_human_decision_time_and_receipt(self):
        from tests.support_release_helpers import ready as prepared,release
        from tests.readiness_helpers import endpoint
        from apps.baas.support_release_delivery import run_once
        with endpoint():
            f=prepared('owned-native-support');j=release(f);run_once(f['case'].pk)
            self.check_source(f['actor'],f['case'],'supportresponse',j)
            Grant.objects.filter(user=f['actor'],case=f['case'],action='support.private.read').update(active=False)
            with self.assertRaises(PermissionDenied):adapter.observe(f['actor'],f['case'],'supportresponse',j.pk)


class NativeEvaluationConcurrencyTests(TransactionTestCase):
    def test_worker_row_lock_holds_native_evaluation_without_deadlock_or_receipt_claim(self):
        f=fixture();j=job(f,'busy-native-worker');locked,release=Event(),Event()
        def holder():
            close_old_connections()
            try:
                with transaction.atomic():
                    Outbox.objects.select_for_update().get(pk=j.pk);locked.set();self.assertTrue(release.wait(20))
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(holder);self.assertTrue(locked.wait(10))
            try:
                with self.assertRaisesMessage(ValidationError,'being reconciled'):evaluate(f,j)
            finally:release.set()
            future.result(timeout=25)
        self.assertFalse(ValidationReplay.objects.exists());self.assertFalse(Handoff.objects.exists())
