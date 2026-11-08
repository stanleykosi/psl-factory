import ast,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class EngagementProfileComponentTests(unittest.TestCase):
    def test_closed_no_worker_adapter(self):
        s=(ROOT/'adapters/factory_engagement_policy_impact.py').read_text();t=ast.parse(s)
        calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
        self.assertFalse(calls & {'start','receive','act','verify','run_until_wait','adopt_profile','capture_current'})
        self.assertIn('factory_engagement.readable(actor,case)',s)
        self.assertIn('configuration(actor,case.pk,row.policy_id)',s)
    def test_fixture_direct_route_without_execution(self):
        s=(ROOT/'tests/engagement_profile805_helpers.py').read_text();t=ast.parse(s)
        calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(t) if isinstance(n,ast.Call)}
        self.assertTrue({'capture','start','adopt_profile'}<=calls)
        self.assertFalse(calls & {'run_once','run_until_wait','assign','register','sign_baseline','adopt_signed'})
        self.assertIn("capture(a,c.pk,'B'",s);self.assertIn('No conversion/sign/adoption',s)
    def test_integrated_registry_private_route_agent_and_lock(self):
        key='workflows.factory_engagement_profiles'
        for name in ('adapters/policy_impact.py','adapters/policy_private_impact.py','apps/agents/policy_impact.py','apps/policy/impact.py'):
            self.assertIn(key,(ROOT/name).read_text())
        self.assertIn("'workflows.factory_engagement_profiles':'engagement'",(ROOT/'adapters/policy_impact.py').read_text())
        self.assertIn('Engagement intake profile metadata only',(ROOT/'apps/agents/policy_impact.py').read_text())
        s=(ROOT/'apps/policy/impact.py').read_text()
        self.assertIn("'workflows.factory_planning_profiles','workflows.factory_engagement_profiles']",s)
        self.assertIn("select_for_update(of=('self',),nowait=True)",s)
    def test_exact_additive_sql_delta(self):
        def sql(name):
            t=ast.parse((ROOT/'apps/policy/migrations'/name).read_text())
            return next(ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='SQL' for x in n.targets))
        old=sql('0032_factory_planning_binding_impact.py');new=sql('0033_factory_engagement_policy_impact.py')
        self.assertEqual(new,old.replace('BETWEEN 1 AND 28','BETWEEN 1 AND 29').replace("'workflows.factory_planning_profiles'","'workflows.factory_engagement_profiles','workflows.factory_planning_profiles'",1))
    def test_native_definitions_keep_real_lock_and_honest_singleton(self):
        s=(ROOT/'tests/test_engagement_profile_impact.py').read_text()
        for text in ('pg_backend_pid()',"SET LOCAL lock_timeout='2s'",'thread.join(12)','connections.close_all()','self.assertNotEqual(pids[0],main_pid)','test-only signed token',"SNAPSHOT_LIMIT',0"):
            self.assertIn(text,s)
