"""Extend the closed coordinator identity and verify the observed downstream record."""

from django.db import migrations


GUARD = """
 IF NEW.definition='process-handoff/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM workflows_nativestation s JOIN core_evidence e ON e.id=NEW.source_head_id
   WHERE e.case_id=NEW.case_id AND NEW.request=jsonb_build_object('station',s.id,'process',s.process)
    AND (s.work_id=NEW.id OR (TG_OP='INSERT' AND s.work_id IS NULL))
  ) THEN RAISE EXCEPTION 'Exact department station and source required'; END IF;
  IF NEW.status='verified' AND NOT EXISTS (
   SELECT 1 FROM workflows_nativestation s
   JOIN workflows_nativestationadvice h ON h.station_id=s.id
   JOIN workflows_nativestationreceipt r ON r.handoff_id=h.id
   JOIN agents_specialistpacket p ON p.id=h.packet_id AND p.work_id=s.work_id AND p.process=s.process
   JOIN workflows_factoryactivity c ON c.work_id=s.work_id AND c.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=c.id AND a.phase='observed'
   WHERE s.work_id=NEW.id AND p.consumed_at IS NOT NULL AND p.superseded_by_id IS NULL
    AND a.result->'station_receipt'=to_jsonb(r.id) AND a.result->'handoff'=to_jsonb(h.id)
    AND a.result->'receiver'=jsonb_build_array(r.receiver_model,r.receiver_pk)
  ) THEN RAISE EXCEPTION 'An observed downstream department receipt is required'; END IF;
 END IF;
"""
CHANGES = (
    ("IF NEW.definition NOT IN ('pmo-issues/v1'", "IF NEW.definition NOT IN ('process-handoff/v1','pmo-issues/v1'"),
    ("p.component=CASE NEW.definition WHEN 'pmo-issues/v1'", "p.component=CASE NEW.definition WHEN 'process-handoff/v1' THEN 'OPS.factory_native_station_execution' WHEN 'pmo-issues/v1'"),
    (" IF NEW.status='verified' THEN", GUARD + " IF NEW.status='verified' THEN"),
)


def modify(editor, reverse=False):
    with editor.connection.cursor() as cursor:
        if reverse:
            cursor.execute("SELECT EXISTS(SELECT 1 FROM workflows_nativestation)")
            if cursor.fetchone()[0]:
                raise RuntimeError("Preserve existing department handoff history before reversing this migration.")
        cursor.execute("SELECT pg_get_functiondef('psl_factory_identity()'::regprocedure)")
        definition = cursor.fetchone()[0]
    for before, after in CHANGES:
        if reverse:
            before, after = after, before
        if definition.count(before) != 1:
            raise RuntimeError("Unexpected predecessor for the department station identity guard.")
        definition = definition.replace(before, after)
    editor.execute(definition, params=None)


class Migration(migrations.Migration):
    dependencies = [("workflows", "0097_nativestation_nativestationadvice_and_more")]
    operations = [
        migrations.RunPython(lambda apps, editor: modify(editor), lambda apps, editor: modify(editor, True)),
        migrations.RunSQL(
            "CREATE TRIGGER station_advice_history BEFORE UPDATE OR DELETE ON workflows_nativestationadvice FOR EACH ROW EXECUTE FUNCTION psl_append_only(); "
            "CREATE TRIGGER station_receipt_history BEFORE UPDATE OR DELETE ON workflows_nativestationreceipt FOR EACH ROW EXECUTE FUNCTION psl_append_only();",
            "DROP TRIGGER station_advice_history ON workflows_nativestationadvice; DROP TRIGGER station_receipt_history ON workflows_nativestationreceipt;",
        ),
    ]
