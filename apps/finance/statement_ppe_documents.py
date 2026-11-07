"""Model-bound private PPE projections; marker text never grants document authority."""
import hashlib,json
from django.core.exceptions import ValidationError
from apps.identity.services import require
from .models import FinanceStatementPPEProjection
from .statement_ppe import is_ppe_statement,recipient_access


def prepare(actor,run,snapshot,projection,evidence):
    from .documents import report_inputs,projection_rows
    recipient_access(run,[actor.pk]);require(actor,run.case,'finance.publish')
    if not is_ppe_statement(run) or not run.statement_ppe_inputs.exists():raise ValidationError('Exact native PPE statement inventory required')
    if snapshot!=report_inputs(run,snapshot['audience']) or projection!=projection_rows(run,snapshot['projection']):
        raise ValidationError('PPE projection must be recomputed from current native output and reviewed audience')
    proof=FinanceStatementPPEProjection.objects.create(run=run,actor=actor,evidence=evidence,
        snapshot=snapshot,projection=projection,payload_hash=evidence.sha256)
    validate(proof)
    return proof


def validate(proof,current=True):
    from .documents import report_inputs,projection_rows
    proof=FinanceStatementPPEProjection.objects.filter(pk=proof.pk).select_related('evidence','run','actor').first()
    if proof is None:raise ValidationError('Persisted native PPE projection required')
    e=proof.evidence;run=proof.run
    if not is_ppe_statement(run) or not run.statement_ppe_inputs.exists() or e.case_id!=run.case_id or e.created_by_id!=proof.actor_id:
        raise ValidationError('Exact same-case native PPE projection and evidence creator required')
    if e.kind!='finance_report_snapshot' or e.source!='derived:ppe-statement:'+str(run.pk) or hashlib.sha256(e.body.encode()).hexdigest()!=e.sha256 or e.sha256!=proof.payload_hash:
        raise ValidationError('Exact immutable PPE projection payload hash required')
    try:body=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Native PPE projection JSON required') from None
    if proof.snapshot.get('run')!=run.pk or proof.snapshot.get('run_key')!=run.operation_key or proof.projection!=body or body!=projection_rows(run,proof.snapshot['projection']):
        raise ValidationError('Private PPE projection differs from exact native statement output')
    if current:
        recipient_access(run,[proof.actor_id])
        for action in ['finance.publish','document.draft']:require(proof.actor,run.case,action)
        from apps.policy.services import decision_authority
        from django.core.exceptions import PermissionDenied
        authorized=False
        for role in proof.snapshot['projection']['publisher_roles']:
            try:decision_authority(proof.actor,run.case,role);authorized=True;break
            except (ValidationError,PermissionDenied):continue
        if not authorized:raise PermissionDenied('Current configured native PPE projection publisher role required')
        if proof.snapshot!=report_inputs(run,proof.snapshot['audience']):raise ValidationError('PPE projection source, output review or audience changed')
    return proof


def fields_for(proof):
    p=proof.projection;e=proof.evidence_id
    return {'executive_summary':{'text':f"Configured Finance metrics for {p['entity']} / {p['period']} / {p['currency']}. "+p['scope'],'evidence_ids':[e]},
        'financial_metrics':{'text':json.dumps({'accounting_basis':p['accounting_basis'],'figures':p['company'],'columns':p['columns'],'ratio_definition':p['comparison_definition'],'ratio_multiplier':p['ratio_multiplier'],'periods':p['included_periods'],'chart_spec':p['chart_spec']},sort_keys=True),'evidence_ids':[e]},
        'bu_totals':{'text':json.dumps(p['by_bu'],sort_keys=True),'evidence_ids':[e]}}


def create_version(actor,proof,template,title,audience,fields,expected):
    proof=validate(proof);recipient_access(proof.run,[actor.pk])
    if actor.pk!=proof.actor_id or template.case_id!=proof.run.case_id or audience!=proof.snapshot['audience'] or fields!=fields_for(proof) or title!='Finance configured output '+str(proof.run_id):
        raise ValidationError('Only exact native model-bound PPE fields may enter a controlled document')
    from apps.documents.controlled import _create_version
    return _create_version(actor,proof.run.case_id,template.pk,title,audience,fields,expected,
        authorized_restricted_source_ids=[proof.evidence_id])


def check_binding(binding,current=True):
    run=binding.run;version=binding.version
    if not is_ppe_statement(run):return
    ids={pk for field in version.fields.values() for pk in field['evidence_ids']}
    if len(ids)!=1:raise ValidationError('Exact single native PPE projection evidence required')
    proof=FinanceStatementPPEProjection.objects.filter(evidence_id=next(iter(ids)),run=run).select_related('run','actor','evidence').first()
    if proof is None:raise ValidationError('Marker-only or foreign private projection cannot authorize a report')
    validate(proof,current)
    if version.document.case_id!=run.case_id or version.created_by_id!=proof.actor_id or binding.snapshot!=proof.snapshot or version.audience!=proof.snapshot['audience'] or version.fields!=fields_for(proof):
        raise ValidationError('PPE controlled document differs from its exact model-bound projection')

    from apps.documents.controlled import project_payload
    from apps.documents.contracts import digest
    expected=project_payload(version.document.title,version.template.definition,version.audience,version.fields)
    if version.document.title!='Finance configured output '+str(run.pk) or version.payload!=expected or version.payload_sha256!=digest(expected) or version.source_manifest!=[{'id':proof.evidence_id,'version':proof.evidence.version,'sha256':proof.payload_hash}]:
        raise ValidationError('PPE document payload or source manifest differs from native projection')
