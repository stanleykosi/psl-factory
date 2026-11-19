"""Isolated row-conflict sources and an explicitly simulated recipient report."""
from copy import deepcopy
import json
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core.models import Case
from apps.core.management.commands.seed_demo import ACTIONS
from apps.finance.payroll_models import PayrollPublication
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.payroll_validators import ACCESS,MERGE
from apps.policy.services import transition
from apps.workflows import factory_payroll
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.payroll_helpers import fixture,policy,capture,pipeline

SOURCE_TENANT='design-payroll-row-controls-walkthrough'
RECIPIENT_TENANT='design-payroll-recipient-walkthrough'


@transaction.atomic
def prepare():
    if os.environ.get('PSL_PAYROLL_ROW_FIXTURE')!='1':raise RuntimeError('Explicit synthetic row fixture guard required')
    previous=Case.objects.filter(tenant=SOURCE_TENANT).first()
    if previous:
        recipient=Case.objects.get(tenant=RECIPIENT_TENANT)
        return {'already_prepared':True,'case':str(previous.pk),
                'work':FactoryWork.objects.get(case=previous,definition=factory_payroll.DEFINITION).pk,
                'recipient_case':str(recipient.pk),'publication':PayrollPublication.objects.get(request__case=recipient).pk}
    users=get_user_model().objects
    operator=users.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
    case=Case.objects.create(tenant=SOURCE_TENANT,title='SAMPLE payroll row conflicts and currency',kind='project',synthetic=True)
    for action in ACTIONS:Grant.objects.get_or_create(case=case,user=operator,action=action)
    def principal(role):
        if role=='preparer':return operator
        return users.create_user('sample-payroll-rows-'+role,first_name='SAMPLE row '+role)
    columns={'row_ref':'Ref','employee_id':'Staff ID','component':'Pay code','amount':'Total'}
    f=fixture(employee_ids=['SAMPLE-ROW-001','SAMPLE-ROW-002','SAMPLE-ROW-003'],context=(operator,case),principal=principal,
              payroll_layouts=[{'format':'csv','delimiter':',','columns':columns},
                              {'format':'xlsx','sheet':'Payroll','columns':columns}])
    access=deepcopy(f['config']['access']);merge=deepcopy(f['config']['merge'])
    access.update(format='psl.payroll-access/v2',row_handling='hold_conflicting_rows',currency_mode='row_currency')
    for provider in access['providers']:
        for layout in provider['spreadsheet_layouts']:layout['columns']['currency']='Currency'
    merge.update(format='psl.payroll-merge/v2',duplicate_within_source='hold_conflicting_rows')
    policy(f,ACCESS,access);policy(f,MERGE,merge)
    first=[{**row,'currency':'TEST'} for row in f['config']['exports'][0]['rows']]
    second=[{**f['config']['exports'][1]['rows'][0],'currency':'TEST'},
            {'row_ref':'B2','employee_id':'SAMPLE-ROW-002','component':'BASIC','amount':'200','currency':'TEST'},
            {'row_ref':'B3','employee_id':'SAMPLE-ROW-003','component':'BASIC','amount':'50','currency':None}]
    inputs=[capture(f,0,'sample-rows-A-v2',rows=first,source_version='SAMPLE-A-v2'),
            capture(f,1,'sample-rows-B-v2',rows=second,control_total='400',source_version='SAMPLE-B-v2')]
    profile=json.loads(Path('fixtures/factory-payroll.json').read_text());profile.pop('classification')
    cfg=draft_operator_policy(operator,case.pk,'OPS.factory_payroll_execution',profile,f['e']['policy_decision'].pk,timezone.now())
    transition(operator,cfg.pk,'validated');transition(operator,cfg.pk,'active')
    work=factory_payroll.start(operator,case.pk,'SAMPLE-ROW-CONFLICTS',f['request'].pk,
        {'input_ids':[row.pk for row in inputs],'hr_snapshot_id':f['hr'].pk},
        'SAMPLE prepare valid rows while duplicate and currency rows stay held',rev(case))

    recipient_case=Case.objects.create(tenant=RECIPIENT_TENANT,title='SAMPLE reviewed payroll totals only',kind='project',synthetic=True)
    hr_owner=users.create_user('sample-payroll-private-hr',first_name='SAMPLE private source owner')
    for action in ACTIONS:Grant.objects.get_or_create(case=recipient_case,user=hr_owner,action=action)
    def recipient_principal(role):
        if role=='manager':return operator
        return users.create_user('sample-payroll-private-'+role,first_name='SAMPLE private '+role)
    recipient=fixture(employee_ids=['PRIVATE-SAMPLE-001','PRIVATE-SAMPLE-002'],context=(hr_owner,recipient_case),principal=recipient_principal)
    combined,matched,total,publication=pipeline(recipient,prefix='SAMPLE-seeded-reviewed-report')
    return {'fixture':'synthetic-row-sources-and-simulated-reviewed-recipient-report','case':str(case.pk),'work':work.pk,
            'request':f['request'].pk,'inputs':[row.pk for row in inputs],'hr_snapshot':f['hr'].pk,
            'source_case_drafts_created':False,'source_case_payroll_approved':False,'source_case_payroll_published':False,
            'recipient_case':str(recipient_case.pk),'publication':publication.pk,
            'recipient_report_reviews':'Explicitly simulated native fixture reviews, not browser or operational approvals',
            'recipient_receipt_created':False,'recipient_private_access':False,'coordinator_provider':'synthetic_factory_v1',
            'operational_policy_values_adopted':False}


print('PSL_PAYROLL_ROW_FIXTURE='+json.dumps(prepare()))
