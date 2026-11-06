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
from apps.finance import billing
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.services import transition
from .seed_demo import ACTIONS

TITLE='Synthetic Finance service billing preparation'
class Command(BaseCommand):
    help='Create isolated synthetic coverage, usage and pricing via real services. No invoice, accounting or payment effect.'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not actor or Case.objects.filter(tenant='synthetic-demo',title=TITLE).exists():raise CommandError('Requires existing demo actor and fresh synthetic case; refuses overwrite')
        case=Case.objects.create(tenant='synthetic-demo',title=TITLE,kind='service',synthetic=True)
        for action in ACTIONS:Grant.objects.create(case=case,user=actor,action=action)
        def rev():case.refresh_from_db();return case.revision
        def evidence(kind,body):return add_evidence(actor,case.pk,kind,body,'synthetic:billing-demo')
        f=json.loads((settings.BASE_DIR/'fixtures/finance-billing.json').read_text(encoding='utf-8'))
        source=evidence('billing_coverage','Synthetic client/service/contract coverage assertion; partial subset only')
        cov=billing.register_coverage(actor,case.pk,**f['coverage'],evidence_id=source.pk,expected=rev())
        owner=evidence('policy_decision','Synthetic unit price, net-exclusive line tax and rounding demonstration; no operational PSL rule')
        oracle=evidence('billing_oracle',json.dumps(f['arithmetic']['oracles']))
        for component,content in [('D08.effective_price_rule_refs',[dict(f['rule'],coverage_id=cov.pk)]),('D08.tax_tier_rounding_rules',dict(f['arithmetic'],oracle_evidence_id=oracle.pk))]:
            cfg=draft_finance_policy(actor,case.pk,component,content,owner.pk,timezone.now()-timedelta(days=1));transition(actor,cfg.pk,'validated');transition(actor,cfg.pk,'active')
        source=evidence('billing_usage',f['csv'])
        u=billing.capture_usage(actor,case.pk,cov.pk,source.pk,rev(),{'provider_ref':'synthetic-data-team','extracted_at':timezone.now().isoformat(),'completeness':'partial'})
        self.stdout.write(json.dumps({'case':str(case.pk),'coverage':cov.pk,'usage':u.pk,'preparation':'not_recorded','invoice_issued':False}))
