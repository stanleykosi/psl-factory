from django import forms
from apps.identity.models import Grant
from apps.finance.forms import CommandForm
from apps.policy.migration_validators import COMPONENT
from .migration_models import MigrationPlan,MigrationAssessment,MigrationProof
from .validation_models import ValidationPackage
def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
 def ev(kind):return forms.ModelChoiceField(c.evidence.filter(kind=kind))
 def plans():return forms.ModelChoiceField(MigrationPlan.objects.filter(case=c))
 def assessments():return forms.ModelChoiceField(MigrationAssessment.objects.filter(plan__case=c))
 defs={
 'plan':('Capture or revise migration evidence plan','migration.capture',{'reference':forms.CharField(max_length=100),'payload':forms.JSONField(widget=forms.Textarea),'package':forms.ModelChoiceField(ValidationPackage.objects.filter(case=c,private_readiness_packet__isnull=True),required=False),'predecessor':forms.IntegerField(min_value=1,required=False),'evidence':ev('migration_plan')}),
 'proof':('Capture supplied migration report receipt','migration.capture',{'plan':plans(),'evidence':ev('migration_proof')}),
 'inventory':('Read selected local evidence inventory','migration.inventory',{'plan':plans()}),
 'assess':('Assess documentary and inventory readiness','migration.assess',{'plan':plans()}),
 'review':('Review exact migration readiness assessment','migration.review',{'assessment':assessments(),'purpose':forms.ChoiceField(choices=[(x,x) for x in ['owner','independent']]),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['approve','return','reject','withdraw']]),'operation_key':forms.CharField(max_length=100),'evidence':ev('migration_review'),'reason':forms.CharField(max_length=1000)}),
 'bind':('Bind reviewed readiness to exact AF13 package','migration.bind',{'assessment':assessments()}),
 'policy':('Draft D11 migration evidence rules','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()}),
 'investigate':('Investigate migration and acceptance gaps','agent.migration',{})}
 return [{'title':title,'form':type('Migration'+k,(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants]
