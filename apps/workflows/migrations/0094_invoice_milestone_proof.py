import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


GUARD = """
CREATE FUNCTION psl_invoice_milestone_proof_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'Invoice milestone proof is append-only';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM workflows_factorywork w
    JOIN workflows_humantask t ON t.id=NEW.task_id AND t.case_id=w.case_id
    JOIN finance_handoff h ON h.id=NEW.handoff_id AND h.case_id=w.case_id
    JOIN pmo_milestone m ON m.id=h.milestone_id AND m.case_id=w.case_id
    JOIN core_evidence completion ON completion.id=m.evidence_id AND completion.case_id=w.case_id
    JOIN agents_caseupload u ON u.id=NEW.upload_id AND u.case_id=w.case_id AND u.actor_id=NEW.actor_id
    JOIN core_evidence e ON e.id=NEW.evidence_id AND e.case_id=w.case_id AND e.created_by_id=NEW.actor_id
    WHERE w.id=NEW.work_id AND w.definition='pmo-finance/v1' AND w.status IN ('ready','waiting')
      AND NOT w.cancel_requested AND w.request->>'handoff'=h.id::text
      AND h.payload->>'milestone_id'=m.id::text AND h.payload->>'evidence_id'=completion.id::text
      AND h.payload->>'evidence_sha256'=completion.sha256 AND h.payload->>'name'=m.name
      AND t.kind='factory_information' AND t.status='open' AND t.claimed_by_id=NEW.actor_id
      AND t.context->>'work'=w.id::text AND t.context->>'resolver'=NEW.actor_id::text
      AND t.context->>'profile'=w.policy_id::text AND t.context->'missing' ? 'invoice_milestone_proof'
      AND u.size BETWEEN 1 AND 5242880 AND lower(u.name) LIKE '%.pdf'
      AND e.kind='invoice_milestone_proof' AND e.source='psl:invoice-milestone-proof/v1'
      AND e.body::jsonb=jsonb_build_object('task',t.id,'work',w.id,'handoff',h.id,'milestone',m.id,
          'upload',u.id,'sha256',u.sha256,'size',u.size,'previous',NEW.previous_id)
  ) THEN
    RAISE EXCEPTION 'Exact open claimed invoice information task and original milestone upload required';
  END IF;
  IF NEW.previous_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM workflows_invoicemilestoneproof p
    WHERE p.id=NEW.previous_id AND p.task_id=NEW.task_id AND p.work_id=NEW.work_id
      AND p.handoff_id=NEW.handoff_id AND p.actor_id=NEW.actor_id AND p.upload_id<>NEW.upload_id
  ) THEN
    RAISE EXCEPTION 'The successor must cite the exact previous proof and a different original file';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_invoice_milestone_proof_guard BEFORE INSERT OR UPDATE OR DELETE
ON workflows_invoicemilestoneproof FOR EACH ROW EXECUTE FUNCTION psl_invoice_milestone_proof_guard();
"""

REVERSE = """
DROP TRIGGER psl_invoice_milestone_proof_guard ON workflows_invoicemilestoneproof;
DROP FUNCTION psl_invoice_milestone_proof_guard();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('agents', '0013_upload_current_claim_guard'),
        ('workflows', '0093_weekly_report_draft'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceMilestoneProof',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation', models.UUIDField()),
                ('note', models.CharField(blank=True, max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('evidence', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('handoff', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.handoff')),
                ('previous', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT,
                                                 to='workflows.invoicemilestoneproof')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='workflows.humantask')),
                ('upload', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='agents.caseupload')),
                ('work', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='workflows.factorywork')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('task', 'operation'), name='invoice_proof_operation'),
                    models.UniqueConstraint(condition=models.Q(previous__isnull=True), fields=('task',),
                                            name='invoice_proof_root'),
                ],
                'indexes': [models.Index(fields=['work', '-id'], name='invoice_proof_work_head')],
            },
        ),
        migrations.RunSQL(GUARD, REVERSE),
    ]
