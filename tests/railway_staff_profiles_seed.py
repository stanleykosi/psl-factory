"""Configure SAMPLE profiles only. No user, grant, invitation or departure changes."""
from copy import deepcopy
import json
import os

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.identity import intake
from apps.identity.intake_models import TenantAuthority


@transaction.atomic
def prepare():
    if os.environ.get('PSL_STAFF_PROFILES_FIXTURE')!='1':raise RuntimeError('Explicit synthetic profile fixture guard required')
    tenant='design-staff-account-walkthrough'
    users=get_user_model().objects
    operator=users.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
    original=TenantAuthority.objects.filter(tenant=tenant,user=operator).latest('version')
    if original.value['classification']!='synthetic':raise RuntimeError('Synthetic delegation required')
    value=deepcopy(original.value)
    value['staff_lifecycle'].update(allow_profile_edit=True,allow_reactivation=None,profiles=[
        {'key':'sample-project-contributor','label':'SAMPLE project contributor','actions':['case.read','action.own','meeting.read']},
        {'key':'sample-workspace-reader','label':'SAMPLE workspace reader','actions':['case.read']}])
    if value==original.value:return {'already_prepared':True,'authority':original.pk}
    root=users.create_superuser('design-staff-profile-bootstrap')
    cfg=intake.provision(root,operator,tenant,value,original.expires_at,True,
                         'SAMPLE named access profiles for browser testing; no operational owners or policy values')
    root.is_active=False;root.save(update_fields=['is_active'])
    return {'fixture':'staff-profiles-source-only','authority':cfg.pk,'tenant':tenant,
            'grants_changed':False,'invitations_created':False,'accounts_changed':False}


print('PSL_STAFF_PROFILES_FIXTURE='+json.dumps(prepare()))
