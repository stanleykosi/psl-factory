"""Personal, private notifications and original-effect reconciliation."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.signing import Signer
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from adapters.account_delivery import receipt_for

from . import alerts
from .alert_models import AccountDelivery, AlertPreference, RecoveryAttempt, SampleAccountInbox

RECOVERY_TTL = timedelta(minutes=30)
RECOVERY_COOLDOWN = timedelta(minutes=2)
LOOKUP_INTERVAL = timedelta(minutes=1)
State = AccountDelivery.State


def fingerprint(label, *parts):
    return salted_hmac(f'factory.account.{label}.v1', repr(parts), algorithm='sha256').hexdigest()


def channel_routes(actor):
    runtime = settings.CONTACT_DELIVERY
    if not runtime or not actor.is_active:
        return {}
    for route in runtime.routes:
        if route.username != actor.get_username():
            continue
        if not runtime.synthetic and (actor.pk != route.account_id or actor.email.casefold() != route.email.casefold()):
            return {}
        return {channel: (address, fingerprint('route', actor.pk, channel, address, runtime.origin,
                                             runtime.relay, runtime.synthetic, route.recovery))
                for channel, address in [('email', route.email), ('whatsapp', route.whatsapp)] if address}
    return {}


def account_version(actor):
    return fingerprint('state', actor.pk, actor.get_username(), actor.email, actor.password, actor.last_login)


@transaction.atomic
def queue_recovery(email):
    now = timezone.now()
    runtime = settings.CONTACT_DELIVERY
    route = next((r for r in runtime.routes if r.recovery and r.email.casefold() == email.casefold()), None) if runtime else None
    if not route:
        return
    key = fingerprint('request', email.casefold())
    cooldown, _ = RecoveryAttempt.objects.select_for_update().get_or_create(key=key, defaults={'until': now})
    if cooldown.until > now:
        return
    cooldown.until = now + RECOVERY_COOLDOWN
    cooldown.save(update_fields=['until'])
    actor = get_user_model().objects.filter(username=route.username, is_active=True).first()
    if not actor or not actor.has_usable_password():
        return
    email_route = channel_routes(actor).get('email')
    if email_route:
        AccountDelivery.objects.create(actor=actor, purpose='recovery', channel='email',
                                       source=fingerprint('recovery', key, now.isoformat()),
                                       route_pin=fingerprint('recovery_route', email_route[1], account_version(actor)),
                                       next_check=now)


def recovery_token(row):
    return Signer(salt='factory.password.recovery.v1').sign(str(row.pk))


def recovery_path(row):
    return f'{reverse("factory_recovery_token")}#{recovery_token(row)}'


def valid_reset(row, actor):
    route = channel_routes(actor).get('email')
    return bool(route and actor.has_usable_password() and row.actor_id == actor.pk
                and row.purpose == 'recovery' and row.state in {State.UNCERTAIN, State.DELIVERED}
                and not row.consumed_at and timezone.now() < row.created_at + RECOVERY_TTL
                and constant_time_compare(row.route_pin, fingerprint('recovery_route', route[1], account_version(actor))))


@transaction.atomic
def queue_alerts(actor):
    prefs = AlertPreference.objects.select_for_update().filter(actor=actor).first()
    if not prefs:
        return
    routes = channel_routes(actor)
    channels = [channel for channel in routes if getattr(prefs, f'{channel}_requested')]
    if not channels:
        return
    now = timezone.now()
    for item in alerts.items(actor):
        if not item['unread']:
            continue
        for channel in channels:
            AccountDelivery.objects.get_or_create(actor=actor, purpose='alert', channel=channel, source=item['key'],
                                                 defaults={'route_pin': routes[channel][1], 'next_check': now})


def message(row, actor):
    route = channel_routes(actor).get(row.channel)
    if not route:
        return None
    runtime = settings.CONTACT_DELIVERY
    if row.purpose == 'recovery':
        if (timezone.now() >= row.created_at + RECOVERY_TTL or not actor.has_usable_password()
                or not constant_time_compare(row.route_pin, fingerprint('recovery_route', route[1], account_version(actor)))):
            return None
        url = runtime.origin + recovery_path(row)
        subject = 'Reset your PSL Factory password'
        body = f'Use this link to reset your password within 30 minutes.\n\n{url}'
    else:
        if not constant_time_compare(row.route_pin, route[1]):
            return None
        prefs = AlertPreference.objects.select_for_update().filter(actor=actor).first()
        if not prefs or not getattr(prefs, f'{row.channel}_requested'):
            return None
        if not any(item['key'] == row.source and item['unread'] for item in alerts.items(actor)):
            return None
        subject = 'You have an alert in PSL Factory'
        body = f'Sign in to review your alerts.\n\n{runtime.origin}{reverse("design_alerts")}'
    return {'channel': row.channel, 'destination': route[0], 'subject': subject, 'body': body}


@transaction.atomic
def claim():
    now = timezone.now()
    row = (AccountDelivery.objects.select_for_update(skip_locked=True).filter(
        state__in=(State.QUEUED, State.UNCERTAIN), next_check__lte=now,
    ).order_by('next_check', 'id').first())
    if not row:
        return None
    actor = row.actor
    payload = message(row, actor) if row.state == State.QUEUED else None
    if row.state == State.QUEUED and not payload:
        row.state = State.HELD
        row.save(update_fields=['state'])
        return row, None
    if payload:
        row.fingerprint = fingerprint('message', *payload.values())
        row.relay_pin = relay_pin(settings.CONTACT_DELIVERY)
    row.state = State.UNCERTAIN
    row.next_check = now + LOOKUP_INTERVAL
    row.save(update_fields=['state', 'fingerprint', 'relay_pin', 'next_check'])
    return row, payload


def relay_pin(runtime):
    return fingerprint('relay', runtime.relay, runtime.synthetic)


def read_sample_receipt(row, payload):
    if payload:
        SampleAccountInbox.objects.get_or_create(delivery=row, defaults={
            'fingerprint': fingerprint('message', *payload.values()),
        })
    if SampleAccountInbox.objects.filter(delivery=row, fingerprint=row.fingerprint).exists():
        return f'test-{row.pk}'
    return None


def work(limit):
    runtime = settings.CONTACT_DELIVERY
    if not runtime:
        return 0
    users = get_user_model().objects.filter(is_active=True).filter(Q(alertpreference__email_requested=True) |
                                                                Q(alertpreference__whatsapp_requested=True))
    for actor in users.filter(username__in=[r.username for r in runtime.routes]).iterator(chunk_size=50):
        queue_alerts(actor)
    checked = 0
    for _ in range(limit):
        claimed = claim()
        if not claimed:
            break
        row, payload = claimed
        checked += 1
        if row.state == State.HELD or not constant_time_compare(row.relay_pin, relay_pin(runtime)):
            continue
        if runtime.synthetic:
            receipt = read_sample_receipt(row, payload)
        else:
            receipt = receipt_for(runtime, row.pk, row.fingerprint,
                                  payload=dict(payload, fingerprint=row.fingerprint) if payload else None)
        if receipt:
            done = timezone.now()
            AccountDelivery.objects.filter(pk=row.pk, next_check=row.next_check, state=State.UNCERTAIN).update(
                state=State.DELIVERED, receipt=receipt, delivered_at=done,
            )
    RecoveryAttempt.objects.filter(until__lt=timezone.now() - RECOVERY_TTL).delete()
    return checked
