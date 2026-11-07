"""Bounded synthetic native fixtures, not process acceptance or live workbook oracles.

TEST is represented by synthetic three-letter TST because the native currency
schema requires three letters. Cell labels in CSV are explicit synthetic source
identifiers, not a claim of XLSX parsing or PSL account mappings.
"""
import json
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.finance import analysis
from apps.finance.models import FinanceRun
from apps.finance.rules import formula_order
from apps.finance.services import capture_import
from apps.policy.services import active_component
from .finance_analysis_helpers import fixture, policy
from .helpers import rev


class FinanceExactCatalogueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.c, cls.e, cls.f, cls.configs, cls.source, _, _ = fixture()

    def maps(self, accounts):
        return [dict(self.f['mapping'][0], key=account, account=account,
                     report_line=account, metric='other', treatment='company',
                     bu=None, pool=None) for account in accounts]

    def configure_maps(self, maps):
        config = policy(self.a, self.c, 'D06.account_bu_maps', maps, self.e['policy_decision'])
        analysis.review(self.a, self.c.pk, 'mapping', config.pk, 'Finance', 'approve',
                        self.e['finance_review'].pk, 'Synthetic exact mapping review', rev(self.c))
        return config

    def imported(self, rows, currency='NGN', locator='synthetic:F03-TB'):
        csv = 'account,amount,currency,period\n' + ''.join(
            f'{account},{amount},{currency},2026-10\n' for account, amount in rows)
        evidence = add_evidence(self.a, self.c.pk, 'financial_input', csv, locator)
        batch = capture_import(self.a, self.c.pk, evidence.pk, rev(self.c))
        return analysis.capture_source(self.a, self.c.pk, batch.pk, 'synthetic-company',
            'accrual', timezone.now()-timedelta(hours=1), 'complete', None,
            self.e['finance_source'].pk, rev(self.c))

    def test_f03_n01_literal_present_zero_and_120_retain_source_rows(self):
        self.configure_maps(self.maps(['A100', 'A200']))
        source = self.imported([('A100', '0'), ('A200', '120')])
        run = analysis.map_source(self.a, self.c.pk, source.pk, [], rev(self.c))
        self.assertEqual(run.result['status'], 'complete')
        self.assertEqual(len(run.result['rows']), 2)
        for row, account, amount, line in zip(run.result['rows'], ['A100','A200'], ['0','120'], [2,3]):
            self.assertEqual((row['account'], row['raw_amount'], row['amount']), (account,amount,amount))
            self.assertEqual((row['source_line'], row['source_evidence']), (line,source.batch.evidence_id))
            self.assertEqual((row['report_line'], row['mapping_key'], row['origin']), (account,account,'import'))
            self.assertEqual(row['findings'], [])
        self.assertFalse(run.result['ledger_posted'])

    def test_f03_e01_conflicting_candidate_rejected_and_unmapped_source_retained(self):
        # Diagnostic boundary, NOT the canonical simultaneous-two-exception report.
        approved = self.configure_maps(self.maps(['A200']))
        source = self.imported([('A300','30'), ('A200','120')])
        candidate = self.maps(['A200'])
        candidate.append(dict(candidate[0], key='conflict', report_line='different'))
        before = FinanceRun.objects.filter(source=source).count()
        with self.assertRaisesMessage(ValidationError, 'Overlapping effective Finance mappings/rules'):
            policy(self.a, self.c, 'D06.account_bu_maps', candidate, self.e['policy_decision'])
        self.assertEqual(active_component('D06.account_bu_maps',self.c).pk, approved.pk)
        self.assertEqual(FinanceRun.objects.filter(source=source).count(), before)
        run = analysis.map_source(self.a,self.c.pk,source.pk,[],rev(self.c))
        self.assertEqual(run.result['status'], 'needs_attention')
        self.assertEqual(len(run.result['rows']),2)
        missing, known = run.result['rows']
        self.assertEqual(missing['findings'], ['Unmapped account'])
        self.assertEqual((missing['account'],missing['amount'],missing['report_line'],missing['mapping_key']),('A300','30',None,None))
        self.assertEqual((known['account'],known['amount'],known['report_line']),('A200','120','A200'))
        for row, line in zip(run.result['rows'],[2,3]):
            self.assertEqual((row['source_line'],row['source_evidence']),(line,source.batch.evidence_id))

    def test_f06_n02_e9_explicit_i3_i13_sum_and_single_scaling(self):
        # Explicit engineering fixture distribution; catalogue supplies only sum 2500.
        rows = [(f'I{i}',value) for i,value in zip(range(3,14),
                ['100','200','300','400','500','250','150','100','200','100','200'])]
        self.configure_maps(self.maps([key for key,_ in rows]))
        policy(self.a,self.c,'D06.unit_sign_currency_period',dict(self.f['conventions'],currency='TST'),self.e['policy_decision'])
        rule = dict(self.f['formulas'][0],key='E9',scope='company_only',
            terms=[{'kind':'line','key':key,'coefficient':'1','value_stage':'base_value'} for key,_ in rows],
            divisor='1000',output_unit='thousands_currency',oracles=[
                {'key':'known','inputs':[{'kind':'line','key':key,'value':value} for key,value in rows],'expected':'2.50'},
                {'key':'unknown','inputs':[{'kind':'line','key':key,'value':None} for key,_ in rows],'expected':None}])
        evidence = add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps(rule['oracles'],sort_keys=True),'synthetic:F06-N02-E9')
        rule['oracle_evidence_id'] = evidence.pk
        policy(self.a,self.c,'D06.rule_oracle_refs',[rule],self.e['policy_decision'])
        source = self.imported(rows,'TST','synthetic:Trial Balance!I3:I13')
        mapping = analysis.map_source(self.a,self.c.pk,source.pk,[],rev(self.c))
        run = analysis.calculate(self.a,self.c.pk,mapping.pk,rev(self.c))
        self.assertEqual(mapping.result['status'],'complete')
        self.assertEqual(run.result['company']['E9']['value'],'2.50')
        self.assertEqual(run.result['currency'],'TST')
        trace = run.result['note_lineage']
        self.assertEqual((trace['mapping_run'],trace['source_id']),(mapping.pk,source.pk))
        self.assertEqual(len(trace['report_lines']),11)
        for index,(key,value) in enumerate(rows):
            item = trace['report_lines'][key]
            self.assertEqual(item['original_total'],value)
            self.assertEqual(len(item['rows']),1)
            row = item['rows'][0]
            self.assertEqual((row['account'],row['amount'],row['source_line'],row['mapping_row_index']), (key,value,index+2,index))
            self.assertEqual(row['source_evidence'],source.batch.evidence_id)
        calc = trace['formulas']['E9']
        self.assertEqual((calc['weighted_numerator'],calc['divisor'],calc['unrounded']),('2500','1000','2.5'))
        self.assertEqual(calc['oracle_evidence_id'],evidence.pk)
        again = dict(rule,key='again',terms=[{'kind':'formula','key':'E9','coefficient':'1','value_stage':'rounded_formula'}])
        with self.assertRaises(ValidationError):
            formula_order([rule,again])
        self.assertFalse(run.result['ledger_posted'])
