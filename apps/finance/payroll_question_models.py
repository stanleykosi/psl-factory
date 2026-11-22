from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class PayrollReportQuestion(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    publication=models.ForeignKey('finance.PayrollPublication',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    operation_key=models.UUIDField(unique=True)
    packet=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)


class PayrollReportQuestionEvent(AppendOnly):
    question=models.ForeignKey(PayrollReportQuestion,on_delete=models.PROTECT,related_name='events')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    kind=models.CharField(max_length=20)
    data=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['question','kind'],name='payroll_question_event_once')]
