"""P22 exact UI work target versus independently versioned owner receipts.

Only the external authoritative source adapter is synthetic. Native capture,
verification, Planning decisions, grants, currentness and SQL are real.
"""
from copy import deepcopy
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, DatabaseError, transaction
from django.test import TestCase
from django.utils import timezone
from apps.pmo import delivery
from apps.pmo.models import DeliverySource, DeliverySourceVerification, DeliveryRecord
from apps.identity.models import Grant
from adapters.delivery import SyntheticDeliverySourceAdapter, LocalDeliveryAdapter
from .test_delivery import DeliveryFixture
from .helpers import rev


from .ui_artifact_helpers import target_payload,approval_payload


class UIArtifactFixture(DeliveryFixture):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery()
        for key,value in vars(f).items():setattr(cls,key,value)

    def inputs(self, required=True, client=False):
        for kind in delivery.PLANNING:
            self.source(kind,{'requires_ui':required,'client_signoff_required':client} if kind=='ui_applicability' else {})

    def target(self,version='v2',verify=True):
        artifact=self.evidence('ui_design_artifact','Synthetic UI artifact '+version)
        owner=self.evidence('ui_target_statement','Product/Design targets exact '+version)
        payload=target_payload(artifact,version)
        s=self.source('ui_target',payload,owner,verify)
        return s,payload

    def approval(self,target,kind='ui_design',version='receipt-17',verify=True):
        payload=approval_payload(target,version,'Client' if kind=='ui_client' else 'Design Lead')
        evidence=self.evidence('ui_owner_signoff','Synthetic independent '+kind+' '+version)
        return self.source(kind,payload,evidence,verify)

    def decide(self):
        return delivery.decide_planning(self.actor,self.case.pk,self.d.pk,'approve',self.e['plan'].pk,
            'PMO confirms exact independently owned source receipts',rev(self.case))


class UIArtifactBindingTests(UIArtifactFixture, TestCase):
    def test_same_candidate_target_v2_does_not_accept_approved_v1(self):
        self.inputs(True,False);target,payload=self.target('v2')
        old=deepcopy(payload);old['artifact_version']='v1'
        approval=self.approval(old,verify=False)
        with self.assertRaisesMessage(ValidationError,'UI artifact target mismatch'):
            delivery.verify_source(self.actor,self.case.pk,approval.pk,rev(self.case))
        self.assertFalse(approval.verifications.exists())
        with self.assertRaisesMessage(ValidationError,'UI artifact target mismatch'):self.decide()
        self.assertFalse(self.d.records.filter(kind='planning_decision').exists())
        self.assertEqual(target.dossier.candidate_id,approval.dossier.candidate_id)

    def test_exact_v2_positive_independent_receipt_versions_and_conditional_client(self):
        self.inputs(True,True);target,payload=self.target('v2')
        design=self.approval(payload,version='design-source-r17')
        with self.assertRaisesMessage(ValidationError,'ui_client'):self.decide()
        client=self.approval(payload,'ui_client','client-source-r4')
        plan=self.decide();snapshot=delivery.planning_inputs(self.d)
        self.assertEqual(snapshot,plan.snapshot)
        self.assertEqual(snapshot['ui_target'],dict({k:payload[k] for k in ['artifact_ref','artifact_version','artifact_sha256','artifact_evidence']},source_id=target.pk,verification_id=target.verifications.get().pk))
        self.assertEqual(snapshot['sources']['ui_design'],[design.pk,design.verifications.get().pk])
        self.assertEqual(snapshot['sources']['ui_client'],[client.pk,client.verifications.get().pk])
        self.assertNotEqual(design.pk,client.pk)
        self.assertEqual(design.payload['source_version'],'design-source-r17')
        self.assertEqual(client.payload['source_version'],'client-source-r4')
        self.assertEqual(design.verifications.get().result['ui_binding'],design.payload)
        self.assertEqual(delivery.approved_plan(self.d).pk,plan.pk)

    def test_matching_version_with_different_artifact_hash_is_not_approval(self):
        self.inputs();target,payload=self.target()
        wrong=deepcopy(payload);wrong['artifact_sha256']='f'*64
        source=self.approval(wrong,verify=False)
        with self.assertRaisesMessage(ValidationError,'UI artifact target mismatch'):
            delivery.verify_source(self.actor,self.case.pk,source.pk,rev(self.case))
        with self.assertRaisesMessage(ValidationError,'UI artifact target mismatch'):self.decide()
        bad=deepcopy(payload);bad['artifact_sha256']='e'*64
        with self.assertRaisesMessage(ValidationError,'artifact hash'):
            self.source('ui_target',bad,target.evidence)

    def test_target_successor_invalidates_only_dependent_planning_not_history_or_other_dossier(self):
        self.inputs();old,payload=self.target('v1');approval=self.approval(payload)
        plan=self.decide();old_receipt=deepcopy(approval.verifications.get().result)
        from apps.pmo.gates import register_candidate
        candidate=register_candidate(self.actor,self.case.pk,'separate-non-ui-build',self.e['requirements'].pk,rev(self.case))
        second=delivery.open_dossier(self.actor,self.case.pk,candidate.pk,self.e['plan'].pk,'Separate non UI work',rev(self.case))
        original=self.d;self.d=second;self.inputs(False,False);other=self.decide();self.d=original
        new,new_payload=self.target('v2',verify=False)
        with self.assertRaisesMessage(ValidationError,'ui_target'):delivery.approved_plan(self.d)
        self.assertEqual(delivery.approved_plan(second).pk,other.pk)
        delivery.verify_source(self.actor,self.case.pk,new.pk,rev(self.case))
        with self.assertRaisesMessage(ValidationError,'UI artifact target mismatch'):delivery.approved_plan(self.d)
        self.approval(new_payload,version='receipt-18')
        with self.assertRaisesMessage(ValidationError,'Current exact Planning'):delivery.approved_plan(self.d)
        successor=self.decide();self.assertNotEqual(successor.pk,plan.pk)
        plan.refresh_from_db();approval.refresh_from_db();old.refresh_from_db()
        self.assertEqual(plan.snapshot['ui_target']['source_id'],old.pk)
        self.assertEqual(approval.verifications.get().result,old_receipt)
        self.assertEqual(delivery.approved_plan(second).pk,other.pk)
        for table,pk,column in [('pmo_deliverysource',old.pk,'payload'),('pmo_deliverysourceverification',approval.verifications.get().pk,'result'),('pmo_deliveryrecord',plan.pk,'snapshot')]:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as c:c.execute(f'UPDATE {table} SET {column}=%s WHERE id=%s',['{}',pk])

    def test_owner_na_and_unknown_preserved_technical_design_independent(self):
        self.inputs(False,False);plan=self.decide()
        self.assertNotIn('ui_target',plan.snapshot)
        self.assertNotIn('ui_design',plan.snapshot['sources'])
        self.source('ui_applicability',{'requires_ui':None,'client_signoff_required':None})
        with self.assertRaisesMessage(ValidationError,'remain unknown'):delivery.planning_inputs(self.d)
        self.source('ui_applicability',{'requires_ui':True,'client_signoff_required':False})
        self.source('technical_design',verify=False)
        target,payload=self.target();self.approval(payload)
        with self.assertRaisesMessage(ValidationError,'technical_design'):self.decide()
        self.source('technical_design');self.assertNotIn('ui_client',self.decide().snapshot['sources'])

    def test_owner_source_identity_cannot_be_relabelled_as_new_approval(self):
        self.inputs();target,payload=self.target('v1');approval=self.approval(payload)
        new,new_payload=self.target('v2')
        with self.assertRaisesMessage(ValidationError,'receipt version cannot be rebound'):
            self.approval(new_payload,version=approval.payload['source_version'])
        self.approval(new_payload,version='receipt-18');self.decide()
        wrong=target_payload(self.evidence('ui_design_artifact','Changed same immutable identifier'),'v2')
        with self.assertRaisesMessage(ValidationError,'already identifies different content'):
            self.source('ui_target',wrong,new.evidence)

    def test_external_binding_must_explicitly_identify_approved_target_and_remains_synthetic(self):
        self.inputs();target,payload=self.target();source=self.approval(payload,verify=False)
        class Wrong(SyntheticDeliverySourceAdapter):
            def read(self,s):
                r=super().read(s);r['ui_binding']['approved_ui_target']['artifact_version']='v1';return r
        with self.assertRaises(ValidationError):delivery.verify_source(self.actor,self.case.pk,source.pk,rev(self.case),Wrong())
        self.assertFalse(source.verifications.exists())
        delivery.verify_source(self.actor,self.case.pk,source.pk,rev(self.case));self.decide()
        from apps.agents.delivery import investigate_delivery
        result=investigate_delivery(self.actor,self.case.pk,self.d.pk,rev(self.case)).result
        self.assertFalse(result['external_authenticity_verified']);self.assertFalse(result['approval_granted'])
        self.assertIn(payload['artifact_evidence']['id'],result['source_evidence_ids'])
        self.case.synthetic=False;self.case.save(update_fields=['synthetic'])
        # Cached dossier relations must not promote retained synthetic receipts into operational readiness.
        with self.assertRaisesMessage(ValidationError,'accepted authoritative adapter contract'):
            delivery.planning_inputs(self.d)
        with self.assertRaisesMessage(ValidationError,'accepted remote adapter contract'):
            delivery.verify_source(self.actor,self.case.pk,source.pk,rev(self.case))

    def test_legacy_empty_approvals_are_not_silently_promoted(self):
        self.inputs();target,payload=self.target()
        for kind in ['ui_design','ui_client']:
            with self.assertRaisesMessage(ValidationError,'Legacy UI receipt'):
                self.source(kind,{})
        self.assertFalse(self.d.sources.filter(kind__in=['ui_design','ui_client']).exists())
        self.approval(payload);self.decide()

    def test_source_grant_revocation_holds_current_target_and_authorized_successor_recovers(self):
        self.inputs();target,payload=self.target();self.approval(payload);self.decide()
        Grant.objects.filter(case=self.case,user=self.actor,action='delivery.source').update(active=False)
        with self.assertRaises(PermissionDenied):delivery.approved_plan(self.d)
        with self.assertRaises(PermissionDenied):self.target('v3')
        from django.contrib.auth import get_user_model
        recorder=get_user_model().objects.create_user('synthetic-ui-recorder')
        Grant.objects.create(case=self.case,user=recorder,action='delivery.source')
        new=delivery.capture_source(recorder,self.case.pk,self.d.pk,'ui_target','owned:ui_target',target.evidence_id,payload,rev(self.case))
        delivery.verify_source(self.actor,self.case.pk,new.pk,rev(self.case))
        # Old approval recorder is also revoked; a target recapture cannot heal it.
        with self.assertRaises(PermissionDenied):delivery.planning_inputs(self.d)
        approval=self.d.sources.filter(kind='ui_design').latest('pk')
        replacement=delivery.capture_source(recorder,self.case.pk,self.d.pk,'ui_design',approval.external_ref,approval.evidence_id,approval.payload,rev(self.case))
        delivery.verify_source(self.actor,self.case.pk,replacement.pk,rev(self.case));self.decide()

    def test_http_explicit_fields_denied_reader_private_evidence_and_get_are_safe(self):
        self.inputs();artifact=self.evidence('ui_design_artifact','Synthetic UI target body')
        owner=self.evidence('ui_target_statement','Explicit Product/Design declaration')
        self.client.force_login(self.actor);url=f'/cases/{self.case.pk}/delivery/'
        before=rev(self.case);response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertContains(response,'UI artifact and source receipt')
        self.assertEqual(rev(self.case),before)
        response=self.client.post(url,{'action':'source','revision':rev(self.case),'dossier':self.d.pk,'evidence':owner.pk,
            'kind':'ui_target','external_ref':'synthetic:product-design-target','artifact_ref':'synthetic:ui/design',
            'artifact_version':'v2','artifact_sha256':artifact.sha256,'artifact_evidence':artifact.pk},follow=True)
        self.assertEqual(response.status_code,200)
        target=self.d.sources.get(kind='ui_target');self.assertEqual(target.payload['artifact_version'],'v2')
        private=self.evidence('agent_private_ui','PRIVATE-UI-SENTINEL')
        with self.assertRaisesMessage(ValidationError,'Private agent source'):
            self.source('ui_target',target_payload(private,'v3'),owner)
        from django.contrib.auth import get_user_model
        reader=get_user_model().objects.create_user('synthetic-ui-unprivileged')
        Grant.objects.create(case=self.case,user=reader,action='case.read')
        self.client.force_login(reader);denied=self.client.get(url)
        self.assertIn(denied.status_code,[403,404]);self.assertNotContains(denied,'synthetic:product-design-target',status_code=denied.status_code)

    def test_generic_new_evidence_does_not_retarget_work_or_revoke_approval(self):
        self.inputs();target,payload=self.target();self.approval(payload);plan=self.decide()
        self.evidence('ui_design_artifact','Unselected newer candidate evidence, not Product/Design target declaration')
        self.assertEqual(delivery.approved_plan(self.d).pk,plan.pk)
        self.assertEqual(delivery.planning_inputs(self.d)['ui_target']['source_id'],target.pk)

    def test_typed_sources_do_not_trust_malformed_evidence_content_hash(self):
        from apps.core.models import Evidence
        malformed=Evidence.objects.create(case=self.case,kind='ui_design_artifact',version=1,body='Captured bytes',
            source='synthetic:malformed-hash',sha256='f'*64,created_by=self.actor)
        payload=target_payload(malformed)
        with self.assertRaisesMessage(ValidationError,'content hash'):
            self.source('ui_target',payload,self.evidence('ui_target_statement'))
        artifact=self.evidence('ui_design_artifact','Valid bytes')
        with self.assertRaisesMessage(ValidationError,'content hash'):
            self.source('ui_target',target_payload(artifact,'v3'),malformed)

    def test_incomplete_authorized_target_declaration_holds_old_plan_until_complete_successor(self):
        self.inputs();target,payload=self.target('v1');self.approval(payload);plan=self.decide()
        declaration={'protocol':'ui-target/v1','artifact_ref':'synthetic:ui/work-design','artifact_version':'v2',
            'artifact_sha256':None,'artifact_evidence':None}
        pending=self.source('ui_target',declaration,self.evidence('ui_target_statement','Product/Design declares v2; artifact evidence pending'),False)
        with self.assertRaisesMessage(ValidationError,'Current declared UI target is incomplete'):
            delivery.verify_source(self.actor,self.case.pk,pending.pk,rev(self.case))
        with self.assertRaisesMessage(ValidationError,'Current declared UI target is incomplete'):delivery.approved_plan(self.d)
        self.assertFalse(pending.verifications.exists());self.assertEqual(plan.snapshot['ui_target']['source_id'],target.pk)
        new,payload2=self.target('v2');self.approval(payload2,version='receipt-18')
        self.assertNotEqual(self.decide().pk,plan.pk)

    def test_http_noncanonical_source_timestamp_returns_validation_without_database_error(self):
        self.inputs();target,payload=self.target()
        self.client.force_login(self.actor)
        count=self.d.sources.count();evidence=self.evidence('ui_owner_signoff','Synthetic owner decision')
        response=self.client.post(f'/cases/{self.case.pk}/delivery/',{'action':'source','revision':rev(self.case),
            'dossier':self.d.pk,'evidence':evidence.pk,
            'kind':'ui_design','external_ref':'synthetic:malformed-date','artifact_ref':payload['artifact_ref'],
            'artifact_version':payload['artifact_version'],'artifact_sha256':payload['artifact_sha256'],
            'source_version':'source-21','signatory_ref':'synthetic:design-lead','decided_at':'2026-01-01 12:00:00+00:00'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'does not match')
        self.assertEqual(self.d.sources.count(),count)


class UIArtifactSQLTests(UIArtifactFixture, TestCase):
    """Raw SQL defenses, using the same native fixture without inherited test cases."""
    def raw_source(self,kind,payload,evidence=None,external_ref=None):
        return DeliverySource.objects.create(dossier=self.d,kind=kind,payload=payload,
            evidence=evidence or self.e['requirements'],external_ref=external_ref or 'raw:'+kind,actor=self.actor)

    def sql_current(self,plan):
        import json
        with connection.cursor() as c:
            c.execute('SELECT psl_delivery_ui_current(%s,%s::jsonb),psl_progress_plan(%s)',[self.d.pk,json.dumps(plan.snapshot),plan.pk])
            return c.fetchone()

    def test_sql_rejects_structural_private_foreign_and_rebound_target_sources(self):
        self.inputs();target,payload=self.target()
        bad=deepcopy(payload);bad['artifact_evidence']['version']+=1
        malformed=[bad,dict(payload,artifact_sha256='f'*64),dict(payload,unexpected=True),{}]
        private=self.evidence('agent_private_ui','PRIVATE-RAW-UI')
        malformed.append(target_payload(private,'v3'))
        from .helpers import setup_case
        from apps.core.services import add_evidence
        actor,other=setup_case(username='ui-sql-foreign');foreign=add_evidence(actor,other.pk,'ui_design_artifact','Foreign artifact','synthetic:other')
        malformed.append(target_payload(foreign,'v4'))
        for value in malformed:
            with self.assertRaises(DatabaseError),transaction.atomic():self.raw_source('ui_target',value)
        replacement=target_payload(self.evidence('ui_design_artifact','Changed v2 content'),'v2')
        with self.assertRaisesMessage(DatabaseError,'cannot be rebound'),transaction.atomic():self.raw_source('ui_target',replacement)
        with self.assertRaises(DatabaseError),transaction.atomic():self.raw_source('ui_design',{})
        self.assertEqual(self.d.sources.filter(kind='ui_target').count(),1)

    def test_sql_requires_explicit_verified_exact_target_and_immutable_receipt_identity(self):
        self.inputs();target,payload=self.target();wrong=dict(payload,artifact_version='v1')
        source=self.approval(wrong,verify=False)
        with self.assertRaisesMessage(DatabaseError,'UI artifact target mismatch'),transaction.atomic():
            DeliverySourceVerification.objects.create(source=source,adapter='synthetic-sql-test',result=SyntheticDeliverySourceAdapter().read(source),actor=self.actor)
        approval=self.approval(payload,version='receipt-18',verify=False)
        result=SyntheticDeliverySourceAdapter().read(approval)
        malformed=[{k:v for k,v in result.items() if k!='ui_binding'},dict(result,payload_sha256='0'*64),dict(result,owner='PMO')]
        for value in malformed:
            with self.assertRaises(DatabaseError),transaction.atomic():
                DeliverySourceVerification.objects.create(source=approval,adapter='synthetic-sql-test',result=value,actor=self.actor)
        delivery.verify_source(self.actor,self.case.pk,approval.pk,rev(self.case))
        replacement=dict(approval.payload,approved_ui_target={k:wrong[k] for k in ['artifact_ref','artifact_version','artifact_sha256']})
        with self.assertRaisesMessage(DatabaseError,'cannot be rebound'),transaction.atomic():
            self.raw_source('ui_design',replacement,approval.evidence,approval.external_ref)
        self.assertEqual(approval.verifications.count(),1)

    def test_sql_currentness_guard_holds_forged_plan_and_consumers_after_successor(self):
        self.inputs(True,True);target,payload=self.target('v1');self.approval(payload);self.approval(payload,'ui_client','client-1')
        plan=self.decide();self.assertEqual(self.sql_current(plan),(True,True))
        missing=deepcopy(plan.snapshot);del missing['sources']['ui_client']
        with self.assertRaisesMessage(DatabaseError,'UI artifact prerequisite snapshot'),transaction.atomic():
            DeliveryRecord.objects.create(dossier=self.d,kind='planning_decision',data=plan.data,snapshot=missing,evidence=plan.evidence,actor=self.actor)
        target2,payload2=self.target('v2',verify=False)
        self.assertEqual(self.sql_current(plan),(False,False))
        with self.assertRaises(DatabaseError),transaction.atomic():
            DeliveryRecord.objects.create(dossier=self.d,kind='planning_decision',data=plan.data,snapshot=plan.snapshot,evidence=plan.evidence,actor=self.actor)
        for kind in ['kickoff','progress','glpi_request','release_ready']:
            with self.assertRaisesMessage(DatabaseError,'UI artifact planning prerequisite'),transaction.atomic():
                DeliveryRecord.objects.create(dossier=self.d,kind=kind,data={},snapshot={'planning_id':plan.pk},evidence=plan.evidence,actor=self.actor)
        delivery.verify_source(self.actor,self.case.pk,target2.pk,rev(self.case))
        self.approval(payload2,version='receipt-18');self.approval(payload2,'ui_client','client-2')
        successor=self.decide();self.assertEqual(self.sql_current(successor),(True,True))
        self.assertEqual(self.sql_current(plan),(False,False))
        with self.assertRaises(DatabaseError),transaction.atomic():
            DeliveryRecord.objects.create(dossier=self.d,kind='progress',data={},snapshot={'planning_id':plan.pk},evidence=plan.evidence,actor=self.actor)
        self.assertEqual(delivery.record_progress(self.actor,self.case.pk,self.d.pk,'progress',self.e['plan'].pk,'Current UI plan only',rev(self.case)).snapshot,{'planning_id':successor.pk})

    def test_sql_grants_unknown_applicability_unicode_and_non_ui_shape(self):
        self.inputs(False,False);non_ui=self.decide();self.assertEqual(self.sql_current(non_ui),(True,True))
        self.source('ui_applicability',{'requires_ui':True,'client_signoff_required':False})
        artifact=self.evidence('ui_design_artifact','Synthetic Unicode artifact')
        payload=target_payload(artifact,'版2','synthetic:设计/🌍')
        target=self.source('ui_target',payload,self.evidence('ui_target_statement'))
        self.approval(payload,version='决定-r17');plan=self.decide();self.assertEqual(self.sql_current(plan),(True,True))
        Grant.objects.filter(case=self.case,user=self.actor,action='delivery.verify').update(active=False)
        self.assertEqual(self.sql_current(plan),(False,False))
        Grant.objects.filter(case=self.case,user=self.actor,action='delivery.verify').update(active=True)
        Grant.objects.filter(case=self.case,user=self.actor,action='delivery.source').update(active=False)
        self.assertEqual(self.sql_current(plan),(False,False))

    def test_sql_incomplete_authorized_head_cannot_verify_or_fall_back_to_old_plan(self):
        self.inputs();target,payload=self.target('v1');self.approval(payload);plan=self.decide()
        pending=dict(payload,artifact_version='v2',artifact_sha256=None,artifact_evidence=None)
        source=self.raw_source('ui_target',pending,self.evidence('ui_target_statement','Current owner target is incomplete'))
        self.assertEqual(self.sql_current(plan),(False,False))
        with self.assertRaisesMessage(DatabaseError,'Current explicit UI source verification'),transaction.atomic():
            DeliverySourceVerification.objects.create(source=source,adapter='synthetic-sql-test',result=SyntheticDeliverySourceAdapter().read(source),actor=self.actor)
        with self.assertRaisesMessage(ValidationError,'incomplete'):delivery.approved_plan(self.d)
        complete,payload2=self.target('v2');self.approval(payload2,version='receipt-18')
        self.assertEqual(self.sql_current(self.decide()),(True,True))
