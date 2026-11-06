import json,os,subprocess,sys
from tests import test_reconstitution as prior


class DomainContractTests(prior.ReconstitutionTests):
    # Reuse the real, separately owned source/control/target provisioning harness,
    # without discovering its six prior tests a second time.
    test_01_ui_missing_policy_scope_agent_and_inventory=None
    test_02_authenticated_receipts_unknown_and_human_dispositions=None
    test_03_complete_review_publication_and_changed_evidence=None
    test_04_duplicates_and_fresh_process_commit_recovery=None
    test_05_sql_guards_and_foreign_scope=None
    test_06_revoked_policy_roles_and_receipt_expiry=None

    @classmethod
    def child(cls,stage,v,cold=True):
        if stage in ['source','initialize','recover']:
            return prior.ReconstitutionTests.child(stage,v,cold)
        env=os.environ.copy();env.update(PGDATABASE=v['control'],DJANGO_SETTINGS_MODULE='config.cold_settings')
        result=subprocess.run([sys.executable,'-m','tests.domain_contract_scenario',stage],input=json.dumps(v),
            text=True,capture_output=True,env=env,timeout=600)
        if result.returncode:raise AssertionError(stage+' failed\n'+result.stdout+'\n'+result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_10_provider_and_destination_through_source_owned_review(self):
        v,r=self.scenario('connected')
        self.assertTrue(r['unknown_preserved']);self.assertTrue(r['destination_reviewed']);self.assertFalse(r['activation_enabled'])
        v.update(r);proof=self.child('restart',v)
        self.assertTrue(proof['persisted']);self.assertEqual(proof['observations'],r['observations'])

    def test_11_contract_guards_binding_expiry_privacy_and_revocation(self):
        _,r=self.scenario('negatives')
        self.assertTrue(r['sql_guards']);self.assertTrue(r['rotation_held']);self.assertTrue(r['foreign_scope_held'])
