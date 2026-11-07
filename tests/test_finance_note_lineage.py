"""Synthetic catalogue arithmetic/provenance, not whole-process owner acceptance."""
import json
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.services import add_evidence
from apps.finance import analysis
from apps.finance.services import capture_import
from apps.finance.documents import projection_rows
from apps.agents.finance_analysis import investigate_finance
from .finance_analysis_helpers import fixture, policy, declared_units
from .helpers import rev


class FinanceNoteLineageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a,cls.c,cls.e,cls.f,cls.configs,cls.source,cls.template,cls.recipient=fixture()

    def golden(self, values, terms, divisor='1', unit='major_currency', expected='0', source_rows=None):
        maps=[]
        for key in values:
            maps.append(dict(self.f['mapping'][0],key=key,account=key,report_line=key,metric='other',treatment='company',bu=None,pool=None,source_rows='preserve_explicit_rows'))
        policy(self.a,self.c,'D06.account_bu_maps',maps,self.e['policy_decision'])
        rule=dict(self.f['formulas'][0],key='note',scope='company_only',terms=[{'kind':'line','key':key,'coefficient':coefficient,'value_stage':'base_value'} for key,coefficient in terms],divisor=divisor,output_unit=unit)
        rule['oracles']=[{'key':'known','inputs':[{'kind':'line','key':key,'value':values[key]} for key,_ in terms],'expected':expected},
                         {'key':'unknown','inputs':[{'kind':'line','key':key,'value':None} for key,_ in terms],'expected':None}]
        oracle=add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps(rule['oracles'],sort_keys=True),'synthetic:catalogue-note-golden')
        rule['oracle_evidence_id']=oracle.pk
        policy(self.a,self.c,'D06.rule_oracle_refs',[rule],self.e['policy_decision'])
        csv='account,amount,currency,period\n'+''.join(f'{key},{value or ""},NGN,2026-10\n' for key,value in values.items())
        if source_rows is not None:
            csv='account,amount,currency,period\n'+''.join(f'{key},{value},NGN,2026-10\n' for key,value in source_rows)
        evidence=add_evidence(self.a,self.c.pk,'financial_input',csv,'synthetic:catalogue-cells')
        batch=capture_import(self.a,self.c.pk,evidence.pk,rev(self.c))
        units=declared_units(self.a,self.c,batch)
        source=analysis.capture_source(self.a,self.c.pk,batch.pk,'synthetic-company','accrual',timezone.now()-timedelta(hours=1),'complete',None,self.e['finance_source'].pk,rev(self.c),unit_declaration=units)
        mapping=analysis.map_source(self.a,self.c.pk,source.pk,[],rev(self.c))
        return mapping,analysis.calculate(self.a,self.c.pk,mapping.pk,rev(self.c))

    def test_f04_n02_movement_is_valid_subtraction_and_not_close_approval(self):
        m,r=self.golden({'I95':'120','K95':'100'},[('I95','1'),('K95','-1')],expected='20')
        self.assertEqual(r.result['company']['note']['value'],'20.00')
        self.assertEqual(r.result['note_lineage']['formulas']['note']['weighted_numerator'],'20')
        self.assertTrue(analysis.certification_findings(r))
        self.assertFalse(r.result['ledger_posted'])

    def test_f04_n02_explicit_total_population(self):
        values=['10','20','-5']+['0']*165
        m,r=self.golden({'G3_G170':'25'},[('G3_G170','1')],expected='25',
                        source_rows=[('G3_G170',value) for value in values])
        self.assertEqual(r.result['company']['note']['value'],'25.00')
        rows=r.result['note_lineage']['report_lines']['G3_G170']['rows']
        self.assertEqual(len(rows),168)
        self.assertEqual([row['amount'] for row in rows],values)

    def test_f05_n01_note_retains_both_account_rows(self):
        m,r=self.golden({'A1':'100','A2':'40'},[('A1','1'),('A2','1')],expected='140')
        self.assertEqual(r.result['company']['note']['value'],'140.00')
        lineage=r.result['note_lineage']
        self.assertEqual(lineage['mapping_run'],m.pk)
        self.assertEqual(lineage['report_lines']['A2']['original_total'],'40')
        self.assertEqual(lineage['report_lines']['A2']['rows'][0]['source_evidence'],m.source.batch.evidence_id)
        self.assertEqual(lineage['report_lines']['A2']['rows'][0]['mapping_row_index'],1)

    def test_f06_n01_n02_base_display_and_no_second_scaling(self):
        from apps.finance.rules import formula_order
        for base,expected in [('2000','2'),('2500','2.5')]:
            m,r=self.golden({'asset':base},[('asset','1')],'1000','thousands_currency',expected)
            trace=r.result['note_lineage']['formulas']['note']
            self.assertEqual(trace['weighted_numerator'],base)
            self.assertEqual(trace['divisor'],'1000')
            self.assertEqual(trace['unrounded'],expected)
            self.assertEqual(trace['display_unit'],'thousands_currency')
            from apps.policy.services import reference_values,active_component
            rule=reference_values(active_component('D06.rule_oracle_refs',self.c))[0]
            downstream=dict(rule,key='again',terms=[{'kind':'formula','key':'note','coefficient':'1','value_stage':'rounded_formula'}])
            with self.assertRaises(ValidationError):formula_order([rule,downstream])

    def test_f04_n01_adjustment_and_successor_lineage(self):
        a=analysis.adjustment(self.a,self.c.pk,self.source.pk,'ADJ-1','additive',[{'account':'sales','amount':'25'}],self.e['finance_adjustment'].pk,'Synthetic adjustment',rev(self.c))
        analysis.review(self.a,self.c.pk,'adjustment',a.pk,'Finance','approve',self.e['finance_review'].pk,'Reviewed',rev(self.c))
        m=analysis.map_source(self.a,self.c.pk,self.source.pk,[a.pk],rev(self.c));r=analysis.calculate(self.a,self.c.pk,m.pk,rev(self.c))
        line=r.result['note_lineage']['report_lines'][m.result['rows'][0]['report_line']]
        self.assertEqual((line['original_total'],line['adjustment_total'],line['adjusted_total']),('-1000','25','-975'))
        self.assertEqual(r.result['note_lineage']['adjustments'][0]['reference'],'ADJ-1')
        self.assertEqual(r.result['note_lineage']['adjustments'][0]['revision'],1)
        analysis.adjustment(self.a,self.c.pk,self.source.pk,'ADJ-1','additive',[{'account':'sales','amount':'30'}],self.e['finance_adjustment'].pk,'Replacement',rev(self.c))
        with self.assertRaises(ValidationError):analysis.ensure_current(r)

    def test_private_ui_and_aggregate_agent_projection_do_not_expand(self):
        m=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c));r=analysis.calculate(self.a,self.c.pk,m.pk,rev(self.c))
        self.assertEqual(r.snapshot['formula_result_implementation'],'finance-note-lineage/v1')
        self.assertNotIn('formula_result_implementation',m.snapshot)
        self.assertEqual(r.pk,analysis.calculate(self.a,self.c.pk,m.pk,rev(self.c)).pk)
        agent=investigate_finance(self.a,self.c.pk,r.pk,rev(self.c))
        self.assertNotIn('note_lineage',agent.result)
        self.assertNotIn('calculation_provenance',json.dumps(agent.result['company_metrics']))
        projection={'include_company':True,'formula_keys':list(r.result['company']),'bu_keys':[]}
        self.assertNotIn('note_lineage',projection_rows(r,projection))
        self.client.force_login(self.a)
        self.assertContains(self.client.get(f'/cases/{self.c.pk}/finance/'),'Company note source and presentation lineage')
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(f'/cases/{self.c.pk}/finance/').status_code,404)

    def test_unknown_and_rounding_provenance(self):
        m,r=self.golden({'asset':'2501'},[('asset','1')],'1000','thousands_currency','2.50')
        trace=r.result['note_lineage']['formulas']['note']
        self.assertEqual((trace['unrounded'],trace['display_value'],trace['rounding_difference']),('2.501','2.50','0.001'))
        m,r=self.golden({'asset':'2501'},[('asset','1')],'1000','thousands_currency','2.50',source_rows=[('asset','')])
        self.assertIsNone(r.result['note_lineage']['report_lines']['asset']['original_total'])
        self.assertIsNone(r.result['note_lineage']['formulas']['note']['weighted_numerator'])
        self.assertIsNone(r.result['company']['note']['value'])

    def test_old_formula_snapshot_cannot_reuse_missing_lineage(self):
        from apps.finance.mapping import calculate_formulas
        m=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c))
        snapshot,configs=analysis.stage_snapshot(self.a,self.source,'formula',m,{})
        snapshot.pop('formula_result_implementation')
        result=calculate_formulas(m,configs['D06.rule_oracle_refs']);result.pop('note_lineage')
        old=analysis.store(self.a,self.c,self.source,'formula',m,{},snapshot,result)
        new=analysis.calculate(self.a,self.c.pk,m.pk,rev(self.c))
        self.assertNotEqual(old.pk,new.pk)
        self.assertIn('note_lineage',new.result)
        with self.assertRaises(ValidationError):analysis.ensure_current(old)
