import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils.dateparse import parse_datetime
from apps.identity.intake import provision

class Command(BaseCommand):
    help='Explicit versioned technical tenant delegation; no accounts, passwords or business role appointments are created.'
    def add_arguments(self,p):
        for name in ['actor','subject','tenant','config','expires','reason']:p.add_argument('--'+name,required=True)
        p.add_argument('--disable',action='store_true')
    def handle(self,*args,**o):
        try:
            User=get_user_model();actor=User.objects.get(username=o['actor']);subject=User.objects.get(username=o['subject'])
            expiry=parse_datetime(o['expires'])
            if expiry is None:raise ValidationError('Explicit timezone-aware ISO expiration required')
            cfg=provision(actor,subject,o['tenant'],json.loads(Path(o['config']).read_text(encoding='utf-8')),expiry,not o['disable'],o['reason'])
        except (User.DoesNotExist,ValidationError,PermissionDenied,OSError,ValueError) as exc:raise CommandError(str(exc)) from None
        self.stdout.write(f'Technical tenant authority version {cfg.version} recorded. No business owner was appointed.')
