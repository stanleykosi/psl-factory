"""Closed dispatch to native factory publication contracts, never an unbound fallback."""
from django.core.exceptions import ValidationError
from .models import FactoryWork


def publication_scope(actor,case,version,work_id):
    name=FactoryWork.objects.filter(pk=work_id,case=case).values_list('definition',flat=True).first()
    if name=='pmo-change/v1':
        from .factory_change import publication_scope as check
    elif name=='rfp-response/v1':
        from .factory_rfp import publication_scope as check
    elif name=='commercial/v1':
        from .factory_commercial import publication_scope as check
    elif name=='finance-accounts/v1':
        from .factory_accounting import publication_scope as check
    elif name=='delivery-handover/v1':
        from .factory_handover import publication_scope as check
    elif name=='delivery-go-live/v1':
        from .factory_go_live import publication_scope as check
    else:raise ValidationError('No registered factory publication contract for this work')
    return check(actor,case,version,work_id)
