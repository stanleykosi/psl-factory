import subprocess,sys,time,json,hashlib,os
from pathlib import Path
from datetime import datetime,timezone
run=int(sys.argv[1]);labels=sys.argv[2:];prefix=f'docs/test-evidence/2026-11-01-factory-run{run}'
assert not Path(prefix+'.json').exists()
files={p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for root in ['apps','adapters','config','contracts','fixtures','templates','tests','static'] for p in Path(root).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for name in ['requirements.in','requirements.lock','AGENTS.md','README.md']:files[name]=hashlib.sha256(Path(name).read_bytes()).hexdigest()
for label in labels:
    if Path(label).is_dir():
        for path in Path(label).rglob('test_*.py'):files[path.as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
Path(prefix+'-source.json').write_text(json.dumps({'files':files},indent=2)+'\n',encoding='utf-8')
argv=[sys.executable,'manage.py','test',*labels,'--keepdb','--noinput','--verbosity','2'];log=prefix+'.txt'
record={'run':run,'command':argv,'started_at':datetime.now(timezone.utc).isoformat(),'log':log,'status':'running','database':'test_'+os.environ.get('PGDATABASE','psl')+'; PostgreSQL127.0.0.1:55432'}
Path(prefix+'.json').write_text(json.dumps(record,indent=2)+'\n');start=time.monotonic()
with open(log,'w',encoding='utf-8') as output:r=subprocess.run(argv,stdout=output,stderr=subprocess.STDOUT)
record.update(status='finished',returncode=r.returncode,elapsed_seconds=round(time.monotonic()-start,3))
Path(prefix+'.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));sys.exit(r.returncode)
