"""Synthetic populated actual-P43 history; callable in the exact predecessor runtime."""
import json
from pathlib import Path
from django.utils import timezone


def seed_predecessor(check):
    from tests.test_factory_planning import setup
    from tests.test_engagement_intake import activate
    from tests.minutes_upgrade_helpers import seed_predecessor as seed_pmo
    from tests.helpers import rev
    from apps.pmo import engagement,planning
    from apps.policy.engagement_validators import ASSIGN,REGISTER
    from apps.workflows import factory,factory_minutes as minutes
    from apps.documents.models import PublicationReceipt
    from apps.documents.controlled import preflight
    f=setup();actor,case=f['a'],f['c'];capture=engagement.latest(case,'capture')
    values=json.loads(Path('fixtures/engagement-intake.json').read_text())
    activate(actor,case,ASSIGN,values['assignment'],f['e']['policy_decision'])
    assignment=engagement.assign(actor,case.pk,actor.pk,'PMO Lead',capture.evidence_id,'UPGRADE-PM')
    activate(actor,case,REGISTER,values['registration'],f['e']['policy_decision'])
    engagement.register(actor,case.pk,'SYN-OLD-UPGRADE','PMO Lead',capture.evidence_id,f['e']['plan'].pk,'UPGRADE-OLD-ID')
    registration=engagement.register(actor,case.pk,'SYN-CURRENT-UPGRADE','PMO Lead',capture.evidence_id,f['e']['plan'].pk,'UPGRADE-CURRENT-ID')
    exported=engagement.export_registration(actor,case.pk,'UPGRADE-EXPORT')
    factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db();check.assertEqual(f['work'].status,'waiting')
    p=seed_pmo(check);a,c,w,version,notes,owner=(p[k] for k in ['actor','case','work','revised','notes','owner'])
    config={'definition':minutes.DEFINITION,'max_steps':60,'max_tokens':50000,'tokens_per_call':100,'max_children':100,'max_depth':3,'lease_seconds':30,'max_age_seconds':86400,'required_evidence_kinds':[minutes.KIND,'meeting_notes'],'information_resolver_id':None,'executor_id':a.pk,'review_role':None,'provider':'synthetic_factory_v1','enabled':True,'extraction_provider':'synthetic_meeting_v1'}
    activate(a,c,'OPS.factory_minutes_execution',config,owner)
    selection={'protocol':minutes.PROTOCOL,'meeting_version_id':version.pk,'evidence_id':notes.pk,'template_id':p['mt'].pk,'audience':'internal','publish':False}
    current=minutes.start(a,c.pk,'UPGRADE-P43','UPGRADE-MEETING',selection,rev(c))
    fields={'kind':'status','occurred_at':version.occurred_at.isoformat(),'purpose':version.purpose,'summary':version.summary,'participant_ids':[a.pk],'decisions':[dict(d,change_evidence_id=None) for d in version.decisions],'actions':[],'existing_action_ids':[p['action'].pk,p['unknown'].pk],'note':'Actual human predecessor commitments retained without inventing owners or dates.'}
    minutes.confirm(a,current.pk,current.revision,rev(c),fields,None);factory.run_until_wait(current.pk);current.refresh_from_db();check.assertEqual(current.status,'verified',current.finding)
    for value in p.values():
        if hasattr(value,'refresh_from_db'):value.refresh_from_db()
    pending_findings=preflight(p['pending'].version)
    check.assertIn('Meeting/action/report source snapshot changed; draft and review a new revision',pending_findings)
    record={'predecessor':'3ac8056','actor':actor.pk,'case':str(case.pk),'capture':capture.pk,'assignment':assignment.pk,'registration':registration.pk,'plan':f['e']['plan'].pk,'policy_evidence':f['e']['policy_decision'].pk,'packet':f['packet'].pk,'packet_sha256':f['packet'].sha256,'planning_work':f['work'].pk,'planning_actor':f['work'].actor_id,'planning_budget':f['work'].budget_used,'export':exported.pk,'identifiers':list(engagement.Identifier.objects.filter(case=case).order_by('pk').values_list('pk',flat=True)),
        'p44_work':w.pk,'p44_proof':p['proof'],'p44_budget':w.budget_used,'p43_work':current.pk,'p43_proof':minutes.verify(current,a),'p43_budget':current.budget_used,'pending_publication':p['pending'].pk,'pending_findings':pending_findings,'receipt_ids':list(PublicationReceipt.objects.order_by('pk').values_list('pk',flat=True)),
        'action':p['action'].pk,'action_state':p['action'].current_id,'unknown_action':p['unknown'].pk,'unknown_state':p['unknown'].current_id}
    return record


def reverify(record):
    from apps.workflows import factory_minutes,factory_escalation
    from apps.workflows.models import FactoryWork
    from apps.pmo import engagement,planning
    from apps.pmo.models import ActionItem
    from apps.core.models import Case,Evidence
    from apps.documents.models import Publication,PublicationReceipt
    from apps.documents.controlled import preflight
    from adapters.publications import InternalPublicationAdapter
    case=Case.objects.get(pk=record['case']);work=FactoryWork.objects.get(pk=record['planning_work'])
    assert engagement.current_assignment(case).pk==record['assignment'];assert engagement.current_registration(case).pk==record['registration']
    assert list(engagement.Identifier.objects.filter(case=case).order_by('pk').values_list('pk',flat=True))==record['identifiers']
    packet,_=planning.packet(case);assert packet.pk==record['packet'] and packet.sha256==record['packet_sha256']
    assert work.actor_id==record['planning_actor'] and work.budget_used==record['planning_budget'] and work.source_head_id==packet.pk
    for key,flow in [('p43',factory_minutes),('p44',factory_escalation)]:
        w=FactoryWork.objects.get(pk=record[key+'_work']);assert flow.verify(w)==record[key+'_proof'];assert w.budget_used==record[key+'_budget']
    assert list(PublicationReceipt.objects.order_by('pk').values_list('pk',flat=True))==record['receipt_ids']
    p=Publication.objects.get(pk=record['pending_publication']);assert preflight(p.version)==record['pending_findings'];assert InternalPublicationAdapter().lookup(p)==str(p.pk);assert p.job.status=='unknown'
    action=ActionItem.objects.get(pk=record['action']);unknown=ActionItem.objects.get(pk=record['unknown_action'])
    assert action.current_id==record['action_state'] and action.current.status=='completed'
    assert unknown.current_id==record['unknown_state'] and unknown.current.owner_id is None and unknown.current.due_at is None
    assert Evidence.objects.filter(pk=record['export'],case=case).exists()
