"""Explicit795 synthetic identity opt-in; legacy payment fixture stays unconfigured.

Assessment-only predeployment fixture: no readiness, GLPI or payment-exception authority.
This is a local test fixture, not owner policy or production fallback. The accepted
identity helper configures/binds before native invoice review/reserve and refuses
revoked or invalid existing configuration rather than repairing it.
"""
from apps.policy.services import active_component
from .helpers import activate
from .billing_helpers import evidence


def fixture():
    from .test_delivery import DeliveryFixture
    from .billing_helpers import coverage,prices,usage,prepare
    from .settlement_helpers import configured,draft,receipt,assign,allocate
    from .obligation_helpers import issue_identified as issue
    f=DeliveryFixture();f.setup_delivery();a,c=f.actor,f.case
    f.cov=coverage(a,c,completeness='complete');prices(a,c,f.cov);u=usage(a,c,f.cov);p=prepare(a,c,f.cov,u=u)
    original=active_component('D05.role_principal_assignments',c).envelope['value'];configured(a,c)
    finance=active_component('D05.role_principal_assignments',c).envelope['value'];activate(a,c,'D05.role_principal_assignments',original+finance,f.e['policy_decision'])
    f.cash_e={k:evidence(a,c,k,'Synthetic exact Finance evidence') for k in ['invoice_review','cash_correction','cash_allocation']}
    f.iss=issue(a,c,draft(a,c,p),f.cash_e);f.r,f.lot=receipt(a,c,'50.00');assign(a,c,f.r,f.cov,f.cash_e);allocate(a,c,f.lot,f.iss,'10',f.cash_e)
    assert_predeployment_fixture(f)
    return f


def assert_predeployment_fixture(f):
    """Fail closed if unrelated release/exception fixture authority is introduced."""
    from django.contrib.auth import get_user_model
    from apps.policy.models import Configuration
    from apps.policy.payment_validators import ROLE,PEOPLE,DELEGATION,VALIDITY
    from apps.pmo.models import DeliveryRecord
    if Configuration.objects.filter(case=f.case,component__in=[ROLE,PEOPLE,DELEGATION,VALIDITY]).exists():
        raise AssertionError('Assessment fixture must not configure payment exception authority')
    if get_user_model().objects.filter(username='payment-approver').exists():
        raise AssertionError('Assessment fixture must not create exception approver')
    if DeliveryRecord.objects.filter(dossier=f.d).exists():
        raise AssertionError('Assessment fixture must not introduce readiness, GLPI or other delivery records')
