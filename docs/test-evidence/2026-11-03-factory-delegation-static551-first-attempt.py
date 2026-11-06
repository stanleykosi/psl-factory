"""Bound delegated-authority changes; prove original invoice effects/calculation code retained."""
import json,hashlib,subprocess,sys,os
from pathlib import Path
run=int(sys.argv[1]);read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
old=read('docs/test-evidence/2026-11-01-factory-run542-source.json')['files']
current=read(f'docs/test-evidence/2026-11-01-factory-run{run}-source.json')['files']
for p,h in current.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
changed={p for p in old if current.get(p)!=old[p]};added=set(current)-set(old)
expected={'apps/policy/delegation_validators.py','apps/policy/role_assignments.py','apps/policy/services.py',
    'apps/policy/factory_routing_validators.py','apps/policy/operator_drafts.py','apps/policy/role_forms.py',
    'apps/finance/analysis.py','apps/finance/invoices.py','apps/finance/settlement_forms.py','apps/finance/settlement_views.py',
    'apps/workflows/factory_routing.py','apps/workflows/factory.py','apps/workflows/factory_views.py',
    'templates/factory/responsibility.html','templates/factory/detail.html'}
assert changed==expected,(changed-expected,expected-changed)
assert added=={'tests/test_factory_delegation.py','fixtures/factory-finance-delegation.json','templates/factory/invoice_delegation_configuration.html'},added
def once(value,a,b):
    assert value.count(a)==1,a
    return value.replace(a,b,1)
p='apps/workflows/factory.py';v=Path(p).read_bytes()
v=once(v,b"    from .factory_routing import delegated_for\n    review=invoices.review(actor,t.case_id,work.invoice_id,'Finance',verdict,evidence_id,reason,t.case.revision,delegated=delegated_for(work,actor))\n",
    b"    review=invoices.review(actor,t.case_id,work.invoice_id,'Finance',verdict,evidence_id,reason,t.case.revision)\n")
assert hashlib.sha256(v).hexdigest()==old[p],'Other factory commands/receipt priority must reconstruct542'
p='apps/finance/invoices.py';v=Path(p).read_bytes()
for a,b in [
    (b'def review(actor,case_id,invoice_id,role,verdict,evidence_id,reason,expected,*,delegated=False):',b'def review(actor,case_id,invoice_id,role,verdict,evidence_id,reason,expected):'),
    (b"authority=review_authority(actor,case,'invoice',role,verdict,i.actor_id,delegated=delegated,invoice=i)",b"authority=review_authority(actor,case,'invoice',role,verdict,i.actor_id)"),
    (b'for_invoice(i,actor,delegated=delegated)',b'for_invoice(i,actor)'),
    (b"    if not isinstance(r.authority,dict):raise ValidationError('Typed recorded invoice authority required')\n    delegated='D05.delegation_rules' in r.authority\n",b''),
    (b'for_invoice(invoice,r.actor,delegated=delegated)',b'for_invoice(invoice,r.actor)'),
    (b"authority=review_authority(r.actor,invoice.case,'invoice',r.role,r.verdict,invoice.actor_id,delegated=delegated,invoice=invoice)",b"authority=review_authority(r.actor,invoice.case,'invoice',r.role,r.verdict,invoice.actor_id)")]:v=once(v,a,b)
assert hashlib.sha256(v).hexdigest()==old[p],'Only invoice review/revalidation may change; reserve/intent/dispatch binding stay exact'
for p in ['apps/finance/invoice_delivery.py','adapters/factory_invoices.py','adapters/invoices.py']:
    assert current[p]==old[p],p
checks=[]
for cmd in [[sys.executable,'manage.py','check'],[sys.executable,'manage.py','makemigrations','--check','--dry-run'],[sys.executable,'-m','compileall','-q','apps','adapters','config','tests']]:
    r=subprocess.run(cmd,env=dict(os.environ,PGDATABASE='psl',PSL_OPERATOR_DRILL_DB='psl_drill_operator_demo',PSL_READINESS_DATABASE_REVISION='fixture-v1'),capture_output=True,text=True)
    checks.append({'command':cmd,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
out=Path(f'docs/test-evidence/2026-11-03-factory-delegation-static{run}.json');assert not out.exists()
out.write_text(json.dumps({'source_run':run,'parent_checkpoint':542,'changed_paths':sorted(changed),'added_paths':sorted(added),
    'all_other_factory_command_bytes_reconstruct_parent':True,'all_other_invoice_command_bytes_reconstruct_parent':True,
    'native_receipt_worker_adapters_models_migrations_dependencies_unchanged':True,'checks':checks,
    'policy_versions_added':['decision-delegation/v3','factory-finance-responsibility/v2'],'operational_business_values_added':False},indent=2)+'\n')
assert all(c['returncode']==0 for c in checks)
print({'source_run':run,'static_passed':3,'changed':len(changed),'added':len(added),'native_effect_commands_unchanged':True})
