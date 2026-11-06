"""Native assessment previews; no exception decision, deployment or closure effect."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from apps.identity.services import require
from apps.policy.impact import digest
from apps.pmo.models import DeliveryDossier
from apps.finance.models import BillingCoverage


def readable(actor,case,operation):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current release evidence reader required')
    actions=['case.read','delivery.read']
    if operation=='payment.assess':actions+=['payment.read','finance.read']
    for action in actions:require(actor,case,action)


def payment(actor,case,dossier_id,coverage_id):
    from apps.finance.payments import guard_assess
    d,cov,manifest,result=guard_assess(actor,case,dossier_id,coverage_id)
    return d,{'policies':manifest['policies'],'source':manifest,'calculation_sha256':digest(result),
        'evaluation':{'kind':'payment_assessment','status':result['status'],'debt_waived':False,
            'deployment_authorized':False,'business_approval':False}},None


def hypercare(actor,case,dossier_id):
    from apps.pmo.delivery_closure import guard_evaluate_hypercare
    d,snapshot=guard_evaluate_hypercare(actor,case,dossier_id)
    return d,{'policies':{'D11.hypercare_criteria_ref':snapshot['policy_id']},'source':snapshot,
        'evaluation':{'kind':'hypercare_evaluation','qualified':snapshot['qualified'],
            'deployment_authorized':False,'closure_authorized':False,'business_approval':False}},None


def head(observer,case,operation,args):
    readable(observer,case,operation)
    d=DeliveryDossier.objects.filter(case=case,pk=args['dossier_id']).first()
    cov=BillingCoverage.objects.filter(case=case,pk=args.get('coverage_id')).first() if operation=='payment.assess' else None
    return {'dossier':d.pk if d else None,'candidate':d.candidate_id if d else None,
        'record_heads':[[k,d.records.filter(kind=k).order_by('-pk').values_list('pk',flat=True).first()] for k in ['glpi_request','release_outcome','go_live','hypercare','closure']] if d else [],
        'coverage':[cov.pk,cov.version,cov.completeness] if cov else None,
        'assessment_only':True,'business_approval':False,'deployment_authorized':False,'closure_authorized':False}
