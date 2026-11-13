"""Index forecast payload citations once, preserving global generic-evidence exclusion."""
from django.db import migrations, models
import django.db.models.deletion


FORWARD = """
CREATE FUNCTION psl_forecast_evidence_refs(p jsonb)
RETURNS TABLE(evidence_id bigint, numeric_reference boolean)
LANGUAGE sql IMMUTABLE AS $$
    SELECT (entry->>'evidence_id')::bigint, bool_or(jsonb_typeof(entry->'evidence_id') = 'number')
    FROM (
        SELECT value AS entry FROM jsonb_array_elements(p->'items')
        UNION ALL
        SELECT value AS entry FROM jsonb_array_elements(p->'openings')
    ) entries
    GROUP BY (entry->>'evidence_id')::bigint
$$;

CREATE FUNCTION psl_index_forecast_evidence_refs() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO finance_forecastevidencereference (scenario_id, evidence_id, numeric_reference)
    SELECT NEW.id, refs.evidence_id, refs.numeric_reference FROM psl_forecast_evidence_refs(NEW.payload) refs;
    RETURN NEW;
END;
$$;

-- The trigger lock fences concurrent inserts until the backfill commits.
CREATE TRIGGER psl_index_forecast_evidence AFTER INSERT ON finance_forecastscenario
FOR EACH ROW EXECUTE FUNCTION psl_index_forecast_evidence_refs();

CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_forecastevidencereference
FOR EACH ROW EXECUTE FUNCTION psl_append_only();

INSERT INTO finance_forecastevidencereference (scenario_id, evidence_id, numeric_reference)
SELECT scenario.id, refs.evidence_id, refs.numeric_reference
FROM finance_forecastscenario scenario
CROSS JOIN LATERAL psl_forecast_evidence_refs(scenario.payload) refs;

"""

REVERSE = """
DROP TRIGGER psl_immutable ON finance_forecastevidencereference;
DROP TRIGGER psl_index_forecast_evidence ON finance_forecastscenario;
DROP FUNCTION psl_index_forecast_evidence_refs();
DROP FUNCTION psl_forecast_evidence_refs(jsonb);
"""


class Migration(migrations.Migration):
    dependencies = [('finance', '0076_obligation_trigger_alias_repair')]
    operations = [
        migrations.CreateModel(
            name='ForecastEvidenceReference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evidence_id', models.BigIntegerField(db_index=True)),
                ('numeric_reference', models.BooleanField()),
                ('scenario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.forecastscenario')),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('scenario', 'evidence_id'), name='forecast_evidence_per_scenario')]},
        ),
        migrations.RunSQL(FORWARD, REVERSE),
    ]
