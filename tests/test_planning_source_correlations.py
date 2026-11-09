"""Exact P06/P17/P18 fixtures. Actual migration0083 must install every SQL guard."""
import copy
import json
import re
from pathlib import Path
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction, DatabaseError
from apps.core.models import Audit, Evidence
from apps.identity.models import Grant
from apps.pmo import planning, planning_sources as sources, commercial
from apps.pmo.models import ActionItem, Baseline, CommercialRevision
from apps.pmo.meetings import change_action
from tests import planning_helpers as h
from tests.helpers import rev


def assert_actual_guards():
    from importlib import import_module
    sql=import_module('apps.workflows.migrations.0083_planning_source_correlation').SQL
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regprocedure('psl_planning_correlation_current(bigint,boolean)')")
        assert cursor.fetchone()[0] is not None, 'Actual0083 must install correlation predicate'
        cursor.execute("SELECT count(*) FROM django_migrations WHERE app='workflows' AND name='0083_planning_source_correlation'")
        assert cursor.fetchone()[0]==1, 'Actual0083 must be recorded'
        for name,body in re.findall(r'CREATE(?: OR REPLACE)? FUNCTION (\w+)\([^$]+?AS \$\$(.*?)\$\$;',sql,re.S):
            cursor.execute('SELECT prosrc FROM pg_proc WHERE proname=%s',[name])
            assert cursor.fetchall()==[(body,)],'Exact actual0083 function body required: '+name


class PlanningSourceCorrelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=h.fixture(username='source-correlation')
        assert_actual_guards()

    def scoped_rows(self,case):
        with connection.cursor() as cursor:
            values=[]
            for table in ['core_case','core_evidence','core_audit','pmo_actionitem']:
                field='id' if table=='core_case' else 'case_id'
                cursor.execute('SELECT to_jsonb(t) FROM '+table+' t WHERE '+field+'=%s ORDER BY id',[case.pk]);values.append(cursor.fetchall())
            cursor.execute('SELECT to_jsonb(s) FROM pmo_actionstate s JOIN pmo_actionitem i ON i.id=s.item_id WHERE i.case_id=%s ORDER BY s.id',[case.pk]);values.append(cursor.fetchall())
            return values

    def capture(self,payload):
        f=self.f
        packet=planning.capture(f['a'],f['c'].pk,payload,planning.latest(f['c'],'packet').pk)
        return packet

    def ready(self,packet):
        f=self.f
        for purpose,meeting in f['meetings'].items():planning.align(f['a'],f['c'].pk,packet.pk,purpose,meeting.pk)
        f['pair']=planning.open_requests(f['a'],f['c'].pk,packet.pk);h.observe(f)
        return planning.prepare(f['a'],f['c'].pk,packet.pk)

    def http(self,actor=None):
        client=Client(enforce_csrf_checks=True);client.force_login(actor or self.f['a'])
        url=reverse('planning',args=[self.f['c'].pk]);self.assertEqual(client.get(url).status_code,200)
        return client,url,client.cookies['csrftoken'].value

    def post(self,client,url,csrf,**data):
        return client.post(url,dict(data,csrfmiddlewaretoken=csrf,revision=rev(self.f['c'])))

    def test_security_physically_absent_with_total_and_no_sow__P06_M02(self):
        from tests.helpers import setup_case
        from apps.core.services import add_evidence
        from apps.pmo import engagement
        actor,case=setup_case(username='p06-no-security-source')
        def evidence(kind,value):return add_evidence(actor,case.pk,kind,json.dumps(value),'synthetic:p06-missing-security')
        prd=evidence('requirements',{'version':'PRD-v1','scope':'Initial project'})
        scope=evidence('plan',{'version':'scope-v1','target_prd_id':prd.pk,'scope':'Initial project'})
        engineering=evidence('engineering_estimate',{'version':'engineering-v1','target_prd_id':prd.pk,'target_scope_id':scope.pk})
        total=evidence('calculator_snapshot',{'calculator_version':'owner-supplied-v7','total':'25000.00','currency':'TST','security_effort':None})
        origin=evidence('engagement_source',{'route':'B','source':'Actual synthetic direct request'})
        engagement.capture(actor,case.pk,'B',origin.pk,'P06-M02-fresh','p06-m02-fresh-capture')
        payload=copy.deepcopy(self.f['payload']);payload.update(prd_id=prd.pk,scope_id=scope.pk,engineering_estimate_id=engineering.pk,security_estimate_id=None)
        payload['source_correlations']=[{'key':field,'source_field':field,'source_id':item.pk,'document_version':'provided-v1',
            'target_prd_id':prd.pk,'target_scope_id':scope.pk,'evidence_id':item.pk,'state':'current',
            'detail':'Explicit supplied-source target declaration','resolution_id':None} for field,item in [('scope_id',scope),('engineering_estimate_id',engineering)]]
        client=Client(enforce_csrf_checks=True);client.force_login(actor);url=reverse('planning',args=[case.pk])
        self.assertEqual(client.get(url).status_code,200)
        response=client.post(url,{'action':'capture','revision':rev(case),'payload':json.dumps(payload),'csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code,302);packet,value=planning.packet(case)
        self.assertIsNone(value['payload']['security_estimate_id'])
        self.assertFalse(case.evidence.filter(kind='security_estimate').exists())
        self.assertFalse(case.evidence.filter(kind__in=['sow','signature']).exists());self.assertFalse(Baseline.objects.filter(case=case).exists())
        self.assertEqual(json.loads(Evidence.objects.get(pk=total.pk).body)['total'],'25000.00')
        self.assertIsNone(json.loads(Evidence.objects.get(pk=total.pk).body)['security_effort'])
        self.assertIn('Security estimate source is missing',planning.report(actor,case.pk)['finding'])
        with self.assertRaisesMessage(ValidationError,'Security estimate source is missing'):planning.inputs(case,packet,False,actor)

    def test_security_missing_despite_total__P06_M02(self):
        f=self.f;p=copy.deepcopy(f['payload']);p['security_estimate_id']=None
        p['source_correlations']=[r for r in p['source_correlations'] if r['source_field']!='security_estimate_id']
        snapshot=h.evidence(f,'calculator_snapshot',{'calculator_version':'owner-supplied-v7','total':'25000.00','currency':'TST','security_effort':None})
        client,url,csrf=self.http();response=self.post(client,url,csrf,action='capture',predecessor=f['packet'].pk,payload=json.dumps(p))
        self.assertEqual(response.status_code,302)
        packet,value=planning.packet(f['c']);self.assertIsNone(value['payload']['security_estimate_id'])
        self.assertEqual(json.loads(Evidence.objects.get(pk=snapshot.pk).body)['total'],'25000.00')
        report=planning.report(f['a'],f['c'].pk)
        self.assertFalse(report['source_correlation']['complete']);self.assertIn('Security estimate source is missing',report['finding'])
        self.assertIn('no zero',report['finding']);
        action=sources.clarify(f['a'],f['c'].pk,packet.pk,'missing.security_estimate_id')
        self.assertIsNone(action.current.owner_id)
        self.assertEqual(action.current.evidence_id,p['prd_id'])
        self.assertIsNone(Baseline.objects.get(case=f['c']).signed_id)
        with self.assertRaises(ValidationError):self.ready(packet)
        selected={k:f['e'][k].pk for k in commercial.SOURCE_KINDS};selected['security_estimate']=None
        with self.assertRaises(ValidationError):commercial.propose(f['a'],f['c'].pk,selected,f['e']['requirements'].pk,'Missing estimate cannot become a complete proposal',rev(f['c']))
        self.assertFalse(CommercialRevision.objects.filter(dossier__case=f['c']).exists())
        self.assertTrue(f['c'].evidence.filter(pk__in=[snapshot.pk,f['e']['plan'].pk,f['e']['costing'].pk]).count()==3)

    def test_conflicting_scope_sources_retained_and_owner_action__P17_M02(self):
        f=self.f;other=h.evidence(f,'scope_baseline','Scope B includes rollout; scope A explicitly excludes rollout')
        p=copy.deepcopy(f['payload']);p['source_correlations'][0]['state']='conflicting'
        p['source_correlations'][0]['detail']='Scope A excludes rollout while scope B includes rollout PRIVATE-SCOPE-INTERPRETATION'
        alt=dict(p['source_correlations'][0],key='alternate-scope',source_id=other.pk,document_version='v2',target_scope_id=other.pk)
        p['source_correlations'].append(alt)
        before=f['e']['plan'].body
        packet=self.capture(p)
        report=planning.report(f['a'],f['c'].pk);self.assertIn('excludes rollout',report['finding'])
        self.assertEqual(len(report['source_correlation']['source_pins']),4)
        item=sources.clarify(f['a'],f['c'].pk,packet.pk,'scope_id')
        self.assertIsNone(item.current.owner_id);self.assertIsNone(item.current.due_at)
        self.assertEqual(sources.clarify(f['a'],f['c'].pk,packet.pk,'scope_id').pk,item.pk)
        from django.contrib.auth import get_user_model
        reader=get_user_model().objects.create_user('ordinary-action-reader')
        for grant in ['case.read','meeting.read','action.read']:Grant.objects.create(case=f['c'],user=reader,action=grant)
        reader_client=Client();reader_client.force_login(reader)
        self.assertNotContains(reader_client.get(reverse('meetings',args=[f['c'].pk])),'PRIVATE-SCOPE-INTERPRETATION')
        self.assertEqual(reader_client.get(reverse('planning',args=[f['c'].pk])).status_code,403)
        self.assertNotIn('PRIVATE-SCOPE-INTERPRETATION',item.current.description)
        self.assertEqual(f['e']['plan'].body,before);self.assertTrue(f['c'].evidence.filter(pk=other.pk).exists())
        p['source_correlations']=[r for r in p['source_correlations'] if r['key']!='alternate-scope']
        with self.assertRaisesMessage(ValidationError,'Retain conflicting source'):self.capture(p)
        self.assertEqual(planning.latest(f['c'],'packet').pk,packet.pk)

    def test_engineering_v3_security_v1_declared_different_prd__P18_M02(self):
        f=self.f;prd3=h.evidence(f,'prd','PRD v3: includes rollout')
        p=copy.deepcopy(f['payload']);p['prd_id']=prd3.pk
        p['source_correlations'][0].update(target_prd_id=prd3.pk)
        p['source_correlations'][1].update(document_version='v3',target_prd_id=prd3.pk,detail='Engineering v3 explicitly estimates PRD v3')
        p['source_correlations'][2].update(document_version='v1',target_prd_id=f['e']['requirements'].pk,detail='Security v1 explicitly estimates PRD v1')
        client,url,csrf=self.http();response=self.post(client,url,csrf,action='capture',predecessor=f['packet'].pk,payload=json.dumps(p))
        self.assertEqual(response.status_code,302);packet,value=planning.packet(f['c'])
        report=planning.report(f['a'],f['c'].pk);finding=next(r for r in report['source_correlation']['findings'] if r['key']=='security_estimate_id')
        self.assertEqual(finding['document_version'],'v1');self.assertEqual(finding['declared_target_prd_id'],f['e']['requirements'].pk)
        self.assertIn('No conversion or equivalence',finding['detail'])
        self.assertEqual(value['payload']['source_correlations'][1]['document_version'],'v3')
        self.assertEqual(value['payload']['source_correlations'][2]['document_version'],'v1')
        self.assertEqual(client.post(url,{'action':'clarify_source','packet_id':packet.pk,'key':'security_estimate_id'}).status_code,403)
        response=self.post(client,url,csrf,action='clarify_source',packet_id=packet.pk,key='security_estimate_id',owner_id=f['owners']['estimates'].pk)
        self.assertEqual(response.status_code,302);self.assertEqual(ActionItem.objects.filter(case=f['c']).count(),1)
        response=self.post(client,url,csrf,action='investigate')
        self.assertEqual(response.status_code,200);self.assertIn('security_estimate_id',[q['key'] for q in response.json()['source_clarification_questions']])
        with self.assertRaises(ValidationError):self.ready(packet)

    def test_independent_document_labels_same_target_are_not_mismatches__P18_M01(self):
        f=self.f;p=copy.deepcopy(f['payload'])
        p['source_correlations'][1]['document_version']='Engineering-v3'
        p['source_correlations'][2]['document_version']='Security-v1'
        packet=self.capture(p);ready=self.ready(packet)
        self.assertTrue(planning.current_readiness(f['c'],ready.pk)['inputs']['source_correlation']['complete'])
        self.assertIsNone(Baseline.objects.get(case=f['c']).signed_id)
        h.evidence(f,'prd','A later unrelated unadopted draft PRD must not replace declared targets')
        self.assertTrue(planning.current_readiness(f['c'],ready.pk)['inputs']['source_correlation']['complete'])

    def test_http_correction_owner_reassignment_disposition_and_currentness(self):
        f=self.f;p=copy.deepcopy(f['payload']);p['source_correlations'][0]['state']='conflicting'
        p['source_correlations'][0]['detail']='Original scope excludes the rollout included in replacement scope'
        packet=self.capture(p);replacement=h.evidence(f,'scope_baseline','Owner-produced replacement scope including rollout')
        response_evidence=h.evidence(f,'planning_clarification','Source owner confirms original is superseded by the exact replacement scope')
        item=sources.clarify(f['a'],f['c'].pk,packet.pk,'scope_id')
        first,owner=f['owners']['scope'],f['owners']['estimates']
        admin,_,admin_csrf=self.http();meeting_url=reverse('meetings',args=[f['c'].pk])
        response=self.post(admin,meeting_url,admin_csrf,action='transition',item=item.pk,operation='assign',evidence=response_evidence.pk,
            reason='Explicit internal source question assignment',action_revision=1,owner=first.pk)
        self.assertEqual(response.status_code,302)
        item.refresh_from_db()
        response=self.post(admin,meeting_url,admin_csrf,action='transition',item=item.pk,operation='assign',evidence=response_evidence.pk,
            reason='Explicit reassignment; no invented authority',action_revision=item.current.number,owner=owner.pk)
        self.assertEqual(response.status_code,302)
        item.refresh_from_db()
        args={'packet_id':packet.pk,'key':'scope_id','action_id':item.pk,'expected_action':item.current.number,'disposition':'exclude_in_successor',
            'evidence_id':response_evidence.pk,'replacement_source_id':replacement.pk,'target_prd_id':p['prd_id'],'target_scope_id':replacement.pk}
        with self.assertRaises(PermissionDenied):sources.resolve(first,f['c'].pk,**args)
        with self.assertRaises(ValidationError):sources.resolve(owner,f['c'].pk,**dict(args,expected_action=1))
        client,url,csrf=self.http(owner);response=self.post(client,url,csrf,action='resolve_source',**args)
        self.assertEqual(response.status_code,302)
        resolution=Audit.objects.get(case=f['c'],action='planning.source_resolved');self.assertFalse(resolution.data['approval_granted'])
        self.assertEqual(self.post(client,url,csrf,action='resolve_source',**args).status_code,302)
        self.assertEqual(Audit.objects.filter(case=f['c'],action='planning.source_resolved').count(),1)
        corrected=copy.deepcopy(p);corrected['scope_id']=replacement.pk
        corrected['source_correlations'][0].update(state='excluded',resolution_id=resolution.pk)
        for row in corrected['source_correlations'][1:]:row.update(target_scope_id=replacement.pk,evidence_id=response_evidence.pk)
        corrected['source_correlations'].append(dict(p['source_correlations'][0],key='corrected-scope',source_id=replacement.pk,
            state='current',document_version='owner-v2',target_scope_id=replacement.pk,evidence_id=response_evidence.pk))
        client,url,csrf=self.http();response=self.post(client,url,csrf,action='capture',predecessor=packet.pk,payload=json.dumps(corrected))
        self.assertEqual(response.status_code,302);successor,_=planning.packet(f['c']);ready=self.ready(successor)
        self.assertEqual(planning.current_readiness(f['c'],ready.pk)['inputs']['source_correlation']['resolution_ids'],[resolution.pk])
        self.assertIn('conflicting',Evidence.objects.get(pk=packet.pk).body)
        before=self.scoped_rows(f['c'])
        self.assertEqual(client.get(url).status_code,200)
        self.assertEqual(self.scoped_rows(f['c']),before)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_planning_correlation_current(%s)',[successor.pk]);self.assertTrue(cursor.fetchone()[0])
        Grant.objects.filter(case=f['c'],user=owner,action='planning.participate').update(active=False)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_planning_correlation_current(%s)',[successor.pk]);self.assertFalse(cursor.fetchone()[0])
        with self.assertRaises(ValidationError):planning.current_readiness(f['c'],ready.pk)
        self.assertTrue(Evidence.objects.filter(pk=ready.pk).exists())
        Grant.objects.filter(case=f['c'],user=owner,action='planning.participate').update(active=True)
        self.assertTrue(planning.current_readiness(f['c'],ready.pk)['inputs']['source_correlation']['complete'])

    def test_legacy_packet_history_retained_without_implicit_target_backfill(self):
        f=self.f;ready=self.ready(f['packet']);prior=Evidence.objects.get(pk=ready.pk).body
        old=planning.packet(f['c'])[1];old.pop('source_pins');old['protocol']='planning-packet/v1';old['payload'].pop('source_correlations')
        legacy=planning.write(f['a'],f['c'],'packet',old)
        value=planning.packet(f['c'])[1];self.assertNotIn('source_correlations',value['payload'])
        report=planning.report(f['a'],f['c'].pk);self.assertEqual(report['status'],'dependent_readiness_held')
        self.assertEqual(len([r for r in report['source_correlation']['findings'] if r['code']=='correlation_unknown']),4)
        with self.assertRaises(ValidationError):planning.current_readiness(f['c'],ready.pk)
        self.assertEqual(Evidence.objects.get(pk=ready.pk).body,prior)
        self.assertEqual(Evidence.objects.get(pk=legacy.pk).body,json.dumps(old,sort_keys=True,separators=(',',':')))
        old['payload']['source_correlations']=copy.deepcopy(f['payload']['source_correlations'])
        unsafe=planning.write(f['a'],f['c'],'packet',old)
        with self.assertRaisesMessage(ValidationError,'Legacy packet'):planning.inputs(f['c'],unsafe,False,f['a'])

    def test_generic_packet_head_cannot_hide_trusted_conflict_or_block_authorized_recovery(self):
        from apps.core.services import add_evidence
        f=self.f;p=copy.deepcopy(f['payload']);p['source_correlations'][0]['state']='conflicting'
        trusted=self.capture(p)
        fake=add_evidence(f['a'],f['c'].pk,'planning_packet','{"approved":true,"scope":"UNTRUSTED-CHOICE"}','untrusted:generic')
        with self.assertRaises(ValidationError):planning.packet(f['c'])
        omission=copy.deepcopy(p);omission['source_correlations']=omission['source_correlations'][1:]
        with self.assertRaisesMessage(ValidationError,'Retain conflicting source'):self.capture(omission)
        successor=self.capture(p);self.assertEqual(planning.packet(f['c'])[0].pk,successor.pk)
        line=Audit.objects.get(case=f['c'],action='planning.packet_source_lineage',data__packet_id=successor.pk)
        self.assertEqual(line.data['trusted_historical_predecessor'],trusted.pk)
        self.assertEqual(line.data['explicit_predecessor'],fake.pk)
        self.assertEqual(line.data['skipped_heads'][0]['reason'],'untrusted_generic_head')
        self.assertFalse(line.data['historical_authority_reused'])
        self.assertNotIn('UNTRUSTED-CHOICE',successor.body)
        self.assertEqual(Evidence.objects.get(pk=fake.pk).body,fake.body)
        self.assertFalse(planning.report(f['a'],f['c'].pk)['source_correlation']['complete'])

    def test_withdrawn_prior_coordinator_does_not_block_fresh_authorized_capture(self):
        f=self.f;old_ready=self.ready(f['packet']);old_body=Evidence.objects.get(pk=old_ready.pk).body
        Grant.objects.filter(case=f['c'],user=f['a'],action='planning.coordinate').update(active=False)
        with self.assertRaises(PermissionDenied):planning.current_readiness(f['c'],old_ready.pk)
        successor=planning.capture(f['owners']['scope'],f['c'].pk,copy.deepcopy(f['payload']),f['packet'].pk)
        self.assertEqual(planning.packet(f['c'])[0].pk,successor.pk)
        self.assertEqual(successor.created_by_id,f['owners']['scope'].pk)
        with self.assertRaises(ValidationError):planning.current_readiness(f['c'],old_ready.pk)
        self.assertEqual(Evidence.objects.get(pk=old_ready.pk).body,old_body)
        line=Audit.objects.get(case=f['c'],action='planning.packet_source_lineage',data__packet_id=successor.pk)
        self.assertEqual(line.data['trusted_historical_predecessor'],f['packet'].pk)
        self.assertFalse(line.data['historical_authority_reused'])
        with self.assertRaises(PermissionDenied):planning.capture(f['a'],f['c'].pk,f['payload'],successor.pk)

    def test_complete_source_proposal_draft_remains_possible_while_correlation_unknown(self):
        f=self.f;p=copy.deepcopy(f['payload']);p['source_correlations'][2]['target_prd_id']=None
        self.capture(p)
        selected={k:f['e'][k].pk for k in commercial.SOURCE_KINDS}
        proposal=commercial.propose(f['a'],f['c'].pk,selected,f['e']['requirements'].pk,'Draft supplied costing while source clarification remains open',rev(f['c']))
        self.assertEqual(proposal.sources,selected);self.assertFalse(proposal.decisions.exists())
        self.assertFalse(planning.report(f['a'],f['c'].pk)['source_correlation']['complete'])
        self.assertIsNone(Baseline.objects.get(case=f['c']).signed_id)

    def test_current_permissions_cross_case_private_and_forged_disposition_denied(self):
        from tests.helpers import setup_case
        from apps.core.services import add_evidence
        f=self.f;other_a,other=setup_case(username='foreign-correlation')
        foreign=add_evidence(other_a,other.pk,'prd','Foreign PRD','synthetic:foreign')
        for field,pk in [('target_prd_id',foreign.pk),('evidence_id',f['packet'].pk),('resolution_id',999999)]:
            p=copy.deepcopy(f['payload']);p['source_correlations'][0][field]=pk
            with self.assertRaises(ValidationError):self.capture(p)
        p=copy.deepcopy(f['payload']);p['source_correlations'][0].update(state='conflicting')
        packet=self.capture(p);Grant.objects.filter(case=f['c'],user=f['a'],action='action.manage').update(active=False)
        with self.assertRaises(PermissionDenied):sources.clarify(f['a'],f['c'].pk,packet.pk,'scope_id')
        self.assertFalse(ActionItem.objects.filter(case=f['c']).exists())
        Grant.objects.filter(case=f['c'],user=f['a'],action='action.manage').update(active=True)
        item=sources.clarify(f['a'],f['c'].pk,packet.pk,'scope_id',f['owners']['scope'].pk)
        Grant.objects.filter(case=f['c'],user=f['owners']['scope'],action='planning.participate').update(active=False)
        self.assertEqual(sources.clarifications(f['c'],packet.pk)[0]['owner_status'],'source_access_held')
        with self.assertRaises(PermissionDenied):sources.resolve(f['owners']['scope'],f['c'].pk,packet.pk,'scope_id',item.pk,item.current.number,'source_correction_required',f['e']['requirements'].pk)
        client,url,csrf=self.http();Grant.objects.filter(case=f['c'],user=f['a'],action='planning.coordinate').update(active=False)
        self.assertEqual(self.post(client,url,csrf,action='capture',predecessor=packet.pk,payload=json.dumps(p)).status_code,200)
        self.assertEqual(planning.latest(f['c'],'packet').pk,packet.pk)


class PlanningCorrelationFactoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from tests.test_factory_planning import setup
        cls.f=setup()
        assert_actual_guards()

    def sql_current(self,packet):
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_planning_correlation_current(%s),psl_engagement_planning_inputs_current(%s)',[packet.pk,packet.pk])
            return cursor.fetchone()

    def test_factory_investigates_exact_conflict_routes_internal_action_and_recovers_successor(self):
        from apps.workflows import factory
        from apps.workflows.models import FactoryAttempt
        f=self.f;p=copy.deepcopy(f['payload']);p['source_correlations'][2]['document_version']='v1';p['source_correlations'][2]['target_prd_id']=None
        packet=planning.capture(f['a'],f['c'].pk,p,f['packet'].pk);factory.run_until_wait(f['work'].pk)
        f['work'].refresh_from_db();self.assertEqual(f['work'].source_head_id,packet.pk)
        self.assertNotEqual(f['work'].status,'verified');self.assertFalse(self.sql_current(packet)[0])
        item=ActionItem.objects.get(case=f['c']);self.assertIsNone(item.current.owner_id)
        result=FactoryAttempt.objects.filter(activity__work=f['work'],activity__kind='ACT04',phase='observed').latest('pk').result
        self.assertEqual(result['investigation']['internal_clarifications'][0]['action_id'],item.pk)
        before=(f['work'].budget_used,ActionItem.objects.count());factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual((f['work'].budget_used,ActionItem.objects.count()),before)
        correction=h.evidence(f,'planning_clarification','Security source explicitly confirms the same target PRD and scope')
        p['source_correlations'][2].update(target_prd_id=p['prd_id'],evidence_id=correction.pk)
        successor=planning.capture(f['a'],f['c'].pk,p,packet.pk)
        for purpose,meeting in f['meetings'].items():planning.align(f['a'],f['c'].pk,successor.pk,purpose,meeting.pk)
        f['pair']=planning.open_requests(f['a'],f['c'].pk,successor.pk);h.observe(f)
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db();self.assertEqual(f['work'].status,'verified',f['work'].finding)
        self.assertEqual(self.sql_current(successor),(True,True));self.assertGreater(f['work'].budget_used,before[0])
        self.assertTrue(ActionItem.objects.filter(pk=item.pk).exists())
        self.assertIsNone(Baseline.objects.get(case=f['c']).signed_id)

    def test_direct_sql_verified_rejects_unknown_successor_and_history_remains_immutable(self):
        from apps.workflows import factory
        from apps.workflows.models import FactoryWork
        f=self.f;h.observe(f);factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'verified');self.assertEqual(self.sql_current(f['packet']),(True,True))
        p=copy.deepcopy(f['payload']);p['source_correlations'][2]['target_prd_id']=None
        packet=planning.capture(f['a'],f['c'].pk,p,f['packet'].pk)
        self.assertEqual(self.sql_current(packet),(False,True));self.assertEqual(self.sql_current(f['packet']),(False,False))
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['work'].pk).update(status='verified')
        with self.assertRaises(DatabaseError),transaction.atomic():Evidence.objects.filter(pk=f['packet'].pk).update(body='forged target')
        marker=Audit.objects.get(case=f['c'],action='planning.recorded',data__evidence_id=f['packet'].pk)
        with self.assertRaises(DatabaseError),transaction.atomic():Audit.objects.filter(pk=marker.pk).update(data={})
        self.assertEqual(planning.latest(f['c'],'packet').pk,packet.pk)


    def test_integrity_rejects_missing_or_changed_immutable_resolution_audit_pin(self):
        f=self.f;value=copy.deepcopy(planning.packet(f['c'])[1]);p=value['payload']
        alternative=h.evidence(f,'scope_baseline','Alternate preserved source')
        row=dict(p['source_correlations'][0],key='retained-alternative',source_id=alternative.pk,state='excluded',resolution_id=99999999)
        p['source_correlations'].append(row)
        pins={k:copy.deepcopy(v) for k,v in value['source_pins']['scope_id'].items()};pins['source']=sources.pin(f['c'],alternative.pk)
        pins['resolution']={'id':99999999,'sha256':'0'*64};value['source_pins'][row['key']]=pins
        forged=planning.write(f['a'],f['c'],'packet',value)
        with self.assertRaises(ValidationError):planning.packet(f['c'])
        self.assertEqual(self.sql_current(forged),(False,False))
        # Test the stronger hash check with an existing immutable audit pointer.
        audit=Audit.objects.create(case=f['c'],actor=f['a'],action='planning.source_resolved',data={'synthetic':'structurally unreviewed response'})
        row['resolution_id']=audit.pk;pins['resolution']['id']=audit.pk
        forged=planning.write(f['a'],f['c'],'packet',value)
        with self.assertRaises(ValidationError):planning.packet(f['c'])
        self.assertEqual(self.sql_current(forged),(False,False))

    def test_unknown_engagement_handoff_stays_independent_and_cannot_claim_planning_complete(self):
        from tests.test_factory_engagement import setup,complete
        from apps.workflows.models import FactoryWork
        from apps.workflows import factory_engagement
        f=setup();result=complete(f);packet=planning.latest(f['c'],'packet')
        self.assertFalse(result['planning_complete']);self.assertEqual(self.sql_current(packet),(False,True))
        self.assertFalse(planning.report(f['a'],f['c'].pk)['source_correlation']['complete'])
        result['planning_complete']=True
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_engagement_factory_current(w,%s::jsonb) FROM workflows_factorywork w WHERE id=%s',[json.dumps(result),f['w'].pk])
            self.assertFalse(cursor.fetchone()[0])
        f['w'].refresh_from_db();self.assertEqual(f['w'].status,'verified')
        self.assertFalse(factory_engagement.verified_output(f['w'])['planning_complete'])


from django.test import TransactionTestCase
class PlanningClarificationConcurrencyTests(TransactionTestCase):
    def test_duplicate_internal_clarification_converges_on_one_native_action(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.contrib.auth import get_user_model
        f=h.fixture(configured=False,username='clarification-race')
        p=copy.deepcopy(f['payload']);p['source_correlations'][0]['state']='conflicting'
        packet=planning.capture(f['a'],f['c'].pk,p,f['packet'].pk);barrier=Barrier(2)
        def writer():
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=f['a'].pk);barrier.wait(timeout=10)
                return sources.clarify(actor,f['c'].pk,packet.pk,'scope_id').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(writer) for _ in range(2)];ids=[future.result(timeout=40) for future in futures]
        self.assertEqual(ids[0],ids[1]);self.assertEqual(ActionItem.objects.filter(case=f['c']).count(),1)
        self.assertEqual(Audit.objects.filter(case=f['c'],action='planning.source_clarification').count(),1)
