"""Bounded configured work: fixed public canary only, never private-evidence extraction."""
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.workflows import readiness as d,readiness_delivery as w
from apps.workflows.readiness_models import IntegrationSelection
@transaction.atomic
def canary(a,case_id,key,expected=None):
 c=d.locked(a,case_id,'integration.probe',expected)
 if not d.gate(c,'provider'):raise ValidationError('Explicit reviewed provider enrollment required')
 selected=IntegrationSelection.objects.filter(case=c,family='provider').order_by('-version').first()
 return w.reserve(a,c.pk,selected.contract_id,key,'evaluation')
