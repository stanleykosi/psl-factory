"""Populated recovery assessment0027→0028; accepted798b inputs; native799 UNRUN."""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit

class SignatureImpactUpgradeTests(TransactionTestCase):
    def test_populated_recovery_impact_assessment_survives_upgrade(self):
        from scripts.impact799_upgrade import TARGET,PREVIOUS,upgrade
        from tests.recovery_impact798_helpers import fixture,policy
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN799_RUNTIME_CLEARANCE'),'coordinator-cleared-impact799')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT799_UPGRADE_EVIDENCE']);self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        # Existing dedicated798 native initial-adoption request fixture checks canonical
        # local adapters and excludes emergency, conversion and signature reaffirmation.
        f=fixture(username='impact799-old');new=policy(f)
        assessment=impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,['pmo.signed_adoption_recovery_requests'],f['e']['policy_decision'].pk,'Existing798 request impact')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['pmo.signed_adoption_recovery_requests']],[f['request'].pk])
        reviewer=get_user_model().objects.create_user(username='impact799-old-reviewer')
        Grant.objects.bulk_create([Grant(case=f['c'],user=reviewer,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        review=impact.review(reviewer,f['c'].pk,assessment.pk,'accept',f['e']['policy_decision'].pk,'Independent prior recovery metadata review')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.helpers import setup_case,prepared
        from tests.signature_helpers import packet_for,contract
        from apps.policy.signature_validators import COMPONENT
        from apps.policy.services import active_component
        from apps.pmo.models import CommercialSignatureUse,CommercialSignatureReaffirmation,RFPCase
        from django.apps import apps
        a,c=setup_case(username='impact799-new');e=prepared(a,c)
        packet=packet_for(a,c,e);old=active_component(COMPONENT,c)
        self.assertFalse(CommercialSignatureUse.objects.filter(packet__case=c).exists())
        self.assertFalse(CommercialSignatureReaffirmation.objects.filter(packet__case=c).exists())
        self.assertFalse(RFPCase.objects.filter(case=c).exists())
        contract(a,c,e['policy_decision']);new=active_component(COMPONENT,c)
        def effects():
            return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
                if m._meta.app_label in ('finance','pmo','core','documents','workflows','agents')}
        baseline=effects()
        row=impact.capture(a,c.pk,old.pk,new.pk,['pmo.signature_packets'],e['policy_decision'].pk,'Selected original packet policy metadata only')
        rows=row.observation['domains']['pmo.signature_packets'];self.assertEqual([r['id'] for r in rows],[packet.pk])
        self.assertFalse(rows[0]['packet_policy_valid_now'])
        for flag in ('signature_authenticity_verified','signing_authorized','effects_performed'):self.assertFalse(rows[0][flag])
        self.assertEqual(set(rows[0]),{'id','kind','metadata_only','domain_route','revision','policy','authority','packet_sha256','packet_policy_valid_now','state','signature_authenticity_verified','signing_authorized','effects_performed'})
        unchanged_except_capture_audit(baseline,effects(),actor=a.pk,case=c.pk,assessment=row.pk,previous=old.pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
