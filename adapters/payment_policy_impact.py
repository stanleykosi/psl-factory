"""Direct D13 assessment pins only; native currentness is not release authority."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.services import require
from apps.policy.payment_validators import DENOMINATOR,FUNDS
from apps.finance.payment_models import PaymentAssessment

KEY='finance.payment_assessments'
COMPONENTS=(DENOMINATOR,FUNDS)

def readable(actor,case):
    if actor is None or not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():
        raise PermissionDenied('Current payment metadata reader required')
    for action in ('case.read','payment.read','finance.read','delivery.read'):
        require(actor,case,action)

def query(actor,config):
    readable(actor,config.case)
    rows=PaymentAssessment.objects.filter(case=config.case)
    if config.component not in COMPONENTS:return rows.none()
    return rows.filter(**{'manifest__policies__'+config.component+'__id':config.pk}).order_by('pk')

def authorize_row(actor,case,row):
    readable(actor,case)
    if row.case_id!=case.pk:raise PermissionDenied('Select this case payment metadata')

def project(row):
    from apps.finance.payments import assessment_current
    try:
        assessment_current(row);current=True
    except (ValidationError,PermissionDenied):current=False
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'payment_controls',
        'sha256':row.sha256,'dossier':row.dossier_id,'coverage':row.coverage_id,
        'native_current':current,'state':'assessment_snapshot_requires_independent_release_controls',
        'assessment_renewed':False,'debt_waived':False,'deployment_authorized':False,
        'deployment_dispatched':False,'cash_moved':False}
