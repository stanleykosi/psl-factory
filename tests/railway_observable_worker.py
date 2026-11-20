"""Acceptance-only time windows for real worker claims and receipts on the preview."""
import os
from time import sleep
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command

from adapters.project_archive import SyntheticObjectArchive
from adapters.publications import InternalPublicationAdapter
from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from apps.documents.models import PublicationJob
from apps.workflows import factory
from apps.workflows.models import FactoryWork
from tests.railway_batch_walkthrough_seed import OBSERVABLE_PREPARATION, PREPARATION, PREVIEW_PROJECT, TENANT


WINDOW_SECONDS = 10
STEPS = {
    'accounts_observable': {'ACT04', 'ACT09'},
    'assets_observable': {'ACT04'},
    'schedules_observable': {'ACT04'},
    'forecast_observable': {'ACT04'},
}


def require_acceptance():
    environment = (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'),
                   os.getenv('PSL_ACCEPTANCE_OBSERVABLE_WORKER'))
    if environment != (PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('Observable worker requires the explicitly enabled Railway acceptance project.')


def sample_key(work):
    case = work.case
    if not case.synthetic or case.tenant != TENANT:
        return None
    for key, (template, title) in OBSERVABLE_PREPARATION.items():
        if case.title == title and work.definition == PREPARATION[template][0]:
            return key
    return None


class ObservableCoordinator(SyntheticFactoryCoordinator):
    def __init__(self, steps):
        self.steps = steps

    def choose(self, context):
        if len(context['eligible']) == 1 and context['eligible'][0] in self.steps:
            sleep(WINDOW_SECONDS)
        return super().choose(context)


def work_progress():
    require_acceptance()
    normal = factory.run_once

    def one_step(work_id, provider=None, adapter=None):
        work = FactoryWork.objects.select_related('case').get(pk=work_id)
        steps = STEPS.get(sample_key(work))
        if steps and provider is None:
            try:
                _, profile = factory.profile(work)
            except (PermissionDenied, ValidationError):
                pass
            else:
                if profile['provider'] == 'synthetic_factory_v1':
                    provider = ObservableCoordinator(steps)
        return normal(work_id, provider=provider, adapter=adapter)

    with patch.object(factory, 'run_once', side_effect=one_step):
        call_command('work_factory_progress')


def work_publications():
    require_acceptance()
    normal = InternalPublicationAdapter.deliver

    def deliver(adapter, job_id, fence):
        publication = PublicationJob.objects.select_related('publication__factory_work__case').get(pk=job_id).publication
        if publication.factory_work_id and sample_key(publication.factory_work) == 'accounts_observable':
            sleep(WINDOW_SECONDS)
        return normal(adapter, job_id, fence)

    with patch.object(InternalPublicationAdapter, 'deliver', deliver):
        call_command('work_publications', limit=20)


def work_archive():
    require_acceptance()
    normal = SyntheticObjectArchive.copy

    def copy(adapter, file, data):
        if sample_key(file.plan.work) == 'archive_observable':
            sleep(WINDOW_SECONDS)
        return normal(adapter, file, data)

    with patch.object(SyntheticObjectArchive, 'copy', copy):
        call_command('work_archive_files', limit=10)
