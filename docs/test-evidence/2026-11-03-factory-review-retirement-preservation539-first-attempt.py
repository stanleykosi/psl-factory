"""Read-only fingerprints for every retained Finance cohort; no command replay."""
import os,sys,json,hashlib,ast
from pathlib import Path
sys.path.insert(0,str(Path.cwd()));run=int(sys.argv[1])
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
for p,h in read(f'docs/test-evidence/2026-11-01-factory-run{run}-source.json')['files'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from adapters.native_application_archive import connect,tables
from psycopg import sql
for node in ast.parse(Path('.runtime/pilot_preservation.py').read_text()).body:
    if isinstance(node,ast.FunctionDef) and node.name in ['definitions','rows']:exec(compile(ast.Module(body=[node],type_ignores=[]),'<review-retirement-preservation>','exec'))
proofs=[]
for context,baseline in [
    ('.runtime/factory-routing-ui-context.json','docs/test-evidence/2026-11-02-factory-responsibility-review-browser512-after.json'),
    ('.runtime/factory-invoice-recovery-ui-context.json','docs/test-evidence/2026-11-03-factory-review-authority-recovery534-after.json'),
    ('.runtime/factory-review-authority-ui-context.json','docs/test-evidence/2026-11-03-factory-review-status-authority534-after.json'),
    ('.runtime/factory-review-status-ui-context.json','docs/test-evidence/2026-11-03-factory-review-status-browser533-after.json')]:
    ctx=read(context);old=read(baseline);assert ctx['synthetic'] and ctx['database'].startswith('psl_factory_')
    with connect(ctx['database']) as db:
        db.execute('SET default_transaction_read_only=on')
        native={'tables':{t:rows(db,t) for t in tables(db)},**definitions(db)}
        indexes=db.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname").fetchall()
    assert native==old['native'] and [list(r) for r in indexes]==old['indexes'],context
    proofs.append({'database':ctx['database'],'baseline':baseline,'rowsets_unchanged':len(native['tables']),
        'guard_and_index_definitions_unchanged':True,'indexes':len(indexes)})
main=read('docs/test-evidence/2026-11-02-factory-routing-baseline.json')
with connect('psl') as db:
    db.execute('SET default_transaction_read_only=on')
    for name,fingerprint in main['native']['tables'].items():
        where="WHERE NOT (app='workflows' AND name='0049_factory_governance_task')" if name=='django_migrations' else ''
        assert rows(db,name,where)==fingerprint,name
    indexes=db.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname").fetchall()
    assert [list(r) for r in indexes]==main['indexes']
    current_definitions=definitions(db)
    #0049 expanded the task-kind check only; all other native definitions are retained.
    current_definitions['constraints']=[r for r in current_definitions['constraints'] if 'workflow_human_task_kind_guard' not in str(r)]
    old_definitions={k:v for k,v in main['native'].items() if k!='tables'}
    old_definitions['constraints']=[r for r in old_definitions['constraints'] if 'workflow_human_task_kind_guard' not in str(r)]
    assert current_definitions==old_definitions
out=Path(f'docs/test-evidence/2026-11-03-factory-review-retirement-preservation{run}.json');assert not out.exists()
out.write_text(json.dumps({'source_run':run,'cohorts':proofs,'main_rowsets_unchanged':len(main['native']['tables']),
    'main_indexes_unchanged':len(indexes),'main_guard_comparison':'Only previously accepted0049 task-kind expansion excluded',
    'commands_replayed':False,'operational_owner_values_added':False},indent=2)+'\n')
print({'retained_cohorts':len(proofs),'rowsets_each':329,'main_rowsets':len(main['native']['tables']),'main_indexes':len(indexes)})
