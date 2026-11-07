"""Exact new assurance claim truth, without model/native workflow mocks."""
import hashlib,json
from django.test import TestCase
from django.db import DatabaseError,transaction
from django.utils import timezone
from apps.core.services import add_evidence
from apps.documents.models import PublicationReceipt
from apps.pmo.change_applicability import declaration_draft
from apps.pmo.change_signatures import current_closure
from apps.pmo.go_live_attestations import pin
from apps.workflows import factory_change as change
from apps.workflows.models import FactoryWork,FactoryActivity,FactoryAttempt
from .helpers import rev
from . import test_change_applicability as fixtures


class FactoryClaimIntegrityTests(TestCase):
    setUp=fixtures.FactoryApplicabilityTests.setUp
    assessments=fixtures.FactoryApplicabilityTests.assessments
    authorized=fixtures.FactoryApplicabilityTests.authorized
    ready=fixtures.FactoryApplicabilityTests.ready
    change_template=fixtures.FactoryApplicabilityTests.change_template
    start=fixtures.FactoryApplicabilityTests.start
    advance=fixtures.FactoryApplicabilityTests.advance
    review=fixtures.FactoryApplicabilityTests.review
    configure=fixtures.FactoryApplicabilityTests.configure

    def prepared_assurance(self, legacy=False):
        auth=self.authorized();self.start(auth);self.advance();self.review('notice');self.advance()
        self.ready(auth);self.advance();self.review('go_live');self.advance()
        receipt=PublicationReceipt.objects.get(publication__version=change.document(self.work,'go_live'))
        if not legacy:self.configure(auth)
        pm=add_evidence(self.actor,self.case.pk,'signature','Actual synthetic PM report acceptance','synthetic:claim-integrity-PM')
        client=None
        if legacy:
            from .change_signature_helpers import declaration_for
            client=add_evidence(self.actor,self.case.pk,'signature','Actual synthetic Client report acceptance','synthetic:claim-integrity-Client')
            declaration=declaration_for(self.actor,auth,receipt,pm,client)
        else:declaration=json.loads(declaration_draft(auth,receipt,self.actor))
        declaration['signatures']['PM']={'evidence':pin(pm),'source_system':'synthetic-owner-register',
            'source_reference':'exact-report-'+str(receipt.publication.version_id),'decision_id':'pm-'+str(pm.pk),
            'decision_version':'1','signer_reference':'synthetic-PM','purpose':'change_go_live_acceptance','signed_at':timezone.now().isoformat()}
        self.work.refresh_from_db()
        closure=change.close(self.actor,self.work.pk,self.work.revision,rev(self.case),receipt.pk,pm.pk,client.pk if client else None,
            'Actual PM and explicit owner applicability',attestation=declaration,operation_key='claim-integrity')
        self.work.refresh_from_db()
        self.assertEqual(closure.client_signature_id,client.pk if client else None)
        self.assertEqual(current_closure(closure).client_signature_id,client.pk if client else None)
        return closure

    def insert_claim(self, claim, key='false-client-claim'):
        activity=FactoryActivity.objects.create(work=self.work,kind='ACT13',key=hashlib.sha256(key.encode()).hexdigest(),
            plan_revision=self.work.plan_revision,status='succeeded')
        return FactoryAttempt.objects.create(activity=activity,number=1,phase='observed',fence=self.work.fence,
            observation={},result=claim)

    def test_native_rejects_false_client_signed_claim(self):
        self.prepared_assurance();claim=change.verify(self.work)
        self.assertFalse(claim['client_signed']);claim['client_signed']=True
        with self.assertRaises(DatabaseError),transaction.atomic():
            self.insert_claim(claim)
            FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_explicit_claim_mutations_hold_and_truthful_observation_passes(self):
        self.prepared_assurance();truth=change.verify(self.work)
        mutations={'client_signed':True,'original_closure_client_signed':True,
            'current_client_signature_id':999999,'assurance_id':999999,
            'client_signature_requirement':'required','deployment_authorized':True,
            'external_authenticity_verified':True,'closure':999999,'authorization':999999,
            'head':999999,'document_version':999999,'receipt_ids':[],
            'verification_scope':'native_controlled_change_delivery_and_human_signature_attestation'}
        for field,value in mutations.items():
            with self.subTest(field=field),self.assertRaises(DatabaseError),transaction.atomic():
                self.insert_claim(dict(truth,**{field:value}),field)
        for field in ['assurance_id','client_signed','original_closure_client_signed','current_client_signature_id','client_signature_requirement']:
            broken=dict(truth);broken.pop(field)
            with self.subTest(missing=field),self.assertRaises(DatabaseError),transaction.atomic():
                self.insert_claim(broken,'missing-'+field)
        self.insert_claim(truth,'truthful-explicit')
        FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        # A genuinely new Client signature changes current assurance, not the old closure.
        from copy import deepcopy
        from apps.pmo.change_models import ChangeClosure
        from apps.pmo.change_applicability import record_successor
        closure=ChangeClosure.objects.get(pk=truth['closure']);first=current_closure(closure)
        policy,entry=self.configure(closure.authorization,'required')
        client=add_evidence(self.actor,self.case.pk,'signature','New actual synthetic Client assurance','synthetic:later-client')
        declaration=deepcopy(first.declaration)
        declaration['applicability']={'policy_id':policy.pk,'revision':policy.revision,'entry':entry}
        declaration['signatures']['Client']=dict(declaration['signatures']['PM'],evidence=pin(client),
            decision_id='new-client-'+str(client.pk),signer_reference='synthetic-Client',signed_at=timezone.now().isoformat())
        record_successor(self.actor,self.case.pk,closure.pk,client.pk,declaration,
            'New actual Client acceptance after unsigned closure','later-client-claim',rev(self.case),first.pk)
        current=change.verify(self.work)
        self.assertTrue(current['client_signed']);self.assertFalse(current['original_closure_client_signed'])
        self.assertEqual(current['current_client_signature_id'],client.pk)
        self.insert_claim(current,'truthful-later-client')
        with self.assertRaises(DatabaseError),transaction.atomic():
            self.insert_claim(dict(current,original_closure_client_signed=True),'false-historical-client')
        with self.assertRaises(DatabaseError),transaction.atomic():
            self.insert_claim(truth,'stale-original-claim')

    def test_legacy_signed_v1_observation_without_new_fields_remains_valid(self):
        self.prepared_assurance(legacy=True);claim=change.verify(self.work)
        for field in ['assurance_id','client_signed','original_closure_client_signed','current_client_signature_id','client_signature_requirement']:claim.pop(field)
        claim['verification_scope']='native_controlled_change_delivery_and_human_signature_attestation'
        self.insert_claim(claim,'truthful-legacy')
        FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
