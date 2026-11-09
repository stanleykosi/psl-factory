from copy import deepcopy
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from apps.documents.contracts import validate_template, PMO_CLIENT_SECTIONS, digest
from apps.documents.controlled import create_version, preflight, request_review
from .document_helpers import publication_fixture, fields
from .helpers import rev


class ClientPMOTemplateTests(SimpleTestCase):
    def test_every_required_section_must_be_projectable_for_every_pmo_type(self):
        for kind in ['sow', 'status_report', 'minutes', 'project_artifact', 'rfp_response']:
            for missing in PMO_CLIENT_SECTIONS:
                with self.subTest(kind=kind, missing=missing):
                    definition = {'document_type': kind, 'required_fields': ['executive_summary'],
                                  'audience_fields': {'client': [key for key in PMO_CLIENT_SECTIONS if key != missing]}}
                    with self.assertRaises(ValidationError):
                        validate_template(definition)

    def test_support_case_keeps_its_existing_client_document_contract(self):
        from types import SimpleNamespace
        validate_template({'document_type': 'status_report', 'required_fields': ['executive_summary'],
                           'audience_fields': {'client': ['executive_summary']}}, case=SimpleNamespace(kind='support'))

    def test_internal_projection_is_not_forced_to_expose_client_sections(self):
        validate_template({'document_type': 'status_report', 'required_fields': ['executive_summary'],
                           'audience_fields': {'client': list(PMO_CLIENT_SECTIONS), 'internal': ['executive_summary', 'internal_notes']}})
        validate_template({'document_type': 'minutes', 'required_fields': ['status'],
                           'audience_fields': {'internal': ['status']}})
        validate_template({'document_type': 'finance_report', 'internal_review_required': False,
                           'required_fields': ['executive_summary', 'financial_metrics', 'bu_totals'],
                           'audience_fields': {'management': ['executive_summary', 'financial_metrics', 'bu_totals']}})


class ClientPMOProjectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, cls.owner, cls.source, cls.template, *_ = publication_fixture()

    def draft(self, value):
        return create_version(self.actor, self.case.pk, self.template.pk, 'Partial draft', 'client', value, rev(self.case))

    def test_missing_and_blank_sections_allow_draft_but_hold_review(self):
        for key in PMO_CLIENT_SECTIONS:
            for blank in [False, True]:
                with self.subTest(key=key, blank=blank):
                    value = fields(self.source)
                    if blank:
                        value[key]['text'] = '   '
                    else:
                        del value[key]
                    version = self.draft(value)
                    self.assertIn('Missing required section: ' + key, preflight(version))
                    with self.assertRaises(ValidationError):
                        request_review(self.actor, self.case.pk, version.pk, rev(self.case))

    def test_omitted_projection_is_rejected_even_with_matching_digest(self):
        version = self.draft(fields(self.source))
        self.assertEqual(preflight(version), [])
        original = deepcopy(version.payload)
        for key in PMO_CLIENT_SECTIONS:
            with self.subTest(key=key):
                version.payload = deepcopy(original)
                version.payload['sections'] = [s for s in version.payload['sections'] if s['heading'] != key]
                version.payload_sha256 = digest(version.payload)
                self.assertIn('Missing mandatory client PMO projection section: ' + key, preflight(version))

    def test_old_configurable_template_cannot_bypass_current_client_review(self):
        version = self.draft(fields(self.source))
        definition = deepcopy(version.template.definition)
        definition['audience_fields']['client'] = ['executive_summary', 'status']
        version.template.definition = definition  # In-memory historical projection, never mutate persisted history.
        self.assertTrue(any('mandatory client PMO projection' in finding for finding in preflight(version)))
