"""Native test definitions. External Intuit client only is mocked; not run by component suite."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
from django.test import TransactionTestCase, override_settings
from django.core.exceptions import ValidationError, PermissionDenied
from apps.workflows import readiness, readiness_delivery, quickbooks_mcp as broker
from apps.core.models import Audit
from apps.core.evidence_access import public_evidence, public_timeline
from apps.identity.models import Grant
from apps.policy.services import register_reference
from apps.policy.readiness_validators import ADAPTER
from apps.policy.ledger_validators import RULES, AUTH
from apps.agents import quickbooks_mcp as agent
from tests import readiness_helpers as rh, ledger_helpers as lh
from tests.helpers import activate
from tests.test_quickbooks_mcp import TOOL, OUTPUT
from adapters.quickbooks_mcp import VERSION, READ_SCOPE

class NativeMCPTests(TransactionTestCase):
    def setUp(self):
        f=rh.fixture('mcp-native',configured=False,family='ledgerdata');self.f=f
        role=register_reference(f['actor'],f['case'].pk,'mcp-finance','schema:psl/role-assignment/v1',
            {'role':'Finance','user_id':f['reviewer'].pk},f['sources']['policy_decision'].pk)
        refs=['mcp-native-role:'+r for r in ['PM','Head of PMO','CEO','PMO Lead','PMO']]+[role.ref]
        activate(f['actor'],f['case'],'D05.role_principal_assignments',refs,f['sources']['policy_decision'])
        f['rules']['require_receipt_probe']=False
        rh.policy(f,ADAPTER)
        f['e']=f['sources']['policy_decision']
        v=json.loads((Path(__file__).resolve().parent.parent/'fixtures/ledger.json').read_text())
        v['source'].update(treatment_evidence_id=f['e'].pk,posting_evidence_id=f['e'].pk)
        v['rules']['treatment_evidence_ids']=[f['e'].pk];v['authority']['user_ids']=[f['reviewer'].pk];f['v']=v
        lh.policy(f,RULES,v['rules']);lh.policy(f,AUTH,v['authority'])
        self.lineage=lh.capture(f)
        value=dict(f['contract'].payload,implementation='hosted_mcp_read_v1',target_key='endpoint:intuit-mcp',
            credential_ref='secret:mcp',credential_revision='v1',principal_ref='principal:fixture',contract_version=VERSION,capabilities=['health'],data_scope='scoped_qbo_invoice_identity_read_v1')
        f['contract']=readiness.capture(f['actor'],f['case'].pk,'primary',value,rh.evidence(f,'integration_contract').pk,predecessor=f['contract'].pk)
        self.entry={'enabled':True,'realm':v['source']['realm'],'principal_ref':'principal:fixture','credential_ref':'secret:mcp',
            'credential_revision':'v1','app_name':'fixture','contract_id':f['contract'].pk,
            'scopes':['com.intuit.quickbooks.accounting',READ_SCOPE],'reviewed_tool':copy.deepcopy(TOOL),
            'output_schema':copy.deepcopy(OUTPUT),'target_argument':'id','result_identity_key':'id','fixed_arguments':{}}
        self.settings=override_settings(READINESS_SECRET_REFS={'secret:mcp':{'env':'PSL_SYNTHETIC_MCP_TOKEN','revision':'v1'}});self.settings.enable();self.addCleanup(self.settings.disable)
        self.env=patch.dict('os.environ',{'PSL_SYNTHETIC_MCP_TOKEN':'SYNTHETIC-NOT-A-CREDENTIAL'});self.env.start();self.addCleanup(self.env.stop)
        self.config=patch.object(broker,'load',side_effect=lambda _: {'fixture':copy.deepcopy(self.entry)});self.config.start();self.addCleanup(self.config.stop)
        self.clientpatch=patch.object(broker,'Client');self.client=self.clientpatch.start().return_value;self.addCleanup(self.clientpatch.stop)
        self.client.discover.return_value=[copy.deepcopy(TOOL)]
        self.client.call.return_value={'id':v['source']['target_reference']}
        rh.probe(f)
        assessment=readiness.assess(f['actor'],f['case'].pk,f['contract'].pk,'mcp-ready')
        readiness.review(f['reviewer'],f['case'].pk,assessment.pk,'confirm','mcp-confirm',f['review_evidence'].pk)
        readiness.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk)

    def reserve(self):
        return broker.reserve(self.f['actor'],self.f['case'].pk,self.lineage.pk,self.f['contract'].pk)

    def test_shared_read_never_creates_finance_check(self):
        row=self.reserve();result=broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
        self.assertEqual(json.loads(result.body)['result']['status'],'observed')
        self.assertFalse(self.lineage.checks.exists())
        self.assertEqual(self.client.call.call_args.args[1],{'id':self.lineage.payload['target_reference']})
        with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,row.pk)

    def test_missing_review_or_schema_change_holds(self):
        self.entry['reviewed_tool']['description']='changed'
        with self.assertRaises(ValidationError):self.reserve()
        self.client.call.assert_not_called()

    def test_revoked_principal_cannot_execute(self):
        row=self.reserve();Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='ledger.verify').update(active=False)
        with self.assertRaises(PermissionDenied):broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
        self.client.call.assert_not_called()

    def test_revocation_inflight_retains_stale_fact(self):
        row=self.reserve()
        def result(*args):
            Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='ledger.verify').update(active=False)
            return {'id':self.lineage.payload['target_reference']}
        self.client.call.side_effect=result
        evidence=broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
        self.assertFalse(json.loads(evidence.body)['current_at_capture'])
        self.assertFalse(self.lineage.checks.exists())

    def test_forged_kind_and_generic_projection(self):
        fake=rh.evidence(self.f,broker.INTENT,{'fake':'source'})
        with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,fake.pk)
        row=self.reserve();result=broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
        self.assertFalse(public_evidence(self.f['case'].evidence.all()).filter(pk__in=[row.pk,result.pk]).exists())
        self.assertFalse(public_timeline(self.f['case']).filter(action__startswith=broker.PREFIX).exists())

    def test_agent_uses_same_gate(self):
        Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='agent.ledger').update(active=False)
        with self.assertRaises(PermissionDenied):agent.read(self.f['actor'],self.f['case'].pk,self.lineage.pk,self.f['contract'].pk)
        self.client.call.assert_not_called()

    def test_agent_mode_grant_is_rechecked_at_dispatch(self):
        row=broker.reserve(self.f['actor'],self.f['case'].pk,self.lineage.pk,self.f['contract'].pk,caller_mode='agent')
        self.assertEqual(json.loads(row.body)['caller_mode'],'agent')
        Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='agent.ledger').update(active=False)
        with self.assertRaises(PermissionDenied):broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
        self.client.call.assert_not_called()

    def test_agent_mode_revoked_inflight_retains_stale_result(self):
        row=broker.reserve(self.f['actor'],self.f['case'].pk,self.lineage.pk,self.f['contract'].pk,caller_mode='agent')
        def result(*args):
            Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='agent.ledger').update(active=False)
            return {'id':self.lineage.payload['target_reference']}
        self.client.call.side_effect=result
        evidence=broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
        self.assertFalse(json.loads(evidence.body)['current_at_capture'])
        with self.assertRaises(PermissionDenied):broker.reconcile(self.f['actor'],self.f['case'].pk,row.pk)

    def factory_work(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        from apps.workflows import factory, factory_ledger as flow
        from tests.ledger_factory_provisional import install
        from tests.helpers import rev
        install()
        value={'definition':flow.DEFINITION,'max_steps':40,'max_tokens':50000,'tokens_per_call':100,'max_children':100,
            'max_depth':3,'lease_seconds':30,'max_age_seconds':86400,'required_evidence_kinds':[flow.KIND],
            'information_resolver_id':None,'executor_id':None,'review_role':None,'provider':'synthetic_factory_v1','enabled':True}
        policy=draft_operator_policy(self.f['actor'],self.f['case'].pk,'OPS.factory_ledger_execution',value,
            self.f['e'].pk,timezone.now()-timedelta(seconds=1))
        transition(self.f['actor'],policy.pk,'validated');transition(self.f['actor'],policy.pk,'active')
        work=flow.start(self.f['actor'],self.f['case'].pk,'mcp-factory',self.lineage.evidence_id,None,rev(self.f['case']))
        return work

    def test_factory_reserves_then_reconciles_without_posting(self):
        from apps.workflows import factory
        work=self.factory_work()
        factory.run_until_wait(work.pk);work.refresh_from_db()
        reservation=Audit.objects.get(case=self.f['case'],action=broker.PREFIX+'reserved',data__factory_work=work.pk)
        intent_id=reservation.data['intent']
        self.assertEqual(self.client.call.call_count,1)
        self.assertTrue(work.activities.filter(kind='ACT11',attempts__result__state='reserved_pending_external_read').exists())
        self.assertNotEqual(work.status,'verified')
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertTrue(work.activities.filter(attempts__phase='observed',attempts__result__mcp_intent=intent_id,
            attempts__result__has_key='mcp_result_evidence').exists())
        self.assertNotEqual(work.status,'verified')
        self.assertFalse(self.lineage.checks.exists())
        factory.run_until_wait(work.pk)
        self.assertEqual(Audit.objects.filter(case=self.f['case'],action=broker.PREFIX+'reserved',data__factory_work=work.pk).count(),1)


    def test_factory_interrupted_reservation_dispatch_rechecks_agent(self):
        from django.db import transaction
        from apps.workflows import factory, factory_ledger as flow
        work=self.factory_work()
        self.entry['enabled']=False
        factory.run_until_wait(work.pk);work.refresh_from_db();work.case.refresh_from_db()
        self.entry['enabled']=True
        with transaction.atomic():
            value=flow.act(work,{'activity':'ACT11'},None,None,None,None,None)
        intent_id=value['mcp_intent']
        self.assertEqual(broker.status(self.f['actor'],self.f['case'].pk,intent_id)['status'],'reserved')
        self.client.call.assert_not_called()
        Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='agent.ledger').update(active=False)
        with self.assertRaises(PermissionDenied):broker.execute(self.f['actor'],self.f['case'].pk,intent_id)
        self.assertFalse(Audit.objects.filter(case=self.f['case'],action=broker.PREFIX+'started',data__intent=intent_id).exists())
        Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='agent.ledger').update(active=True)
        broker.execute(self.f['actor'],self.f['case'].pk,intent_id)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertNotEqual(work.status,'verified')
        self.assertEqual(self.client.call.call_count,1)

    def test_factory_cancelled_reservation_does_not_dispatch(self):
        from django.db import transaction
        from apps.workflows import factory, factory_ledger as flow
        work=self.factory_work();self.entry['enabled']=False
        factory.run_until_wait(work.pk);work.refresh_from_db();work.case.refresh_from_db();self.entry['enabled']=True
        with transaction.atomic():
            result=flow.act(work,{'activity':'ACT11'},None,None,None,None,None)
        factory.manage(self.f['actor'],work.pk,work.revision,'cancel')
        with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,result['mcp_intent'])
        self.client.call.assert_not_called()

    def reserved_factory(self):
        from django.db import transaction
        from apps.workflows import factory, factory_ledger as flow
        work=self.factory_work();self.entry['enabled']=False
        factory.run_until_wait(work.pk);work.refresh_from_db();work.case.refresh_from_db();self.entry['enabled']=True
        with transaction.atomic():
            result=flow.act(work,{'activity':'ACT11'},None,None,None,None,None)
        return work,result['mcp_intent']

    def replace_factory_policy(self,work,enabled):
        from datetime import timedelta
        from django.utils import timezone
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        from apps.workflows import factory
        _,value=factory.profile(work)
        value=dict(value,enabled=enabled)
        successor=draft_operator_policy(self.f['actor'],self.f['case'].pk,'OPS.factory_ledger_execution',value,
            self.f['e'].pk,timezone.now()-timedelta(seconds=1))
        transition(self.f['actor'],successor.pk,'validated');transition(self.f['actor'],successor.pk,'active')
        return successor

    def test_factory_disabled_profile_holds_reserved_dispatch(self):
        work,intent=self.reserved_factory()
        self.replace_factory_policy(work,False)
        with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,intent)
        self.client.call.assert_not_called()
        self.assertFalse(Audit.objects.filter(case=self.f['case'],action=broker.PREFIX+'started',data__intent=intent).exists())

    def test_factory_replaced_profile_holds_reserved_dispatch(self):
        work,intent=self.reserved_factory()
        self.replace_factory_policy(work,True)
        with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,intent)
        self.client.call.assert_not_called()

    def test_factory_verified_work_holds_old_reserved_dispatch(self):
        from apps.workflows import factory
        work,intent=self.reserved_factory()
        check=lh.verify(self.f,self.lineage);lh.review(self.f,check)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'verified',work.finding)
        with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,intent)
        self.client.call.assert_not_called()

    def test_factory_blocked_work_holds_reserved_dispatch(self):
        from apps.workflows import factory
        work,intent=self.reserved_factory()
        token=factory.claim(work.pk)
        factory.record_failure(work.pk,token,ValidationError('Synthetic existing factory hold'))
        work.refresh_from_db();self.assertEqual(work.status,'blocked')
        with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,intent)
        self.client.call.assert_not_called()

    def test_factory_configuration_hold_blocks_reserved_dispatch(self):
        from apps.workflows import factory
        work,intent=self.reserved_factory()
        token=factory.claim(work.pk)
        factory.record_failure(work.pk,token,ValidationError('configuration_needed: synthetic existing factory hold'))
        work.refresh_from_db();self.assertEqual(work.status,'configuration_needed')
        with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,intent)
        self.client.call.assert_not_called()

    def test_factory_profile_changed_inflight_retains_stale_observation(self):
        work,intent=self.reserved_factory()
        def result(*args):
            self.replace_factory_policy(work,False)
            return {'id':self.lineage.payload['target_reference']}
        self.client.call.side_effect=result
        evidence=broker.execute(self.f['actor'],self.f['case'].pk,intent)
        self.assertFalse(json.loads(evidence.body)['current_at_capture'])
        with self.assertRaises(ValidationError):broker.reconcile(self.f['actor'],self.f['case'].pk,intent)
        self.assertEqual(self.client.call.call_count,1)
        self.assertFalse(self.lineage.checks.exists())


    def test_enclosing_transaction_rejected_before_claim_or_transport(self):
        from django.db import transaction
        row=self.reserve()
        self.client.reset_mock()
        with transaction.atomic():
            with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
        self.client.initialize.assert_not_called()
        self.client.call.assert_not_called()
        self.assertFalse(Audit.objects.filter(case=self.f['case'],action=broker.PREFIX+'started',data__intent=row.pk).exists())

    def test_disabled_autocommit_rejected_before_claim_or_transport(self):
        from django.db import connection
        row=self.reserve()
        self.client.reset_mock()
        connection.set_autocommit(False)
        try:
            with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
        finally:
            connection.rollback()
            connection.set_autocommit(True)
        self.client.initialize.assert_not_called()
        self.client.call.assert_not_called()
        self.assertFalse(Audit.objects.filter(case=self.f['case'],action=broker.PREFIX+'started',data__intent=row.pk).exists())

    def assert_no_synthetic_credential_retained(self):
        from apps.core.models import Evidence
        from apps.workflows.readiness_models import IntegrationObservation, IntegrationAssessment, IntegrationReview, IntegrationProbe
        token='SYNTHETIC-NOT-A-CREDENTIAL'
        collections=[Evidence.objects.filter(case=self.f['case']).values(),Audit.objects.filter(case=self.f['case']).values(),
            IntegrationObservation.objects.filter(contract__case=self.f['case']).values(),
            IntegrationAssessment.objects.filter(contract__case=self.f['case']).values(),
            IntegrationReview.objects.filter(assessment__contract__case=self.f['case']).values(),
            IntegrationProbe.objects.filter(contract__case=self.f['case']).values()]
        for rows in collections:
            self.assertNotIn(token,json.dumps(list(rows),default=str))

    def test_native_discovery_echo_not_retained_in_readiness_state(self):
        from adapters import quickbooks_mcp as wire
        from apps.workflows.readiness_models import IntegrationObservation
        token='SYNTHETIC-NOT-A-CREDENTIAL'
        job=readiness_delivery.reserve(self.f['actor'],self.f['case'].pk,self.f['contract'].pk,'echo-health','health')
        def response(method,params):
            if method=='initialize':return {'protocolVersion':VERSION,'capabilities':{'tools':{}},'serverInfo':{}}
            self.assertEqual(method,'tools/list')
            return {'tools':[dict(TOOL,description=token)]}
        # Keep the real Client discovery/echo guard. Mock only external RPC traffic.
        with patch.object(broker,'Client',wire.Client),patch.object(wire.Client,'request',side_effect=response) as rpc,patch.object(wire,'transport',return_value=None) as notification:
            self.assertTrue(readiness_delivery.run_once(case_id=self.f['case'].pk))
            job.refresh_from_db();self.assertEqual(job.status,'unknown');self.assertEqual(job.attempts,1)
            self.assertFalse(IntegrationObservation.objects.filter(job=job).exists())
            with self.assertRaises(ValidationError) as error:
                readiness_delivery.operate(self.f['actor'],self.f['case'].pk,job.pk,'retry','No replay of unknown discovery')
            self.assertNotIn(token,str(error.exception))
            self.assertEqual(notification.call_count,1)
            self.assertEqual([call.args[0] for call in rpc.call_args_list],['initialize','tools/list'])
        self.assert_no_synthetic_credential_retained()
        self.assertFalse(self.lineage.checks.exists())

    def test_native_schema_valid_projection_echo_records_unknown_once(self):
        from adapters import quickbooks_mcp as wire
        # Explicit synthetic reviewed output schema, not an invented Intuit contract.
        self.entry['output_schema']['properties']['note']={'type':'string','maxLength':100}
        self.entry['output_schema']['required'].append('note')
        rh.probe(self.f,key='echo-output-health')
        assessment=readiness.assess(self.f['actor'],self.f['case'].pk,self.f['contract'].pk,'echo-output-ready')
        readiness.review(self.f['reviewer'],self.f['case'].pk,assessment.pk,'confirm','echo-output-confirm',self.f['review_evidence'].pk)
        readiness.select(self.f['actor'],self.f['case'].pk,self.f['contract'].pk,self.f['selection_evidence'].pk)
        row=self.reserve();token='SYNTHETIC-NOT-A-CREDENTIAL'
        def response(method,params):
            if method=='initialize':return {'protocolVersion':VERSION,'capabilities':{'tools':{}},'serverInfo':{}}
            if method=='tools/list':return {'tools':[copy.deepcopy(TOOL)]}
            self.assertEqual(method,'tools/call')
            return {'structuredContent':{'id':self.lineage.payload['target_reference'],'note':token}}
        with patch.object(broker,'Client',wire.Client),patch.object(wire.Client,'request',side_effect=response) as rpc,patch.object(wire,'transport',return_value=None):
            result=broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
            self.assertEqual(json.loads(result.body)['result'],{'status':'unknown','projection':None})
            self.assertEqual([call.args[0] for call in rpc.call_args_list],['initialize','tools/list','tools/call'])
            calls=rpc.call_count
            recovered=broker.reconcile(self.f['actor'],self.f['case'].pk,row.pk)
            self.assertEqual(recovered['mcp_outcome'],'unknown');self.assertFalse(recovered['finance_verification'])
            self.assertEqual(rpc.call_count,calls)
            with self.assertRaises(ValidationError):broker.execute(self.f['actor'],self.f['case'].pk,row.pk)
            self.assertEqual(rpc.call_count,calls)
        self.assertEqual(Audit.objects.filter(case=self.f['case'],action=broker.PREFIX+'started',data__intent=row.pk).count(),1)
        self.assertEqual(Audit.objects.filter(case=self.f['case'],action=broker.PREFIX+'completed',data__intent=row.pk).count(),1)
        self.assert_no_synthetic_credential_retained()
        self.assertFalse(self.lineage.checks.exists())
