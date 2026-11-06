"""Keep one go-live anchor; allow only linear immutable human evidence reaffirmations."""
from django.db import migrations,models

KINDS=['planning_decision','kickoff','progress','glpi_request','release_ready','release_outcome','go_live','hypercare','archive','handover','finance_confirmation','closure_decision','closure','go_live_reaffirmation']
SQL=r"""
CREATE FUNCTION psl_go_live_reaffirmation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.kind='go_live_reaffirmation' THEN
  IF jsonb_typeof(NEW.data) IS DISTINCT FROM 'object'
   OR NOT(NEW.data ?& ARRAY['receipt_id','pm_signature_id','client_signature_id','note','previous_acceptance_id','authority'])
   OR NEW.data-ARRAY['receipt_id','pm_signature_id','client_signature_id','note','previous_acceptance_id','authority']<>'{}'::jsonb
   OR jsonb_typeof(NEW.data->'note') IS DISTINCT FROM 'string' OR length(btrim(NEW.data->>'note')) NOT BETWEEN 1 AND 4000
   OR jsonb_typeof(NEW.data->'authority') IS DISTINCT FROM 'object'
   OR NOT (NEW.data->'authority' ? 'D05.role_principal_assignments') OR NOT (NEW.data->'authority' ? 'D05.decision_action_matrix')
   OR NOT EXISTS(SELECT 1 FROM pmo_deliveryrecord previous
    WHERE previous.id=NEW.parent_id AND previous.dossier_id=NEW.dossier_id AND previous.kind IN ('go_live','go_live_reaffirmation')
     AND NEW.data->>'previous_acceptance_id'=previous.id::text AND NEW.id>previous.id AND NEW.created_at>=previous.created_at)
   OR NOT EXISTS(SELECT 1 FROM pmo_deliveryrecord anchor WHERE anchor.dossier_id=NEW.dossier_id AND anchor.kind='go_live')
   OR EXISTS(SELECT 1 FROM pmo_deliveryrecord closed WHERE closed.dossier_id=NEW.dossier_id AND closed.kind='closure')
  THEN RAISE EXCEPTION 'Exact open-dossier go-live anchor, linear prior evidence head and explicit authority required'; END IF;
  IF NOT EXISTS(SELECT 1 FROM documents_publicationreceipt r JOIN documents_publication p ON p.id=r.publication_id
    JOIN documents_version v ON v.id=p.version_id JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id
    JOIN pmo_deliverydossier dd ON dd.id=b.dossier_id
    JOIN core_evidence pm ON pm.id=(NEW.data->>'pm_signature_id')::bigint
    JOIN core_evidence client ON client.id=(NEW.data->>'client_signature_id')::bigint
    WHERE r.id=(NEW.data->>'receipt_id')::bigint AND b.dossier_id=NEW.dossier_id AND b.purpose='go_live'
     AND v.audience='client' AND b.snapshot=NEW.snapshot AND r.payload_sha256=v.payload_sha256 AND r.payload=v.payload
     AND pm.case_id=dd.case_id AND client.case_id=dd.case_id AND pm.kind='signature' AND client.kind='signature'
     AND pm.id<>client.id AND NEW.evidence_id=pm.id)
  THEN RAISE EXCEPTION 'Exact delivered client go-live report and distinct actual signature evidence required'; END IF;
  IF EXISTS(SELECT 1 FROM pmo_deliveryrecord used JOIN pmo_deliverydossier dd ON dd.id=used.dossier_id
    JOIN pmo_deliverydossier target ON target.case_id=dd.case_id AND target.id=NEW.dossier_id
    WHERE used.kind IN ('go_live','go_live_reaffirmation') AND
     (used.data->>'pm_signature_id' IN (NEW.data->>'pm_signature_id',NEW.data->>'client_signature_id')
      OR used.data->>'client_signature_id' IN (NEW.data->>'pm_signature_id',NEW.data->>'client_signature_id')))
  THEN RAISE EXCEPTION 'Actual go-live signature evidence cannot be reused'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_go_live_reaffirmation BEFORE INSERT ON pmo_deliveryrecord FOR EACH ROW EXECUTE FUNCTION psl_go_live_reaffirmation();
"""

class Migration(migrations.Migration):
    dependencies=[('pmo','0041_identity_resolution_guard'),('documents','0017_factory_go_live_scope')]
    operations=[migrations.RemoveConstraint(model_name='deliveryrecord',name='delivery_known_record_kind'),
        migrations.AlterField(model_name='deliveryrecord',name='kind',field=models.CharField(choices=[(x,x) for x in KINDS],max_length=30)),
        migrations.AddConstraint(model_name='deliveryrecord',constraint=models.CheckConstraint(condition=models.Q(kind__in=KINDS),name='delivery_known_record_kind')),
        migrations.AddConstraint(model_name='deliveryrecord',constraint=models.UniqueConstraint(fields=['parent'],condition=models.Q(kind='go_live_reaffirmation'),name='delivery_go_live_reaffirmation_parent')),
        migrations.RunSQL(SQL)]
