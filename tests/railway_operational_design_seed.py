"""Seed the named Railway acceptance lane using real domain services and synthetic inputs."""
import json
import os
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core.client_contacts import save as save_contact
from apps.core.models import Case, ClientContactRevision
from apps.core.services import add_evidence
from apps.finance import hrfinance, payroll
from apps.finance.models import InvoiceIssue
from apps.identity import intake, staff
from apps.identity.actions import ACTIONS
from apps.identity.models import CaseIntake, Grant
from apps.pmo.meetings import create_action
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.reminder_validators import COMPONENT
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from tests import payroll_helpers
from tests.helpers import rev
from tests.test_design_payroll_sources import COLUMNS

if os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance':
    raise SystemExit('Exact design acceptance environment required')

users = get_user_model()
actor = users.objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
tenant = 'design-browser-lifecycle'


def evidence(case, kind, body):
    return add_evidence(actor, case.pk, kind, body, 'synthetic:design-lifecycle-acceptance')


def activate(config):
    transition(actor, config.pk, 'validated')
    transition(actor, config.pk, 'active')


def billing():
    case = Case.objects.get(tenant='design-browser-acceptance', title='Browser acceptance client billing and receipts', synthetic=True)
    for action in [action for action in ACTIONS if action.startswith('finance.reminder.')]:
        Grant.objects.get_or_create(case=case, user=actor, action=action)
    issue = InvoiceIssue.objects.get(invoice__case=case, invoice__reference='BROWSER-INVOICE-001')
    old = ClientContactRevision.objects.filter(case=case, purpose='billing').first()
    if old is None:
        proof = evidence(case, 'policy_decision', 'Synthetic delivery fixture. The simulator performs no outgoing call.')
        row = save_contact(actor, case, 'billing', {'revision':rev(case), 'evidence':proof, 'customer':issue.invoice.preparation.coverage.customer,
            'client_name':'Synthetic client', 'name':'Synthetic billing desk', 'email':'browser-billing@example.invalid','role':'Billing'})
        activate(draft_operator_policy(actor, case.pk, COMPONENT, {'contact_revision_ids':[row.pk], 'sender_ids':[actor.pk],
            'receipt_recorder_ids':[actor.pk], 'mode':'synthetic_inbox', 'days_after_due':0, 'minimum_days_between':0},
            proof.pk, timezone.now()-timedelta(seconds=1)))
    return {'case':str(case.pk),'issue':issue.pk}


def staff_lifecycle():
    init = CaseIntake.objects.filter(tenant=tenant, reference='staff-lifecycle').first()
    if init:
        return {'case':str(init.case_id)}
    root = users.objects.create_superuser('design-browser-staff-bootstrap')
    actions = ['case.read','evidence.add','policy.configure','policy.activate','action.manage','action.own']
    scope = {'format':'psl.tenant-access/v1','create_cases':True,'manage_access':True,'kinds':['project'],
             'allowed_actions':actions,'initial_actions':actions,'classification':'synthetic',
             'staff_lifecycle':{'invite_minutes':1440,'allow_invite':True,'allow_deactivation':True}}
    intake.provision(root,actor,tenant,scope,timezone.now()+timedelta(days=3),True,'Synthetic staff browser acceptance only')
    root.is_active = False
    root.save(update_fields=['is_active'])
    case = intake.create_case(actor,tenant,'staff-lifecycle','Browser acceptance staff lifecycle','project')
    _, token = staff.invite(actor,case.pk,'design-staff-example','Synthetic staff example','staff-example@example.invalid',
                           ['case.read','action.own'],rev(case))
    person = staff.accept(token,'Synthetic fixture only 8116')
    person.set_unusable_password()
    person.save(update_fields=['password'])
    proof = evidence(case,'policy_decision','Synthetic reassignment role and proof for browser acceptance')
    activate(draft_roles(actor,case.pk,[{'role':'PMO Lead','user_id':u.pk} for u in [actor,person]],
                         proof.pk,timezone.now()-timedelta(seconds=1)))
    action = create_action(actor,case.pk,'BROWSER-STAFF-ACTION','Verify synthetic staff handover',person.pk,
                           timezone.now()+timedelta(days=2),proof.pk,'Synthetic reassignment example',rev(case))
    return {'case':str(case.pk),'person':person.pk,'action':action.pk}


def payroll_sources():
    case, created = Case.objects.get_or_create(tenant=tenant, title='Browser acceptance payroll sources', kind='project', synthetic=True)
    if not created:
        return {'case':str(case.pk)}
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in dict.fromkeys(ACTIONS)])
    with patch.object(payroll_helpers, 'setup_case', return_value=(actor,case)):
        data = payroll_helpers.fixture(principal=lambda name: users.objects.create_user('design-browser-payroll-'+name), payroll_layouts=[
           {'format':'csv','delimiter':',','columns':COLUMNS},
           {'format':'xlsx','sheet':'Payroll','columns':COLUMNS},
        ])
    combined = payroll_helpers.combined(data)
    payroll_helpers.approve(data,combined)
    match = payroll.match(data['preparer'],case.pk,combined.pk,data['hr'].pk,'browser-match',rev(case))
    link = payroll.hr_correction(data['preparer'],case.pk,match.pk,'browser-correction',data['e']['hr_correction_request'].pk,rev(case))
    raw = deepcopy(data['hr_config']['export'])
    raw['extracted_at'] = timezone.now().isoformat()
    new = hrfinance.capture(actor,case.pk,data['hr_contract'].pk,'browser-successor',json.dumps(raw),rev(case))
    ev = evidence(case,'hr_correction_response','Synthetic HR decision proof for the exact corrected export')
    return {'case':str(case.pk),'followup':link.pk,'successor':new.pk,'evidence':ev.pk,'request':data['request'].pk}


for key, seed in [('reminder',billing),('staff',staff_lifecycle),('payroll',payroll_sources)]:
    try:
        with transaction.atomic():
            outcome = seed()
        print('PSL_LIFECYCLE_FIXTURE='+json.dumps({'key':key,**outcome}),flush=True)
    except Exception as exc:
        print('PSL_LIFECYCLE_FIXTURE_ERROR='+json.dumps({'key':key,'type':type(exc).__name__,'reason':str(exc)[:250]}),flush=True)
