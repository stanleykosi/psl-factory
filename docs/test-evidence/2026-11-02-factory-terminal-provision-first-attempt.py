"""Fresh synthetic native release and ready intake; leave agent work/cancellation to UI."""
import os,sys,json,uuid,subprocess,hashlib
from pathlib import Path
sys.path.insert(0,str(Path.cwd()));run=int(sys.argv[1])
files=json.loads(Path(f'docs/test-evidence/2026-11-01-factory-run{run}-source.json').read_text())['files']
for p,h in files.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
out=Path('.runtime/factory-terminal-ui-context.json');assert not out.exists()
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
from adapters.native_application_archive import connect
from psycopg import sql
database='psl_factory_terminal_ui_'+uuid.uuid4().hex[:12]
with connect('postgres') as db:
    db.autocommit=True;assert not db.execute('SELECT 1 FROM pg_database WHERE datname=%s',(database,)).fetchone()
    db.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(database)))
log=Path(f'docs/test-evidence/2026-11-02-factory-terminal-fresh-install{run}.txt');assert not log.exists()
os.environ['PGDATABASE']=database
with log.open('x',encoding='utf-8') as stream:
    result=subprocess.run([sys.executable,'manage.py','migrate','--noinput'],stdout=stream,stderr=subprocess.STDOUT)
assert result.returncode==0
import django;django.setup()
from tests.test_delivery import DeliveryFixture
from tests.test_factory_go_live import setup
f=DeliveryFixture();f.setup_delivery();f.release();f=setup(base=f)
out.write_text(json.dumps({'database':database,'case':str(f.case.pk),'dossier':f.d.pk,'work':f.work.pk,'actor':f.actor.username,
    'actor_id':f.actor.pk,'profile':f.profile.pk,'inputs':f.inputs,'synthetic':True,'runtime':run,'fresh_template0':True,
    'classification':'Native synthetic release/intake fixture only; actual agent preparation and human cancellation await browser actions; no operational owner values'},indent=2)+'\n')
print({'database':database,'case':str(f.case.pk),'work':f.work.pk,'status':f.work.status})
