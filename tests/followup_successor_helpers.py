import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.models import RegisteredReference
from apps.policy.services import transition,active_component,reference_values,save_draft
from apps.policy.operator_drafts import draft_operator_policy
from apps.documents.contracts import digest
from apps.policy.followup_successor_validators import COMPONENT
from apps.finance import receipt_followup as source,followup_successors as d
from .billing_helpers import evidence
from .helpers import envelope

def request(a,c,original,outcome='unknown'):
    projection=dict(format='psl.finance-receipt-followup/v1',source_case_id=str(c.pk),source_invoice_id=original.invoice_id,
        source_correction_id=original.intent.get('correction'),variant=original.kind,mapping_sha256='a'*64,observation_sha256='b'*64,
        packet_sha256='c'*64,publication_operation='d'*64,outcome=outcome,business_jobs_reenacted=False,debt_waived=False,activation_enabled=False)
    proof=evidence(a,c,'integration_contract','Synthetic successor lineage relationship evidence')
    return source.receive(a,c.pk,projection,proof.pk),proof

def configure(a,c,r):
    e=evidence(a,c,'policy_decision','Synthetic independent Finance successor criteria; not a real appointment')
    owner=dict(owner_id=a.pk,owner_role='Finance',resolutions=['investigate','link_current_intent','decline'],request_valid_seconds=3600,allow_synthetic=True)
    if not source.resolve(source.FOLLOWUP,c).status=='ACTIVE':
        cfg=draft_operator_policy(a,c.pk,source.FOLLOWUP,owner,e.pk,timezone.now());transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    source.decide(a,c.pk,r.pk,'investigate','Synthetic source investigation; no financial authorisation','successor-investigation')
    reviewer=get_user_model().objects.create_user(username='successor-reviewer',password='test-only-password')
    for action in ['case.read','finance.read','finance.receipt_followup.read','finance.receipt_followup.review_successor','agent.receipt_followup']:
        Grant.objects.create(user=reviewer,case=c,action=action)
    assignment=active_component('D05.role_principal_assignments',c)
    refs=list(assignment.envelope['value'])
    value={'role':'PM','user_id':reviewer.pk};ref='role:successor-reviewer'
    RegisteredReference.objects.create(case=c,ref=ref,schema_ref='schema:psl/role-assignment/v1',content=value,sha256=digest(value),evidence=e)
    cfg=save_draft(a,c.pk,envelope(c,'D05.role_principal_assignments',refs+[ref],e));transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    # A role-policy successor changes the source decision pin: record a new current owner disposition.
    source.decide(a,c.pk,r.pk,'investigate','Synthetic current role-assignment investigation','successor-investigation-current')
    v=json.loads(Path('fixtures/finance-followup-successors.json').read_text())['template'];v['reviewer_id']=reviewer.pk
    cfg=draft_operator_policy(a,c.pk,COMPONENT,v,e.pk,timezone.now());transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    return reviewer,cfg,e
