from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe, require_POST

from . import account_delivery, alerts
from .alert_models import AccountDelivery, AlertPreference, AlertRead


@login_required
@require_safe
@never_cache
def index(request):
    rows = alerts.items(request.user)
    group = request.GET.get('group', '')
    query = request.GET.get('q', '').strip()[:100]
    unread = request.GET.get('unread') == '1'
    if group in {'action', 'update'}:
        rows = [row for row in rows if row['group'] == group]
    if query:
        rows = [row for row in rows if query.casefold() in ' '.join(str(row[k]) for k in ('label', 'subject', 'detail')).casefold()]
    if unread:
        rows = [row for row in rows if row['unread']]
    return render(request, 'design/alerts.html', {'rows': rows, 'group': group, 'query': query, 'unread': unread})


@login_required
@require_safe
@never_cache
def preview(request):
    rows = [row for row in alerts.items(request.user) if row['unread']]
    return render(request, 'design/alert_preview.html', {'rows': rows[:5]})


@login_required
@require_POST
@never_cache
def mark_read(request):
    key = request.POST.get('key', '')
    if len(key) != 64 or not any(row['key'] == key for row in alerts.items(request.user)):
        raise Http404
    AlertRead.objects.get_or_create(actor=request.user, key=key)
    return redirect('design_alerts')


class AlertPreferencesForm(forms.Form):
    email_requested = forms.BooleanField(required=False, label='Email alerts')
    whatsapp_requested = forms.BooleanField(required=False, label='WhatsApp alerts')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def preferences(request):
    prefs = AlertPreference.objects.filter(actor=request.user).first()
    form = AlertPreferencesForm(request.POST if request.method == 'POST' else None, initial={
        'revision': prefs.revision if prefs else 1, 'email_requested': bool(prefs and prefs.email_requested),
        'whatsapp_requested': bool(prefs and prefs.whatsapp_requested),
    })
    if request.method == 'POST' and form.is_valid():
        values = form.cleaned_data
        try:
            alerts.save_preferences(request.user, values['revision'], values['email_requested'], values['whatsapp_requested'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Alert preferences saved.')
            return redirect('design_alert_preferences')
    routes = account_delivery.channel_routes(request.user)
    recent = AccountDelivery.objects.filter(actor=request.user, purpose='alert').order_by('-created_at')[:20]
    runtime = settings.CONTACT_DELIVERY
    return render(request, 'design/alert_preferences.html', {
        'form': form, 'email_ready': 'email' in routes, 'whatsapp_ready': 'whatsapp' in routes,
        'recent': recent, 'sample_mailbox': bool(runtime and runtime.synthetic and routes),
    })


@login_required
@require_safe
@never_cache
def sample_mailbox(request):
    runtime = settings.CONTACT_DELIVERY
    if not runtime or not runtime.synthetic or not account_delivery.channel_routes(request.user):
        raise Http404
    rows = AccountDelivery.objects.filter(actor=request.user, purpose='recovery', state=AccountDelivery.State.DELIVERED,
                                          consumed_at__isnull=True).order_by('-created_at')[:5]
    links = [{'url': account_delivery.recovery_path(row), 'row': row}
             for row in rows if account_delivery.valid_reset(row, request.user)]
    response = render(request, 'design/sample_mailbox.html', {'links': links})
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response
