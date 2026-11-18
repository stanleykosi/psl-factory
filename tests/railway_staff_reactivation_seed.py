"""SAMPLE restoration authority only; no existing staff, grant or role changes."""
from copy import deepcopy
import json
import os

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.identity import intake
from apps.identity.intake_models import TenantAuthority
from apps.identity.staff_models import StaffAdmission


@transaction.atomic
def prepare():
    if os.environ.get('PSL_STAFF_REACTIVATION_FIXTURE')!='1':raise RuntimeError('Explicit synthetic restoration fixture guard required')
    tenant='design-staff-account-walkthrough';users=get_user_model().objects
    operator=users.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
    original=TenantAuthority.objects.filter(tenant=tenant,user=operator).latest('version')
    if original.value['classification']!='synthetic':raise RuntimeError('Synthetic authority required')
    if not StaffAdmission.objects.filter(user__username='sample-profile-invite-157',invitation__case__tenant=tenant).exists():
        raise RuntimeError('The browser-accepted SAMPLE account must exist first')
    if original.value['staff_lifecycle'].get('allow_reactivation') is True:
        return {'already_prepared':True,'authority':original.pk,'existing_staff_changed':False}
    root=users.create_superuser('design-staff-reactivation-bootstrap')
    value=deepcopy(original.value);value['staff_lifecycle']['allow_reactivation']=True
    cfg=intake.provision(root,operator,tenant,value,original.expires_at,True,
                         'SAMPLE fresh-access restoration browser test only; no operational delegation')
    root.is_active=False;root.save(update_fields=['is_active'])
    return {'fixture':'staff-reactivation-authority-only','authority':cfg.pk,
        'inactive_technical_bootstrap_created':root.pk,'existing_staff_changed':False,'grants_changed':False,'roles_changed':False}


print('PSL_STAFF_REACTIVATION_FIXTURE='+json.dumps(prepare()))
