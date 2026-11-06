"""Independent native P38/P39 prerequisites, with actual Finance attestations retained."""
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.identity.models import Grant
from apps.agents.models import AgentRun
from apps.agents.delivery import investigate_delivery
from apps.pmo.delivery_closure import closure_inputs,closure_requirements,confirm_finance
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.models import DeliveryRecord,DeliveryDocumentBinding,MeetingVersion,Milestone
from apps.pmo.meetings import record_meeting
from apps.pmo.services import complete_milestone
from apps.workflows.services import run_once
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
        old=self.checks(self.selected)['finance']['references']
        m=complete_milestone(self.actor,self.case.pk,'Additional completed milestone',self.e['completion'].pk,rev(self.case));self.assertTrue(run_once())
        checks=self.checks();self.assertEqual(checks['finance']['status'],'held');self.assertEqual(checks['archive']['status'],'current')
        self.assertEqual(checks['retrospective']['status'],'unknown')
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
        from apps.core.services import add_evidence
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
        from apps.core.services import add_evidence
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
