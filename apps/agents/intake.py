"""Bounded intake triage: current granted duplicates and missing next steps."""
from apps.identity.intake import investigate as inspect

def investigate(actor,case_id):
    return {'capability':'A01 intake triage','process_ids':['P03','P16'],**inspect(actor,case_id)}
