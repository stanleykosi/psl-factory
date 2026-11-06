"""Native evaluation through existing AF13 authority; never a new acceptance authority."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import event,bump
from apps.identity.services import require
from apps.policy.services import active_component,reference_values
from apps.policy.validation_validators import ACCEPTANCE
from apps.finance import acceptance_evaluation as evaluation
from adapters import validation_native as adapter
from .contracts import digest
from .validation_models import ValidationReplay,ValidationExample


def native(row):return row.provenance.get('format') in adapter.FORMATS


def package_access(actor,p):
    # Historical native sources remain protected even after policy/source supersession.
    for row in ValidationReplay.objects.filter(package=p,provenance__format__in=adapter.FORMATS):
        adapter.source(actor,p.case,row.provenance['family'],row.provenance['job'])


def rules(p):
    cfg=active_component(ACCEPTANCE,p.case);value=reference_values(cfg)[0]
    if 'native_execution' not in value:raise ValidationError('Configure versioned AF13 native execution criteria')
    return cfg,value['native_execution']


@transaction.atomic
@evaluation.evaluated
def record(actor,case_id,package_id,example_id,family,job_id,evidence_id,key,expected):
    from . import validation as af13
    c=af13.locked(actor,case_id,'validation.replay.record',expected);p=af13.package_for(c,package_id)
    af13._private_access(actor,p);af13.package_current(p)
    if not isinstance(key,str) or not key.strip() or len(key)>100:raise ValidationError('Bounded native evaluation key required')
    evidence=af13.subject(c,evidence_id)
    old=ValidationReplay.objects.filter(package=p,operation_key=key).first()
    if old:
        if not native(old) or (old.actor_id,old.example_id,old.evidence_id,old.provenance['family'],old.provenance['job'])!=(actor.pk,example_id,evidence.pk,family,job_id):
            raise ValidationError('Native evaluation key conflicts with prior evidence')
        return old # Historical receipt only; current() remains mandatory for current use.
    cfg,v=rules(p)
    if family not in v['families']:raise ValidationError('Native family is not configured for this acceptance scope')
    ex=ValidationExample.objects.filter(case=c,pk=example_id).first()
    if not ex or ex.pk not in p.payload['example_ids']:raise ValidationError('Exact selected owner example required')
    expect=af13.approved_review(p,'expectations')
    actual,head,j=adapter.observe(actor,c,family,job_id)
    if adapter.reserved_at(j,family)<=expect.created_at:raise ValidationError('Native reservation subject must follow the independently reviewed expectations')
    provenance={'format':adapter.FORMAT,'evidence_class':'synthetic_native_execution' if c.synthetic else 'operational_native_execution',
        'family':family,'job':job_id,'head':head,'criteria':cfg.pk,'build_ref':p.payload['build_ref'],
        'source_identity':adapter.build(),
        'scope':'native_source_receipt_only','external_acceptance_claimed':False,'execution_build_verified':False,'build_identity_meaning':'observation_process_only'}
    row=ValidationReplay.objects.create(package=p,example=ex,expectation_review=expect,operation_key=key,actual=actual,
        provenance=provenance,result={'subject_matches':ex.expected.get('subject_sha256')==actual['subject_sha256'],'matches':digest(actual)==af13.finite(ex.expected),'implementation':adapter.FORMAT,
        'actual_sha256':digest(actual),'expected_sha256':af13.finite(ex.expected),'execution_evidence':'native_source_observation',
        'underlying_workflow_executed':j.attempts>0},evidence=evidence,actor=actor)
    evaluation.changed();event(actor,c,'agent.data.native_validation_recorded',replay=row.pk,matches=row.result['matches']);bump(c);return row


def current(row,actor):
    from . import validation as af13
    if not native(row):raise ValidationError('Native workflow evaluation required; supplied actuals cannot establish execution')
    if row.provenance['format']!=adapter.FORMAT:raise ValidationError('Legacy native evaluation lacks the exact subject binding; retain history and use a current evaluation')
    cfg,v=rules(row.package);p=row.package
    require(row.actor,p.case,'validation.replay.record')
    actual,head,j=adapter.observe(actor,p.case,row.provenance['family'],row.provenance['job'])
    # Reauthorize recorder and the named human acceptor against the same exact source.
    adapter.source(row.actor,p.case,row.provenance['family'],row.provenance['job'])
    expect=af13.approved_review(p,'expectations')
    if (row.provenance['family'] not in v['families'] or row.provenance['criteria']!=cfg.pk or row.expectation_review_id!=expect.pk
        or row.provenance['head']!=head or row.actual!=actual or adapter.reserved_at(j,row.provenance['family'])<=expect.created_at
        or row.provenance['build_ref']!=p.payload['build_ref'] or row.result['implementation']!=adapter.FORMAT
        or row.provenance['source_identity']!=adapter.build()
        or row.result['actual_sha256']!=digest(actual) or row.result['expected_sha256']!=af13.finite(row.example.expected)
        or not row.result['matches'] or digest(actual)!=af13.finite(row.example.expected)
        or not 0<=(timezone.now()-row.created_at).total_seconds()<=v['freshness_seconds']):
        raise ValidationError('Native execution/source/criteria/expectations changed or expired; evaluate current evidence')
    if not j.attempts or j.status in ['pending','leased','unknown']:raise ValidationError('Unexecuted or uncertain native work cannot establish acceptance')
    if j.status=='confirmed' and not actual['receipt_present']:raise ValidationError('Confirmed source work requires its verified native receipt')
    expected_class='synthetic_native_execution' if p.case.synthetic else 'operational_native_execution'
    if row.provenance['evidence_class']!=expected_class:raise ValidationError('Native evidence classification changed')
    if p.payload['level']=='operational' and p.case.synthetic:raise ValidationError('Synthetic cases cannot establish operational acceptance')
    return row.pk
