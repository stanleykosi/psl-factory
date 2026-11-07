"""Native synthetic P44/minutes history reused by actual upgrade proofs."""
import json
from pathlib import Path
from django.utils import timezone

def seed_predecessor(self):
    from tests.test_escalations import fixture,profile
    from tests.helpers import rev
    from tests.document_helpers import artifact
    from tests.meeting_helpers import MINUTES_DEFINITION
    from apps.core.services import add_evidence
    from apps.documents.controlled import register_template,request_review,review_version,reserve_publication
    from apps.documents.delivery import run_publication_once
    from apps.documents.models import PublicationReceipt,PublicationJob
    from apps.policy.operator_drafts import draft_operator_policy
    from apps.policy.services import transition
    from apps.pmo import escalations as native
    from apps.pmo.meetings import record_meeting,create_action,change_action
    from apps.pmo.reporting import draft_minutes
    from apps.workflows import factory,factory_escalation as escalation
    from adapters.publications import PublicationTimeoutAfterAccept,InternalPublicationAdapter
    actor,case,owner,evidence,template,recipient,issue=fixture()
    mt=register_template(actor,case.pk,'Upgrade native minutes',MINUTES_DEFINITION,owner.pk,rev(case))
    artifact(actor,case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[template.pk,mt.pk],'repository':'internal-versioned','retention_days':30},owner)
    value=json.loads(Path('fixtures/factory-escalation.json').read_text());value.pop('classification');value.update(preparer_id=actor.pk,executor_id=actor.pk)
    policy=draft_operator_policy(actor,case.pk,'OPS.factory_escalation_execution',value,owner.pk,timezone.now());transition(actor,policy.pk,'validated');transition(actor,policy.pk,'active')
    captured=profile(actor,case,issue,evidence,'client_dependent',True)
    request=native.request_escalation(actor,case.pk,captured.pk,'escalate','Client',evidence.pk,'Actual synthetic predecessor communication',rev(case))
    work=escalation.start(actor,case.pk,'UPGRADE-P44',request.pk,template.pk,'Native predecessor handoff',rev(case))
    factory.run_until_wait(work.pk);work.refresh_from_db();escalation.decide(actor,work.pk,work.revision,rev(case),request.pk,'Head of PMO','approve','Exact human client decision')
    factory.run_until_wait(work.pk);work.refresh_from_db();version=escalation.document(work)
    escalation.review(actor,work.pk,work.revision,rev(case),version.pk,'approve','Exact predecessor communication review')
    factory.run_until_wait(work.pk);work.refresh_from_db();self.assertEqual(work.status,'verified',work.finding);proof=escalation.verify(work)
    notes=add_evidence(actor,case.pk,'meeting_notes','Confirm the delivery plan.\nInvestigate the dependency.','synthetic:upgrade-notes')
    original=record_meeting(actor,case.pk,'UPGRADE-MEETING','status','2026-11-06T00:30:58.123456+02:00','Native meeting before upgrade','Human-confirmed predecessor summary',[actor.pk],[{'text':'Confirm the delivery plan.','evidence_id':notes.pk}],notes.pk,rev(case))
    action=create_action(actor,case.pk,'UPGRADE-ACTION','Investigate the dependency.',actor.pk,None,notes.pk,'Actual existing commitment',rev(case),original.meeting_id)
    unknown=create_action(actor,case.pk,'UPGRADE-UNKNOWN','Await actual owner and deadline',None,None,notes.pk,'Unknowns remain explicit',rev(case),original.meeting_id)
    first=draft_minutes(actor,case.pk,original.meeting_id,mt.pk,'client',rev(case));request_review(actor,case.pk,first.version_id,rev(case));review_version(actor,case.pk,first.version_id,'approve','Exact native minutes',rev(case))
    first_pub=reserve_publication(actor,case.pk,first.version_id,rev(case));run_publication_once(job_id=first_pub.job.pk)
    change_action(actor,case.pk,action.pk,'complete',notes.pk,'Actual owner completes native action',rev(case),1)
    revised=record_meeting(actor,case.pk,'UPGRADE-MEETING','status',original.occurred_at,'Native corrected purpose','Corrected actual attribution',[actor.pk],original.decisions,notes.pk,rev(case),original.meeting_id)
    second=draft_minutes(actor,case.pk,original.meeting_id,mt.pk,'client',rev(case));request_review(actor,case.pk,second.version_id,rev(case));review_version(actor,case.pk,second.version_id,'approve','Exact corrected native minutes',rev(case))
    pending=reserve_publication(actor,case.pk,second.version_id,rev(case));run_publication_once(PublicationTimeoutAfterAccept(),job_id=pending.job.pk)
    self.assertEqual(PublicationJob.objects.get(publication=pending).status,'unknown')
    return {'actor':actor, 'case':case, 'work':work, 'proof':proof, 'notes':notes, 'original':original, 'revised':revised, 'action':action, 'unknown':unknown, 'first':first, 'first_pub':first_pub, 'second':second, 'pending':pending, 'mt':mt, 'owner':owner}
