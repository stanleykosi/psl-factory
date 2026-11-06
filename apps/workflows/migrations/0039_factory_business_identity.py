import hashlib,json
from django.db import migrations,models

def backfill(apps,schema_editor):
    Work=apps.get_model('workflows','FactoryWork');Coverage=apps.get_model('finance','BillingCoverage')
    seen=set()
    for work in Work.objects.order_by('pk').iterator():
        cov=Coverage.objects.get(pk=work.request['coverage'],case_id=work.case_id)
        value={'case':str(work.case_id),'customer':cov.customer,'contract':cov.contract,'kind':'completion','usage':None}
        key=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        identity=(work.case_id,work.definition,key)
        if identity in seen:raise RuntimeError('Conflicting legacy factory work requires explicit reconciliation before switch')
        seen.add(identity);Work.objects.filter(pk=work.pk).update(business_key=key)

SQL="""
CREATE FUNCTION psl_factory_business_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.business_key IS DISTINCT FROM OLD.business_key THEN RAISE EXCEPTION 'Factory business identity is immutable'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_business_identity BEFORE UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_factory_business_identity();
"""

class Migration(migrations.Migration):
    dependencies=[('workflows','0038_factory_guards')]
    operations=[
        migrations.AddField(model_name='factorywork',name='business_key',field=models.CharField(max_length=64,null=True)),
        migrations.RunPython(backfill,migrations.RunPython.noop),
        migrations.AlterField(model_name='factorywork',name='business_key',field=models.CharField(max_length=64)),
        migrations.AddConstraint(model_name='factorywork',constraint=models.UniqueConstraint(fields=['case','definition','business_key'],name='factory_business_identity')),
        migrations.RunSQL(SQL,reverse_sql='DROP TRIGGER psl_factory_business_identity ON workflows_factorywork; DROP FUNCTION psl_factory_business_identity();')]
