from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


GUARDS = """
CREATE FUNCTION psl_change_milestone_link_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM id FROM core_case WHERE id=NEW.case_id AND kind='project' FOR UPDATE;
    IF NOT FOUND OR NOT EXISTS (
        SELECT 1 FROM pmo_changeversion v
        JOIN pmo_changerequest r ON r.id=v.change_id AND r.current_id=v.id
        JOIN pmo_changeauthorization a ON a.version_id=v.id
        JOIN pmo_changeexecutionevent e ON e.authorization_id=a.id AND e.kind='plan_updated'
        JOIN core_evidence plan ON plan.id=e.evidence_id AND plan.case_id=r.case_id AND plan.kind='plan'
        JOIN core_evidence source ON source.id=NEW.original_plan_id AND source.case_id=r.case_id AND source.kind='plan'
        JOIN pmo_baseline b ON b.case_id=r.case_id AND b.signed_id=NEW.signed_id
        JOIN core_evidence signed ON signed.id=b.signed_id AND signed.case_id=r.case_id AND signed.kind='signature'
        JOIN finance_billingcoverage cov ON cov.id=NEW.coverage_id AND cov.case_id=r.case_id
        JOIN policy_configuration cfg ON cfg.id=NEW.terms_id AND cfg.case_id=r.case_id AND cfg.component='D12.stage_terms'
        WHERE r.case_id=NEW.case_id AND v.id=NEW.version_id AND e.id=NEW.plan_event_id
          AND COALESCE(e.impact_details->'source_plan_id', to_jsonb(e.evidence_id))=to_jsonb(source.id)
          AND (SELECT state FROM policy_policystate state WHERE state.configuration_id=cfg.id ORDER BY state.id DESC LIMIT 1)='active'
          AND EXISTS (
              SELECT 1 FROM policy_registeredreference terms
              WHERE terms.case_id=cfg.case_id AND terms.version=1 AND (cfg.envelope->'value') ? terms.ref
                AND terms.schema_ref='schema:psl/billing-stage/v1'
                AND terms.content->'coverage_id'=to_jsonb(cov.id) AND terms.content->>'stage'=NEW.stage
          )
          AND NOT EXISTS (
              SELECT 1 FROM pmo_changeexecutionevent newer
              JOIN pmo_changeauthorization na ON na.id=newer.authorization_id
              WHERE na.version_id=v.id AND newer.kind='plan_updated' AND newer.id>e.id
          )
    ) THEN RAISE EXCEPTION 'A milestone link requires the exact signed terms and current same-project change plan'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER psl_change_milestone_link_scope BEFORE INSERT ON pmo_changemilestonelink
FOR EACH ROW EXECUTE FUNCTION psl_change_milestone_link_scope();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_changemilestonelink
FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

REVERSE = """
DROP TRIGGER psl_immutable ON pmo_changemilestonelink;
DROP TRIGGER psl_change_milestone_link_scope ON pmo_changemilestonelink;
DROP FUNCTION psl_change_milestone_link_scope();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('pmo', '0082_rfp_submission_artifact'),
        ('finance', '0010_billingcoverage_billingusage_billingpreparation_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='ChangeMilestoneLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stage', models.CharField(choices=[('uat', 'User acceptance testing'), ('completion', 'Completion')], max_length=20)),
                ('scope_note', models.CharField(max_length=240)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.case')),
                ('version', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='pmo.changeversion')),
                ('plan_event', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pmo.changeexecutionevent')),
                ('original_plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.evidence')),
                ('signed', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.evidence')),
                ('coverage', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.billingcoverage')),
                ('terms', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='policy.configuration')),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'constraints': [models.CheckConstraint(condition=models.Q(stage__in=['uat', 'completion']),
                                                             name='change_milestone_billing_stage')]},
        ),
        migrations.RunSQL(GUARDS, REVERSE),
    ]
