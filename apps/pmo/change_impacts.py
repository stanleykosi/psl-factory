"""Owner-authored Normal change impact contracts, not inferred business decisions.

P57: SOP 9.10.3. P59: SOP 9.10.5–9.10.8. Existing Standard and
Emergency routes retain their separate contracts. Empty legacy detail is unknown.
"""
import json
from django.core.exceptions import ValidationError, PermissionDenied
from apps.documents.controlled import baseline_manifest
from apps.documents.contracts import validate

OUTPUTS = ('discipline', 'timeline', 'cost_resource', 'risk', 'dependency')

def inventory(value):
    validate({'type':['array','null'],'maxItems':100,'uniqueItems':True,
              'items':{'type':'string','minLength':1,'maxLength':240}},value)
    if value is not None and any(not x.strip() for x in value):
        raise ValidationError('Scope items must be explicit nonblank owner identifiers')
    return value

def assessment_details(version, contributor, outputs, production_impact, scope_items):
    if outputs is None:return {}
    validate({'type':'object','properties':{k:{'type':['string','null'],'minLength':1,'maxLength':4000} for k in OUTPUTS},
              'required':list(OUTPUTS),'additionalProperties':False}, outputs)
    if any(isinstance(x,str) and not x.strip() for x in outputs.values()):
        raise ValidationError('Use an explicit owner statement or unknown, not blank impact')
    if production_impact is not None and type(production_impact) is not bool:
        raise ValidationError('Production impact must be true, false or unknown')
    if contributor!='Infra' and production_impact is not None:
        raise ValidationError('Infra owns production applicability')
    if contributor!='Engineering' and scope_items is not None:
        raise ValidationError('Engineering supplies the scope inventory for prescribed decisions')
    return {'outputs':outputs,'production_impact':production_impact,'scope_items':inventory(scope_items),
            'baseline':version.base_manifest}

def validate_assessments(version, latest):
    if not version.base_manifest.get('plan_id') or not version.base_manifest.get('costing_id'):
        raise ValidationError('Current plan and cost baseline references required')
    from apps.identity.services import require
    for team,a in latest.items():
        require(a.actor,version.change.case,'change.assess:'+team)
        d=a.impact_details
        if not d or d.get('baseline')!=version.base_manifest:
            raise ValidationError(team+' impact outputs and exact baseline references remain unknown')
        if any(d['outputs'].get(k) is None for k in OUTPUTS):
            raise ValidationError(team+' discipline/timeline/cost-resource/risk/dependency impact remains unknown')
    if latest['Infra'].impact_details['production_impact'] is None:
        raise ValidationError('Infra production deployment impact unknown; clarify applicability before P32 handoff')
    if not latest['Engineering'].impact_details['scope_items']:
        raise ValidationError('Engineering approved-scope inventory remains unknown; obtain owner clarification')

def authorized_details(auth):
    rows={a.contributor:a for a in auth.version.assessments.filter(pk__in=auth.assessment_ids).order_by('pk')}
    return rows

def timeline_text(auth):
    if auth.version.category!='Normal':return ''
    return '\n'.join(a.contributor+': '+a.impact_details['outputs']['timeline'] for a in authorized_details(auth).values())

def execution_details(actor,case,auth,kind,evidence,scope_items,dossier_id,candidate_id):
    if auth.version.category!='Normal':return {},evidence
    rows=authorized_details(auth)
    details={'assessment_ids':auth.assessment_ids,'baseline':baseline_manifest(case)}
    if kind=='plan_updated':
        from apps.core.services import add_evidence
        details.update(approved_timeline=timeline_text(auth),source_plan_id=evidence.pk)
        # The derived plan is an explicit amendment with the exact owner plan as its base.
        evidence=add_evidence(actor,case.pk,'plan',json.dumps({'source_plan_id':evidence.pk,
            'source_plan_sha256':evidence.sha256,'source_plan_text':evidence.body,'authorization_id':auth.pk,**details},sort_keys=True),'psl:approved-change-plan')
        case.refresh_from_db(fields=['revision'])
    if kind=='implemented':
        actual=inventory(scope_items);approved=rows['Engineering'].impact_details['scope_items']
        extra=sorted(set(actual or [])-set(approved))
        details.update(scope_items=actual,extra_scope=extra,scope_status='unknown' if actual is None else 'deviation' if extra else 'incomplete' if set(actual)!=set(approved) else 'within_approved_scope')
        production=rows['Infra'].impact_details['production_impact']
        details['production_impact']=production
        if any(value is not None and type(value) is not int for value in [candidate_id,dossier_id]):
            raise ValidationError('Exact implementation candidate identifier required')
        details['candidate_id']=candidate_id
        if production and candidate_id is not None:
            from .models import DeliveryCandidate
            if not DeliveryCandidate.objects.filter(case=case,pk=candidate_id).exists():
                raise ValidationError('Implementation candidate must belong to this case')
        if production and dossier_id:
            from .delivery import dossier_for,readiness_inputs
            dossier=dossier_for(case,dossier_id)
            if dossier.candidate_id!=candidate_id:
                raise ValidationError('P32 dossier must match the exact Engineering implementation candidate')
            details.update(dossier_id=dossier.pk,readiness=readiness_inputs(dossier))
        elif not production and (dossier_id or candidate_id):raise ValidationError('Do not attach production readiness to an owner-confirmed non-production change')
    return details,evidence

def deviation_hold(auth):
    if auth.version.category!='Normal':return
    if auth.execution.filter(impact_details__scope_status='deviation').exists():
        raise ValidationError('Extra unapproved scope recorded; return to assessment and authority in a new CR revision')

def validate_execution(auth,latest):
    if auth.version.category!='Normal':return
    deviation_hold(auth)
    implementation=latest['implemented'].impact_details
    if implementation.get('scope_status')!='within_approved_scope':
        raise ValidationError('Implementation scope unknown or beyond approved CR; return to assessment and authority, not retrospective normalization')
    for e in latest.values():
        if e.impact_details.get('assessment_ids')!=auth.assessment_ids:
            raise ValidationError('Execution must reference the exact approved impact outputs')
    if implementation.get('production_impact'):
        if not implementation.get('dossier_id'):
            raise ValidationError('Production change awaits exact P32 delivery dossier/readiness; ordinary approval is not release authority')
        from .delivery import dossier_for,readiness_inputs
        d=dossier_for(auth.version.change.case,implementation['dossier_id'])
        if d.candidate_id!=implementation.get('candidate_id'):
            raise ValidationError('P32 dossier must match the exact Engineering implementation candidate')
        if readiness_inputs(d)!=implementation['readiness']:
            raise ValidationError('P32 readiness changed; reconcile exact production evidence')
    if any(a.timeline_impact for a in authorized_details(auth).values()):
        from .models import MinutesReportBinding
        plan=latest['plan_updated']
        reports=MinutesReportBinding.objects.filter(report__case=auth.version.change.case,report__kind='weekly_client')
        current=next((r for r in timeline_snapshot(auth.version.change.case)['rows'] if r['authorization_id']==auth.pk),None)
        if not any(weekly_report_matches(auth,plan,r,current) for r in reports.select_related('version__document')):
            raise ValidationError('Approved timeline amendment must appear in a current weekly client report')

def weekly_report_matches(auth,plan,report,current):
    pinned=next((r for r in report.manifest.get('normal_change_timeline',{}).get('rows',[]) if r['authorization_id']==auth.pk),None)
    text='\n'.join(s['text'] for s in report.version.payload['sections'])
    return bool(current and current['status']=='current approved' and pinned==current
        and report.version.document.current_id==report.version_id
        and plan.pk in report.manifest.get('change_history',{}).get('execution',[])
        and timeline_text(auth) in text and f'plan evidence #{plan.evidence_id}' in text)

def assessment_form(post):
    raw=post.get('production_impact','unknown')
    if raw not in ['unknown','true','false']:raise ValidationError('Choose true, false or unknown production impact')
    return {'outputs':{k:post.get('impact_'+k,'').strip() or None for k in OUTPUTS},
            'production_impact':{'unknown':None,'true':True,'false':False}[raw],
            'scope_items':post.get('scope_items','').splitlines() if post.get('scope_items','').strip() else None}

def execution_form(post):
    return {'scope_items':post.get('scope_items','').splitlines() if post.get('scope_items','').strip() else None,
            'dossier_id':int(post['dossier_id']) if post.get('dossier_id') else None,
            'candidate_id':int(post['candidate_id']) if post.get('candidate_id') else None}

def timeline_required(auth):
    return auth.version.category=='Normal' and any(a.timeline_impact for a in authorized_details(auth).values())

def notice_has_timeline(auth,version):
    return not timeline_required(auth) or timeline_text(auth) in '\n'.join(s['text'] for s in version.payload['sections'])

def timeline_snapshot(case):
    from .models import ChangeExecutionEvent
    from .change_execution import validate_authorization
    rows=ChangeExecutionEvent.objects.filter(authorization__version__change__case=case,kind='plan_updated').select_related('authorization__version__change').order_by('pk')
    latest={}
    for e in rows:
        if e.impact_details.get('approved_timeline'):latest[e.authorization_id]=e
    result=[]
    for e in latest.values():
        auth=e.authorization;version=auth.version;status='current approved';reason='Current source decisions; not deployment authority'
        if version.change.current_id!=version.pk:
            status='superseded';reason='A newer CR revision requires its own assessment and authority'
        else:
            try:
                validate_authorization(case,auth);deviation_hold(auth)
            except (ValidationError,PermissionDenied) as exc:
                status='held';reason=str(exc)
        result.append({'authorization_id':auth.pk,'change_version_id':version.pk,'reference':version.change.reference,
            'revision':version.number,'plan_event_id':e.pk,'plan_evidence_id':e.evidence_id,
            'timeline':e.impact_details['approved_timeline'],'status':status,'reason':reason})
    return {'baseline':baseline_manifest(case),'rows':result}

def report_timeline(snapshot):
    return '\n'.join(f"{r['reference']} / revision {r['revision']} / {r['status']} / plan evidence #{r['plan_evidence_id']}:\n{r['timeline']}\n{r['reason']}" for r in snapshot['rows'])
