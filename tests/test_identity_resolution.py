import json
from pathlib import Path
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from django.test import TransactionTestCase,Client
from django.db import transaction,DatabaseError,close_old_connections
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.identity.actions import ACTIONS
from apps.policy.identity_resolution_validators import COMPONENT,SCHEMA,validate_reference
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo import engagement as engagement,identity_resolution as d
from tests.helpers import setup_case,roles

class ProjectIdentityResolutionTests(TransactionTestCase):
    def fixture(self):
        a,c=setup_case(username='identity-owner');cases=[c];proofs=[];policies=[]
        for index in range(3):
            if index:
                c=Case.objects.create(tenant=cases[0].tenant,title='Possible duplicate '+str(index),kind='project',synthetic=True)
                Grant.objects.bulk_create([Grant(case=c,user=a,action=x) for x in ACTIONS]);cases.append(c)
            e=add_evidence(a,c.pk,'engagement_source','Synthetic identity source '+str(index),'synthetic:identity')
            p=add_evidence(a,c.pk,'policy_decision','Synthetic source ownership; no real PMO appointment','synthetic:identity')
            roles(a,c,p);engagement.capture(a,c.pk,'B',e.pk,'source-'+str(index),'capture')
            proofs.append(e);policies.append(p)
        return a,cases,proofs,policies

    def configure(self,a,c,p,**changes):
        value=json.loads(Path('fixtures/engagement-identity-resolution.json').read_text());value.pop('classification');value.update(changes)
        cfg=draft_operator_policy(a,c.pk,COMPONENT,value,p.pk,timezone.now());transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active');return cfg

    def resolve(self,a,c,other,e,oe,key='identity-alias',relation='alias'):
        return d.resolve(a,c.pk,other.pk,relation,'PMO Lead',e.pk,oe.pk,'Synthetic human identity finding; no business merge',key)

    def test_missing_policy_holds_only_resolution_current_findings_ui_and_revocation(self):
        a,cases,e,p=self.fixture();c,other,_=cases
        with self.assertRaises(ValidationError):self.resolve(a,c,other,e[0],e[1])
        self.assertEqual(engagement.Record.objects.filter(kind='capture').count(),3);self.assertFalse(d.Decision.objects.exists())
        self.configure(a,c,p[0])
        with self.assertRaises(ValidationError):self.resolve(a,c,other,e[0],e[1])
        self.configure(a,other,p[1]);r=self.resolve(a,c,other,e[0],e[1]);self.assertEqual(self.resolve(a,c,other,e[0],e[1]).pk,r.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():
            d.Decision.objects.create(case=c,other_case=other,relation='unresolved',operation_key='forged-cross-proof',data=r.data,evidence=e[1],other_evidence=e[0],actor=a)
        value=d.report(a,c.pk);self.assertTrue(value['decisions'][0]['currently_accepted']);self.assertFalse(value['access_transferred']);self.assertFalse(value['financial_authority'])
        client=Client();client.force_login(a);url=reverse('identity_resolution',args=[c.pk])
        self.assertContains(client.get(url,{'other_case':str(other.pk)}),'Finding against')
        response=client.post(url,{'action':'resolve','other_case_id':str(other.pk),'relation':'distinct','role':'PMO Lead','evidence_id':e[0].pk,'other_evidence_id':e[1].pk,'reason':'Synthetic owner concluded separate engagements','key':'distinct-findings'})
        self.assertEqual(response.status_code,302);self.assertEqual(d.report(a,c.pk)['decisions'][0]['relation'],'distinct')
        self.assertEqual(engagement.report(a,c.pk)['identity_resolution']['decisions'][0]['relation'],'distinct')
        Grant.objects.filter(case=other,user=a,action='engagement.resolve_identity').update(active=False)
        self.assertFalse(d.report(a,c.pk)['decisions'][0]['currently_accepted'])
        with self.assertRaises(PermissionDenied):self.resolve(a,c,other,e[0],e[1],'revoked-write')
        Grant.objects.filter(case=other,user=a,action='case.read').update(active=False)
        row=d.report(a,c.pk)['decisions'][0];self.assertEqual(row,{'id':row['id'],'status':'other_case_access_held'})
        self.assertNotContains(client.get(url),str(other.pk))
        for action in ['update','delete']:
            with self.assertRaises(DatabaseError),transaction.atomic():
                q=d.Decision.objects.all();q.update(relation='unresolved') if action=='update' else q.delete()
        self.assertFalse(engagement.Identifier.objects.exists())

    def test_cycles_conflicting_targets_scope_proofs_and_policy_changes(self):
        a,cases,e,p=self.fixture();c,other,third=cases
        for case,policy in zip(cases,p):self.configure(a,case,policy)
        self.resolve(a,c,other,e[0],e[1])
        with self.assertRaises(ValidationError):self.resolve(a,other,c,e[1],e[0],'cycle')
        with self.assertRaises(ValidationError):self.resolve(a,c,third,e[0],e[2],'ambiguous-target')
        with self.assertRaises(ValidationError):self.resolve(a,c,c,e[0],e[0],'self-alias')
        with self.assertRaises(ValidationError):self.resolve(a,c,other,e[1],e[0],'foreign-proof')
        self.resolve(a,c,other,e[0],e[1],'explicitly-distinct','distinct')
        self.resolve(a,c,third,e[0],e[2],'new-canonical-target')
        self.configure(a,c,p[0],max_decisions=100)
        self.assertFalse(d.report(a,c.pk)['decisions'][0]['currently_accepted'])
        self.configure(a,c,p[0],max_decisions=1)
        with self.assertRaises(ValidationError):self.resolve(a,c,third,e[0],e[2],'budget-held')
        foreign=Case.objects.create(tenant='other-tenant',title='Foreign project',kind='project',synthetic=True)
        Grant.objects.bulk_create([Grant(case=foreign,user=a,action=x) for x in ACTIONS])
        foreign_proof=add_evidence(a,foreign.pk,'engagement_source','Synthetic foreign identity evidence','synthetic:foreign')
        with self.assertRaises(ValidationError):self.resolve(a,c,foreign,e[0],foreign_proof,'foreign-tenant')
        with self.assertRaises(ValidationError):validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content={'resolution_roles':[],'max_decisions':0,'allow_synthetic':True}),c)
        # No grant, identifier or business record is implicitly copied by aliasing.
        self.assertEqual(d.Decision.objects.count(),3);self.assertFalse(engagement.Identifier.objects.exists())

    def test_opposite_aliases_on_two_connections_cannot_form_a_cycle(self):
        a,cases,e,p=self.fixture();c,other,_=cases
        self.configure(a,c,p[0]);self.configure(a,other,p[1]);barrier=Barrier(2)
        def resolve(index):
            close_old_connections()
            try:
                barrier.wait(timeout=30)
                try:self.resolve(a,c if index==0 else other,other if index==0 else c,e[index],e[1-index],'opposite-'+str(index));return 'recorded'
                except ValidationError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(resolve,range(2)))
        self.assertEqual(sorted(results),['held','recorded']);self.assertEqual(d.Decision.objects.count(),1)
