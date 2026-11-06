"""Strengthen exact instruction/receipt lineage without rewriting applied0060."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0060_factory_rfp').SQL
OLD="JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN core_evidence h ON h.id=NEW.source_head_id"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+"\n   JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id JOIN core_evidence draft ON draft.id=(cr.sources->>'sow')::bigint")
OLD="AND r.matrix=h.body::jsonb->'matrix' AND j.status='confirmed'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,"""AND r.matrix=h.body::jsonb->'matrix'
    AND r.intake_id=(h.body::jsonb->>'intake')::bigint
    AND cr.sources->'requirements'=h.body::jsonb->'sources'->'requirements'
    AND cr.sources->'plan'=h.body::jsonb->'sources'->'plan' AND cr.sources->'costing'=h.body::jsonb->'sources'->'costing'
    AND draft.body::jsonb->'public_terms_id'=h.body::jsonb->'public_terms'
    AND (d.kind<>'loss_archive' OR d.lessons_id=(h.body::jsonb->>'lessons')::bigint)
    AND (p.factory_work_id IS NULL OR EXISTS(SELECT 1 FROM core_evidence origin WHERE origin.id=p.factory_source_id
     AND origin.case_id=NEW.case_id AND origin.kind='agent_private_rfp_intake'
     AND origin.body::jsonb-'lessons'=h.body::jsonb-'lessons'))
    AND j.status='confirmed'""")

class Migration(migrations.Migration):
    dependencies=[('workflows','0060_factory_rfp'),('documents','0019_factory_rfp_scope')]
    operations=[migrations.RunSQL(SQL)]
