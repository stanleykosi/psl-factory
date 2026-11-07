"""Static contract checks; native workflow proofs are separate."""
from copy import deepcopy
from types import SimpleNamespace
from django.test import SimpleTestCase
from jsonschema import Draft202012Validator
from apps.policy.change_applicability_validators import VALUE, unresolved_draft
from apps.policy.registry import components


class ApplicabilityContractTests(SimpleTestCase):
    def valid(self, value):
        return not list(Draft202012Validator(VALUE).iter_errors(value))

    def draft(self):
        return unresolved_draft(SimpleNamespace(pk='11111111-1111-1111-1111-111111111111', synthetic=True))

    def entry(self, requirement=None):
        return {'authorization_id': 1, 'change_version_id': 2, 'requirement': requirement,
                'source': {'id': 3, 'version': 1, 'sha256': 'a'*64}, 'owner': None, 'rationale': 'Owner decision pending'}

    def test_unresolved_default_no_appointed_owner(self):
        self.assertEqual(self.draft()['entries'], [])
        self.assertTrue(self.valid(self.draft()))
        self.assertIsNone(components()['D11.change_go_live_client_applicability']['current_value'])
        self.assertEqual(components()['D11.change_go_live_client_applicability']['status'], 'UNCONFIGURED')

    def test_closed_requirement_variants(self):
        for requirement in [None, 'unresolved', 'required', 'not_applicable']:
            value = self.draft(); value['entries'] = [self.entry(requirement)]
            self.assertTrue(self.valid(value))
        for requirement in ['internal', 'Standard', 'Emergency', False, 'client_signed']:
            value['entries'][0]['requirement'] = requirement
            self.assertFalse(self.valid(value))

    def test_no_category_audience_or_baseline_waiver_fields(self):
        for key in ['client_facing', 'category', 'baseline_exemption_id', 'audience', 'client_signed', 'production_authorized']:
            value = self.draft(); value[key] = False
            self.assertFalse(self.valid(value))

    def test_pin_and_owner_are_closed_typed_objects(self):
        value = self.draft(); value['entries'] = [self.entry('not_applicable')]
        owner = {'actor_id': 4, 'role': 'PM', 'authority': {'D05.role_principal_assignments': 5}}
        value['entries'][0]['owner'] = owner
        self.assertTrue(self.valid(value))
        for bad in [{'role': 'Administrator'}, {'actor_id': '4'}, {'authority': {'claimed_title': 'Head of PMO'}}]:
            other = deepcopy(value); other['entries'][0]['owner'].update(bad)
            self.assertFalse(self.valid(other))

    def test_d11_baseline_schema_unchanged(self):
        self.assertEqual(components()['D11.client_signature_contract']['schema_ref'], 'schema:psl/policy-component/D11.client_signature_contract/v1')

    def test_changed_templates_compile(self):
        from django.template.loader import get_template
        for name in ['pmo/changes.html','pmo/change_applicability_panel.html','pmo/change_signature_fields.html','factory/change_detail.html']:
            self.assertIsNotNone(get_template(name))

    def test_not_applicable_declaration_never_accepts_client_signature(self):
        from django.core.exceptions import ValidationError
        from apps.pmo.change_applicability import validate_declaration, PROTOCOL
        from apps.pmo.change_signatures import PURPOSE
        from django.utils import timezone
        value={'protocol':PROTOCOL,'purpose':PURPOSE,'case_id':self.draft()['case_id'],
               'change':{},'authorization':{},'execution':[],'report':{},'attesting_actor_id':1,
               'applicability':{'policy_id':1,'revision':1,'entry':self.entry('not_applicable')},
               'signatures':{'PM':{'evidence':{'id':1,'version':1,'sha256':'a'*64},'source_system':'synthetic',
                'source_reference':'exact-report','decision_id':'pm-1','decision_version':'1','signer_reference':'synthetic-PM',
                'purpose':PURPOSE,'signed_at':timezone.now().isoformat()}}}
        self.assertEqual(set(validate_declaration(value)['signatures']),{'PM'})
        value['signatures']['Client']=deepcopy(value['signatures']['PM'])
        with self.assertRaises(ValidationError):validate_declaration(value)
