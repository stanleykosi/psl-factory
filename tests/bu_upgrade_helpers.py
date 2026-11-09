"""Actual0075 synthetic history preserved across the additive BU boundary."""
def seed_predecessor(check):
    from tests.engagement_upgrade_helpers import seed_predecessor as seed
    from tests.test_factory_engagement import setup,complete
    from tests.bu_helpers import fixture,staff,event,publish
    from tests.helpers import rev
    from apps.finance import bu
    record={'prior':seed(check)}
    f=setup(name='bu-upgrade-engagement');proof=complete(f)
    record['engagement']={'work':f['w'].pk,'proof':proof}
    native=fixture();reports=[]
    for result in [staff(native),event(native)]:
        p=publish(native,result);receipt=bu.receive(native['manager'],native['case'].pk,p.pk,rev(native['case']))
        reports.append({'report':p.pk,'receipt':receipt.pk,'payload':bu.read_report(native['manager'],p.pk)})
    record['bu']={'recipient':native['manager'].pk,'reports':reports}
    return record

def reverify(record):
    from tests.engagement_upgrade_helpers import reverify as verify_prior
    from django.contrib.auth import get_user_model
    from apps.workflows.models import FactoryWork
    from apps.workflows import factory_engagement
    from apps.finance import bu
    from apps.finance.bu_models import BUReceipt
    verify_prior(record['prior'])
    assert factory_engagement.verified_output(FactoryWork.objects.get(pk=record['engagement']['work']))==record['engagement']['proof']
    actor=get_user_model().objects.get(pk=record['bu']['recipient'])
    for p in record['bu']['reports']:
        assert bu.read_report(actor,p['report'])==p['payload']
        assert BUReceipt.objects.filter(pk=p['receipt'],report_id=p['report'],actor=actor).exists()
