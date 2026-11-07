"""P10 canonical fixtures, native SOW connection and optional current assertion."""
from copy import deepcopy
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from apps.identity.models import Grant
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence, public_timeline, public_agent_runs
from apps.documents.models import Template, Version, Publication, PublicationReceipt, PublicationJob, TemplateClaim, TemplateResolution
from apps.documents.controlled import register_template, create_version, preflight, request_review, review_version, reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents import template_current as tc
from apps.policy.services import transition
from apps.pmo.commercial import draft_submission, capture_response, adopt_signed
from apps.pmo.signatures import assert_current_signed_baseline
from apps.pmo.models import Baseline
from .helpers import rev, setup_case
from .document_helpers import artifact, publication_fixture, fields, DEFINITION
from .test_commercial_changes import fixture, proposal, approvals, DEFINITION as SOW
from .signature_helpers import packet_for


def scope(actor, case, evidence, document_type='sow', purpose='Project SOW', context='This engagement', owner='Source owner A', audience='client'):
    return tc.register_scope(actor, case.pk, document_type, audience, purpose, context, owner, evidence.pk, rev(case))


def configure(actor, case, evidence, templates, scopes):
    return artifact(actor, case, tc.COMPONENT, 'schema:psl/document-storage/v3',
        {'template_ids':[t.pk for t in templates], 'repository':'internal-versioned', 'retention_days':30,
         'template_owners':[{'scope_id':s.pk, 'user_id':a.pk} for s,a in scopes]}, evidence)


def claim(actor, case, s, t, evidence, confirmed=True):
    return tc.claim_current(actor, case.pk, s.pk, t.pk, evidence.pk, 'Exact source current claim', rev(case), confirm_owner=confirmed)


class TemplateCurrentTests(TestCase):
    def setUp(self):
        self.actor,self.case,self.e,self.t1 = fixture()
        self.t2 = register_template(self.actor,self.case.pk,self.t1.name,SOW,self.e['policy_decision'].pk,rev(self.case))
        self.scope = scope(self.actor,self.case,self.e['policy_decision'])
        self.policy = configure(self.actor,self.case,self.e['policy_decision'],[self.t1,self.t2],[(self.scope,self.actor)])
        self.claim2 = claim(self.actor,self.case,self.scope,self.t2,self.e['policy_decision'])

    def test_P10_M01_native_sow_exact_template_v2_document_v1_not_latest_registration(self):
        a,c=self.actor,self.case
        newer=register_template(a,c.pk,self.t1.name,SOW,self.e['policy_decision'].pk,rev(c))
        r=proposal(a,c,self.e);approvals(a,c,r)
        version=draft_submission(a,c.pk,r.pk,self.t2.pk,rev(c),template_scope_id=self.scope.pk)
        self.assertEqual((self.t2.version,version.number,version.template_id),(2,1,self.t2.pk))
        self.assertEqual(version.template_current_manifest['owner_claim_id'],self.claim2.pk)
        self.assertNotEqual(version.template_id,newer.pk)
        self.assertEqual(tc.status(self.scope)['status'],'CURRENT')
        self.assertFalse(Baseline.objects.filter(case=c,signed__isnull=False).exists())
        self.assertEqual(preflight(version),[])
        self.client.force_login(a)
        self.assertContains(self.client.get(f'/cases/{c.pk}/documents/'),'Document version 1')
        self.assertContains(self.client.get(f'/cases/{c.pk}/commercial/'),'Current-template assertion')

    def test_P10_M02_conflicting_claims_preserved_owner_resolves_exact_set_not_newest(self):
        a,c=self.actor,self.case
        source=tc.capture_source(a,c.pk,'Second source insists template one is current','private-current-source',rev(c))
        second=claim(a,c,self.scope,self.t1,source)
        self.assertEqual(tc.status(self.scope)['status'],'OWNER_CONFLICT')
        r=proposal(a,c,self.e);approvals(a,c,r)
        with self.assertRaises(ValidationError):draft_submission(a,c.pk,r.pk,self.t2.pk,rev(c),template_scope_id=self.scope.pk)
        historical=draft_submission(a,c.pk,r.pk,self.t2.pk,rev(c))
        self.assertEqual(historical.template_current_manifest,{})
        ids=[self.claim2.pk,second.pk]
        resolution=tc.resolve_claims(a,c.pk,self.scope.pk,self.claim2.pk,ids,source.pk,'Older claim is correct for this context',rev(c))
        version=draft_submission(a,c.pk,r.pk,self.t2.pk,rev(c),template_scope_id=self.scope.pk)
        self.assertEqual(version.template_current_manifest['resolution_id'],resolution.pk)
        self.assertEqual(TemplateClaim.objects.filter(scope=self.scope).count(),2)
        self.assertEqual(set(TemplateClaim.objects.filter(scope=self.scope).values_list('evidence_id',flat=True)),{source.pk,self.e['policy_decision'].pk})
        third=claim(a,c,self.scope,self.t1,source,False)
        self.assertEqual(tc.status(self.scope)['status'],'OWNER_CONFLICT')
        self.assertTrue(preflight(version))
        with self.assertRaises(ValidationError):tc.resolve_claims(a,c.pk,self.scope.pk,second.pk,ids,source.pk,'Stale set',rev(c))
        self.assertEqual(TemplateResolution.objects.count(),1)
        self.assertEqual(third.template_id,self.t1.pk)

    def test_unrelated_purpose_context_owner_audience_and_case_do_not_conflict(self):
        a,c=self.actor,self.case
        for kw in [{'purpose':'Renewal SOW'},{'context':'Another contract'},{'owner':'Source owner B'}]:
            other=scope(a,c,self.e['policy_decision'],**kw)
            claim(a,c,other,self.t1,self.e['policy_decision'],False)
            self.assertEqual(tc.status(other)['status'],'OWNER_CONFIRMATION_REQUIRED')
        internal=dict(SOW,audience_fields={'internal':SOW['required_fields']})
        t=register_template(a,c.pk,'Internal SOW',internal,self.e['policy_decision'].pk,rev(c))
        other=scope(a,c,self.e['policy_decision'],audience='internal')
        claim(a,c,other,t,self.e['policy_decision'],False)
        b,d,e,u=fixture(username='other-case')
        other=scope(b,d,e['policy_decision']);claim(b,d,other,u,e['policy_decision'],False)
        self.assertEqual(tc.status(self.scope)['status'],'CURRENT')
        self.assertEqual(tc.status(self.scope)['manifest']['template_id'],self.t2.pk)
        with self.assertRaises(PermissionDenied):claim(a,c,self.scope,u,self.e['policy_decision'],False)

    def test_unconfigured_authority_and_retraction_hold_only_current_claim(self):
        a,c=self.actor,self.case
        transition(a,self.policy.pk,'revoked')
        self.assertEqual(tc.status(self.scope)['status'],'OWNER_CONFIRMATION_REQUIRED')
        with self.assertRaises(ValidationError):claim(a,c,self.scope,self.t1,self.e['policy_decision'])
        reported=claim(a,c,self.scope,self.t1,self.e['policy_decision'],False)
        self.assertEqual(tc.status(self.scope)['status'],'OWNER_CONFLICT')
        tc.retract_claim(a,c.pk,reported.pk,self.e['policy_decision'].pk,'Incorrect source reference',rev(c))
        self.assertEqual(tc.status(self.scope)['status'],'OWNER_CONFIRMATION_REQUIRED')
        r=proposal(a,c,self.e);approvals(a,c,r)
        self.assertEqual(draft_submission(a,c.pk,r.pk,self.t1.pk,rev(c)).template_current_manifest,{})
        with self.assertRaises(ValidationError):draft_submission(a,c.pk,r.pk,self.t2.pk,rev(c),template_scope_id=self.scope.pk)
        self.assertEqual(TemplateClaim.objects.count(),2)

    def test_wrong_owner_and_revoked_grants_cannot_confirm_or_resolve(self):
        a,c=self.actor,self.case
        other=get_user_model().objects.create_user(username='registrar',is_staff=True,is_superuser=True)
        for action in ['case.read','document.read','document.template']:
            Grant.objects.create(case=c,user=other,action=action)
        with self.assertRaises(PermissionDenied):claim(other,c,self.scope,self.t1,self.e['policy_decision'])
        reported=claim(other,c,self.scope,self.t1,self.e['policy_decision'],False)
        with self.assertRaises(PermissionDenied):tc.resolve_claims(other,c.pk,self.scope.pk,reported.pk,[self.claim2.pk,reported.pk],self.e['policy_decision'].pk,'Not the owner',rev(c))
        tc.retract_claim(other,c.pk,reported.pk,self.e['policy_decision'].pk,'Withdraw my claim',rev(c))
        Grant.objects.filter(case=c,user=a,action='document.template').update(active=False)
        self.assertEqual(tc.status(self.scope)['status'],'OWNER_CONFIRMATION_REQUIRED')

    def test_native_sow_http_current_assertion_and_private_source_no_generic_leak(self):
        a,c=self.actor,self.case
        secret=tc.capture_source(a,c.pk,'P10 PRIVATE OWNER CONTENT','P10-PRIVATE-LOCATOR',rev(c))
        self.assertFalse(public_evidence(Evidence.objects.all()).filter(pk=secret.pk).exists())
        self.assertFalse(public_timeline(c).filter(action__startswith='document.template_current.').exists())
        self.client.force_login(a)
        r=proposal(a,c,self.e);approvals(a,c,r)
        response=self.client.post(f'/cases/{c.pk}/commercial/',{'action':'draft','revision':rev(c),'proposal':r.pk,'template':self.t2.pk,'template_scope':self.scope.pk})
        self.assertEqual(response.status_code,302)
        self.assertEqual(Version.objects.get().template_current_manifest['scope_id'],self.scope.pk)
        url=f'/cases/{c.pk}/documents/templates/current/'
        before=rev(c)
        self.assertContains(self.client.get(url),'P10 PRIVATE OWNER CONTENT')
        self.assertEqual(rev(c),before)
        reader=get_user_model().objects.create_user(username='case-only')
        for action in ['case.read','agent.extract']:
            Grant.objects.create(case=c,user=reader,action=action)
        self.client.force_login(reader)
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertNotContains(self.client.get(f'/cases/{c.pk}/'),'P10-PRIVATE-LOCATOR')
        self.assertNotContains(self.client.get(f'/cases/{c.pk}/'),'P10 PRIVATE OWNER CONTENT')

    def test_signed_adopted_baseline_and_historical_receipt_survive_new_current_claim(self):
        a,c=self.actor,self.case
        r=proposal(a,c,self.e);approvals(a,c,r)
        v=draft_submission(a,c.pk,r.pk,self.t2.pk,rev(c),template_scope_id=self.scope.pk)
        request_review(a,c.pk,v.pk,rev(c));review_version(a,c.pk,v.pk,'approve','Exact client review',rev(c))
        reserve_publication(a,c.pk,v.pk,rev(c));run_publication_once()
        receipt=PublicationReceipt.objects.get(publication__version=v)
        response=capture_response(a,c.pk,r.pk,receipt.pk,'signed',self.e['signature'].pk,'Exact signature received',rev(c))
        packet_for(a,c,self.e,r)
        adoption=adopt_signed(a,c.pk,r.pk,response.pk,rev(c))
        before=deepcopy(adoption.after);payload=deepcopy(receipt.payload);manifest=deepcopy(v.template_current_manifest)
        assert_current_signed_baseline(c)
        second=claim(a,c,self.scope,self.t1,self.e['policy_decision'])
        tc.resolve_claims(a,c.pk,self.scope.pk,second.pk,[self.claim2.pk,second.pk],self.e['policy_decision'].pk,'Owner prefers older template going forward',rev(c))
        assert_current_signed_baseline(c)
        baseline=Baseline.objects.get(case=c)
        self.assertEqual({key:getattr(baseline,key) for key in before},before)
        v.refresh_from_db();receipt.refresh_from_db()
        self.assertEqual((v.template_id,v.number,v.template_current_manifest),(self.t2.pk,1,manifest))
        self.assertEqual(receipt.payload,payload)
        self.client.force_login(a)
        self.assertContains(self.client.get('/documents/inbox/'),v.document.title)
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_sql_guards_reject_cross_scope_stale_owner_and_forged_manifest(self):
        a,c=self.actor,self.case
        with self.assertRaises(DatabaseError),transaction.atomic():
            TemplateClaim.objects.filter(pk=self.claim2.pk).update(note='rewrite')
        with self.assertRaises(DatabaseError),transaction.atomic():
            TemplateResolution.objects.create(scope=self.scope,selected_claim=self.claim2,claim_ids=[],evidence=self.e['policy_decision'],note='Omitted source',actor=a,owner_policy=self.policy)
        r=proposal(a,c,self.e);approvals(a,c,r)
        v=draft_submission(a,c.pk,r.pk,self.t2.pk,rev(c),template_scope_id=self.scope.pk)
        kwargs={f.name:getattr(v,f.name) for f in Version._meta.fields if f.name not in ['id','created_at','number']}
        kwargs['template_current_manifest']=dict(v.template_current_manifest,template_id=self.t1.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():Version.objects.create(number=2,**kwargs)
        Grant.objects.filter(case=c,user=a,action='document.template').update(active=False)
        with self.assertRaises(DatabaseError),transaction.atomic():
            TemplateClaim.objects.create(scope=self.scope,template=self.t2,evidence=self.e['policy_decision'],note='Revoked owner',actor=a,owner_policy=self.policy)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_template_current(%s)',[self.scope.pk]);self.assertIsNone(cursor.fetchone()[0])


class TemplateCurrentPublicationTests(TestCase):
    def setUp(self):
        self.a,self.c,self.owner,self.source,self.t,self.recipient,_,_=publication_fixture()
        self.s=scope(self.a,self.c,self.owner,document_type='status_report',purpose='Weekly status')
        self.t2=register_template(self.a,self.c.pk,self.t.name,DEFINITION,self.owner.pk,rev(self.c))
        self.policy=configure(self.a,self.c,self.owner,[self.t,self.t2],[(self.s,self.a)])
        self.claim=claim(self.a,self.c,self.s,self.t,self.owner)

    def prepare(self):
        v=create_version(self.a,self.c.pk,self.t.pk,'Current report','client',fields(self.source),rev(self.c),template_scope_id=self.s.pk)
        request_review(self.a,self.c.pk,v.pk,rev(self.c));review_version(self.a,self.c.pk,v.pk,'approve','Exact report',rev(self.c))
        return v

    def test_conflict_before_delivery_holds_new_effect_and_sql_receipt(self):
        v=self.prepare();p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c))
        claim(self.a,self.c,self.s,self.t2,self.owner)
        run_publication_once();self.assertEqual(PublicationJob.objects.get().status,'held')
        self.assertFalse(PublicationReceipt.objects.exists())
        with self.assertRaises(DatabaseError),transaction.atomic():
            PublicationReceipt.objects.create(publication=p,recipient=self.recipient,operation_key='forged-effect',payload=v.payload,payload_sha256=v.payload_sha256)
        with self.assertRaises(DatabaseError),transaction.atomic():
            Publication.objects.create(version=v,actor=self.a,review=v.reviews.get(),policies=p.policies,recipient_ids=p.recipient_ids,retention_days=30,operation_key='forged-publication')

    def test_timeout_receipt_recovery_after_owner_revocation_and_old_inbox(self):
        from adapters.publications import PublicationTimeoutAfterAccept
        v=self.prepare();reserve_publication(self.a,self.c.pk,v.pk,rev(self.c))
        run_publication_once(PublicationTimeoutAfterAccept())
        self.assertEqual(PublicationJob.objects.get().status,'unknown')
        self.assertEqual(PublicationReceipt.objects.count(),1)
        transition(self.a,self.policy.pk,'revoked')
        run_publication_once(PublicationTimeoutAfterAccept())
        self.assertEqual(PublicationJob.objects.get().status,'confirmed')
        self.client.force_login(self.recipient);self.assertContains(self.client.get('/documents/inbox/'),'Delivery is progressing.')
        Grant.objects.filter(case=self.c,user=self.recipient,action='document.receive:client').update(active=False)
        self.assertNotContains(self.client.get('/documents/inbox/'),'Delivery is progressing.')

    def test_http_capture_conflict_resolution_and_draft_only_owner_policy(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/documents/templates/current/'
        self.assertEqual(self.client.post(url,{'action':'source','revision':rev(self.c),'body':'Owner source literal','locator':'synthetic:owner-source'}).status_code,302)
        e=Evidence.objects.filter(kind=tc.SOURCE_KIND).latest('pk')
        self.assertEqual(self.client.post(url,{'action':'claim','revision':rev(self.c),'scope':self.s.pk,'template':self.t2.pk,'evidence':e.pk,'note':'Competing source','confirm_owner':'on'}).status_code,302)
        self.assertContains(self.client.get(url),'OWNER_CONFLICT')
        ids=tc.status(self.s)['claim_ids']
        self.assertEqual(self.client.post(url,{'action':'resolve','revision':rev(self.c),'scope':self.s.pk,'selected_claim':self.claim.pk,'claim_ids':json.dumps(ids),'evidence':e.pk,'note':'Keep original template'}).status_code,302)
        self.assertEqual(tc.status(self.s)['status'],'CURRENT')
        from django.utils import timezone
        content={'template_ids':[self.t.pk,self.t2.pk],'repository':'internal-versioned','retention_days':30,'template_owners':[{'scope_id':self.s.pk,'user_id':self.a.pk}]}
        self.assertEqual(self.client.post(url,{'action':'owner_policy','revision':rev(self.c),'content':json.dumps(content),'evidence':self.owner.pk,'effective_from':timezone.now().isoformat()}).status_code,302)
        from apps.policy.models import Configuration
        self.assertEqual(Configuration.objects.filter(case=self.c,component=tc.COMPONENT).latest('revision').states.latest('pk').state,'draft')
        self.assertEqual(tc.status(self.s)['status'],'CURRENT')

    def test_generic_agent_current_pin_preserves_private_claim_metadata_boundary(self):
        from apps.agents.documents import draft_document, check_document
        secret=tc.capture_source(self.a,self.c.pk,'PRIVATE CLAIM BODY','PRIVATE CLAIM LOCATOR',rev(self.c))
        second=claim(self.a,self.c,self.s,self.t,secret,False)
        self.assertEqual(tc.status(self.s)['status'],'CURRENT')
        v=draft_document(self.a,self.c.pk,self.t.pk,'Agent report','client',[self.source.pk],rev(self.c),template_scope_id=self.s.pk)
        self.assertEqual(v.template_current_manifest['claim_ids'],[self.claim.pk,second.pk])
        checked=check_document(self.a,self.c.pk,v.pk)
        self.assertNotIn('template_current_manifest',checked.result)
        self.assertNotIn('PRIVATE CLAIM',json.dumps(checked.result))
        with self.assertRaises(ValidationError):draft_document(self.a,self.c.pk,self.t.pk,'Unsafe','client',[secret.pk],rev(self.c))
        reader=get_user_model().objects.create_user(username='case-agent-reader')
        for action in ['case.read','agent.extract']:
            Grant.objects.create(case=self.c,user=reader,action=action)
        self.client.force_login(reader)
        response=self.client.get(f'/cases/{self.c.pk}/')
        self.assertNotContains(response,'PRIVATE CLAIM')
        self.assertNotContains(response,'template_current_manifest')

    def test_new_private_domain_claim_sources_are_not_exposed_to_generic_document_readers(self):
        a,c=self.a,self.c
        definition={'document_type':'finance_report','required_fields':['executive_summary','financial_metrics','bu_totals'],
                    'audience_fields':{'internal':['executive_summary','financial_metrics','bu_totals']},'internal_review_required':False}
        t=register_template(a,c.pk,'PRIVATE DOMAIN TEMPLATE',definition,self.owner.pk,rev(c))
        secret=tc.capture_source(a,c.pk,'PRIVATE DOMAIN SOURCE BODY','PRIVATE DOMAIN LOCATOR',rev(c))
        s=scope(a,c,secret,document_type='finance_report',purpose='PRIVATE DOMAIN PURPOSE',audience='internal')
        claim(a,c,s,t,secret,False)
        reader=get_user_model().objects.create_user(username='ordinary-document-reader')
        for action in ['case.read','document.read','document.template','agent.extract']:
            Grant.objects.create(case=c,user=reader,action=action)
        self.client.force_login(reader)
        response=self.client.get(f'/cases/{c.pk}/documents/templates/current/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'PRIVATE DOMAIN')
        with self.assertRaises(PermissionDenied):claim(reader,c,s,t,secret,False)
        with self.assertRaises(PermissionDenied):scope(reader,c,secret,purpose='Borrow private source')
        with self.assertRaises(DatabaseError),transaction.atomic():
            TemplateClaim.objects.create(scope=s,template=t,evidence=secret,note='Unauthorized domain insert',actor=reader)


from django.test import TransactionTestCase


class TemplateClaimConcurrencyTests(TransactionTestCase):
    def test_direct_sql_new_receipt_waits_for_conflicting_claim_then_denies_effect(self):
        import threading,time
        from django.db import close_old_connections
        a,c,owner,src,t,recipient,_,_=publication_fixture()
        s=scope(a,c,owner,document_type='status_report',purpose='Concurrent report')
        t2=register_template(a,c.pk,t.name,DEFINITION,owner.pk,rev(c))
        configure(a,c,owner,[t,t2],[(s,a)]);claim(a,c,s,t,owner)
        v=create_version(a,c.pk,t.pk,'Race report','client',fields(src),rev(c),template_scope_id=s.pk)
        request_review(a,c.pk,v.pk,rev(c));review_version(a,c.pk,v.pk,'approve','Exact race review',rev(c))
        p=reserve_publication(a,c.pk,v.pk,rev(c))
        inserted=threading.Event();release=threading.Event();attempting=threading.Event();result={}
        def capture():
            close_old_connections()
            try:
                with transaction.atomic():
                    claim(a,c,s,t2,owner)
                    inserted.set()
                    if not release.wait(15):raise AssertionError('Release timed out')
            except BaseException as exc:result['capture_error']=repr(exc);inserted.set()
            finally:close_old_connections()
        def effect():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()');result['effect_pid']=cursor.fetchone()[0]
                attempting.set()
                PublicationReceipt.objects.create(publication=p,recipient=recipient,operation_key='concurrent-direct-receipt',payload=v.payload,payload_sha256=v.payload_sha256)
                result['effect']='incorrectly accepted'
            except DatabaseError as exc:result['effect']='denied';result['reason']=str(exc)
            except BaseException as exc:result['effect_error']=repr(exc)
            finally:close_old_connections()
        first=threading.Thread(target=capture);second=threading.Thread(target=effect)
        first.start()
        try:
            self.assertTrue(inserted.wait(15));self.assertNotIn('capture_error',result)
            second.start();self.assertTrue(attempting.wait(15))
            waiting=False
            for _ in range(100):
                with connection.cursor() as cursor:
                    cursor.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',[result['effect_pid']]);row=cursor.fetchone()
                if row and row[0]=='Lock':waiting=True;break
                time.sleep(.02)
            self.assertTrue(waiting,'Actual concurrent backend must wait on the case lock')
        finally:
            release.set();first.join(20)
            if second.ident is not None:second.join(20)
        self.assertFalse(first.is_alive());self.assertFalse(second.is_alive())
        self.assertNotIn('capture_error',result);self.assertNotIn('effect_error',result)
        self.assertEqual(result['effect'],'denied',result)
        self.assertIn('Current template claim changed',result['reason'])
        self.assertFalse(PublicationReceipt.objects.filter(publication=p).exists())
