from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event
from apps.documents.contracts import digest
from apps.policy.services import resolve,reference_values
from .delivery import dossier_for,latest
from .delivery_closure import hypercare_inputs,latest_go_live
from .clocks import aware
from .models import DeliverySignal,DeliveryDossier,DeliveryScanCursor


@transaction.atomic
def scan_delivery(actor,case_id,dossier_id):
    case=lock_case(actor,case_id,'delivery.manage');d=dossier_for(case,dossier_id,current=False)
    outcome=latest(d,'release_outcome',False)
    if not outcome or latest(d,'closure',False):return []
    r=resolve('D11.hypercare_criteria_ref',case)
    source={'outcome_id':outcome.pk,'policy':[r.status,r.configuration.pk if r.configuration else None],
        'source_ids':list(d.sources.filter(kind__startswith='hypercare_').order_by('pk').values_list('pk',flat=True)[:101]),
        'acceptance_id':latest_go_live(d,False).pk if latest_go_live(d,False) else None}
    if len(source['source_ids'])>100:raise ValidationError('Hypercare scan exceeds bounded source budget')
    if r.status!='ACTIVE':kind='hypercare_policy_missing';snapshot={'source':source,'findings':[r.component+': '+r.status]}
    else:
        due=aware(outcome.data['released_at'])+timedelta(hours=reference_values(r.configuration)[0]['minimum_hours'])
        if timezone.now()<due:return []
        try:
            dossier_for(case,d.pk);evaluation=hypercare_inputs(d)
            if evaluation['qualified'] is True:return []
            findings=evaluation['findings']
        except (ValidationError,PermissionDenied) as exc:findings=[str(exc)]
        kind='hypercare_due';snapshot={'source':source,'due_at':due.isoformat(),'findings':findings}
    signal,created=DeliverySignal.objects.get_or_create(dossier=d,kind=kind,source_key=digest(source),defaults={'snapshot':snapshot})
    if created:event(actor,case,'delivery.obligation_signal',signal=signal.pk,dossier=d.pk,kind=kind)
    return [signal] if created else []


@transaction.atomic
def scan_due(limit=100):
    if type(limit) is not int or not 1<=limit<=1000:raise ValidationError('Delivery scan limit must be 1–1000')
    cursor,_=DeliveryScanCursor.objects.get_or_create(name='delivery-hypercare-v1')
    cursor=DeliveryScanCursor.objects.select_for_update().get(pk=cursor.pk)
    rows=list(DeliveryDossier.objects.filter(pk__gt=cursor.last_dossier_id).select_related('actor').order_by('pk')[:limit])
    if not rows and cursor.last_dossier_id:
        cursor.last_dossier_id=0;rows=list(DeliveryDossier.objects.select_related('actor').order_by('pk')[:limit])
    total=0
    for d in rows:
        try:
            with transaction.atomic():total+=len(scan_delivery(d.actor,d.case_id,d.pk))
        except (ValidationError,PermissionDenied):pass
        cursor.last_dossier_id=d.pk
    cursor.save(update_fields=['last_dossier_id']);return total
