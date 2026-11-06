"""Live evidence investigation and typed package binding; no decision/effect tools."""
from django.db import transaction
from apps.documents import protection_acceptance as domain

def investigate(a,case_id):return domain.investigate(a,case_id)

@transaction.atomic
def prepare(a,case_id,assessment_id,package_id,reference,predecessor=None,expected=None,native_kind="restore"):
 domain.af.locked(a,case_id,'agent.validation',expected)
 return domain.prepare(a,case_id,assessment_id,package_id,reference,predecessor,None,native_kind)
