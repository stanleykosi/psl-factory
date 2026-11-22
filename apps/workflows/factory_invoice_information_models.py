from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class InvoiceMilestoneProof(AppendOnly):
    work = models.ForeignKey('workflows.FactoryWork', on_delete=models.PROTECT)
    task = models.ForeignKey('workflows.HumanTask', on_delete=models.PROTECT)
    handoff = models.ForeignKey('finance.Handoff', on_delete=models.PROTECT)
    upload = models.ForeignKey('agents.CaseUpload', on_delete=models.PROTECT)
    evidence = models.OneToOneField('core.Evidence', on_delete=models.PROTECT)
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.UUIDField()
    note = models.CharField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['task', 'operation'], name='invoice_proof_operation'),
            models.UniqueConstraint(fields=['task'], condition=models.Q(previous__isnull=True), name='invoice_proof_root'),
        ]
        indexes = [models.Index(fields=['work', '-id'], name='invoice_proof_work_head')]
