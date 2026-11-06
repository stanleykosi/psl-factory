"""Shared native publication preconditions, read-only selected guard and SQL boundaries."""
import json
from copy import deepcopy
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError
from django.test import TestCase,Client
from django.urls import reverse
from apps.core.models import Audit
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.documents import controlled,delivery
from apps.documents.models import Version,Publication,PublicationJob,PublicationReceipt
from apps.policy import pilot,pilot_bindings as bindings,pilot_binding_validators as validators
from apps.policy.models import PilotBinding
from apps.policy.services import transition
from adapters import pilot_guards,pilot_preflight,document_guard
from tests.helpers import rev,setup_case
from tests.document_helpers import publication_fixture,approved,drafted
from tests.test_pilot_preflight import selection


def fixture():
    a,c,e,source,template,recipient,recipients,storage=publication_fixture()
    v=approved(a,c,template,source)
    return a,c,e,source,template,v,storage


def guard(a,c,v):return {'operation':'document.publish','user_id':a.pk,'arguments':{'expected_revision':rev(c),'version_id':v.pk}}


def contract(a,c):
    p=selection(a,c);p['operations']=['document.publish'];return pilot.configure(a,c.pk,p)


def payload(a,c,v):
    example=json.loads((settings.BASE_DIR/'fixtures/pilot-bindings.json').read_text())
    technical=pilot_preflight.technical()
    return {'format':'psl.pilot-bindings/v1','guards':[guard(a,c,v)],'deployment':dict(example['deployment'],
        families=['publication'],expected={k:technical[k] for k in ['source_identity','schema_identity','database_identity']})}


class DocumentGuardTests(TestCase):
    def test_guard_is_read_only_and_actual_reservation_uses_exact_same_current_requirements(self):
        a,c,e,source,template,v,storage=fixture()
        before=(Publication.objects.count(),PublicationJob.objects.count(),Audit.objects.count(),rev(c))
        result=pilot_guards.check(a,c,guard(a,c,v));self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(before,(Publication.objects.count(),PublicationJob.objects.count(),Audit.objects.count(),rev(c)))
        self.assertEqual(result['head']['document']['version'],v.pk)
        for text in ['PRIVATE TRACE','Delivery is progressing.']:self.assertNotIn(text,json.dumps(result))
        p=controlled.reserve_publication(a,c.pk,v.pk,rev(c))
        self.assertTrue(set(p.policies.values())<=set(result['policy_pins']))
        result=pilot_guards.check(a,c,guard(a,c,v));self.assertEqual(result['state'],'HELD')
        self.assertEqual(result['head']['document']['publication'],p.pk)
        delivery.run_publication_once();result=pilot_guards.check(a,c,guard(a,c,v))
        self.assertEqual(result['head']['document']['receipt_state'],'verified_internal_receipt')
        self.assertEqual(Publication.objects.count(),1);self.assertEqual(PublicationJob.objects.get().attempts,1)
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_missing_policy_holds_only_publication_and_missing_actor_grant_cannot_be_replaced_by_observer(self):
        a,c,e,source,template,v,storage=fixture();transition(a,storage.pk,'revoked')
        result=pilot_guards.check(a,c,guard(a,c,v));self.assertEqual(result['state'],'HELD')
        self.assertTrue(any(f.get('component')==storage.component for f in result['findings']))
        self.assertTrue(add_evidence(a,c.pk,'document','Unrelated evidence capture remains available','synthetic:document-guard').pk)
        self.assertFalse(Publication.objects.exists())
        Grant.objects.filter(user=a,case=c,action='document.publish').update(active=False)
        self.assertEqual(pilot_guards.check(a,c,guard(a,c,v))['findings'],[{'code':'native_authority_denied'}])

    def test_observer_access_precedes_selected_version_lookup_and_current_heads_hold_old_versions(self):
        a,c,e,source,template,v,storage=fixture();new=drafted(a,c,template,source,v.document_id)
        result=pilot_guards.check(a,c,guard(a,c,v));self.assertEqual(result['state'],'HELD')
        self.assertEqual(result['head']['document']['current'],new.pk)
        Grant.objects.filter(user=a,case=c,action='document.read').update(active=False)
        for pk in [v.pk,999999999]:
            g=guard(a,c,v);g['arguments']['version_id']=pk
            with self.assertRaises(PermissionDenied):pilot_guards.check(a,c,g)
        self.assertFalse(Publication.objects.exists())

    def test_binding_ui_and_engineering_review_cannot_publish_and_source_drift_stales_pack(self):
        a,c,e,source,template,v,storage=fixture();selected=contract(a,c)
        b=get_user_model().objects.create_user(username='document-guard-reviewer')
        Grant.objects.bulk_create([Grant(user=b,case=c,action=k) for k in Grant.objects.filter(user=a,case=c).values_list('action',flat=True)])
        client=Client(enforce_csrf_checks=True);client.force_login(a);url=reverse('pilot_bindings',args=[c.pk,selected.pk])
        self.assertContains(client.get(url),'Exact controlled document version');self.assertEqual(client.post(url,{}).status_code,403)
        value=payload(a,c,v);d=value['deployment']
        response=client.post(url,dict(operation='document.publish',participant=a.pk,expected_revision=rev(c),version_id=v.pk,
            deployment_ref=d['ref'],revision=d['revision'],web_key_ref=d['web_key_ref'],worker_key_ref=d['worker_key_ref'],families=d['families'],freshness_seconds=d['freshness_seconds'],
            csrfmiddlewaretoken=client.cookies['csrftoken'].value,**d['expected']))
        self.assertEqual(response.status_code,302);binding=PilotBinding.objects.get()
        bindings.review(b,c.pk,binding.pk,'accept','Read-only engineering review, no publication approval')
        pack=pilot.capture(a,c.pk,selected.pk);self.assertTrue(pilot.inspect(a,c.pk,pack.pk)['current'])
        self.assertFalse(Publication.objects.exists());self.assertFalse(PublicationJob.objects.exists())
        controlled.reserve_publication(a,c.pk,v.pk,rev(c))
        self.assertFalse(pilot.inspect(a,c.pk,pack.pk)['current'])
        self.assertEqual(Publication.objects.count(),1)

    def test_closed_sql_contract_rejects_unknown_keys_foreign_subjects_nonintegers_and_unselected_people(self):
        a,c,e,source,template,v,storage=fixture();selected=contract(a,c);value=payload(a,c,v)
        binding=bindings.configure(a,c.pk,selected.pk,value)
        _,foreign=setup_case(username='foreign-document-guard')
        # A foreign source uses actual registered native document services.
        from tests.document_helpers import DEFINITION,fields
        from tests.helpers import roles
        other=get_user_model().objects.get(username='foreign-document-guard')
        proof=add_evidence(other,foreign.pk,'policy_decision','Synthetic foreign document policy','synthetic:document')
        src=add_evidence(other,foreign.pk,'completion','Delivery is progressing. Internal incident trace is private.','synthetic:document')
        t=controlled.register_template(other,foreign.pk,'Foreign report',DEFINITION,proof.pk,rev(foreign))
        fv=controlled.create_version(other,foreign.pk,t.pk,'Foreign report','client',fields(src),rev(foreign))
        for mutate in [lambda p:p['guards'][0].update(operation='arbitrary.effect'),
                       lambda p:p['guards'][0]['arguments'].update(extra_authority=True),
                       lambda p:p['guards'][0]['arguments'].update(version_id=fv.pk),
                       lambda p:p['guards'][0]['arguments'].update(version_id=float(v.pk)),
                       lambda p:p['guards'][0].update(user_id=other.pk)]:
            bad=deepcopy(value);mutate(bad)
            with self.assertRaises(ValidationError):validators.validate(selected,bad)
            values={f.name:getattr(binding,f.name) for f in binding._meta.fields if f.name not in ['id','created_at','contract','payload']}
            # The one-binding-per-contract constraint is avoided with a real successor selection.
            next_contract=pilot.configure(a,c.pk,dict(selected.payload),selected.pk)
            self.assertFalse(PilotBinding.objects.filter(contract=next_contract).exists())
            with self.assertRaisesMessage(DatabaseError,'PSL'),transaction.atomic():
                PilotBinding.objects.create(**values,contract=next_contract,payload=bad)
            # A valid payload succeeds against the same contract; no unrelated constraint
            # may masquerade as proof that the malformed payload was rejected.
            PilotBinding.objects.create(**values,contract=next_contract,payload=value)
            selected=next_contract

    def test_finance_bound_publication_observer_needs_native_finance_read_without_a_new_pmo_gate(self):
        from tests.finance_analysis_helpers import fixture as finance_fixture,pipeline
        from apps.finance import analysis,documents
        a,c,e,config,policies,source,template,recipient=finance_fixture(username='guard-finance-owner',recipient_username='guard-finance-reader')
        mapping,allocation,output=pipeline(a,c,source)
        analysis.review(a,c.pk,'output',output.pk,'Finance','approve',e['finance_review'].pk,'Explicit synthetic output review',rev(c))
        version=documents.draft_report(a,c.pk,output.pk,template.pk,'internal',rev(c))
        result=pilot_guards.check(a,c,guard(a,c,version));self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertNotIn('financial_metrics',json.dumps(result));self.assertFalse(Publication.objects.exists())
        reader=get_user_model().objects.create_user(username='guard-document-observer')
        for action in ['case.read','policy.read','pilot.read','document.read']:Grant.objects.create(user=reader,case=c,action=action)
        with self.assertRaises(PermissionDenied):pilot_guards.check(reader,c,guard(a,c,version))
        self.assertFalse(document_guard.choices(reader,c).exists())
        publication=controlled.reserve_publication(a,c.pk,version.pk,rev(c))
        self.assertIsNone(publication.review_id)
        self.assertEqual(publication.version_id,version.pk)
