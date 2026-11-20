"""Independent native P38/P39 prerequisites, with actual Finance attestations retained."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.agents.models import AgentRun
from apps.agents.delivery import investigate_delivery
from apps.pmo.delivery import open_dossier
from apps.pmo.delivery_closure import (
    closure_inputs, closure_requirements, confirm_finance, current_finance_confirmation, decide_closure, finalize_closure,
)
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.gates import register_candidate
from apps.pmo.models import DeliveryRecord,DeliveryDocumentBinding,MeetingVersion,Milestone
from apps.pmo.meetings import record_meeting
from apps.pmo.services import complete_milestone
from apps.workflows.services import run_once
from apps.workflows.models import FactoryWork
from adapters.delivery import LocalDeliveryAdapter
from tests.helpers import rev,setup_case
from tests.test_delivery import DeliveryFixture


class ClosurePreparationTests(DeliveryFixture,TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery();selected=f.closing()
        for key,value in vars(f).items():setattr(cls,key,value)
        cls.selected=selected

    def checks(self,data=None):return {r['key']:r for r in closure_requirements(self.d,data)['checks']}

    def test_independent_unknown_inputs_and_agent_use_same_native_checks_without_draft_or_effect(self):
        self.assertFalse(DeliveryDocumentBinding.objects.filter(dossier=self.d,purpose='closure').exists())
        result=LocalDeliveryAdapter().read_closure(self.d);checks={c['key']:c for c in result['checks']}
        self.assertEqual(checks['retrospective']['status'],'unknown');self.assertEqual(checks['report']['status'],'unknown')
        self.assertEqual(checks['finance']['status'],'current');self.assertFalse(result['ready_to_prepare'])
        before=DeliveryRecord.objects.filter(dossier=self.d).count()
        run=investigate_delivery(self.actor,self.case.pk,self.d.pk,rev(self.case),self.selected)
        self.assertTrue(run.result['closure_requirements']['ready_to_prepare']);self.assertFalse(run.result['approval_granted'])
        self.assertEqual(run.result['coverage']['scope'],'latest_per_kind_and_consumed_documents')
        snapshot=closure_inputs(self.d,self.selected);current=self.checks(self.selected)
        self.assertEqual(current['finance']['references'],[snapshot['finance_confirmation_id']])
        self.assertEqual(current['handover']['references'],snapshot['handover_ids'])
        self.assertFalse(DeliveryDocumentBinding.objects.filter(dossier=self.d,purpose='closure').exists())
        self.assertEqual(DeliveryRecord.objects.filter(dossier=self.d).count(),before)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=self.d,kind__in=['closure_decision','closure']).exists())

    def test_changed_finance_inventory_needs_actual_current_confirmation_without_holding_other_preparation(self):
        candidate = register_candidate(self.actor, self.case.pk, 'no-finance-confirmation',
                                       self.e['requirements'].pk, rev(self.case))
        unconfirmed = open_dossier(self.actor, self.case.pk, candidate.pk, self.e['plan'].pk,
                                   'Separate synthetic delivery with no Finance confirmation.', rev(self.case))
        self.client.force_login(self.actor)
        page = self.client.get(reverse('closure_preparation', args=[self.case.pk, unconfirmed.pk]))
        self.assertContains(page, '<summary><strong>Finance notification coverage</strong> · Unknown</summary>', html=True)
        self.assertContains(page, 'Finance confirmation has not been recorded.')
        self.assertFalse(page.context['report']['ready_to_prepare'])
        finance = next(check for check in page.context['report']['checks'] if check['key'] == 'finance')
        self.assertEqual((finance['status'], finance['references']), ('unknown', []))
        with self.assertRaises(ValidationError):
            current_finance_confirmation(unconfirmed)

        old=self.checks(self.selected)['finance']['references']
        m=complete_milestone(self.actor,self.case.pk,'Additional completed milestone',self.e['completion'].pk,rev(self.case));self.assertTrue(run_once())
        checks=self.checks();self.assertEqual(checks['finance']['status'],'held');self.assertEqual(checks['archive']['status'],'current')
        self.assertEqual(checks['retrospective']['status'],'unknown')
        page = self.client.get(reverse('closure_preparation', args=[self.case.pk, self.d.pk]), self.selected)
        self.assertContains(page, '<summary><strong>Finance notification coverage</strong> · Needs attention</summary>', html=True)
        self.assertFalse(page.context['report']['ready_to_prepare'])
        with self.assertRaises(ValidationError):
            confirm_finance(self.actor,self.case.pk,self.d.pk,[],True,self.e['completion'].pk,'Empty is not current coverage',rev(self.case))
        ids=list(Milestone.objects.filter(case=self.case).order_by('pk').values_list('pk',flat=True))
        current=confirm_finance(self.actor,self.case.pk,self.d.pk,ids,True,self.e['completion'].pk,'Actual Finance attestation of complete updated inventory',rev(self.case))
        self.assertEqual(self.checks(self.selected)['finance']['references'],[current.pk]);self.assertNotEqual(old,[current.pk])
        self.assertTrue(closure_requirements(self.d,self.selected)['ready_to_prepare'])

    def test_retrospective_version_time_and_typed_foreign_sources_are_checked_independently(self):
        prior=MeetingVersion.objects.get(pk=self.selected['retrospective_id'])
        new=record_meeting(self.actor,self.case.pk,prior.meeting.reference,'retrospective',timezone.now()+timedelta(days=1),
            'Future synthetic retrospective','Not an actual occurred meeting',[self.actor.pk],[],self.e['requirements'].pk,rev(self.case),meeting_id=prior.meeting_id)
        self.assertEqual(self.checks(self.selected)['retrospective']['status'],'held')
        future=dict(self.selected,retrospective_id=new.pk)
        self.assertIn('must have occurred',self.checks(future)['retrospective']['finding'])
        self.assertEqual(self.checks(future)['finance']['status'],'current')
        for pk in [True,1.2,'1',0,9223372036854775808]:
            with self.assertRaises(ValidationError):closure_requirements(self.d,dict(self.selected,retrospective_id=pk))
            with self.assertRaises(ValidationError):closure_inputs(self.d,dict(self.selected,report_evidence_id=pk))
        other,case=setup_case(username='foreign-closure')
        evidence=add_evidence(other,case.pk,'closure_report','PRIVATE FOREIGN REPORT','synthetic:foreign')
        self.assertEqual(self.checks(dict(self.selected,report_evidence_id=evidence.pk))['report']['status'],'held')

    def test_current_native_handover_version_and_revoked_finance_authority_hold_preflight(self):
        from apps.documents.controlled import create_version
        old=DeliveryDocumentBinding.objects.get(dossier=self.d,purpose='handover').version
        create_version(self.actor,self.case.pk,old.template_id,old.document.title,old.audience,old.fields,rev(self.case),document_id=old.document_id)
        checks=self.checks(self.selected);self.assertEqual(checks['handover']['status'],'held');self.assertIn('newer document revision',checks['handover']['finding'])
        Grant.objects.filter(user=self.actor,case=self.case,action='delivery.finance_confirm').update(active=False)
        self.assertEqual(self.checks(self.selected)['finance']['status'],'held')
        with self.assertRaises(ValidationError):closure_inputs(self.d,self.selected)

    def test_closed_checklist_reads_the_exact_recorded_legacy_sources_without_new_selection(self):
        self.assertEqual(connection.vendor, 'postgresql')
        version = draft_delivery_document(self.actor, self.case.pk, self.d.pk, 'closure', self.t.pk,
                                          self.selected, rev(self.case))
        decide_closure(self.actor, self.case.pk, version.pk, 'approve', self.e['requirements'].pk,
                       'Synthetic approval of the exact prior closure sources.', rev(self.case))
        closed = finalize_closure(self.actor, self.case.pk, self.d.pk, rev(self.case))
        self.assertFalse(FactoryWork.objects.filter(case=self.case, definition='delivery-closure/v1').exists())

        original = MeetingVersion.objects.select_related('meeting').get(pk=self.selected['retrospective_id'])
        later = record_meeting(self.actor, self.case.pk, original.meeting.reference, 'retrospective', timezone.now(),
                               'Later learning review', 'Later private retrospective summary', [self.actor.pk], [],
                               self.e['requirements'].pk, rev(self.case), meeting_id=original.meeting_id)
        other_report = add_evidence(self.actor, self.case.pk, 'closure_report', 'Later report evidence body', 'synthetic:later')
        unrelated = {'retrospective_id': later.pk, 'report_evidence_id': other_report.pk}
        reader = get_user_model().objects.create_user('closed-delivery-reader')
        Grant.objects.bulk_create([Grant(user=reader, case=self.case, action=key) for key in ('case.read', 'delivery.read')])
        self.client.force_login(reader)
        url = reverse('closure_preparation', args=[self.case.pk, self.d.pk])
        checked = self.client.get(url)
        self.assertEqual(checked['Cache-Control'], 'no-store')
        self.assertContains(checked, '<h1>Closure recorded</h1>', html=True)
        self.assertContains(checked, '<summary><strong>Retrospective</strong> · Recorded evidence</summary>', html=True)
        self.assertNotContains(checked, 'Not yet selected')
        self.assertNotContains(checked, 'Start controlled closure work')
        self.assertNotContains(checked, 'Ask the agent to investigate')
        self.assertNotContains(checked, 'Select recorded inputs')
        self.assertNotContains(checked, 'PM performance summary, risks and resolutions')
        self.assertNotContains(checked, 'Later private retrospective summary')
        report = checked.context['report']
        self.assertEqual(report['recorded_closure_id'], closed.pk)
        self.assertFalse(report['ready_to_prepare'])
        self.assertNotIn('selected', report)
        checks = {row['key']: row for row in report['checks']}
        self.assertEqual(checks['retrospective']['references'], [original.pk])
        self.assertEqual(checks['report']['references'], [self.selected['report_evidence_id']])
        self.assertEqual(checks['finance']['references'], [closed.snapshot['finance_confirmation_id']])
        self.assertEqual(checks['handover']['references'], closed.snapshot['handover_ids'])
        self.assertEqual(self.client.get(url, unrelated).context['report']['checks'], report['checks'])

        self.client.force_login(self.actor)
        before = (rev(self.case), AgentRun.objects.filter(case=self.case).count(), self.d.records.count())
        response = self.client.post(url, dict(unrelated, action='investigate', revision=before[0]))
        self.assertEqual(response.context['report']['checks'], report['checks'])
        self.assertEqual((rev(self.case), AgentRun.objects.filter(case=self.case).count(), self.d.records.count()), before)

        Grant.objects.filter(user=self.actor, case=self.case, action='meeting.record').update(active=False)
        self.client.force_login(reader)
        limited = self.client.get(url)
        self.assertContains(limited, '<summary><strong>Retrospective</strong> · Recorded source unavailable</summary>', html=True)
        independent = {row['key']: row for row in limited.context['report']['checks']}
        self.assertEqual(independent['retrospective']['references'], [])
        self.assertEqual(independent['report']['references'], [self.selected['report_evidence_id']])
        self.assertEqual(limited.context['report']['recorded_closure_id'], closed.pk)
        Grant.objects.filter(user=reader, case=self.case, action='delivery.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_ui_agent_and_direct_posts_recheck_current_authority_and_preserve_business_records(self):
        self.client.force_login(self.actor);url=reverse('closure_preparation',args=[self.case.pk,self.d.pk])
        page=self.client.get(url);self.assertContains(page,'Prepare for closure');self.assertEqual(page['Cache-Control'],'no-store')
        self.assertContains(page,'Required outputs');self.assertContains(page,'WAT')
        self.assertEqual(page.context['checked_at'].isoformat(),page.context['report']['as_of'])
        self.assertNotContains(page,'type="hidden" name="retrospective_id"')
        self.assertContains(page,'name="action" value="investigate"')
        self.assertEqual(self.client.get(reverse('closure_preparation',args=[self.case.pk,9223372036854775807])).status_code,404)
        self.assertContains(page,'Not yet selected');self.assertContains(page,'Ask the agent to investigate')
        self.assertNotContains(page,'PM performance summary, risks and resolutions')
        before=DeliveryRecord.objects.filter(dossier=self.d).count()
        post={'action':'investigate','revision':rev(self.case),**self.selected}
        response=self.client.post(url,post);self.assertEqual(response.status_code,302)
        self.assertTrue(AgentRun.objects.get(case=self.case).result['closure_requirements']['ready_to_prepare'])
        self.assertEqual(DeliveryRecord.objects.filter(dossier=self.d).count(),before)
        private=add_evidence(self.actor,self.case.pk,'agent_private_closure','PRIVATE RAW INPUT','synthetic:private')
        invalid=dict(post,report_evidence_id=private.pk,revision=rev(self.case))
        response=self.client.post(url,invalid);self.assertEqual(response.status_code,200);self.assertNotContains(response,'PRIVATE RAW INPUT')
        self.assertEqual(AgentRun.objects.filter(case=self.case).count(),1)
        Grant.objects.filter(user=self.actor,case=self.case,action='agent.delivery').update(active=False)
        self.assertNotContains(self.client.get(url),'Ask the agent to investigate')
        self.assertEqual(self.client.post(url,post).status_code,403);self.assertEqual(AgentRun.objects.filter(case=self.case).count(),1)
        response=self.client.post(url,dict(post,action='check'))
        self.assertEqual(response.status_code,302);self.assertIn('retrospective_id='+str(self.selected['retrospective_id']),response.url)
        self.assertEqual(AgentRun.objects.filter(case=self.case).count(),1)
        Grant.objects.filter(user=self.actor,case=self.case,action='delivery.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code,403)
