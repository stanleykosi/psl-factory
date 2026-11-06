from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case, event, bump, add_evidence
from apps.documents.models import Template
from apps.documents.controlled import create_version
from adapters.pmo_reporting import LocalPMOReportingAdapter
from .models import Meeting, ActionItem, PeriodReport, MinutesReportBinding
from .clocks import aware, REPORT_KINDS
from .meetings import meeting_actions


def meeting_manifest(meeting):
    return {'meeting_version':meeting.current_id,'actions':[[a.pk,a.current_id] for a in meeting_actions(meeting)]}


def binding_manifest(binding):
    if binding.meeting_id:return meeting_manifest(binding.meeting)
    report=binding.report
    return LocalPMOReportingAdapter().read(report.case,report.start_at,report.end_at,timezone.now())['manifest']


def action_line(item):
    state=item.current
    owner=f'Owner reference #{state.owner_id}' if state.owner_id else 'Owner unassigned'
    due=state.due_at.isoformat() if state.due_at else 'Deadline unknown'
    return f'{item.reference}: {state.description} · {state.status} · {owner} · {due}'


def fields_for(template,audience,values,evidence_id):
    allowed=template.definition['audience_fields'].get(audience)
    if not allowed:raise ValidationError('Template does not support the intended audience')
    return {key:{'text':values[key],'evidence_ids':[evidence_id]} for key in allowed if key in values}


@transaction.atomic
def draft_minutes(actor,case_id,meeting_id,template_id,audience,expected):
    case=lock_case(actor,case_id,'minutes.draft',expected)
    meeting=Meeting.objects.select_related('current').filter(case=case,pk=meeting_id).first()
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type='minutes').first()
    if not meeting or not template:raise ValidationError('Choose a case meeting and controlled minutes template')
    current=meeting.current;actions=list(meeting_actions(meeting))
    decisions='\n'.join(d['text']+(f" [change evidence #{d['change_evidence_id']}]" if d.get('change_evidence_id') else '') for d in current.decisions) or 'No decisions recorded'
    lines='\n'.join(action_line(item) for item in actions) or 'No action commitments recorded'
    values={'executive_summary':current.summary,'scope':'Meeting statements and change references do not amend the signed baseline.',
        'status':f'Meeting {meeting.reference}, revision {current.number}, at {current.occurred_at.isoformat()}',
        'participants':', '.join(f'Participant reference #{pk}' for pk in current.participant_ids) or 'Participants not yet mapped',
        'decisions':decisions,'actions':lines,'owners':'\n'.join(f'{a.reference}: '+(f'Owner reference #{a.current.owner_id}' if a.current.owner_id else 'Unassigned') for a in actions) or 'No action owners recorded',
        'deadlines':'\n'.join(f'{a.reference}: '+(a.current.due_at.isoformat() if a.current.due_at else 'Unknown') for a in actions) or 'No action deadlines recorded'}
    source_text='Formal minutes source: '+str(current.evidence_id)+'\n'+'\n'.join(key+': '+value for key,value in values.items())
    evidence=add_evidence(actor,case.pk,'minutes_snapshot',source_text,'psl:minutes:'+str(meeting.pk),expected)
    old=MinutesReportBinding.objects.filter(meeting=meeting,version__audience=audience).order_by('-pk').select_related('version').first()
    title='Minutes: '+meeting.reference
    case.refresh_from_db()
    version=create_version(actor,case.pk,template.pk,title,audience,fields_for(template,audience,values,evidence.pk),case.revision,
        old.version.document_id if old and old.version.audience==audience else None)
    binding=MinutesReportBinding.objects.create(version=version,meeting=meeting,manifest=meeting_manifest(meeting))
    event(actor,case,'minutes.drafted',meeting=meeting.pk,version=version.pk,binding=binding.pk,scope_changed=False)
    return binding


@transaction.atomic
def draft_period_report(actor,case_id,kind,start_at,end_at,template_id,audience,expected,policies=None,reuse_existing=False):
    case=lock_case(actor,case_id,'report.draft',expected)
    start_at,end_at=aware(start_at,'Period start'),aware(end_at,'Period end')
    if kind not in REPORT_KINDS or end_at<=start_at or (end_at-start_at).days>366:
        raise ValidationError('Choose a known reporting purpose and a positive period of at most 366 days')
    if kind=='weekly_client' and audience!='client' or kind=='internal_tuesday' and audience!='internal':
        raise ValidationError('Weekly client and internal PMO purposes keep their prescribed audiences')
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type='status_report').first()
    if not template:raise ValidationError('Choose a case status-report template')
    as_of=timezone.now()
    snapshot=LocalPMOReportingAdapter().read(case,start_at,end_at,as_of)
    report,created=PeriodReport.objects.get_or_create(case=case,kind=kind,start_at=start_at,end_at=end_at,audience=audience)
    if reuse_existing and report.document_id:
        binding=MinutesReportBinding.objects.filter(report=report,version_id=report.document.current_id).first()
        if binding and binding.manifest==snapshot['manifest'] and binding.version.template_id==template.pk:return binding
        raise ValidationError('Existing report period needs a human-requested revision before scheduled reuse')
    actions=snapshot['actions'];open_actions=[a for a in actions if a.current.status not in ['completed','cancelled']]
    values={'executive_summary':f'{kind.replace("_"," ").capitalize()} · {start_at.isoformat()} to {end_at.isoformat()} · Snapshot as of {as_of.isoformat()}. Coverage is local recorded PMO evidence; external systems and financial reporting are not represented as complete.',
        'status':f'{len(snapshot["meetings"])} meetings in the selected period; {len(snapshot["milestones"])} PMO milestones; {len(open_actions)} open commitments across this case.',
        'actions':'\n'.join(action_line(a) for a in actions) or 'No action commitments recorded',
        'owners':'\n'.join(f'{a.reference}: '+(f'Owner reference #{a.current.owner_id}' if a.current.owner_id else 'Unassigned') for a in open_actions) or 'No open commitments',
        'deadlines':'\n'.join(f'{a.reference}: '+(a.current.due_at.isoformat() if a.current.due_at else 'Unknown') for a in open_actions) or 'No open commitments',
        'risks':'\n'.join(f'{a.reference}: deadline overdue at snapshot' for a in open_actions if snapshot['timings'][a.pk]=='OVERDUE') or 'No overdue explicit deadlines in the captured action set; this is not a complete risk assessment.',
        'next_steps':'Follow up on recorded commitments and collect missing owner/deadline evidence. Publication remains a human-controlled action.',
        'decisions':'\n'.join(d['text'] for m in snapshot['meetings'] for d in m.current.decisions) or 'No meeting decisions recorded in the selected period'}
    values['status']+=f' {len(snapshot["issues"])} recorded issues; {len(snapshot["changes"])} recorded changes.'
    values['status']+=f' {len(snapshot["rfp_history"].get("rfpresponse",[]))} RFP responses; {len(snapshot["rfp_history"].get("rfpsubmission",[]))} actual submissions.'
    values['status']+=f' {len(snapshot["delivery_history"]["dossiers"])} delivery dossiers; {len(snapshot["delivery_history"]["records"])} delivery/release/closure evidence records. Counts do not establish production readiness.'
    values['status']+=f' {len(snapshot["escalation_history"]["requests"])} escalation/de-escalation requests; {len(snapshot["escalation_history"]["receipts"])} actual recipient receipts.'
    values['issue_status']='\n'.join(f'{i.reference}: {i.current.status} / {i.current.severity or "Unknown severity"}' for i in snapshot['issues']) or 'No local issue records'
    values['issue_impact']='\n'.join(f'{i.reference}: {i.current.next_action}' for i in snapshot['issues']) or 'No recorded issue next actions'
    values['scope']='\n'.join(f'{c.reference} v{c.current.number}: {c.current.category}; {c.current.module}; {c.current.description}' for c in snapshot['changes']) or 'No recorded change requests'
    values['issue_resolution']='\n'.join(f'{i.reference}: fix evidence #{i.current.fix_id or "Unknown"}; root cause #{i.current.root_cause_id or "Unknown"}' for i in snapshot['issues']) or 'No local resolution records'
    evidence=add_evidence(actor,case.pk,'report_snapshot','\n'.join(k+': '+v for k,v in values.items()),'psl:period-report:'+str(report.pk),expected)
    case.refresh_from_db()
    title='Report: '+kind+' · '+start_at.isoformat()+' / '+end_at.isoformat()
    version=create_version(actor,case.pk,template.pk,title,audience,fields_for(template,audience,values,evidence.pk),case.revision,report.document_id)
    if created:report.document=version.document;report.save(update_fields=['document'])
    binding=MinutesReportBinding.objects.create(version=version,report=report,manifest=snapshot['manifest'],policies=policies or {})
    event(actor,case,'report.drafted',report=report.pk,version=version.pk,binding=binding.pk,policies=policies or {})
    return binding
