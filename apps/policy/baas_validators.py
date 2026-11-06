from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.finance.rules import decimal
from adapters.forecast import obj,rows,KEY,MONEY
from adapters.reconciliation import NULLKEY
from .document_validators import typed,ROLES

SUPPORTED={'D09.reconciliation_contract_ref','D09.queue_state_command_map'}
KEYS={'type':'array','maxItems':100,'uniqueItems':True,'items':KEY}
ROLE_LIST={'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}}
CONTRACT=obj({'implementation':{'const':'exact_declared_sources_v1'},'sources':obj({'ledger':KEY,'settlement':KEY,'queue':NULLKEY}),
    'decimal_places':{'type':'integer','minimum':0,'maximum':8},'amount_tolerance':MONEY,'max_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},
    'pending_after_seconds':{'type':'integer','minimum':0,'maximum':31536000},'pending_queue_states':KEYS,'statuses':obj({'settled':KEYS,'pending':KEYS,'failed':KEYS}),
    'attestation_kinds':{'type':'array','uniqueItems':True,'items':{'enum':['ledger','settlement','queue']}},'attester_roles':ROLE_LIST})
COMMAND=obj({'key':KEY,'kind':{'enum':['corrective_credit','fund_movement','queue_transition']},'currency':{'type':'string','pattern':'^[A-Z]{3}$'},
    'allowed_findings':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['settlement_confirmed','not_confirmed','ambiguous']}},
    'require_queue_state':NULLKEY,'from_state':NULLKEY,'to_state':NULLKEY,'max_amount':MONEY,'amount_rule':{'enum':['exact_ledger_amount','up_to_ledger_amount','no_money']},
    'account_pairs':rows(obj({'from_account':NULLKEY,'to_account':KEY})),
    'approver_roles':ROLE_LIST,'sender_roles':ROLE_LIST,'verifier_roles':ROLE_LIST,'allow_preparer_review':{'type':'boolean'},'distinct_outcome_verifier':{'type':'boolean'}})
MAP=obj({'implementation':{'const':'engineering_request_only_v1'},'recipient_id':{'type':'integer','minimum':1},'execution_source':KEY,
    'lease_seconds':{'type':'integer','minimum':15,'maximum':300},'max_attempts':{'type':'integer','minimum':1,'maximum':10},
    'duplicate_subject_method':{'const':'one_delivery_per_partner_transaction_kind_transition_v1'},'commands':rows(COMMAND,1)})

def validate_reference(component,target,case,runtime=False):
    if component=='D09.reconciliation_contract_ref':
        v=typed(target,'schema:psl/baas-reconciliation/v1',CONTRACT)
        if v['amount_tolerance'] is None:raise ValidationError('Configure exact known reconciliation tolerance, never default zero')
        decimal(v['amount_tolerance'],nonnegative=True)
        all_statuses=sum(v['statuses'].values(),[])
        if not v['statuses']['settled'] or len(all_statuses)!=len(set(all_statuses)):raise ValidationError('Settled/pending/failed statuses must be explicit and disjoint')
        if v['sources']['queue'] is None and 'queue' in v['attestation_kinds']:raise ValidationError('Queue attestation needs a configured queue source')
        return
    v=typed(target,'schema:psl/baas-queue-commands/v1',MAP)
    if len({r['key'] for r in v['commands']})!=len(v['commands']):raise ValidationError('Duplicate business command key')
    for c in v['commands']:
        queue=c['kind']=='queue_transition'
        if queue:
            if not c['from_state'] or not c['to_state'] or c['from_state']==c['to_state'] or c['require_queue_state']!=c['from_state'] or c['amount_rule']!='no_money' or c['max_amount'] is not None or c['account_pairs']:raise ValidationError('Queue command requires exact distinct states, no amount/accounts, and matching current-state prerequisite')
        else:
            if c['from_state'] or c['to_state'] or c['amount_rule']=='no_money' or c['max_amount'] is None or not c['account_pairs']:raise ValidationError('Financial request requires explicit amount bound, account route and no queue transition')
            decimal(c['max_amount'],positive=True)
            for pair in c['account_pairs']:
                if c['kind']=='fund_movement' and (not pair['from_account'] or pair['from_account']==pair['to_account']):raise ValidationError('Fund movement needs distinct allowed accounts')
                if c['kind']=='corrective_credit' and pair['from_account'] is not None:raise ValidationError('This corrective credit method does not infer a funding account')
        if len({(r['from_account'],r['to_account']) for r in c['account_pairs']})!=len(c['account_pairs']):raise ValidationError('Duplicate allowed account route')
    if not runtime:
        from .services import decision_authority
        person=get_user_model().objects.filter(pk=v['recipient_id'],is_active=True).first()
        if not person or not Grant.objects.filter(case=case,user=person,action='baas.engineering.receive',active=True).exists():raise ValidationError('Engineering recipient requires an active actual principal and case receive grant')
        decision_authority(person,case,'Engineering')
