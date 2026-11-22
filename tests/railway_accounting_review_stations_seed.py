"""Isolated Finance setup and independent accounting review browser stations."""
import json
import os
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents.models import Publication
from apps.finance import analysis
from apps.finance.models import FinanceDocumentBinding, FinanceReview, FinanceRun, FinanceSource
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.services import register_reference
from apps.workflows import factory, factory_accounting as accounting
from apps.workflows.models import FactoryWork, HumanTask
from tests import finance_analysis_helpers as source
from tests.factory_accounting_helpers import configured
from tests.helpers import activate, rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_ACCOUNTING_REVIEW_STATIONS_FIXTURE'
TENANT = 'design-accounting-review-stations'
MARKER = 'sample.accounting_review_station'
TRIAL_ACTIONS = {'case.read', 'finance.read', 'finance.review', 'factory.read', 'factory.execute', 'factory.manage',
                 'policy.read'}
LABELS = {'setup': 'SAMPLE accounts awaiting statement and business-unit settings',
          'reviews': 'SAMPLE independent accounts source and rule reviews'}


def seed(case, preparer, reviewer, mode):
    users = get_user_model().objects
    baseline_reviewer = users.create_user(username=f'sample-accounting-baseline-reviewer-{mode}')
    for actor, actions in ((preparer, set(ACTIONS)), (reviewer, TRIAL_ACTIONS),
                           (baseline_reviewer, {'case.read','finance.read','finance.review'})):
        Grant.objects.bulk_create([Grant(case=case,user=actor,action=action) for action in sorted(actions)])
    with patch.object(source, 'setup_case', return_value=(preparer, case)):
        _, _, evidence, values, policies, statement_source, template, _ = source.fixture(
            review=False, recipient_username=f'sample-accounting-stations-recipient-{mode}')
    roles=['finance:human']
    for actor in (baseline_reviewer, reviewer):
        assignment = register_reference(preparer,case.pk,f'sample-stations-finance:{actor.pk}',
            'schema:psl/role-assignment/v1',{'role':'Finance','user_id':actor.pk},evidence['policy_decision'].pk)
        roles.append(assignment.ref)
    activate(preparer,case,'D05.role_principal_assignments',roles,evidence['policy_decision'])
    for rule in values['authority']['finance']:
        if rule['purpose'] in accounting.analysis.PURPOSE.values() or rule['purpose'] in {'source','adjustment','output'}:
            rule['allow_preparer_review']=False
    source.policy(preparer,case,'D05.decision_action_matrix',values['authority'],evidence['policy_decision'])
    proof=evidence['finance_review']
    source_review=analysis.review(baseline_reviewer,case.pk,'source',statement_source.pk,'Finance','approve',proof.pk,
                                  'Synthetic trial balance and its exact source inventory reviewed.',rev(case))
    if mode=='setup':
        mapping_review=analysis.review(baseline_reviewer,case.pk,'mapping',policies['D06.account_bu_maps'].pk,
            'Finance','approve',proof.pk,'Synthetic account alignment rule independently reviewed.',rev(case))
        fixture=configured(preparer,case,evidence,statement_source,template,None,statement_contract_id=None)
        adjustment_id=None
    else:
        adjustment=analysis.adjustment(preparer,case.pk,statement_source.pk,'SAMPLE-REPORT-ADJUSTMENT',
            'additive',[{'account':'direct_cost','amount':'20'}],evidence['finance_adjustment'].pk,
            'Synthetic supplemental reporting item that does not post to the ledger.',rev(case))
        fixture=configured(preparer,case,evidence,statement_source,template,source.METRICS)
        work=fixture['work']
        accounting.recheck(preparer,work.pk,work.revision,statement_source.pk,[adjustment.pk],
                           'Use the exact synthetic reporting adjustment.')
        mapping_review=None
        adjustment_id=adjustment.pk
    work=fixture['work']
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    status = 'configuration_needed' if mode=='setup' else 'waiting'
    if (work.status!=status or FinanceDocumentBinding.objects.filter(run__case=case).exists()
            or Publication.objects.filter(factory_work=work).exists()):
        raise RuntimeError('The sample must wait for the exact independent reviews or declared missing setup.')
    return event(preparer,case,MARKER,work=work.pk,reviewer=reviewer.pk,source=statement_source.pk,
                 source_review=source_review.pk,proof=proof.pk,configuration=fixture['configuration'].pk,
                 mapping=policies['D06.account_bu_maps'].pk,mapping_review=mapping_review.pk if mapping_review else None,
                 adjustment=adjustment_id,baseline_reviewer=baseline_reviewer.pk)


@transaction.atomic
def prepare(mode):
    if os.getenv(GUARD)!='1' or mode not in LABELS:
        raise RuntimeError('Choose the explicit synthetic setup or reviews station.')
    reviewer=fixture_reviewer()
    cid=uuid5(NAMESPACE_URL,f'{TENANT}:{mode}')
    attrs={'tenant':TENANT,'title':LABELS[mode],'kind':'project','synthetic':True}
    case,created=Case.objects.get_or_create(pk=cid,defaults=attrs)
    if any(getattr(case,key)!=value for key,value in attrs.items()):
        raise RuntimeError('Preserve the original exact synthetic accounting case.')
    owner_name=f'sample-accounting-station-preparer-{mode}'
    if created:
        owner=get_user_model().objects.create_user(owner_name)
        marker=seed(case,owner,reviewer,mode)
    else:
        marker=Audit.objects.select_related('actor').get(case=case,action=MARKER,actor__username=owner_name)
    owner=marker.actor
    data=marker.data
    if (data['reviewer']!=reviewer.pk or owner.has_usable_password() or not owner.is_active
            or owner.is_staff or owner.is_superuser or Grant.objects.filter(user=owner).exclude(case=case).exists()
            or set(Grant.objects.filter(case=case,user=reviewer,active=True).values_list('action',flat=True))!=TRIAL_ACTIONS):
        raise RuntimeError('Preserve the separate isolated preparer and current Trial review permissions.')
    work=FactoryWork.objects.get(pk=data['work'],case=case,actor=owner,definition=accounting.DEFINITION)
    exact_source=FinanceSource.objects.get(pk=data['source'],case=case,actor=owner)
    FinanceReview.objects.get(pk=data['source_review'],case=case,source=exact_source,verdict='approve',
                              evidence_id=data['proof'],actor_id=data['baseline_reviewer'])
    if mode=='setup':
        FinanceReview.objects.get(pk=data['mapping_review'],case=case,configuration_id=data['mapping'],verdict='approve',
                                  evidence_id=data['proof'],actor_id=data['baseline_reviewer'])
        if (work.status!='configuration_needed' or not FinanceRun.objects.filter(source=exact_source,kind='mapping').exists()
                or FinanceRun.objects.filter(source=exact_source,kind__in=['allocation','formula','statement']).exists()):
            raise RuntimeError('Keep the exact reviewed input and mapping preview while the two policy slots are open.')
    if Publication.objects.filter(factory_work=work).exists():
        raise RuntimeError('This acceptance specimen must remain unpublished.')
    open_reviews=list(HumanTask.objects.filter(case=case, context__work=work.pk, status='open',
        kind='factory_accounting_review').values_list('pk','context__purpose'))
    return {**data,'case':str(case.pk),'mode':mode,'preserved':not created,'open_reviews':open_reviews,
            'work_path':reverse('factory_detail',args=[work.pk]),'decision':reverse('factory_invoice_decision',args=[work.pk]),
            'rules':reverse('workspace_settings',args=[case.pk])+'?area=finance'}


def run(mode):
    if (os.getenv('RAILWAY_PROJECT_ID'),os.getenv('RAILWAY_ENVIRONMENT_NAME'),os.getenv('RAILWAY_SERVICE_ID'),
            os.getenv(GUARD))!=(PREVIEW_PROJECT,'design-acceptance','00c14ca1-5361-4bee-97a5-2ec7aba6ef18','1'):
        raise RuntimeError('Use only the isolated Railway acceptance checks service.')
    database=os.getenv('PGDATABASE','')
    if not database or database.lower().startswith('test_') or connection.vendor!='postgresql':
        raise RuntimeError('Select the existing PostgreSQL preview database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0]!=database:
            raise RuntimeError('The configured preview database must match the connection.')
    print(GUARD+'='+json.dumps(prepare(mode)),flush=True)
