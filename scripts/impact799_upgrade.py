"""One-shot policy0028 upgrade. Invoked only by the separately cleared native harness."""
import hashlib
import importlib
import json
from pathlib import Path

TARGET = ('policy', '0028_signature_packet_policy_impact')
PREVIOUS = ('policy', '0027_signed_adoption_recovery_policy_impact')
FUNCTION_PREVIOUS = '0027_signed_adoption_recovery_policy_impact'
FUNCTION = 'psl_policy_impact_guard()'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def body(module):
    sql = importlib.import_module('apps.policy.migrations.' + module).Migration.operations[0].sql
    return sql.split('$$', 2)[1]


def compare(before, after, old_fingerprint, new_fingerprint):
    """Exact raw preservation except the declared function and one migration marker."""
    require(set(before) == set(after), 'Snapshot sections changed')
    require(set(before['tables']) == set(after['tables']), 'Table set changed')
    require(set(before['functions']) == set(after['functions']), 'Function set changed')
    require(before['functions'][FUNCTION] == old_fingerprint, 'Old function fingerprint differs')
    require(after['functions'][FUNCTION] == new_fingerprint and old_fingerprint != new_fingerprint,
            'New function fingerprint differs')
    for name in before:
        if name not in {'tables', 'functions', 'sequences'}:
            require(before[name] == after[name], 'Unexpected schema/settings delta: ' + name)
    for name in before['functions']:
        if name != FUNCTION:
            require(before['functions'][name] == after['functions'][name], 'Other function changed')
    for name in before['tables']:
        if name != 'django_migrations':
            require(before['tables'][name] == after['tables'][name], 'Existing rows changed: ' + name)
    old = before['tables']['django_migrations']; new = after['tables']['django_migrations']
    require(all(row in new for row in old), 'Historical migration rows changed')
    added = [json.loads(row) for row in new if row not in old]
    require(len(new) == len(old) + 1 and len(added) == 1, 'Not exactly one migration marker')
    marker = added[0]
    require((marker['app'], marker['name']) == TARGET, 'Wrong migration marker')
    require(not any((json.loads(row)['app'], json.loads(row)['name']) == TARGET for row in old), 'Target already applied')
    require(set(before['sequences']) == set(after['sequences']), 'Sequence set changed')
    for name, value in before['sequences'].items():
        next_value = after['sequences'][name]
        require(value['definition'] == next_value['definition'], 'Sequence definition changed')
        if name == 'django_migrations_id_seq':
            expected = value['state'][0] + (1 if value['state'][1] else 0)
            require(marker['id'] == expected and next_value['state'] == [expected, True], 'Unexpected migration sequence advance')
        else:
            require(value == next_value, 'Other sequence changed: ' + name)
    return {'status': 'EXACT_DECLARED_UPGRADE_ONLY', 'marker': marker,
            'function_before': old_fingerprint, 'function_after': new_fingerprint}


def upgrade(connection, evidence):
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.recorder import MigrationRecorder
    from source_units777_snapshot import snapshot, load
    evidence = Path(evidence)
    require(evidence.is_dir() and not any(evidence.iterdir()), 'Unique empty upgrade evidence directory required')
    require(connection.get_autocommit() and not connection.in_atomic_block, 'Upgrade requires committed fixture/autocommit')
    applied = MigrationRecorder(connection).applied_migrations()
    require(PREVIOUS in applied and TARGET not in applied, 'Exact0027/absent0028 prerequisite failed')
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    require([(m.app_label, m.name, backwards) for m, backwards in plan] == [(*TARGET, False)], 'Only0028 may be applied')
    with connection.cursor() as cursor:
        cursor.execute("SELECT prosrc,pg_get_functiondef(oid) FROM pg_proc WHERE oid=%s::regprocedure", [FUNCTION])
        old_body, old_def = cursor.fetchone()
    require(old_body == body(FUNCTION_PREVIOUS), 'Current body differs from immutable0027')
    snapshot(evidence/'before.json.gz')
    try:
        executor.migrate([TARGET])
    finally:
        # Preserve actual partial/committed state even if migration raises.
        snapshot(evidence/'after-attempt.json.gz')
    with connection.cursor() as cursor:
        cursor.execute("SELECT prosrc,pg_get_functiondef(oid) FROM pg_proc WHERE oid=%s::regprocedure", [FUNCTION])
        new_body, new_def = cursor.fetchone()
    require(new_body == body(TARGET[1]), 'New body differs from frozen0028')
    # CREATE OR REPLACE must leave every function property except its exact body unchanged.
    require(old_def.replace(old_body, new_body, 1) == new_def, 'Undeclared function property changed')
    result = compare(load(evidence/'before.json.gz'), load(evidence/'after-attempt.json.gz'),
                     hashlib.sha256(old_def.encode()).hexdigest(), hashlib.sha256(new_def.encode()).hexdigest())
    again = MigrationExecutor(connection)
    require(not again.migration_plan(again.loader.graph.leaf_nodes()), 'Repeated migration is not empty')
    again.migrate([TARGET])
    snapshot(evidence/'after-repeat.json.gz')
    require(load(evidence/'after-repeat.json.gz') == load(evidence/'after-attempt.json.gz'), 'Repeated migration changed raw state')
    (evidence/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
