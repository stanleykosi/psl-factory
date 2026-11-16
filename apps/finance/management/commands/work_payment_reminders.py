from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand

from apps.finance import reminders
from apps.finance.reminder_models import PaymentReminderDispatch


class Command(BaseCommand):
    help = 'Deliver explicitly released reminders to the isolated synthetic inbox.'

    def handle(self, **options):
        ready = PaymentReminderDispatch.objects.filter(
            mode='synthetic_inbox', draft__issue__invoice__case__synthetic=True, receipt__isnull=True,
        ).order_by('pk').values_list('pk', flat=True)[:20]
        for dispatch_id in ready:
            try:
                reminders.simulate(dispatch_id)
            except (PermissionDenied, ValidationError):
                self.stdout.write(f'Reminder {dispatch_id} held for current authorization or source verification')
