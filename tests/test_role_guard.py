"""Real D05/delegated document services; all people/operational flags/values are fixtures."""
import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import TestCase,TransactionTestCase,Client
from django.db import transaction,DatabaseError,close_old_connections
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Audit
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy import role_assignments as nominations,pilot,pilot_bindings as bindings
from apps.policy.services import transition,decision_authority,role_policy,resolve
from apps.policy.models import Configuration,PilotBinding
from apps.documents import controlled
from apps.documents.models import ControlledReview,Publication
from apps.pmo.models import Decision
from apps.pmo.services import decide
from adapters import pilot_guards,pilot_preflight
from tests.helpers import setup_case,prepared,rev
from tests.document_helpers import DEFINITION,fields
from tests.test_pilot_preflight import selection


def fixture(own_role=False,explicit=False):
    a,c=setup_case(synthetic=False,username='authority-principal');e=prepared(a,c)
    b=get_user_model().objects.create_user(username='authority-delegate')
    for action in ['case.read','policy.read','pilot.read','document.review_controlled']:
        Grant.objects.create(user=b,case=c,action=action)
    config=json.loads((settings.BASE_DIR/'fixtures/role-delegation.json').read_text())
    start=timezone.now()-timedelta(minutes=1);end=timezone.now()+timedelta(hours=2)
    window={'roles':config['principal_roles'],'valid_from':start.isoformat(),'valid_until':end.isoformat()}
    assignments=[{'role':role,'user_id':a.pk,'eligibility':deepcopy(window)} for role in config['principal_roles']]
    if own_role:assignments.append({'role':config['delegate_own_role'],'user_id':b.pk})
    p=nominations.draft(a,c.pk,assignments,e['policy_decision'].pk,start);transition(a,p.pk,'validated');transition(a,p.pk,'active')
    value={'role':config['role'],'principal_id':a.pk,'delegate_id':b.pk,'valid_from':start.isoformat(),'valid_until':(end+timedelta(hours=1)).isoformat()}
    if explicit:value['delegate_eligibility']={'roles':config['delegate_combined_roles'] if own_role else [config['role']],
        'valid_from':start.isoformat(),'valid_until':(timezone.now()+timedelta(minutes=10)).isoformat()}
    d=nominations.draft_delegations(a,c.pk,[value],e['policy_decision'].pk,start);transition(a,d.pk,'validated');transition(a,d.pk,'active')
    return {'a':a,'b':b,'c':c,'e':e,'nomination':p,'delegation':d,'value':value,'end':end,'config':config}


def check(f,actor=None,role='PMO Lead',action='approve',delegated=False):
    return pilot_guards.check(f['a'],f['c'],{'operation':'role.decision.evaluate','user_id':(actor or f['a']).pk,
        'arguments':{'expected_revision':rev(f['c']),'role':role,'decision_action':action,'delegated':delegated}})


class RoleGuardTests(TestCase):
    def test_direct_guard_shares_native_authority_without_granting_actions_or_requiring_unused_policies(self):
        f=fixture();a,c=f['a'],f['c'];transition(a,f['delegation'].pk,'revoked')
        Grant.objects.filter(user=a,case=c,action='decision.record').update(active=False)
        before=(Decision.objects.count(),Audit.objects.count(),rev(c))
        result=check(f);self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(result['native_required_components'],['D05.role_principal_assignments'])
        self.assertFalse(result['head']['role_evaluation']['action_grants_evaluated']);self.assertFalse(result['business_approval'])
        self.assertEqual(before,(Decision.objects.count(),Audit.objects.count(),rev(c)))
        with self.assertRaises(PermissionDenied):decide(a,c.pk,'PMO Lead',rev(c))
        self.assertEqual(check(f,action='reject')['state'],'HELD')

    def test_v2_principal_can_delegate_single_role_and_actual_document_review_expires_with_principal_eligibility(self):
        f=fixture();a,b,c=f['a'],f['b'],f['c']
        authority=decision_authority(b,c,'PMO Lead',delegated=True)
        self.assertEqual(authority['D05.role_principal_assignments'],f['nomination'].pk)
        self.assertEqual(check(f,b,delegated=True)['state'],'READY_AT_OBSERVATION')
        self.assertEqual(check(f,b)['state'],'HELD')
        source=add_evidence(a,c.pk,'completion','Delivery is progressing. Internal incident trace is private.','synthetic:authority')
        template=controlled.register_template(a,c.pk,'Authority status report',DEFINITION,f['e']['policy_decision'].pk,rev(c))
        version=controlled.create_version(a,c.pk,template.pk,'Authority report','client',fields(source),rev(c))
        controlled.request_review(a,c.pk,version.pk,rev(c))
        with self.assertRaises(PermissionDenied):controlled.review_version(b,c.pk,version.pk,'approve','No impersonation',rev(c))
        review=controlled.review_version(b,c.pk,version.pk,'approve','Current explicit delegated review',rev(c),delegated=True)
        self.assertEqual(review.authority,authority)
        with patch('apps.policy.role_assignments.timezone.now',return_value=f['end']):
            with self.assertRaises(ValidationError):controlled.validate_review(c,version)
        self.assertEqual(ControlledReview.objects.count(),1);self.assertFalse(Publication.objects.exists())

    def test_operational_mixed_delegate_needs_explicit_bundle_while_own_role_remains_available(self):
        f=fixture(own_role=True);a,b,c=f['a'],f['b'],f['c']
        with self.assertRaisesMessage(ValidationError,'delegated role-bundle eligibility is not configured'):
            decision_authority(b,c,'PMO Lead',delegated=True)
        self.assertEqual(role_policy(b,c,'Finance').pk,f['nomination'].pk)
        self.assertEqual(check(f,b,delegated=True)['state'],'HELD')
        value=deepcopy(f['value']);value['delegate_eligibility']={'roles':f['config']['delegate_combined_roles'],
            'valid_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'valid_until':(timezone.now()+timedelta(minutes=10)).isoformat()}
        p=nominations.draft_delegations(a,c.pk,[value],f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(a,p.pk,'validated');transition(a,p.pk,'active')
        self.assertEqual(check(f,b,delegated=True)['state'],'READY_AT_OBSERVATION')
        end=nominations.instant(value['delegate_eligibility']['valid_until'])
        with patch('apps.policy.delegation_validators.timezone.now',return_value=end):
            with self.assertRaises(ValidationError):decision_authority(b,c,'PMO Lead',delegated=True)
            self.assertEqual(role_policy(b,c,'Finance').pk,f['nomination'].pk)

    def test_invalid_delegated_bundle_drafts_cannot_replace_active_rule(self):
        f=fixture(own_role=True,explicit=True);bad=[]
        value=deepcopy(f['value']);value['delegate_eligibility']['roles']=['Finance'];bad.append(value)
        value=deepcopy(f['value']);value['delegate_eligibility']['valid_from']='2026-10-29T00:00:00';bad.append(value)
        value=deepcopy(f['value']);value['delegate_eligibility']['valid_until']=value['delegate_eligibility']['valid_from'];bad.append(value)
        value=deepcopy(f['value']);value['delegate_eligibility']['valid_from']=(timezone.now()+timedelta(days=2)).isoformat();value['delegate_eligibility']['valid_until']=(timezone.now()+timedelta(days=3)).isoformat();bad.append(value)
        value=deepcopy(f['value']);value['waive_independence']=True;bad.append(value)
        value=deepcopy(f['value']);value['principal_id']=True;bad.append(value)
        for value in bad:
            p=nominations.draft_delegations(f['a'],f['c'].pk,[value],f['e']['policy_decision'].pk,timezone.now())
            with self.assertRaises(ValidationError):transition(f['a'],p.pk,'validated')
            self.assertEqual(p.states.latest('pk').state,'draft')
            self.assertEqual(resolve('D05.delegation_rules',f['c']).configuration.pk,f['delegation'].pk)

    def test_typed_delegation_ui_drafts_without_activation_and_boolean_false_binding_is_valid(self):
        f=fixture(own_role=True);a,b,c=f['a'],f['b'],f['c'];client=Client(enforce_csrf_checks=True);client.force_login(a)
        url=reverse('policy',args=[c.pk]);self.assertContains(client.get(url),'Delegation and delegated role eligibility')
        self.assertEqual(client.post(url,{}).status_code,403)
        value=deepcopy(f['value']);value['delegate_eligibility']={'roles':f['config']['delegate_combined_roles'],
            'valid_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'valid_until':(timezone.now()+timedelta(minutes=10)).isoformat()}
        response=client.post(url,{'action':'delegations_draft','delegations':json.dumps([value]),'evidence':f['e']['policy_decision'].pk,
            'effective_from':timezone.now().isoformat(),'csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code,302);draft=Configuration.objects.filter(case=c,component='D05.delegation_rules').latest('pk')
        self.assertEqual(draft.states.latest('pk').state,'draft');self.assertEqual(resolve('D05.delegation_rules',c).configuration.pk,f['delegation'].pk)
        p=selection(a,c);p['operations']=['role.decision.evaluate'];p['participants'].append({'user_id':b.pk,'actions':['case.read']})
        selected=pilot.configure(a,c.pk,p);url=reverse('pilot_bindings',args=[c.pk,selected.pk]);self.assertContains(client.get(url),'Evaluate explicit scoped delegation')
        example=json.loads((settings.BASE_DIR/'fixtures/pilot-bindings.json').read_text());d=example['deployment'];technical=pilot_preflight.technical()
        response=client.post(url,dict(operation='role.decision.evaluate',participant=b.pk,expected_revision=rev(c),role='Finance',decision_action='approve',
            deployment_ref=d['ref'],revision=d['revision'],web_key_ref=d['web_key_ref'],worker_key_ref=d['worker_key_ref'],families=d['families'],freshness_seconds=d['freshness_seconds'],
            csrfmiddlewaretoken=client.cookies['csrftoken'].value,**{key:technical[key] for key in ['source_identity','schema_identity','database_identity']}))
        self.assertEqual(response.status_code,302);binding=PilotBinding.objects.get()
        self.assertIs(binding.payload['guards'][0]['arguments']['delegated'],False)
        self.assertEqual(bindings.report(a,c,selected)['native_guards'][0]['state'],'READY_AT_OBSERVATION')

    def test_nonapprove_variants_use_only_current_explicit_action_matrix(self):
        from tests.document_helpers import artifact
        f=fixture(own_role=True,explicit=True)
        self.assertEqual(check(f,f['b'],action='reject',delegated=True)['state'],'HELD')
        cfg=artifact(f['a'],f['c'],'D05.decision_action_matrix','schema:psl/decision-actions/v1',
            {'rules':[{'role':'PMO Lead','actions':['reject']}]},f['e']['policy_decision'])
        result=check(f,f['b'],action='reject',delegated=True)
        self.assertEqual(result['state'],'READY_AT_OBSERVATION');self.assertIn(cfg.pk,result['policy_pins'])
        self.assertEqual(check(f,f['b'],action='return',delegated=True)['state'],'HELD')
        self.assertFalse(Decision.objects.exists())

    def test_principal_unconfigured_eligibility_and_delegate_nomination_drift_hold_only_delegated_use(self):
        from apps.policy.services import reference_values
        f=fixture(own_role=True,explicit=True);a,b,c=f['a'],f['b'],f['c']
        values=reference_values(f['nomination'])
        for row in values:row.pop('eligibility',None)
        p=nominations.draft(a,c.pk,values,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(a,p.pk,'validated');transition(a,p.pk,'active')
        with self.assertRaises(ValidationError):decision_authority(b,c,'PMO Lead',delegated=True)
        self.assertEqual(role_policy(b,c,'Finance').pk,p.pk)
        values=reference_values(f['nomination']);window={'roles':['Finance','QA'],'valid_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'valid_until':f['end'].isoformat()}
        values=[row for row in values if row['user_id']!=b.pk]+[{'role':role,'user_id':b.pk,'eligibility':deepcopy(window)} for role in window['roles']]
        p=nominations.draft(a,c.pk,values,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(a,p.pk,'validated');transition(a,p.pk,'active')
        with self.assertRaisesMessage(ValidationError,'Exact delegated role-bundle eligibility changed'):decision_authority(b,c,'PMO Lead',delegated=True)
        self.assertEqual(role_policy(b,c,'Finance').pk,p.pk)

    def test_sql_boolean_variant_closure_and_agent_distinguish_unused_components_from_runtime_holds(self):
        from apps.agents.pilot import investigate
        from apps.policy.pilot_binding_validators import validate
        f=fixture();a,c=f['a'],f['c'];transition(a,f['delegation'].pk,'revoked')
        p=selection(a,c);p['operations']=['role.decision.evaluate'];selected=pilot.configure(a,c.pk,p)
        example=json.loads((settings.BASE_DIR/'fixtures/pilot-bindings.json').read_text());tech=pilot_preflight.technical()
        payload={'format':'psl.pilot-bindings/v1','guards':[{'operation':'role.decision.evaluate','user_id':a.pk,
            'arguments':{'expected_revision':rev(c),'role':'PMO Lead','decision_action':'approve','delegated':False}}],
            'deployment':dict(example['deployment'],expected={key:tech[key] for key in ['source_identity','schema_identity','database_identity']})}
        binding=bindings.configure(a,c.pk,selected.pk,payload);pack=pilot.capture(a,c.pk,selected.pk)
        run=investigate(a,c.pk,pack.pk)
        self.assertFalse(any('role.decision.evaluate: dependent runtime policy hold' in text for text in run['findings']))
        self.assertTrue(any('not needed by the selected native variants' in text for text in run['findings']))
        self.assertEqual(run['effect_tools'],[])
        for change in [lambda p:p['guards'][0]['arguments'].update(delegated=0),lambda p:p['guards'][0]['arguments'].update(decision_action='execute'),lambda p:p['guards'][0]['arguments'].update(role='Root')]:
            bad=deepcopy(payload);change(bad)
            with self.assertRaises(ValidationError):validate(selected,bad)
            successor=pilot.configure(a,c.pk,dict(selected.payload),selected.pk)
            values={field.name:getattr(binding,field.name) for field in binding._meta.fields if field.name not in ['id','created_at','contract','payload']}
            with self.assertRaisesMessage(DatabaseError,'PSL'),transaction.atomic():PilotBinding.objects.create(**values,contract=successor,payload=bad)
            PilotBinding.objects.create(**values,contract=successor,payload=payload)
            selected=successor


    def test_scoped_delegation_origin_revocation_denies_dependent_metadata_without_holding_direct_nomination(self):
        from apps.policy import scopes
        f=fixture(own_role=True,explicit=True);a,b,c=f['a'],f['b'],f['c']
        source_owner,source_case=setup_case(synthetic=False,username='delegation-source-owner')
        proof=add_evidence(source_owner,source_case.pk,'policy_decision','Synthetic organization delegation source','synthetic:role-scope')
        cfg=nominations.draft_delegations(source_owner,source_case.pk,[f['value']],proof.pk,timezone.now()-timedelta(seconds=1))
        transition(source_owner,cfg.pk,'validated');scope=scopes.create(source_owner,cfg.pk,'organization',source_case.tenant,[])
        scopes.transition(source_owner,scope.pk,'validated');scopes.transition(source_owner,scope.pk,'active')
        for action in ['case.read','policy.read']:Grant.objects.create(user=a,case=source_case,action=action)
        local=scopes.apply(a,scope.pk,c.pk,f['e']['policy_decision'].pk,[])
        transition(a,local.pk,'validated');transition(a,local.pk,'active')
        self.assertEqual(check(f,b,delegated=True)['state'],'READY_AT_OBSERVATION')
        Grant.objects.filter(user=a,case=source_case,action='policy.read').update(active=False)
        with self.assertRaises(PermissionDenied):check(f,b,delegated=True)
        self.assertEqual(check(f)['state'],'READY_AT_OBSERVATION')


from concurrent.futures import ThreadPoolExecutor
from threading import Event


class RoleGuardConcurrencyTests(TransactionTestCase):
    def test_current_grant_revocation_serializes_before_delegated_document_decision(self):
        from apps.core.models import Case
        f=fixture();a,b,c=f['a'],f['b'],f['c']
        source=add_evidence(a,c.pk,'completion','Delivery is progressing. Internal incident trace is private.','synthetic:authority-concurrency')
        template=controlled.register_template(a,c.pk,'Delegated concurrent report',DEFINITION,f['e']['policy_decision'].pk,rev(c))
        version=controlled.create_version(a,c.pk,template.pk,'Concurrent report','client',fields(source),rev(c))
        controlled.request_review(a,c.pk,version.pk,rev(c));revision=rev(c);locked,release,started=Event(),Event(),Event()
        def revoke():
            close_old_connections()
            try:
                with transaction.atomic():
                    Case.objects.select_for_update().get(pk=c.pk)
                    Grant.objects.filter(user=b,case=c,action='document.review_controlled').update(active=False)
                    locked.set();self.assertTrue(release.wait(20))
            finally:close_old_connections()
        def review():
            close_old_connections();started.set()
            try:return controlled.review_version(b,c.pk,version.pk,'approve','Must not use a revoked action grant',revision,delegated=True)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            holder=pool.submit(revoke);self.assertTrue(locked.wait(10));attempt=pool.submit(review);self.assertTrue(started.wait(10))
            release.set();holder.result(timeout=25)
            with self.assertRaises(PermissionDenied):attempt.result(timeout=25)
        self.assertFalse(ControlledReview.objects.exists());self.assertFalse(Publication.objects.exists())
