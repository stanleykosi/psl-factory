"""Actual separately provisioned PostgreSQL provider; synthetic people/criteria only."""
import os,sys,json,base64,copy
from types import SimpleNamespace
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
import django
django.setup()
import psycopg
from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.finance import receipt_followup as source
from apps.finance.models import InvoiceJob
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,active_component
from apps.policy.invoice_receipt_validators import FOLLOWUP
from adapters import native_finance as native,finance_followup_readback as adapter
from adapters.finance_readback_database import provider,ACTIVE

v=json.load(sys.stdin);stage=sys.argv[1];check=SimpleTestCase()
rules=json.loads(Path('fixtures/finance-followup-readback.json').read_text(encoding='utf-8'));rules.pop('classification')
os.environ['PSL_NATIVE_FINANCE_PASSWORD_READBACK']=connection.settings_dict.get('PASSWORD','')
os.environ['PSL_NATIVE_FINANCE_IDENTITY_READBACK']=v['identity']
entry=dict(database=v['provider'],host=connection.settings_dict['HOST'],port=int(connection.settings_dict['PORT']),user=connection.settings_dict['USER'],
 password_env='PSL_NATIVE_FINANCE_PASSWORD_READBACK',credential_revision='fixture-v1',identity_ref='fixture-readback-finance',identity_secret_env='PSL_NATIVE_FINANCE_IDENTITY_READBACK',
 classification='synthetic',sslmode='disable',revision='fixture-v1',case_ids=[v['case']]+([v['operational_case']] if v.get('operational_case') else []))
settings.NATIVE_FINANCE={'providers':{'fixture-finance':entry},'stores':{}}

def seed():
    from tests.settlement_helpers import fixture,draft,issue
    from tests.billing_helpers import evidence
    a,c,_,p,e=fixture(v['case']);issued=issue(a,c,draft(a,c,p),e)
    Case.objects.create(id=v['operational_case'],tenant=c.tenant,title='Synthetic test of an operational classification boundary',kind='project',synthetic=False)
    return {'projection':dict(format='psl.finance-receipt-followup/v1',source_case_id=str(c.pk),source_invoice_id=issued.invoice_id,source_correction_id=None,
        variant='issue',mapping_sha256='a'*64,observation_sha256='b'*64,packet_sha256='c'*64,publication_operation='d'*64,outcome='unknown',
        business_jobs_reenacted=False,debt_waived=False,activation_enabled=False)}

def actors():
    c=Case.objects.get(pk=v['case']);j=InvoiceJob.objects.filter(invoice__case=c).select_related('actor').first()
    return j.actor,c,j

def receive(projection=None):
    a,c,_=actors();e=add_evidence(a,c.pk,'integration_contract','Synthetic handoff supplied by current source owner','synthetic:readback')
    r=source.receive(a,c.pk,projection or v['projection'],e.pk);return {'request':r.pk}

def decide(configure=False):
    a,c,j=actors();r=source.Request.objects.get(request_key=source.digest(v['projection']))
    if configure:
        e=add_evidence(a,c.pk,'policy_decision','Synthetic source-owner readback criteria, no real appointment','synthetic:readback')
        cfg=draft_operator_policy(a,c.pk,FOLLOWUP,dict(owner_id=a.pk,owner_role='Finance',resolutions=['investigate','link_current_intent','decline'],request_valid_seconds=3600,allow_synthetic=True),e.pk,timezone.now())
        transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    result=source.decide(a,c.pk,r.pk,'link_current_intent','Synthetic exact current source intent investigation',v.get('key','owner-link'),j.pk)
    return source.report(a,c.pk,r.pk)

def probe():
    projection=v['projection'];mapping=SimpleNamespace(provider_ref='fixture-finance',plan=SimpleNamespace(case=SimpleNamespace(synthetic=True)),payload={k:projection[k] for k in ['source_case_id','source_invoice_id','source_correction_id','variant']})
    binding,_=native.binding(mapping)
    reader=adapter
    if v.get('include_successors'):
        from adapters import finance_successor_readback as reader
    result=reader.read(mapping,projection,rules,binding)
    check.assertIsNone(ACTIVE.get());check.assertFalse(result['execution_authorized']);check.assertFalse(result['financial_effect_verified'])
    if v.get('controls'):
        foreign={**projection,'source_case_id':v['operational_case']}
        mismatched=SimpleNamespace(provider_ref=mapping.provider_ref,plan=mapping.plan,payload={**mapping.payload,'source_case_id':v['operational_case']})
        mismatch_binding,_=native.binding(mismatched)
        with check.assertRaises(ValidationError):adapter.read(mismatched,foreign,rules,mismatch_binding)
        check.assertEqual(adapter.read(mapping,projection,{**rules,'max_records':10},binding),result) # Unrelated pricing/Finance references are excluded.
        for patch_value in [{'max_records':1},{'max_queries':1},{'max_payload_bytes':1}]:
            with check.assertRaises(ValidationError):adapter.read(mapping,projection,{**rules,**patch_value},binding)
        with patch('apps.finance.receipt_followup.timezone.now',return_value=timezone.now()+timedelta(hours=2)):
            expired=adapter.read(mapping,projection,rules,binding);check.assertEqual(expired['disposition'],'stale');check.assertEqual(expired['hold_code'],'request_expired')
        _,(_,args,_)=native.binding(mapping)
        with check.assertRaises(PermissionDenied):
            with provider(args,rules):Grant.objects.filter(case_id=v['case']).update(active=False)
        with check.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
            with provider(args,rules) as db:db.connection.execute('UPDATE core_case SET title=title WHERE id=%s',[v['case']])
        check.assertIsNone(ACTIVE.get())
        with patch.dict(os.environ,{'PSL_NATIVE_FINANCE_IDENTITY_READBACK':base64.b64encode(os.urandom(32)).decode()}):
            with check.assertRaises(ValidationError):adapter.read(mapping,projection,rules,binding)
    return result

def lineage():
    from tests.correction_helpers import configure as financial_configure,note,apply
    from tests.followup_successor_helpers import configure
    from apps.finance import followup_successors as d
    from apps.finance.models import InvoiceIssue
    a,c,j=actors();financial_configure(a,c)
    e={'cash_correction':c.evidence.filter(kind='cash_correction').first(),'review':add_evidence(a,c.pk,'financial_correction_review','Synthetic current legal note review','synthetic:lineage')}
    target=apply(a,c,note(a,c,InvoiceIssue.objects.get(invoice=j.invoice),e),e);target.refresh_from_db();check.assertEqual(target.status,'confirmed')
    r=source.Request.objects.get(pk=v['request']);proof=add_evidence(a,c.pk,'integration_contract','Synthetic exact source-owned lineage evidence','synthetic:lineage')
    p=d.propose(a,c.pk,r.pk,j.pk,target.pk,'legal_correction',proof.pk,'Synthetic exact legal correction lineage','native-adapter-lineage')
    b,_,_=configure(a,c,r);d.review(b,c.pk,p.pk,'approve',proof.pk,'Independent lineage approval only','native-adapter-review')
    return {'successor_reviewer':b.pk}

if stage=='seed':result=seed()
elif stage=='initialize':native.initialize('fixture-finance',True);result={'initialized':True}
elif stage=='probe':result=probe()
elif stage=='receive':result=receive()
elif stage=='decide':result=decide(True)
elif stage=='supersede':result=decide(True)
elif stage=='revoke':
    a,c,_=actors();Grant.objects.filter(user=a,case=c,action='finance.receipt_followup.decide').update(active=False);result=source.report(a,c.pk,v['request'])
elif stage=='conflict':result=receive({**v['projection'],'outcome':'present'})
elif stage=='lineage':result=lineage()
elif stage=='lineage_revoke':
    Grant.objects.filter(user_id=v['successor_reviewer'],case_id=v['case'],action='finance.receipt_followup.review_successor').update(active=False);result={'revoked':True}
else:raise ValueError('Unknown installed test stage')
print(json.dumps(result))
