from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

SQL="""
CREATE FUNCTION psl_factory_execution_binding_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM workflows_factorywork w JOIN policy_configuration c ON c.case_id=w.case_id
   JOIN core_evidence e ON e.case_id=w.case_id
   WHERE w.id=NEW.work_id AND c.id=NEW.configuration_id AND c.component='OPS.factory_recovery_authority'
    AND e.id=NEW.evidence_id AND e.kind='policy_decision'
    AND NEW.previous_id IS NOT DISTINCT FROM w.execution_binding_id AND NEW.work_revision=w.revision+1
    AND NEW.rule->>'definition'=w.definition
    AND (NEW.rule->>'principal_id')::bigint=NEW.principal_id AND (NEW.rule->>'reviewer_id')::bigint=NEW.reviewer_id)
 THEN RAISE EXCEPTION 'Exact same-work recovery authority, evidence and current predecessor required'; END IF;
 IF NEW.sequence<>COALESCE((SELECT sequence+1 FROM workflows_factoryexecutionbinding WHERE id=NEW.previous_id AND work_id=NEW.work_id),1)
 THEN RAISE EXCEPTION 'Execution recovery sequence cannot fork or skip history'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_execution_binding_scope BEFORE INSERT ON workflows_factoryexecutionbinding FOR EACH ROW EXECUTE FUNCTION psl_factory_execution_binding_scope();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_factoryexecutionbinding FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_factory_execution_pointer() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.execution_binding_id IS NOT NULL THEN RAISE EXCEPTION 'Initial work must retain its authenticated starter'; END IF;
 ELSIF NEW.execution_binding_id IS DISTINCT FROM OLD.execution_binding_id THEN
  IF NOT EXISTS(SELECT 1 FROM workflows_factoryexecutionbinding b WHERE b.id=NEW.execution_binding_id
    AND b.work_id=NEW.id AND b.previous_id IS NOT DISTINCT FROM OLD.execution_binding_id AND b.work_revision=NEW.revision)
   OR NEW.fence<=OLD.fence OR NEW.revision<=OLD.revision OR NEW.lease_until IS NOT NULL
   OR NEW.budget_used<>OLD.budget_used OR NEW.budget_limit<>OLD.budget_limit
  THEN RAISE EXCEPTION 'Execution recovery must preserve work, allowance and fenced authority history'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_execution_pointer BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_factory_execution_pointer();
"""

class Migration(migrations.Migration):
    dependencies=[('workflows','0051_factory_planning_receipt'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='FactoryExecutionBinding',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('sequence',models.PositiveIntegerField()),('work_revision',models.PositiveIntegerField()),
        ('rule',models.JSONField()),('reason',models.CharField(max_length=2000)),('created_at',models.DateTimeField(auto_now_add=True)),
        ('work',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='execution_bindings',to='workflows.factorywork')),
        ('previous',models.OneToOneField(null=True,on_delete=django.db.models.deletion.PROTECT,related_name='successor',to='workflows.factoryexecutionbinding')),
        ('principal',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
        ('reviewer',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
        ('configuration',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='policy.configuration')),
        ('evidence',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='core.evidence'))],
        options={'constraints':[models.UniqueConstraint(fields=('work','sequence'),name='factory_execution_binding_sequence')]}),
        migrations.AddField(model_name='factorywork',name='execution_binding',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,related_name='+',to='workflows.factoryexecutionbinding')),
        migrations.RunSQL(SQL)]
