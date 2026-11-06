from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.pmo.costing import run

class Command(BaseCommand):
    help='Run/reconcile one exact granted P14 calculation; no invoice or external effects.'
    def add_arguments(self,p):
        for key in ['actor','plan','engineering','security','inputs']:p.add_argument('--'+key,type=int,required=True)
        p.add_argument('--case',required=True);p.add_argument('--key',required=True)
    def handle(self,*args,**v):
        r=run(get_user_model().objects.get(pk=v['actor']),v['case'],v['plan'],v['engineering'],v['security'],v['inputs'],v['key']);self.stdout.write(str(r.pk))
