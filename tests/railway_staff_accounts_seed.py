"""Source-only account roster/departure fixture; no account is disabled here."""
import json
import os
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.identity import intake,staff
from apps.identity.actions import ACTIONS
from apps.identity.intake_models import CaseIntake
from apps.core.services import add_evidence
from apps.pmo.meetings import create_action
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from tests.helpers import rev


@transaction.atomic
def prepare():
    if os.environ.get('PSL_STAFF_ACCOUNTS_FIXTURE')!='1':raise RuntimeError('Explicit synthetic fixture guard required')
    tenant='design-staff-account-walkthrough'
    existing=CaseIntake.objects.filter(tenant=tenant,reference='staff-account-one').first()
    if existing:return {'already_prepared':True,'case':str(existing.case_id)}
    users=get_user_model().objects
    operator=users.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
    root=users.create_superuser('design-staff-account-bootstrap')
    value={'format':'psl.tenant-access/v3','create_cases':True,'manage_access':True,'kinds':['project'],
        'allowed_actions':list(dict.fromkeys(ACTIONS)),'initial_actions':list(dict.fromkeys(ACTIONS)),
        'classification':'synthetic','staff_lifecycle':{'invite_minutes':60,'allow_invite':True,
        'allow_deactivation':True,'allow_roster':True,'allow_account_deactivation':True,'allow_unassigned_departure':True}}
    cfg=intake.provision(root,operator,tenant,value,timezone.now()+timedelta(days=3),True,
                         'Synthetic browser account departure only; no operational delegation')
    one=intake.create_case(operator,tenant,'staff-account-one','SAMPLE staff departure · project one','project')
    two=intake.create_case(operator,tenant,'staff-account-two','SAMPLE staff departure · project two','project')
    _,token=staff.invite(operator,one.pk,'sample-staff-departure','SAMPLE departing colleague',
                        'departing-colleague@example.invalid',['case.read','action.own'],rev(one))
    target=staff.accept(token,secrets.token_urlsafe(32))
    successor=users.create_user('sample-staff-successor',first_name='SAMPLE continuing colleague')
    records=[]
    for case in [one,two]:
        for user in [target,successor]:
            for action in ['case.read','action.own']:
                intake.change_access(operator,case.pk,user.pk,action,True,'Synthetic staff handover fixture')
        proof=add_evidence(operator,case.pk,'policy_decision',
            'SAMPLE account departure. Preserve deadlines; one action may remain Owner needed while another goes to the current sample successor.',
            'synthetic:staff-account-browser')
        policy=draft_roles(operator,case.pk,[{'role':'PMO Lead','user_id':u.pk} for u in [target,successor]],
                           proof.pk,timezone.now())
        transition(operator,policy.pk,'validated');transition(operator,policy.pk,'active')
        item=create_action(operator,case.pk,'SAMPLE-STAFF-HANDOVER','SAMPLE verify handover in '+case.title,
                           target.pk,timezone.now()+timedelta(days=2),proof.pk,'Explicit synthetic action',rev(case))
        records.append({'case':str(case.pk),'proof':proof.pk,'action':item.pk})
    root.is_active=False;root.save(update_fields=['is_active'])
    return {'fixture':'staff-account-departure','person':target.pk,'successor':successor.pk,
            'authority':cfg.pk,'scopes':records,'account_deactivated':False,'work_created':False}


print('PSL_STAFF_FIXTURE='+json.dumps(prepare()))
