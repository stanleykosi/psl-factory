from django.apps import AppConfig


class IdentityConfig(AppConfig):
    name = 'apps.identity'

    def ready(self):
        from . import staff_sessions  # noqa: F401 — register the ordinary login signal
