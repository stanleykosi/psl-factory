"""Prepare synthetic source facts only; working drafts remain browser commands."""
from copy import deepcopy
import json
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core.models import Case
from apps.core.management.commands.seed_demo import ACTIONS
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory_payroll
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.payroll_helpers import fixture,capture


@transaction.atomic
def prepare():
    if os.environ.get('PSL_PAYROLL_WORKING_FIXTURE')!='1':raise RuntimeError('Explicit synthetic payroll fixture guard required')
    tenant='design-payroll-working-walkthrough'
    previous=Case.objects.filter(tenant=tenant).first()
    if previous:
        work=FactoryWork.objects.filter(case=previous,definition='finance-payroll/v1').only('id').get()
        return {'already_prepared':True,'case':str(previous.pk),'work':work.pk}
    users=get_user_model().objects
    operator=users.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
    case=Case.objects.create(tenant=tenant,title='SAMPLE payroll working rows · September',kind='project',synthetic=True)
    for action in ACTIONS:Grant.objects.get_or_create(case=case,user=operator,action=action)
    def principal(role):
        if role=='preparer':return operator
        return users.create_user('sample-payroll-working-'+role,first_name='SAMPLE payroll '+role)
    columns={'row_ref':'Ref','employee_id':'Staff ID','component':'Pay code','amount':'Total'}
    f=fixture(employee_ids=['SAMPLE-WORKER-001','SAMPLE-WORKER-002'],context=(operator,case),principal=principal,
        payroll_layouts=[{'format':'csv','delimiter':',','columns':columns},
                        {'format':'xlsx','sheet':'Payroll','columns':columns}])
    value=json.loads(Path('fixtures/factory-payroll.json').read_text());value.pop('classification')
    cfg=draft_operator_policy(operator,case.pk,'OPS.factory_payroll_execution',value,f['e']['policy_decision'].pk,timezone.now())
    transition(operator,cfg.pk,'validated');transition(operator,cfg.pk,'active')
    rows=deepcopy(f['config']['exports'][1]['rows']);rows[0]['amount']=None
    f['inputs'][1]=capture(f,1,'sample-unknown-pay-item',rows=rows,control_total=None)
    selection={'input_ids':[row.pk for row in f['inputs']],'hr_snapshot_id':f['hr'].pk}
    work=factory_payroll.start(operator,case.pk,'SAMPLE-PRIVATE-WORKING',f['request'].pk,selection,
        'SAMPLE review payroll rows while an amount needs source correction',rev(case))
    return {'fixture':'payroll-working-synthetic-source-only','case':str(case.pk),'work':work.pk,'request':f['request'].pk,
        'inputs':selection['input_ids'],'hr_snapshot':f['hr'].pk,'working_drafts_created':False,
        'payroll_approved':False,'payroll_published':False,'coordinator_provider':'synthetic_factory_v1',
        'combined_operator_roles':'Synthetic HR source owner and Finance preparer only; not an operational eligibility decision',
        'reviewer':f['reviewer'].pk,'recipient':f['manager'].pk}


print('PSL_PAYROLL_WORKING_FIXTURE='+json.dumps(prepare()))
