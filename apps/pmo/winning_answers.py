"""Read individual reviewed answers released by the source project for a specific bid."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.agents.assistant_access import WINNING, permission
from apps.core.workbench import granted
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.models import Configuration
from .models import RFPDisposition
from .rfp_outcomes import assert_public_submission_sources, historical_submission


def options(actor, destination):
    configured = Configuration.objects.filter(component=WINNING,
        envelope__value__answers__contains=[{'destination': str(destination.pk)}]).values('case_id')
    projects = granted(actor, ['case.read', 'rfp.read']).filter(pk__in=configured,
        synthetic=destination.synthetic, tenant=destination.tenant).exclude(pk=destination.pk)
    choices = []
    for project in projects.order_by('pk').iterator():
        config = permission(project, WINNING)
        if config is None:
            continue
        for entry in config.envelope['value']['answers']:
            if entry['destination'] != str(destination.pk):
                continue
            pin = {'policy': config.pk, 'source': str(project.pk), **entry}
            try:
                citation = read(actor, destination, pin)
            except (ValidationError, PermissionDenied):
                continue
            choices.append((digest(pin), pin, citation))
    return choices


def read(actor, destination, pin):
    from apps.core.models import Case

    project = Case.objects.filter(pk=pin['source'], tenant=destination.tenant, synthetic=destination.synthetic).first()
    if project is None or pin['destination'] != str(destination.pk):
        raise PermissionDenied
    for action in ('case.read', 'rfp.read'):
        require(actor, project, action)
    config = permission(project, WINNING)
    entry = {key: pin[key] for key in ('destination', 'outcome_id', 'requirement')}
    if not config or config.pk != pin['policy'] or entry not in config.envelope['value']['answers']:
        raise PermissionDenied('This answer is no longer released to this project.')
    disposition = RFPDisposition.objects.select_related('outcome__submission__response', 'rfp').filter(
        rfp__case=project, kind='route_a', outcome_id=pin['outcome_id'], outcome__result='won').first()
    if not disposition:
        raise ValidationError('The original winning outcome is unavailable.')
    submission = disposition.outcome.submission
    assert_public_submission_sources(project, submission)
    response = historical_submission(project, submission)
    row = next((r for r in response.matrix if r['key'] == pin['requirement'] and r['disposition'] == 'addressed'), None)
    if not row or not row['response'].strip():
        raise ValidationError('The original submission contains no accepted answer for this requirement.')
    return {'label': f'{disposition.rfp.reference} · winning response {response.number} · {row["key"]}',
            'fact': row['response'], 'url': reverse('rfp', args=[project.pk]),
            'record': {'field': 'winning_answer', 'pk': response.pk, 'outcome': disposition.outcome_id,
                       'requirement': row['key'], 'permission': config.pk}}
