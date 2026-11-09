"""Populated799 packet assessment0028→0029; pending accepted799, no runtime clearance."""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit

class EmergencyImpactUpgradeTests(TransactionTestCase):
    def test_populated_signature_impact_assessment_survives_upgrade(self):
        from scripts.impact800_upgrade import TARGET,PREVIOUS,upgrade
        from tests.helpers import setup_case,prepared
        from tests.signature_helpers import packet_for,contract
        from apps.policy.signature_validators import COMPONENT
        from apps.policy.services import active_component
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN800_RUNTIME_CLEARANCE'),'coordinator-cleared-impact800')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT800_UPGRADE_EVIDENCE']);self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        a,c=setup_case(username='impact800-old');e=prepared(a,c);packet=packet_for(a,c,e)
        old=active_component(COMPONENT,c);contract(a,c,e['policy_decision']);new=active_component(COMPONENT,c)
        assessment=impact.capture(a,c.pk,old.pk,new.pk,['pmo.signature_packets'],e['policy_decision'].pk,'Existing799 packet metadata')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['pmo.signature_packets']],[packet.pk])
        reviewer=get_user_model().objects.create_user(username='impact800-old-reviewer')
        Grant.objects.bulk_create([Grant(case=c,user=reviewer,action=g.action) for g in Grant.objects.filter(case=c,user=a)])
        review=impact.review(reviewer,c.pk,assessment.pk,'accept',e['policy_decision'].pk,'Independent prior packet review')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.emergency_impact800_helpers import fixture,policy
        from django.apps import apps
        f=fixture(username='impact800-new');new=policy(f)
        def effects():return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('finance','pmo','core','documents','workflows','agents')}
        # Native original chronology/gates/signatures are setup, not projection effects.
        baseline=effects()
        row=impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,['pmo.emergency_recovery_requests'],f['e']['policy_decision'].pk,'Request snapshot only')
        rows=row.observation['domains']['pmo.emergency_recovery_requests'];self.assertEqual([r['id'] for r in rows],[f['request'].pk])
        self.assertFalse(rows[0]['request_snapshot_current'])
        for flag in ('authority_recovered','approval_granted','effects_performed'):self.assertFalse(rows[0][flag])
        self.assertEqual(set(rows[0]),{'id','kind','metadata_only','domain_route','outcome','snapshot_sha256','request_snapshot_current','state','authority_recovered','approval_granted','effects_performed'})
        unchanged_except_capture_audit(baseline,effects(),actor=f['a'].pk,case=f['c'].pk,assessment=row.pk,previous=f['policy'].pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
