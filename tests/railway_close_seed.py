"""Create named synthetic decision and recovery examples in design-acceptance only."""
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from adapters.publications import PublicationTimeoutAfterAccept
from apps.core.models import Case
from apps.documents.controlled import request_review, reserve_publication, review_version
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationJob, PublicationReceipt
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.pmo.gates import record_gate, verify_gate
from apps.workflows import factory, factory_accounting
from apps.workflows.models import HumanTask
from apps.workflows.services import run_once
from tests import document_helpers, finance_analysis_helpers, test_delivery
from tests import test_factory_closure as closure
from tests import test_factory_delivery as release
from tests import test_factory_go_live as go_live
from tests.factory_accounting_helpers import configured
from tests.helpers import rev
from tests.test_factory_escalation import FactoryEscalationTests
from tests.test_factory_forecast import PublicationTimeoutBeforeAcceptance
from tests.test_factory_leadership import FactoryLeadershipTests


def exact_publish(fixture, version):
    actor, case = fixture.actor, fixture.case
    if version.audience == 'client':
        request_review(actor, case.pk, version.pk, rev(case))
        review_version(actor, case.pk, version.pk, 'approve', 'Synthetic exact client projection', rev(case))
    publication = reserve_publication(actor, case.pk, version.pk, rev(case))
    run_publication_once(job_id=publication.job.pk)
    return PublicationReceipt.objects.get(publication=publication)


def unclear_delivery(work, adapter=None):
    adapter = adapter or PublicationTimeoutAfterAccept()
    for _ in range(24):
        job = PublicationJob.objects.filter(publication__factory_work=work).first()
        if job and job.status == 'pending':
            run_publication_once(adapter, job_id=job.pk)
            job.refresh_from_db()
        if job and job.status == 'unknown':
            return PublicationReceipt.objects.filter(publication=job.publication).first()
        if not factory.run_once(work.pk, adapter=adapter):
            break
    raise RuntimeError('Fixture did not preserve an uncertain original delivery')


def release_work(recovery):
    f = release.setup()
    if recovery:
        release.release_sources(f)
        factory.run_until_wait(f.work.pk)
        gate = record_gate(f.actor, f.case.pk, f.candidate.pk, 'qa_exit', 'BROWSER-QA-SUCCESSOR',
                           f.e['requirements'].pk, rev(f.case))
        verify_gate(f.actor, f.case.pk, gate.pk, rev(f.case))
    else:
        for kind in delivery.PLANNING:
            f.source(kind, {'requires_ui': False, 'client_signoff_required': False} if kind == 'ui_applicability' else {})
        factory.run_until_wait(f.work.pk)
    return f.work, {'evidence': f.e['plan'].pk, 'dossier': f.d.pk}


def release_return_work(_recovery):
    f, issue, fix = release.return_fixture()
    return f.work, {'evidence': f.e['plan'].pk, 'dossier': f.d.pk, 'issue': issue.issue_id, 'fix': fix.pk}


def release_owner_work(_recovery):
    work, details = release_work(False)
    Grant.objects.filter(case=work.case, user=work.actor, action='delivery.planning_decide').update(active=False)
    return work, details


@transaction.atomic
def supply_returned_release_prerequisites():
    from apps.workflows.models import FactoryWork

    work = FactoryWork.objects.get(case__tenant='design-browser-close-release-return-state', case__synthetic=True,
                                   actor__username='psl-agent-trial', definition='delivery-release/v1')
    f = test_delivery.DeliveryFixture()
    f.actor, f.case = work.actor, work.case
    f.d = delivery.dossier_for(f.case, work.request['dossier'])
    f.candidate = f.d.candidate
    f.e = {'requirements': f.candidate.requirements}
    approval = delivery.approved_plan(f.d)
    if not approval.data.get('issue_remedy'):
        raise RuntimeError('Expected the native approval after the sample issue fix')
    if not delivery.latest(f.d, 'glpi_request', False):
        meeting = test_delivery.record_meeting(f.actor,f.case.pk,'BROWSER-RETURN-KICKOFF','kickoff',timezone.now(),
            'Kickoff after the reviewed sample fix','Synthetic source-owned kickoff evidence',[f.actor.pk],[],
            f.e['requirements'].pk,rev(f.case))
        delivery.record_progress(f.actor,f.case.pk,f.d.pk,'kickoff',meeting.evidence_id,'Actual synthetic kickoff',rev(f.case),meeting.pk)
        f.gates(delivery.UPSTREAM_GATES)
        reference = 'SYNTHETIC-GLPI-RETURN-READY'
        delivery.record_release_request(f.actor,f.case.pk,f.d.pk,reference,f.e['requirements'].pk,
                                        'Independent synthetic release request',rev(f.case))
        f.gates(delivery.GLPI_GATES, reference)
    print('PSL_CLOSE_FIXTURE=' + json.dumps({'key': 'release-return-prerequisites', 'work': work.pk,
                                           'approval': approval.pk}), flush=True)


def invoice_reconciliation_work(_recovery):
    from apps.finance import invoice_delivery
    from apps.finance.models import InvoiceJob
    from tests import factory_helpers
    from tests.obligation_helpers import factory_approve_identified

    f = factory_helpers.fixture()
    work = f['work']
    factory.run_until_wait(work.pk)
    factory_approve_identified(f)
    factory.run_once(work.pk)
    job = InvoiceJob.objects.get(invoice__case=f['case'], kind='issue')
    pk, fence = invoice_delivery.claim(case_id=f['case'].pk, job_id=job.pk)
    invoice_delivery.finish(pk, fence, 'unknown', 'Synthetic provider response unavailable')
    factory.run_until_wait(work.pk)
    return work, {'job': job.pk, 'invoice': job.invoice_id}


def schedule_review_work(_recovery):
    from tests import schedule_helpers, test_factory_schedules

    operator, case = finance_analysis_helpers.setup_case()
    preparer = get_user_model().objects.create_user(username='schedule-preparer')
    Grant.objects.bulk_create([Grant(case=case, user=preparer, action=action) for action in dict.fromkeys(ACTIONS)])
    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(preparer, case)):
        data = schedule_helpers.fixture(reviewer=operator)
    scenario = test_factory_schedules.FactorySchedulesTests()
    with patch.object(test_factory_schedules, 'fixture', return_value=data):
        scenario.setUp()
    scenario.payload['rows'] = [schedule_helpers.row(data, 'supplement', '20', 'additive',
                                                     lines=[{'account': 'sales', 'amount': '20'}])]
    work = scenario.start()
    scenario.advance()
    return work, {'evidence': data['e']['finance_review'].pk, 'adjustment_evidence': data['e']['finance_adjustment'].pk}


def asset_review_work(_recovery):
    import copy
    from datetime import date, timedelta
    from tests import ppe_helpers, test_factory_ppe

    operator, case = finance_analysis_helpers.setup_case()
    preparer = get_user_model().objects.create_user(username='asset-preparer')
    Grant.objects.bulk_create([Grant(case=case, user=preparer, action=action) for action in dict.fromkeys(ACTIONS)])
    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(preparer, case)):
        data = ppe_helpers.fixture(reviewer=operator)
    body = copy.deepcopy(data['ppe']['body'])
    body['label_as_of'] = (date.fromisoformat(body['period_end']) + timedelta(days=1)).isoformat()
    data['register'] = ppe_helpers.capture(data, body)
    scenario = test_factory_ppe.FactoryPPETests()
    with patch.object(test_factory_ppe, 'fixture', return_value=data):
        scenario.setUp()
    work = scenario.start()
    scenario.advance()
    return work, {'evidence': data['e']['finance_review'].pk, 'basis': data['e']['ppe_basis_explanation'].pk,
                  'register': data['register'].pk}


@transaction.atomic
def supply_asset_correction():
    import copy
    from apps.core.services import add_evidence
    from apps.finance import ppe
    from apps.workflows import factory_ppe
    from apps.workflows.models import FactoryWork

    work = FactoryWork.objects.get(case__tenant='design-browser-close-asset-state-review', case__synthetic=True,
                                   definition=factory_ppe.DEFINITION)
    source, _ = factory_ppe.source(work, work.actor, False)
    original = factory_ppe.schedule(work)
    if original is None or ppe.latest(original, 'schedule').verdict!='return':
        raise RuntimeError('Expected a reviewed sample asset return in the browser')
    corrected = copy.deepcopy(source.payload)
    opening = add_evidence(work.actor,work.case_id,'ppe_opening','Synthetic corrected asset opening source supplied by the preparer.',
                           'synthetic:browser-asset-opening-correction')
    corrected['opening_evidence_id'] = opening.pk
    supplied = add_evidence(work.actor,work.case_id,'ppe_register',json.dumps(corrected), 'synthetic:browser-asset-register-correction')
    replacement = ppe.capture(work.actor,work.case_id,source.reference,supplied.pk,rev(work.case))
    print('PSL_CLOSE_FIXTURE=' + json.dumps({'key':'asset-source-correction','work':work.pk,'register':replacement.pk,
                                           'opening':opening.pk}), flush=True)


def go_live_work(recovery):
    f = go_live.setup()
    factory.run_until_wait(f.work.pk)
    facts = {}
    if recovery:
        go_live.review(f)
        receipt = unclear_delivery(f.work)
        pm = f.evidence('signature', 'Synthetic supplied PM sign-off for the exact go-live report')
        client = f.evidence('signature', 'Synthetic supplied client sign-off for the exact go-live report')
        facts = {'receipt': receipt.pk, 'pm': pm.pk, 'client': client.pk, 'attestation': f.attestation(receipt, pm, client)}
    return f.work, facts


def forecast_work(group, recovery=None):
    from apps.workflows import factory_forecast
    from tests import forecast_helpers
    from tests.billing_helpers import evidence
    from tests.test_factory_forecast import ForecastFactoryTests
    from tests.test_factory_group_forecast import GroupForecastFactoryTests

    actor, case = document_helpers.setup_case()
    with patch.object(forecast_helpers, 'setup_case', return_value=(actor, case)):
        fixture = GroupForecastFactoryTests() if group else ForecastFactoryTests()
        fixture.setUp()
        work = fixture.start()
        fixture.advance()
    if group:
        return work, {'recipient':fixture.reader.username,'version':factory_forecast.document(work).version_id}
    proof = evidence(actor, case, 'forecast_review', 'Synthetic Finance review of the exact selected forecast.')
    run = factory_forecast.calculation(work, actor)
    facts = {'evidence':proof.pk,'run':run.pk}
    if recovery:
        factory_forecast.human_action(actor,work.pk,work.revision,rev(case),fixture.scenario.pk,'review',
                                      {'run':run,'role':'Finance','verdict':'approve','evidence':proof,
                                       'reason':'Synthetic exact reviewed forecast before unclear delivery'})
        receipt = unclear_delivery(work,recovery)
        facts['receipt'] = receipt.pk if receipt else None
        facts['job'] = PublicationJob.objects.get(publication__factory_work=work).pk
    return work, facts


def forecast_recovery_work(recovery):
    adapter = PublicationTimeoutAfterAccept() if recovery else PublicationTimeoutBeforeAcceptance()
    return forecast_work(False, adapter)


@transaction.atomic
def supply_forecast_actuals():
    from tests.billing_helpers import evidence
    from apps.workflows import factory_forecast
    from apps.workflows.models import FactoryWork

    work = FactoryWork.objects.get(case__tenant='design-browser-close-forecast-management-review', case__synthetic=True,
                                   definition=factory_forecast.DEFINITION, status='verified')
    value = {'entity':'synthetic-company','account':'account-1','currency':'NGN','basis':'gross_cash',
             'source':'supplied-source','transaction':'BROWSER-FORECAST-ACTUAL','direction':'inflow',
             'amount':'15','occurred_on':timezone.localdate().isoformat()}
    statement = evidence(work.actor,work.case,'forecast_actual',json.dumps(value))
    verification = evidence(work.actor,work.case,'forecast_actual_verification',json.dumps(value))
    match = evidence(work.actor,work.case,'forecast_match','Synthetic source linking the bank entry to receipt-1.')
    print('PSL_CLOSE_FIXTURE=' + json.dumps({'key':'forecast-supplied-actual','work':work.pk,'scenario':factory_forecast.source(work,work.actor)[0].pk,
                                           'statement':statement.pk,'verification':verification.pk,'match':match.pk}), flush=True)


def closure_work(recovery):
    f = closure.setup()
    factory.run_until_wait(f.work.pk)
    if recovery:
        closure.approve(f)
        f.work.refresh_from_db()
        closure.closure.cancel(f.actor, f.work.pk, f.work.revision)
    return f.work, {'evidence': f.e['requirements'].pk}


def closure_alternative(blocked):
    f = closure.setup(known=not blocked)
    if not blocked:
        document_helpers.artifact(f.actor, f.case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                                  {'rules': [{'role': 'Head of PMO', 'actions': ['return']}]}, f.e['policy_decision'])
    factory.run_until_wait(f.work.pk)
    return f.work, {'evidence': f.e['requirements'].pk}


def escalation_work(recovery):
    fixture = FactoryEscalationTests()
    fixture.setUp()
    if recovery:
        fixture.ready()
        receipt = unclear_delivery(fixture.w)
        return fixture.w, {'receipt': receipt.pk}
    fixture.start()
    fixture.advance()
    return fixture.w, {}


def leadership_work(recovery):
    fixture = FactoryLeadershipTests()
    fixture.setUp()
    fixture.start_work()
    fixture.advance()
    if recovery:
        fixture.review()
        receipt = unclear_delivery(fixture.work)
        return fixture.work, {'receipt': receipt.pk}
    return fixture.work, {}


def accounting_work(recovery):
    actor, case, evidence, _, _, source, template, _ = finance_analysis_helpers.fixture()
    work = configured(actor, case, evidence, source, template, finance_analysis_helpers.METRICS)['work']
    factory.run_until_wait(work.pk)
    facts = {'evidence': evidence['finance_review'].pk}
    if recovery:
        task = HumanTask.objects.get(case=case, kind='factory_accounting_review', status='open')
        task = factory_accounting.claim(actor, task.pk, task.revision)
        factory_accounting.decide(actor, task.pk, task.revision, 'approve', facts['evidence'], 'Synthetic reviewed accounting output')
        facts['receipt'] = unclear_delivery(work).pk
    return work, facts


def restricted_finance_fixture(browser_role, *, staff=False, hr_receipt=True):
    from tests import bu_helpers, payroll_helpers

    operator, case = document_helpers.setup_case()
    manager = get_user_model().objects
    owner = manager.create_user(username='example-hr-owner')
    Grant.objects.bulk_create([Grant(case=case,user=owner,action=action) for action in dict.fromkeys(ACTIONS)])

    def principal(role):
        return operator if role==browser_role else manager.create_user(username='example-'+role)

    with patch.object(payroll_helpers,'setup_case',return_value=(owner,case)):
        f=payroll_helpers.fixture(employee_ids=['E900','E002'] if staff else None,
                                  principal=principal,preparer_receipt=hr_receipt)
    if staff:
        from apps.finance import payroll
        bu_helpers.configure(f)
        combined=payroll_helpers.combined(f)
        payroll_helpers.approve(f,combined)
        match=payroll.match(f['preparer'],case.pk,combined.pk,f['hr'].pk,'sample-bu-payroll-match',rev(case))
        payroll_helpers.approve(f,match)
        f['match']=match
    Grant.objects.get_or_create(case=case,user=f['manager'],action='factory.read')
    return f


def configure_restricted_work(f, name):
    from apps.policy.operator_drafts import draft_operator_policy
    from apps.policy.services import transition

    with open('fixtures/factory-'+name+'.json',encoding='utf-8') as stream:
        value=json.load(stream)
    value.pop('classification')
    config=draft_operator_policy(f['owner'],f['case'].pk,'OPS.factory_'+name+'_execution',value,
                                 f['e']['policy_decision'].pk,timezone.now())
    transition(f['owner'],config.pk,'validated')
    transition(f['owner'],config.pk,'active')


def business_unit_state(stage):
    from apps.policy.bu_validators import DISCLOSE
    from apps.workflows import factory_bu as bu
    from tests import bu_helpers

    roles={'review':'reviewer','publish':'preparer','receipts':'manager','held':'preparer'}
    f=restricted_finance_fixture(roles[stage],staff=True)
    configure_restricted_work(f,'bu')
    if stage=='held':
        bu_helpers.policy(f,DISCLOSE,dict(f['bu_config']['disclosure'],minimum_staff=10))
    rule=bu_helpers.rule(f)
    inputs={'mode':'staff','payroll_id':f['match'].pk,'source_id':None,'rule_ids':[rule.pk],'comparison':None}
    work=bu.start(f['preparer'],f['case'].pk,'BROWSER-BU',inputs,'Sample staff cost by business unit',rev(f['case']))
    facts={'rule':rule.pk,'evidence':f['e']['bu_review'].pk}
    if stage!='review':
        bu_helpers.review(f,rule)
        factory.run_until_wait(work.pk)
        result=bu.result(work);bu_helpers.review(f,result);facts['result']=result.pk
    if stage=='receipts':
        factory.run_until_wait(work.pk);work.refresh_from_db()
        published=bu.human_action(f['preparer'],work.pk,work.revision,rev(f['case']),'publish',{})
        facts['publication']=published.pk
    factory.run_until_wait(work.pk)
    if stage=='receipts':
        from apps.workflows.factory_progress import set_progress
        work.refresh_from_db();set_progress(f['preparer'],work.pk,work.revision,True)
    return work,facts


def payroll_state(stage):
    from apps.workflows import factory_payroll as payroll
    from tests.payroll_helpers import approve,capture

    roles={'review':'reviewer','receipt':'manager','publish':'preparer','hr':'preparer','followup':'reviewer'}
    f=restricted_finance_fixture(roles[stage],hr_receipt=stage!='hr')
    configure_restricted_work(f,'payroll')
    inputs={'input_ids':[item.pk for item in f['inputs']],'hr_snapshot_id':f['hr'].pk}
    work=payroll.start(f['preparer'],f['case'].pk,'BROWSER-PAYROLL',f['request'].pk,inputs,
                       'Sample payroll review',rev(f['case']))
    facts={'evidence':f['e']['payroll_review'].pk,'snapshot':f['hr'].pk,'hr_evidence':f['e']['hr_disclosure_decision'].pk}
    if stage!='review':
        for item in f['inputs']:approve(f,item)
        for kind in (['combine'] if stage=='hr' else ['combine','match','aggregate']):
            factory.run_until_wait(work.pk)
            approve(f,payroll.run(work,kind))
    if stage in ('receipt','followup'):
        factory.run_until_wait(work.pk);work.refresh_from_db()
        report=payroll.human_action(f['preparer'],work.pk,work.revision,rev(f['case']),'publish',{})
        facts['publication']=report.pk
        if stage=='followup':
            payroll.human_action(f['manager'],work.pk,work.revision,rev(f['case']),'receive',{'publication_id':report.pk})
            payroll.cancel(f['preparer'],work.pk,work.revision)
            replacement=capture(f,0,'sample-publication-correction',source_version='A-v2')
            facts['corrected_inputs']=[replacement.pk,f['inputs'][1].pk]
            return work,facts
    factory.run_until_wait(work.pk)
    if stage=='receipt':
        from apps.workflows.factory_progress import set_progress
        work.refresh_from_db();set_progress(f['preparer'],work.pk,work.revision,True)
    return work,facts


def ledger_state(stage):
    from datetime import timedelta
    from apps.workflows import factory_ledger as ledger
    from tests import ledger_helpers
    from tests.test_factory_ledger import FactoryLedgerTests

    operator,case=document_helpers.setup_case()
    if stage=='decide':
        preparer=get_user_model().objects.create_user(username='example-ledger-preparer')
        Grant.objects.bulk_create([Grant(case=case,user=preparer,action=action) for action in dict.fromkeys(ACTIONS)])
    else:
        preparer=operator
    with patch.object(ledger_helpers,'setup_case',return_value=(preparer,case)):
        f=ledger_helpers.fixture(reviewer=operator if stage=='decide' else None)
    example=FactoryLedgerTests();example.fixture_factory=lambda:f;example.setUp()
    if stage=='duplicate':
        ledger_helpers.capture(f)
    work=example.start();example.advance()
    native=ledger.lineage(work)
    facts={'review_evidence':f['e'].pk}
    if native:
        fields=['provider','realm','entity','source_reference','target_reference','transaction_date',
                'accounting_period','treatment_evidence_id']
        value={key:native.payload[key] for key in fields}
        value.update(state='found',observed_at=(timezone.now()-timedelta(seconds=1)).isoformat(),incumbent_version='sample-read-1')
        proof=ledger_helpers.evidence(f,'quickbooks_verification',value)
        facts.update(lineage=native.pk,observation=proof.pk)
        if stage=='decide':
            from apps.finance.ledger import verify
            verify(preparer,case.pk,native.pk,proof.pk,rev(case))
        fresh=ledger_helpers.evidence(f,'quickbooks_verification',dict(value,incumbent_version='sample-read-2'))
        facts['fresh_observation']=fresh.pk
    return work,facts


@transaction.atomic
def seed(key, setup, recovery):
    from tests import factory_helpers
    title = 'Browser acceptance ' + key.replace('-', ' ')
    case, created = Case.objects.get_or_create(tenant='design-browser-close-' + key, kind='project', title=title, synthetic=True)
    if not created:
        raise RuntimeError('This named fixture already exists')
    user_model = get_user_model()
    operator = user_model.objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    Grant.objects.bulk_create([Grant(case=case, user=operator, action=action) for action in dict.fromkeys(ACTIONS)])
    create_user = user_model.objects.create_user
    with (
        patch.object(document_helpers, 'setup_case', return_value=(operator, case)),
        patch.object(finance_analysis_helpers, 'setup_case', return_value=(operator, case)),
        patch.object(factory_helpers, 'setup_case', return_value=(operator, case)),
        patch.object(test_delivery, 'setup_case', return_value=(operator, case)),
        patch.object(test_delivery, 'run_once', side_effect=lambda: run_once(case_id=case.pk)),
        patch.object(test_delivery.DeliveryFixture, 'publish', exact_publish),
        patch.object(user_model.objects, 'create_user', side_effect=lambda username: create_user(username=f'close-{key}-{username}')),
    ):
        work, facts = setup(recovery)
    work.refresh_from_db()
    return {'work': work.pk, 'case': str(case.pk), 'status': work.status, **facts}


if (os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance'
        or os.environ.get('RAILWAY_PROJECT_ID') != 'f957481b-c6f7-43af-bc66-449a330a9d53'):
    raise SystemExit('Exact isolated acceptance environment required')

fixtures = [
    (name + ('-recovery' if recovery else '-decision'), build, recovery)
    for name, build in [('release', release_work), ('go-live', go_live_work), ('closure', closure_work),
                        ('escalation', escalation_work), ('leadership', leadership_work), ('accounts', accounting_work)]
    for recovery in (False, True)
]
selected = os.environ.get('PSL_CLOSE_FIXTURE_ONLY')
if selected == 'closure-states':
    fixtures = [('closure-return', closure_alternative, False), ('closure-blocked', closure_alternative, True)]
    selected = None
elif selected == 'review-states':
    fixtures = [('escalation-state-review', escalation_work, False),
                ('leadership-state-review', leadership_work, False),
                ('accounts-state-review', accounting_work, False)]
    selected = None
elif selected == 'release-return-state':
    fixtures = [('release-return-state', release_return_work, False)]
elif selected == 'invoice-reconciliation-state':
    fixtures = [('invoice-reconciliation-state', invoice_reconciliation_work, False)]
elif selected == 'finance-state-review':
    supply_returned_release_prerequisites()
    fixtures = [('invoice-reconciliation-state', invoice_reconciliation_work, False),
                ('schedule-state-review', schedule_review_work, False)]
    selected = None
elif selected == 'asset-state-review':
    fixtures = [('asset-state-review', asset_review_work, False), ('release-owner-state', release_owner_work, False)]
    selected = None
elif selected == 'asset-source-correction':
    supply_asset_correction()
    fixtures = []
elif selected == 'forecast-states':
    fixtures = [('forecast-management-review', forecast_work, False), ('forecast-group-review', forecast_work, True),
                ('forecast-original-delivery', forecast_recovery_work, True)]
    selected = None
elif selected == 'forecast-supplied-actual':
    supply_forecast_actuals()
    fixtures = [('forecast-missing-receipt', forecast_recovery_work, False)]
    selected = None
elif selected == 'forecast-lookup-only':
    fixtures = [('forecast-lookup-only', forecast_recovery_work, False)]
elif selected == 'restricted-finance-states':
    fixtures = [(prefix+'-'+stage, build, stage)
                for prefix,build,stages in [('business-units',business_unit_state,['review','publish','receipts','held']),
                                            ('payroll',payroll_state,['review','hr','publish','receipt']),
                                            ('ledger',ledger_state,['observe','decide','duplicate'])]
                for stage in stages]
    selected = None
elif selected == 'payroll-publication-followup':
    fixtures = [('payroll-publication-followup', payroll_state, 'followup')]
for key, build, recovery in fixtures:
    if selected and selected != key:
        continue
    try:
        result = seed(key, build, recovery)
    except Exception as exc:
        print('PSL_CLOSE_FIXTURE_ERROR=' + json.dumps({'key': key, 'type': type(exc).__name__, 'reason': str(exc)[:300]}), flush=True)
    else:
        print('PSL_CLOSE_FIXTURE=' + json.dumps({'key': key, **result}), flush=True)
