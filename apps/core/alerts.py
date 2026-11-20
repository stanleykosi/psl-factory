"""Current alert projection and durable personal read state."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse

from apps.agents.assistant_models import AssistantTurn
from apps.agents.assistant_views import owned_conversations
from apps.documents.contracts import digest
from apps.workflows.factory_views import visible
from apps.workflows.models import FactoryProgress

from .alert_models import AlertPreference, AlertRead
from .presentation import workspace_name
from .workbench import work


def items(actor):
    from apps.pmo.rfp_followup import reminders
    from apps.workflows.factory_invoice_review import assigned_alerts
    rows = list(reminders(actor))
    rows.extend(assigned_alerts(actor))
    for item in work(actor, limit=8)['rows']:
        # Incumbent or fixed-charge settlement applies a further domain check.
        if item['kind'] == 'initiated_finance_intent':
            continue
        rows.append({'key': digest(['assignment', item]), 'label': item['label'],
                     'subject': workspace_name(item), 'detail': item['reference'],
                     'url': item['url'], 'group': 'action'})
    turns = AssistantTurn.objects.filter(conversation__in=owned_conversations(actor), status='answered').select_related(
        'conversation__case',
    ).defer('question', 'answer', 'sources').order_by('-created_at', '-pk')[:20]
    for turn in turns:
        rows.append({'key': digest(['answer', str(turn.pk)]), 'label': 'Assistant reply',
                     'subject': workspace_name(turn.conversation.case), 'detail': turn.conversation.persona.title(),
                     'url': reverse('assistant_thread', args=[turn.conversation_id]), 'group': 'update'})
    works = visible(actor).exclude(definition__in=['finance-payroll/v1', 'finance-bu/v1'])
    jobs = FactoryProgress.objects.filter(work__in=works, requested_by=actor, status='held').select_related(
        'work__case',
    ).order_by('-updated_at', '-pk')[:20]
    for job in jobs:
        rows.append({'key': digest(['held', job.pk, job.updated_at.isoformat()]), 'label': 'Background work needs attention',
                     'subject': workspace_name(job.work.case), 'detail': '',
                     'url': reverse('factory_detail', args=[job.work_id]), 'group': 'action'})
    seen = set(AlertRead.objects.filter(actor=actor, key__in=[row['key'] for row in rows]).values_list('key', flat=True))
    for row in rows:
        row['unread'] = row['key'] not in seen
    return rows


@transaction.atomic
def save_preferences(actor, revision, email, whatsapp):
    prefs, _ = AlertPreference.objects.get_or_create(actor=actor)
    prefs = AlertPreference.objects.select_for_update().get(pk=prefs.pk)
    if prefs.revision != revision:
        raise ValidationError('Preferences changed. Review the current settings before saving.')
    if (prefs.email_requested, prefs.whatsapp_requested) != (email, whatsapp):
        prefs.email_requested, prefs.whatsapp_requested = email, whatsapp
        prefs.revision += 1
        prefs.save(update_fields=['email_requested', 'whatsapp_requested', 'revision'])
