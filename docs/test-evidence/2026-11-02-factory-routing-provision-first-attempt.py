"""Fresh isolated browser proof. Select the DB before importing Django in every child."""
import os,sys,json,hashlib,subprocess,uuid
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
mode=sys.argv[1];run=int(sys.argv[2]);read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
context=Path('.runtime/factory-routing-ui-context.json');provision=Path('.runtime/factory-routing-provision-context.json')
files=read(f'docs/test-evidence/2026-11-01-factory-run{run}-source.json')['files']
for p,h in files.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
assert read(f'docs/test-evidence/2026-11-01-factory-run{run}.json')['returncode']==0
os.environ.setdefault('PSL_OPERATOR_DRILL_DB','psl_drill_operator_demo');os.environ.setdefault('PSL_READINESS_DATABASE_REVISION','fixture-v1')
if mode=='provision':
    assert not context.exists() and not provision.exists()
    from adapters.native_application_archive import connect
    from psycopg import sql
    database='psl_factory_routing_ui_'+uuid.uuid4().hex[:12]
    with connect('postgres') as db:
        db.autocommit=True;assert not db.execute('SELECT 1 FROM pg_database WHERE datname=%s',(database,)).fetchone()
        db.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(database)))
    provision.write_text(json.dumps({'database':database,'source_run':run,'synthetic':True,'template':'template0'},indent=2)+'\n')
    env=dict(os.environ,PGDATABASE=database)
    with Path(f'docs/test-evidence/2026-11-02-factory-routing-fresh-install{run}.txt').open('x',encoding='utf-8') as log:
        subprocess.run([sys.executable,'manage.py','migrate','--noinput'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    subprocess.run([sys.executable,__file__,'seed',str(run)],env=env,check=True);sys.exit(0)
ctx=read(provision);assert ctx['source_run']==run and ctx['synthetic'] and ctx['database'].startswith('psl_factory_routing_ui_')
os.environ['PGDATABASE']=ctx['database'];os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
import django;django.setup()
from django.db import connection
assert connection.settings_dict['NAME']==ctx['database'] and ctx['database']!='psl'
from django.db.migrations.executor import MigrationExecutor
executor=MigrationExecutor(connection);assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
if mode=='seed':
    from django.contrib.auth import get_user_model
    from apps.workflows.models import FactoryWork
    assert not context.exists() and not get_user_model().objects.exists() and not FactoryWork.objects.exists()
    from tests.factory_helpers import fixture
    from tests.test_factory_routing import configure
    f=fixture(responsibility=False);config=configure(f,process_owner_id=None)
    ctx.update(case=str(f['case'].pk),work=f['work'].pk,actor=f['actor'].username,actor_id=f['actor'].pk,
        decision_evidence=f['evidence']['policy_decision'].pk,review_evidence=f['proof'].pk,initial_assignment=config.pk,
        provider='synthetic_factory_v1',adapter_directory=str(Path('.runtime/factory-routing-mock-receipts').resolve()),port=8014,
        fixture_only=True,database_selected_before_django=True)
    context.write_text(json.dumps(ctx,indent=2)+'\n');print(json.dumps({'database':ctx['database'],'work':ctx['work'],'fixture_only':True}))
elif mode=='serve':
    ctx=read(context)
    from django.conf import settings
    from adapters.factory_invoices import MockFactoryInvoiceAdapter
    settings.FACTORY_ADAPTERS={ctx['case']:MockFactoryInvoiceAdapter(ctx['adapter_directory'])}
    settings.SESSION_COOKIE_NAME='psl_factory_routing_session';settings.CSRF_COOKIE_NAME='psl_factory_routing_csrf'
    from django.core.management import execute_from_command_line
    execute_from_command_line([sys.argv[0],'runserver','127.0.0.1:8014','--noreload'])
elif mode=='readback':
    ctx=read(context)
    with connection.cursor() as cur:cur.execute('SET default_transaction_read_only=on')
    from apps.workflows.models import FactoryWork,HumanTask,FactoryAttempt,TaskEvent
    from apps.finance.models import InvoiceReview,InvoiceIssue,InvoiceDelivery
    from apps.policy.factory_routing_validators import COMPONENT
    from apps.policy.models import Configuration
    from apps.workflows.factory_routing import evaluate
    w=FactoryWork.objects.select_related('case','actor','invoice').get(pk=ctx['work']);assert w.status=='verified'
    gov=HumanTask.objects.get(case=w.case,kind='factory_governance');review=InvoiceReview.objects.get(invoice=w.invoice)
    assert gov.status=='completed' and TaskEvent.objects.filter(task=gov,action='factory.owners_rechecked',data__approval_granted=False).exists()
    assert review.publication_packet==__import__('apps.finance.invoices',fromlist=['review_packet']).review_packet(w.invoice)
    assert Configuration.objects.filter(case=w.case,component=COMPONENT).count()==2
    assert InvoiceIssue.objects.filter(invoice=w.invoice).count()==1 and InvoiceDelivery.objects.filter(invoice=w.invoice).count()==1
    assert w.activities.filter(kind='ACT10',status='succeeded').count()==2 and w.budget_limit==20000
    out=Path(f'docs/test-evidence/2026-11-02-factory-routing-browser{run}.json');assert not out.exists()
    out.write_text(json.dumps({'database':ctx['database'],'work':w.pk,'case':str(w.case_id),'source_run':run,
        'state':w.status,'governance_task':gov.pk,'native_review':review.pk,'native_issue_receipts':1,'native_delivery_receipts':1,
        'budget_used':w.budget_used,'budget_limit':w.budget_limit,'routing':evaluate(w),
        'actual_ui_actions':['Agent investigation/draft/packet/ownership wait','Human claim governance','Human draft/validate/activate corrected assignments','Human recheck without approval','Agent current routing','Human exact Finance review','Agent mock issue/delivery/receipt verification'],
        'classification':'Native synthetic browser proof; one human fixture has multiple roles. Not independent UAT or real provider evaluation',
        'operational_assignments_added':False},indent=2)+'\n');print({'state':w.status,'budget':w.budget_used,'native_receipts':2})
else:raise AssertionError(mode)
