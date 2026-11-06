from django.core.exceptions import PermissionDenied
from django.test import TestCase
from apps.identity.models import Grant
from apps.workflows import application_recovery as d
from adapters.pilot_physical import read
from adapters.pilot_preflight import job
from tests.helpers import setup_case
from tests.test_application_recovery import RecoveryFixture


class PilotPhysicalTests(RecoveryFixture,TestCase):
    def test_pending_native_archive_never_becomes_restore_or_physical_acceptance(self):
        self.fixture();self.authorize();j=d.reserve(self.a,self.c.pk,self.plan.pk,'archive')
        result=job(self.a,self.c,'application',j.pk)
        self.assertFalse(result['receipt_verified']);self.assertFalse(result['recovery_evidence']['native_restore_verified'])
        self.assertFalse(result['replay_permitted']);j.refresh_from_db();self.assertEqual(j.attempts,0)
        self.assertEqual(j.status,'pending');self.assertNotIn(str(self.root),str(result))

    def test_current_whole_database_and_fresh_control_authority_precede_job_lookup(self):
        self.fixture();self.authorize();j=d.reserve(self.a,self.c.pk,self.plan.pk,'archive')
        setup_case(username='physical-foreign-private')
        for pk in [j.pk,999999999]:
            with self.assertRaises(PermissionDenied):read(self.a,self.c,'application',pk)
            with self.assertRaises(PermissionDenied):read(self.a,self.c,'cold',pk)
        self.assertTrue(self.c.evidence.exists())
