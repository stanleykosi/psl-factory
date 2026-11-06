from django.db import transaction
from apps.workflows import native_finance as d

@transaction.atomic
def prepare(actor,case_id,plan_id,reference,effect_key,provider_ref,evidence_id,predecessor=None):
    p=d.d.Plan.objects.get(pk=plan_id,case_id=case_id);d.access(actor,p.case,'agent',family=d.d.effect(p,effect_key)['family'])
    return d.capture(actor,case_id,plan_id,reference,effect_key,provider_ref,evidence_id,predecessor)

@transaction.atomic
def investigate(actor,case_id,mapping_id):
    d.get(actor,case_id,mapping_id,'agent');r=d.report(actor,case_id,mapping_id);r['effect_tools']=[]
    r['next_steps']=list(r['holds'])
    for o in r['observations']:
        if o['outcome'] in ['unknown','conflict']:r['next_steps'].append(f"Observation {o['id']}: {o['outcome']}; retain quarantine and investigate the original Finance operation")
        if not o['current']:r['next_steps'].append(f"Collect fresh exact native evidence for observation {o['id']}")
        elif not o['human_review_current']:r['next_steps'].append(f"Obtain independent Finance review for observation {o['id']}")
    r['next_steps'].append('Publish only the exact reviewed companion packet; no archived retry, invoice creation, provisioning or activation')
    return r
