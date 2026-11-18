"""Fence old sessions without scanning, decoding or deleting unrelated sessions."""
from django.contrib.auth import logout
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .staff_models import StaffAccountChange

KEY = '_psl_staff_epoch'


def epoch(user):
    return StaffAccountChange.objects.filter(user=user).order_by('-pk').values_list('pk',flat=True).first() or 0


@receiver(user_logged_in, dispatch_uid='psl.identity.staff_session_epoch')
def record_login(sender, request, user, **kwargs):
    if request is not None:
        request.session[KEY] = epoch(user)


class StaffSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current = epoch(request.user)
            # Existing unchanged accounts retain their ordinary sessions. A new
            # lifecycle event fences legacy sessions too, including after reactivation.
            if request.session.get(KEY,0) != current:
                logout(request)
        return self.get_response(request)
