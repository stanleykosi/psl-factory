"""Guarded synthetic question fixtures; never reset an existing question or approval."""
import json
import os
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.core.models import Case,Evidence
from apps.core.management.commands.seed_demo import ACTIONS
from apps.identity.models import Grant
from apps.finance.payroll_models import PayrollPublication
from apps.finance.payroll_question_models import PayrollReportQuestion
from apps.finance import payroll_questions as domain
from apps.policy.payroll_validators import QUESTION_ROUTE
from apps.policy.services import resolve
from tests.payroll_helpers import fixture,pipeline,policy
from tests.helpers import rev

TENANT='design-payroll-hr-question-walkthrough'


@transaction.atomic
def prepare():
    if os.environ.get('PSL_PAYROLL_QUESTION_FIXTURE')!='1':raise RuntimeError('Explicit synthetic question fixture guard required')
    users=get_user_model().objects
    operator=users.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
    recipient_case=Case.objects.get(tenant='design-payroll-recipient-walkthrough',synthetic=True)
    publication=PayrollPublication.objects.get(request__case=recipient_case)
    source_owner=users.get(username='sample-payroll-private-hr',is_active=True)
    if resolve(QUESTION_ROUTE,recipient_case).status!='ACTIVE':
        proof=Evidence.objects.filter(case=recipient_case,kind='policy_decision').latest('pk')
        policy({'owner':source_owner,'case':recipient_case,'e':{'policy_decision':proof}},QUESTION_ROUTE,{
            'owner_id':source_owner.pk,'action':'answer_aggregate_question',
            'disclosure':'report_identity_and_topic_only','reply':'closed_codes_only'})
    previous=Case.objects.filter(tenant=TENANT).first()
    if previous:
        question=PayrollReportQuestion.objects.get(case=previous)
        return {'already_prepared':True,'recipient_case':str(recipient_case.pk),'recipient_report':publication.pk,
                'hr_case':str(previous.pk),'hr_question':question.pk}
    case=Case.objects.create(tenant=TENANT,title='SAMPLE HR response to a staff-cost question',kind='project',synthetic=True)
    for action in ACTIONS:Grant.objects.get_or_create(case=case,user=operator,action=action)
    def principal(role):return users.create_user('sample-payroll-question-'+role,first_name='SAMPLE question '+role)
    f=fixture(employee_ids=['PRIVATE-QUESTION-001','PRIVATE-QUESTION-002'],context=(operator,case),principal=principal)
    *_,report=pipeline(f,prefix='SAMPLE-simulated-question-report')
    policy(f,QUESTION_ROUTE,{'owner_id':operator.pk,'action':'answer_aggregate_question',
        'disclosure':'report_identity_and_topic_only','reply':'closed_codes_only'})
    from uuid import uuid4
    question=domain.record(f['manager'],case.pk,report.pk,'staff_source_review',uuid4(),rev(case))
    domain.advance(f['manager'],case.pk,question.pk,'dispatched',0,rev(case))
    return {'fixture':'synthetic-report-and-delivered-HR-question','recipient_case':str(recipient_case.pk),
        'recipient_report':publication.pk,'recipient_permissions_changed':False,
        'hr_case':str(case.pk),'hr_report':report.pk,'hr_question':question.pk,
        'seeded_reviews_and_question_dispatch':'Explicitly simulated native setup, not browser or operational human evidence',
        'hr_response_created':False,'question_receipt_created':False,'operational_policy_values_adopted':False}


print('PSL_PAYROLL_QUESTION_FIXTURE='+json.dumps(prepare()))
