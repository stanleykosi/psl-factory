from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class Issue(models.Model):
    tenant=models.CharField(max_length=100)
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=160)
    current=models.ForeignKey('IssueState',null=True,on_delete=models.PROTECT,related_name='+')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['tenant','reference'],name='authoritative_issue_identity')]


class IssueState(AppendOnly):
    def __str__(self):return f'{self.issue.reference} · state #{self.pk} · {self.status}'
    issue=models.ForeignKey(Issue,on_delete=models.PROTECT,related_name='states')
    number=models.PositiveIntegerField()
    title=models.CharField(max_length=240)
    kind=models.CharField(max_length=100)
    severity=models.CharField(max_length=20,null=True)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    next_action=models.CharField(max_length=1000)
    status=models.CharField(max_length=20)
    acknowledged_at=models.DateTimeField(null=True)
    resolved_at=models.DateTimeField(null=True)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    fix=models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT,related_name='+')
    root_cause=models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT,related_name='+')
    external_links=models.JSONField(default=list)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['issue','number'],name='issue_state_revision')]


class IssueClosureEntry(AppendOnly):
    state=models.ForeignKey(IssueState,on_delete=models.PROTECT,related_name='closure_entries')
    role=models.CharField(max_length=20)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['state','role'],name='issue_closure_log_role')]
