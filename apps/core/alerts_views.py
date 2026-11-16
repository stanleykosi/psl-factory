from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe, require_POST

from . import alerts
from .alert_models import AlertPreference, AlertRead


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
    email_requested = forms.BooleanField(required=False, label='Request email alerts')
    whatsapp_requested = forms.BooleanField(required=False, label='Request WhatsApp alerts')
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
    return render(request, 'design/alert_preferences.html', {'form': form})
