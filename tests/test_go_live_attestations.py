"""P33 exact declared linkage, with real services/PostgreSQL and synthetic signers."""
from copy import deepcopy
from datetime import timedelta
import json
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.pmo import delivery, delivery_closure as closure
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.gates import register_candidate, record_gate, verify_gate
from apps.pmo.models import DeliveryRecord
from apps.identity.models import Grant
from tests.document_helpers import artifact
from tests.helpers import rev
from tests.test_delivery import DeliveryFixture


class GoLiveAttestationTests(DeliveryFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery();f.release()
        inputs={k:f.evidence(kind).pk for k,kind in [('checklist','deployment_checklist'),('incident_reporting','incident_reporting'),('rollback','rollback_plan')]}
        f.version=draft_delivery_document(f.actor,f.case.pk,f.d.pk,'go_live',f.t.pk,inputs,rev(f.case))
        f.receipt=f.publish(f.version)
        f.pm=f.evidence('signature','Synthetic actual later PM decision');f.client_signature=f.evidence('signature','Synthetic actual later Client decision')
        f.declared=f.attestation(f.receipt,f.pm,f.client_signature)
        for key,value in vars(f).items():setattr(cls,key,value)

    def accept(self,value=None):
        return closure.accept_go_live(self.actor,self.case.pk,self.d.pk,self.receipt.pk,self.pm.pk,self.client_signature.pk,
            'Actual supplied synthetic decision facts, not inferred from upload',rev(self.case),attestation=value if value is not None else self.declared)

    def raw(self,value,**overrides):
        from apps.policy.services import decision_authority
        data={'receipt_id':self.receipt.pk,'pm_signature_id':self.pm.pk,'client_signature_id':self.client_signature.pk,
              'note':'Exact SQL test','authority':decision_authority(self.actor,self.case,'PM'),'attestation':value}
        args=dict(dossier=self.d,kind='go_live',parent=delivery.latest(self.d,'release_outcome'),evidence=self.pm,
                  actor=self.actor,data=data,snapshot=self.version.deliverydocumentbinding.snapshot)
        args.update(overrides)
        return DeliveryRecord.objects.create(**args)

    def rejected_native_and_sql(self,value):
        with self.assertRaises(ValidationError):self.accept(value)
        with self.assertRaises(DatabaseError),transaction.atomic():self.raw(value)
        self.assertFalse(self.d.records.filter(kind='go_live').exists())

    def authority(self):
        return artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v8',
            {'rules':[{'role':'PM','actions':['reaffirm_go_live']}]},self.e['policy_decision'])

    def reaffirm(self,old,value=None,mode='metadata_binding',receipt=None,pm=None,client=None):
        return closure.reaffirm_go_live(self.actor,self.case.pk,self.d.pk,old.pk,(receipt or self.receipt).pk,
            (pm or self.pm).pk,(client or self.client_signature).pk,'Explicit evidence binding, not new physical signature',rev(self.case),
            attestation=value if value is not None else self.declared,mode=mode)

    def test_exact_positive_preserves_supplied_decision_time_not_upload_time(self):
        actual=self.declared['signatures']['PM']['signed_at']
        old=self.accept();current=closure.accepted_go_live(self.d)
        self.assertEqual(current.pk,old.pk);self.assertEqual(old.data['attestation']['signatures']['PM']['signed_at'],actual)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=self.d,kind='go_live').count(),1)
        self.assertEqual(connection.vendor,'postgresql')
        with connection.cursor() as c:
            c.execute('SELECT psl_gl_attestation(r) FROM pmo_deliveryrecord r WHERE id=%s',[old.pk]);self.assertTrue(c.fetchone()[0])

    def test_direct_sql_exact_positive_and_immutable_decision(self):
        old=self.raw(self.declared)
        self.assertEqual(closure.accepted_go_live(self.d).pk,old.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():DeliveryRecord.objects.filter(pk=old.pk).update(data={})

    def test_all_subject_and_evidence_pins_reject_individually_native_and_sql(self):
        paths=[('dossier_id',),('candidate','id'),('candidate','reference'),('candidate','requirements','id'),
          ('candidate','requirements','version'),('candidate','requirements','sha256'),('release','id'),('release','external_ref'),
          ('release','released_at'),('report','document_id'),('report','version_id'),('report','number'),('report','payload_sha256'),
          ('report','receipt_id'),('attesting_actor_id',),('signatures','PM','evidence','id'),('signatures','PM','evidence','version'),
          ('signatures','PM','evidence','sha256'),('signatures','Client','evidence','id'),('case_id',)]
        for path in paths:
            with self.subTest(path=path):
                value=deepcopy(self.declared);node=value
                for key in path[:-1]:node=node[key]
                previous=node[path[-1]]
                node[path[-1]]=previous+999 if type(previous) is int else '0'*64 if path[-1].endswith('sha256') else '00000000-0000-0000-0000-000000000001' if path[-1]=='case_id' else 'wrong'
                self.rejected_native_and_sql(value)

    def test_missing_unknown_naive_future_pre_release_times_and_unprovided_facts(self):
        for path in [('protocol',),('signatures','PM','source_system'),('signatures','Client','decision_id'),('signatures','PM','decision_version'),('signatures','Client','signer_reference'),('signatures','PM','signed_at')]:
            with self.subTest(missing=path):
                value=deepcopy(self.declared);node=value
                for key in path[:-1]:node=node[key]
                del node[path[-1]];self.rejected_native_and_sql(value)
        for supplied in ['2026-11-07T10:00:00',(timezone.now()+timedelta(days=1)).isoformat(),self.declared['release']['released_at'],'tomorrow',None]:
            with self.subTest(time=supplied):
                value=deepcopy(self.declared);value['signatures']['PM']['signed_at']=supplied;self.rejected_native_and_sql(value)
        value=deepcopy(self.declared);value['signatures']['PM']['made_up']=True;self.rejected_native_and_sql(value)
        value=deepcopy(self.declared);value['signatures']['PM']['decision_id']='';self.rejected_native_and_sql(value)

    def test_generic_signature_uploaded_after_release_with_uat_purpose_rejects(self):
        self.assertGreater(self.pm.created_at,delivery.latest(self.d,'release_outcome').created_at)
        value=deepcopy(self.declared);value['signatures']['PM']['purpose']='pre_release_uat'
        self.rejected_native_and_sql(value)

    def test_recorded_uat_history_on_other_candidate_rejects_initial_currentness_and_sql(self):
        old=self.accept()
        candidate=register_candidate(self.actor,self.case.pk,'other-UAT-subject',self.e['requirements'].pk,rev(self.case))
        record_gate(self.actor,self.case.pk,candidate.pk,'uat_client','Actual UAT source contradicts selected signature',self.pm.pk,rev(self.case))
        with self.assertRaisesMessage(ValidationError,'Recorded UAT'):closure.accepted_go_live(self.d)
        with connection.cursor() as c:
            c.execute('SELECT psl_gl_attestation(r) FROM pmo_deliveryrecord r WHERE id=%s',[old.pk]);self.assertFalse(c.fetchone()[0])
        self.authority()
        with self.assertRaisesMessage(ValidationError,'Recorded UAT'):self.reaffirm(old)

    def test_unchanged_metadata_binding_is_linear_preserves_original_decisions(self):
        old=self.accept();self.authority();head=self.reaffirm(old)
        self.assertEqual(head.parent_id,old.pk);self.assertEqual(head.data['attestation'],old.data['attestation'])
        self.assertEqual(head.data['mode'],'metadata_binding');self.assertEqual(closure.accepted_go_live(self.d).pk,head.pk)
        self.assertEqual(self.d.records.filter(kind='go_live').count(),1)
        with self.assertRaisesMessage(ValidationError,'STALE_VERSION'):self.reaffirm(old)
        value=deepcopy(self.declared);value['signatures']['PM']['decision_id']='alter-original-fact'
        with self.assertRaisesMessage(ValidationError,'original source'):self.reaffirm(head,value)

    def test_metadata_binding_cannot_launder_changed_report_or_new_evidence(self):
        old=self.accept();self.authority()
        pm=self.evidence('signature','Different PM evidence cannot be metadata-only')
        value=self.attestation(self.receipt,pm,self.client_signature)
        with self.assertRaisesMessage(ValidationError,'unchanged'):self.reaffirm(old,value,pm=pm)
        inputs=dict(self.version.deliverydocumentbinding.data,rollback=self.evidence('rollback_plan','Actual changed rollback').pk)
        version=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'go_live',self.t.pk,inputs,rev(self.case));receipt=self.publish(version)
        value=self.attestation(receipt,self.pm,self.client_signature)
        with self.assertRaisesMessage(ValidationError,'unchanged'):self.reaffirm(old,value,receipt=receipt)
        with self.assertRaisesMessage(ValidationError,'reused'):self.reaffirm(old,value,mode='fresh_signatures',receipt=receipt)
        pm=self.evidence('signature','Actual synthetic signature for new report');client=self.evidence('signature','Actual synthetic client signature for new report')
        head=self.reaffirm(old,self.attestation(receipt,pm,client),mode='fresh_signatures',receipt=receipt,pm=pm,client=client)
        self.assertEqual(closure.accepted_go_live(self.d).pk,head.pk)

    def test_current_grant_revocation_holds_native_currentness_and_sql(self):
        old=self.accept();Grant.objects.filter(case=self.case,user=self.actor,action='delivery.manage').delete()
        with self.assertRaises(PermissionDenied):closure.accepted_go_live(self.d)
        with connection.cursor() as c:
            c.execute('SELECT psl_gl_attestation(r) FROM pmo_deliveryrecord r WHERE id=%s',[old.pk]);self.assertFalse(c.fetchone()[0])

    def test_http_requires_explicit_envelope_and_accepts_exact_declaration(self):
        self.client.force_login(self.actor);url=reverse('delivery',args=[self.case.pk])
        post={'action':'accept','revision':rev(self.case),'dossier':self.d.pk,'receipt':self.receipt.pk,
              'pm_signature':self.pm.pk,'client_signature':self.client_signature.pk,'note':'Actual supplied exact facts'}
        response=self.client.post(url,post);self.assertContains(response,'explicit go-live-attestation/v1')
        self.assertFalse(self.d.records.filter(kind='go_live').exists())
        post['attestation']=json.dumps(self.declared);response=self.client.post(url,post)
        self.assertRedirects(response,url);self.assertEqual(closure.accepted_go_live(self.d).data['attestation'],self.declared)

    def test_legacy_untyped_insert_is_rejected_without_backfill(self):
        from apps.policy.services import decision_authority
        data={'receipt_id':self.receipt.pk,'pm_signature_id':self.pm.pk,'client_signature_id':self.client_signature.pk,'note':'Legacy shape'}
        with self.assertRaises(DatabaseError),transaction.atomic():self.raw(self.declared,data=data)
        with self.assertRaises(ValidationError):closure.accept_go_live(self.actor,self.case.pk,self.d.pk,self.receipt.pk,self.pm.pk,self.client_signature.pk,'No missing fact defaults',rev(self.case))

    def test_reuploaded_source_decision_identity_cannot_sign_a_second_artifact(self):
        old=self.accept();self.authority()
        pm=self.evidence('signature','Reupload of same PM source decision');client=self.evidence('signature','Reupload of same Client source decision')
        value=self.attestation(self.receipt,pm,client)
        for role in ['PM','Client']:
            for key in ['source_system','source_reference','decision_id','decision_version']:
                value['signatures'][role][key]=self.declared['signatures'][role][key]
        with self.assertRaisesMessage(ValidationError,'source decision identity'):
            self.reaffirm(old,value,mode='fresh_signatures',pm=pm,client=client)
        from apps.policy.services import decision_authority
        data=dict(old.data,attestation=value,mode='fresh_signatures',previous_acceptance_id=old.pk,
            pm_signature_id=pm.pk,client_signature_id=client.pk,authority=decision_authority(self.actor,self.case,'PM','reaffirm_go_live'))
        with self.assertRaises(DatabaseError),transaction.atomic():
            self.raw(value,kind='go_live_reaffirmation',parent=old,evidence=pm,data=data)

    def test_direct_sql_metadata_mode_cannot_change_ids_subject_or_original_decision(self):
        old=self.accept();self.authority()
        from apps.policy.services import decision_authority
        data=dict(old.data,mode='metadata_binding',previous_acceptance_id=old.pk,
            authority=decision_authority(self.actor,self.case,'PM','reaffirm_go_live'))
        for key in ['receipt_id','pm_signature_id','client_signature_id','previous_acceptance_id']:
            with self.subTest(key=key),self.assertRaises(DatabaseError),transaction.atomic():
                self.raw(self.declared,kind='go_live_reaffirmation',parent=old,data=dict(data,**{key:data[key]+999}))
        for path in [('report','payload_sha256'),('signatures','PM','decision_id'),('signatures','Client','signed_at')]:
            value=deepcopy(self.declared);node=value
            for key in path[:-1]:node=node[key]
            node[path[-1]]='0'*64 if path[-1]=='payload_sha256' else timezone.now().isoformat() if path[-1]=='signed_at' else 'different-decision'
            with self.subTest(path=path),self.assertRaises(DatabaseError),transaction.atomic():
                self.raw(value,kind='go_live_reaffirmation',parent=old,data=dict(data,attestation=value))
        head=self.raw(self.declared,kind='go_live_reaffirmation',parent=old,data=data)
        self.assertEqual(closure.accepted_go_live(self.d).pk,head.pk)

    def test_authority_and_numeric_json_types_cannot_be_forged_directly(self):
        from apps.policy.services import decision_authority
        base={'receipt_id':self.receipt.pk,'pm_signature_id':self.pm.pk,'client_signature_id':self.client_signature.pk,
            'note':'Exact authority must remain current','authority':decision_authority(self.actor,self.case,'PM'),'attestation':self.declared}
        for authority in [{},{'D05.role_principal_assignments':999999},dict(base['authority'],unknown=1)]:
            with self.subTest(authority=authority),self.assertRaises(DatabaseError),transaction.atomic():
                self.raw(self.declared,data=dict(base,authority=authority))
        value=deepcopy(self.declared);value['report']['number']=float(value['report']['number'])
        self.rejected_native_and_sql(value)

    def test_explicit_time_can_precede_upload_but_not_release(self):
        signed_at=timezone.now().isoformat()
        pm=self.evidence('signature','Uploaded after actual declared signing');client=self.evidence('signature','Client upload also later')
        value=self.attestation(self.receipt,pm,client,signed_at=signed_at)
        old=closure.accept_go_live(self.actor,self.case.pk,self.d.pk,self.receipt.pk,pm.pk,client.pk,
            'Actual signed-at supplied independently of later upload',rev(self.case),attestation=value)
        self.assertLess(timezone.datetime.fromisoformat(signed_at),pm.created_at)
        self.assertEqual(closure.accepted_go_live(self.d).pk,old.pk)


class PreReleaseUATRegressionTests(DeliveryFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery()
        for key,value in vars(f).items():setattr(cls,key,value)

    def go_live_receipt(self):
        data = {key: self.evidence(kind).pk for key, kind in [
            ('checklist', 'deployment_checklist'), ('incident_reporting', 'incident_reporting'), ('rollback', 'rollback_plan')]}
        version = draft_delivery_document(self.actor, self.case.pk, self.d.pk, 'go_live', self.t.pk, data, rev(self.case))
        return self.publish(version)

    def released_with_uat(self, pm_uat, client_uat):
        self.plan()
        for kind in delivery.UPSTREAM_GATES:
            evidence = pm_uat if kind == 'uat_product_manager' else client_uat if kind == 'uat_client' else self.e['requirements']
            gate = record_gate(self.actor, self.case.pk, self.candidate.pk, kind, 'PRE-RELEASE-754:' + kind, evidence.pk, rev(self.case))
            verify_gate(self.actor, self.case.pk, gate.pk, rev(self.case))
        delivery.record_release_request(self.actor, self.case.pk, self.d.pk, 'GLPI-754', self.e['plan'].pk,
            'Exact pre-release UAT approvals and Engineering Go', rev(self.case))
        self.gates(delivery.GLPI_GATES, 'GLPI-754')
        ready = delivery.prepare_readiness(self.actor, self.case.pk, self.d.pk, rev(self.case))
        outcome = delivery.capture_release(self.actor, self.case.pk, self.d.pk, ready.pk, timezone.now(),
            'INFRA-754', self.e['completion'].pk, 'Actual later synthetic release', rev(self.case))
        return outcome

    def test_p33_m02_signature_typed_pre_release_uat_cannot_be_reused_as_go_live(self):
        pm_uat = self.evidence('signature', 'Pre-release UAT signature only, not go-live: PM')
        client_uat = self.evidence('signature', 'Pre-release UAT signature only, not go-live: Client')
        outcome = self.released_with_uat(pm_uat, client_uat)
        receipt = self.go_live_receipt()
        self.assertLess(client_uat.created_at, outcome.created_at)
        self.assertEqual(delivery.valid_release(self.d).pk, outcome.pk)
        with self.assertRaises(ValidationError):
            closure.accept_go_live(self.actor, self.case.pk, self.d.pk, receipt.pk, pm_uat.pk, client_uat.pk,
                'Attempt to reuse recorded pre-release UAT signatures only', rev(self.case))
        self.assertFalse(self.d.records.filter(kind__in=['go_live', 'go_live_reaffirmation']).exists())

    def test_exact_pre_release_uat_ids_reject_even_with_declared_later_go_live_purpose(self):
        pm=self.evidence('signature','Actual synthetic UAT PM signature');client=self.evidence('signature','Actual synthetic UAT Client signature')
        self.released_with_uat(pm,client);receipt=self.go_live_receipt()
        declaration=self.attestation(receipt,pm,client)
        with self.assertRaisesMessage(ValidationError,'Recorded UAT'):
            closure.accept_go_live(self.actor,self.case.pk,self.d.pk,receipt.pk,pm.pk,client.pk,
                'A later claimed purpose cannot override recorded UAT decision evidence',rev(self.case),attestation=declaration)
        self.assertFalse(self.d.records.filter(kind='go_live').exists())


from django.test import TransactionTestCase

class GoLiveSQLConcurrencyTests(TransactionTestCase):
    """Raw SQL must serialize same-case reuse, not only native lock_case callers."""
    def setUp(self):
        from apps.pmo.meetings import record_meeting
        from apps.policy.services import decision_authority
        f=DeliveryFixture();f.setup_delivery();f.release()
        other=DeliveryFixture();other.__dict__.update(vars(f))
        other.candidate=register_candidate(f.actor,f.case.pk,'second-real-release-subject',f.e['requirements'].pk,rev(f.case))
        other.d=delivery.open_dossier(f.actor,f.case.pk,other.candidate.pk,f.e['plan'].pk,'Independent actual delivery subject',rev(f.case))
        for kind in delivery.PLANNING:
            other.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        delivery.decide_planning(f.actor,f.case.pk,other.d.pk,'approve',f.e['plan'].pk,'Exact second Planning exit',rev(f.case))
        meeting=record_meeting(f.actor,f.case.pk,'SECOND-KICKOFF','kickoff',timezone.now(),'Independent second delivery kickoff',
            'Actual synthetic participants and decision', [f.actor.pk],[],f.e['requirements'].pk,rev(f.case))
        delivery.record_progress(f.actor,f.case.pk,other.d.pk,'kickoff',meeting.evidence_id,'Second actual kickoff',rev(f.case),meeting.pk)
        other.gates(delivery.UPSTREAM_GATES)
        delivery.record_release_request(f.actor,f.case.pk,other.d.pk,'GLPI-SECOND',f.e['requirements'].pk,'Second actual deployment request',rev(f.case))
        other.gates(delivery.GLPI_GATES,'GLPI-SECOND');ready=delivery.prepare_readiness(f.actor,f.case.pk,other.d.pk,rev(f.case))
        delivery.capture_release(f.actor,f.case.pk,other.d.pk,ready.pk,timezone.now(),'second-actual-release',f.e['completion'].pk,'Second actual Infra outcome',rev(f.case))
        pm=f.evidence('signature','Same supplied PM decision must not be reused');client=f.evidence('signature','Same supplied Client decision must not be reused')
        self.rows=[];self.case=f.case
        for current in [f,other]:
            inputs={k:f.evidence(kind).pk for k,kind in [('checklist','deployment_checklist'),('incident_reporting','incident_reporting'),('rollback','rollback_plan')]}
            v=draft_delivery_document(f.actor,f.case.pk,current.d.pk,'go_live',f.t.pk,inputs,rev(f.case));receipt=f.publish(v)
            value=current.attestation(receipt,pm,client)
            self.rows.append(dict(dossier_id=current.d.pk,kind='go_live',parent_id=delivery.valid_release(current.d).pk,evidence_id=pm.pk,actor_id=f.actor.pk,
                data={'receipt_id':receipt.pk,'pm_signature_id':pm.pk,'client_signature_id':client.pk,'note':'Direct SQL concurrent reuse attempt',
                    'authority':decision_authority(f.actor,f.case,'PM'),'attestation':value},snapshot=v.deliverydocumentbinding.snapshot))

    def test_concurrent_different_dossiers_cannot_reuse_same_signature_decisions(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        import time
        barrier=Barrier(2)
        def insert(row):
            close_old_connections()
            try:
                with transaction.atomic():
                    barrier.wait(timeout=15)
                    value=DeliveryRecord.objects.create(**row)
                    time.sleep(.4)  # Keep first insertion uncommitted while the peer enters.
                return value.pk
            except DatabaseError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(insert,self.rows))
        self.assertEqual(results.count('held'),1,results)
        self.assertEqual(DeliveryRecord.objects.filter(dossier__case=self.case,kind='go_live').count(),1)

    def test_snapshot_isolation_cannot_bypass_cross_dossier_reuse_serialization(self):
        with self.assertRaisesMessage(DatabaseError,'READ COMMITTED'),transaction.atomic():
            with connection.cursor() as c:c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            DeliveryRecord.objects.create(**self.rows[0])
        self.assertFalse(DeliveryRecord.objects.filter(dossier__case=self.case,kind='go_live').exists())
