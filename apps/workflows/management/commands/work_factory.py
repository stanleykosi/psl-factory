from django.core.management.base import BaseCommand,CommandError
from apps.workflows import factory
from apps.workflows.models import FactoryWork

class Command(BaseCommand):
    help='Process explicitly selected factory work using current native authority; no global queue drain.'
    def add_arguments(self,parser):
        parser.add_argument('--work',type=int,action='append',required=True,help='Exact work ID; repeat for up to50 selected items')
        parser.add_argument('--until-wait',action='store_true',help='Continue within the same persisted allowance until a wait or stop')
    def handle(self,*args,**options):
        ids=options['work']
        if len(ids)>50 or any(pk<1 for pk in ids):raise CommandError('Select at most50 positive work IDs')
        ids=list(dict.fromkeys(ids))
        if FactoryWork.objects.filter(pk__in=ids).count()!=len(ids):raise CommandError('Every selected work item must exist; no work was started')
        for pk in ids:
            if options['until_wait']:factory.run_until_wait(pk)
            else:factory.run_once(pk)
            work=FactoryWork.objects.get(pk=pk)
            self.stdout.write(f'Work {pk}: {work.status}; allowance reserved {work.budget_used}/{work.budget_limit}')
