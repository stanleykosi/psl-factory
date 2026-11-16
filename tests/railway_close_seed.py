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
from tests.test_factory_leadership import FactoryLeadershipTests


def exact_publish(fixture, version):
    actor, case = fixture.actor, fixture.case
    if version.audience == 'client':
        request_review(actor, case.pk, version.pk, rev(case))
        review_version(actor, case.pk, version.pk, 'approve', 'Synthetic exact client projection', rev(case))
    publication = reserve_publication(actor, case.pk, version.pk, rev(case))
    run_publication_once(job_id=publication.job.pk)
    return PublicationReceipt.objects.get(publication=publication)


def unclear_delivery(work):
    for _ in range(24):
        job = PublicationJob.objects.filter(publication__factory_work=work).first()
        if job and job.status == 'pending':
            run_publication_once(PublicationTimeoutAfterAccept(), job_id=job.pk)
            job.refresh_from_db()
        if job and job.status == 'unknown':
            return PublicationReceipt.objects.get(publication=job.publication)
        if not factory.run_once(work.pk, adapter=PublicationTimeoutAfterAccept()):
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


def closure_work(recovery):
    f = closure.setup()
    factory.run_until_wait(f.work.pk)
    if recovery:
        closure.approve(f)
        f.work.refresh_from_db()
        closure.closure.cancel(f.actor, f.work.pk, f.work.revision)
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


@transaction.atomic
def seed(key, setup, recovery):
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
        patch.object(test_delivery, 'setup_case', return_value=(operator, case)),
        patch.object(test_delivery, 'run_once', side_effect=lambda: run_once(case_id=case.pk)),
        patch.object(test_delivery.DeliveryFixture, 'publish', exact_publish),
        patch.object(user_model.objects, 'create_user', side_effect=lambda username: create_user(username=f'close-{key}-{username}')),
    ):
        work, facts = setup(recovery)
    work.refresh_from_db()
    return {'work': work.pk, 'case': str(case.pk), 'status': work.status, **facts}


if os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance':
    raise SystemExit('Exact isolated acceptance environment required')

for name, build in [('release', release_work), ('go-live', go_live_work), ('closure', closure_work),
                    ('escalation', escalation_work), ('leadership', leadership_work), ('accounts', accounting_work)]:
    for recovery in (False, True):
        key = name + ('-recovery' if recovery else '-decision')
        selected = os.environ.get('PSL_CLOSE_FIXTURE_ONLY')
        if selected and selected != key:
            continue
        try:
            result = seed(key, build, recovery)
        except Exception as exc:
            print('PSL_CLOSE_FIXTURE_ERROR=' + json.dumps({'key': key, 'type': type(exc).__name__, 'reason': str(exc)[:300]}), flush=True)
        else:
            print('PSL_CLOSE_FIXTURE=' + json.dumps({'key': key, **result}), flush=True)
