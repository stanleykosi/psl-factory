from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class ProjectIdentityDecision(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT,related_name='+')
    other_case=models.ForeignKey('core.Case',on_delete=models.PROTECT,related_name='+')
    relation=models.CharField(max_length=20,choices=[('alias','Alias of target'),('distinct','Distinct engagement'),('unresolved','Still unresolved')])
    operation_key=models.CharField(max_length=100)
    data=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    other_evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','operation_key'],name='project_identity_decision_key'),
            models.CheckConstraint(condition=~models.Q(case=models.F('other_case')),name='project_identity_distinct_cases'),
            models.CheckConstraint(condition=models.Q(relation__in=['alias','distinct','unresolved']),name='project_identity_relation')]
