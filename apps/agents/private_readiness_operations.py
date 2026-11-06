"""Private operator investigation and typed planning, never approval or recovery effects."""
from django.db import transaction
from apps.workflows import private_readiness_operations as domain
from apps.workflows import protection
from apps.workflows.operator_recovery import locked

def investigate(a,case_id):return domain.investigate(a,case_id)

@transaction.atomic
def prepare(a,case_id,reference,payload,evidence_id,expected=None,predecessor=None):
 locked(a,case_id,'agent.operations',expected)
 return protection.capture_plan(a,case_id,reference,payload,evidence_id,None,predecessor)
