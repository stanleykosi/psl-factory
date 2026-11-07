"""Real0076 populated history; no provisional guard and no F01 factory before0077."""
def seed_predecessor(check):
    import json
    from pathlib import Path
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from apps.core.models import Evidence
    from apps.finance.bu_models import BUReport
    from apps.workflows import factory,factory_bu
    from apps.policy.operator_drafts import draft_operator_policy
    from apps.policy.services import transition
    from tests.bu_upgrade_helpers import seed_predecessor as seed
    from tests.ledger_helpers import fixture,capture,verify,review
    from tests.helpers import rev
    from apps.finance import ledger
    record={'prior':seed(check)}
    existing=BUReport.objects.get(pk=record['prior']['bu']['reports'][1]['report']);native=existing.work;actor=native.actor;case=native.case
    value=json.loads(Path('fixtures/factory-bu.json').read_text());value.pop('classification')
    evidence=Evidence.objects.filter(case=case,kind='policy_decision').first()
    p=draft_operator_policy(actor,case.pk,'OPS.factory_bu_execution',value,evidence.pk,timezone.now());transition(actor,p.pk,'validated');transition(actor,p.pk,'active')
    inputs={'mode':'event','payroll_id':None,'source_id':native.parent_id,'rule_ids':[],'comparison':None}
    work=factory_bu.start(actor,case.pk,'F01-UPGRADE-BU',inputs,'Retained native BU preparation',rev(case));factory.run_until_wait(work.pk);work.refresh_from_db()
    record['bu_factory']={'work':work.pk,'status':work.status,'head':work.source_head_id,'budget':work.budget_used,'native':factory_bu.report(work)}
    f=fixture('f01-upgrade-preparer','f01-upgrade-reviewer');old=capture(f);x=verify(f,old);review(f,x)
    newer=capture(f,dict(old.payload,outcome='uncertain'),old.pk);x=verify(f,newer);review(f,x)
    record['ledger']={'case':str(f['case'].pk),'actor':f['actor'].pk,'old':old.pk,'current':newer.pk,'report':ledger.report(f['actor'],f['case'].pk,newer.pk),'checks':list(ledger.LedgerCheck.objects.filter(lineage__case=f['case']).values_list('pk',flat=True)),'decisions':list(ledger.LedgerDecision.objects.filter(verification__lineage__case=f['case']).values_list('pk',flat=True))}
    reverify(record);return record

def reverify(record):
    from tests.bu_upgrade_helpers import reverify as previous
    from django.contrib.auth import get_user_model
    from apps.workflows.models import FactoryWork
    from apps.workflows import factory_bu
    from apps.finance import ledger
    from django.core.exceptions import ValidationError
    previous(record['prior']);r=record['bu_factory'];w=FactoryWork.objects.get(pk=r['work'])
    assert (w.status,w.source_head_id,w.budget_used)==(r['status'],r['head'],r['budget'])
    assert factory_bu.report(w)==r['native']
    r=record['ledger'];actor=get_user_model().objects.get(pk=r['actor'])
    assert ledger.report(actor,r['case'],r['current'])==r['report']
    try:ledger.report(actor,r['case'],r['old'])
    except ValidationError:pass
    else:raise AssertionError('Superseded original lineage must remain historical')
    assert list(ledger.LedgerCheck.objects.filter(lineage__case_id=r['case']).values_list('pk',flat=True))==r['checks']
    assert list(ledger.LedgerDecision.objects.filter(verification__lineage__case_id=r['case']).values_list('pk',flat=True))==r['decisions']
