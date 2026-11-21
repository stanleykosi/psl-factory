from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Evidence
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.pmo.delivery_ui import MissingDesignSignoff
from apps.pmo.models import DeliveryDossier
from apps.workflows.models import FactoryWork
from tests import railway_design_signoff_hold_seed as seed
from tests.helpers import rev


class DesignSignoffHoldFixtureTests(TestCase):
    def test_exact_ui_signoff_hold_preserves_original_inputs_and_links_scoped_setup(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user(seed.TRIAL)
        data = seed.prepare()
        self.assertEqual(seed.prepare(), {**data, 'preserved': True})
        work = FactoryWork.objects.get(pk=data['work'])
        dossier = DeliveryDossier.objects.get(pk=data['dossier'])
        inputs = {e.pk: e.sha256 for e in Evidence.objects.filter(pk__in=(data['requirements'], data['estimate']))}
        self.assertEqual(len(inputs), 2)
        self.assertEqual((work.actor_id, work.policy_id, work.status), (trial.pk, data['profile'], 'waiting'))
        author = get_user_model().objects.get(username=seed.AUTHOR)
        with self.assertRaises(MissingDesignSignoff):
            delivery.decide_planning(author, dossier.case_id, dossier.pk, 'approve', dossier.evidence_id,
                                     'Exact sample Planning exit', rev(dossier.case))

        self.client.force_login(trial)
        detail = self.client.get(data['path'])
        self.assertContains(detail, 'Design sign-off needed')
        self.assertContains(detail, 'Setup needed')
        self.assertContains(detail, f'<dt>Requirements</dt><dd>Recorded · revision {data["requirements_version"]}</dd>', html=True)
        self.assertContains(detail, f'<dt>Engineering estimate</dt><dd>Recorded · revision {data["estimate_version"]}</dd>', html=True)
        self.assertContains(detail, 'SAMPLE Planning Lead')
        self.assertContains(detail, f'href="{data["setup"]}"')
        self.assertNotContains(detail, 'Approve exact Planning exit')
        self.assertNotContains(detail, 'Release readiness record')
        setup = self.client.get(data['setup'].split('#')[0])
        self.assertContains(setup, 'id="ui-design-signoff"')
        self.assertContains(setup, '<strong>Design Lead source route</strong> · Setting needed', html=True)
        self.assertContains(setup, seed.TITLE)
        self.assertFalse(dossier.records.exists())
        self.assertFalse(dossier.sources.filter(kind='ui_design').exists())

        Grant.objects.filter(user=trial, case=dossier.case, action='planning.read').update(active=False)
        delivered_only = self.client.get(data['path'])
        self.assertContains(delivered_only, 'Design sign-off needed')
        self.assertContains(delivered_only, 'Current estimate reference unavailable')
        self.assertContains(delivered_only, f'href="{data["setup"]}"')
        Grant.objects.filter(user=trial, case=dossier.case, action='policy.read').update(active=False)
        self.assertNotContains(self.client.get(data['path']), 'Open Setup')
        self.assertEqual(self.client.get(data['setup'].split('#')[0]).status_code, 403)
        self.assertEqual(inputs, {e.pk: e.sha256 for e in Evidence.objects.filter(pk__in=inputs)})
