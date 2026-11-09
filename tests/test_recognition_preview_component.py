"""Bounded exact-production extraction; no database, Django startup or provider."""
import ast
from pathlib import Path
from types import SimpleNamespace as N
from unittest import TestCase
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]

class RecognitionPreviewComponentTests(TestCase):
    def source(self,path):return ast.parse((ROOT/path).read_text())
    def node(self,path,name):return next(n for n in self.source(path).body if isinstance(n,ast.FunctionDef) and n.name==name)
    def test_native_record_preserves_locks_and_only_creates_after_guard(self):
        s=ast.unparse(self.node('apps/finance/recognition.py','record'))
        self.assertIn('@transaction.atomic',s)
        self.assertLess(s.index('locked('),s.index('guard_record('))
        self.assertLess(s.index('guard_record('),s.index('RecognitionRecord.objects.create('))
        self.assertIn('if old:',s)
    def test_replay_precedes_currentness_without_effect(self):
        s=ast.unparse(self.node('apps/finance/recognition.py','guard_record'))
        self.assertLess(s.index('if old:'),s.index('packet_current('))
        self.assertNotIn('.create(',s);self.assertNotIn('bump(',s)
    def test_observer_grant_precedes_private_lookup(self):
        s=ast.unparse(self.node('apps/finance/recognition_preview.py','get'))
        self.assertLess(s.index('readable('),s.index('Evidence.objects.filter('))
        self.assertLess(s.index('Audit.objects.filter('),s.index('json.loads('))
    def test_guard_executes_original_native_checks_and_redacts_errors(self):
        node=self.node('apps/finance/recognition_preview.py','guard')
        value={'actor_id':1,'packet_id':2,'operation_key':'secret-key','evidence_id':3,'note':'private-note','packet_sha256':'p','evidence_sha256':'e'}
        native=Mock();native.guard_record.return_value=(N(pk=2,sha256='p'),N(sha256='e'),{},None,{}, {})
        env={'get':Mock(return_value=(N(pk=4,sha256='i'),value)),'native':native,'ValidationError':ValueError}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<exact-production-guard>','exec'),env)
        result=env['guard'](N(pk=1),N(),4,'i')
        self.assertFalse(result[1]['effects_scheduled']);self.assertNotIn('private-note',repr(result))
        native.guard_record.side_effect=ValueError('private-note')
        with self.assertRaisesRegex(ValueError,'^Private attestation input is not currently usable$'):env['guard'](N(pk=1),N(),4,'i')
    def test_private_prefix_and_unbound_disclosure(self):
        s=(ROOT/'apps/finance/recognition_preview.py').read_text()
        self.assertIn("KIND='agent_private_recognition_input'",s)
        self.assertIn("'agent_private_'",(ROOT/'apps/core/evidence_access.py').read_text())
        self.assertIn('unbound to separately entered native form input',(ROOT/'apps/agents/pilot.py').read_text())
    def test_migration_preserves_every_prior_sql_variant(self):
        def sql(name):
            return ast.literal_eval(next(n.value for n in self.source('apps/policy/migrations/'+name).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SQL' for t in n.targets)))
        old=sql('0019_planning_readiness_preview.py');new=sql('0020_recognition_attestation_preview.py')
        start=new.index("  WHEN 'recognition.attest' THEN");end=new.index("  WHEN 'planning.readiness' THEN",start)
        restored=(new[:start]+new[end:]).replace("NOT IN ('recognition.attest','planning.readiness'","NOT IN ('planning.readiness'",1)
        self.assertEqual(restored,old)
        for fragment in ["ARRAY['expected_revision','recognition_input_id','recognition_input_sha256']",'agent_private_recognition_input','psl:recognition-proposed-input/v1','IS DISTINCT FROM c.case_id']:
            self.assertIn(fragment,new[start:end])
    def test_composed_registry_retains_both_observer_prechecks(self):
        tree=self.source('adapters/pilot_guards.py')
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REGISTRY' for t in n.targets))
        keys=[ast.literal_eval(k) for k in node.value.keys]
        self.assertEqual(len(keys),20);self.assertEqual(len(keys),len(set(keys)))
        self.assertTrue({'recognition.attest','planning.readiness','approval.route','ledger.review'}<=set(keys))
        check=ast.unparse(self.node('adapters/pilot_guards.py','check'))
        self.assertIn("selection['operation'] == 'recognition.attest'",check)
        self.assertIn("selection['operation'] == 'planning.readiness'",check)
