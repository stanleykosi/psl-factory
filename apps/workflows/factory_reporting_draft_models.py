from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class WeeklyReportDraftVersion(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    work = models.ForeignKey('workflows.FactoryWork', null=True, on_delete=models.PROTECT,
                             related_name='weekly_edit_drafts')
    source_head = models.ForeignKey('core.Evidence', null=True, on_delete=models.PROTECT)
    return_review = models.ForeignKey('documents.ControlledReview', null=True, on_delete=models.PROTECT)
    submitted_work = models.ForeignKey('workflows.FactoryWork', null=True, on_delete=models.PROTECT,
                                       related_name='weekly_submitted_drafts')
    values = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['case', 'author', 'work', '-id'], name='weekly_draft_head')]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(work__isnull=True, source_head__isnull=True, return_review__isnull=True)
                           | models.Q(work__isnull=False, source_head__isnull=False, return_review__isnull=False)),
                name='weekly_draft_exact_basis',
            ),
        ]
