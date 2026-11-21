from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction

from apps.identity.services import require
from apps.workflows.native_stations import NativeStation, checked_observation, enroll_next, registry


class Command(BaseCommand):
    help = "Enroll the next source-owned department events with the workflow coordinator."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--process", help="Reconcile one original subject with its department station.")
        parser.add_argument("--subject")
        parser.add_argument("--actor", type=int)

    def handle(self, *args, **options):
        recovery = [options["process"], options["subject"], options["actor"]]
        if any(v is not None for v in recovery):
            if not all(recovery) or options["process"] not in registry():
                raise CommandError("Select one registered process, original subject and authorised operator.")
            with transaction.atomic():
                route = registry()[options["process"]]
                try:
                    subject = apps.get_model(route.model)._default_manager.get(pk=options["subject"])
                    actor = get_user_model().objects.get(pk=options["actor"], is_active=True)
                    event, _ = NativeStation.objects.get_or_create(process=route.process,
                        subject_model=subject._meta.label_lower, subject_pk=str(subject.pk))
                    record = checked_observation(event, actor)
                    require(actor, record.case, "factory.manage")
                except (ObjectDoesNotExist, PermissionDenied, ValidationError, ValueError) as exc:
                    raise CommandError("The original subject and current department recovery authority are required.") from exc
            self.stdout.write("Source event reconciled.")
            return
        limit = options["limit"]
        if not 1 <= limit <= 100:
            raise CommandError("Choose a batch size between one and 100.")
        for _ in range(limit):
            if not enroll_next():
                break
