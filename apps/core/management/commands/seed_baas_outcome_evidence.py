from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from apps.core.services import add_evidence
from apps.baas.models import CorrectiveDelivery,EngineeringOutcome
import json

class Command(BaseCommand):
    help='Create supplied synthetic Engineering outcome/proof evidence after a real local request receipt; does not record or verify an outcome'
    def add_arguments(self,p):p.add_argument('--receipt',required=True,type=int);p.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        a=get_user_model().objects.filter(username=options['username'],is_active=True).first();d=CorrectiveDelivery.objects.select_related('request__case','job').filter(pk=options['receipt'],request__case__synthetic=True).first()
        if not a or not d or EngineeringOutcome.objects.filter(delivery=d).exists():raise CommandError('Requires explicit synthetic receipt with no prior reported outcome')
        v={'operation_key':d.operation_key,'request_hash':d.payload['request_hash'],'source':d.job.intent['execution_source'],'external_reference':'SYNTHETIC-ENGINEERING-RESULT-'+str(d.pk),'status':'applied','observed_at':timezone.now().isoformat(),'command':d.payload['command']}
        e=add_evidence(a,d.request.case_id,'engineering_outcome',json.dumps(v),'synthetic:engineering-result-fixture')
        proof=add_evidence(a,d.request.case_id,'engineering_outcome_verification',json.dumps(v),'synthetic:independent-result-fixture')
        self.stdout.write(json.dumps({'receipt':d.pk,'outcome_evidence':e.pk,'verification_evidence':proof.pk,'source_authenticity':'synthetic_fixture_only','recorded':False,'verified':False,'financial_execution':False}))
