import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


FORWARD = """
CREATE FUNCTION psl_rfp_estimate_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM workflows_factorywork w
        JOIN pmo_rfpintake i ON i.id = NEW.intake_id
        JOIN pmo_rfpcase r ON r.id = i.rfp_id AND r.case_id = w.case_id
        JOIN agents_agentrun a ON a.id = NEW.draft_id AND a.case_id = w.case_id AND a.actor_id = NEW.actor_id
        JOIN core_evidence e ON e.id = NEW.evidence_id AND e.case_id = w.case_id AND e.kind = 'policy_decision'
        JOIN policy_configuration c ON c.id = NEW.configuration_id AND c.case_id = w.case_id
        WHERE w.id = NEW.work_id AND w.definition = 'rfp-response/v1' AND w.request->>'rfp' = r.id::text
          AND c.component = 'OPS.rfp_security_estimate_routes' AND a.provider = 'deterministic-security-request-v1'
          AND a.result->'scope' = NEW.payload->'scope' AND a.result->'scope'->>'work' = w.id::text
          AND a.result->'scope'->>'intake' = i.id::text
          AND (NEW.attachment_id IS NULL OR EXISTS (SELECT 1 FROM agents_caseupload u
                WHERE u.id = NEW.attachment_id AND u.case_id = w.case_id AND u.actor_id = NEW.actor_id
                  AND NEW.payload->'attachment'->>'sha256' = u.sha256))
    ) THEN RAISE EXCEPTION 'Security request must bind its exact bid, proof, route and permitted private file';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_estimate_scope BEFORE INSERT ON pmo_rfpestimaterequest
FOR EACH ROW EXECUTE FUNCTION psl_rfp_estimate_scope_guard();
"""
REVERSE = """
DROP TRIGGER psl_rfp_estimate_scope ON pmo_rfpestimaterequest;
DROP FUNCTION psl_rfp_estimate_scope_guard();
"""
TABLES = ('pmo_rfpestimaterequest', 'pmo_rfpestimatedispatch', 'pmo_rfpestimatemailbox', 'pmo_rfpestimatereceipt')


class Migration(migrations.Migration):
    dependencies = [
        ('pmo', '0073_archive_copy_lease_operation'),
        ('agents', '0013_upload_current_claim_guard'),
        ('workflows', '0089_handover_reply_provenance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(name='RFPEstimateRequest', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('payload', models.JSONField()), ('sha256', models.CharField(max_length=64)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('work', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='estimate_requests', to='workflows.factorywork')),
            ('intake', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pmo.rfpintake')),
            ('draft', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='agents.agentrun')),
            ('evidence', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
            ('configuration', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='policy.configuration')),
            ('attachment', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='agents.caseupload')),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='RFPEstimateDispatch', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('operation', models.UUIDField(default=uuid.uuid4, unique=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('request', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='dispatch', to='pmo.rfpestimaterequest')),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='RFPEstimateMailbox', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('reference', models.CharField(max_length=160)),
            ('payload', models.JSONField()), ('sha256', models.CharField(max_length=64)),
            ('dispatch', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='mailbox', to='pmo.rfpestimatedispatch')),
        ]),
        migrations.CreateModel(name='RFPEstimateReceipt', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('reference', models.CharField(max_length=160)), ('delivered', models.BooleanField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('dispatch', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='receipt', to='pmo.rfpestimatedispatch')),
            ('evidence', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.RunSQL(FORWARD, REVERSE),
        migrations.RunSQL(
            [f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()' for table in TABLES],
            [f'DROP TRIGGER psl_immutable ON {table}' for table in TABLES],
        ),
    ]
