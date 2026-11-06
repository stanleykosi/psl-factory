"""Owner declarations, with finite same-unit operations and evidenced golden cases."""
import json
from django.core.exceptions import ValidationError
from .document_validators import typed
from .finance_validators import obj,rows,KEY
from apps.pmo.services import subject
from apps.finance.rules import decimal

ID={'type':'integer','minimum':1}
UNIT={'enum':['major_currency','thousands_currency','millions_currency']}
AMOUNT={'anyOf':[{'type':'string','minLength':1},{'type':'null'}]}
PRODUCER=obj({'key':KEY,'source_run':ID,'operation_key':{'type':'string','minLength':1,'maxLength':100},
    'source_review':ID,'metric':KEY,'unit':UNIT,'convention':KEY,'evidence_id':ID})
EXAMPLE=obj({'kind':{'enum':['positive','negative','zero','unknown']},'input':AMOUNT,'expected':AMOUNT})
CONVERSION=obj({'key':KEY,'from_convention':KEY,'to_convention':KEY,'unit':UNIT,
    'operation':{'enum':['identity','reverse_sign']},'factor':{'enum':['1','-1']},
    'evidence_id':ID,'oracle_evidence_id':ID,'oracles':{'type':'array','minItems':4,'maxItems':4,'items':EXAMPLE}})

def validate_reference(component,target,case):
    producer=component=='D06.producer_conventions'
    value=typed(target,'schema:psl/'+('producer-conventions' if producer else 'statement-conversions')+'/v1',obj({'declarations':rows(PRODUCER if producer else CONVERSION)}))
    if len({r['key'] for r in value['declarations']})!=len(value['declarations']):raise ValidationError('Unique convention declaration keys required')
    if producer:
        identities=[tuple(row[k] for k in ['source_run','operation_key','source_review','metric','unit']) for row in value['declarations']]
        if len(set(identities))!=len(identities):raise ValidationError('One producer convention per exact output identity is required')
    from apps.finance.models import FinanceRun,FinanceReview
    for row in value['declarations']:
        subject(case,row['evidence_id'],'finance_review')
        if producer:
            run=FinanceRun.objects.filter(pk=row['source_run'],case=case,kind='formula',operation_key=row['operation_key']).first()
            if run is None or not FinanceReview.objects.filter(pk=row['source_review'],case=case,run=run,purpose='output',verdict='approve').exists():
                raise ValidationError('Producer declaration requires exact same-case formula operation and approved output review')
            metric=run.result['company'].get(row['metric'])
            if metric is None or metric['unit']!=row['unit']:raise ValidationError('Producer metric/unit mismatch')
        else:
            if row['factor']!=('1' if row['operation']=='identity' else '-1'):raise ValidationError('Operation must match explicit finite factor')
            if row['operation']=='identity' and row['from_convention']!=row['to_convention']:raise ValidationError('Identity requires the exact same convention identifier')
            if row['operation']=='reverse_sign' and row['from_convention']==row['to_convention']:raise ValidationError('Reversal requires distinct explicit convention identifiers')
            if {r['kind'] for r in row['oracles']}!={'positive','negative','zero','unknown'}:raise ValidationError('Positive, negative, zero and unknown golden examples required')
            evidence=subject(case,row['oracle_evidence_id'],'finance_oracle')
            try: oracle=json.loads(evidence.body)
            except (ValueError,TypeError):raise ValidationError('Structured convention oracle required')
            if oracle!=row['oracles']:raise ValidationError('Conversion examples differ from exact oracle evidence')
            for example in row['oracles']:
                amount=example['input'];expected=example['expected'];kind=example['kind']
                if kind=='unknown':
                    if amount is not None or expected is not None:raise ValidationError('Unknown must stay unknown')
                else:
                    if amount is None or expected is None:raise ValidationError('Known conversion oracle must remain known')
                    n=decimal(amount)
                    if not {'positive':n>0,'negative':n<0,'zero':n==0}[kind]:raise ValidationError('Oracle sign category mismatch')
                    from apps.finance.conventions import apply_conversion
                    if decimal(apply_conversion(amount,row))!=decimal(expected):raise ValidationError('Convention conversion oracle mismatch')
    return value
