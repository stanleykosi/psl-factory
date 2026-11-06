"""Scoped planning and investigation only; no human review or provider effect tools."""
from django.db import transaction
from apps.workflows import domain_contracts as d

@transaction.atomic
def prepare(actor,case_id,plan_id,reference,kind,payload,evidence_id,predecessor=None):
    p=d.d.Plan.objects.get(pk=plan_id,case_id=case_id);d.d.access(actor,p.case,'agent')
    return d.capture(actor,case_id,plan_id,reference,kind,payload,evidence_id,predecessor)

@transaction.atomic
def investigate(actor,case_id,contract_id):
    r=d.get(actor,case_id,contract_id,'agent');result=d.report(actor,case_id,r.pk)
    result['effect_tools']=[]
    result['next_steps']=['Obtain current source-owner review of exact provider identity, credential revision and payload mapping'] if not result['review_current'] else []
    for o in result['observations']:
        if not o['current']:result['next_steps'].append(f"Collect fresh evidence for observation {o['id']}")
        elif not o['human_review_current']:result['next_steps'].append(f"Request independent source-owner evidence review for observation {o['id']}")
        if o['outcome'] in ['unknown','conflict']:result['next_steps'].append('Retain quarantine and investigate the original operation; no inferred retry')
        for k,state in (o['prerequisites'] or {}).items():
            if state!='verified':result['next_steps'].append(f'{k}: {state}; configure a supported destination contract before dependent activation work')
    return result
