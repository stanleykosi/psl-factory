"""Live private capability investigation and typed contract preparation; no effects/decisions."""
from django.db import transaction
from apps.workflows import readiness as domain,private_file_readiness as private

def investigate(actor,case):return private.investigate(actor,case)

@transaction.atomic
def prepare(actor,case_id,reference,payload,evidence_id,job_id,expected=None,predecessor=None):
 domain.locked(actor,case_id,'agent.integrations',expected)
 return domain.capture(actor,case_id,reference,payload,evidence_id,predecessor=predecessor,native_file_job=job_id)
