"""Append-only external visibility; Engineering/Security retain every lifecycle decision."""
import json
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.core.models import Evidence
from apps.identity.services import require
from apps.documents.contracts import validate
from adapters.issue_references import FIELDS,read_supplied
from .issue_access import issue_subject
from .issues import current_issue,links
from .models import IssueReferenceContract as Contract,IssueReferenceObservation as Observation,IssueReferenceRevision as Revision

KINDS=['risk','incident','change']


def read_scope(actor,contract):
    for action in ['case.read','issue.read','issue.reference.'+contract.kind+'.read']:require(actor,contract.case,action)
    for action in ['issue.reference.configure','evidence.add']:require(contract.actor,contract.case,action)
    issue_subject(contract.case,contract.evidence_id)


@transaction.atomic
def configure(actor,case_id,kind,source_identity,allowed_fields,mode,evidence_id,expected):
    case=lock_case(actor,case_id,'issue.reference.configure',expected)
    require(actor,case,'issue.read')
    if kind not in KINDS or not isinstance(source_identity,str) or not source_identity.strip() or len(source_identity)>200:
        raise ValidationError('Exact external owner source identity and reference kind required')
    if not isinstance(allowed_fields,list) or any(type(k) is not str for k in allowed_fields) or len(set(allowed_fields))!=len(allowed_fields) or any(k not in FIELDS for k in allowed_fields):
        raise ValidationError('Explicit bounded permitted source fields required')
    if mode not in ['supplied','synthetic_mock'] or mode=='synthetic_mock' and not case.synthetic:
        raise ValidationError('Only supplied readback or synthetic mock sources can be configured')
    row=Contract.objects.create(case=case,kind=kind,source_identity=source_identity,allowed_fields=allowed_fields,mode=mode,evidence=issue_subject(case,evidence_id),actor=actor)
    event(actor,case,'issue.reference_scope',contract=row.pk);bump(case);return row


@transaction.atomic
def observe(actor,case_id,issue_id,state_id,contract_id,source_ref,evidence_id,expected):
    case=lock_case(actor,case_id,'issue.reference.observe',expected)
    issue=current_issue(case,issue_id,state_id)
    contract=Contract.objects.filter(case=case,pk=contract_id).first()
    if not contract:raise ValidationError('Select this case exact source read contract')
    read_scope(actor,contract)
    e=Evidence.objects.filter(case=case,pk=evidence_id,kind='agent_private_issue_readback').first()
    if not e:raise ValidationError('Select exact scoped reference readback evidence')
    require(e.created_by,case,'evidence.add')
    data,at=read_supplied(contract,e,source_ref)
    old=Observation.objects.filter(issue=issue,contract=contract,source_ref=source_ref,evidence=e).first()
    if old:return old
    row=Observation.objects.create(issue=issue,state=issue.current,contract=contract,source_ref=source_ref,evidence=e,source_sha256=e.sha256,observed_at=at,availability=data['availability'],fields=data['fields'],actor=actor)
    event(actor,case,'issue.reference_observed',issue=issue.pk,observation=row.pk,availability=row.availability);bump(case);return row


def observation(actor,case,pk,issue=None):
    if type(pk) is not int or pk<1:raise ValidationError('An exact positive integer observation identity is required')
    row=Observation.objects.select_related('contract__case','contract__actor','evidence__created_by','issue__case','actor').filter(pk=pk,issue__case=case).first()
    if not row or issue and row.issue_id!=issue.pk:raise ValidationError('Select this issue exact observation')
    read_scope(actor,row.contract)
    require(row.actor,case,'issue.reference.observe');require(row.evidence.created_by,case,'evidence.add')
    if row.evidence.kind!='agent_private_issue_readback':raise ValidationError('Scoped source observation required')
    if row.source_sha256!=row.evidence.sha256:raise ValidationError('Source observation hash does not match')
    return row


def head(issue):return issue.reference_revisions.order_by('-number').first()


def reference_values(issue):
    latest=head(issue)
    return latest.references if latest else issue.current.external_links


@transaction.atomic
def correct(actor,case_id,issue_id,state_id,previous_id,references,relations,evidence_id,reason,expected):
    case=lock_case(actor,case_id,'issue.manage',expected);require(actor,case,'issue.read')
    issue=current_issue(case,issue_id,state_id);previous=head(issue)
    if previous_id is not None and (type(previous_id) is not int or previous_id<1):raise ValidationError('An exact integer predecessor revision is required')
    if previous_id!=(previous.pk if previous else None):raise ValidationError('Refresh the exact current reference revision')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reference correction')
    if not isinstance(references,list) or len(references)>20:raise ValidationError('At most twenty references are permitted')
    seen=set()
    for item in references:
        if not isinstance(item,dict) or set(item)-{'kind','source_ref','evidence_id','observation_id'}:raise ValidationError('Typed reference fields required')
        links(case,[{k:v for k,v in item.items() if k!='observation_id'}])
        identity=(item['kind'],item['source_ref'])
        if identity in seen:raise ValidationError('Each source reference occurs once')
        seen.add(identity)
        if item.get('observation_id') is not None:
            row=observation(actor,case,item['observation_id'],issue)
            if [row.contract.kind,row.source_ref]!=list(identity):raise ValidationError('Observation must match the selected external owner record')
    validate({'type':'array','maxItems':20,'uniqueItems':True,'items':{'type':'object','properties':{
        'incident_ref':{'type':'string','minLength':1,'maxLength':240},'change_ref':{'type':'string','minLength':1,'maxLength':240},
        'evidence_id':{'type':'integer','minimum':1},'confirmed':{'const':True}},'required':['incident_ref','change_ref','evidence_id','confirmed'],'additionalProperties':False}},relations)
    for relation in relations:
        if ('incident',relation['incident_ref']) not in seen or ('change',relation['change_ref']) not in seen:raise ValidationError('Human-confirmed relation must link selected incident and change records')
        issue_subject(case,relation['evidence_id'])
    row=Revision.objects.create(issue=issue,state=issue.current,number=previous.number+1 if previous else 1,previous=previous,references=references,relations=relations,evidence=issue_subject(case,evidence_id),reason=reason,actor=actor)
    event(actor,case,'issue.references_corrected',issue=issue.pk,revision=row.pk,previous=previous_id);bump(case);return row


def source_superseded(row):
    # A different record from the same supplied export is not this record's successor.
    for e in row.evidence.case.evidence.filter(kind=row.evidence.kind,source=row.evidence.source,version__gt=row.evidence.version).only('body'):
        try:data=json.loads(e.body)
        except (TypeError,ValueError):continue
        if isinstance(data,dict) and data.get('source_identity')==row.contract.source_identity and data.get('source_ref')==row.source_ref:return True
    return False


def report(actor,issue,max_age_seconds=None):
    require(actor,issue.case,'issue.read')
    if max_age_seconds is not None and (type(max_age_seconds) is not int or max_age_seconds<1):raise ValidationError('Freshness needs an explicit positive configured threshold')
    latest=head(issue);rows=[]
    if latest:
        issue_subject(issue.case,latest.evidence_id)
        require(latest.actor,issue.case,'issue.manage')
    for link in reference_values(issue):
        # Do not surface source identities or fields when a current source grant is withdrawn.
        issue_subject(issue.case,link['evidence_id'])
        data={k:link[k] for k in ['kind','source_ref','evidence_id']}
        data.update(availability='unknown',freshness='unknown',currentness='unobserved',fields={},observed_at=None,source_authenticity_verified=False)
        if link.get('observation_id'):
            row=observation(actor,issue.case,link['observation_id'],issue)
            newer=Observation.objects.filter(issue=issue,contract=row.contract,source_ref=row.source_ref,pk__gt=row.pk).exists()
            source_newer=source_superseded(row)
            data.update(observation_id=row.pk,source_identity=row.contract.source_identity,source_sha256=row.source_sha256,observed_at=row.observed_at.isoformat(),availability=row.availability,fields=row.fields,
                currentness='superseded' if newer or source_newer else 'current',mode=row.contract.mode)
            if max_age_seconds is not None:data['freshness']='stale' if (timezone.now()-row.observed_at).total_seconds()>max_age_seconds else 'fresh'
        rows.append(data)
    relations=latest.relations if latest else []
    for relation in relations:issue_subject(issue.case,relation['evidence_id'])
    return {'revision_id':latest.pk if latest else None,'references':rows,'relations':relations,'external_lifecycle_changed':False}
