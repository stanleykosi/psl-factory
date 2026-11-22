"""Explicit read-only receipt/provenance probe for the isolated browser sample."""
import json
import os
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.agents.models import AgentJob
from apps.pmo.models import DeliveryDossier,ClientUATGateBinding
from apps.pmo import client_uat as domain
from adapters import client_uat as contract

if os.environ.get('PSL_CLIENT_UAT_PROBE')!='1':raise RuntimeError('Explicit SAMPLE read-only probe guard required')
case=Case.objects.get(tenant='design-client-uat-walkthrough',synthetic=True)
actor=get_user_model().objects.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
domain.readable(actor,case)
dossier=DeliveryDossier.objects.get(case=case)
target=domain.head(dossier,contract.TARGET)
response=domain.head(dossier,contract.RESPONSE,target.pk) if target else None
result={'read_only':True,'synthetic':True,'case':str(case.pk),'dossier':dossier.pk,'target':target.pk if target else None,
    'response':response.pk if response else None,'current_human_review':None,'current_delivery_binding':None,'agents':[]}
if response:
    result['required_file_check_protocol']=contract.INSPECTION
    result['legacy_file_check_count']=response.verifications.filter(adapter=contract.LEGACY_INSPECTION).count()
    result['current_file_check_count']=response.verifications.filter(adapter=contract.INSPECTION).count()
    try:
        review=domain.current_review(actor,response);result['current_human_review']=review.pk
        binding=ClientUATGateBinding.objects.filter(review=review).order_by('-pk').first()
        if binding:
            domain.gate_current(dossier.candidate,binding.verification);result['current_delivery_binding']=binding.pk
    except (ValidationError,PermissionDenied):result['currentness']='fresh_source_authority_or_current_protocol_review_needed'
    domain.proof_rows(actor,response)
    for pin in response.payload['proofs']:
        job=AgentJob.objects.filter(upload_id=pin['id'],actor_id=pin['actor_id'],role='A07').values('pk','status','result__model','result__source_sha256').first()
        if job:
            model=job['result__model']
            result['agents'].append({'job':job['pk'],'status':job['status'],'model':model if isinstance(model,str) and len(model)<=200 else None,
                'source_hash_matches':job['result__source_sha256']==pin['sha256']})
print('PSL_CLIENT_UAT_PROVENANCE='+json.dumps(result))
