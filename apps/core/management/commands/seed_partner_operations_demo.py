import json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,save_draft,transition
from apps.policy.registry import components
from apps.policy.partner_drafts import draft_partner_policy
from apps.policy.partner_validators import STAGES,DEADLINES,ACTIVITY,METER
from apps.baas import partner_operations as domain
from apps.finance import billing
from .seed_demo import ACTIONS

class Command(BaseCommand):
    help='Create an isolated synthetic partner case; no actual renewal, onboarding or invoice effect'
    @transaction.atomic
    def handle(self,*args,**options):
        title='Synthetic partner renewal, onboarding and Finance activity'
        if Case.objects.filter(title=title).exists():raise CommandError('Synthetic partner demo already exists; refusing overwrite')
        a=get_user_model().objects.filter(username='studio-demo',is_active=True).first()
        if not a:raise CommandError('Existing studio-demo principal required')
        c=Case.objects.create(tenant='synthetic-demo',title=title,kind='support',synthetic=True)
        for action in ACTIONS:Grant.objects.create(case=c,user=a,action=action)
        def rev():c.refresh_from_db();return c.revision
        def e(kind,v):return add_evidence(a,c.pk,kind,json.dumps(v) if not isinstance(v,str) else v,'synthetic:partner-demo',rev())
        owner=e('policy_decision','Synthetic dual PM/Finance demo principal, same report reviewer explicitly allowed; not actual business authority')
        refs=[register_reference(a,c.pk,'partner-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':a.pk},owner.pk).ref for role in ['PM','Finance']]
        cfg=save_draft(a,c.pk,{'slot_id':'D05','component_id':'D05.role_principal_assignments','component_schema_ref':components()['D05.role_principal_assignments']['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'service','ref':str(c.pk)},'effective_from':(timezone.now()-timedelta(days=1)).isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(owner.pk)],'human_decision_ref':'evidence:'+str(owner.pk),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test','value':refs});transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        now=timezone.now();period=now.astimezone(__import__('zoneinfo').ZoneInfo('Africa/Lagos')).strftime('%Y-%m');suffix=c.pk.hex[:10]
        cov_e=e('billing_coverage','Synthetic explicit contract/service coverage');cov=billing.register_coverage(a,c.pk,'SYNTHETIC-PARTNER-COVERAGE','synthetic-customer','payments','synthetic-contract','NGN','net_exclusive',period,period,'complete',cov_e.pk,rev())
        f=json.loads((settings.BASE_DIR/'fixtures/partner-operations.json').read_text(encoding='utf-8'));f['activity'].update(recipient_id=a.pk,allow_preparer_review=True);f['meter'].update(coverage_id=cov.pk,partner='synthetic-partner-'+suffix)
        for key,value in [(DEADLINES,f['deadlines']),(STAGES,f['stages']),(ACTIVITY,f['activity']),(METER,f['meter'])]:
            cfg=draft_partner_policy(a,c.pk,key,value,owner.pk,now-timedelta(days=1));transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        partner=f['meter']['partner'];records={};executed=e('signature','Synthetic executed agreement source; no real legal execution')
        values={
          'agreement':{'partner':partner,'customer':'synthetic-customer','contract':'synthetic-contract','starts_on':str(now.date()-timedelta(days=30)),'expires_on':str(now.date()+timedelta(days=3)),'notice_on':str(now.date()+timedelta(days=1)),'auto_renewal':'unknown','clause_reference':'SYNTHETIC-CLAUSE-1','executed_evidence_id':executed.pk,'executed_sha256':executed.sha256},
          'onboarding':{'partner':partner,'customer':'synthetic-customer','tracker':'synthetic-tracker','reported_stage':'review','reported_entry_at':(now-timedelta(hours=5)).isoformat(),'missing_documents':['signed-id']},
          'activity':{'partner':partner,'customer':'synthetic-customer','source':'synthetic-admin','period':period,'extracted_at':now.isoformat(),'completeness':'complete','products':['payments'],'events':[{'event':suffix+'-event-'+str(i),'user':'synthetic-user-'+str(i%2),'product':'payments','kind':'use','at':now.isoformat(),'quantity':str(i)} for i in [1,2,3]]}}
        for kind,value in values.items():
            proof=e('partner_'+kind,value);records[kind]=domain.capture(a,c.pk,kind,kind.upper()+'-001',proof.pk,rev()).pk
        decision=e('partner_decision','Synthetic exact human review/Finance acceptance evidence, no external notice or invoice');stage=e('partner_stage','Synthetic authorised actual stage entry');doc=e('document','Synthetic permitted onboarding document')
        self.stdout.write(json.dumps({'case':str(c.pk),'records':records,'coverage':cov.pk,'decision_evidence':decision.pk,'stage_evidence':stage.pk,'stage_document':doc.pk,'stage_entry_at':(now-timedelta(hours=5)).isoformat(),'owner':a.pk,'dual_role_synthetic_demo':True,'renewal_executed':False,'invoice_created':False}))
