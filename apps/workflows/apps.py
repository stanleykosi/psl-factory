from django.apps import AppConfig, apps
from django.db.models.signals import post_save


class WorkflowsConfig(AppConfig):
    name = "apps.workflows"

    def ready(self):
        from .native_station_contracts import registry
        from .native_stations import capture

        for model in {route.model for route in registry().values()}:
            post_save.connect(capture, sender=apps.get_model(model), dispatch_uid=f"psl.native-station.{model.lower()}")
