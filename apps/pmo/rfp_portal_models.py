from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class RFPPortalReceipt(AppendOnly):
    submission = models.OneToOneField('pmo.RFPSubmission', on_delete=models.PROTECT, related_name='portal_receipt')
    review = models.ForeignKey('documents.ControlledReview', on_delete=models.PROTECT)
    evidence = models.OneToOneField('core.Evidence', on_delete=models.PROTECT)
    reference = models.CharField(max_length=160)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
