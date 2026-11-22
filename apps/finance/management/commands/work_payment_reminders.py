from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.finance import reminders
from apps.finance.reminder_models import PaymentReminderDispatch


class Command(BaseCommand):
    help = 'Deliver explicitly released reminders to the isolated synthetic inbox.'

    def handle(self, **options):
        ready = PaymentReminderDispatch.objects.filter(
            mode__in=['synthetic_inbox', 'synthetic_mailbox'], draft__issue__invoice__case__synthetic=True, receipt__isnull=True,
        ).filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now()))
        for dispatch_id, mode in ready.order_by('pk').values_list('pk', 'mode')[:20]:
            try:
                process = reminders.run_mailbox if mode == 'synthetic_mailbox' else reminders.simulate
                process(dispatch_id)
            except (PermissionDenied, ValidationError, OSError):
                self.stdout.write(f'Reminder {dispatch_id} held for current authorization or source verification')
