from django.http import Http404
from django.utils import timezone

from apps.core import account_delivery, alerts
from apps.core.alert_models import AlertPreference, AlertRead

from .http import BOOLEAN, DATETIME, REVISION, TEXT, array, choice, endpoint, obj


ALERT = obj({'id': TEXT, 'title': TEXT, 'subject': {'type': 'string'}, 'detail': {'type': 'string'},
             'group': choice('action', 'update'), 'read': BOOLEAN, 'django_url': TEXT})
PREFERENCES = obj({'revision': REVISION, 'email_requested': BOOLEAN, 'whatsapp_requested': BOOLEAN})
STATUS = obj({**PREFERENCES['properties'], 'email_ready': BOOLEAN, 'whatsapp_ready': BOOLEAN})


@endpoint(response=obj({'items': array(ALERT), 'as_of': DATETIME}), summary='Read current personal alerts')
def inbox(request):
    return {'as_of': timezone.now(), 'items': [
        {'id': row['key'], 'title': row['label'], 'subject': row['subject'], 'detail': row['detail'],
         'group': row['group'], 'read': not row['unread'], 'django_url': row['url']}
        for row in alerts.items(request.user)
    ]}


@endpoint(method='POST', request=obj({}), response=obj({'id': TEXT, 'read': BOOLEAN}),
          summary='Acknowledge an alert for the signed-in user')
def mark_read(request, notification_id, *, body):
    if len(notification_id) != 64 or not any(row['key'] == notification_id for row in alerts.items(request.user)):
        raise Http404
    AlertRead.objects.get_or_create(actor=request.user, key=notification_id)
    return {'id': notification_id, 'read': True}


def preference_data(actor):
    record = AlertPreference.objects.filter(actor=actor).first()
    routes = account_delivery.channel_routes(actor)
    return {'revision': record.revision if record else 1,
            'email_requested': bool(record and record.email_requested),
            'whatsapp_requested': bool(record and record.whatsapp_requested),
            'email_ready': 'email' in routes, 'whatsapp_ready': 'whatsapp' in routes}


@endpoint(response=STATUS, summary='Read personal preferences and currently verified channels')
def preferences(request):
    return preference_data(request.user)


@endpoint(method='POST', request=PREFERENCES, response=STATUS, summary='Save personal alert preferences')
def save_preferences(request, *, body):
    alerts.save_preferences(request.user, body['revision'], body['email_requested'], body['whatsapp_requested'])
    return preference_data(request.user)
