from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.policy.services import active_component,reference_values,decision_authority
from apps.pmo.services import subject
from .analysis import review_authority,note
from .models import InvoiceCorrection,CashSuccessor,FinancialCorrectionReview


def policy(case,target):
    c=active_component('D14.adjustment_correction_rule_refs',case);legal=active_component('D14.legal_document_requirements',case)
    rules=[r for r in reference_values(c) if r['target']==target];docs=[r for r in reference_values(legal) if r['target']==target]
    if len(rules)!=1 or len(docs)!=1:raise ValidationError('Configure exact correction authority and legal evidence for '+target)
    return {c.component:c.pk,legal.component:legal.pk,'rule':rules[0],'legal':docs[0]}

def execution_authority(actor,request,target,role,action):
    case=request.case;list(Grant.objects.select_for_update().filter(case=case).order_by('pk'));require(actor,case,action)
    p=policy(case,target)
    if role not in p['rule']['roles'] or p['rule']['require_distinct_preparer'] and request.actor_id==actor.pk:raise PermissionDenied('Configured correction executor role/separation is not satisfied')
    return dict(decision_authority(actor,case,role),**p)

def request_for(case,kind,pk):
    model=InvoiceCorrection if kind=='invoice' else CashSuccessor if kind=='cash' else None
    r=model.objects.filter(case=case,pk=pk).first() if model else None
    if not r:raise ValidationError('Select exact case invoice correction or cash successor')
    return r

def snapshot(request):
    if isinstance(request,InvoiceCorrection):
        from .corrections import review_snapshot
    else:
        from .cash_successors import review_snapshot
    return review_snapshot(request)

@transaction.atomic
def review(actor,case_id,kind,request_id,role,verdict,evidence_id,reason,expected):
    case=lock_case(actor,case_id,'finance.correction.review',expected);r=request_for(case,kind,request_id);note(reason)
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose a configured review action')
    value=snapshot(r);purpose='invoice_correction' if kind=='invoice' else 'cash_successor'
    auth=review_authority(actor,case,purpose,role,verdict,r.actor_id)
    result=FinancialCorrectionReview.objects.create(correction=r if kind=='invoice' else None,successor=r if kind=='cash' else None,
        snapshot=value,role=role,verdict=verdict,authority=auth,evidence=subject(case,evidence_id,'financial_correction_review'),note=reason,actor=actor)
    event(actor,case,'financial_correction.reviewed',kind=kind,request=request_id,review=result.pk,verdict=verdict);bump(case);return result

def approved(request):
    invoice=isinstance(request,InvoiceCorrection);q={'correction':request} if invoice else {'successor':request}
    r=FinancialCorrectionReview.objects.filter(**q).order_by('-pk').first()
    if not r or r.verdict!='approve':raise ValidationError('Exact correction requires current configured human review')
    require(r.actor,request.case,'finance.correction.review')
    authority=review_authority(r.actor,request.case,'invoice_correction' if invoice else 'cash_successor',r.role,r.verdict,request.actor_id)
    strip=lambda x:{k:v for k,v in x.items() if k!='D05.decision_action_matrix'}
    if strip(authority)!=strip(r.authority) or snapshot(request)!=r.snapshot:raise ValidationError('Correction review/source/policy is stale; prepare and review current evidence')
    return r
