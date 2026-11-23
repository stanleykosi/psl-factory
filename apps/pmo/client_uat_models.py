from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class ClientUATGateBinding(AppendOnly):
    review=models.ForeignKey('pmo.DeliverySourceVerification',on_delete=models.PROTECT,related_name='client_uat_gates')
    verification=models.ForeignKey('pmo.GateVerification',on_delete=models.PROTECT,related_name='client_uat_bindings')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    snapshot=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
