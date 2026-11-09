import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase,Client
from django.db import transaction,DatabaseError,close_old_connections
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from django.urls import reverse
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,resolve
from apps.policy.engagement_validators import ASSIGN,REGISTER,SCHEMAS,validate_reference
from apps.pmo import engagement as d
from apps.agents.engagement import investigate
from tests.helpers import setup_case,roles

def activate(a,c,component,value,e):
    p=draft_operator_policy(a,c.pk,component,value,e.pk,timezone.now());transition(a,p.pk,'validated');transition(a,p.pk,'active');return p

class EngagementIntakeTests(TransactionTestCase):
    def fixture(self,name='engagement-human'):
        a,c=setup_case(username=name)
        e=add_evidence(a,c.pk,'engagement_source','Synthetic direct client engagement source','synthetic:engagement')
        p=add_evidence(a,c.pk,'plan','Synthetic pre-signature planning evidence','synthetic:engagement')
        policy=add_evidence(a,c.pk,'policy_decision','Synthetic PMO authority and namespace; no operational appointment','synthetic:engagement')
        values=json.loads(Path('fixtures/engagement-intake.json').read_text());return a,c,e,p,policy,values

    def ready(self,name='engagement-human'):
        a,c,e,p,policy,v=self.fixture(name);roles(a,c,policy)
        d.capture(a,c.pk,'B',e.pk,'direct-client','capture')
        activate(a,c,ASSIGN,v['assignment'],policy);d.assign(a,c.pk,a.pk,'PMO Lead',e.pk,'assign')
        activate(a,c,REGISTER,v['registration'],policy)
        return a,c,e,p,policy,v

    def test_capture_before_policy_assignment_registration_alias_export_and_current_holds(self):
        a,c,e,p,policy,v=self.fixture();r=d.capture(a,c.pk,'B',e.pk,'direct-client','capture')
        self.assertEqual(d.capture(a,c.pk,'B',e.pk,'direct-client','capture').pk,r.pk)
        self.assertEqual(resolve(ASSIGN,c).status,'MISSING')
        with self.assertRaises(ValidationError):d.assign(a,c.pk,a.pk,'PMO Lead',e.pk,'missing-assignment-policy')
        self.assertEqual(d.Record.objects.count(),1)
        roles(a,c,policy);activate(a,c,ASSIGN,v['assignment'],policy);d.assign(a,c.pk,a.pk,'PMO Lead',e.pk,'assignment')
        self.assertEqual(d.report(a,c.pk)['assignment_status'],'current')
        with self.assertRaises(ValidationError):d.register(a,c.pk,'SYN-1','PMO Lead',e.pk,p.pk,'missing-id-policy')
        activate(a,c,REGISTER,v['registration'],policy)
        r=d.register(a,c.pk,'SYN-1','PMO Lead',e.pk,p.pk,'registration');self.assertEqual(d.register(a,c.pk,'SYN-1','PMO Lead',e.pk,p.pk,'registration').pk,r.pk)
        d.register(a,c.pk,'SYN-2','PMO Lead',e.pk,p.pk,'corrected-registration')
        self.assertEqual(d.Identifier.objects.count(),2);self.assertEqual(d.report(a,c.pk)['registration_status'],'current')
        export=d.export_registration(a,c.pk,'downstream');self.assertEqual(d.export_registration(a,c.pk,'downstream').pk,export.pk);self.assertEqual(json.loads(export.body)['value'],'SYN-2')
        client=Client();client.force_login(a);self.assertContains(client.get(reverse('engagement',args=[c.pk])),'Engagement and project identity')
        self.assertContains(client.get(reverse('case',args=[c.pk])), 'href="'+reverse('engagement',args=[c.pk])+'"')
        response=client.post(reverse('engagement',args=[c.pk]),{'action':'investigate','revision':c.revision});self.assertEqual(response.status_code,200);self.assertEqual(response.json()['effect_tools'],[])
        for model in [d.Record,d.Identifier]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.all().update(case=c)
        Grant.objects.filter(case=c,user=a,action='engagement.assign').update(active=False)
        self.assertEqual(d.report(a,c.pk)['assignment_status'],'held_or_stale')
        with self.assertRaises(PermissionDenied):d.export_registration(a,c.pk,'after-revocation')
        self.assertEqual(d.Identifier.objects.count(),2)

    def test_route_source_config_scope_normalization_and_identity_conflicts(self):
        from types import SimpleNamespace
        a,c,e,p,policy,v=self.ready()
        for component,key in [(ASSIGN,'assignment'),(REGISTER,'registration')]:
            bad={**v[key],'allow_synthetic':False}
            with self.assertRaises(ValidationError):validate_reference(component,SimpleNamespace(schema_ref=SCHEMAS[component][0],content=bad),c)
        with self.assertRaises(ValidationError):d.capture(a,c.pk,'A',e.pk,'rfp-won','forged-rfp',999999)
        with self.assertRaises(ValidationError):d.capture(a,c.pk,'C',e.pk,'product-paper','wrong-product-source')
        d.register(a,c.pk,'SYN-1','PMO Lead',e.pk,p.pk,'first-id')
        b,other,oe,op,_,_=self.ready('other-engagement')
        with self.assertRaises(ValidationError):d.register(b,other.pk,'syn-1','PMO Lead',oe.pk,op.pk,'conflicting-id')
        with self.assertRaises(ValidationError):d.capture(a,c.pk,'B',oe.pk,'foreign','foreign-evidence')
        with self.assertRaises(PermissionDenied):investigate(b,c.pk)
        product=add_evidence(a,c.pk,'product_input','Synthetic Product paper source','synthetic:product')
        d.capture(a,c.pk,'C',product.pk,'product-paper','successor-capture')
        self.assertEqual(d.report(a,c.pk)['registration_status'],'held_or_stale');self.assertEqual(d.Identifier.objects.count(),1)

    def test_two_connections_converge_on_registration(self):
        a,c,e,p,policy,v=self.ready();barrier=Barrier(2)
        def register(_):
            close_old_connections()
            try:barrier.wait(timeout=30);return d.register(a,c.pk,'SYN-CONCURRENT','PMO Lead',e.pk,p.pk,'same-registration').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(register,range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(d.Identifier.objects.count(),1)

    def test_pre_signature_delivery_registration_bridge_preserves_owned_source_verification(self):
        from tests.helpers import project_evidence,rev
        from apps.pmo.services import prepare_baseline
        from apps.pmo.gates import register_candidate
        from apps.pmo.delivery import open_dossier,verify_source
        from apps.pmo.models import Baseline,DeliverySource
        a,c,e,p,policy,v=self.ready();sources=project_evidence(a,c)
        prepare_baseline(a,c.pk,sources['plan'].pk,sources['costing'].pk,sources['sow'].pk,rev(c))
        d.assign(a,c.pk,a.pk,'PMO Lead',e.pk,'current-pm')
        d.register(a,c.pk,'SYN-DELIVERY','PMO Lead',e.pk,sources['plan'].pk,'formal-id')
        candidate=register_candidate(a,c.pk,'delivery-engagement',sources['requirements'].pk,rev(c))
        dossier=open_dossier(a,c.pk,candidate.pk,sources['plan'].pk,'Synthetic PM scope before signature',rev(c))
        r=d.link_delivery(a,c.pk,dossier.pk,'delivery-link');self.assertEqual(d.link_delivery(a,c.pk,dossier.pk,'delivery-link').pk,r.pk)
        source=DeliverySource.objects.get(pk=r.data['source']);self.assertEqual(source.kind,'registration');self.assertEqual(source.evidence.kind,'engagement_registration')
        self.assertFalse(source.verifications.exists());verify_source(a,c.pk,source.pk,rev(c));self.assertTrue(source.verifications.exists())
        self.assertIsNone(Baseline.objects.get(case=c).signed_id)

    def test_route_a_requires_and_links_actual_reviewed_won_rfp_conversion(self):
        from tests import test_rfp as upstream
        from tests.helpers import rev
        a,c,e,t,route=upstream.fixture();response=upstream.response(a,c,e);upstream.approve(a,c,e,response);submission=upstream.submit(a,c,e,t,response)
        outcome=upstream.rfp.outcome(a,c.pk,submission.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Synthetic evidenced won bid',rev(c))
        disposition=upstream.rfp.dispose(a,c.pk,outcome.pk,None,rev(c))
        r=d.capture(a,c.pk,'A',e['rfp_outcome'].pk,'won-rfp','route-a',disposition.pk)
        self.assertEqual(r.data['rfp_disposition'],disposition.pk);self.assertEqual(r.data['route'],'A')

    def test_unicode_normalization_expansion_is_validated_before_database_write(self):
        a,c,e,p,policy,v=self.ready()
        activate(a,c,REGISTER,{**v['registration'],'format':'bounded_text','max_length':120},policy)
        with self.assertRaises(ValidationError):d.register(a,c.pk,'\u00df'*120,'PMO Lead',e.pk,p.pk,'unicode-expansion')
        self.assertFalse(d.Identifier.objects.exists());self.assertFalse(d.Record.objects.filter(kind='registration').exists())
