"""Separate-process interruption fixture; refuse every non-test database."""
import os,sys
assert os.environ.get('PGDATABASE','').startswith('test_'),'Only an isolated test database is allowed'
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from apps.workflows import factory
from apps.workflows.models import FactoryWork
pk=int(sys.argv[1]);assert FactoryWork.objects.get(pk=pk).case.synthetic
class Interrupted:
    def choose(self,context):os._exit(37)
if sys.argv[2] in ['closure_interrupt_before_commit','closure_interrupt_after_commit']:
    assert FactoryWork.objects.get(pk=pk).definition=='delivery-closure/v1'
    from apps.pmo.models import DeliveryRecord
    from apps.core.read_observation import assert_command_allowed
    if sys.argv[2]=='closure_interrupt_before_commit':
        original=factory.act
        def interrupt_before_commit(work,choice,*args):
            assert_command_allowed();result=original(work,choice,*args)
            if choice['activity']=='ACT11':os._exit(38)
            return result
        factory.act=interrupt_before_commit
    else:
        original=factory.fence
        def interrupt_after_commit(work,token):
            original(work,token);assert_command_allowed()
            if DeliveryRecord.objects.filter(dossier_id=work.request['dossier'],kind='closure').exists():os._exit(39)
        factory.fence=interrupt_after_commit
    factory.run_until_wait(pk)
elif sys.argv[2] in ['handover_interrupt_after_delivery','go_live_interrupt_after_delivery']:
    expected={'handover_interrupt_after_delivery':'delivery-handover/v1','go_live_interrupt_after_delivery':'delivery-go-live/v1'}[sys.argv[2]]
    assert FactoryWork.objects.get(pk=pk).definition==expected
    from adapters.publications import InternalPublicationAdapter
    class ExitAfterDelivery(InternalPublicationAdapter):
        def deliver(self,job_id,fence):
            super().deliver(job_id,fence)
            os._exit(39)
    factory.run_until_wait(pk,adapter=ExitAfterDelivery())
elif sys.argv[2]=='interrupt_after_action':
    original=factory.act
    def interrupt_after_action(work,choice,*args):
        result=original(work,choice,*args)
        if choice['activity']=='ACT08':os._exit(38)
        return result
    factory.act=interrupt_after_action
    factory.run_until_wait(pk)
else:factory.run_once(pk,Interrupted() if sys.argv[2]=='interrupt' else None)
