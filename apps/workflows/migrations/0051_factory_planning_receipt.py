from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

SQL="""
CREATE FUNCTION psl_factory_planning_receipt_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
  JOIN workflows_factorywork w ON w.id=t.work_id JOIN policy_configuration p ON p.id=(a.result->>'coordinator_policy')::bigint
  JOIN workflows_integrationcontract c ON c.id=(a.result->>'contract')::bigint
  WHERE a.id=NEW.attempt_id AND a.phase='started' AND t.kind='ACT03'
   AND a.result->>'schema'='factory-provider-request/v1' AND p.component='OPS.factory_coordinator'
   AND p.case_id=w.case_id AND c.case_id=w.case_id AND c.payload->>'kind'='provider'
   AND NEW.binding=a.result->'binding') THEN RAISE EXCEPTION 'Exact native coordinator request and authenticated binding required'; END IF;
 IF NOT NEW.valid AND NEW.result<>'{}'::jsonb THEN RAISE EXCEPTION 'Rejected provider output must not be retained as native facts'; END IF;
 IF NEW.valid AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
  JOIN workflows_factorywork w ON w.id=t.work_id WHERE a.id=NEW.attempt_id
   AND jsonb_typeof(NEW.result)='object' AND (SELECT count(*) FROM jsonb_object_keys(NEW.result))=2
   AND NEW.result ?& ARRAY['activity','citations'] AND a.result->'payload'->'eligible' ? (NEW.result->>'activity')
   AND jsonb_typeof(NEW.result->'citations')='array' AND jsonb_array_length(NEW.result->'citations') BETWEEN 1 AND 16
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.result->'citations') x WHERE NOT EXISTS(
     SELECT 1 FROM jsonb_each(a.result->'citation_map') m JOIN core_evidence e ON e.id=(m.value#>>'{}')::bigint
     WHERE m.value=x.value AND e.case_id=w.case_id)))
 THEN RAISE EXCEPTION 'Native planning choice and citations must match this exact permitted request'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_planning_receipt_scope BEFORE INSERT ON workflows_factoryplanningreceipt FOR EACH ROW EXECUTE FUNCTION psl_factory_planning_receipt_scope();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_factoryplanningreceipt FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

class Migration(migrations.Migration):
    dependencies=[('workflows','0050_factory_accounting'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='FactoryPlanningReceipt',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('valid',models.BooleanField()),('result',models.JSONField()),('output_sha256',models.CharField(max_length=64)),
        ('binding',models.JSONField()),('created_at',models.DateTimeField(auto_now_add=True)),
        ('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ('attempt',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='planning_receipt',to='workflows.factoryattempt'))]),
        migrations.RunSQL(SQL)]
