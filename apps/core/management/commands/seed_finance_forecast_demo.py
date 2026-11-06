"""Adds isolated synthetic forecast records to a named existing synthetic Finance case."""
import json
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import active_component,reference_values,resolve,register_reference,transition
from apps.policy.finance_drafts import draft_finance_policy
from apps.documents.controlled import register_template
from apps.finance.models import ForecastScenario,InvoiceIssue
from apps.finance import forecast,cash
from .seed_demo import ACTIONS

class Command(BaseCommand):
    help='Add synthetic forecast inputs, pending actual and report configuration to a named synthetic case; no review/publication or money execution'
    def add_arguments(self,p):p.add_argument('--case',required=True);p.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        a=get_user_model().objects.filter(username=options['username'],is_active=True).first();case=Case.objects.filter(pk=options['case'],synthetic=True).first()
        if not a or not case or ForecastScenario.objects.filter(case=case).exists():raise CommandError('Requires existing demo actor, exact synthetic case and no prior forecast; refuses overwrite')
        for action in ACTIONS:Grant.objects.get_or_create(case=case,user=a,action=action,defaults={'active':True})
        for audience in ['internal','management']:Grant.objects.get_or_create(case=case,user=a,action='document.receive:'+audience)
        def rev():case.refresh_from_db();return case.revision
        def e(kind,value):return add_evidence(a,case.pk,kind,json.dumps(value) if not isinstance(value,str) else value,'synthetic:forecast-demo',rev())
        owner=e('policy_decision','Synthetic forecast authority, finite method, aggregate projections and local recipients; not actual owner policy')
        def policy(key,value):
            c=draft_finance_policy(a,case.pk,key,value,owner.pk,timezone.now()-timedelta(days=1));transition(a,c.pk,'validated');transition(a,c.pk,'active');return c
        f=json.loads((settings.BASE_DIR/'fixtures/finance-forecast.json').read_text(encoding='utf-8'))
        matrix=reference_values(active_component('D05.decision_action_matrix',case))[0]
        matrix.setdefault('finance',[]);matrix['finance'] += [{'purpose':p,'role':'Finance','actions':['approve','return','reject'],'allow_preparer_review':True} for p in ['forecast','forecast_rollover','forecast_priority']]
        policy('D05.decision_action_matrix',matrix)
        oracle=e('forecast_oracle',f['method']['oracles']);policy(forecast.METHOD,dict(f['method'],oracle_evidence_id=oracle.pk))
        existing=resolve('D10.audience_projection_rules',case);projection=dict(f['projection'])
        if existing.status=='ACTIVE':projection.update(reference_values(existing.configuration)[0])
        policy('D10.audience_projection_rules',projection)
        today=timezone.localdate();month=today.strftime('%Y-%m');n=today.year*12+today.month;following=f'{n//12:04}-{n%12+1:02}'
        opening={'account':'synthetic-operating-account','amount':'100','observed_on':today.isoformat(),'cutoff':'start_of_day'};o=e('forecast_opening',opening)
        source=e('document','Synthetic inflow selection and recurring spending assumption; no expense/payment approval')
        issue=InvoiceIssue.objects.filter(invoice__case=case).first()
        if not issue:raise CommandError('Seed requires a proven synthetic invoice to demonstrate corrected receivable lineage')
        value={'entity':'synthetic-company','currency':issue.invoice.currency,'basis':'gross_cash','as_of':today.isoformat(),'months':[month,following],
            'coverage':{'accounts':[opening['account']],'inflows':'partial','outflows':'partial','omissions':['Synthetic selected-account scenario only; native company/group inventories and bank authenticity are absent']},
            'openings':[dict(opening,evidence_id=o.pk)],'items':[
            {'key':'client-receipt','kind':'receivable','source_ref':'invoice-'+str(issue.pk),'owner':'synthetic-finance','amount':str(cash.open_amount(issue)),'expected_on':today.isoformat(),'original_due':issue.invoice.due_date.isoformat() if issue.invoice.due_date else None,'issue_id':issue.pk,'evidence_id':source.pk,'commitment':'forecast_only'},
            {'key':'recurring-outflow','kind':'outflow','source_ref':'synthetic-outflow-1','owner':'synthetic-requester','amount':'10','expected_on':today.isoformat(),'original_due':today.isoformat(),'issue_id':None,'evidence_id':source.pk,'commitment':'reported_commitment'}],'rollover':[]}
        inputs=e('forecast_input',value);s=forecast.capture(a,case.pk,'SYNTHETIC-FORECAST-001',inputs.pk,'Synthetic selected corrected receivable and explicit spending scenario',rev())
        report={'entity':value['entity'],'account':opening['account'],'currency':value['currency'],'basis':value['basis'],'source':'synthetic-cash-export','transaction':'SYNTHETIC-ACTUAL-001','direction':'outflow','amount':'5','occurred_on':today.isoformat()}
        reported=e('forecast_actual',report);actual=forecast.capture_actual(a,case.pk,reported.pk,rev());verified=e('forecast_actual_verification',report)
        review=e('forecast_review','Synthetic current forecast/priorities review and explicit scenario coverage');match=e('forecast_match','Synthetic explicit partial actual-to-outflow assumption match')
        definition={'document_type':'finance_report','required_fields':['executive_summary','financial_metrics','bu_totals'],'audience_fields':{k:['executive_summary','financial_metrics','bu_totals'] for k in ['internal','management']},'internal_review_required':False}
        t=register_template(a,case.pk,'Synthetic cash forecast',definition,owner.pk,rev())
        storage=resolve('D11.template_storage_retention_rules',case);stored=reference_values(storage.configuration)[0] if storage.status=='ACTIVE' else {'template_ids':[],'repository':'internal-versioned','retention_days':30}
        stored['template_ids'].append(t.pk)
        def activate_value(component,value):
            from apps.policy.services import save_draft
            from apps.policy.registry import components
            config=save_draft(a,case.pk,{'slot_id':component.split('.')[0],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'service','ref':str(case.pk)},'effective_from':timezone.now().isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(owner.pk)],'human_decision_ref':'evidence:'+str(owner.pk),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test','value':value})
            transition(a,config.pk,'validated');transition(a,config.pk,'active')
        r=register_reference(a,case.pk,'forecast-demo:storage','schema:psl/document-storage/v2' if 'closure_inventory' in stored else 'schema:psl/document-storage/v1',stored,owner.pk)
        activate_value('D11.template_storage_retention_rules',{'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref})
        old=resolve('D11.recipient_grant_refs',case);refs=list(old.configuration.envelope['value']) if old.status=='ACTIVE' else []
        for audience in ['internal','management']:
            refs.append(register_reference(a,case.pk,'forecast-demo:recipient:'+audience,'schema:psl/document-recipient/v1',{'audience':audience,'user_id':a.pk},owner.pk).ref)
        activate_value('D11.recipient_grant_refs',list(dict.fromkeys(refs)))
        self.stdout.write(json.dumps({'case':str(case.pk),'scenario':s.pk,'actual':actual.pk,'verification_evidence':verified.pk,'match_evidence':match.pk,'review_evidence':review.pk,'template':t.pk,'reviewed':False,'published':False}))
