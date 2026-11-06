"""Bounded private evidence planning and typed packet preparation; no human decisions."""
from django.db import transaction
from apps.identity.services import require
from apps.finance import readiness_acceptance as domain

def investigate(actor,case_id):return domain.investigate(actor,case_id)

@transaction.atomic
def prepare(actor,case_id,assessment_id,package_id,reference,predecessor=None,expected=None):
 case=domain.af.locked(actor,case_id,'agent.validation',expected)
 require(actor,case,'validation.package.prepare')
 return domain.prepare(actor,case_id,assessment_id,package_id,reference,predecessor)
