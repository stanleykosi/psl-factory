"""Synthetic supplied-reference interface; not real Finance workbook approval."""
import copy
import json
from unittest.mock import patch
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, transaction
from django.test import TestCase
from apps.core.models import Evidence
from apps.finance import forecast
from apps.finance.models import ForecastRun
from apps.identity.models import Grant
from apps.policy.services import reference_values, resolve
from .forecast_helpers import fixture, payload, scenario, review
from .billing_helpers import evidence, policy
from .helpers import rev

class WorkbookReferenceTests(TestCase):
    def setUp(self): self.a, self.c, self.method = fixture()

    def store(self, kind, value):
        e = evidence(self.a, self.c, 'forecast_workbook_'+kind, json.dumps(value))
        return {'id': e.pk, 'version': e.version, 'sha256': e.sha256}

    def fixture(self, *, unknown=False, revision=1):
        v = payload(self.a, self.c, amount=None if unknown else '50')
        opening = dict(v['openings'][0]); opening.pop('evidence_id'); opening['amount'] = '0'
        e = evidence(self.a, self.c, 'forecast_opening', json.dumps(opening))
        v['openings'] = [dict(opening, evidence_id=e.pk)]
        scope = {k: v[k] for k in ['entity','currency','basis','as_of','months']}
        scope.update(workbook='synthetic-cash', workbook_version='v1', scenario='FORECAST-1', revision=revision, unit='NGN-whole')
        months = []
        for index, month in enumerate(v['months']):
            column = 'C' if index == 0 else 'D'
            cells = {role: {'sheet':'PRIVATE-CASH', 'address':column+str(i+1)} for i,role in enumerate(['opening','inflow','outflow','closing'])}
            values = {'opening':'0' if index == 0 else None if unknown else '50', 'inflow':None if unknown and index == 0 else '50' if index == 0 else '0',
                      'outflow':'0' if index == 0 else '20', 'closing':None if unknown else '50' if index == 0 else '30'}
            months.append({'month':month,'cells':cells,'literals':values})
        edges = [{'source':{'month':months[0]['month'],'cell':months[0]['cells']['closing']},'target':{'month':months[1]['month'],'cell':months[1]['cells']['opening']}}]
        oracle = {'protocol':'forecast-workbook-oracle/v1','scope':scope,'months':[{'month':m['month'],'literals':m['literals']} for m in months]}
        oracle_pin = self.store('oracle', oracle)
        contract = {'protocol':'forecast-workbook-reference-contract/v1','implementation':'monthly_cash_chain_v1','scope':scope,
                    'months':[{'month':m['month'],'cells':m['cells']} for m in months],'edges':edges,'oracle':oracle_pin}
        contract_pin = self.store('contract', contract)
        snapshot = {'protocol':'forecast-workbook-chain-snapshot/v1','scope':scope,'observed_on':v['as_of'],'extracted_on':v['as_of'],'months':copy.deepcopy(months),'edges':copy.deepcopy(edges)}
        v['workbook_chain'] = {'snapshot':self.store('snapshot',snapshot),'contract':contract_pin,'oracle':oracle_pin,'unit':scope['unit']}
        method = dict(self.method, workbook_reference={'contract':contract_pin,'oracle':oracle_pin,'snapshot_max_age_days':0})
        policy(self.a,self.c,'D10.forecast_inclusion_rule_id',method)
        return v, snapshot

    def prepare(self,v):
        s=scenario(self.a,self.c,v)
        return forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c))

    def changed(self,v,snapshot):
        v=copy.deepcopy(v);v['workbook_chain']['snapshot']=self.store('snapshot',snapshot);return v

    def held(self,r,code):
        self.assertEqual(r.result['status'],'held')
        self.assertEqual(r.result['workbook_comparison']['status'],'held')
        self.assertIn(code,[f['code'] for f in r.result['workbook_comparison']['findings']])
        self.assertIsNone(r.result['periods'][0]['closing']);self.assertIsNone(r.result['periods'][1]['opening'])
        with self.assertRaises(ValidationError):review(self.a,self.c,r)

    def test_valid_explicit_graph_exact_citations_repeat(self):
        v,_=self.fixture();r=self.prepare(v)
        self.assertEqual(r.result['workbook_comparison']['status'],'equivalent')
        self.assertEqual(r.result['periods'][1]['closing'],'30')
        self.assertEqual(forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c)).pk,r.pk)
        review(self.a,self.c,r)
        from apps.agents.forecast import investigate
        result=investigate(self.a,self.c.pk,r.pk,rev(self.c)).result
        self.assertTrue({p['id'] for k,p in v['workbook_chain'].items() if k!='unit'}.issubset({p['id'] for p in result['citations']}))

    def test_c06_same_scenario_version_wrong_edge_equal_values(self):
        v,snap=self.fixture();good=self.prepare(v);original=copy.deepcopy(good.result)
        snap['edges'][0]['source']['cell']=snap['months'][0]['cells']['inflow']
        # The correction is a new durable version; the bad edge is within that
        # exact same declared scenario/version, never a foreign-scenario trick.
        v,snap=self.fixture(revision=2)
        snap['edges'][0]['source']['cell']=snap['months'][0]['cells']['inflow']
        bad=self.prepare(self.changed(v,snap));self.held(bad,'workbook_reference_mismatch')
        self.assertEqual(bad.scenario.number,snap['scope']['revision'])
        broken=next(f for f in bad.result['workbook_comparison']['findings'] if f['code']=='workbook_reference_mismatch')
        self.assertEqual(broken['expected']['source']['cell']['address'],'C4')
        self.assertEqual(broken['actual']['source']['cell']['address'],'C2')
        self.assertEqual(snap['months'][0]['literals']['inflow'],snap['months'][0]['literals']['closing'])
        good.refresh_from_db();self.assertEqual(good.result,original)

    def test_durable_wrong_reference_held_no_fallback(self):
        v,snap=self.fixture();snap['edges'][0]['source']['cell']=snap['months'][0]['cells']['inflow']
        self.held(self.prepare(self.changed(v,snap)),'workbook_reference_mismatch')

    def test_missing_duplicate_dangling_edges(self):
        v,snap=self.fixture()
        from apps.finance.forecast_workbook import compare
        s=scenario(self.a,self.c,v);_,native=forecast.calculate(s)
        for mode,code in [('missing','workbook_reference_missing'),('duplicate','workbook_reference_duplicate_target'),('dangling','workbook_reference_dangling')]:
            bad=copy.deepcopy(snap)
            if mode=='missing':bad['edges']=[]
            elif mode=='duplicate':bad['edges']*=2
            else:bad['edges'][0]['source']['cell']['address']='Z99'
            candidate=copy.deepcopy(s);candidate.payload=self.changed(v,bad)
            result=compare(candidate,reference_values(resolve(forecast.METHOD,self.c).configuration)[0],native['periods'])
            self.assertIn(code,[x['code'] for x in result['findings']])

    def test_missing_month_held(self):
        v,snap=self.fixture();snap['months'].pop()
        self.held(self.prepare(self.changed(v,snap)),'workbook_month_mismatch')

    def test_scope_and_dates_units_are_not_converted(self):
        v,snap=self.fixture()
        from apps.finance.forecast_workbook import compare
        s=scenario(self.a,self.c,v);_,native=forecast.calculate(s)
        for field,value in [('currency','USD'),('entity','foreign'),('unit','thousands'),('scenario','foreign'),('revision',2),('as_of','2000-01-01'),('workbook_version','v2')]:
            bad=copy.deepcopy(snap);bad['scope'][field]=value;candidate=copy.deepcopy(s);candidate.payload=self.changed(v,bad)
            result=compare(candidate,reference_values(resolve(forecast.METHOD,self.c).configuration)[0],native['periods'])
            self.assertIn('workbook_scope_mismatch',[x['code'] for x in result['findings']])

    def test_missing_pins_retained_held(self):
        v=payload(self.a,self.c);v['workbook_chain']={'snapshot':None,'contract':None,'oracle':None,'unit':'NGN-whole'}
        self.held(self.prepare(v),'workbook_contract_missing')

    def test_unknown_is_equivalent_but_not_zero(self):
        v,_=self.fixture(unknown=True);r=self.prepare(v)
        self.assertEqual(r.result['workbook_comparison']['status'],'equivalent')
        self.assertIsNone(r.result['periods'][0]['closing']);self.assertIsNone(r.result['periods'][1]['opening'])
        result=copy.deepcopy(r.result);result['status']='ready'
        with self.assertRaises(DatabaseError),transaction.atomic():ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=r.manifest,result=result,sha256='a'*64,actor=self.a)

    def test_oracle_numerical_mismatch_independent_of_graph(self):
        v,snap=self.fixture();snap['months'][0]['literals']['closing']='51'
        self.held(self.prepare(self.changed(v,snap)),'workbook_oracle_mismatch')

    def test_formula_external_link_text_inert(self):
        v,snap=self.fixture();snap['months'][0]['formula_text']={r:'=EXEC("https://invalid.test/private"); VBA; __import__("os")' for r in ['opening','inflow','outflow','closing']}
        with patch('subprocess.run',side_effect=AssertionError('No execution')),patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
            r=self.prepare(self.changed(v,snap))
        self.assertEqual(r.result['workbook_comparison']['status'],'equivalent')
        self.assertNotIn('invalid.test',json.dumps(r.result))

    def test_actual_source_date_stale(self):
        from datetime import timedelta
        from django.utils import timezone
        v,snap=self.fixture();snap['observed_on']=(timezone.localdate()-timedelta(days=1)).isoformat()
        self.held(self.prepare(self.changed(v,snap)),'workbook_source_stale')

    def test_foreign_source_unavailable_without_disclosure(self):
        v,_=self.fixture()
        from apps.core.models import Case
        other=Case.objects.create(tenant='foreign',title='Foreign',synthetic=True)
        e=Evidence.objects.create(case=other,kind='forecast_workbook_snapshot',version=1,source='foreign',body='PRIVATE FOREIGN',sha256='a'*64,created_by=self.a)
        v['workbook_chain']['snapshot']={'id':e.pk,'version':1,'sha256':e.sha256}
        r=self.prepare(v);self.held(r,'workbook_snapshot_unavailable');self.assertNotIn('PRIVATE FOREIGN',json.dumps(r.result))

    def test_legacy_no_equivalence_claim_and_raw_claim_rejected(self):
        r=self.prepare(payload(self.a,self.c));self.assertNotIn('workbook_comparison',r.result)
        result=dict(r.result,workbook_comparison={'status':'equivalent'})
        with self.assertRaises(DatabaseError),transaction.atomic():ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=r.manifest,result=result,sha256='a'*64,actor=self.a)

    def test_raw_ready_equivalence_and_fallback_rejected(self):
        v,snap=self.fixture();snap['edges']=[];r=self.prepare(self.changed(v,snap))
        for change in ['ready','equivalent','fallback']:
            result=copy.deepcopy(r.result);manifest=copy.deepcopy(r.manifest)
            if change=='ready':result['status']='ready'
            elif change=='fallback':result['periods'][1]['opening']='50'
            else:result['workbook_comparison']['status']='equivalent';result['workbook_comparison']['findings']=[];manifest['workbook_comparison']=result['workbook_comparison']
            with self.subTest(change=change),self.assertRaises(DatabaseError),transaction.atomic():ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=manifest,result=result,sha256='a'*64,actor=self.a)

    def test_grant_revision_policy_date_currentness_and_history(self):
        v,_=self.fixture();r=self.prepare(v);original=copy.deepcopy(r.result)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.forecast.calculate').update(active=False)
        with self.assertRaises(PermissionDenied):forecast.ensure_current(r)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.forecast.calculate').update(active=True)
        from datetime import timedelta
        from django.utils import timezone
        today=timezone.localdate()
        with patch('django.utils.timezone.localdate',return_value=today+timedelta(days=1)):
            with self.assertRaises(ValidationError):forecast.ensure_current(r)
        policy(self.a,self.c,forecast.METHOD,self.method)
        with self.assertRaises(ValidationError):forecast.ensure_current(r)
        scenario(self.a,self.c,v)
        with self.assertRaises(ValidationError):forecast.ensure_current(r)
        r.refresh_from_db();self.assertEqual(r.result,original)

    def test_partial_policy_cannot_launder_broken_graph(self):
        v,snap=self.fixture();m=reference_values(resolve(forecast.METHOD,self.c).configuration)[0]
        m['partial_publication']='label_partial';policy(self.a,self.c,forecast.METHOD,m)
        snap['edges']=[];r=self.prepare(self.changed(v,snap));self.held(r,'workbook_reference_missing')
        result=copy.deepcopy(r.result);result['status']='partial'
        with self.assertRaises(DatabaseError),transaction.atomic():ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=r.manifest,result=result,sha256='a'*64,actor=self.a)

    def test_private_inventory_and_group_do_not_disclose_references(self):
        from apps.core.evidence_access import public_evidence
        from apps.workflows import factory_forecast_sources as bridge
        v,_=self.fixture();r=self.prepare(v);s=r.scenario
        ids={s.evidence_id}|{i['evidence_id'] for i in v['openings']+v['items']}|{v['workbook_chain'][k]['id'] for k in ['snapshot','contract','oracle']}
        selection={'protocol':bridge.PROTOCOL,'scenario_id':s.pk,'as_of':v['as_of'],'months':v['months'],'source_ids':sorted(ids),'template_id':None,'audience':'internal'}
        bridge.selection(self.a,self.c,selection)
        with self.assertRaises(ValidationError):bridge.selection(self.a,self.c,dict(selection,source_ids=sorted(ids-{v['workbook_chain']['contract']['id']})))
        report=bridge.investigation(self.a,self.c,dict(selection,audience='group'),r.pk)
        self.assertNotIn('PRIVATE-CASH',json.dumps(report));self.assertNotIn('workbook_comparison',json.dumps(report))
        self.assertFalse(public_evidence(Evidence.objects.filter(pk__in=[v['workbook_chain'][k]['id'] for k in ['snapshot','contract','oracle']])).exists())
        Grant.objects.filter(case=self.c,user=self.a,action='finance.read').update(active=False)
        with self.assertRaises(PermissionDenied):bridge.investigation(self.a,self.c,selection,r.pk)

    def test_coherent_forged_numbers_cannot_bypass_native_sources(self):
        v,snap=self.fixture();v['items'][0]['amount']='60';r=self.prepare(v)
        self.held(r,'workbook_oracle_mismatch')
        result=copy.deepcopy(r.result);manifest=copy.deepcopy(r.manifest)
        result['status']='ready';result['findings']=[]
        result['workbook_comparison']['status']='equivalent';result['workbook_comparison']['findings']=[]
        manifest['workbook_comparison']=result['workbook_comparison']
        for period, supplied in zip(result['periods'],snap['months']):period.update(supplied['literals'])
        with self.assertRaises(DatabaseError),transaction.atomic():ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=manifest,result=result,sha256='a'*64,actor=self.a)

    def test_workbook_rows_are_append_only(self):
        v,_=self.fixture();r=self.prepare(v)
        from apps.finance.models import ForecastScenario
        for model,pk in [(ForecastScenario,r.scenario_id),(ForecastRun,r.pk)]:
            with self.subTest(model=model.__name__),self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).update(actor_id=self.a.pk)
            with self.subTest(model=model.__name__),self.assertRaises(DatabaseError),transaction.atomic():
                from django.db import connection
                with connection.cursor() as c:c.execute('DELETE FROM '+connection.ops.quote_name(model._meta.db_table)+' WHERE id=%s',[pk])

    def test_contract_revision_is_not_silently_adopted(self):
        v,_=self.fixture();r=self.prepare(v);old=copy.deepcopy(r.result)
        contract=json.loads(Evidence.objects.get(pk=v['workbook_chain']['contract']['id']).body)
        changed=self.store('contract',contract)
        m=reference_values(resolve(forecast.METHOD,self.c).configuration)[0]
        m['workbook_reference']['contract']=changed;policy(self.a,self.c,forecast.METHOD,m)
        with self.assertRaises(ValidationError):forecast.ensure_current(r)
        candidate=forecast.prepare(self.a,self.c.pk,r.scenario_id,rev(self.c))
        self.held(candidate,'workbook_policy_pin_mismatch')
        self.assertEqual(candidate.scenario.payload['workbook_chain']['contract'],v['workbook_chain']['contract'])
        r.refresh_from_db();self.assertEqual(r.result,old)

    def test_wrong_role_duplicate_cell_and_absent_oracle_are_held(self):
        from apps.finance.forecast_workbook import compare
        v,snap=self.fixture();s=scenario(self.a,self.c,v);_,native=forecast.calculate(s)
        m=reference_values(resolve(forecast.METHOD,self.c).configuration)[0]
        bad=copy.deepcopy(snap);bad['months'][0]['cells']['opening']=bad['months'][0]['cells']['inflow']
        candidate=copy.deepcopy(s);candidate.payload=self.changed(v,bad)
        result=compare(candidate,m,native['periods'])
        self.assertIn('workbook_cell_duplicate',[x['code'] for x in result['findings']])
        candidate=copy.deepcopy(s);candidate.payload=copy.deepcopy(v);candidate.payload['workbook_chain']['oracle']=None
        result=compare(candidate,m,native['periods'])
        self.assertIn('workbook_oracle_missing',[x['code'] for x in result['findings']])

    def test_valid_unknown_graph_can_follow_explicit_partial_review(self):
        v,_=self.fixture(unknown=True)
        m=reference_values(resolve(forecast.METHOD,self.c).configuration)[0]
        m['partial_publication']='label_partial';policy(self.a,self.c,forecast.METHOD,m)
        r=self.prepare(v);self.assertEqual(r.result['status'],'partial');review(self.a,self.c,r)
        self.assertIsNone(r.result['periods'][1]['closing'])

    def test_actual_group_receipt_excludes_private_workbook_graph(self):
        from django.contrib.auth import get_user_model
        from apps.documents.controlled import register_template,reserve_publication
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt
        from apps.finance import group_forecast as group
        from apps.policy.services import register_reference,active_component
        from .document_helpers import artifact
        from .helpers import activate
        v,snap=self.fixture();snap['months'][0]['formula_text']={k:'PRIVATE-FORMULA-EXTERNAL-LINK' for k in ['opening','inflow','outflow','closing']}
        r=self.prepare(self.changed(v,snap));review(self.a,self.c,r)
        reader=get_user_model().objects.create_user(username='workbook-group-reader')
        Grant.objects.create(case=self.c,user=reader,action='document.receive:group')
        owner=evidence(self.a,self.c,'policy_decision','Synthetic selected group disclosure only')
        definition={'document_type':'finance_group_report','required_fields':['executive_summary','financial_metrics','bu_totals'],'audience_fields':{'group':['executive_summary','financial_metrics','bu_totals']},'internal_review_required':True}
        template=register_template(self.a,self.c.pk,'Synthetic workbook group report',definition,owner.pk,rev(self.c))
        artifact(self.a,self.c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},owner)
        ref=register_reference(self.a,self.c.pk,'workbook:group-recipient','schema:psl/document-recipient/v1',{'audience':'group','user_id':reader.pk},owner.pk)
        activate(self.a,self.c,'D11.recipient_grant_refs',[ref.ref],owner)
        g={'implementation':'native_selected_items_v1','run_id':r.pk,'run_hash':r.sha256,'rows':['receipt-1'],'fields':['kind','residual','expected_on'],
           'metadata':['currency','basis','as_of'],'recipient_ids':[reader.pk],'reviewer_roles':['Finance'],'publisher_roles':['Finance'],'allow_preparer_review':True,'oracle_evidence_id':1}
        expected=group.project(r.result,g)
        oracle=evidence(self.a,self.c,'forecast_group_oracle',json.dumps(expected));g['oracle_evidence_id']=oracle.pk
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',self.c))[0]);projection['group']=g
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        version=group.draft(self.a,self.c.pk,r.pk,template.pk,rev(self.c))
        group.review(self.a,self.c.pk,version.pk,'Finance','approve','Synthetic exact disclosure',rev(self.c))
        publication=reserve_publication(self.a,self.c.pk,version.pk,rev(self.c));run_publication_once(case_id=self.c.pk,job_id=publication.job.pk)
        receipt=PublicationReceipt.objects.get(publication=publication)
        for secret in ['PRIVATE-CASH','PRIVATE-FORMULA-EXTERNAL-LINK','workbook_comparison','workbook_chain','snapshot','contract']:
            self.assertNotIn(secret,json.dumps(receipt.payload))
        metrics=next(section['text'] for section in receipt.payload['sections'] if section['heading']=='financial_metrics')
        self.assertNotIn('opening',metrics);self.assertNotIn('closing',metrics)
        self.assertFalse(Grant.objects.filter(case=self.c,user=reader,action='finance.read').exists())
