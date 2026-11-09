"""Read-only raw synthetic rows and opaque definition fingerprints; never print function bodies."""
import gzip,hashlib,json,sys
from pathlib import Path
from django.db import connection

def snapshot(path):
    with connection.cursor() as c:
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        tables={}
        for (name,) in c.fetchall():
            c.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(name)+' t')
            tables[name]=sorted(row[0] for row in c.fetchall())
        queries={
          'functions':"SELECT p.oid::regprocedure::text,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind='f'",
          'columns':"SELECT c.relname||'.'||a.attname,jsonb_build_object('type',format_type(a.atttypid,a.atttypmod),'notnull',a.attnotnull,'ordinal',a.attnum,'default',pg_get_expr(d.adbin,d.adrelid))::text FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped",
          'constraints':"SELECT conrelid::regclass::text||'.'||conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace",
          'indexes':"SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public'",
          'triggers':"SELECT tgrelid::regclass::text||'.'||tgname,pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN(SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace)"}
        result={'tables':tables}
        for key,query in queries.items():
            c.execute(query)
            result[key]={name:hashlib.sha256(value.encode()).hexdigest() if key=='functions' else value for name,value in c.fetchall()}
        c.execute("SELECT name,setting FROM pg_settings WHERE name IN ('server_version','server_encoding','fsync','synchronous_commit','full_page_writes','unix_socket_directories','listen_addresses','transaction_isolation','wal_segment_size','max_wal_size','min_wal_size') ORDER BY name")
        result['settings']=dict(c.fetchall())
        assert all(result['settings'][key]=='on' for key in ['fsync','synchronous_commit','full_page_writes'])
        assert result['settings']['server_encoding']=='UTF8'
        assert result['settings']['wal_segment_size']=='1048576'
        assert result['settings']['max_wal_size']=='24' and result['settings']['min_wal_size']=='2'
        c.execute("SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconnlimit,rolvaliduntil,rolconfig FROM pg_roles ORDER BY rolname")
        result['roles']=c.fetchall()
        c.execute("SELECT nspname,nspowner,nspacl FROM pg_namespace WHERE nspname='public'")
        result['permissions']=c.fetchall()
        c.execute("SELECT schemaname,sequencename,sequenceowner,data_type,start_value,min_value,max_value,increment_by,cycle,cache_size FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")
        sequences={}
        for row in c.fetchall():
            name=row[1];c.execute('SELECT last_value,is_called FROM '+connection.ops.quote_name(name))
            sequences[name]={'definition':list(row),'state':list(c.fetchone())}
        result['sequences']=sequences
    with gzip.open(path,'wt') as f:json.dump(result,f,sort_keys=True,default=str)
    print('Snapshot',Path(path).name,len(tables),'tables',sum(map(len,tables.values())),'rows',len(sequences),'sequences')

def load(path):
    with gzip.open(path,'rt') as f:return json.load(f)

if __name__=='__main__':
    import django;django.setup()
    snapshot(sys.argv[1])
