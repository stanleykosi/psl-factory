from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class PrivateProtectionPacket(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 parent=models.OneToOneField('self',null=True,on_delete=models.PROTECT)
 package=models.OneToOneField('documents.ValidationPackage',on_delete=models.PROTECT,related_name='private_protection_packet')
 assessment=models.ForeignKey('workflows.IntegrationAssessment',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 snapshot=models.JSONField()
 sha256=models.CharField(max_length=64)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='private_protection_packet_version')]
