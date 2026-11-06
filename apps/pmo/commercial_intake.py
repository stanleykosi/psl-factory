"""Capture unknown commercial inputs before configuration; native services own all decisions."""
import json,hashlib
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.models import Evidence,Audit
from apps.core.evidence_access import public_evidence
from apps.core.services import add_evidence,event
from apps.identity.services import require
from apps.documents.contracts import validate
from apps.documents.models import Template
from adapters.commercial_intake import KIND,PROTOCOL,VALUE,CommercialIntakeAdapter
from adapters.costing import read as read_inputs,ARRAY,VALUE as INPUT_VALUE
from . import costing
from .models import CommercialRevision

PUBLIC={'requirements':'requirements','plan':'plan','engineering_estimate':'engineering_estimate','security_estimate':'security_estimate','sow':'sow'}

def latest(case):return Evidence.objects.filter(case=case,kind=KIND).order_by('-version').first()

def validate_sources(actor,case,value):
    validate(VALUE,value);costing.readable(actor,case,True)
    for key,kind in PUBLIC.items():
        if value[key] is not None and not public_evidence(Evidence.objects.filter(case=case,pk=value[key],kind=kind)).exists():raise ValidationError('Exact same-case '+kind+' source required')
    if value['context_id'] is not None and not public_evidence(Evidence.objects.filter(case=case,pk=value['context_id'],kind__in=['requirements','client_feedback','change_request'])).exists():raise ValidationError('Exact requirements, client feedback or change context required')
    if value['inputs'] is not None:
        source=Evidence.objects.filter(case=case,pk=value['inputs'],kind='p14_inputs').first()
        if not source:raise ValidationError('Exact private declared costing inputs required')
        read_inputs(source.body,ARRAY(INPUT_VALUE,1))
    if value['oracle_id'] is not None and value['rule_id'] is None:raise ValidationError('Name the actual rule before linking its independent oracle')
    if value['rule_id'] is not None:
        rule=costing.rule_for(case,value['rule_id']);oracle=costing.oracle_for(rule,value['oracle_id']) if value['oracle_id'] is not None else None
        costing.current_source(rule,oracle)
    if value['template_id'] is not None and not Template.objects.filter(case=case,pk=value['template_id'],definition__document_type='sow').exists():raise ValidationError('Exact controlled SOW template required')
    if value['predecessor_id'] is not None and not CommercialRevision.objects.filter(dossier__case=case,pk=value['predecessor_id']).exists():raise ValidationError('Commercial predecessor belongs to another case')
    return value

@transaction.atomic
def capture(actor,case_id,value,predecessor=None,expected=None):
    case=costing.locked(actor,case_id,'commercial.prepare',expected)
    old=latest(case)
    if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit current intake predecessor required')
    validate_sources(actor,case,value)
    if old:
        try:
            if read(actor,case,old)==value:return old
        except (ValidationError,PermissionDenied):pass # valid new sources can replace a stale/withdrawn predecessor
    row=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'sources':value},sort_keys=True,separators=(',',':')),'psl:factory-commercial-intake/v1')
    event(actor,case,'factory.commercial_intake',evidence_id=row.pk,sha256=row.sha256)
    return row

def read(actor,case,evidence):
    costing.readable(actor,case,True)
    if not evidence or evidence.case_id!=case.pk or evidence.kind!=KIND or evidence.sha256!=hashlib.sha256(evidence.body.encode()).hexdigest():raise ValidationError('Exact private commercial intake and hash required')
    if not Audit.objects.filter(case=case,actor=evidence.created_by,action='factory.commercial_intake',data={'evidence_id':evidence.pk,'sha256':evidence.sha256}).exists():raise ValidationError('Native commercial intake provenance required')
    costing.readable(evidence.created_by,case,True);require(evidence.created_by,case,'commercial.prepare')
    value=CommercialIntakeAdapter().read(evidence)['sources']
    return validate_sources(actor,case,value)
