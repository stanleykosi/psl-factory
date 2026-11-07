"""Synthetic explicit owner decisions only. No operational defaults or appointments."""
from copy import deepcopy
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, transaction, connection
from django.test import TestCase
from apps.policy.change_applicability_validators import COMPONENT, SCHEMA
from apps.policy.services import decision_authority, transition
from apps.pmo.go_live_attestations import pin
from apps.pmo.change_execution import close_change, execution_manifest
from apps.pmo.change_applicability import PROTOCOL, owner_requirement, record_successor
from apps.pmo.change_signatures import current_closure
from apps.pmo.models import ChangeClosure, ChangeClosureApplicability
from apps.core.services import add_evidence
from .helpers import rev
from .document_helpers import artifact
from .test_change_closure_signatures import ChangeClosureSignatureTests


class ChangeApplicabilityTests(TestCase):
    setUp = ChangeClosureSignatureTests.setUp
    assessments = ChangeClosureSignatureTests.assessments
    authorized = ChangeClosureSignatureTests.authorized
    ready = ChangeClosureSignatureTests.ready
    change_template = ChangeClosureSignatureTests.change_template
    publish_change = ChangeClosureSignatureTests.publish_change
    prepared = ChangeClosureSignatureTests.prepared
    close_prepared = ChangeClosureSignatureTests.close_prepared

    def configure(self, auth, requirement='not_applicable'):
        source = add_evidence(self.actor,self.case.pk,'policy_decision','Synthetic exact change applicability decision','synthetic:applicability-owner')
        entry = {'authorization_id':auth.pk,'change_version_id':auth.version_id,'requirement':requirement,
            'source':pin(source),'owner':None if requirement in [None,'unresolved'] else {
                'actor_id':self.actor.pk,'role':'PM','authority':decision_authority(self.actor,self.case,'PM')},
            'rationale':'Explicit synthetic decision, not an operational choice'}
        value = {'protocol':'change-go-live-client-applicability/v1','case_id':str(self.case.pk),
                 'entries':[entry],'allow_synthetic':True}
        artifact(self.actor,self.case,COMPONENT,SCHEMA,value,source)
        from apps.policy.services import active_component
        return active_component(COMPONENT,self.case), entry

    def explicit(self, items, requirement='not_applicable'):
        policy, entry = self.configure(items[0],requirement)
        declaration = deepcopy(items[-1]); declaration['protocol']=PROTOCOL
        declaration['applicability']={'policy_id':policy.pk,'revision':policy.revision,'entry':entry}
        if requirement == 'not_applicable': del declaration['signatures']['Client']
        return policy, declaration

    def close_explicit(self, items, declaration, key='applicability-1'):
        auth, receipt, pm, client, _ = items
        client_id=client.pk if declaration['applicability']['entry']['requirement']=='required' else None
        return close_change(self.actor,self.case.pk,auth.pk,receipt.pk,pm.pk,client_id,'Actual exact applicability evidence',rev(self.case),attestation=declaration,operation_key=key)

    def test_missing_policy_holds_unsigned_but_existing_signed_path_survives(self):
        items=self.prepared();auth,receipt,pm,client,value=items
        with self.assertRaises(ValidationError):
            close_change(self.actor,self.case.pk,auth.pk,receipt.pk,pm.pk,None,'No guessed client',rev(self.case),attestation=value)
        self.assertFalse(ChangeClosure.objects.exists())
        self.assertEqual(current_closure(self.close_prepared(items)).client_signature_id,client.pk)

    def test_null_and_unresolved_do_not_authorize_unsigned(self):
        items=self.prepared()
        for requirement in [None,'unresolved']:
            self.configure(items[0],requirement)
            with self.assertRaises(ValidationError):owner_requirement(items[0])
        self.assertFalse(ChangeClosure.objects.exists())

    def test_explicit_not_applicable_records_no_client_signature(self):
        items=self.prepared();policy,value=self.explicit(items)
        closure=self.close_explicit(items,value);row=current_closure(closure)
        self.assertIsNone(closure.client_signature_id);self.assertIsNone(row.client_signature_id)
        self.assertEqual(set(row.declaration['signatures']),{'PM'})
        self.assertEqual(row.requirement,'not_applicable');self.assertEqual(row.policy_id,policy.pk)
        self.assertFalse(items[0].signature_bindings.exists())

    def test_required_explicit_retains_shared_envelope_compatibility(self):
        items=self.prepared();_,value=self.explicit(items,'required')
        for key in ['source_system','source_reference','decision_id','decision_version']:
            value['signatures']['Client'][key]=value['signatures']['PM'][key]
        closure=self.close_explicit(items,value)
        self.assertEqual(current_closure(closure).client_signature_id,items[3].pk)

    def test_wrong_change_execution_artifact_receipt_source_pins_hold(self):
        items=self.prepared();_,value=self.explicit(items)
        variants=[]
        for field in ['change','authorization','execution','report']:
            bad=deepcopy(value);bad[field]={};variants.append(bad)
        bad=deepcopy(value);bad['applicability']['entry']['source']['sha256']='0'*64;variants.append(bad)
        for bad in variants:
            with self.assertRaises(ValidationError):self.close_explicit(items,bad)
        self.assertFalse(ChangeClosure.objects.exists());self.assertFalse(ChangeClosureApplicability.objects.exists())

    def test_no_fake_client_signature_in_not_applicable(self):
        items=self.prepared();_,value=self.explicit(items)
        value['signatures']['Client']=items[-1]['signatures']['Client']
        with self.assertRaises(ValidationError):self.close_explicit(items,value)
        self.assertFalse(ChangeClosure.objects.exists())

    def test_revoked_policy_holds_current_assurance_retains_history(self):
        items=self.prepared();policy,value=self.explicit(items)
        closure=self.close_explicit(items,value);row=current_closure(closure)
        transition(self.actor,policy.pk,'revoked')
        with self.assertRaises(ValidationError):current_closure(closure)
        self.assertEqual(ChangeClosureApplicability.objects.get(pk=row.pk).declaration,value)
        self.assertEqual(ChangeClosure.objects.get(pk=closure.pk).receipt_id,items[1].pk)

    def test_owner_grant_revocation_holds_without_rewriting(self):
        from apps.identity.models import Grant
        items=self.prepared();_,value=self.explicit(items);closure=self.close_explicit(items,value)
        Grant.objects.filter(case=self.case,user=self.actor,action='case.read').update(active=False)
        with self.assertRaises((ValidationError,PermissionDenied)):current_closure(closure)
        self.assertEqual(ChangeClosureApplicability.objects.count(),1)

    def test_owner_is_not_required_to_be_configuration_operator(self):
        from apps.identity.models import Grant
        items=self.prepared();_,value=self.explicit(items)
        Grant.objects.filter(case=self.case,user=self.actor,action='policy.activate').update(active=False)
        closure=self.close_explicit(items,value)
        self.assertEqual(current_closure(closure).requirement,'not_applicable')
        self.assertIsNone(closure.client_signature_id)

    def test_required_to_not_applicable_and_back_preserves_original_closure(self):
        items=self.prepared();closure=self.close_prepared(items);original=deepcopy(closure.__dict__)
        _,value=self.explicit(items)
        first=record_successor(self.actor,self.case.pk,closure.pk,None,value,'Owner applicability correction','successor-1',rev(self.case))
        self.assertIsNone(current_closure(closure).client_signature_id)
        _,required=self.explicit(items,'required')
        second=record_successor(self.actor,self.case.pk,closure.pk,items[3].pk,required,'Owner requires actual Client acceptance','successor-2',rev(self.case),first.pk)
        self.assertEqual(current_closure(closure),second);closure.refresh_from_db()
        for key in ['receipt_id','pm_signature_id','client_signature_id','execution_ids','created_at']:
            self.assertEqual(getattr(closure,key),original[key])
        self.assertEqual(first.declaration,value);self.assertIsNotNone(first.legacy_binding_id)

    def test_not_applicable_to_required_retains_null_original_fact(self):
        items=self.prepared();_,value=self.explicit(items);closure=self.close_explicit(items,value);first=current_closure(closure)
        _,required=self.explicit(items,'required')
        row=record_successor(self.actor,self.case.pk,closure.pk,items[3].pk,required,'Actual Client signature now required','required-successor',rev(self.case),first.pk)
        self.assertEqual(current_closure(closure),row);closure.refresh_from_db()
        self.assertIsNone(closure.client_signature_id);self.assertEqual(row.client_signature_id,items[3].pk)

    def test_raw_sql_null_closure_bypass_rejected(self):
        auth,receipt,pm,client,_=self.prepared()
        with self.assertRaises(DatabaseError),transaction.atomic():
            ChangeClosure.objects.create(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=None,
                execution_ids=execution_manifest(auth),note='Unsigned bypass',actor=self.actor)
        self.assertFalse(ChangeClosure.objects.exists())

    def test_raw_sql_untyped_assurance_and_history_mutation_rejected(self):
        items=self.prepared();policy,value=self.explicit(items)
        with self.assertRaises(DatabaseError),transaction.atomic():
            ChangeClosureApplicability.objects.create(authorization=items[0],receipt=items[1],pm_signature=items[2],client_signature=None,
                requirement='not_applicable',policy=policy,execution_ids=execution_manifest(items[0]),declaration={},
                authority=decision_authority(self.actor,self.case,'PM'),operation_key='raw',note='Bypass',actor=self.actor)
        closure=self.close_explicit(items,value);row=current_closure(closure)
        with self.assertRaises(DatabaseError),transaction.atomic(),connection.cursor() as cursor:
            cursor.execute('UPDATE pmo_changeclosureapplicability SET requirement=%s WHERE id=%s',['required',row.pk])
        with self.assertRaises(DatabaseError),transaction.atomic(),connection.cursor() as cursor:
            cursor.execute('DELETE FROM pmo_changeclosureapplicability WHERE id=%s',[row.pk])

    def test_exact_replay_returns_original_without_duplicate_history(self):
        items=self.prepared();_,value=self.explicit(items);closure=self.close_explicit(items,value)
        before=ChangeClosureApplicability.objects.count()
        self.assertEqual(self.close_explicit(items,value).pk,closure.pk)
        self.assertEqual(ChangeClosureApplicability.objects.count(),before)
        changed=deepcopy(value);changed['signatures']['PM']['decision_version']='2'
        with self.assertRaises(ValidationError):self.close_explicit(items,changed)

    def test_stale_predecessor_cannot_rewrite_history(self):
        items=self.prepared();_,value=self.explicit(items);closure=self.close_explicit(items,value)
        _,required=self.explicit(items,'required')
        with self.assertRaises(ValidationError):
            record_successor(self.actor,self.case.pk,closure.pk,items[3].pk,required,'Missing predecessor','bad-predecessor',rev(self.case))
        self.assertEqual(ChangeClosureApplicability.objects.count(),1)

    second_prepared = ChangeClosureSignatureTests.second_prepared

    def test_multi_target_policy_keeps_unrelated_exact_changes_selectable(self):
        first=self.prepared();_,entry1=self.configure(first[0])
        second=self.second_prepared();_,entry2=self.configure(second[0],'required')
        source=self.e['policy_decision']
        value={'protocol':'change-go-live-client-applicability/v1','case_id':str(self.case.pk),
               'entries':[entry1,entry2],'allow_synthetic':True}
        policy=artifact(self.actor,self.case,COMPONENT,SCHEMA,value,source)
        self.assertEqual(owner_requirement(first[0]),(policy,entry1))
        self.assertEqual(owner_requirement(second[0]),(policy,entry2))

    def test_foreign_and_private_source_cannot_be_policy_evidence(self):
        from .helpers import setup_case
        items=self.prepared();_,entry=self.configure(items[0])
        other_actor,other=setup_case(username='foreign-applicability')
        foreign=add_evidence(other_actor,other.pk,'policy_decision','Other case owner source','synthetic:foreign')
        private=add_evidence(self.actor,self.case.pk,'agent_private_owner_guess','Untrusted model guess','synthetic:private')
        for source in [foreign,private]:
            bad=deepcopy(entry);bad['source']=pin(source)
            value={'protocol':'change-go-live-client-applicability/v1','case_id':str(self.case.pk),'entries':[bad],'allow_synthetic':True}
            with self.assertRaises(ValidationError):artifact(self.actor,self.case,COMPONENT,SCHEMA,value,self.e['policy_decision'])

    def test_no_additional_business_approval_or_finance_effect(self):
        from apps.pmo.models import ChangeDecision
        items=self.prepared();before=list(ChangeDecision.objects.values())
        _,value=self.explicit(items);closure=self.close_explicit(items,value)
        self.assertEqual(list(ChangeDecision.objects.values()),before)
        self.assertEqual(closure.authorization_id,items[0].pk)
        self.assertNotIn('deployment_authorized',current_closure(closure).declaration)
        self.assertNotIn('debt_waiver',current_closure(closure).declaration)

    def test_expired_policy_and_changed_owner_authority_hold(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.policy.services import save_draft, active_component
        from .helpers import activate
        items=self.prepared();policy,value=self.explicit(items);closure=self.close_explicit(items,value)
        expired=deepcopy(policy.envelope)
        expired['effective_until']=(timezone.now()-timedelta(seconds=1)).isoformat()
        successor=save_draft(self.actor,self.case.pk,expired)
        transition(self.actor,successor.pk,'validated');transition(self.actor,successor.pk,'active')
        with self.assertRaises(ValidationError):current_closure(closure)
        _,value2=self.explicit(items)
        row=record_successor(self.actor,self.case.pk,closure.pk,None,value2,'Current owner replacement','new-policy',rev(self.case),closure.authorization.applicability_records.last().pk)
        authority=active_component('D05.role_principal_assignments',self.case)
        activate(self.actor,self.case,'D05.role_principal_assignments',authority.envelope['value'],self.e['policy_decision'])
        with self.assertRaises(ValidationError):current_closure(closure)
        self.assertEqual(ChangeClosureApplicability.objects.get(pk=row.pk).declaration,value2)

    def test_successor_cannot_invent_later_original_pm_signing_time(self):
        from django.utils import timezone
        items=self.prepared();closure=self.close_prepared(items);_,value=self.explicit(items)
        value['signatures']['PM']['signed_at']=timezone.now().isoformat()
        with self.assertRaises(ValidationError):
            record_successor(self.actor,self.case.pk,closure.pk,None,value,'Attempt changed original signing time','later-pm',rev(self.case))
        self.assertFalse(ChangeClosureApplicability.objects.exists())


from django.test import TransactionTestCase


class ChangeApplicabilityRaceTests(TransactionTestCase):
    setUp = ChangeApplicabilityTests.setUp
    assessments = ChangeApplicabilityTests.assessments
    authorized = ChangeApplicabilityTests.authorized
    ready = ChangeApplicabilityTests.ready
    change_template = ChangeApplicabilityTests.change_template
    publish_change = ChangeApplicabilityTests.publish_change
    prepared = ChangeApplicabilityTests.prepared
    configure = ChangeApplicabilityTests.configure
    explicit = ChangeApplicabilityTests.explicit

    def test_two_connections_cannot_create_two_initial_assurances(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        items=self.prepared();policy,value=self.explicit(items)
        authority=decision_authority(self.actor,self.case,'PM');ids=execution_manifest(items[0]);barrier=Barrier(2)
        def insert(key):
            close_old_connections()
            try:
                with transaction.atomic():
                    barrier.wait(timeout=15)
                    ChangeClosureApplicability.objects.create(authorization=items[0],receipt=items[1],pm_signature=items[2],
                        client_signature=None,requirement='not_applicable',policy=policy,execution_ids=ids,
                        declaration=value,authority=authority,operation_key=key,note='Synthetic concurrent exact decision',actor=self.actor)
                return 'inserted'
            except DatabaseError:
                return 'rejected'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(insert,['race-one','race-two']))
        self.assertCountEqual(results,['inserted','rejected'])
        self.assertEqual(ChangeClosureApplicability.objects.count(),1)
        self.assertFalse(ChangeClosure.objects.exists())

    def test_repeatable_read_assurance_insertion_fails_closed(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        items=self.prepared();policy,value=self.explicit(items)
        authority=decision_authority(self.actor,self.case,'PM');ids=execution_manifest(items[0])
        def insert():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                    ChangeClosureApplicability.objects.create(authorization=items[0],receipt=items[1],pm_signature=items[2],
                        client_signature=None,requirement='not_applicable',policy=policy,execution_ids=ids,
                        declaration=value,authority=authority,operation_key='repeatable-read',note='Synthetic isolation check',actor=self.actor)
                return 'inserted'
            except DatabaseError as exc:
                self.assertIn('READ COMMITTED',str(exc));return 'rejected'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:result=pool.submit(insert).result(timeout=30)
        self.assertEqual(result,'rejected');self.assertFalse(ChangeClosureApplicability.objects.exists())

    # Kept on the transactional class to exercise real commit timestamps, not a clock mock.
    def test_new_actual_client_signature_after_original_unsigned_closure(self):
        from django.utils import timezone
        items=self.prepared();_,value=self.explicit(items)
        closure=ChangeApplicabilityTests.close_explicit(self,items,value)
        first=current_closure(closure)
        new_client=add_evidence(self.actor,self.case.pk,'signature','Genuinely new synthetic Client acceptance after unsigned closure','synthetic:new-client-acceptance')
        _,required=self.explicit(items,'required')
        required['signatures']['Client'].update(evidence=pin(new_client),decision_id='new-client-decision-'+str(new_client.pk),signed_at=timezone.now().isoformat())
        row=record_successor(self.actor,self.case.pk,closure.pk,new_client.pk,required,'New actual Client acceptance, not metadata backdating','new-client-later',rev(self.case),first.pk)
        closure.refresh_from_db()
        self.assertIsNone(closure.client_signature_id)
        self.assertEqual(current_closure(closure).client_signature_id,new_client.pk)
        from apps.pmo.go_live_attestations import instant
        self.assertGreater(instant(row.declaration['signatures']['Client']['signed_at']),closure.created_at)
        self.assertEqual(row.declaration['signatures']['PM'],first.declaration['signatures']['PM'])
        self.assertEqual(first.requirement,'not_applicable')


from . import test_factory_change as factory_tests


class FactoryApplicabilityTests(TestCase):
    setUp = factory_tests.FactoryChangeTests.setUp
    assessments = factory_tests.FactoryChangeTests.assessments
    authorized = factory_tests.FactoryChangeTests.authorized
    ready = factory_tests.FactoryChangeTests.ready
    change_template = factory_tests.FactoryChangeTests.change_template
    start = factory_tests.FactoryChangeTests.start
    advance = factory_tests.FactoryChangeTests.advance
    review = factory_tests.FactoryChangeTests.review
    configure = ChangeApplicabilityTests.configure

    def test_factory_verifies_exact_not_applicable_without_client_signed_claim(self):
        import json
        from django.utils import timezone
        from django.urls import reverse
        from apps.documents.models import PublicationReceipt
        from apps.workflows import factory_change as change
        from apps.workflows.models import FactoryWork
        from apps.pmo.models import ChangeDecision
        from apps.pmo.change_applicability import declaration_draft
        auth=self.authorized();self.start(auth);self.advance();self.review('notice');self.advance()
        self.ready(auth);self.advance();self.review('go_live');self.advance()
        receipt=PublicationReceipt.objects.get(publication__version=change.document(self.work,'go_live'))
        policy,_=self.configure(auth)
        pm=add_evidence(self.actor,self.case.pk,'signature','Actual synthetic PM acceptance of exact factory artifact','synthetic:factory-pm')
        declaration=json.loads(declaration_draft(auth,receipt,self.actor))
        declaration['signatures']['PM']={'evidence':pin(pm),'source_system':'synthetic-owner-register',
            'source_reference':'exact-factory-report-'+str(receipt.publication.version_id),'decision_id':'pm-'+str(pm.pk),
            'decision_version':'1','signer_reference':'synthetic-PM','purpose':'change_go_live_acceptance',
            'signed_at':timezone.now().isoformat()}
        decisions=list(ChangeDecision.objects.values());self.work.refresh_from_db()
        closure=change.close(self.actor,self.work.pk,self.work.revision,rev(self.case),receipt.pk,pm.pk,None,
            'Exact PM acceptance and owner applicability, not Client signature',attestation=declaration,operation_key='factory-applicability')
        with self.assertRaises(DatabaseError),transaction.atomic():
            FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        result=change.verify(self.work)
        self.assertFalse(result['client_signed']);self.assertFalse(result['original_closure_client_signed'])
        self.assertIsNone(result['current_client_signature_id']);self.assertFalse(result['deployment_authorized'])
        self.assertEqual(result['client_signature_requirement'],'not_applicable')
        self.assertEqual(list(ChangeDecision.objects.values()),decisions)
        self.assertEqual(len(result['receipt_ids']),2);self.assertIsNone(closure.client_signature_id)
        self.client.force_login(self.actor)
        page=self.client.get(reverse('factory_detail',args=[self.work.pk]))
        self.assertContains(page,'Inspect the recorded owner applicability')
        transition(self.actor,policy.pk,'revoked')
        with self.assertRaises(ValidationError):change.verify(self.work)
        self.assertEqual(PublicationReceipt.objects.get(pk=receipt.pk).payload_sha256,receipt.payload_sha256)

    def test_shared_identity_guard_keeps_accepted_finance_workbook_clauses(self):
        from importlib import import_module
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_get_functiondef('psl_factory_identity()'::regprocedure)")
            definition=cursor.fetchone()[0]
        finance=import_module('apps.finance.migrations.0073_workbook_reference')
        self.assertEqual(definition.count(finance.NEW),2)
        self.assertNotIn(finance.OLD,definition)
        self.assertIn('cc.execution_ids=b.execution_ids AND psl_change_assurance_claim(cc,a.result)',definition)
        self.assertNotIn('cc.execution_ids=b.execution_ids AND cc.pm_signature_id<>cc.client_signature_id',definition)
