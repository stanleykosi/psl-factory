"""Stage-specific impact804b harness. Does not start/stop/allocate databases or contact providers.

Only preflight is safe without explicit runtime clearance. Coordinator owns startup,
predecessor seed/recovery stages and normal through-stop supervision.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = Path('/tmp/psl-sourceunit777b-owned/data')
SYSTEM = '7705450556148731993'
PRIMARY = 'psl_sourceunit777'
TEST = 'test_psl_sourceunit777'
MAX_BYTES = 175 * 1024**2
LAUNCH_BYTES = 165 * 1024**2


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def resources(start=False):
    size = int(subprocess.check_output(['du', '-sb', str(DATA)]).split()[0])
    value = {'pgdata_bytes':size, 'overlay_free':shutil.disk_usage(ROOT).free,
        'tmp_free':shutil.disk_usage('/tmp').free}
    require(size <= (145*1024**2 if start else LAUNCH_BYTES), 'Owned PGDATA exceeds preflight/batch budget')
    require(value['overlay_free'] >= 256*1024**2, 'Overlay free space below bounded launch floor')
    require(value['tmp_free'] >= 450*1024**2, 'Temporary filesystem free space below bounded launch floor')
    return value


def selection():
    value=json.loads((ROOT/'docs/design/impact804b-selection.json').read_text())
    ids=[item for batch in value['batches'] for item in batch['ids']]
    require(len(ids)==len(set(ids))==value['count']==12, 'Exact12 regressions required')
    require(len(value['batches'])==7 and all(len(b['ids'])<=2 for b in value['batches']), 'Bounded batches required')
    for path,pin in value['source_pins'].items():
        require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==pin,'Source pin changed: '+path)
    return value


def static_preflight(args):
    require(sys.flags.optimize == 0, 'Verified assertion comparator requires nonoptimized Python')
    require(os.environ.get('PSL_LEDGER_PROVISIONAL') in (None, '', '0'), 'Provisional ledger DDL flag forbidden')
    require(git('rev-parse', 'HEAD') == args.expected_head, 'Frozen source head differs')
    require(bool(selection()['accepted_predecessor']) and args.predecessor==selection()['accepted_predecessor'], 'Exact accepted impact802 predecessor required')
    require(not subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',args.predecessor,'HEAD']).returncode, 'Accepted ancestor missing')
    require(os.environ.get('PSL_INVOICE_CRASH_OWNED_SYSTEM') is None,'Crash target opt-in may only be set by verified worker stage')
    require(not git('diff', '--name-only') and not git('diff','--cached','--name-only'), 'Tracked source has uncommitted changes')
    value = selection()
    # Standalone stages cannot bypass the reviewed baseline gate.
    import runpy
    runpy.run_path(str(ROOT/'scripts/impact804b_inputs.py'),run_name='__impact804b_inputs__')
    # Import/check only. Neither django.setup nor model checks open a DB connection.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django
    django.setup()
    from django.core.checks import run_checks
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.state import ProjectState
    from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
    loader = MigrationLoader(None)
    require(not MigrationAutodetector(loader.project_state(), ProjectState.from_apps(django.apps.apps),
        NonInteractiveMigrationQuestioner()).changes(graph=loader.graph), 'Model migration drift')
    require(not run_checks(databases=[]), 'Django static checks failed')
    return {'head':args.expected_head, 'predecessor':args.predecessor, 'count':value['count'],
        'runtime_guard_source':args.expected_head, 'resources':resources(start=args.command=='preflight')}


def connect(target):
    require(os.environ.get('RUN804B_RUNTIME_CLEARANCE') == 'coordinator-cleared-impact804b', 'No runtime clearance; no database connection attempted')
    require(os.environ.get('PGHOST') == '127.0.0.1' and os.environ.get('PGPORT') == '55777'
        and os.environ.get('PGUSER') == 'psl' and os.environ.get('PGDATABASE') == PRIMARY,
        'Explicit owned loopback connection coordinates required')
    require((DATA/'postmaster.pid').exists(), 'Coordinator must start and verify the owned cluster')
    pid_lines = (DATA/'postmaster.pid').read_text().splitlines()
    require(pid_lines[1] == str(DATA) and pid_lines[3] == '55777', 'Postmaster target differs')
    from django.conf import settings
    from django.db import connections
    connections.close_all()
    settings.DATABASES['default']['NAME'] = target
    connections['default'].settings_dict['NAME'] = target
    connection = connections['default']
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(), system_identifier::text FROM pg_control_system()')
        require(cursor.fetchone() == (target,SYSTEM), 'Connected database/system identity differs')
        cursor.execute("SELECT name, setting FROM pg_settings WHERE name IN ('fsync','synchronous_commit','full_page_writes')")
        require(all(value == 'on' for name,value in cursor.fetchall()), 'Durability settings differ')
        cursor.execute('SELECT datname FROM pg_database WHERE datname IN (%s,%s)',[PRIMARY,TEST])
        require({row[0] for row in cursor.fetchall()} == {PRIMARY,TEST}, 'Both existing owned DBs must already exist; no allocation permitted')
    return connection


def exact_ids(suite):
    for item in suite:
        if hasattr(item,'id'):
            yield item.id()
        else:
            yield from exact_ids(item)


def verify_schema(connection):
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.recorder import MigrationRecorder
    from importlib import import_module
    target=('policy','0032_factory_planning_binding_impact')
    require(target in MigrationRecorder(connection).applied_migrations(),'Exact0032 marker required')
    executor=MigrationExecutor(connection)
    require(not executor.migration_plan(executor.loader.graph.leaf_nodes()),'Empty migration plan required; continuation never migrates')
    expected=import_module('apps.policy.migrations.'+target[1]).Migration.operations[0].sql.split('$$',2)[1]
    with connection.cursor() as cursor:
        cursor.execute("SELECT prosrc,pg_get_functiondef(oid) FROM pg_proc WHERE oid=%s::regprocedure",['psl_policy_impact_guard()'])
        body,definition=cursor.fetchone()
    require(body==expected,'Exact0032 function body required')
    require(hashlib.sha256(definition.encode()).hexdigest()=='21a1a35aab45dad6614938e84855be45a32b1a004f82da9cc98e92d5a5c6513e','Exact804a0032 function fingerprint required')


def tests(args):
    require(args.target == TEST, 'Tests must use the separate existing owned test database')
    connection = connect(TEST)
    verify_schema(connection)
    from django.db.migrations.recorder import MigrationRecorder
    require(MigrationRecorder(connection).migration_qs.filter(app='finance',name='0076_obligation_trigger_alias_repair').exists(),
        'Reviewed779 schema repair required; this runner never migrates or creates databases')
    require(MigrationRecorder(connection).migration_qs.filter(app='workflows', name='0077_factory_ledger').exists(), 'Real workflow0077 migration required')
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname='psl_factory_ledger' AND NOT tgisinternal AND tgenabled IN ('O','A')")
        require(cursor.fetchone()[0] == 1, 'Real enabled factory ledger trigger required; no provisional installation')
    from django.db.migrations.executor import MigrationExecutor
    executor = MigrationExecutor(connection)
    require(not executor.migration_plan(executor.loader.graph.leaf_nodes()), 'Existing database schema must already match composed source')
    from django.test.runner import DiscoverRunner
    from source_units777_snapshot import snapshot, load
    batches=selection()['batches']
    require(1 <= args.batch <= len(batches), 'Choose an exact declared batch')
    batch=batches[args.batch-1];ids=batch['ids']
    runner = DiscoverRunner(verbosity=2,interactive=False,keepdb=True)
    runner.setup_test_environment()
    try:
        suite = runner.build_suite(ids)
        require(sorted(exact_ids(suite)) == sorted(ids), 'Discovered tests differ from exact selection')
        (args.evidence/'selected.json').write_text(json.dumps(ids,indent=2)+'\n')
        snapshot(args.evidence/'tests-before.json.gz')
        baseline=load(args.evidence/'tests-before.json.gz')
        nonempty=[table for table,rows in baseline['tables'].items() if rows and table not in {'django_migrations','django_content_type','auth_permission'}]
        require(not nonempty, 'TransactionTestCase would flush pre-existing test DB business rows; hold without running: '+str(nonempty))
        start = time.monotonic()
        result = runner.run_suite(suite)
        outcome = {'component':batch['component'],'testsRun':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'skipped':result.skipped,'elapsed':time.monotonic()-start}
        (args.evidence/'outcome.json').write_text(json.dumps(outcome,indent=2)+'\n')
        snapshot(args.evidence/'tests-after.json.gz')
        after=load(args.evidence/'tests-after.json.gz')
        sequence_changes={k:{'before':baseline['sequences'].get(k),'after':after['sequences'].get(k)} for k in set(baseline['sequences'])|set(after['sequences']) if baseline['sequences'].get(k)!=after['sequences'].get(k)}
        (args.evidence/'sequence-changes.json').write_text(json.dumps(sequence_changes,indent=2)+'\n')
        from qbo781_preservation import preserved
        different=[table for table in baseline['tables'] if baseline['tables'][table] != after['tables'].get(table)]
        raw={'raw_different_tables':different, 'metadata_row_changes':{}}
        for table in ('django_content_type','auth_permission'):
            before_rows=baseline['tables'][table];after_rows=after['tables'][table]
            raw['metadata_row_changes'][table]={'removed':[row for row in before_rows if row not in after_rows],
                'added':[row for row in after_rows if row not in before_rows]}
        (args.evidence/'raw-row-changes.json').write_text(json.dumps(raw,indent=2)+'\n')
        try:
            comparison=preserved(baseline,after)
        except (AssertionError,KeyError,TypeError,ValueError):
            (args.evidence/'preservation-HOLD.txt').write_text('Exact state/metadata/FK preservation failed; raw snapshots retained.\n')
            raise RuntimeError('HOLD: exact state preservation failed; no automatic continuation') from None
        (args.evidence/'preservation.json').write_text(json.dumps(comparison,indent=2)+'\n')
        require(result.testsRun == len(ids) and not result.skipped and result.wasSuccessful(), 'Native batch failed; retain all raw output')
    finally:
        os.environ.pop('PSL_INVOICE_CRASH_OWNED_SYSTEM',None)
        runner.teardown_test_environment()
        connection.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=['preflight','snapshot','tests','schema'])
    parser.add_argument('--expected-head',required=True)
    parser.add_argument('--predecessor',required=True)
    parser.add_argument('--target',choices=[PRIMARY,TEST],default=PRIMARY)
    parser.add_argument('--evidence',type=Path)
    parser.add_argument('--batch',type=int,default=1)
    args = parser.parse_args()
    info = static_preflight(args)
    if args.command == 'preflight':
        print(json.dumps(info,indent=2)); return
    require(args.evidence is not None and not args.evidence.exists(), 'Unique new evidence directory required; never overwrite previous proof')
    # Enforce clearance BEFORE creating any runtime artifact or opening a connection.
    require(os.environ.get('RUN804B_RUNTIME_CLEARANCE') == 'coordinator-cleared-impact804b', 'Runtime clearance is pending')
    args.evidence.mkdir(parents=True)
    (args.evidence/'preflight.json').write_text(json.dumps(info,indent=2)+'\n')
    from django.db import connections
    try:
        if args.command == 'schema':
            connection=connect(args.target)
            verify_schema(connection)
            (args.evidence/'schema.json').write_text(json.dumps({'status':'EXACT0032_EMPTY_PLAN'})+'\n')
        elif args.command == 'tests':
            tests(args)
        else:
            connect(args.target)
            from source_units777_snapshot import snapshot
            snapshot(args.evidence/'before.json.gz')
        (args.evidence/'resources-after.json').write_text(json.dumps(resources(),indent=2)+'\n')
    finally:
        connections.close_all()


if __name__ == '__main__':
    main()
