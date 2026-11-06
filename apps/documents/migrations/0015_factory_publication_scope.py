from django.db import migrations,models
import django.db.models.deletion

SQL=r"""
CREATE FUNCTION psl_publication_factory_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_policy_id IS NULL)
  OR (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_source_id IS NULL)
 THEN RAISE EXCEPTION 'Complete optional factory publication scope required'; END IF;
 IF NEW.factory_work_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM workflows_factorywork w JOIN documents_version v ON v.id=NEW.version_id JOIN documents_document d ON d.id=v.document_id
   JOIN policy_configuration p ON p.id=NEW.factory_policy_id JOIN core_evidence e ON e.id=NEW.factory_source_id
   WHERE w.id=NEW.factory_work_id AND w.definition='commercial/v1' AND w.case_id=d.case_id
   AND p.case_id=w.case_id AND p.component='OPS.factory_commercial_execution' AND e.case_id=w.case_id AND e.kind='agent_private_commercial_intake'
   AND EXISTS(SELECT 1 FROM pmo_commercialdocumentbinding b JOIN pmo_commercialrevision r ON r.id=b.revision_id JOIN pmo_commercialcase c ON c.id=r.dossier_id WHERE b.version_id=v.id AND c.case_id=w.case_id))
 THEN RAISE EXCEPTION 'Same-case commercial factory publication references required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_publication_factory_scope BEFORE INSERT ON documents_publication FOR EACH ROW EXECUTE FUNCTION psl_publication_factory_scope();
"""

class Migration(migrations.Migration):
    dependencies=[('documents','0014_native_subject_identity'),('workflows','0041_factory_commercial')]
    operations=[
        migrations.AddField(model_name='publication',name='factory_work',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,related_name='document_publications',to='workflows.factorywork')),
        migrations.AddField(model_name='publication',name='factory_policy',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,related_name='+',to='policy.configuration')),
        migrations.AddField(model_name='publication',name='factory_source',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,related_name='+',to='core.evidence')),
        migrations.RunSQL(SQL)]
