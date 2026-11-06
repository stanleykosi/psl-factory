import json,copy
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
from apps.policy.baas_drafts import draft_baas_policy
from apps.baas.models import SupportCase
from apps.baas import reconciliation as recon
from .seed_demo import ACTIONS

class Command(BaseCommand):
    help='Create fresh synthetic reconciliation sources, policy and unreviewed request evidence; no handoff or financial execution'
    def add_arguments(self,p):p.add_argument('--username',default='studio-demo');p.add_argument('--title',default='Synthetic BaaS reconciliation and Engineering requests')
    @transaction.atomic
    def handle(self,*args,**options):
        a=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not a or Case.objects.filter(tenant='synthetic-demo',title=options['title']).exists():raise CommandError('Requires existing demo actor and fresh title; refuses overwrite')
        c=Case.objects.create(tenant='synthetic-demo',title=options['title'],kind='support',synthetic=True)
        SupportCase.objects.create(case=c,channel='synthetic-reconciliation',external_ref=str(c.pk))
        for action in ACTIONS:Grant.objects.create(case=c,user=a,action=action)
        def rev():c.refresh_from_db();return c.revision
        def e(kind,value):return add_evidence(a,c.pk,kind,json.dumps(value) if not isinstance(value,str) else value,'synthetic:reconciliation-demo',rev())
        owner=e('policy_decision','Synthetic dual-role UI fixture only: one demo principal explicitly holds Finance and Engineering; this does not appoint real humans or authorise financial execution')
        refs=[register_reference(a,c.pk,'demo:role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':a.pk},owner.pk).ref for role in ['Finance','Engineering']]
        config=save_draft(a,c.pk,{'slot_id':'D05','component_id':'D05.role_principal_assignments','component_schema_ref':components()['D05.role_principal_assignments']['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'service','ref':str(c.pk)},'effective_from':timezone.now().isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(owner.pk)],'human_decision_ref':'evidence:'+str(owner.pk),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test','value':refs})
        transition(a,config.pk,'validated');transition(a,config.pk,'active')
        f=json.loads((settings.BASE_DIR/'fixtures/baas-reconciliation.json').read_text(encoding='utf-8'));f['commands']['recipient_id']=a.pk
        # Explicit isolated demo variation; tests exercise distinct real principal references with the fixture's true setting.
        for command in f['commands']['commands']:command['distinct_outcome_verifier']=False
        for key,value in [(recon.CONTRACT,f['contract']),(recon.COMMANDS,f['commands'])]:
            config=draft_baas_policy(a,c.pk,key,value,owner.pk,timezone.now()-timedelta(days=1));transition(a,config.pk,'validated');transition(a,config.pk,'active')
        suffix=c.pk.hex[:12];tx='synthetic-tx-'+suffix;pending='pending-tx-'+suffix;stamp=timezone.now().isoformat();batches={}
        for kind in ['ledger','settlement','queue']:
            rows=[{'partner':'synthetic-partner','transaction':ref,'customer':customer,'currency':'NGN','amount':amount,'status':status if kind=='settlement' else 'reported','account':'client-account','queue_state':'pending' if kind=='queue' else None,'observed_at':stamp} for ref,customer,amount,status in [(tx,'synthetic-customer','100','settled'),(pending,'synthetic-pending-customer','20','pending')]]
            value={'kind':kind,'source':'synthetic-'+kind,'as_of':stamp,'completeness':'complete','partners':['synthetic-partner'],'rows':rows}
            source=e('reconciliation_input',value);batches[kind]=recon.capture(a,c.pk,kind,source.pk,rev())
        attestation=e('reconciliation_attestation',{'batch_sha256':batches['settlement'].evidence.sha256,'source':batches['settlement'].payload['source']})
        v={'partner':'synthetic-partner','transaction':tx,'customer':'synthetic-customer','command':'credit','kind':'corrective_credit','amount':'100','currency':'NGN','from_account':None,'to_account':'client-account','from_state':None,'to_state':None}
        request=e('corrective_request',v);decision=e('corrective_decision','Synthetic exact transaction, correction amount, route and configured human review evidence; no actual customer credit')
        self.stdout.write(json.dumps({'case':str(c.pk),'batches':{k:b.pk for k,b in batches.items()},'attestation_evidence':attestation.pk,'request_evidence':request.pk,'decision_evidence':decision.pk,'operation_key':'SYNTHETIC-CORRECTIVE-'+suffix,'delivered':False,'financial_execution':False,'dual_role_synthetic_demo':True}))
