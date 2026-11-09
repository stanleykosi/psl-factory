"""Synthetic source scenarios P57-M01/M02, P59-M01/M02; not whole-process acceptance."""
import json
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import DatabaseError,transaction
from django.utils import timezone
from django.urls import reverse
from apps.core.services import add_evidence
from apps.pmo.changes import assess_change,impact,decide_change,authorize_change,log_change
from apps.pmo.change_execution import record_execution,execution_manifest,draft_change_document
from apps.pmo.change_impacts import timeline_text
from apps.pmo.reporting import draft_period_report
from apps.documents.controlled import register_template
from tests.helpers import rev
from tests.signature_helpers import packet_for, reaffirm_for
from tests import test_commercial_changes as native_tests
from tests.test_commercial_changes import impact_fixture

class ChangeImpactTests(TestCase):
    setUp=native_tests.ControlledChangeTests.setUp
    assessments=native_tests.ControlledChangeTests.assessments
    ready=native_tests.ChangeExecutionTests.ready
    authorized=native_tests.ChangeExecutionTests.authorized
    change_template=native_tests.ChangeExecutionTests.change_template
    publish_change=native_tests.ChangeExecutionTests.publish_change

    def reassess(self,team,**changes):
        data=impact_fixture(team);data.update(changes)
        return assess_change(self.actor,self.case.pk,self.cv.pk,team,False,False,False,self.source.pk,'Explicit synthetic owner evidence',rev(self.case),**data)

    def test_native_console_records_owner_fields_and_actual_scope_deviation(self):
        self.client.force_login(self.actor);url=reverse('changes',args=[self.case.pk])
        data=impact_fixture('Engineering')
        post={'action':'assess','revision':rev(self.case),'version':self.cv.pk,'contributor':'Engineering',
              'cost_impact':'false','timeline_impact':'false','client_facing':'false','production_impact':'unknown',
              'scope_items':'CR-001/item-1','evidence':self.source.pk,'note':'Owner-authored console statement'}
        post.update({'impact_'+k:v for k,v in data['outputs'].items()})
        self.assertEqual(self.client.post(url,post).status_code,302)
        assessment=self.cv.assessments.get()
        self.assertEqual(assessment.impact_details['outputs'],data['outputs'])
        self.assertEqual(assessment.impact_details['scope_items'],data['scope_items'])
        self.assertContains(self.client.get(url),'Engineering reviewed its synthetic discipline impact')
        auth=self.authorized();events=self.ready(auth)
        post={'action':'execution','revision':rev(self.case),'authorization':auth.pk,'kind':'implemented',
              'scope_items':'CR-001/item-1\nextra-item','evidence':events['implemented'].evidence_id,
              'note':'Engineering reports extra scope; authority question remains open'}
        self.assertEqual(self.client.post(url,post).status_code,302)
        with self.assertRaisesRegex(ValidationError,'Extra unapproved scope'):execution_manifest(auth)

    def test_p57_four_team_outputs_bound_to_current_baseline(self):
        self.assessments(False,False,False)
        ids,flags=impact(self.cv)
        self.assertEqual(len(ids),4)
        for row in self.cv.assessments.all():
            self.assertEqual(row.impact_details['baseline'],self.cv.base_manifest)
            self.assertEqual(set(row.impact_details['outputs']),{'discipline','timeline','cost_resource','risk','dependency'})
        self.assertFalse(flags['timeline_impact'])
        with self.assertRaises(DatabaseError),transaction.atomic():
            self.cv.assessments.filter(pk=ids[0]).update(impact_details={})
        from apps.pmo.models import Baseline
        from apps.pmo.signatures import assert_current_signed_baseline
        other=add_evidence(self.actor,self.case.pk,'plan','Changed current owner plan','synthetic:plan')
        # P20 correctly forbids changing a signed pointer without new dual proof.
        with self.assertRaisesMessage(DatabaseError,'Separate current SOW and PRD signature consumption required'),transaction.atomic():
            Baseline.objects.filter(case=self.case).update(plan=other)
        self.assertEqual(Baseline.objects.get(case=self.case).plan_id,self.e['plan'].pk)

        # An independent, fully approved change replaces the baseline legitimately.
        # Keep the original request current within its own history so its later
        # decision is rejected specifically for the stale baseline, not revision.
        replacement=log_change(self.actor,self.case.pk,'CR-BASELINE','Normal','Delivery',
            'Separately approved plan replacement','New baseline owner request',self.source.pk,rev(self.case))
        for team in ['Engineering','QA','Infra','Security']:
            assess_change(self.actor,self.case.pk,replacement.pk,team,True,True,True,self.source.pk,
                'Owner reviewed replacement baseline',rev(self.case),**impact_fixture(team,True))
        for role in ['Product','Engineering','Client','Engineering Lead','Security Manager']:
            decide_change(self.actor,self.case.pk,replacement.pk,role,'approve',self.source.pk,
                'Owner approves exact replacement assessment',rev(self.case))
        revised=dict(self.e,plan=other)
        for kind in ['costing','sow','signature']:
            revised[kind]=add_evidence(self.actor,self.case.pk,kind,'Replacement '+kind,'synthetic:baseline-replacement')
        commercial=native_tests.proposal(self.actor,self.case,revised,self.source)
        native_tests.approvals(self.actor,self.case,commercial)
        receipt=native_tests.delivered(self.actor,self.case,commercial,self.t)
        response=native_tests.capture_response(self.actor,self.case.pk,commercial.pk,receipt.pk,'signed',
            revised['signature'].pk,'Human checked exact replacement signed SOW',rev(self.case))
        packet=packet_for(self.actor,self.case,revised,commercial)
        authorize_change(self.actor,self.case.pk,replacement.pk,commercial.pk,rev(self.case))
        adoption=native_tests.adopt_signed(self.actor,self.case.pk,commercial.pk,response.pk,rev(self.case))
        self.assertEqual(adoption.before,self.cv.base_manifest)
        self.assertEqual(adoption.after['plan_id'],other.pk)
        self.assertEqual(assert_current_signed_baseline(self.case).pk,packet.pk)
        self.cv.change.refresh_from_db()
        self.assertEqual(self.cv.change.current_id,self.cv.pk)
        self.assertEqual(list(self.cv.assessments.order_by('pk').values_list('pk',flat=True)),ids)
        with self.assertRaisesRegex(ValidationError,'active baseline'):
            decide_change(self.actor,self.case.pk,self.cv.pk,'Product','approve',self.source.pk,'Owner decision',rev(self.case))

    def test_p57_unknown_infra_and_missing_category_do_not_default_to_nonproduction(self):
        self.assessments(False,False,False)
        self.reassess('Infra',production_impact=None)
        with self.assertRaisesRegex(ValidationError,'production deployment impact unknown'):impact(self.cv)
        self.reassess('Infra',production_impact=False)
        output=impact_fixture('QA')['outputs'];output['risk']=None
        self.reassess('QA',outputs=output)
        with self.assertRaisesRegex(ValidationError,'risk/dependency impact remains unknown'):impact(self.cv)
        self.reassess('QA');self.assertEqual(len(impact(self.cv)[0]),4)

    def test_legacy_empty_details_remain_readable_but_not_new_approval_eligible(self):
        for team in ['Engineering','QA','Infra','Security']:
            assess_change(self.actor,self.case.pk,self.cv.pk,team,False,False,False,self.source.pk,'Historical generic owner statement',rev(self.case))
        with self.assertRaisesRegex(ValidationError,'outputs.*unknown'):impact(self.cv)
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(reverse('changes',args=[self.case.pk])),'Historical generic owner statement')

    def test_p59_extra_scope_is_recorded_and_requires_new_revision_not_later_normalization(self):
        auth=self.authorized();events=self.ready(auth)
        self.assertEqual(len(execution_manifest(auth)),4)
        source=add_evidence(self.actor,self.case.pk,'change_implementation','Engineering found additional unapproved scope','synthetic:deviation')
        deviation=record_execution(self.actor,self.case.pk,auth.pk,'implemented',source.pk,'Return for new assessment and authority',rev(self.case),scope_items=['CR-001/item-1','unapproved-extra'])
        self.assertEqual(deviation.impact_details['extra_scope'],['unapproved-extra'])
        with self.assertRaisesRegex(ValidationError,'Extra unapproved scope'):execution_manifest(auth)
        self.ready(auth)
        with self.assertRaisesRegex(ValidationError,'Extra unapproved scope'):execution_manifest(auth)
        self.assertEqual(auth.execution.filter(pk=deviation.pk).count(),1)
        # Reassessment authorizes only a new forward revision, never the old deviation.
        self.cv=log_change(self.actor,self.case.pk,'CR-001','Normal','Delivery','Forward scope includes the extra item','Human requests reassessment',self.source.pk,rev(self.case))
        self.assessments(False,False,False)
        self.reassess('Engineering',scope_items=['CR-001/item-1','unapproved-extra'])
        for role in ['Product','Engineering']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'New forward scope decision',rev(self.case))
        successor=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        for kind,e_kind in [('plan_updated','plan'),('implemented','change_implementation'),('testing_validated','change_validation'),('documentation_updated','document')]:
            evidence=add_evidence(self.actor,self.case.pk,e_kind,'New forward work after authorization','synthetic:forward')
            record_execution(self.actor,self.case.pk,successor.pk,kind,evidence.pk,'Fresh owner evidence for successor only',rev(self.case),scope_items=['CR-001/item-1','unapproved-extra'] if kind=='implemented' else None)
        self.assertEqual(len(execution_manifest(successor)),4)
        with self.assertRaisesRegex(ValidationError,'Extra unapproved scope'):execution_manifest(auth)


    def test_unknown_scope_can_be_clarified_but_never_assumed(self):
        auth=self.authorized();self.ready(auth)
        source=add_evidence(self.actor,self.case.pk,'change_implementation','Owner has not supplied item inventory','synthetic:unknown')
        unknown=record_execution(self.actor,self.case.pk,auth.pk,'implemented',source.pk,'Inventory unknown',rev(self.case))
        self.assertEqual(unknown.impact_details['scope_status'],'unknown')
        validation=add_evidence(self.actor,self.case.pk,'change_validation','QA validation record','synthetic:qa')
        record_execution(self.actor,self.case.pk,auth.pk,'testing_validated',validation.pk,'Testing evidence does not decide scope',rev(self.case))
        with self.assertRaisesRegex(ValidationError,'scope unknown'):execution_manifest(auth)
        self.ready(auth);self.assertEqual(len(execution_manifest(auth)),4)

    def test_production_completion_routes_to_native_p32_and_does_not_block_plan_work(self):
        self.assessments(False,False,False);self.reassess('Infra',production_impact=True)
        for role in ['Product','Engineering']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Owner decision',rev(self.case))
        auth=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        self.ready(auth)
        with self.assertRaisesRegex(ValidationError,'P32 delivery dossier/readiness'):execution_manifest(auth)
        self.assertEqual(auth.execution.count(),4)
        implementation=auth.execution.get(kind='implemented')
        with self.assertRaisesRegex(ValidationError,'case delivery dossier'):
            record_execution(self.actor,self.case.pk,auth.pk,'implemented',implementation.evidence_id,'Exact dossier must exist in this case',rev(self.case),scope_items=['CR-001/item-1'],dossier_id=999999)

    def test_p59_timeline_flows_to_exact_updated_plan_weekly_report_and_notice(self):
        self.assessments(False,True,True)
        for role in ['Product','Engineering','Client','Engineering Lead','Security Manager']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Owner decision on supplied timeline',rev(self.case))
        auth=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case));events=self.ready(auth)
        plan=json.loads(events['plan_updated'].evidence.body)
        self.assertEqual(plan['approved_timeline'],timeline_text(auth))
        self.assertEqual(plan['assessment_ids'],auth.assessment_ids)
        with self.assertRaisesRegex(ValidationError,'weekly client report'):execution_manifest(auth)
        # A report manifest alone cannot prove that a template displayed the impact.
        from apps.documents.models import Template
        # Explicit historical immutable template fixture; current registration disallows this shape.
        narrow=Template.objects.create(case=self.case,name='Synthetic narrow weekly',version=1,created_by=self.actor,evidence=self.e['policy_decision'],
            definition={'document_type':'status_report','required_fields':['executive_summary'],'audience_fields':{'client':['executive_summary']}})
        from apps.identity.models import Grant
        Grant.objects.get_or_create(case=self.case,user=self.actor,action='report.read')
        before=timezone.now()
        draft_period_report(self.actor,self.case.pk,'weekly_client',before-timedelta(days=14),before-timedelta(days=7),narrow.pk,'client',rev(self.case))
        with self.assertRaisesRegex(ValidationError,'weekly client report'):execution_manifest(auth)
        # Native report service and native manifest, not an extra report engine.
        template=register_template(self.actor,self.case.pk,'Synthetic weekly',{'document_type':'status_report','required_fields':['executive_summary','status'],
            'audience_fields':{'client':['executive_summary','status','timeline','scope','risks','dependencies']}},self.e['policy_decision'].pk,rev(self.case))
        now=timezone.now()
        report=draft_period_report(self.actor,self.case.pk,'weekly_client',now-timedelta(days=7),now,template.pk,'client',rev(self.case))
        texts='\n'.join(s['text'] for s in report.version.payload['sections'])
        self.assertIn(timeline_text(auth),texts)
        self.assertIn(events['plan_updated'].pk,report.manifest['change_history']['execution'])
        self.assertEqual(len(execution_manifest(auth)),4)
        receipt=self.publish_change(auth,self.change_template(),'notice')
        notice=receipt.publication.version
        self.assertEqual(receipt.payload,notice.payload)
        self.assertIn(timeline_text(auth),'\n'.join(s['text'] for s in notice.payload['sections']))
        # Report from before a later plan amendment cannot prove the later plan.
        source=add_evidence(self.actor,self.case.pk,'plan','Updated detailed plan','synthetic:later-plan')
        record_execution(self.actor,self.case.pk,auth.pk,'plan_updated',source.pk,'Later plan amendment',rev(self.case))
        with self.assertRaisesRegex(ValidationError,'weekly client report'):execution_manifest(auth)

    def test_assessment_projection_orders_reassessed_owners_explicitly(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.pmo.change_impacts import authorized_details
        self.assessments(False,False,False);self.reassess('Engineering')
        for role in ['Product','Engineering']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Exact reassessed scope',rev(self.case))
        auth=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        with CaptureQueriesContext(connection) as queries:rows=authorized_details(auth)
        self.assertEqual(list(rows),['QA','Infra','Security','Engineering'])
        self.assertEqual([r.pk for r in rows.values()],sorted(auth.assessment_ids))
        self.assertTrue(any('ORDER BY "pmo_changeassessment"."id" ASC' in q['sql'] for q in queries))
        self.assertEqual(timeline_text(auth),'\n'.join(team+': No timeline change' for team in rows))

    def approved_report(self):
        auth=self.authorized();self.ready(auth)
        report=native_tests.weekly_change_report(self.actor,self.case,self.e['policy_decision'])
        return auth,report

    def assert_timeline_status(self,report,status):
        from apps.pmo.change_impacts import timeline_snapshot,report_timeline
        from apps.pmo.reporting import binding_manifest
        snapshot=timeline_snapshot(self.case)
        self.assertEqual(snapshot['rows'][0]['status'],status)
        self.assertIn(status,report_timeline(snapshot))
        self.assertNotEqual(binding_manifest(report),report.manifest)
        self.assertEqual(self.cv.changeauthorization_set.get().execution.filter(kind='plan_updated').count(),1)

    def test_weekly_timeline_marks_superseded_revision_and_invalidates_old_report(self):
        auth,report=self.approved_report()
        log_change(self.actor,self.case.pk,'CR-001','Normal','Delivery','Revised scope','Owner revision',self.source.pk,rev(self.case))
        self.assert_timeline_status(report,'superseded')

    def test_weekly_timeline_marks_later_returned_decision_and_invalidates_old_report(self):
        auth,report=self.approved_report()
        native_tests.artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',
            {'rules':[{'role':'Product','actions':['return']}]},self.e['policy_decision'])
        decide_change(self.actor,self.case.pk,self.cv.pk,'Product','return',self.source.pk,'Owner returns approved scope for reassessment',rev(self.case))
        self.assert_timeline_status(report,'held')

    def test_weekly_timeline_marks_revoked_authority_even_without_a_new_decision_row(self):
        from apps.identity.models import Grant
        auth,report=self.approved_report()
        Grant.objects.filter(case=self.case,user=self.actor,action='change.decide').update(active=False)
        self.assert_timeline_status(report,'held')

    def test_weekly_timeline_marks_scope_deviation_and_retains_original_plan_history(self):
        auth,report=self.approved_report()
        source=add_evidence(self.actor,self.case.pk,'change_implementation','Actual extra item','synthetic:extra')
        record_execution(self.actor,self.case.pk,auth.pk,'implemented',source.pk,'Return for authority',rev(self.case),scope_items=['CR-001/item-1','extra'])
        self.assert_timeline_status(report,'held')

    def test_report_drafted_while_held_requires_refresh_after_authority_restoration(self):
        from apps.identity.models import Grant
        self.assessments(False,True,True)
        for role in ['Product','Engineering','Client','Engineering Lead','Security Manager']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Owner timeline decision',rev(self.case))
        auth=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case));self.ready(auth)
        grants=Grant.objects.filter(case=self.case,user=self.actor,action='change.decide')
        grants.update(active=False)
        held=native_tests.weekly_change_report(self.actor,self.case,self.e['policy_decision'])
        self.assertEqual(held.manifest['normal_change_timeline']['rows'][0]['status'],'held')
        grants.update(active=True)
        with self.assertRaisesRegex(ValidationError,'weekly client report'):execution_manifest(auth)
        current=native_tests.weekly_change_report(self.actor,self.case,self.e['policy_decision'])
        self.assertEqual(current.manifest['normal_change_timeline']['rows'][0]['status'],'current approved')
        self.assertEqual(len(execution_manifest(auth)),4)

    def test_timeline_notice_cannot_omit_approved_impact_in_rendered_audience(self):
        from apps.documents.controlled import create_version,preflight
        from apps.pmo.models import ChangeDocumentBinding
        self.assessments(False,True,True)
        for role in ['Product','Engineering','Client','Engineering Lead','Security Manager']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Owner decision',rev(self.case))
        auth=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        from apps.documents.models import Template
        # Explicit historical immutable template fixture; current registration disallows this shape.
        template=Template.objects.create(case=self.case,name='Narrow notice',version=1,created_by=self.actor,evidence=self.e['policy_decision'],
            definition={'document_type':'project_artifact','required_fields':['executive_summary','status'],'audience_fields':{'client':['executive_summary','status']}})
        with self.assertRaisesRegex(ValidationError,'notice template must display'):
            draft_change_document(self.actor,self.case.pk,auth.pk,template.pk,'notice',rev(self.case))
        # Existing historical narrow binding still cannot pass current publication preflight.
        fields={k:{'text':'Historical narrow notice without timeline','evidence_ids':[self.source.pk]} for k in ['executive_summary','status']}
        old=create_version(self.actor,self.case.pk,template.pk,'Historical incomplete notice','client',fields,rev(self.case))
        ChangeDocumentBinding.objects.create(version=old,authorization=auth,purpose='notice')
        self.assertTrue(any('exact approved timeline' in x for x in preflight(old)))


from tests import test_delivery as delivery_tests

class ProductionChangeImpactTests(delivery_tests.DeliveryFixture,TestCase):

    def setUp(self):
        self.setup_delivery();native_tests.change_roles(self.actor,self.case,self.e['policy_decision'])
        # Expanded role configuration needs a current human attestation of the
        # original exact signatures, not a bypass of P20 release assurance.
        reaffirm_for(self.actor,self.case)
        self.change_source=add_evidence(self.actor,self.case.pk,'change_request','Synthetic production change','synthetic:production-change')
        self.cv=log_change(self.actor,self.case.pk,'CR-001','Normal','Delivery','Approved production scope','Owner request',self.change_source.pk,rev(self.case))

    def test_p32_ready_dossier_must_match_explicit_engineering_candidate(self):
        from apps.pmo.gates import register_candidate,record_gate
        self.ready()  # Existing native Planning, UAT/Engineering Go, GLPI and readiness services.
        for team in ['Engineering','QA','Infra','Security']:
            data=impact_fixture(team)
            if team=='Infra':data['production_impact']=True
            assess_change(self.actor,self.case.pk,self.cv.pk,team,False,False,False,self.change_source.pk,'Owner confirms actual production change impact',rev(self.case),**data)
        for role in ['Product','Engineering']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.change_source.pk,'Owner scope decision',rev(self.case))
        auth=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        events=native_tests.ChangeExecutionTests.ready(self,auth)
        other=register_candidate(self.actor,self.case.pk,'unrelated-build-same-baseline',self.e['requirements'].pk,rev(self.case))
        with self.assertRaisesRegex(ValidationError,'exact Engineering implementation candidate'):
            record_execution(self.actor,self.case.pk,auth.pk,'implemented',events['implemented'].evidence_id,'Wrong valid ready dossier',rev(self.case),scope_items=['CR-001/item-1'],candidate_id=other.pk,dossier_id=self.d.pk)
        with self.assertRaisesRegex(ValidationError,'exact Engineering implementation candidate'):
            record_execution(self.actor,self.case.pk,auth.pk,'implemented',events['implemented'].evidence_id,'Candidate linkage unknown',rev(self.case),scope_items=['CR-001/item-1'],dossier_id=self.d.pk)
        implementation=record_execution(self.actor,self.case.pk,auth.pk,'implemented',events['implemented'].evidence_id,'Engineering binds actual candidate to approved scope',rev(self.case),scope_items=['CR-001/item-1'],candidate_id=self.candidate.pk,dossier_id=self.d.pk)
        record_execution(self.actor,self.case.pk,auth.pk,'testing_validated',events['testing_validated'].evidence_id,'QA validates exact latest implementation',rev(self.case))
        self.assertEqual(implementation.impact_details['candidate_id'],self.candidate.pk)
        self.assertEqual(len(implementation.impact_details['readiness']['glpi']),3)
        self.assertEqual(implementation.impact_details['dossier_id'],self.d.pk)
        self.assertEqual(len(execution_manifest(auth)),4)
        changed=self.evidence('approval','New unverified GLPI Security source')
        record_gate(self.actor,self.case.pk,self.candidate.pk,'glpi_security','GLPI-001',changed.pk,rev(self.case))
        with self.assertRaises(ValidationError):execution_manifest(auth)
