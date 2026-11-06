"""Operationally flagged synthetic people/values; real services and PostgreSQL."""
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy import role_assignments as rules
from apps.policy.services import role_policy,transition,resolve
from apps.policy.models import Configuration
from apps.pmo.services import decide,sign_baseline
from apps.pmo.models import Decision,Baseline
from adapters.role_assignments import LocalRoleAssignmentsAdapter
from apps.agents.role_assignments import investigate
from tests.helpers import setup_case,prepared,rev


def fixture(explicit=True):
    a,c=setup_case(synthetic=False,username='explicit-role-owner');e=prepared(a,c)
    people={role:get_user_model().objects.create_user(username='explicit-'+role.replace(' ','-')) for role in ['CEO','PMO Lead']}
    for user in people.values():
        for action in ['case.read','decision.record']:Grant.objects.create(user=user,case=c,action=action)
    value=json.loads((settings.BASE_DIR/'fixtures/role-eligibility.json').read_text())
    window=dict(value['eligibility'],valid_from=(timezone.now()-timedelta(minutes=1)).isoformat(),valid_until=(timezone.now()+timedelta(hours=1)).isoformat())
    assignments=[dict(role=role,user_id=a.pk,**({'eligibility':deepcopy(window)} if explicit else {})) for role in value['roles']]
    assignments += [{'role':role,'user_id':user.pk} for role,user in people.items()]
    p=rules.draft(a,c.pk,assignments,e['policy_decision'].pk,timezone.now()-timedelta(seconds=1))
    transition(a,p.pk,'validated');transition(a,p.pk,'active')
    return {'actor':a,'case':c,'e':e,'people':people,'assignments':assignments,'policy':p,'window':window}


def decisions(f):
    for role in ['PM','Head of PMO']:decide(f['actor'],f['case'].pk,role,rev(f['case']))
    for role,user in f['people'].items():decide(user,f['case'].pk,role,rev(f['case']))


class RoleEligibilityTests(TestCase):
    def test_exact_explicit_bundle_runs_native_decisions_and_baseline_without_new_gates(self):
        self.assertEqual(connection.vendor,'postgresql');f=fixture();decisions(f)
        sign_baseline(f['actor'],f['case'].pk,f['e']['signature'].pk,rev(f['case']))
        self.assertEqual(Decision.objects.count(),4)
        self.assertEqual(Baseline.objects.get(case=f['case']).signed_id,f['e']['signature'].pk)
        report=LocalRoleAssignmentsAdapter().read(f['actor'],f['case'].pk)
        self.assertEqual(report['assignments'][0]['eligibility'],'explicit_current')
        self.assertFalse(report['action_authority_granted']);self.assertFalse(report['independence_controls_waived'])

    def test_missing_eligibility_holds_only_multirole_decision_and_capture_remains_available(self):
        f=fixture(False);a,c=f['actor'],f['case']
        self.assertEqual(resolve(rules.COMPONENT,c).status,'ACTIVE')
        with self.assertRaisesMessage(ValidationError,'Operational dual-role eligibility is not configured'):decide(a,c.pk,'PM',rev(c))
        self.assertEqual(role_policy(f['people']['CEO'],c,'CEO').pk,f['policy'].pk)
        self.assertTrue(add_evidence(a,c.pk,'document','Unrelated evidence capture','synthetic:role-test').pk)
        self.assertEqual(len(investigate(a,c.pk)['held_bundles']),1);self.assertFalse(Decision.objects.exists())

    def test_expiry_is_half_open_actor_specific_and_stales_unsigned_approval_use(self):
        f=fixture();decisions(f);end=rules.instant(f['window']['valid_until'])
        with patch('apps.policy.role_assignments.timezone.now',return_value=end):
            self.assertEqual(resolve(rules.COMPONENT,f['case']).status,'ACTIVE')
            with self.assertRaisesMessage(ValidationError,'window is not current'):role_policy(f['actor'],f['case'],'PM')
            self.assertEqual(role_policy(f['people']['CEO'],f['case'],'CEO').pk,f['policy'].pk)
            with self.assertRaises(ValidationError):sign_baseline(f['actor'],f['case'].pk,f['e']['signature'].pk,rev(f['case']))
        self.assertIsNone(Baseline.objects.get(case=f['case']).signed_id)

    def test_invalid_bundles_remain_drafts_and_cannot_replace_active_nomination(self):
        f=fixture();a,c=f['actor'],f['case'];base=f['assignments'];bad=[]
        for field,value in [('valid_until',f['window']['valid_from']),('valid_from','2026-10-29T00:00:00'),('roles',['PM'])]:
            rows=deepcopy(base)
            for row in rows[:2]:row['eligibility'][field]=value
            bad.append(rows)
        rows=deepcopy(base);rows[1].pop('eligibility');bad.append(rows)
        rows=deepcopy(base);rows[1]['eligibility']['valid_until']=(timezone.now()+timedelta(days=1)).isoformat();bad.append(rows)
        rows=deepcopy(base);rows[0]['waive_independence']=True;bad.append(rows)
        rows=deepcopy(base);rows[0]['user_id']=True;bad.append(rows)
        for rows in bad:
            p=rules.draft(a,c.pk,rows,f['e']['policy_decision'].pk,timezone.now())
            with self.assertRaises(ValidationError):transition(a,p.pk,'validated')
            self.assertEqual(p.states.latest('pk').state,'draft')
            self.assertEqual(resolve(rules.COMPONENT,c).configuration.pk,f['policy'].pk)

    def test_eligibility_cannot_grant_action_or_waive_native_reviewer_independence(self):
        f=fixture();a,c=f['actor'],f['case']
        Grant.objects.filter(user=a,case=c,action='decision.record').update(active=False)
        self.assertEqual(role_policy(a,c,'PM').pk,f['policy'].pk)
        with self.assertRaises(PermissionDenied):decide(a,c.pk,'PM',rev(c))
        from apps.finance.ledger_agents import authority
        with self.assertRaisesMessage(PermissionDenied,'Independent Finance reviewer required'):
            authority(a,c,'reviewer',value={'reviewer_id':a.pk,'projector_id':a.pk,'owner_id':a.pk})
        self.assertFalse(Decision.objects.exists())

    def test_policy_successor_and_revocation_require_fresh_native_authority(self):
        f=fixture();decisions(f);a,c=f['actor'],f['case']
        p=rules.draft(a,c.pk,f['assignments'],f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1))
        transition(a,p.pk,'validated');transition(a,p.pk,'active')
        with self.assertRaisesMessage(ValidationError,'authority configuration changed'):sign_baseline(a,c.pk,f['e']['signature'].pk,rev(c))
        transition(a,p.pk,'revoked')
        with self.assertRaises(ValidationError):role_policy(a,c,'PM')
        self.assertEqual(Decision.objects.count(),4)

    def test_csrf_typed_ui_drafts_only_and_agent_rechecks_current_scope(self):
        f=fixture(False);a,c=f['actor'],f['case'];client=Client(enforce_csrf_checks=True);client.force_login(a)
        url=reverse('policy',args=[c.pk]);self.assertContains(client.get(url),'Role assignments and explicit eligibility')
        self.assertEqual(client.post(url,{}).status_code,403)
        explicit=deepcopy(f['assignments'])
        for row in explicit[:2]:row['eligibility']=deepcopy(f['window'])
        result=client.post(url,{'action':'roles_draft','assignments':json.dumps(explicit),'evidence':f['e']['policy_decision'].pk,'effective_from':(timezone.now()-timedelta(seconds=1)).isoformat(),'csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(result.status_code,302);p=Configuration.objects.filter(case=c,component=rules.COMPONENT).latest('pk')
        self.assertEqual(p.states.latest('pk').state,'draft');self.assertEqual(resolve(rules.COMPONENT,c).configuration.pk,f['policy'].pk)
        for action in ['validated','active']:
            self.assertEqual(client.post(url,{'action':action,'configuration':p.pk,'csrfmiddlewaretoken':client.cookies['csrftoken'].value}).status_code,302)
        self.assertEqual(role_policy(a,c,'PM').pk,p.pk)
        report_url=reverse('role_eligibility_guidance',args=[c.pk]);self.assertContains(client.get(report_url),'explicit_current')
        Grant.objects.filter(user=a,case=c,action='policy.read').update(active=False)
        self.assertEqual(client.get(report_url).status_code,403)
        for pk in [c.pk,setup_case(username='foreign-eligibility')[1].pk]:
            with self.assertRaises(PermissionDenied):LocalRoleAssignmentsAdapter().read(a,pk)

    def test_scoped_bundle_adoption_requires_origin_access_and_never_installs_action_grants(self):
        from apps.policy import scopes
        f=fixture();a,c=f['actor'],f['case']
        source=rules.draft(a,c.pk,f['assignments'],f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1))
        transition(a,source.pk,'validated');scope=scopes.create(a,source.pk,'organization',c.tenant,[])
        scopes.transition(a,scope.pk,'validated');scopes.transition(a,scope.pk,'active')
        reader,target=setup_case(synthetic=False,username='role-target-owner')
        proof=add_evidence(reader,target.pk,'policy_decision','Explicit synthetic target adoption','synthetic:role-scope')
        for action in ['case.read','policy.read']:Grant.objects.create(user=reader,case=c,action=action)
        local=scopes.apply(reader,scope.pk,target.pk,proof.pk,[])
        transition(reader,local.pk,'validated');transition(reader,local.pk,'active')
        self.assertEqual(role_policy(a,target,'PM').pk,local.pk)
        self.assertFalse(Grant.objects.filter(user=a,case=target).exists())
        with self.assertRaises(PermissionDenied):decide(a,target.pk,'PM',rev(target))
        self.assertEqual(LocalRoleAssignmentsAdapter().read(reader,target.pk)['configuration'],local.pk)
        Grant.objects.filter(user=reader,case=c,action='policy.read').update(active=False)
        with self.assertRaises(PermissionDenied):LocalRoleAssignmentsAdapter().read(reader,target.pk)
        scopes.transition(a,scope.pk,'revoked')
        with self.assertRaises(ValidationError):role_policy(a,target,'PM')


from tests.test_emergencies import EmergencyFixture


class EmergencyBundleTests(EmergencyFixture,TestCase):
    def test_v2_shared_security_engineering_requires_explicit_current_bundle_and_fresh_decisions(self):
        from apps.policy.change_drafts import draft_standard_policy
        from apps.policy.services import reference_values
        from tests.document_helpers import artifact
        from tests.test_emergencies import GATES
        from apps.pmo.emergencies import authorize_emergency,preauthorization_inputs
        from apps.pmo.models import EmergencyAuthorization
        a,c,e=self.actor,self.case,self.e['policy_decision']
        value={'mode':'coexist','incident_lead_role':'Security Lead','incident_engineering_overlap':'explicit_same_person',
            'exception_roles':[],'priority_basis':'explicit_incident_p1_attestation','role_eligibility':'current_D05_bundle'}
        p=draft_standard_policy(a,c.pk,'D01.emergency_glpi_relationship',value,e.pk,timezone.now()-timedelta(seconds=1))
        transition(a,p.pk,'validated');transition(a,p.pk,'active')
        artifact(a,c,'D01.satisfied_gate_map','schema:psl/change-satisfied-gates/v2',{'emergency':GATES},e)
        self.decisions(incident_role='Security Lead');self.glpi()
        with self.assertRaisesMessage(ValidationError,'Current exact explicit D05 eligibility required'):
            authorize_emergency(a,c.pk,self.profile.pk,rev(c))
        assignments=reference_values(self.roles);end=timezone.now()+timedelta(hours=1)
        window={'roles':sorted({r['role'] for r in assignments}),'valid_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'valid_until':end.isoformat()}
        for row in assignments:row['eligibility']=deepcopy(window)
        cfg=rules.draft(a,c.pk,assignments,e.pk,timezone.now()-timedelta(seconds=1))
        transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        with self.assertRaises(ValidationError):authorize_emergency(a,c.pk,self.profile.pk,rev(c))
        self.decisions(incident_role='Security Lead')
        # Existing source-verified GLPI receipts remain; only current human decisions changed.
        authorization=authorize_emergency(a,c.pk,self.profile.pk,rev(c))
        self.assertEqual(EmergencyAuthorization.objects.count(),1)
        self.assertEqual(authorization.profile_id,self.profile.pk)
        with patch('apps.policy.role_assignments.timezone.now',return_value=end):
            with self.assertRaises(ValidationError):preauthorization_inputs(c,self.profile)
