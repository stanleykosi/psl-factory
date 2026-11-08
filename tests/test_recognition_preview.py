"""Native PostgreSQL cases for candidate790; not runtime acceptance until executed."""
import json
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied, ValidationError
from apps.core.models import Audit, Case, Evidence
from apps.core.evidence_access import public_evidence, public_timeline
from apps.identity.models import Grant
from apps.finance import recognition as native, recognition_preview as preview
from apps.finance.recognition_models import RecognitionRecord
from .recognition_helpers import fixture
from .helpers import rev


class RecognitionPreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=fixture()

    def capture(self, key='private-key-sentinel', note='private-note-sentinel'):
        f=self.f
        return preview.capture(f['actor'],f['case'].pk,f['packet'].pk,key,
            f['evidence']['completion'].pk,note,rev(f['case']))

    def guard(self,row,actor=None):
        f=self.f
        return preview.guard(actor or f['actor'],f['case'],row.pk,row.sha256)

    def test_capture_is_private_not_attestation(self):
        row=self.capture();f=self.f
        self.assertEqual(row.kind,preview.KIND)
        self.assertFalse(public_evidence(Evidence.objects.all()).filter(pk=row.pk).exists())
        self.assertFalse(public_timeline(f['case']).filter(action=preview.ACTION).exists())
        self.assertFalse(RecognitionRecord.objects.exists())
        self.assertNotIn('private-note-sentinel',str(row))

    def test_guard_readonly_projection_and_native_parity(self):
        row=self.capture();f=self.f
        before=(Audit.objects.count(),Evidence.objects.count(),rev(f['case']))
        with patch.object(native,'record',side_effect=AssertionError('No command during observation')):
            packet,context,old=self.guard(row)
        self.assertEqual(packet.pk,f['packet'].pk);self.assertIsNone(old)
        self.assertNotIn('private-note-sentinel',json.dumps(context))
        self.assertNotIn('private-key-sentinel',json.dumps(context))
        self.assertFalse(context['business_approval']);self.assertFalse(context['separately_entered_intent_bound'])
        self.assertEqual(before,(Audit.objects.count(),Evidence.objects.count(),rev(f['case'])))
        record=native.record(f['actor'],f['case'].pk,packet.pk,'attest','private-key-sentinel',
            f['evidence']['completion'].pk,'private-note-sentinel',rev(f['case']))
        self.assertEqual(record.kind,'attest')

    def test_observer_denied_before_lookup(self):
        f=self.f;Grant.objects.filter(case=f['case'],user=f['actor'],action='recognition.read').update(active=False)
        with patch.object(Evidence.objects,'filter',side_effect=AssertionError('Lookup before grant')):
            with self.assertRaises(PermissionDenied):preview.get(f['actor'],f['case'],1,'0'*64)

    def test_wrong_hash_or_missing_input_rejected(self):
        row=self.capture();f=self.f
        for pk,sha in [(row.pk,'0'*64),(row.pk+999,row.sha256)]:
            with self.assertRaises(ValidationError):preview.get(f['actor'],f['case'],pk,sha)

    def test_proposed_principal_is_not_substituted(self):
        row=self.capture()
        with self.assertRaises(ValidationError):self.guard(row,self.f['finance'])

    def test_revoked_actor_cannot_preview_or_capture(self):
        row=self.capture();f=self.f
        Grant.objects.filter(case=f['case'],user=f['actor'],action='recognition.attest').update(active=False)
        with self.assertRaises(PermissionDenied):self.guard(row)
        with self.assertRaises(PermissionDenied):self.capture('another')

    def test_exact_recorded_replay_retained(self):
        row=self.capture();f=self.f
        old=native.record(f['actor'],f['case'].pk,f['packet'].pk,'attest','private-key-sentinel',
            f['evidence']['completion'].pk,'private-note-sentinel',rev(f['case']))
        self.assertEqual(self.guard(row)[2].pk,old.pk)
        self.assertEqual(RecognitionRecord.objects.count(),1)

    def test_changed_native_intent_not_replay(self):
        row=self.capture();f=self.f
        native.record(f['actor'],f['case'].pk,f['packet'].pk,'attest','private-key-sentinel',
            f['evidence']['completion'].pk,'different native note',rev(f['case']))
        with self.assertRaisesMessage(ValidationError,'Private attestation input is not currently usable'):self.guard(row)

    def test_native_failure_details_are_not_projected(self):
        row=self.capture()
        with patch.object(native,'guard_record',side_effect=ValidationError('private-note-sentinel')):
            with self.assertRaises(ValidationError) as raised:self.guard(row)
        self.assertNotIn('private-note-sentinel',str(raised.exception))

    def test_stale_revision_capture_has_no_effect(self):
        f=self.f;before=(Evidence.objects.count(),Audit.objects.count())
        with self.assertRaises(ValidationError):
            preview.capture(f['actor'],f['case'].pk,f['packet'].pk,'key',f['evidence']['completion'].pk,'note',rev(f['case'])+1)
        self.assertEqual(before,(Evidence.objects.count(),Audit.objects.count()))

    def test_capture_versions_are_append_only(self):
        first=self.capture();second=self.capture('second-key')
        self.assertEqual(second.version,first.version+1)
        with self.assertRaises(ValueError):first.save()
        self.assertFalse(RecognitionRecord.objects.exists())

    def test_unprovenanced_private_row_rejected(self):
        row=self.capture();f=self.f
        forged=Evidence.objects.create(case=f['case'],kind=preview.KIND,version=row.version+1,
            source=preview.SOURCE,body=row.body,sha256=row.sha256,created_by=f['actor'])
        with self.assertRaisesMessage(ValidationError,'Native private capture provenance required'):
            self.guard(forged)

    def test_choices_require_current_domain_read(self):
        row=self.capture();f=self.f
        self.assertTrue(preview.choices(f['actor'],f['case']).filter(pk=row.pk).exists())
        Grant.objects.filter(case=f['case'],user=f['actor'],action='recognition.read').update(active=False)
        with self.assertRaises(PermissionDenied):preview.choices(f['actor'],f['case'])

    def binding(self):
        from apps.policy import pilot
        from tests.test_pilot_preflight import selection
        from tests.test_document_guard import payload
        f=self.f;a,c=f['actor'],f['case'];row=self.capture()
        value=selection(a,c);value['operations']=['recognition.attest']
        value['participants']=[{'user_id':a.pk,'actions':['recognition.attest']}]
        contract=pilot.configure(a,c.pk,value)
        selected=payload(a,c,type('Subject',(),{'pk':1})())
        selected['guards']=[{'operation':'recognition.attest','user_id':a.pk,'arguments':{
            'expected_revision':rev(c),'recognition_input_id':row.pk,'recognition_input_sha256':row.sha256}}]
        return row,contract,selected

    def test_real_binding_form_and_agent_hide_private_input(self):
        from apps.policy import pilot, pilot_bindings
        from apps.policy.pilot_binding_views import BindingForm
        from apps.agents.pilot import investigate
        f=self.f;source,contract,value=self.binding()
        bound=pilot_bindings.configure(f['actor'],f['case'].pk,contract.pk,value)
        self.assertEqual(set(bound.payload['guards'][0]['arguments']),{'expected_revision','recognition_input_id','recognition_input_sha256'})
        form=BindingForm(f['actor'],contract)
        self.assertIn(source.pk,list(form.fields['recognition_input_id'].queryset.values_list('pk',flat=True)))
        self.assertEqual(form.fields['recognition_input_id'].label_from_instance(source),'#'+str(source.pk))
        observation=pilot.capture(f['actor'],f['case'].pk,contract.pk)
        agent=investigate(f['actor'],f['case'].pk,observation.pk)
        self.assertEqual(agent['effect_tools'],[])
        for text in ['private-note-sentinel','private-key-sentinel',source.body]:self.assertNotIn(text,str(agent))
        self.assertIn('unbound',str(agent));self.assertFalse(RecognitionRecord.objects.exists())
        Grant.objects.filter(case=f['case'],user=f['actor'],action='recognition.read').update(active=False)
        self.assertFalse(BindingForm(f['actor'],contract).fields['recognition_input_id'].queryset.exists())

    def invalid_bindings(self,value,foreign):
        from copy import deepcopy
        for key,item in [('note','private'),('recognition_input_id',None),('recognition_input_id',True),('recognition_input_id',1.5),('recognition_input_id',foreign),('recognition_input_sha256',None),('recognition_input_sha256','0'*64)]:
            invalid=deepcopy(value);invalid['guards'][0]['arguments'][key]=item;yield invalid
        invalid=deepcopy(value);del invalid['guards'][0]['arguments']['recognition_input_id'];yield invalid

    def test_closed_binding_schema_rejects_private_and_malformed_arguments(self):
        from apps.policy import pilot_bindings
        f=self.f;source,contract,value=self.binding()
        for invalid in self.invalid_bindings(value,source.pk+999):
            with self.assertRaises(ValidationError):pilot_bindings.configure(f['actor'],f['case'].pk,contract.pk,invalid)

    def test_sql_variant_rejects_malformed_foreign_or_wrong_kind(self):
        from django.db import transaction, DatabaseError
        from apps.policy.models import PilotBinding
        from apps.documents.contracts import digest
        from tests.helpers import setup_case
        from apps.core.services import add_evidence
        f=self.f;source,contract,value=self.binding();a,c=setup_case(username='foreign-recognition790')
        foreign=add_evidence(a,c.pk,preview.KIND,'Untrusted foreign input','synthetic:negative')
        invalids=list(self.invalid_bindings(value,foreign.pk))
        from copy import deepcopy
        invalid=deepcopy(value);invalid['guards'][0]['arguments'].update(recognition_input_id=f['decision'].pk,recognition_input_sha256=f['decision'].sha256);invalids.append(invalid)
        for invalid in invalids:
            with self.assertRaises(DatabaseError),transaction.atomic():
                PilotBinding.objects.create(contract=contract,actor=f['actor'],payload=invalid,sha256=digest(invalid))
        self.assertFalse(PilotBinding.objects.filter(contract=contract).exists())

    def test_recorded_replay_survives_supersession_but_new_intent_holds(self):
        from copy import deepcopy
        f=self.f;source=self.capture()
        record=native.record(f['actor'],f['case'].pk,f['packet'].pk,'attest','private-key-sentinel',
            f['evidence']['completion'].pk,'private-note-sentinel',rev(f['case']))
        native.prepare(f['actor'],f['case'].pk,f['packet'].reference,deepcopy(f['packet'].payload),
            f['evidence']['completion'].pk,rev(f['case']))
        self.assertEqual(self.guard(source)[2].pk,record.pk)
        with self.assertRaises(ValidationError):self.capture('new-intent')
        self.assertEqual(RecognitionRecord.objects.count(),1)

    def test_cross_tenant_input_rejected_with_domain_grants_on_both(self):
        from apps.core.services import add_evidence
        f=self.f;other=Case.objects.create(tenant='other790',title='Other synthetic case',kind='project',synthetic=True)
        Grant.objects.bulk_create([Grant(case=other,user=f['actor'],action=g.action) for g in Grant.objects.filter(case=f['case'],user=f['actor'])])
        foreign=add_evidence(f['actor'],other.pk,preview.KIND,'untrusted foreign data',preview.SOURCE)
        with self.assertRaises(ValidationError):self.guard(foreign)

    def test_closed_envelope_rejects_malformed_values_with_exact_provenance(self):
        import hashlib
        from copy import deepcopy
        from apps.core.services import event
        f=self.f;source=self.capture();original=json.loads(source.body)
        for index,(key,value) in enumerate([('note',None),('packet_id',True),('operation_key','invalid key'),('extra','private')],start=source.version+1):
            body=deepcopy(original);body[key]=value;raw=json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False)
            row=Evidence.objects.create(case=f['case'],kind=preview.KIND,source=preview.SOURCE,version=index,
                body=raw,sha256=hashlib.sha256(raw.encode()).hexdigest(),created_by=f['actor'])
            event(f['actor'],f['case'],preview.ACTION,evidence=row.pk,sha256=row.sha256)
            with self.assertRaisesMessage(ValidationError,'Malformed private proposed input'):self.guard(row)
