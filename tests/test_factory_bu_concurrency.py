from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from django.test import TransactionTestCase
from django.db import close_old_connections
from django.utils import timezone
from apps.workflows import factory_bu as bu
from apps.workflows.models import FactoryWork
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from tests.bu_helpers import fixture,source,review

class FactoryBUConcurrencyTests(TransactionTestCase):
    def test_two_connections_preserve_single_canonical_intake(self):
        f=fixture();v=json.loads(Path('fixtures/factory-bu.json').read_text());v.pop('classification');p=draft_operator_policy(f['preparer'],f['case'].pk,'OPS.factory_bu_execution',v,f['e']['policy_decision'].pk,timezone.now());transition(f['preparer'],p.pk,'validated');transition(f['preparer'],p.pk,'active')
        s=source(f);review(f,s);inputs={'mode':'event','source_id':s.pk,'payroll_id':None,'rule_ids':[],'comparison':None}
        def task(n):
            close_old_connections()
            try:return bu.start(f['preparer'],f['case'].pk,'BU-race-'+str(n),inputs,'Same canonical source').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(task,[0,1]))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(FactoryWork.objects.filter(definition=bu.DEFINITION).count(),1)
