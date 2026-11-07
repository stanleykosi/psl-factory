"""Explicit reviewed identity mapping, never inferred from a ledger-note comparison."""
import json
from datetime import date
from django.core.exceptions import ValidationError
from .statement_validators import LINE, ID
from .finance_validators import obj
from apps.pmo.services import subject

PPE_LINE=obj({**{k:v for k,v in LINE['properties'].items() if k not in ['source_run','source_review']},
    'source_type':{'const':'ppe_schedule'}, 'schedule_id':ID,'schedule_review_id':ID,'register_id':ID,
    'schedule_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
    'metric':{'enum':['cost','accumulated','book_value','charge']},
    'mapping_evidence_id':ID,
    'coverage':obj({'period_start':{'type':'string','format':'date'},'period_end':{'type':'string','format':'date'},
        'label_as_of':{'type':'string','format':'date'},'method':{'enum':['exact_calendar_month','explicit_reviewed_coverage']},
        'explanation':{'type':'string','minLength':1,'maxLength':1000}})})


def mapping(row,value):
    return {'protocol':'ppe-statement-identity/v1',
        **{k:value[k] for k in ['entity','period','currency','accounting_basis']},
        'input':{k:v for k,v in row.items() if k!='mapping_evidence_id'}}


def validate_binding(row,case,value):
    from apps.finance.models import ScheduleWork,ScheduleReview
    work=ScheduleWork.objects.filter(pk=row['schedule_id'],case=case,kind='ppe_schedule').first()
    if not work or work.sha256!=row['schedule_sha256'] or work.payload['register_id']!=row['register_id']:
        raise ValidationError('Exact same-case PPE schedule hash and register required')
    if not ScheduleReview.objects.filter(pk=row['schedule_review_id'],work=work,authority__purpose='schedule',verdict='approve').exists():
        raise ValidationError('Exact PPE schedule approval required')
    e=subject(case,row['mapping_evidence_id'],'policy_decision')
    try: declared=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Structured PPE identity mapping evidence required') from None
    if declared!=mapping(row,value):raise ValidationError('Independent evidence must match exact PPE source field, basis, coverage and presentation mapping')
    if work.parent_id and work.parent.source.accounting_basis!=value['accounting_basis']:
        raise ValidationError('PPE native ledger comparison basis differs; no basis conversion')
    scope=work.result['scope']
    if any(scope[k]!=value[k] for k in ['entity','currency']) or scope['unit']!=row['unit']:
        raise ValidationError('PPE entity, currency and unit must match; no conversion')
    if row['source_sign'] is None or row['source_sign']!=row['destination_sign']:
        raise ValidationError('Explicit identical PPE presentation signs required; no conversion')
    if row['source_location']!='totals.'+row['metric']:
        raise ValidationError('PPE field mapping must identify the exact native totals field')
    coverage=row['coverage']
    try:start,end,label=[date.fromisoformat(coverage[k]) for k in ['period_start','period_end','label_as_of']]
    except ValueError:raise ValidationError('Actual PPE coverage dates required') from None
    if start>end or any(coverage[k]!=scope[k] for k in ['period_start','period_end','label_as_of']):
        raise ValidationError('PPE date coverage must preserve native dates exactly')
    if coverage['method']=='exact_calendar_month':
        import calendar
        if start.strftime('%Y-%m')!=value['period'] or start.day!=1 or end.strftime('%Y-%m')!=value['period'] or end.day!=calendar.monthrange(end.year,end.month)[1] or label!=end:
            raise ValidationError('Exact calendar-month PPE coverage differs; explicit reviewed coverage required')
    return work
