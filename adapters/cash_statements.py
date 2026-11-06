"""Strict supplied statement interchange; human verification is separate from parsing."""
import json
from decimal import localcontext
from datetime import datetime
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.documents.contracts import validate
from apps.finance.rules import decimal
from apps.policy.finance_validators import obj,KEY,DEC

SCHEMA=obj({'source':KEY,'transaction_ref':KEY,'customer':KEY,'amount':{'anyOf':[DEC,{'type':'null'}]},
    'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'amount_basis':KEY,'received_at':{'type':'string'}})

def parse(body):
    if len(body)>10000:raise ValidationError('Cash statement exceeds interchange budget')
    try:value=json.loads(body)
    except ValueError:raise ValidationError('Cash statement must be structured JSON')
    validate(SCHEMA,value)
    if value['amount'] is not None:
        with localcontext() as ctx:
            ctx.prec=512;value['amount']=format(decimal(value['amount'],positive=True).normalize(),'f')
    try:
        at=datetime.fromisoformat(value['received_at'])
        if at.utcoffset() is None or at>timezone.now():raise ValueError
    except ValueError:raise ValidationError('Actual receipt timestamp must be aware and not in the future')
    return value
