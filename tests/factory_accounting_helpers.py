import json
from pathlib import Path
from django.utils import timezone
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from tests.helpers import rev

def configured(a,c,e,source,template,metrics,**changes):
    from apps.workflows import factory_accounting
    value=json.loads(Path('fixtures/factory-accounting.json').read_text());assert value.pop('classification')=='synthetic_test_only'
    value.update(information_resolver_id=a.pk,executor_id=a.pk,template_id=template.pk,bu_metrics=metrics)
    value.update(changes)
    config=draft_operator_policy(a,c.pk,'OPS.factory_accounting_execution',value,e['policy_decision'].pk,timezone.now())
    transition(a,config.pk,'validated');transition(a,config.pk,'active')
    work=factory_accounting.start(a,c.pk,'ACCOUNTING-EXAMPLE',source.pk,[],'Synthetic management accounts',rev(c))
    return {'actor':a,'case':c,'evidence':e,'source':source,'template':template,'work':work,'value':value,'configuration':config}
