"""Source-bound RFP services. A win starts Route A; it never signs a SOW."""
import json
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case, bump, event, add_evidence
from apps.identity.services import require
from apps.policy.services import active_component, reference_values, decision_authority
from .models import (RFPCase,RFPIntake,RFPAssignment,RFPContribution,RFPResponse,
    RFPReview,RFPOutcome,RFPDisposition,Baseline,CommercialCase)
from .services import subject

TEAMS={'Engineering':'engineering_estimate','QA':'qa_estimate','Security':'security_estimate','Product':'product_input'}
REVIEW_ROLES=['PMO Lead','Engineering Lead']

def note(value):
    if not isinstance(value,str) or not value.strip() or len(value)>4000:raise ValidationError('Provide an evidenced explanation, at most 4000 characters')

def past(value):
    if not value or timezone.is_naive(value) or value>timezone.now():raise ValidationError('Provide an actual timezone-aware time, no later than now')

def root(case):
    r=RFPCase.objects.filter(case=case).first()
    if not r:raise ValidationError('Log this case RFP intake first')
    return r

def ensure_open(r):
    if RFPDisposition.objects.filter(rfp=r).exists():raise ValidationError('RFP disposition is recorded; history remains immutable')

def authority(actor,case,purpose,role):
    c=active_component('D05.decision_action_matrix',case)
    if role not in reference_values(c)[0].get('rfp',{}).get(purpose+'_roles',[]):
        raise PermissionDenied('Configure RFP '+purpose+' authority before this action')
    return dict(decision_authority(actor,case,role),**{c.component:c.pk})

def authority_matches(recorded,current):
    # Assignment/outcome are source assertions, not an approval of the whole action matrix.
    # authority() rechecks the chosen role under the CURRENT namespace. Adding an unrelated
    # outcome permission must not force an already submitted bid to be submitted again.
    component='D05.decision_action_matrix'
    return {k:v for k,v in recorded.items() if k!=component}=={k:v for k,v in current.items() if k!=component}


def outcome_authority_matches(recorded,current):
    return authority_matches({k:v for k,v in recorded.items() if k!='_selection_context'},current)

@transaction.atomic
def intake(actor,case_id,reference,evidence_id,received_at,deadline_status,deadline_at,deadline_evidence_id,note_text,expected):
    case=lock_case(actor,case_id,'rfp.intake',expected);note(note_text);past(received_at)
    if case.kind!='project' or not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Use a project workspace and an RFP reference of at most 160 characters')
    r=RFPCase.objects.filter(case=case).first()
    if not r:
        if Baseline.objects.filter(case=case).exists() or CommercialCase.objects.filter(case=case).exists():raise ValidationError('Use a new pre-engagement workspace for RFP intake')
        if RFPCase.objects.filter(tenant=case.tenant,reference=reference.strip()).exists():raise ValidationError('RFP reference already logged for this tenant')
        r=RFPCase.objects.create(case=case,tenant=case.tenant,reference=reference.strip())
    ensure_open(r)
    if r.reference!=reference.strip():raise ValidationError('Keep the immutable RFP reference')
    e=subject(case,evidence_id,'rfp_intake')
    if deadline_status not in ['unknown','stated','not_stated']:raise ValidationError('State whether the deadline is unknown, stated or explicitly not stated')
    de=None
    if deadline_status=='stated':
        if not deadline_at or timezone.is_naive(deadline_at):raise ValidationError('A stated deadline needs its exact aware time and source')
        de=subject(case,deadline_evidence_id,'rfp_deadline')
    elif deadline_at or deadline_evidence_id:raise ValidationError('Only a stated deadline has a deadline time/source')
    i=RFPIntake.objects.create(rfp=r,number=r.intakes.count()+1,received_at=received_at,deadline_status=deadline_status,
        deadline_at=deadline_at,deadline_evidence=de,evidence=e,note=note_text,actor=actor)
    r.current_intake=i;r.current_response=None;r.save(update_fields=['current_intake','current_response'])
    event(actor,case,'rfp.intake',intake=i.pk,deadline_status=deadline_status);bump(case);return i

@transaction.atomic
def assign(actor,case_id,pm,role,evidence_id,note_text,expected):
    case=lock_case(actor,case_id,'rfp.assign',expected);r=root(case);ensure_open(r);note(note_text)
    auth=authority(actor,case,'assignment',role);require(pm,case,'rfp.prepare');decision_authority(pm,case,'PM')
    a=RFPAssignment.objects.create(intake=r.current_intake,pm=pm,role=role,authority=auth,evidence=subject(case,evidence_id),note=note_text,actor=actor)
    event(actor,case,'rfp.assigned',assignment=a.pk,pm=pm.pk);bump(case);return a

@transaction.atomic
def contribute(actor,case_id,team,evidence_id,expected):
    if team not in TEAMS:raise ValidationError('Select Engineering, QA, Security or Product')
    case=lock_case(actor,case_id,'rfp.contribute:'+team,expected);r=root(case);ensure_open(r)
    x=RFPContribution.objects.create(intake=r.current_intake,team=team,evidence=subject(case,evidence_id,TEAMS[team]),actor=actor)
    event(actor,case,'rfp.input',contribution=x.pk,team=team);bump(case);return x

def current_assignment(r):
    case=r.case;i=r.current_intake;a=i.assignments.order_by('-pk').first()
    if not a:raise ValidationError('Assign an accountable PM')
    from django.contrib.auth import get_user_model
    if get_user_model().objects.filter(pk__in={a.actor_id,a.pm_id},is_active=True).count()!=len({a.actor_id,a.pm_id}):raise PermissionDenied('Current active assignment principals required')
    require(a.actor,case,'rfp.assign');require(a.pm,case,'rfp.prepare');decision_authority(a.pm,case,'PM')
    if not authority_matches(a.authority,authority(a.actor,case,'assignment',a.role)):raise ValidationError('Assignment authority changed; reaffirm assignment')
    return a

def source_snapshot(r):
    case=r.case;i=r.current_intake;a=current_assignment(r)
    inputs={}
    for team in TEAMS:
        x=i.contributions.filter(team=team).order_by('-pk').first()
        if not x:raise ValidationError('Capture '+team+' input')
        require(x.actor,case,'rfp.contribute:'+team);inputs[team]={'id':x.pk,'evidence':x.evidence_id,'sha256':x.evidence.sha256}
    return {'intake':i.pk,'assignment':a.pk,'assignment_authority':a.authority,'inputs':inputs}

def current_response(case,pk):
    r=root(case);ensure_open(r)
    v=RFPResponse.objects.filter(pk=pk,rfp=r).first()
    if not v or r.current_response_id!=v.pk or v.snapshot!=source_snapshot(r):raise ValidationError('RFP source or assignment changed; prepare a current response')
    from .commercial import current_revision,terminal
    current_revision(case,v.commercial_id)
    if terminal(v.commercial) or v.reviews.filter(verdict__in=['return','reject']).exists():raise ValidationError('Returned or rejected response needs a new revision')
    require(v.actor,case,'rfp.prepare');decision_authority(v.actor,case,'PM')
    return v

@transaction.atomic
def prepare_response(actor,case_id,evidence_id,matrix,sources,expected,public_terms_id=None):
    case=lock_case(actor,case_id,'rfp.prepare',expected);r=root(case);ensure_open(r);snap=source_snapshot(r)
    a=RFPAssignment.objects.get(pk=snap['assignment'])
    if a.pm_id!=actor.pk:raise PermissionDenied('Only the assigned PM prepares this response')
    e=subject(case,evidence_id,'rfp_response')
    public_terms=subject(case,public_terms_id,'rfp_commercial_terms')
    if not isinstance(sources,dict) or set(sources)!={'requirements','plan','costing'}:raise ValidationError('Select exact requirements, plan and costing sources')
    for kind,pk in sources.items():
        if type(pk) is not int or pk<1:raise ValidationError('Commercial source IDs must be positive integers')
        subject(case,pk,kind)
    if not isinstance(matrix,list) or not 1<=len(matrix)<=100:raise ValidationError('Provide 1–100 cited requirement mappings')
    seen=set()
    for row in matrix:
        if not isinstance(row,dict) or set(row)!={'key','evidence_id','response','disposition'}:raise ValidationError('Mapping needs key, evidence_id, response and disposition')
        if not isinstance(row['key'],str) or not row['key'].strip() or len(row['key'])>100 or row['key'] in seen:raise ValidationError('Requirement keys must be unique nonempty strings')
        if type(row['evidence_id']) is not int or row['evidence_id']<1:raise ValidationError('Requirement evidence_id must be a positive integer')
        seen.add(row['key']);req=subject(case,row['evidence_id'])
        if req.kind not in ['requirements','rfp_intake'] or row['disposition'] not in ['addressed','clarification','out_of_scope']:raise ValidationError('Cite requirements/intake and an explicit disposition')
        if req.pk not in [sources['requirements'],r.current_intake.evidence_id]:raise ValidationError('Map the exact selected requirements or current received RFP source')
        note(row['response'])
    # New exact draft evidence prevents stale commercial approvals surviving a wording-only revision.
    draft=add_evidence(actor,case.pk,'sow',json.dumps({'rfp_response':e.pk,'body':e.body,'matrix':matrix,
        'public_terms_id':public_terms.pk,'public_terms_sha256':public_terms.sha256},sort_keys=True),'derived:rfp-response:'+str(e.pk))
    case.refresh_from_db()
    from .commercial import propose
    commercial=propose(actor,case.pk,dict(sources,engineering_estimate=snap['inputs']['Engineering']['evidence'],security_estimate=snap['inputs']['Security']['evidence'],sow=draft.pk),e.pk,'RFP commercial response; no signed SOW',case.revision,_rfp=True)
    case.refresh_from_db()
    v=RFPResponse.objects.create(rfp=r,intake=r.current_intake,assignment=a,commercial=commercial,number=r.responses.count()+1,snapshot=snap,matrix=matrix,evidence=e,actor=actor)
    r.current_response=v;r.save(update_fields=['current_response']);event(actor,case,'rfp.response_prepared',response=v.pk);bump(case);return v

def public_terms_for(v):
    source=subject(v.rfp.case,v.commercial.sources['sow'],'sow')
    try:
        data=json.loads(source.body);terms=subject(v.rfp.case,data['public_terms_id'],'rfp_commercial_terms')
        if data['public_terms_sha256']!=terms.sha256:raise ValidationError('Public commercial terms source changed')
    except (KeyError,TypeError,ValueError):raise ValidationError('Select explicit public commercial terms in a new response; internal costing is not an outward quotation')
    return terms

@transaction.atomic
def review(actor,case_id,response_id,role,verdict,evidence_id,note_text,expected):
    case=lock_case(actor,case_id,'rfp.review',expected);v=current_response(case,response_id);note(note_text)
    if role not in REVIEW_ROLES or verdict not in ['approve','return','reject']:raise ValidationError('Select prescribed response review role and verdict')
    auth=decision_authority(actor,case,role,verdict)
    x=RFPReview.objects.create(response=v,role=role,verdict=verdict,authority=auth,evidence=subject(case,evidence_id),note=note_text,actor=actor)
    event(actor,case,'rfp.reviewed',review=x.pk,verdict=verdict,role=role);bump(case);return x

def reviewed(v):
    current_response(v.rfp.case,v.pk);ids=[]
    for role in REVIEW_ROLES:
        x=v.reviews.filter(role=role).order_by('-pk').first()
        if not x or x.verdict!='approve':raise ValidationError('Current RFP review missing: '+role)
        require(x.actor,v.rfp.case,'rfp.review')
        if decision_authority(x.actor,v.rfp.case,role)!=x.authority:raise ValidationError('RFP review authority changed')
        ids.append(x.pk)
    return ids

@transaction.atomic
def outcome(actor,case_id,submission_id,result,observed_at,role,evidence_id,note_text,expected,selection_context=None):
    from .models import RFPSubmission
    case=lock_case(actor,case_id,'rfp.outcome',expected);r=root(case);ensure_open(r);note(note_text);past(observed_at)
    require(actor,case,'case.read');require(actor,case,'rfp.read')
    s=RFPSubmission.objects.filter(pk=submission_id,response__rfp=r).first()
    if not s or observed_at<s.submitted_at:raise ValidationError('Outcome must follow an actual exact submission')
    if result not in ['won','lost','pending','unknown']:raise ValidationError('Record won, lost, pending or unknown')
    from .rfp_outcomes import selection_authority
    auth=authority(actor,case,'outcome',role)
    selection=selection_authority(case,s,selection_context)
    if selection:auth['_selection_context']=selection
    x=RFPOutcome.objects.create(submission=s,result=result,observed_at=observed_at,role=role,authority=auth,evidence=subject(case,evidence_id,'rfp_outcome'),note=note_text,actor=actor)
    event(actor,case,'rfp.outcome_recorded',outcome=x.pk,result=result);bump(case);return x

@transaction.atomic
def dispose(actor,case_id,outcome_id,lessons_id,expected):
    case=lock_case(actor,case_id,'rfp.dispose',expected);r=root(case);ensure_open(r)
    require(actor,case,'case.read');require(actor,case,'rfp.read')
    x=RFPOutcome.objects.filter(pk=outcome_id,submission__response__rfp=r).first()
    if not x or x.result not in ['won','lost'] or r.responses.filter(submissions__outcomes__pk__gt=x.pk).exists():raise ValidationError('Use the latest evidenced won/lost outcome')
    from .rfp_outcomes import historical_submission,require_current_selection
    v=historical_submission(case,x.submission)
    require(x.actor,case,'rfp.outcome')
    if not outcome_authority_matches(x.authority,authority(x.actor,case,'outcome',x.role)):raise ValidationError('Outcome authority changed; reaffirm outcome')
    require_current_selection(case,x)
    lessons=subject(case,lessons_id,'rfp_lessons') if x.result=='lost' else None
    d=RFPDisposition.objects.create(rfp=r,outcome=x,kind='route_a' if x.result=='won' else 'loss_archive',lessons=lessons,actor=actor,
        snapshot={'response':v.pk,'submission':x.submission_id,'outcome':x.pk,'case':str(case.pk),'route':'A' if x.result=='won' else None,'baseline_imported':False,'sources':v.snapshot,'commercial_sources':v.commercial.sources})
    event(actor,case,'rfp.disposed',disposition=d.pk,kind=d.kind);bump(case);return d
