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
    if binding.manifest.get('source_mode')=='leadership_selected_facts/v1':
        from .leadership_reporting import current_manifest
        return current_manifest(binding)
    report=binding.report
    adapter=LocalPMOReportingAdapter()
    read=adapter.read_client_facts if binding.manifest.get('source_mode')=='weekly_client_facts/v1' else adapter.read
    snapshot=read(report.case,report.start_at,report.end_at,timezone.now())
    if binding.manifest.get('source_mode')=='weekly_client_facts/v1':
        content,_=client_content(report.case,snapshot,binding.manifest.get('client_content',{}).get('id'))
        return client_manifest(snapshot,content)
    return snapshot['manifest']


def action_line(item):
    state=item.current
    owner=f'Owner reference #{state.owner_id}' if state.owner_id else 'Owner unassigned'
    due=state.due_at.isoformat() if state.due_at else 'Deadline unknown'
    return f'{item.reference}: {state.description} · {state.status} · {owner} · {due}'


CLIENT_SCOPE_COVERAGE = 'Unknown: approved project scope is not established by this selected local weekly PMO fact set. This report does not amend scope.'
CLIENT_DEPENDENCY_COVERAGE = 'Unknown: project dependencies are not established by this selected weekly fact and narrative set. Obtain current dependency evidence; no absence of dependencies is implied.'


def fields_for(template,audience,values,evidence_id):
    allowed=template.definition['audience_fields'].get(audience)
    if not allowed:raise ValidationError('Template does not support the intended audience')
    from apps.documents.pmo_sections import complete_native_client_sections
    fields = {key:{'text':values[key],'evidence_ids':[evidence_id]} for key in allowed if key in values}
    return complete_native_client_sections(fields, audience, [evidence_id])


@transaction.atomic
def draft_minutes(actor,case_id,meeting_id,template_id,audience,expected):
    case=lock_case(actor,case_id,'minutes.draft',expected)
    meeting=Meeting.objects.select_related('current').filter(case=case,pk=meeting_id).first()
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type='minutes').first()
    if not meeting or not template:raise ValidationError('Choose a case meeting and controlled minutes template')
    current=meeting.current;actions=list(meeting_actions(meeting))
    decisions='\n'.join(d['text']+(f" [change evidence #{d['change_evidence_id']}]" if d.get('change_evidence_id') else '') for d in current.decisions) or 'No decisions recorded'
    lines='\n'.join(action_line(item) for item in actions) or 'No action commitments recorded'
    values={'executive_summary':'Purpose: '+current.purpose+'\n'+current.summary,'scope':'Meeting statements and change references do not amend the signed baseline.',
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
def draft_period_report(actor,case_id,kind,start_at,end_at,template_id,audience,expected,policies=None,reuse_existing=False,*,client_safe=False,client_content_id=None):
    case=lock_case(actor,case_id,'report.draft',expected)
    start_at,end_at=aware(start_at,'Period start'),aware(end_at,'Period end')
    if kind not in REPORT_KINDS or end_at<=start_at or (end_at-start_at).days>366:
        raise ValidationError('Choose a known reporting purpose and a positive period of at most 366 days')
    if kind=='weekly_client' and audience!='client' or kind=='internal_tuesday' and audience!='internal':
        raise ValidationError('Weekly client and internal PMO purposes keep their prescribed audiences')
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type='status_report').first()
    if not template:raise ValidationError('Choose a case status-report template')
    if type(client_safe) is not bool:raise ValidationError('Explicit client projection mode required')
    if client_safe:
        if reuse_existing:raise ValidationError('Client-safe reports need explicit content-bound revision; scheduled reuse is preparation-only')
        required={'executive_summary','scope','status','risks','timeline','dependencies','next_steps'}
        if kind!='weekly_client' or audience!='client' or not required.issubset(template.definition['required_fields']) or set(template.definition['audience_fields'].get('client',[]))!=required:
            raise ValidationError('Weekly client projection requires summary, scope, progress, risks, milestones/timeline, dependencies and next steps')
    as_of=timezone.now()
    adapter=LocalPMOReportingAdapter()
    snapshot=(adapter.read_client_facts if client_safe else adapter.read)(case,start_at,end_at,as_of)
    # Legacy/manual and scheduled drafts copy the same protected source domains.
    # Authorize before report creation, snapshot evidence, or scheduled reuse.
    report_source_access(actor,case,snapshot['manifest'])
    if client_safe:
        content,client_sections=client_content(case,snapshot,client_content_id)
        snapshot['manifest']=client_manifest(snapshot,content)
    report,created=PeriodReport.objects.get_or_create(case=case,kind=kind,start_at=start_at,end_at=end_at,audience=audience)
    if reuse_existing and report.document_id:
        binding=MinutesReportBinding.objects.filter(report=report,version_id=report.document.current_id).first()
        if binding and binding.manifest==snapshot['manifest'] and binding.version.template_id==template.pk:return binding
        raise ValidationError('Existing report period needs a human-requested revision before scheduled reuse')
    if not client_safe:
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
        from .change_impacts import report_timeline
        change_timeline=report_timeline(snapshot['change_timeline'])
        values['timeline']=change_timeline or 'No recorded approved change timeline amendments'
        if change_timeline:values['status']+='\nRecorded change timeline amendments:\n'+change_timeline
        values['scope']='\n'.join(f'{c.reference} v{c.current.number}: {c.current.category}; {c.current.module}; {c.current.description}' for c in snapshot['changes']) or 'No recorded change requests'
        values['issue_resolution']='\n'.join(f'{i.reference}: fix evidence #{i.current.fix_id or "Unknown"}; root cause #{i.current.root_cause_id or "Unknown"}' for i in snapshot['issues']) or 'No local resolution records'
    if client_safe:
        values=client_safe_values(snapshot,start_at,end_at,as_of)
        values.update({key:section['text'] for key,section in client_sections.items()})
    evidence=add_evidence(actor,case.pk,'ops_client_report_projection' if client_safe else 'report_snapshot','\n'.join(k+': '+v for k,v in values.items()),('psl:weekly-client-projection:' if client_safe else 'psl:period-report:')+str(report.pk),expected)
    case.refresh_from_db()
    title='Report: '+kind+' · '+start_at.isoformat()+' / '+end_at.isoformat()
    if client_safe and report.document_id:title=report.document.title
    projected_values = values
    if audience == 'client' and not client_safe:
        # P52 makes scope/risks/dependencies mandatory, but must not expose the
        # legacy internal change descriptions or action references merely by
        # adding headings to a previously narrow client template. Retain the
        # existing explicit approved change timeline, not raw scope prose.
        safe = client_safe_values(snapshot, start_at, end_at, as_of)
        projected_values = dict(values, scope=CLIENT_SCOPE_COVERAGE,
                                dependencies=CLIENT_DEPENDENCY_COVERAGE, risks=safe['risks'])
    fields=fields_for(template,audience,projected_values,evidence.pk)
    if client_safe:
        # Inventory and narrative citations were authorized above. Only this freshly
        # generated projection crosses the private storage primitive, never caller IDs.
        from apps.documents.controlled import _create_version
        version=_create_version(actor,case.pk,template.pk,title,audience,fields,case.revision,report.document_id,authorized_restricted_source_ids=[evidence.pk])
    else:version=create_version(actor,case.pk,template.pk,title,audience,fields,case.revision,report.document_id)
    if created:report.document=version.document;report.save(update_fields=['document'])
    binding=MinutesReportBinding.objects.create(version=version,report=report,manifest=snapshot['manifest'],policies=policies or {})
    event(actor,case,'report.drafted',report=report.pk,version=version.pk,binding=binding.pk,policies=policies or {})
    return binding


def client_safe_values(snapshot,start_at,end_at,as_of):
    """Bounded local facts only: raw notes, identities and references never enter this projection."""
    actions=snapshot['actions'];opened=[a for a in actions if a.current.status not in ['completed','cancelled']]
    overdue=sum(snapshot['timings'][a.pk]=='OVERDUE' for a in opened)
    unassigned=sum(a.current.owner_id is None for a in opened);undated=sum(a.current.due_at is None for a in opened)
    issues=snapshot['issues'];unresolved=sum(i.current.status in ['Open','In Progress'] for i in issues)
    return {
        'scope': CLIENT_SCOPE_COVERAGE,
        'dependencies': CLIENT_DEPENDENCY_COVERAGE,
        'executive_summary':f'Weekly client report for {start_at.isoformat()} to {end_at.isoformat()}. Prepared as of {as_of.isoformat()}. This is partial local coverage of selected meeting, action, milestone, issue and change facts only. Delivery/RFP/escalation histories, change-approval timelines, Engineering, Security, Finance and external-system reporting are not included.',
        'status':f'Progress evidence: {len(snapshot["milestones"])} milestone completions recorded during this period. Current local records contain {len(opened)} open commitments and {unresolved} unresolved issues. These counts do not establish overall project completion or delivery health.',
        'risks':f'Attention in the recorded commitment set: {overdue} explicit deadlines are overdue at preparation, {unassigned} owners are unassigned and {undated} deadlines are unknown. Project risks and unprovided source updates remain unassessed; this is not a complete risk assessment.',
        'timeline':f'Milestones: {len(snapshot["milestones"])} completion records fall within the selected period. Future milestone dates and unprovided progress are not inferred from these records.',
        'next_steps':'Confirm outstanding source updates and follow up the recorded commitments and unresolved issues with their accountable owners. No new delivery date, scope commitment, approval or resolution is implied.'}


def client_content(case,snapshot,content_id):
    """Human-supplied client prose is evidence, never review or distribution authority."""
    import json
    from apps.core.models import Evidence
    from apps.core.evidence_access import forecast_private
    from apps.documents.contracts import validate
    content=Evidence.objects.filter(case=case,pk=content_id,kind='agent_private_report_content').first()
    if not content or forecast_private(content):raise ValidationError('Select human-supplied, cited client content for progress, risks, milestones and next steps')
    try:data=json.loads(content.body)
    except (ValueError,TypeError):raise ValidationError('Client report content must be a typed source document') from None
    section={'type':'object','properties':{'text':{'type':'string','minLength':1,'maxLength':10000},'evidence_ids':{'type':'array','minItems':1,'maxItems':18,'uniqueItems':True,'items':{'type':'integer','minimum':1}}},'required':['text','evidence_ids'],'additionalProperties':False}
    keys=['status','risks','timeline','next_steps']
    validate({'type':'object','properties':{'protocol':{'const':'pmo-weekly-client-content/v1'},'sections':{'type':'object','properties':{k:section for k in keys},'required':keys,'additionalProperties':False}},'required':['protocol','sections'],'additionalProperties':False},data)
    permitted=client_citation_ids(case,snapshot)
    for key,value in data['sections'].items():
        if not value['text'].strip() or value['text'].strip().casefold() in ['tbd','todo','unknown','n/a','pending']:
            raise ValidationError('Resolve the '+key+' placeholder or explicitly explain the missing source facts')
        if any(type(pk) is not int or pk not in permitted for pk in value['evidence_ids']):raise ValidationError('Every narrative citation must identify permitted evidence in the selected native meeting/action/milestone/issue/change inventory')
    return content,data['sections']


def report_source_access(actor,case,manifest):
    """Historical read permission is independent of whether the source is still current."""
    from apps.identity.services import require
    require(actor,case,'report.read')
    from .incident_reporting import selected_access
    for pin in manifest.get('incident_claims', []): selected_access(actor,case,pin)
    checks=[(manifest.get('meetings') or manifest.get('actions') or manifest.get('milestones'),'meeting.read'),
        (manifest.get('issues') or any(manifest.get('escalation_history',{}).values()),'issue.read'),
        (manifest.get('changes') or any(manifest.get('change_history',{}).values()) or manifest.get('normal_change_timeline',{}).get('rows'),'change.read'),
        (manifest.get('gates') or any(manifest.get('delivery_history',{}).values()),'delivery.read'),
        (bool(manifest.get('rfp_history')),'rfp.read')]
    for present,action in checks:
        if present:require(actor,case,action)


def client_manifest(snapshot,content):
    return dict(snapshot['manifest'],client_content={'id':content.pk,'sha256':content.sha256} if content else None)


def client_citation_ids(case,snapshot):
    """Exact native facts only. P56 ownership does not waive overlapping private domains."""
    from apps.core.models import Evidence
    from apps.core.evidence_access import restricted,forecast_private
    changes={c.current.evidence_id for c in snapshot['changes']}
    ids={m.current.evidence_id for m in snapshot['meetings']}|{a.current.evidence_id for a in snapshot['actions']}|{m.evidence_id for m in snapshot['milestones']}|{i.current.evidence_id for i in snapshot['issues']}|changes
    return {e.pk for e in Evidence.objects.filter(case=case,pk__in=ids)
        if not restricted(e) or e.pk in changes and e.source=='psl:p56-confirmed-request/v1' and not forecast_private(e)}
