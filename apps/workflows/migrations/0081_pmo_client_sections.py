"""P52: exact seven-section weekly client projection, retaining every other guard.

No historical migration or historical document/receipt is rewritten. The
accepted predecessor's function is transformed only at the closed section
contract, and an unexpected predecessor definition fails the migration.
"""
from django.db import migrations

SCOPE = 'Unknown: approved project scope is not established by this selected local weekly PMO fact set. This report does not amend scope.'
DEPENDENCIES = 'Unknown: project dependencies are not established by this selected weekly fact and narrative set. Obtain current dependency evidence; no absence of dependencies is implied.'
OLD_LIST = '["executive_summary","status","risks","timeline","next_steps"]'
NEW_LIST = '["executive_summary","scope","status","risks","timeline","dependencies","next_steps"]'
OLD_SORTED = '["executive_summary","next_steps","risks","status","timeline"]'
NEW_SORTED = '["dependencies","executive_summary","next_steps","risks","scope","status","timeline"]'
COVERAGE = """ AND v.fields->'scope'->>'text'='{scope}'
 AND v.fields->'dependencies'->>'text'='{dependencies}'
 AND EXISTS(SELECT 1 FROM jsonb_array_elements(v.payload->'sections') section WHERE section->>'heading'='scope' AND section->>'text'='{scope}')
 AND EXISTS(SELECT 1 FROM jsonb_array_elements(v.payload->'sections') section WHERE section->>'heading'='dependencies' AND section->>'text'='{dependencies}')
""".format(scope=SCOPE, dependencies=DEPENDENCIES)
MARKER = " AND content.body::jsonb->>'protocol'='pmo-weekly-client-content/v1'"


def transform(schema_editor, reverse=False):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_reporting_document(bigint,bigint,bigint)'::regprocedure)")
        definition = cursor.fetchone()[0]
    pairs = [(OLD_LIST, NEW_LIST, 2), (OLD_SORTED, NEW_SORTED, 1),
             ("jsonb_array_length(template.definition->'audience_fields'->'client')=5",
              "jsonb_array_length(template.definition->'audience_fields'->'client')=7", 1),
             ("jsonb_array_length(v.payload->'sections')=5", "jsonb_array_length(v.payload->'sections')=7", 1)]
    for old, new, count in pairs:
        if reverse:
            old, new = new, old
        if definition.count(old) != count:
            raise RuntimeError('Unexpected weekly client section guard predecessor; review before migration')
        definition = definition.replace(old, new)
    if reverse:
        if definition.count(COVERAGE) != 1:
            raise RuntimeError('Expected exact client coverage checks before reversal')
        definition = definition.replace(COVERAGE, '')
    else:
        if definition.count(MARKER) != 1:
            raise RuntimeError('Expected one client narrative protocol boundary')
        definition = definition.replace(MARKER, COVERAGE + MARKER)
    schema_editor.execute(definition, params=None)


def forwards(apps, schema_editor):
    transform(schema_editor)


def backwards(apps, schema_editor):
    transform(schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [('workflows', '0080_factory_issue_reference'), ('pmo', '0045_commercial_signature_packet')]
    operations = [migrations.RunPython(forwards, backwards)]
