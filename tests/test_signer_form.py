from django.test import SimpleTestCase

from apps.workflows.factory_go_live_views import SignerForm


class SignerFormTests(SimpleTestCase):
    def test_actual_signing_seconds_survive_form_validation_and_browser_constraints(self):
        form = SignerForm({
            'source_system': 'Sample signature register',
            'source_reference': 'Sample source',
            'decision_id': 'Sample decision',
            'decision_version': '1',
            'signer_reference': 'Sample signer',
            'signed_at': '2026-11-18T06:05:26',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['signed_at'].second, 26)
        self.assertIn('step="1"', str(form['signed_at']))
