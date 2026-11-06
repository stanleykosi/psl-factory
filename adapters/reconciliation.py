"""Bounded supplied-source adapter. Declared source is not authenticated source."""
import json
from datetime import datetime
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.documents.contracts import validate
from apps.finance.rules import decimal
from adapters.forecast import obj,rows,KEY,MONEY

TIME={'type':'string','maxLength':40}
NULLKEY={'anyOf':[KEY,{'type':'null'}]}
ROW=obj({'partner':KEY,'transaction':KEY,'customer':KEY,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'amount':MONEY,'status':KEY,'account':NULLKEY,'queue_state':NULLKEY,'observed_at':TIME})
BATCH=obj({'kind':{'enum':['ledger','settlement','queue']},'source':KEY,'as_of':TIME,'completeness':{'enum':['complete','partial','unknown']},'partners':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':KEY},'rows':rows(ROW)})
REQUEST=obj({'partner':KEY,'transaction':KEY,'customer':KEY,'command':KEY,'kind':{'enum':['corrective_credit','fund_movement','queue_transition']},'amount':MONEY,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'from_account':NULLKEY,'to_account':NULLKEY,'from_state':NULLKEY,'to_state':NULLKEY})
OUTCOME=obj({'operation_key':KEY,'request_hash':{'type':'string','pattern':'^[a-f0-9]{64}$'},'source':KEY,'external_reference':KEY,'status':{'enum':['applied','rejected','unknown']},'observed_at':TIME,'command':REQUEST})

def at(value):
    try:d=datetime.fromisoformat(value)
    except (TypeError,ValueError):raise ValidationError('Use an actual aware ISO timestamp')
    if timezone.is_naive(d) or d>timezone.now():raise ValidationError('Source observation must be actual and aware, not future')
    return d

def parse(body,schema):
    try:v=json.loads(body)
    except (ValueError,TypeError):raise ValidationError('Supply bounded structured reconciliation JSON')
    validate(schema,v);return v

def batch(body):
    v=parse(body,BATCH);as_of=at(v['as_of'])
    for r in v['rows']:
        if at(r['observed_at'])>as_of:raise ValidationError('Row observed after declared source as-of')
        if r['partner'] not in v['partners']:raise ValidationError('Row partner outside declared coverage')
        if r['amount'] is not None:decimal(r['amount'],nonnegative=True)
    return v

def request(body):
    v=parse(body,REQUEST)
    if v['amount'] is not None:decimal(v['amount'],positive=True)
    if v['kind']=='queue_transition':
        if v['amount'] is not None or v['from_account'] or v['to_account'] or not v['from_state'] or not v['to_state']:raise ValidationError('Queue request needs exact states and no money/accounts')
    elif v['from_state'] or v['to_state'] or not v['to_account']:raise ValidationError('Financial request needs destination and no queue transition')
    if v['kind']=='fund_movement' and (not v['from_account'] or v['from_account']==v['to_account']):raise ValidationError('Fund request needs distinct explicit accounts')
    return v

def outcome(body):
    v=parse(body,OUTCOME);at(v['observed_at']);request(json.dumps(v['command']));return v

class InternalEngineeringAdapter:
    """Real local request delivery only; never executes a financial command."""
    def lookup(self,job):
        from apps.baas.models import CorrectiveDelivery
        from apps.finance.analysis import digest
        r=CorrectiveDelivery.objects.filter(tenant=job.request.case.tenant,operation_key=job.request.operation_key).first()
        if not r:return None
        if r.request_id!=job.request_id or r.payload!=job.intent['public'] or r.sha256!=digest(r.payload) or r.recipient_id!=job.intent['recipient']:raise ValidationError('Engineering receipt differs from reserved request')
        return r.pk
    def deliver(self,pk,fence):
        from apps.baas.corrective_delivery import deliver_local
        return deliver_local(pk,fence)
