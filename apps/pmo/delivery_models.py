from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

RECORD_KINDS=['planning_decision','kickoff','progress','glpi_request','release_ready','release_outcome',
    'go_live','hypercare','archive','handover','finance_confirmation','closure_decision','closure','go_live_reaffirmation']
GO_LIVE_KINDS=['go_live','go_live_reaffirmation']


class DeliveryDossier(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    candidate=models.OneToOneField('pmo.DeliveryCandidate',on_delete=models.PROTECT)
    baseline=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'#{self.pk} · {self.candidate.reference}'


class DeliverySource(AppendOnly):
    dossier=models.ForeignKey(DeliveryDossier,on_delete=models.PROTECT,related_name='sources')
    kind=models.CharField(max_length=40)
    external_ref=models.CharField(max_length=240)
    payload=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class DeliverySourceVerification(AppendOnly):
    source=models.ForeignKey(DeliverySource,on_delete=models.PROTECT,related_name='verifications')
    adapter=models.CharField(max_length=100)
    result=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class DeliveryRecord(AppendOnly):
    dossier=models.ForeignKey(DeliveryDossier,on_delete=models.PROTECT,related_name='records')
    kind=models.CharField(max_length=30,choices=[(x,x) for x in RECORD_KINDS])
    parent=models.ForeignKey('self',null=True,on_delete=models.PROTECT,related_name='children')
    data=models.JSONField()
    snapshot=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(kind__in=RECORD_KINDS),name='delivery_known_record_kind'),
            *[models.UniqueConstraint(fields=['dossier','kind'],condition=models.Q(kind=k),name='delivery_once_'+k)
                for k in ['release_outcome','go_live','closure']],
            models.UniqueConstraint(fields=['parent'],condition=models.Q(kind='go_live_reaffirmation'),name='delivery_go_live_reaffirmation_parent')]
    def __str__(self):return f'#{self.pk} · {self.kind} · dossier #{self.dossier_id}'


class DeliveryDocumentBinding(AppendOnly):
    version=models.OneToOneField('documents.Version',on_delete=models.PROTECT)
    dossier=models.ForeignKey(DeliveryDossier,on_delete=models.PROTECT)
    purpose=models.CharField(max_length=20)
    snapshot=models.JSONField()
    data=models.JSONField()


class DeliverySignal(AppendOnly):
    dossier=models.ForeignKey(DeliveryDossier,on_delete=models.PROTECT,related_name='signals')
    kind=models.CharField(max_length=30)
    source_key=models.CharField(max_length=64)
    snapshot=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['dossier','kind','source_key'],name='delivery_signal_once')]


class DeliveryScanCursor(models.Model):
    name=models.CharField(max_length=40,unique=True)
    last_dossier_id=models.BigIntegerField(default=0)
