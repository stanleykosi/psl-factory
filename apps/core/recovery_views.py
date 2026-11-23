import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.password_validation import (
    CommonPasswordValidator, MinimumLengthValidator, NumericPasswordValidator, UserAttributeSimilarityValidator,
    validate_password,
)
from django.core.signing import BadSignature, Signer
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_safe

from .account_delivery import queue_recovery, valid_reset
from .alert_models import AccountDelivery

RESET_SESSION_KEY = 'factory_password_recovery'


class RecoveryForm(forms.Form):
    email = forms.EmailField(label='Work email', max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))


class RecoveryCodeForm(forms.Form):
    token = forms.CharField(label='Recovery code', max_length=128, widget=forms.TextInput(attrs={'autocomplete': 'off'}))


class RecoveryPasswordForm(SetPasswordForm):
    def validate_password_for_user(self, user, password_field_name='password2'):
        password = self.cleaned_data.get(password_field_name)
        if password:
            try:
                validate_password(password, user, password_validators=[MinimumLengthValidator(12),
                    UserAttributeSimilarityValidator(), CommonPasswordValidator(), NumericPasswordValidator()])
            except forms.ValidationError as error:
                self.add_error(password_field_name, error)


def private_response(response):
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def recover(request):
    form = RecoveryForm(request.POST if request.method == 'POST' else None)
    if form.is_valid():
        queue_recovery(form.cleaned_data['email'])
        return private_response(redirect('factory_recovery_sent'))
    return private_response(render(request, 'registration/factory_recovery.html', {'form': form}))


@never_cache
@require_safe
def sent(request):
    return private_response(render(request, 'registration/factory_recovery.html', {'sent': True}))


@sensitive_variables('token')
def bind_recovery_session(request, token):
    request.session.pop(RESET_SESSION_KEY, None)
    try:
        key = uuid.UUID(Signer(salt='factory.password.recovery.v1').unsign(token))
    except (BadSignature, ValueError):
        return False
    row = AccountDelivery.objects.select_related('actor').filter(pk=key).first()
    if not row or not valid_reset(row, row.actor):
        return False
    request.session.cycle_key()
    request.session[RESET_SESSION_KEY] = str(key)
    return True


def recovery_session(request):
    key = request.session.get(RESET_SESSION_KEY)
    row = AccountDelivery.objects.select_related('actor').filter(pk=key).first() if key else None
    if not row or not valid_reset(row, row.actor):
        request.session.pop(RESET_SESSION_KEY, None)
        return None
    return row


@transaction.atomic
@sensitive_variables('data', 'form')
def change_recovered_password(request, row, data):
    actor = get_user_model().objects.select_for_update().get(pk=row.actor_id)
    row = AccountDelivery.objects.select_for_update().get(pk=row.pk)
    if not valid_reset(row, actor):
        request.session.pop(RESET_SESSION_KEY, None)
        return None, False
    form = RecoveryPasswordForm(actor, data)
    if not form.is_valid():
        return form, False
    form.save()
    row.consumed_at = timezone.now()
    row.save(update_fields=['consumed_at'])
    request.session.pop(RESET_SESSION_KEY, None)
    return form, True


@sensitive_post_parameters('token')
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def redeem(request):
    form = RecoveryCodeForm(request.POST if request.method == 'POST' else None)
    if not form.is_bound:
        return private_response(render(request, 'registration/factory_recovery.html', {'code': form}))
    if form.is_valid():
        bind_recovery_session(request, form.cleaned_data['token'])
    else:
        request.session.pop(RESET_SESSION_KEY, None)
    return private_response(redirect('factory_recovery_confirm'))


@sensitive_post_parameters('new_password1', 'new_password2')
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def confirm(request):
    row = recovery_session(request)
    if not row:
        return private_response(render(request, 'registration/factory_recovery.html', {'invalid': True}))
    if request.method != 'POST':
        return private_response(render(request, 'registration/factory_recovery.html', {
            'new_password': RecoveryPasswordForm(row.actor),
        }))
    form, changed = change_recovered_password(request, row, request.POST)
    if changed:
        return private_response(redirect('factory_recovery_complete'))
    if form is None:
        return private_response(render(request, 'registration/factory_recovery.html', {'invalid': True}))
    return private_response(render(request, 'registration/factory_recovery.html', {'new_password': form}))


@never_cache
@require_safe
def complete(request):
    return private_response(render(request, 'registration/factory_recovery.html', {'complete': True}))
