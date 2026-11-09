"""P60 signatures must attest the actual delivered change go-live artifact.

The first three cases deliberately construct every native prerequisite before
submitting signatures explicitly belonging to other artifacts. Their rejection
assertions are the regression contract, not expected failures or legacy passes.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.services import add_evidence
from apps.pmo.change_execution import close_change, execution_manifest
from apps.pmo.models import ChangeClosure, ChangeDocumentBinding
from .helpers import rev
from .test_commercial_changes import ChangeExecutionTests


class ChangeClosureSignatureTests(TestCase):
    setUp = ChangeExecutionTests.setUp
    assessments = ChangeExecutionTests.assessments
    authorized = ChangeExecutionTests.authorized
    ready = ChangeExecutionTests.ready
    change_template = ChangeExecutionTests.change_template
    publish_change = ChangeExecutionTests.publish_change

    def assert_unrelated_signatures_rejected(self, purpose, artifact):
        auth = self.authorized()
        template = self.change_template()
        notice = self.publish_change(auth, template, 'notice')
        self.ready(auth)
        receipt = self.publish_change(auth, template, 'go_live')
        binding = ChangeDocumentBinding.objects.get(version=receipt.publication.version)
        self.assertEqual(binding.authorization_id, auth.pk)
        self.assertEqual(binding.execution_ids, execution_manifest(auth))
        self.assertEqual(notice.publication.version.changedocumentbinding.purpose, 'notice')
        signatures = [add_evidence(
            self.actor, self.case.pk, 'signature',
            f'{role} signed {purpose} artifact {artifact}, not this change go-live document',
            f'synthetic:unrelated-signature/{purpose}/{artifact}/{role}',
        ) for role in ('PM', 'Client')]
        self.assertNotEqual(signatures[0].pk, signatures[1].pk)
        with self.assertRaises(ValidationError):
            close_change(self.actor, self.case.pk, auth.pk, receipt.pk,
                         signatures[0].pk, signatures[1].pk,
                         'Attempt to reuse unrelated signature facts', rev(self.case))
        self.assertFalse(ChangeClosure.objects.filter(authorization=auth).exists())

    def test_unrelated_document_signatures_cannot_close_valid_change(self):
        self.assert_unrelated_signatures_rejected('sow', 'unrelated-contract')

    def test_uat_signatures_cannot_close_valid_change(self):
        self.assert_unrelated_signatures_rejected('uat', 'pre-release-uat')

    def test_prior_change_signatures_cannot_close_valid_change(self):
        self.assert_unrelated_signatures_rejected('change_go_live', 'CR-PRIOR')

    def prepared(self):
        from .change_signature_helpers import declaration_for
        auth=self.authorized();t=self.change_template();self.publish_change(auth,t,'notice')
        self.ready(auth);receipt=self.publish_change(auth,t,'go_live')
        pm=add_evidence(self.actor,self.case.pk,'signature','Actual synthetic PM signature of exact change report','synthetic:change-pm')
        client=add_evidence(self.actor,self.case.pk,'signature','Actual synthetic Client signature of exact change report','synthetic:change-client')
        return auth,receipt,pm,client,declaration_for(self.actor,auth,receipt,pm,client)

    def close_prepared(self,items):
        auth,receipt,pm,client,value=items
        return close_change(self.actor,self.case.pk,auth.pk,receipt.pk,pm.pk,client.pk,'Actual source signature verification',rev(self.case),attestation=value)

    def test_exact_source_signatures_close_and_reverify(self):
        from apps.pmo.change_signatures import current_closure
        closure=self.close_prepared(self.prepared())
        row=current_closure(closure)
        self.assertEqual(row.receipt_id,closure.receipt_id)
        self.assertEqual(row.mode,'fresh_signatures')

    def test_purpose_and_exact_subject_pins_reject_without_closure(self):
        from copy import deepcopy
        items=self.prepared();value=items[-1]
        for key in ['case_id','change','authorization','execution','report','attesting_actor_id']:
            modified=deepcopy(value);modified[key]=None
            with self.subTest(key=key),self.assertRaises(ValidationError):self.close_prepared((*items[:-1],modified))
        modified=deepcopy(value);modified['purpose']='uat'
        with self.assertRaises(ValidationError):self.close_prepared((*items[:-1],modified))
        self.assertFalse(ChangeClosure.objects.exists())

    def test_signed_at_requires_actual_aware_after_report_not_future(self):
        from copy import deepcopy
        from datetime import timedelta
        from django.utils import timezone
        items=self.prepared()
        for value in ['2020-01-01T00:00:00',items[1].publication.version.created_at.isoformat(),(timezone.now()+timedelta(days=1)).isoformat()]:
            declaration=deepcopy(items[-1]);declaration['signatures']['PM']['signed_at']=value
            with self.subTest(value=value),self.assertRaises(ValidationError):self.close_prepared((*items[:-1],declaration))

    def test_shared_signed_envelope_keeps_explicit_PM_and_Client_signatures(self):
        items=self.prepared();value=items[-1]
        for key in ['source_system','source_reference','decision_id','decision_version']:
            value['signatures']['Client'][key]=value['signatures']['PM'][key]
        from apps.pmo.change_signatures import current_closure
        closure=self.close_prepared(items)
        row=current_closure(closure)
        self.assertNotEqual(row.pm_signature_id,row.client_signature_id)
        self.assertNotEqual(value['signatures']['PM']['signer_reference'],value['signatures']['Client']['signer_reference'])

    def test_metadata_successor_preserves_existing_closure_and_decision_facts(self):
        from apps.pmo.change_signatures import bind_historical,current_closure
        items=self.prepared();closure=self.close_prepared(items);before=dict(closure.__dict__)
        first=current_closure(closure)
        row=bind_historical(self.actor,self.case.pk,closure.pk,items[-1],'Recover unchanged actual source facts',rev(self.case),first.pk)
        closure.refresh_from_db()
        self.assertEqual(closure.receipt_id,items[1].pk);self.assertEqual(closure.created_at,before['created_at'])
        self.assertEqual(current_closure(closure),row)
        self.assertEqual(ChangeClosure.objects.count(),1)
        self.assertEqual(row.previous_id,first.pk)

    def test_metadata_rejects_changed_decisions_and_wrong_predecessor(self):
        from copy import deepcopy
        from apps.pmo.change_signatures import bind_historical,current_closure
        items=self.prepared();closure=self.close_prepared(items);first=current_closure(closure)
        changed=deepcopy(items[-1]);changed['signatures']['PM']['decision_version']='2'
        with self.assertRaises(ValidationError):bind_historical(self.actor,self.case.pk,closure.pk,changed,'Changed facts',rev(self.case),first.pk)
        with self.assertRaises(ValidationError):bind_historical(self.actor,self.case.pk,closure.pk,items[-1],'Missing predecessor',rev(self.case))

    def test_native_sql_rejects_untyped_binding_and_direct_closure(self):
        from django.db import DatabaseError,transaction
        from apps.pmo.models import ChangeClosureSignatureBinding
        from apps.policy.services import decision_authority
        auth,receipt,pm,client,value=self.prepared()
        with self.assertRaises(DatabaseError),transaction.atomic():
            ChangeClosureSignatureBinding.objects.create(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=client,
                execution_ids=execution_manifest(auth),declaration={},authority=decision_authority(self.actor,self.case,'PM'),mode='fresh_signatures',note='Bypass',actor=self.actor)
        with self.assertRaises(DatabaseError),transaction.atomic():
            ChangeClosure.objects.create(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=client,
                execution_ids=execution_manifest(auth),note='Direct closure bypass',actor=self.actor)

    def test_native_sql_rejects_wrong_pin_naive_time_and_same_evidence(self):
        from copy import deepcopy
        from django.db import DatabaseError,transaction
        from apps.pmo.models import ChangeClosureSignatureBinding
        from apps.policy.services import decision_authority
        auth,receipt,pm,client,value=self.prepared()
        variants=[]
        bad=deepcopy(value);bad['report']['payload_sha256']='0'*64;variants.append(bad)
        bad=deepcopy(value);bad['signatures']['PM']['signed_at']='2026-11-07T00:00:00';variants.append(bad)
        bad=deepcopy(value)
        bad['signatures']['Client']['evidence']=deepcopy(bad['signatures']['PM']['evidence'])
        variants.append(bad)
        for bad in variants:
            with self.assertRaises(DatabaseError),transaction.atomic():
                ChangeClosureSignatureBinding.objects.create(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=client,
                    execution_ids=execution_manifest(auth),declaration=bad,authority=decision_authority(self.actor,self.case,'PM'),mode='fresh_signatures',note='Bypass',actor=self.actor)

    def test_recorder_revocation_holds_current_python_and_sql_proof(self):
        from apps.pmo.change_signatures import current_closure
        from apps.identity.models import Grant
        from django.db import connection
        from django.core.exceptions import PermissionDenied
        closure=self.close_prepared(self.prepared());row=current_closure(closure)
        Grant.objects.filter(user=self.actor,case=self.case,action='change.manage').delete()
        with self.assertRaises((ValidationError,PermissionDenied)):current_closure(closure)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_change_signature_current(r) FROM pmo_changeclosuresignaturebinding r WHERE id=%s',[row.pk])
            self.assertEqual(cursor.fetchone(),(False,))

    def test_http_requires_explicit_declaration_and_transports_actual_facts(self):
        import json
        items=self.prepared();auth,receipt,pm,client,value=items
        self.client.force_login(self.actor)
        data={'action':'close','authorization':auth.pk,'receipt':receipt.pk,'pm_signature':pm.pk,'client_signature':client.pk,'note':'Actual signed change','revision':rev(self.case)}
        self.client.post(f'/cases/{self.case.pk}/changes/',data)
        self.assertFalse(ChangeClosure.objects.exists())
        data.update(attestation=json.dumps(value),revision=rev(self.case))
        self.client.post(f'/cases/{self.case.pk}/changes/',data)
        self.assertEqual(ChangeClosure.objects.count(),1)

    def second_prepared(self):
        from apps.pmo.changes import log_change
        from .change_signature_helpers import declaration_for
        self.cv=log_change(self.actor,self.case.pk,'CR-002','Normal','Delivery','A different change','Separate request',self.source.pk,rev(self.case))
        auth=self.authorized()
        from apps.documents.models import Template
        template=Template.objects.get(case=self.case,name='Change status')
        self.publish_change(auth,template,'notice');self.ready(auth);receipt=self.publish_change(auth,template,'go_live')
        pm=add_evidence(self.actor,self.case.pk,'signature','Actual second change PM signature','synthetic:second-pm')
        client=add_evidence(self.actor,self.case.pk,'signature','Actual second change Client signature','synthetic:second-client')
        return auth,receipt,pm,client,declaration_for(self.actor,auth,receipt,pm,client)

    def test_prior_change_evidence_and_reuploaded_source_decision_rejected(self):
        from copy import deepcopy
        from apps.pmo.go_live_attestations import pin
        from apps.pmo.models import ChangeClosureSignatureBinding
        from apps.policy.services import decision_authority
        from django.db import DatabaseError,transaction
        first=self.prepared();self.close_prepared(first);second=self.second_prepared()
        bad=deepcopy(second[-1]);bad['signatures']['PM']['evidence']=pin(first[2])
        with self.assertRaises(ValidationError):self.close_prepared((second[0],second[1],first[2],second[3],bad))
        bad=deepcopy(second[-1])
        for key in ['source_system','source_reference','decision_id','decision_version']:bad['signatures']['PM'][key]=first[-1]['signatures']['PM'][key]
        with self.assertRaises(ValidationError):self.close_prepared((*second[:-1],bad))
        with self.assertRaises(DatabaseError),transaction.atomic():
            ChangeClosureSignatureBinding.objects.create(authorization=second[0],receipt=second[1],pm_signature=second[2],client_signature=second[3],execution_ids=execution_manifest(second[0]),declaration=bad,authority=decision_authority(self.actor,self.case,'PM'),mode='fresh_signatures',note='Reuploaded decision bypass',actor=self.actor)
        self.close_prepared(second)
        self.assertEqual(ChangeClosure.objects.count(),2)

    def test_existing_sow_signature_cannot_be_relabelled(self):
        from .change_signature_helpers import declaration_for
        items=self.prepared();auth,receipt,pm,client,value=items
        pm=self.e['signature'];value=declaration_for(self.actor,auth,receipt,pm,client)
        with self.assertRaises(ValidationError):self.close_prepared((auth,receipt,pm,client,value))

    def test_sql_null_purpose_cannot_bypass(self):
        from django.db import DatabaseError,transaction
        from apps.pmo.models import ChangeClosureSignatureBinding
        from apps.policy.services import decision_authority
        auth,receipt,pm,client,value=self.prepared();value['signatures']['PM']['purpose']=None
        with self.assertRaises(DatabaseError),transaction.atomic():
            ChangeClosureSignatureBinding.objects.create(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=client,
                execution_ids=execution_manifest(auth),declaration=value,authority=decision_authority(self.actor,self.case,'PM'),mode='fresh_signatures',note='Null purpose bypass',actor=self.actor)

    def test_subject_draft_has_no_inferred_signature_facts(self):
        import json
        from apps.pmo.change_signatures import declaration_draft
        auth,receipt,pm,client,value=self.prepared()
        draft=json.loads(declaration_draft(auth,receipt,self.actor))
        self.assertEqual(draft['report'],value['report'])
        for signature in draft['signatures'].values():
            self.assertIsNone(signature['signed_at']);self.assertIsNone(signature['signer_reference'])
            self.assertIsNone(signature['decision_id']);self.assertIsNone(signature['evidence']['id'])
        with self.assertRaises(ValidationError):self.close_prepared((auth,receipt,pm,client,draft))


from django.test import TransactionTestCase
class ChangeSignatureRaceTests(TransactionTestCase):
    setUp=ChangeClosureSignatureTests.setUp
    assessments=ChangeClosureSignatureTests.assessments
    authorized=ChangeClosureSignatureTests.authorized
    ready=ChangeClosureSignatureTests.ready
    change_template=ChangeClosureSignatureTests.change_template
    publish_change=ChangeClosureSignatureTests.publish_change
    prepared=ChangeClosureSignatureTests.prepared
    second_prepared=ChangeClosureSignatureTests.second_prepared

    def test_two_connections_cannot_reuse_same_declared_decision_across_changes(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections,transaction,DatabaseError
        from apps.pmo.models import ChangeClosureSignatureBinding
        from apps.policy.services import decision_authority
        first=self.prepared();second=self.second_prepared()
        for key in ['source_system','source_reference','decision_id','decision_version']:second[-1]['signatures']['PM'][key]=first[-1]['signatures']['PM'][key]
        authority=decision_authority(self.actor,self.case,'PM');barrier=Barrier(2)
        def insert(items):
            close_old_connections()
            try:
                auth,receipt,pm,client,value=items
                with transaction.atomic():
                    barrier.wait(timeout=10)
                    ChangeClosureSignatureBinding.objects.create(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=client,
                        execution_ids=execution_manifest(auth),declaration=value,authority=authority,mode='fresh_signatures',note='Actual concurrent synthetic source facts',actor=self.actor)
                return 'inserted'
            except DatabaseError as exc:
                self.assertIn('Exact current signed change artifact/source facts required',str(exc))
                return 'rejected'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(insert,[first,second]))
        self.assertCountEqual(results,['inserted','rejected'])
        self.assertEqual(ChangeClosureSignatureBinding.objects.count(),1)
        self.assertEqual(ChangeClosure.objects.count(),0)

    def test_repeatable_read_signature_insertion_fails_closed(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections,transaction,connection,DatabaseError
        from apps.pmo.models import ChangeClosureSignatureBinding
        from apps.policy.services import decision_authority
        auth,receipt,pm,client,value=self.prepared()
        ids=execution_manifest(auth);authority=decision_authority(self.actor,self.case,'PM')
        def insert():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cur:cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                    ChangeClosureSignatureBinding.objects.create(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=client,
                        execution_ids=ids,declaration=value,authority=authority,mode='fresh_signatures',note='Actual facts under nondefault snapshot',actor=self.actor)
            except DatabaseError as exc:return str(exc)
            finally:close_old_connections()
            return 'unexpected insertion'
        with ThreadPoolExecutor(max_workers=1) as pool:result=pool.submit(insert).result(timeout=30)
        self.assertIn('Change signature binding requires READ COMMITTED',result)
        self.assertEqual(ChangeClosureSignatureBinding.objects.count(),0)
