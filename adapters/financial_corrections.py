"""Supplied legal-note and corrected-statement interchange, not remote legal/bank authenticity."""
import json
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from apps.policy.finance_validators import obj,KEY,DEC
from adapters.cash_statements import parse as parse_statement

NOTE=obj({'document_ref':KEY,'invoice_reference':KEY,'kind':{'enum':['credit','debit','void']},'amount':{'anyOf':[DEC,{'type':'null'}]},
    'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'amount_basis':{'const':'gross_including_tax'}})

def parse_note(body):
    if len(body)>10000:raise ValidationError('Correction note exceeds supplied-document budget')
    try:value=json.loads(body)
    except ValueError:raise ValidationError('Supply a structured correction note')
    validate(NOTE,value);return value

def parse_successor(body):return parse_statement(body)


def lookup(job):
    from apps.finance.models import InvoiceCorrectionAcceptance,InvoiceCorrectionDelivery
    from apps.finance.billing import digest
    from apps.finance.corrections import public_payload
    model=InvoiceCorrectionAcceptance if job.kind=='adjust' else InvoiceCorrectionDelivery
    receipt=model.objects.filter(correction_id=job.intent['correction'],correction__issue__invoice=job.invoice).first()
    if receipt:
        if receipt.sha256!=digest(receipt.payload):raise ValidationError('Immutable correction receipt hash mismatch')
        if job.kind=='adjust_deliver':
            accepted=InvoiceCorrectionAcceptance.objects.get(correction=receipt.correction)
            if receipt.payload!=public_payload(accepted) or receipt.recipient_id!=job.intent['recipient']:raise ValidationError('Correction receipt payload/destination mismatch')
    return receipt
